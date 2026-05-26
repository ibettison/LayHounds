from fastapi import FastAPI, APIRouter, HTTPException, Request, Header
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import random
import logging
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Optional, Literal, Any
import uuid
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from betfair_client import betfair, BetfairError, EVENT_TYPE_GREYHOUND  # noqa: E402,F401
from race_categories import (  # noqa: E402
    RaceCategory,
    random_category,
    detect_category_from_market_name,
    winner_weights,
)
from licences import (  # noqa: E402
    LICENCE_SERVER_MODE,
    LICENCE_SERVER_URL,
    build_central_router,
    build_customer_router,
    create_stripe_checkout_session,
    get_stripe_checkout_status,
    handle_stripe_webhook,
    is_licence_active,
    background_revalidate_loop,
)
from session_events import (  # noqa: E402
    publish as sse_publish,
    subscribe as sse_subscribe,
    format_sse,
    clear_session as sse_clear_session,
)

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")


# ---------- Constants ----------
INITIAL_STAKE = 0.05
TARGET_PROFIT = 0.05

UK_GREYHOUND_NAMES = [
    "Ballymac Vic", "Droopys Sydney", "Romeo Magico", "Swift Iconic",
    "Tullymurry Act", "Newinn Taylor", "Burgess Bullet", "Kilgraney Rumble",
    "Pestana Rocky", "Coolavanny Aunt", "Jaytee Yankee", "Skywalker Logan",
    "Bockos Doomie", "Hovex Bolt", "Slippy Bullet", "Droopys Verve",
    "Rough Sailor", "Magical Bale", "Fearless Storm", "Westmead Hawk",
    "Toolatetosell", "Ballyboden Boss", "Crossfield Storm", "King Turbo",
    "Swift Falcon", "Templeogue Whip", "Crash Bandicoot", "Loughteen Blanco",
    "Dazzling Sunset", "Ballyanne Sim", "Yahoo Hippy", "Imperial Spirit",
    "Roxholme Magic", "Tyrur Lewis", "Killeacle Annie", "Dancing Anto",
]


# ---------- Models ----------
class SessionConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    stake: float = INITIAL_STAKE
    num_favourites: int = Field(default=2, ge=1, le=4)
    stop_win: float = Field(default=5.0, ge=0)
    stop_loss: float = Field(default=5.0, ge=0)
    max_races: int = Field(default=20, ge=1, le=200)
    starting_bank: float = Field(default=10.0, ge=0)
    mode: Literal["simulator", "paper_live", "live"] = "simulator"
    max_liability_cap: float = Field(default=5.0, ge=0)  # live-mode safety
    risk_accepted: bool = False  # required for live mode
    commission_rate: float = Field(default=0.05, ge=0.0, le=0.2)  # Betfair typical 5%
    odds_min: float = Field(default=1.01, ge=1.01, le=1000.0)  # only lay favs with odds >=
    odds_max: float = Field(default=1000.0, ge=1.01, le=1000.0)  # and <=
    max_recovery_level: int = Field(default=3, ge=1, le=5)  # configurable depth of recovery staircase
    auto_place: bool = False  # live mode: auto-fire bet 60s before next race start


class Greyhound(BaseModel):
    trap: int
    name: str
    odds: float
    favourite_rank: int  # 1 = favourite


class LayBet(BaseModel):
    favourite_rank: int
    dog_trap: int
    dog_name: str
    odds: float
    stake: float
    liability: float
    recovery_level: int  # 0 = initial, 1-3 = recovery levels
    result: Optional[Literal["win", "loss"]] = None  # win = lay won (dog lost)
    pnl: Optional[float] = None


class Race(BaseModel):
    race_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    race_num: int
    venue: str
    runners: List[Greyhound]
    bets: List[LayBet]
    winning_trap: int
    pnl_change: float
    bank_after: float
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: Literal["simulator", "paper_live", "live"] = "simulator"
    market_id: Optional[str] = None
    market_start_time: Optional[str] = None
    betfair_bet_ids: List[str] = Field(default_factory=list)
    category: Optional[RaceCategory] = None


class RecoveryChain(BaseModel):
    """Tracks pending recovery for a specific favourite rank."""
    level: int = 0  # 0 = no active recovery (next bet is initial)
    pending_stake: float = INITIAL_STAKE  # stake to use on next race
    accumulated_loss: float = 0.0
    busted: bool = False  # True after level 3 loss; chain stopped


class Session(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    config: SessionConfig
    bank: float
    total_pnl: float = 0.0
    total_staked: float = 0.0
    total_liability_risked: float = 0.0
    races_played: int = 0
    status: Literal["active", "stopped_win", "stopped_loss", "stopped_max", "stopped_manual"] = "active"
    recovery_chains: Dict[str, RecoveryChain] = Field(default_factory=dict)  # key = str(rank)
    races: List[Race] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------- Helpers ----------
def generate_race(race_num: int) -> tuple[List[Greyhound], str, RaceCategory]:
    venues = ["Romford", "Hove", "Nottingham", "Sheffield", "Crayford", "Towcester", "Newcastle", "Sunderland"]
    venue = random.choice(venues)
    category = random_category()
    names = random.sample(UK_GREYHOUND_NAMES, 6)
    raw_odds = []
    # Generate spread of odds: one strong fav (~1.8-3), then progressively longer
    base = random.uniform(1.8, 3.5)
    for i in range(6):
        o = round(base + i * random.uniform(0.6, 1.8) + random.uniform(-0.3, 0.6), 2)
        o = max(1.5, o)
        raw_odds.append(o)
    random.shuffle(raw_odds)  # shuffle so trap order != odds order
    # Assign trap 1..6
    runners_unsorted = [{"trap": i + 1, "name": names[i], "odds": raw_odds[i]} for i in range(6)]
    # Compute favourite rank by sorting by odds asc
    sorted_by_odds = sorted(runners_unsorted, key=lambda r: r["odds"])
    rank_by_trap = {r["trap"]: idx + 1 for idx, r in enumerate(sorted_by_odds)}
    runners = [
        Greyhound(trap=r["trap"], name=r["name"], odds=r["odds"], favourite_rank=rank_by_trap[r["trap"]])
        for r in runners_unsorted
    ]
    return runners, venue, category


def pick_winner(runners: List[Greyhound], category: Optional[RaceCategory] = None) -> int:
    """Pick the winning trap.

    If a `category` is supplied, weights blend the category's published favourite
    win-rates with a small odds jitter (calibrated long-run distribution).
    If `category` is None, falls back to pure implied-odds (1/odds) weighting
    so legacy callers (preview-cap Monte-Carlo) keep their original behaviour.
    """
    if category is not None:
        rs = [{"favourite_rank": r.favourite_rank, "odds": r.odds} for r in runners]
        norm = winner_weights(rs, category)
    else:
        weights = [1.0 / r.odds for r in runners]
        total = sum(weights)
        norm = [w / total for w in weights]
    pick = random.random()
    cum = 0.0
    for r, w in zip(runners, norm):
        cum += w
        if pick <= cum:
            return r.trap
    return runners[-1].trap


def get_runner_by_rank(runners: List[Greyhound], rank: int) -> Greyhound:
    for r in runners:
        if r.favourite_rank == rank:
            return r
    raise ValueError(f"No runner at rank {rank}")


async def fetch_live_race() -> Dict[str, Any]:
    """Fetch next upcoming UK/IE greyhound market and convert to our race shape.

    Returns dict with: runners (List[Greyhound]), venue, market_id, market_start_time.
    """
    markets = await betfair.list_greyhound_markets(minutes_ahead=60, max_results=5)
    if not markets:
        raise HTTPException(400, "No upcoming UK/IE greyhound markets in next 60 minutes")
    # Find first market with fresh prices
    for m in markets:
        market_id = m["marketId"]
        book = await betfair.get_market_book(market_id)
        if not book:
            continue
        # Build runner rows: selectionId -> best lay price (odds we'd lay at)
        runner_meta = {r["selectionId"]: r for r in m.get("runners", [])}
        priced = []
        for br in book.get("runners", []):
            if br.get("status") != "ACTIVE":
                continue
            ex = br.get("ex", {})
            lay_prices = ex.get("availableToLay", [])
            if not lay_prices:
                continue
            odds = lay_prices[0]["price"]
            sel_id = br["selectionId"]
            meta = runner_meta.get(sel_id, {})
            priced.append({
                "selection_id": sel_id,
                "name": meta.get("runnerName", f"Runner {sel_id}"),
                "trap": int(meta.get("metadata", {}).get("CLOTH_NUMBER") or meta.get("metadata", {}).get("TRAP_NUMBER") or 0),
                "odds": float(odds),
            })
        if len(priced) < 2:
            continue
        # Assign traps if missing (use order from market)
        for i, p in enumerate(priced):
            if not p["trap"]:
                p["trap"] = i + 1
        # Compute favourite rank by ascending odds
        sorted_by_odds = sorted(priced, key=lambda r: r["odds"])
        rank_by_sel = {r["selection_id"]: idx + 1 for idx, r in enumerate(sorted_by_odds)}
        runners = [
            Greyhound(trap=p["trap"], name=p["name"], odds=round(p["odds"], 2), favourite_rank=rank_by_sel[p["selection_id"]])
            for p in priced
        ]
        # Also return selection_id mapping so live bets can target correct runner
        sel_by_rank = {rank_by_sel[p["selection_id"]]: p["selection_id"] for p in priced}
        market_name = m.get("marketName") or ""
        event_name = (m.get("event") or {}).get("name") or ""
        category = detect_category_from_market_name(market_name, event_name)
        return {
            "runners": runners,
            "venue": m.get("event", {}).get("venue") or m.get("event", {}).get("name", "Live"),
            "market_id": market_id,
            "market_start_time": m.get("marketStartTime"),
            "selection_by_rank": sel_by_rank,
            "category": category,
        }
    raise HTTPException(400, "No markets with live prices available")


def session_to_doc(s: Session) -> dict:
    return s.model_dump()


def doc_to_session(d: dict) -> Session:
    d = {k: v for k, v in d.items() if k != "_id"}
    return Session(**d)


# ---------- Endpoints ----------
@api_router.get("/")
async def root():
    return {"message": "Greyhound Lay Simulator API"}


@api_router.post("/sessions", response_model=Session)
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


@api_router.get("/sessions", response_model=List[Session])
async def list_sessions():
    docs = await db.sessions.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return [Session(**d) for d in docs]


@api_router.get("/sessions/{session_id}", response_model=Session)
async def get_session(session_id: str):
    doc = await db.sessions.find_one({"id": session_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Session not found")
    return Session(**doc)


@api_router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    res = await db.sessions.delete_one({"id": session_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Session not found")
    sse_clear_session(session_id)
    return {"deleted": True}


@api_router.delete("/sessions")
async def reset_all_sessions():
    """Wipe every saved session — full reset. Bank carryover restarts from scratch."""
    # Snapshot ids first so we can clear SSE state for each.
    ids = await db.sessions.distinct("id")
    res = await db.sessions.delete_many({})
    for sid in ids:
        sse_clear_session(sid)
    return {"deleted": res.deleted_count}


@api_router.post("/sessions/{session_id}/next-race", response_model=Session)
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
    selection_by_rank: Dict[int, int] = {}
    betfair_bet_ids: List[str] = []

    if mode == "simulator":
        runners, venue, category = generate_race(session.races_played + 1)
    else:
        # LIVE / PAPER_LIVE: refuse to place a new bet if the previous live race
        # for this session still has unsettled Betfair bets — otherwise the new
        # bet's stake will be calculated from a stale recovery chain (showing
        # no loss yet) and any required L1+ recovery will be MISSED.
        # Do one synchronous settlement check first so the chain catches up.
        if mode == "live":
            last_live = next(
                (r for r in reversed(session.races)
                 if r.source == "live" and r.betfair_bet_ids and r.winning_trap == 0),
                None,
            )
            if last_live:
                try:
                    cleared = await betfair.list_cleared_orders(
                        market_id=last_live.market_id,
                        bet_ids=last_live.betfair_bet_ids,
                    )
                except BetfairError as e:
                    raise HTTPException(409, f"Cannot place new live bet — previous race still pending settlement and Betfair listClearedOrders failed: {e}")
                rows = (cleared or {}).get("clearedOrders") or []
                settled_ids = {r.get("betId") for r in rows if r.get("betId")}
                remaining = [b for b in last_live.betfair_bet_ids if b not in settled_ids]
                if remaining:
                    raise HTTPException(
                        409,
                        f"Cannot place new live bet — previous race #{last_live.race_num} ({last_live.venue}) "
                        f"still has {len(remaining)} unsettled bet(s) on Betfair. Wait for settlement "
                        f"(usually < 60s after race finishes) or refresh via /api/sessions/{session_id}/refresh-live-settlement."
                    )
                # Fold the settled P&L back into the session BEFORE picking next stake
                await _close_live_race(session_id, last_live.race_id, rows)
                # Re-fetch the now-updated session so recovery_chains carry the new level
                doc2 = await db.sessions.find_one({"id": session_id}, {"_id": 0})
                if doc2:
                    session = doc_to_session(doc2)
        live = await fetch_live_race()
        runners = live["runners"]
        venue = live["venue"]
        market_id = live["market_id"]
        market_start_time = live["market_start_time"]
        selection_by_rank = live["selection_by_rank"]
        category = live["category"]

    # Place lay bets for each favourite slot
    overrun_mode = session.races_played >= session.config.max_races
    bets: List[LayBet] = []
    for rank in range(1, session.config.num_favourites + 1):
        chain = session.recovery_chains.get(str(rank), RecoveryChain())
        if chain.busted:
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
        stake = round(chain.pending_stake, 4)
        liability = round(stake * (runner.odds - 1), 4)

        # Liability cap applies to all modes — auto-busts recovery chains
        # whose next bet would exceed the safety cap.
        if session.config.max_liability_cap > 0 and liability > session.config.max_liability_cap:
            chain.busted = True
            continue

        bets.append(LayBet(
            favourite_rank=rank, dog_trap=runner.trap, dog_name=runner.name,
            odds=runner.odds, stake=stake, liability=liability,
            recovery_level=chain.level,
        ))

        if mode == "live":
            try:
                sel_id = selection_by_rank[rank]
                # Idempotent ref: session + race + rank → unique per attempt
                cor = f"layhounds-{session.id[:8]}-{session.races_played + 1}-{rank}"
                # betfair_client.place_lay_bet handles BOTH normal lays (>=£1) and
                # sub-£1 lays (via betTargetType=BACKERS_PROFIT) — single call.
                result = await betfair.place_lay_bet(
                    market_id, sel_id, runner.odds, stake,
                    customer_order_ref=cor,
                )
                for rep in result.get("instructionReports", []):
                    if rep.get("betId"):
                        betfair_bet_ids.append(rep["betId"])
            except BetfairError as e:
                # Surface the precise Betfair error so the user knows WHY it failed.
                raise HTTPException(502, f"Betfair bet placement failed: {e}")

    # Live mode: bet placed on real Betfair, no simulated settlement
    if mode == "live":
        race = Race(
            race_num=session.races_played + 1, venue=venue, runners=runners,
            bets=bets, winning_trap=0, pnl_change=0.0, bank_after=session.bank,
            source=mode, market_id=market_id, market_start_time=market_start_time,
            betfair_bet_ids=betfair_bet_ids, category=category,
        )
        session.races_played += 1
        session.races.append(race)
        await db.sessions.replace_one({"id": session_id}, session_to_doc(session))
        # ---- SSE: push the placed bet to any connected listeners ----
        await sse_publish(session_id, "bet_placed", {
            "race_num": race.race_num,
            "venue": venue,
            "market_id": market_id,
            "market_start_time": market_start_time,
            "category": category.model_dump() if category else None,
            "bets": [{
                "rank": b.favourite_rank, "trap": b.dog_trap, "name": b.dog_name,
                "odds": b.odds, "stake": b.stake, "liability": b.liability,
                "recovery_level": b.recovery_level,
            } for b in bets],
            "betfair_bet_ids": betfair_bet_ids,
            "total_stake": round(sum(b.stake for b in bets), 4),
            "total_liability": round(sum(b.liability for b in bets), 4),
        })
        # Kick off background settlement polling so the user gets a UI update
        # the moment Betfair returns the cleared-order P&L for this race.
        asyncio.create_task(poll_live_settlement(session_id, race.race_id, market_id, betfair_bet_ids))
        return session

    # Simulator + paper_live: simulate outcome (blended category win-rates)
    winning_trap = pick_winner(runners, category)

    pnl_change = 0.0
    total_staked = 0.0
    total_liability = 0.0
    for bet in bets:
        chain = session.recovery_chains[str(bet.favourite_rank)]
        total_staked += bet.stake
        total_liability += bet.liability
        if bet.dog_trap == winning_trap:
            bet.result = "loss"
            bet.pnl = -bet.liability
            pnl_change -= bet.liability
            new_accum = chain.accumulated_loss + bet.liability + bet.stake
            if chain.level >= session.config.max_recovery_level:
                chain.busted = True
                chain.level = session.config.max_recovery_level
                chain.pending_stake = session.config.stake
                chain.accumulated_loss = new_accum
            else:
                chain.level += 1
                chain.accumulated_loss = new_accum
                chain.pending_stake = round(bet.liability + bet.stake + session.config.stake, 4)
        else:
            bet.result = "win"
            gross_win = bet.stake
            commission = round(gross_win * session.config.commission_rate, 4)
            net_win = round(gross_win - commission, 4)
            bet.pnl = net_win
            pnl_change += net_win
            chain.level = 0
            chain.accumulated_loss = 0.0
            chain.pending_stake = session.config.stake

    session.bank = round(session.bank + pnl_change, 4)
    session.total_pnl = round(session.total_pnl + pnl_change, 4)
    session.total_staked = round(session.total_staked + total_staked, 4)
    session.total_liability_risked = round(session.total_liability_risked + total_liability, 4)
    session.races_played += 1

    race = Race(
        race_num=session.races_played, venue=venue, runners=runners, bets=bets,
        winning_trap=winning_trap, pnl_change=round(pnl_change, 4),
        bank_after=session.bank, source=mode, market_id=market_id,
        market_start_time=market_start_time, category=category,
    )
    session.races.append(race)

    if session.total_pnl >= session.config.stop_win:
        session.status = "stopped_win"
    elif session.total_pnl <= -session.config.stop_loss:
        session.status = "stopped_loss"
    elif session.races_played >= session.config.max_races:
        # End-of-day: only stop if no chains are still in active recovery.
        # Otherwise, keep racing in "overrun" mode until each chain either
        # wins (resets to L0) or busts.
        has_recovery = any(
            (c.level > 0 and not c.busted)
            for c in session.recovery_chains.values()
        )
        if not has_recovery:
            session.status = "stopped_max"

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
            "category": category.model_dump() if category else None,
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


@api_router.get("/betfair/status")
async def betfair_status():
    return await betfair.status()


# ============================================================================
# Live settlement polling + Server-Sent-Events stream
# ============================================================================

async def poll_live_settlement(session_id: str, race_id: str, market_id: str,
                                bet_ids: List[str]):
    """Background task: poll Betfair for settled-order results on a live race.

    Runs for up to ~5 minutes after a live bet is placed. Once Betfair returns
    SETTLED rows for every bet_id, we close the race in the local session
    (winning_trap, pnl_change, recovery chain updates) and emit a
    `race_resulted` SSE so the UI animates. While we're still waiting, emits
    a heartbeat `poll_status` SSE every poll so the UI shows "Waiting for
    Betfair settlement…" with a live attempt counter.
    """
    if not bet_ids:
        return
    POLL_INTERVAL = 5  # seconds
    MAX_ATTEMPTS = 60  # → 5 minutes
    attempt = 0
    try:
        while attempt < MAX_ATTEMPTS:
            attempt += 1
            await asyncio.sleep(POLL_INTERVAL)
            try:
                cleared = await betfair.list_cleared_orders(market_id=market_id, bet_ids=bet_ids)
            except BetfairError as e:
                logger.warning("Settlement poll error session=%s attempt=%d: %s", session_id[:8], attempt, e)
                await sse_publish(session_id, "poll_status", {
                    "race_id": race_id, "attempt": attempt, "max_attempts": MAX_ATTEMPTS,
                    "market_status": f"poll_error: {e}",
                })
                continue

            rows = (cleared or {}).get("clearedOrders") or []
            settled_ids = {r.get("betId") for r in rows if r.get("betId")}
            remaining = [b for b in bet_ids if b not in settled_ids]

            await sse_publish(session_id, "poll_status", {
                "race_id": race_id, "attempt": attempt, "max_attempts": MAX_ATTEMPTS,
                "settled": len(settled_ids), "remaining": len(remaining),
                "market_status": "awaiting_settlement" if remaining else "settled",
            })

            if remaining:
                continue

            # All bets settled — fold P&L back into the session.
            await _close_live_race(session_id, race_id, rows)
            return
        # Timed out — let the UI know
        await sse_publish(session_id, "poll_status", {
            "race_id": race_id, "attempt": attempt, "max_attempts": MAX_ATTEMPTS,
            "market_status": "timeout",
        })
        await sse_publish(session_id, "error", {
            "message": "Settlement polling timed out (5 min) — refresh manually.",
            "context": {"race_id": race_id, "market_id": market_id},
        })
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.exception("poll_live_settlement crashed: %s", e)
        await sse_publish(session_id, "error", {
            "message": f"Settlement poller crashed: {type(e).__name__}: {e}",
            "context": {"race_id": race_id},
        })


async def _close_live_race(session_id: str, race_id: str, cleared_rows: List[Dict[str, Any]]):
    """Update the Race + Session with realised P&L from Betfair's cleared orders.

    `cleared_rows` is the raw `clearedOrders` array from listClearedOrders —
    each row has `betId`, `priceMatched`, `sizeMatched`, `profit` (signed).
    """
    doc = await db.sessions.find_one({"id": session_id}, {"_id": 0})
    if not doc:
        return
    session = doc_to_session(doc)
    race = next((r for r in session.races if r.race_id == race_id), None)
    if not race:
        logger.warning("Settlement received for unknown race_id=%s session=%s", race_id, session_id[:8])
        return

    # Map bet_id → row for fast lookup
    by_bet = {r.get("betId"): r for r in cleared_rows if r.get("betId")}

    pnl_change = 0.0
    losses_by_rank: Dict[int, float] = {}
    wins_by_rank: Dict[int, float] = {}
    # Iterate bets in placement order — each bet has a betfair bet_id at the
    # SAME INDEX in race.betfair_bet_ids (live placement appends in lock-step).
    for i, bet in enumerate(race.bets):
        bet_id = race.betfair_bet_ids[i] if i < len(race.betfair_bet_ids) else None
        row = by_bet.get(bet_id) if bet_id else None
        if row is None:
            continue
        profit = float(row.get("profit") or 0.0)  # signed, gross
        bet.pnl = round(profit, 4)
        if profit >= 0:
            bet.result = "win"
            wins_by_rank[bet.favourite_rank] = profit
        else:
            bet.result = "loss"
            losses_by_rank[bet.favourite_rank] = profit
        pnl_change += profit

    # Update recovery chains using same logic as simulator/paper_live
    for bet in race.bets:
        chain = session.recovery_chains.get(str(bet.favourite_rank))
        if not chain:
            continue
        if bet.result == "loss":
            new_accum = chain.accumulated_loss + bet.liability + bet.stake
            if chain.level >= session.config.max_recovery_level:
                chain.busted = True
                chain.level = session.config.max_recovery_level
                chain.pending_stake = session.config.stake
                chain.accumulated_loss = new_accum
            else:
                chain.level += 1
                chain.accumulated_loss = new_accum
                chain.pending_stake = round(bet.liability + bet.stake + session.config.stake, 4)
        else:
            chain.level = 0
            chain.accumulated_loss = 0.0
            chain.pending_stake = session.config.stake

    # Figure out the actual winning trap from the bet results.
    losing_bet = next((b for b in race.bets if b.result == "loss"), None)
    winning_trap = losing_bet.dog_trap if losing_bet else 0
    race.winning_trap = winning_trap
    race.pnl_change = round(pnl_change, 4)
    race.bank_after = round(session.bank + pnl_change, 4)

    session.bank = race.bank_after
    session.total_pnl = round(session.total_pnl + pnl_change, 4)

    await db.sessions.replace_one({"id": session_id}, session_to_doc(session))

    winner_dog = next((r for r in race.runners if r.trap == winning_trap), None)
    await sse_publish(session_id, "race_resulted", {
        "race_num": race.race_num,
        "venue": race.venue,
        "winning_trap": winning_trap,
        "winner_name": winner_dog.name if winner_dog else None,
        "winner_odds": winner_dog.odds if winner_dog else None,
        "pnl_change": race.pnl_change,
        "bank_after": race.bank_after,
        "category": race.category.model_dump() if race.category else None,
        "bets": [{
            "rank": b.favourite_rank, "trap": b.dog_trap, "name": b.dog_name,
            "pnl": b.pnl, "result": b.result, "recovery_level": b.recovery_level,
        } for b in race.bets],
        "source": "live_settled",
    })
    await sse_publish(session_id, "bank_updated", {
        "bank": session.bank, "starting_bank": session.config.starting_bank,
        "total_pnl": session.total_pnl,
    })


@api_router.get("/sessions/{session_id}/events")
async def session_event_stream(session_id: str, request: Request):
    """Server-Sent-Events stream for a single session.

    The browser opens `new EventSource('/api/sessions/{id}/events')` and
    receives bet_placed / race_resulted / bank_updated / poll_status events
    in real time.
    """
    from fastapi.responses import StreamingResponse
    doc = await db.sessions.find_one({"id": session_id}, {"_id": 0, "id": 1})
    if not doc:
        raise HTTPException(404, "Session not found")

    async def event_generator():
        # Send an initial "ready" frame so the client knows the channel is open.
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
            "X-Accel-Buffering": "no",  # disable nginx buffering for true streaming
        },
    )


@api_router.post("/sessions/{session_id}/refresh-live-settlement")
async def refresh_live_settlement(session_id: str, race_id: Optional[str] = None):
    """Manually trigger a one-shot settlement check (no polling loop) for the
    most recent live race, or a specific race_id. Useful when the user
    suspects Betfair has finally settled but the auto-poller hasn't caught it.
    """
    doc = await db.sessions.find_one({"id": session_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Session not found")
    session = doc_to_session(doc)
    races = [r for r in session.races if r.source == "live" and r.betfair_bet_ids]
    if race_id:
        race = next((r for r in races if r.race_id == race_id), None)
    else:
        race = races[-1] if races else None
    if not race:
        raise HTTPException(404, "No live race with placed bets found")

    try:
        cleared = await betfair.list_cleared_orders(
            market_id=race.market_id, bet_ids=race.betfair_bet_ids
        )
    except BetfairError as e:
        raise HTTPException(502, f"Betfair listClearedOrders failed: {e}")

    rows = (cleared or {}).get("clearedOrders") or []
    settled_ids = {r.get("betId") for r in rows if r.get("betId")}
    remaining = [b for b in race.betfair_bet_ids if b not in settled_ids]
    if remaining:
        return {"settled": False, "settled_count": len(settled_ids), "remaining": remaining}
    await _close_live_race(session_id, race.race_id, rows)
    return {"settled": True, "settled_count": len(settled_ids)}


@api_router.get("/betfair/funds")
async def betfair_funds():
    """Return the Betfair account balance — used by Paper-Live / Live to source the bank.
    Falls back to a structured error so the UI can render a helpful message.
    """
    if not betfair.is_configured():
        raise HTTPException(400, "Betfair credentials not configured on server")
    try:
        funds = await betfair.get_account_funds()
        return {
            "available_to_bet": float(funds.get("availableToBetBalance", 0.0) or 0.0),
            "exposure": float(funds.get("exposure", 0.0) or 0.0),
            "exposure_limit": float(funds.get("exposureLimit", 0.0) or 0.0),
            "retained_commission": float(funds.get("retainedCommission", 0.0) or 0.0),
            "wallet": funds.get("wallet") or "UK",
        }
    except BetfairError as e:
        raise HTTPException(502, str(e))


@api_router.post("/sessions/{session_id}/refresh-bank", response_model=Session)
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


@api_router.get("/bank/current")
async def current_bank():
    """Return the ending bank of the most recent session, or None if no sessions exist."""
    doc = await db.sessions.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
    if not doc:
        return {"bank": None}
    return {"bank": doc.get("bank", 0.0), "from_session_id": doc.get("id"), "status": doc.get("status")}


@api_router.get("/daily-stats")
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


class CapPreviewInput(BaseModel):
    stake: float = Field(ge=0.01)
    max_liability_cap: float = Field(ge=0)
    num_favourites: int = Field(default=2, ge=1, le=4)
    commission_rate: float = Field(default=0.05, ge=0, le=0.2)
    iterations: int = Field(default=2000, ge=100, le=10000)
    odds_min: float = Field(default=1.01, ge=1.01)
    odds_max: float = Field(default=1000.0, ge=1.01)
    max_recovery_level: int = Field(default=3, ge=1, le=5)


@api_router.post("/preview-cap")
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
                accum_loss += liability + pending
                if level >= inp.max_recovery_level:
                    return {"bust_level": inp.max_recovery_level, "chain_pnl": chain_pnl, "races": races}
                level += 1
                pending = liability + pending + inp.stake
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


@api_router.get("/betfair/races")
async def betfair_races(minutes_ahead: int = 30, max_results: int = 10):
    try:
        markets = await betfair.list_greyhound_markets(minutes_ahead=minutes_ahead, max_results=max_results)
    except BetfairError as e:
        raise HTTPException(502, f"Betfair error: {e}")
    return {"count": len(markets), "markets": markets}


@api_router.get("/betfair/market/{market_id}/preview")
async def betfair_market_preview(market_id: str):
    """Return the live runners + current lay-side odds for a specific market.

    Used by the frontend "Upcoming Race Preview" panel to show the user the
    field 5 minutes before the off — with live price updates so the user can
    see the market shape as the bet approaches.

    Returns:
        runners: [{trap, name, odds, favourite_rank, selection_id}]
        market_id, market_name, event_name, start_time, category
        last_updated: ISO timestamp
    """
    try:
        book = await betfair.get_market_book(market_id)
    except BetfairError as e:
        raise HTTPException(502, f"Betfair error: {e}")
    if not book:
        raise HTTPException(404, "Market not found or not yet active")

    # Look up the market catalogue for runner names / metadata / venue / name
    try:
        cats = await betfair.list_market_catalogue(market_ids=[market_id])
    except BetfairError:
        cats = []
    m = cats[0] if cats else {}
    runner_meta = {r["selectionId"]: r for r in m.get("runners", [])}

    priced = []
    for br in book.get("runners", []):
        if br.get("status") != "ACTIVE":
            continue
        ex = br.get("ex", {})
        lay_prices = ex.get("availableToLay", [])
        back_prices = ex.get("availableToBack", [])
        if not lay_prices:
            continue
        sel_id = br["selectionId"]
        meta = runner_meta.get(sel_id, {})
        priced.append({
            "selection_id": sel_id,
            "name": meta.get("runnerName", f"Runner {sel_id}"),
            "trap": int(meta.get("metadata", {}).get("CLOTH_NUMBER")
                        or meta.get("metadata", {}).get("TRAP_NUMBER") or 0),
            "odds": round(float(lay_prices[0]["price"]), 2),
            "back_odds": round(float(back_prices[0]["price"]), 2) if back_prices else None,
            "lay_size": round(float(lay_prices[0].get("size") or 0), 2),
        })

    # Assign traps in order if Betfair didn't supply CLOTH_NUMBER
    for i, p in enumerate(priced):
        if not p["trap"]:
            p["trap"] = i + 1

    sorted_by_odds = sorted(priced, key=lambda r: r["odds"])
    rank_by_sel = {r["selection_id"]: idx + 1 for idx, r in enumerate(sorted_by_odds)}
    runners = [
        {**p, "favourite_rank": rank_by_sel[p["selection_id"]]}
        for p in priced
    ]

    market_name = m.get("marketName") or ""
    event_name = (m.get("event") or {}).get("name") or ""
    category = detect_category_from_market_name(market_name, event_name)

    return {
        "market_id": market_id,
        "market_name": market_name,
        "event_name": event_name,
        "start_time": m.get("marketStartTime"),
        "category": category.model_dump(),
        "runners": sorted(runners, key=lambda r: r["trap"]),
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


@api_router.post("/sessions/{session_id}/run-races", response_model=Session)
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


@api_router.post("/sessions/{session_id}/stop", response_model=Session)
async def stop_session(session_id: str):
    doc = await db.sessions.find_one({"id": session_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Session not found")
    session = Session(**doc)
    if session.status == "active":
        session.status = "stopped_manual"
        await db.sessions.replace_one({"id": session_id}, session_to_doc(session))
    return session


# ====================================================================
# Marketing site endpoints (Phase 1 stubs — wired in Phase 2)
# ====================================================================

class CheckoutResponse(BaseModel):
    url: Optional[str] = None
    message: Optional[str] = None
    provider: str
    test_mode: bool = True


@api_router.post("/payments/stripe/checkout")
async def stripe_checkout(request: Request, email: Optional[str] = None):
    """Create a real Stripe Checkout Session via emergentintegrations.

    The Checkout Session redirects to Stripe-hosted payment UI; on success Stripe
    sends the customer back to /checkout/success?session_id=... which polls
    /api/payments/stripe/status/{session_id} until paid, at which point a Licence
    is issued and the licence_key is returned to the success page.
    """
    if not LICENCE_SERVER_MODE:
        raise HTTPException(400, "This server is not the central licence host (set LICENCE_SERVER_MODE=true on lay-hounds.co.uk)")
    origin = str(request.base_url).rstrip("/")
    try:
        return await create_stripe_checkout_session(db=db, origin_url=origin, email=email)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Stripe checkout create failed")
        raise HTTPException(502, f"Stripe checkout failed: {type(e).__name__}: {e}")


@api_router.get("/payments/stripe/status/{session_id}")
async def stripe_status(session_id: str, request: Request):
    """Polled by the success page until payment_status == 'paid'. Returns licence_key on first paid."""
    if not LICENCE_SERVER_MODE:
        raise HTTPException(400, "Not the central licence host")
    origin = str(request.base_url).rstrip("/")
    try:
        return await get_stripe_checkout_status(db=db, session_id=session_id, origin_url=origin)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Stripe status check failed")
        raise HTTPException(502, f"Stripe status check failed: {type(e).__name__}: {e}")


@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request, stripe_signature: Optional[str] = Header(None)):
    if not LICENCE_SERVER_MODE:
        raise HTTPException(404, "No webhook endpoint here")
    body = await request.body()
    origin = str(request.base_url).rstrip("/")
    try:
        return await handle_stripe_webhook(db=db, body=body, signature=stripe_signature or "", origin_url=origin)
    except Exception as e:
        logger.exception("Stripe webhook handling failed")
        raise HTTPException(400, f"Webhook error: {type(e).__name__}: {e}")


@api_router.post("/payments/paypal/checkout")
async def paypal_checkout():
    """PayPal subscription order — placeholder until you drop your PayPal REST app credentials."""
    paypal_id = os.environ.get("PAYPAL_CLIENT_ID", "")
    if not paypal_id or paypal_id.startswith("PLACEHOLDER"):
        return {
            "provider": "paypal",
            "message": "PayPal checkout — drop your PayPal REST client_id + client_secret in backend/.env and we'll wire the live flow next.",
            "test_mode": True,
        }
    return {"provider": "paypal", "url": "https://www.paypal.com/checkoutnow?token=PLACEHOLDER", "test_mode": True}


class ContactInput(BaseModel):
    email: str = Field(min_length=3, max_length=120)
    message: str = Field(min_length=1, max_length=4000)


@api_router.post("/contact")
async def contact(inp: ContactInput):
    """Persist contact-form submissions to MongoDB. Phase 2 will email + Slack alert."""
    if "@" not in inp.email or "." not in inp.email:
        raise HTTPException(400, "Invalid email")
    doc = {
        "id": str(uuid.uuid4()),
        "email": inp.email.strip(),
        "message": inp.message.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "handled": False,
    }
    await db.contact_messages.insert_one(doc)
    logger.info("contact form: %s", inp.email)
    return {"ok": True}


app.include_router(api_router)

# Licence routers (always mount the customer one; mount central only on the host with LICENCE_SERVER_MODE=true)
if LICENCE_SERVER_URL:
    app.include_router(build_customer_router(db), prefix="/api")
if LICENCE_SERVER_MODE:
    app.include_router(build_central_router(db), prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def startup_tasks():
    if LICENCE_SERVER_URL:
        asyncio.create_task(background_revalidate_loop(db))
        logger.info("Licence revalidate loop scheduled (LICENCE_SERVER_URL=%s)", LICENCE_SERVER_URL)
    if LICENCE_SERVER_MODE:
        logger.info("Running in CENTRAL LICENCE SERVER mode — /api/licences/* + /api/webhook/stripe live")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
