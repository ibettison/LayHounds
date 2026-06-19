import asyncio
import logging
import math
import random
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from betfair_client import betfair, BetfairError
from db import db
from licence_client import LICENCE_SERVER_URL, is_licence_active
from models import LayBet, Race, RecoveryChain, Session, SessionConfig
from services.racing import (
    doc_to_session,
    fetch_live_race,
    generate_race,
    get_runner_by_rank,
    pick_winner,
    session_to_doc,
)
from services.backtest_analysis import (
    build_analysis_csv,
    generated_race_snapshots,
    session_race_snapshots,
)
from services.favourite_risk import favourite_risk_bet_plan, format_skip_reasons
from services.historical_replay import next_historical_replay_race
from services.recovery import apply_settled_bet_to_chain, plan_recovery_bet
from services.settlement import reconcile_live_settlements
from services.session_status import apply_stop_conditions
from session_events import (
    clear_session as sse_clear_session,
    format_sse,
    publish as sse_publish,
    subscribe as sse_subscribe,
)

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


def _remaining_stop_loss_budget(session: Session) -> Optional[float]:
    if session.config.stop_loss <= 0:
        return 0.0
    return round(max(session.config.stop_loss + session.total_pnl, 0.0), 4)


def _floor_money(value: float) -> float:
    return math.floor(max(value, 0.0) * 10000) / 10000


def _has_unsettled_live_recovery_bet(session: Session, rank: int) -> bool:
    """True when a live recovery bet for this rank is still awaiting Betfair settlement."""
    for race in session.races:
        if race.source != "live":
            continue
        for bet in race.bets:
            if bet.favourite_rank != rank:
                continue
            if bet.recovery_level <= 0:
                continue
            if not bet.betfair_bet_id or not bet.matched_size:
                continue
            if not bet.settled_at and not bet.result:
                return True
    return False


@router.get("/")
async def root():
    return {"message": "Greyhound Lay Simulator API"}


@router.post("/sessions", response_model=Session)
async def create_session(config: SessionConfig):
    if config.mode in ("paper_live", "live"):
        if not betfair.is_configured():
            raise HTTPException(400, "Betfair credentials not configured on server")
        # Licence gate — only checked if this install is wired to a licence server.
        if LICENCE_SERVER_URL:
            allowed, reason = await is_licence_active(db)
            if not allowed:
                raise HTTPException(402, f"Live Unlock required: {reason}")
    if config.mode == "live" and not config.risk_accepted:
        raise HTTPException(400, "Live mode requires explicit risk acceptance")

    # For paper_live + live, the bank tracks the REAL Betfair available balance.
    # Override the user-supplied starting_bank with the live value so the UI is honest.
    starting_bank = config.starting_bank
    if config.mode in ("paper_live", "live"):
        try:
            funds = await betfair.get_account_funds()
            starting_bank = round(float(funds.get("availableToBetBalance", 0.0) or 0.0), 2)
        except BetfairError as e:
            raise HTTPException(502, f"Could not fetch Betfair balance: {e}")
        except Exception as e:
            # Catch httpx.HTTPStatusError, connect errors, JSON decode errors, etc.
            logger.exception("Betfair funds fetch failed during session create")
            raise HTTPException(502, f"Betfair connectivity error: {type(e).__name__}: {e}")

    try:
        chains = {str(i): RecoveryChain(pending_stake=config.stake) for i in range(1, config.num_favourites + 1)}
        session = Session(config=config, bank=starting_bank, recovery_chains=chains)
        session.config.starting_bank = starting_bank
        await db.sessions.insert_one(session_to_doc(session))
        return session
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Session create failed (mode=%s)", config.mode)
        raise HTTPException(500, f"Session create failed: {type(e).__name__}: {e}")


@router.get("/sessions", response_model=List[Session])
async def list_sessions():
    docs = await db.sessions.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return [Session(**d) for d in docs]


@router.get("/sessions/{session_id}", response_model=Session)
async def get_session(session_id: str):
    doc = await db.sessions.find_one({"id": session_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Session not found")
    return Session(**doc)


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    res = await db.sessions.delete_one({"id": session_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Session not found")
    sse_clear_session(session_id)
    return {"deleted": True}


@router.delete("/sessions")
async def reset_all_sessions():
    """Wipe every saved session — full reset. Bank carryover restarts from scratch."""
    # Snapshot ids first so we can clear SSE state for each.
    ids = await db.sessions.distinct("id")
    res = await db.sessions.delete_many({})
    for sid in ids:
        sse_clear_session(sid)
    return {"deleted": res.deleted_count}


@router.post("/sessions/{session_id}/next-race", response_model=Session)
async def next_race(session_id: str):
    doc = await db.sessions.find_one({"id": session_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Session not found")
    session = Session(**doc)

    if session.status != "active":
        raise HTTPException(400, f"Session is {session.status}")

    mode = session.config.mode
    market_id = None
    market_start_time = None
    market_time_label = None
    selection_by_rank: Dict[int, int] = {}
    betfair_bet_ids: List[str] = []
    historical_winning_trap: Optional[int] = None
    historical_commission_rate: Optional[float] = None
    historical_market_name: Optional[str] = None
    historical_race_time: Optional[str] = None
    historical_favourite_odds: Optional[float] = None
    historical_second_favourite_odds: Optional[float] = None

    if mode == "simulator":
        historical = next_historical_replay_race(session)
        if historical:
            runners = historical.runners
            venue = historical.venue
            category = historical.category
            historical_winning_trap = historical.winning_trap
            historical_commission_rate = historical.commission_rate
            market_id = f"historical:{historical.market_id}"
            historical_market_name = historical.market_name
            historical_race_time = historical.race_time
            historical_favourite_odds = historical.favourite_odds
            historical_second_favourite_odds = historical.second_favourite_odds
            market_start_time = historical.replay_start_time
            market_time_label = historical.market_time_label
        else:
            logger.error(
                "Historical Replay requested for session=%s but no Betfair historical race was available",
                session_id[:8],
            )
            raise HTTPException(
                503,
                "Historical Replay data is not available yet. Please check that the Betfair historical archive is attached, then try again.",
            )
    else:
        if mode == "live":
            try:
                await reconcile_live_settlements(session_id)
            except BetfairError as e:
                raise HTTPException(502, f"Could not check Betfair settlement history: {e}")
            doc2 = await db.sessions.find_one({"id": session_id}, {"_id": 0})
            if doc2:
                session = doc_to_session(doc2)
                apply_stop_conditions(session, allow_recovery_overrun=False)
                if session.status != "active":
                    await db.sessions.replace_one({"id": session_id}, session_to_doc(session))
                    raise HTTPException(400, f"Session is {session.status}")
        live = await fetch_live_race()
        runners = live["runners"]
        venue = live["venue"]
        market_id = live["market_id"]
        market_start_time = live["market_start_time"]
        selection_by_rank = live["selection_by_rank"]
        category = live["category"]
        if mode == "live" and market_id:
            existing_live_market = next(
                (r for r in session.races if r.source == "live" and r.market_id == market_id),
                None,
            )
            if existing_live_market:
                logger.info(
                    "Skipping duplicate live placement for session=%s market=%s race=%s",
                    session_id[:8],
                    market_id,
                    existing_live_market.race_num,
                )
                return session

    bet_ranks, risk_skip_reasons = favourite_risk_bet_plan(
        runners,
        session.config,
        distance_m=category.distance_m if category else None,
    )
    skipped_bets = format_skip_reasons(risk_skip_reasons)

    # Place lay bets for each favourite slot
    overrun_mode = session.races_played >= session.config.max_races
    bets: List[LayBet] = []
    for rank in bet_ranks:
        chain_key = str(rank)
        if chain_key not in session.recovery_chains:
            session.recovery_chains[chain_key] = RecoveryChain(pending_stake=session.config.stake)
        chain = session.recovery_chains[chain_key]
        if chain.busted:
            continue
        if mode == "live" and chain.level > 0 and _has_unsettled_live_recovery_bet(session, rank):
            logger.warning(
                "Skipping duplicate live recovery placement for session=%s rank=%s level=%s; previous recovery bet still unsettled",
                session_id[:8],
                rank,
                chain.level,
            )
            continue
        # In overrun mode (past max_races), only bet on chains in active recovery
        if overrun_mode and chain.level == 0:
            continue
        try:
            runner = get_runner_by_rank(runners, rank)
        except ValueError:
            continue
        # Odds range filter: skip favs outside the configured band
        # (skip in overrun mode too — if odds outside band, chain still pending next race)
        if runner.odds < session.config.odds_min or runner.odds > session.config.odds_max:
            continue
        bet_plan = plan_recovery_bet(
            chain,
            runner.odds,
            session.config,
            stop_loss_budget=_remaining_stop_loss_budget(session),
        )
        stake = _floor_money(bet_plan.stake)
        liability = round(stake * (runner.odds - 1), 4)
        if stake <= 0 or liability <= 0:
            continue
        new_bet = LayBet(
            favourite_rank=rank, dog_trap=runner.trap, dog_name=runner.name,
            odds=runner.odds, stake=stake, liability=liability,
            recovery_level=chain.level,
        )
        bets.append(new_bet)

        if mode == "live":
            try:
                sel_id = selection_by_rank[rank]
                # Idempotent ref: session + race + rank → unique per attempt
                cor = f"layhounds-{session.id[:8]}-{session.races_played + 1}-{rank}"
                cap_price = None
                if session.config.max_liability_cap > 0:
                    cap_price = 1 + (session.config.max_liability_cap / stake)
                max_chase_price = min(
                    session.config.odds_max,
                    cap_price if cap_price else session.config.odds_max,
                )
                result = await betfair.place_lay_bet_chasing(
                    market_id,
                    sel_id,
                    runner.odds,
                    stake,
                    customer_order_ref=cor,
                    max_ticks=session.config.live_price_chase_ticks if session.config.live_price_chase else 0,
                    max_seconds=session.config.live_price_chase_seconds,
                    max_liability=session.config.max_liability_cap if session.config.max_liability_cap > 0 else None,
                    max_price=max_chase_price,
                )
                # Capture the first instruction report so the UI can show the
                # actual betfair-side matched size + average price immediately.
                reports = (result.get("instructionReports") or [])
                if reports:
                    rep = reports[0]
                    bet_id = rep.get("betId")
                    matched = float(rep.get("sizeMatched") or 0.0)
                    if bet_id and matched > 0:
                        betfair_bet_ids.append(bet_id)
                    new_bet.betfair_bet_id = bet_id
                    new_bet.matched_size = matched or None
                    new_bet.matched_price = float(rep.get("averagePriceMatched") or 0.0) or None
                    chase = result.get("chase") or {}
                    new_bet.chase_attempts = int(chase.get("attempts") or 1)
                    new_bet.chase_final_price = chase.get("final_price")
                    new_bet.chase_timed_out = bool(chase.get("timed_out"))
                    if new_bet.chase_final_price:
                        new_bet.odds = float(new_bet.chase_final_price)
                        new_bet.liability = round(stake * (new_bet.odds - 1), 4)
                    if matched <= 0:
                        new_bet.placement_status = "unmatched"
                    elif matched + 0.005 < new_bet.stake:
                        new_bet.placement_status = "partial"
                    else:
                        new_bet.placement_status = "matched"
                    if new_bet.matched_price:
                        new_bet.slippage_ticks = betfair.count_ticks(new_bet.odds, new_bet.matched_price)
            except BetfairError as e:
                # Surface the precise Betfair error so the user knows WHY it failed.
                raise HTTPException(502, f"Betfair bet placement failed: {e}")

    # Live mode: bet placed on real Betfair, no simulated settlement
    if mode == "live":
        race = Race(
            race_num=session.races_played + 1, venue=venue, runners=runners,
            bets=bets, winning_trap=0, pnl_change=0.0, bank_after=session.bank,
            source=mode, market_id=market_id, market_start_time=market_start_time,
            market_time_label=market_time_label,
            betfair_bet_ids=betfair_bet_ids, category=category,
            skipped_bets=skipped_bets,
        )
        session.races_played += 1
        session.races.append(race)
        apply_stop_conditions(session, allow_recovery_overrun=False)
        await db.sessions.replace_one({"id": session_id}, session_to_doc(session))
        # ---- SSE: push the placed bet to any connected listeners ----
        await sse_publish(session_id, "bet_placed", {
            "race_num": race.race_num,
            "venue": venue,
            "market_id": market_id,
            "market_name": historical_market_name,
            "market_start_time": market_start_time,
            "race_time": historical_race_time,
            "market_time_label": market_time_label,
            "favourite_odds": historical_favourite_odds,
            "second_favourite_odds": historical_second_favourite_odds,
            "category": category.model_dump() if category else None,
            "bets": [{
                "rank": b.favourite_rank, "trap": b.dog_trap, "name": b.dog_name,
                "odds": b.odds, "stake": b.stake, "liability": b.liability,
                "recovery_level": b.recovery_level,
            } for b in bets],
            "betfair_bet_ids": betfair_bet_ids,
            "total_stake": round(sum(b.stake for b in bets), 4),
            "total_liability": round(sum(b.liability for b in bets), 4),
            "skipped_bets": skipped_bets,
        })
        return session

    # Simulator + paper_live: simulate outcome (blended category win-rates)
    winning_trap = historical_winning_trap or pick_winner(runners, category)

    total_staked = 0.0
    total_liability = 0.0
    gross_pnl_change = 0.0
    for bet in bets:
        total_staked += bet.stake
        total_liability += bet.liability
        if bet.dog_trap == winning_trap:
            bet.result = "loss"
            bet.pnl = -bet.liability
            gross_pnl_change -= bet.liability
        else:
            bet.result = "win"
            bet.pnl = bet.stake
            gross_pnl_change += bet.stake

    market_commission = round(
        max(gross_pnl_change, 0.0) * (historical_commission_rate if historical_commission_rate is not None else session.config.commission_rate),
        4,
    )
    winning_bets = [bet for bet in bets if bet.result == "win" and (bet.pnl or 0.0) > 0]
    total_winning_gross = sum(bet.pnl or 0.0 for bet in winning_bets)
    if market_commission > 0 and total_winning_gross > 0:
        allocated = 0.0
        for idx, bet in enumerate(winning_bets):
            if idx == len(winning_bets) - 1:
                commission_share = round(market_commission - allocated, 4)
            else:
                commission_share = round(market_commission * ((bet.pnl or 0.0) / total_winning_gross), 4)
                allocated = round(allocated + commission_share, 4)
            bet.pnl = round((bet.pnl or 0.0) - commission_share, 4)

    pnl_change = round(sum((bet.pnl or 0.0) for bet in bets), 4)
    projected_session_profit = round(session.total_pnl + pnl_change, 4)
    for bet in bets:
        chain = session.recovery_chains[str(bet.favourite_rank)]
        apply_settled_bet_to_chain(
            chain,
            bet,
            session.config,
            bet.pnl or 0.0,
            session_profit=projected_session_profit,
        )

    session.bank = round(session.bank + pnl_change, 4)
    session.total_pnl = round(session.total_pnl + pnl_change, 4)
    session.total_staked = round(session.total_staked + total_staked, 4)
    session.total_liability_risked = round(session.total_liability_risked + total_liability, 4)
    session.races_played += 1

    race = Race(
        race_num=session.races_played, venue=venue, runners=runners, bets=bets,
        winning_trap=winning_trap, pnl_change=round(pnl_change, 4),
        bank_after=session.bank, source=mode, market_id=market_id,
        market_name=historical_market_name,
        market_start_time=market_start_time,
        race_time=historical_race_time,
        market_time_label=market_time_label,
        favourite_odds=historical_favourite_odds,
        second_favourite_odds=historical_second_favourite_odds,
        category=category,
        skipped_bets=skipped_bets,
    )
    session.races.append(race)

    apply_stop_conditions(session)

    await db.sessions.replace_one({"id": session_id}, session_to_doc(session))

    # ---- SSE: push race-resolved + bank update so the UI animates ----
    if mode in ("simulator", "paper_live"):
        winner_dog = next((r for r in runners if r.trap == winning_trap), None)
        await sse_publish(session_id, "race_resulted", {
            "race_num": race.race_num,
            "venue": venue,
            "winning_trap": winning_trap,
            "winner_name": winner_dog.name if winner_dog else None,
            "winner_odds": winner_dog.odds if winner_dog else None,
            "pnl_change": round(pnl_change, 4),
            "bank_after": session.bank,
            "market_time_label": market_time_label,
            "category": category.model_dump() if category else None,
            "skipped_bets": skipped_bets,
            "bets": [{
                "rank": b.favourite_rank, "trap": b.dog_trap, "name": b.dog_name,
                "pnl": b.pnl, "result": b.result, "recovery_level": b.recovery_level,
            } for b in bets],
        })
        await sse_publish(session_id, "bank_updated", {
            "bank": session.bank, "starting_bank": session.config.starting_bank,
            "total_pnl": session.total_pnl,
        })
    return session


@router.get("/sessions/{session_id}/events")
async def session_event_stream(session_id: str, request: Request):
    """Server-Sent-Events stream for a single session."""
    doc = await db.sessions.find_one({"id": session_id}, {"_id": 0, "id": 1})
    if not doc:
        raise HTTPException(404, "Session not found")

    async def event_generator():
        yield format_sse({"event": "ready", "data": {"session_id": session_id}})
        try:
            async for ev in sse_subscribe(session_id):
                if await request.is_disconnected():
                    break
                yield format_sse(ev)
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/sessions/{session_id}/refresh-live-settlement")
async def refresh_live_settlement(session_id: str, race_id: Optional[str] = None):
    """Reconcile live races from actual Betfair settled-order history."""
    doc = await db.sessions.find_one({"id": session_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Session not found")
    try:
        result = await reconcile_live_settlements(session_id, race_id=race_id)
    except BetfairError as e:
        raise HTTPException(502, f"Betfair listClearedOrders failed: {e}")
    if not result["found"]:
        raise HTTPException(404, "No live race with placed bets found")
    return result


@router.post("/sessions/{session_id}/refresh-bank", response_model=Session)
async def refresh_session_bank(session_id: str):
    """Sync a Paper-Live or Live session's bank with the live Betfair balance.
    Computes the realised P&L delta and updates total_pnl accordingly so the
    daily journal stays accurate.
    """
    doc = await db.sessions.find_one({"id": session_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Session not found")
    session = Session(**doc)
    if session.config.mode != "live":
        raise HTTPException(400, "refresh-bank only applies to live sessions (paper-live settles locally)")
    try:
        funds = await betfair.get_account_funds()
    except BetfairError as e:
        raise HTTPException(502, str(e))
    new_bank = round(float(funds.get("availableToBetBalance", 0.0) or 0.0), 2)
    delta = round(new_bank - session.bank, 4)
    session.bank = new_bank
    session.total_pnl = round(session.total_pnl + delta, 4)
    await db.sessions.replace_one({"id": session_id}, session_to_doc(session))
    return session


@router.get("/bank/current")
async def current_bank():
    """Return the ending bank of the most recent session, or None if no sessions exist."""
    doc = await db.sessions.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
    if not doc:
        return {"bank": None}
    return {"bank": doc.get("bank", 0.0), "from_session_id": doc.get("id"), "status": doc.get("status")}


@router.get("/daily-stats")
async def daily_stats():
    """Aggregate P&L per session (each session = one trading day)."""
    docs = await db.sessions.find({}, {"_id": 0}).sort("created_at", 1).to_list(500)
    rows = []
    cumulative = 0.0
    for d in docs:
        pnl = d.get("total_pnl", 0.0)
        cumulative += pnl
        rows.append({
            "id": d["id"],
            "created_at": d.get("created_at"),
            "pnl": round(pnl, 2),
            "cumulative_pnl": round(cumulative, 2),
            "bank_start": d.get("config", {}).get("starting_bank", 0.0),
            "bank_end": d.get("bank", 0.0),
            "races": d.get("races_played", 0),
            "status": d.get("status", "active"),
            "mode": d.get("config", {}).get("mode", "simulator"),
        })
    return {"days": rows, "total_pnl": round(cumulative, 2), "sessions": len(rows)}


def _csv_response(csv_body: str, filename: str) -> Response:
    return Response(
        content=csv_body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _analysis_config(
    *,
    stake: float,
    starting_bank: float,
    stop_loss: float,
    max_liability_cap: float,
    commission_rate: float,
    max_recovery_level: int,
) -> SessionConfig:
    if stake <= 0:
        raise HTTPException(400, "stake must be > 0")
    if starting_bank < 0:
        raise HTTPException(400, "starting_bank must be >= 0")
    if stop_loss < 0:
        raise HTTPException(400, "stop_loss must be >= 0")
    if max_liability_cap < 0:
        raise HTTPException(400, "max_liability_cap must be >= 0")
    if commission_rate < 0 or commission_rate > 0.2:
        raise HTTPException(400, "commission_rate must be 0..0.2")
    if max_recovery_level < 1 or max_recovery_level > 5:
        raise HTTPException(400, "max_recovery_level must be 1..5")
    return SessionConfig(
        mode="simulator",
        num_favourites=1,
        stake=stake,
        starting_bank=starting_bank,
        stop_win=1_000_000,
        stop_loss=stop_loss,
        max_races=200,
        max_liability_cap=max_liability_cap,
        commission_rate=commission_rate,
        max_recovery_level=max_recovery_level,
    )


@router.get("/analysis/backtest.csv")
async def backtest_analysis_csv(
    races: int = 1000,
    include_races: bool = True,
    repeat_50_samples: int = 20,
    seed: Optional[int] = None,
    stake: float = 0.05,
    starting_bank: float = 1000.0,
    stop_loss: float = 1000.0,
    max_liability_cap: float = 0.0,
    commission_rate: float = 0.05,
    max_recovery_level: int = 3,
):
    if races < 1 or races > 20000:
        raise HTTPException(400, "races must be 1..20000")
    if repeat_50_samples < 0 or repeat_50_samples > 200:
        raise HTTPException(400, "repeat_50_samples must be 0..200")
    config = _analysis_config(
        stake=stake,
        starting_bank=starting_bank,
        stop_loss=stop_loss,
        max_liability_cap=max_liability_cap,
        commission_rate=commission_rate,
        max_recovery_level=max_recovery_level,
    )
    snapshots = generated_race_snapshots(races, seed=seed)
    csv_body = build_analysis_csv(
        snapshots,
        config,
        include_races=include_races,
        repeat_50_samples=repeat_50_samples,
        seed=seed,
    )
    return _csv_response(csv_body, "layhounds-backtest-analysis.csv")


@router.get("/sessions/{session_id}/analysis.csv")
async def session_analysis_csv(
    session_id: str,
    include_races: bool = True,
    repeat_50_samples: int = 20,
):
    doc = await db.sessions.find_one({"id": session_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Session not found")
    if repeat_50_samples < 0 or repeat_50_samples > 200:
        raise HTTPException(400, "repeat_50_samples must be 0..200")
    session = Session(**doc)
    snapshots = session_race_snapshots(session)
    if not snapshots:
        raise HTTPException(400, "Session has no settled races to analyse")
    csv_body = build_analysis_csv(
        snapshots,
        session.config,
        include_races=include_races,
        repeat_50_samples=repeat_50_samples,
        seed=None,
    )
    return _csv_response(csv_body, f"layhounds-session-{session_id[:8]}-analysis.csv")


class CapPreviewInput(BaseModel):
    stake: float = Field(ge=0.01)
    max_liability_cap: float = Field(ge=0)
    num_favourites: int = Field(default=2, ge=1, le=4)
    commission_rate: float = Field(default=0.05, ge=0, le=0.2)
    iterations: int = Field(default=2000, ge=100, le=10000)
    odds_min: float = Field(default=1.01, ge=1.01)
    odds_max: float = Field(default=1000.0, ge=1.01)
    max_recovery_level: int = Field(default=3, ge=1, le=5)


@router.post("/preview-cap")
async def preview_cap(inp: CapPreviewInput):
    """Monte-Carlo preview of cap impact for given stake/cap.
    Runs `iterations` independent race chains per favourite rank.
    Returns bust-level distribution, expected profit/race, worst chain loss.
    """

    def simulate_one_rank():
        """Simulate one chain-life on a given rank until it resets (win) or busts."""
        level = 0
        pending = inp.stake
        accum_loss = 0.0
        chain_pnl = 0.0
        races = 0
        # Loop races until chain resets to L0 via a win, or busts.
        for _ in range(10):
            runners, _v, category = generate_race(1)
            runner = get_runner_by_rank(runners, 1)  # treat as rank-1 surrogate
            odds = runner.odds
            if odds < inp.odds_min or odds > inp.odds_max:
                return {"won_at_level": level, "chain_pnl": chain_pnl, "races": races}
            liability = pending * (odds - 1)
            if inp.max_liability_cap > 0 and liability > inp.max_liability_cap:
                return {"bust_level": level, "chain_pnl": -accum_loss, "races": races}
            races += 1
            winner = pick_winner(runners, category)
            if winner == runner.trap:
                # lay loses
                chain_pnl -= liability
                target = inp.stake * (1 - inp.commission_rate)
                accum_loss += liability
                if level >= inp.max_recovery_level:
                    return {"bust_level": inp.max_recovery_level, "chain_pnl": chain_pnl, "races": races}
                level += 1
                pending = (accum_loss + target) / max(1 - inp.commission_rate, 0.0001)
            else:
                gross = pending
                commission = gross * inp.commission_rate
                chain_pnl += gross - commission
                return {"won_at_level": level, "chain_pnl": chain_pnl, "races": races}
        return {"bust_level": level, "chain_pnl": chain_pnl, "races": races}

    # Restore default random for simulation determinism
    _seed = random.getstate()
    random.seed(42)
    try:
        max_lvl = inp.max_recovery_level
        stats = {f"bust_L{i}": 0 for i in range(max_lvl + 1)}
        stats.update({f"won_L{i}": 0 for i in range(max_lvl + 1)})
        total_pnl = 0.0
        total_races = 0
        worst_chain = 0.0
        for _ in range(inp.iterations):
            res = simulate_one_rank()
            total_pnl += res["chain_pnl"]
            total_races += res["races"]
            worst_chain = min(worst_chain, res["chain_pnl"])
            if "won_at_level" in res:
                key = f"won_L{min(res['won_at_level'], max_lvl)}"
                stats[key] = stats.get(key, 0) + 1
            else:
                key = f"bust_L{min(res['bust_level'], max_lvl)}"
                stats[key] = stats.get(key, 0) + 1
    finally:
        random.setstate(_seed)

    chains_total = inp.iterations
    wins = sum(v for k, v in stats.items() if k.startswith("won_"))
    busts = chains_total - wins
    bust_at_L0 = stats.get("bust_L0", 0)
    reach_top = stats.get(f"won_L{max_lvl}", 0) + stats.get(f"bust_L{max_lvl}", 0)

    return {
        "iterations": chains_total,
        "per_rank": inp.num_favourites,
        "max_recovery_level": max_lvl,
        "win_rate": round(wins / chains_total * 100, 1),
        "bust_rate": round(busts / chains_total * 100, 1),
        "reach_top_rate": round(reach_top / chains_total * 100, 1),
        "reach_l3_rate": round(reach_top / chains_total * 100, 1),  # legacy alias
        "bust_distribution": {
            "L0_cap_blocked": bust_at_L0,
            **{f"L{i}": stats.get(f"bust_L{i}", 0) for i in range(1, max_lvl + 1)},
        },
        "win_distribution": {
            f"L{i}": stats.get(f"won_L{i}", 0) for i in range(0, max_lvl + 1)
        },
        "expected_profit_per_race": round(total_pnl / max(total_races, 1) * inp.num_favourites, 4),
        "worst_chain_loss": round(worst_chain, 2),
    }


@router.post("/sessions/{session_id}/run-races", response_model=Session)
async def run_races(session_id: str, count: int = 10):
    """Run multiple races back-to-back in one call. Stops early on stop conditions."""
    if count < 1 or count > 100:
        raise HTTPException(400, "count must be 1..100")
    last_session = None
    for _ in range(count):
        # Re-load each iteration to honour fresh stop conditions
        doc = await db.sessions.find_one({"id": session_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Session not found")
        s = Session(**doc)
        if s.status != "active":
            return s
        last_session = await next_race(session_id)
    if last_session is None:
        doc = await db.sessions.find_one({"id": session_id}, {"_id": 0})
        return Session(**doc)
    return last_session


@router.post("/sessions/{session_id}/stop", response_model=Session)
async def stop_session(session_id: str):
    doc = await db.sessions.find_one({"id": session_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Session not found")
    session = Session(**doc)
    if session.status == "active":
        session.status = "stopped_manual"
        await db.sessions.replace_one({"id": session_id}, session_to_doc(session))
    return session


