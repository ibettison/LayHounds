import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from betfair_client import betfair, BetfairError
from db import db
from models import Session
from services.racing import doc_to_session, session_to_doc
from services.recovery import apply_settled_bet_to_chain
from services.session_status import apply_stop_conditions
from session_events import publish as sse_publish

logger = logging.getLogger(__name__)


async def _close_live_race(session_id: str, race_id: str, cleared_rows: List[Dict[str, Any]]):
    """Update a live race/session from Betfair cleared orders."""
    doc = await db.sessions.find_one({"id": session_id}, {"_id": 0})
    if not doc:
        return
    session = doc_to_session(doc)
    race = next((r for r in session.races if r.race_id == race_id), None)
    if not race:
        logger.warning("Settlement received for unknown race_id=%s session=%s", race_id, session_id[:8])
        return

    by_bet = {r.get("betId"): r for r in cleared_rows if r.get("betId")}

    pnl_change = 0.0
    newly_settled = []
    for bet in race.bets:
        if bet.settled_at or bet.result:
            continue
        bet_id = bet.betfair_bet_id
        row = by_bet.get(bet_id) if bet_id else None
        if row is None:
            continue

        profit = float(row.get("profit") or 0.0)
        bet.pnl = round(profit, 4)
        bet.settled_profit = round(profit, 4)
        bet.betfair_status = row.get("betStatus")
        bet.settled_at = datetime.now(timezone.utc).isoformat()
        bet.matched_size = (
            float(row.get("sizeSettled") or row.get("sizeMatched") or bet.matched_size or 0.0)
            or bet.matched_size
        )
        bet.matched_price = (
            float(row.get("priceMatched") or row.get("priceRequested") or bet.matched_price or 0.0)
            or bet.matched_price
        )
        bet.placement_status = "settled"
        if bet.matched_price:
            bet.slippage_ticks = betfair.count_ticks(bet.odds, bet.matched_price)
        if profit >= 0:
            bet.result = "win"
        else:
            bet.result = "loss"
        pnl_change += profit
        newly_settled.append(bet)

    for bet in newly_settled:
        chain = session.recovery_chains.get(str(bet.recovery_rank or bet.favourite_rank))
        if chain:
            apply_settled_bet_to_chain(chain, bet, session.config, bet.pnl or 0.0)

    losing_bet = next((b for b in race.bets if b.result == "loss"), None)
    winning_trap = losing_bet.dog_trap if losing_bet else 0
    race_settled = all((not b.betfair_bet_id) or b.settled_at or b.result for b in race.bets)
    if race_settled:
        race.winning_trap = winning_trap

    race.pnl_change = round(race.pnl_change + pnl_change, 4)
    race.bank_after = round(session.bank + pnl_change, 4)

    session.bank = race.bank_after
    session.total_pnl = round(session.total_pnl + pnl_change, 4)
    apply_stop_conditions(session, allow_recovery_overrun=False)

    await db.sessions.replace_one({"id": session_id}, session_to_doc(session))

    winner_dog = next((r for r in race.runners if r.trap == winning_trap), None)
    await sse_publish(session_id, "race_resulted", {
        "race_num": race.race_num,
        "venue": race.venue,
        "winning_trap": race.winning_trap,
        "winner_name": winner_dog.name if winner_dog else None,
        "winner_odds": winner_dog.odds if winner_dog else None,
        "pnl_change": race.pnl_change,
        "bank_after": race.bank_after,
        "category": race.category.model_dump() if race.category else None,
        "bets": [{
            "rank": b.favourite_rank,
            "trap": b.dog_trap,
            "name": b.dog_name,
            "pnl": b.pnl,
            "result": b.result,
            "recovery_level": b.recovery_level,
            "recovery_rank": b.recovery_rank or b.favourite_rank,
        } for b in race.bets],
        "source": "live_settled",
        "fully_settled": race_settled,
    })
    await sse_publish(session_id, "bank_updated", {
        "bank": session.bank,
        "starting_bank": session.config.starting_bank,
        "total_pnl": session.total_pnl,
        "status": session.status,
    })


async def reconcile_live_settlements(session_id: str, race_id: Optional[str] = None) -> Dict[str, Any]:
    """Check Betfair cleared-order history for unresolved live bets.

    Recovery is applied as soon as each individual Betfair bet is settled, so a
    losing selection can affect the next race even if its paired bet is pending.
    """
    doc = await db.sessions.find_one({"id": session_id}, {"_id": 0})
    if not doc:
        return {"found": False, "settled": 0, "pending": 0, "races": []}

    session = doc_to_session(doc)
    candidates = [
        r for r in session.races
        if r.source == "live"
        and r.betfair_bet_ids
        and any(b.betfair_bet_id and not b.settled_at and not b.result for b in r.bets)
        and (race_id is None or r.race_id == race_id)
    ]

    results = []
    settled_count = 0
    pending_count = 0

    for race in candidates:
        cleared = await betfair.list_cleared_orders(
            market_id=race.market_id,
            bet_ids=race.betfair_bet_ids,
        )
        rows = (cleared or {}).get("clearedOrders") or []
        settled_ids = {r.get("betId") for r in rows if r.get("betId")}
        remaining = [b for b in race.betfair_bet_ids if b not in settled_ids]
        newly_available = [
            b.betfair_bet_id for b in race.bets
            if b.betfair_bet_id in settled_ids and not b.settled_at and not b.result
        ]

        if not newly_available:
            pending_count += 1
            results.append({
                "race_id": race.race_id,
                "race_num": race.race_num,
                "market_id": race.market_id,
                "settled": False,
                "settled_count": len(settled_ids),
                "remaining": remaining,
            })
            continue

        await _close_live_race(session_id, race.race_id, rows)
        if remaining:
            pending_count += 1
        else:
            settled_count += 1
        results.append({
            "race_id": race.race_id,
            "race_num": race.race_num,
            "market_id": race.market_id,
            "settled": not remaining,
            "settled_count": len(settled_ids),
            "remaining": remaining,
        })

    return {
        "found": bool(candidates),
        "settled": settled_count,
        "pending": pending_count,
        "races": results,
    }
