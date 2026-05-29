import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from betfair_client import betfair, BetfairError
from db import db
from models import Session
from services.racing import doc_to_session, session_to_doc
from session_events import publish as sse_publish

logger = logging.getLogger(__name__)

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
    if race.winning_trap:
        return

    # Map bet_id → row for fast lookup
    by_bet = {r.get("betId"): r for r in cleared_rows if r.get("betId")}

    pnl_change = 0.0
    losses_by_rank: Dict[int, float] = {}
    wins_by_rank: Dict[int, float] = {}
    for bet in race.bets:
        bet_id = bet.betfair_bet_id
        row = by_bet.get(bet_id) if bet_id else None
        if row is None:
            continue
        profit = float(row.get("profit") or 0.0)  # signed, gross
        bet.pnl = round(profit, 4)
        bet.settled_profit = round(profit, 4)
        bet.betfair_status = row.get("betStatus")
        bet.settled_at = datetime.now(timezone.utc).isoformat()
        bet.matched_size = float(row.get("sizeSettled") or row.get("sizeMatched") or bet.matched_size or 0.0) or bet.matched_size
        bet.matched_price = float(row.get("priceMatched") or row.get("priceRequested") or bet.matched_price or 0.0) or bet.matched_price
        bet.placement_status = "settled"
        if bet.matched_price:
            bet.slippage_ticks = betfair.count_ticks(bet.odds, bet.matched_price)
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
            base_level = max(chain.level, bet.recovery_level)
            new_accum = round(
                chain.accumulated_loss
                + bet.liability
                + session.config.stake,
                4,
            )
            if base_level >= session.config.max_recovery_level:
                chain.busted = True
                chain.level = session.config.max_recovery_level
                chain.pending_stake = session.config.stake
                chain.accumulated_loss = new_accum
            else:
                chain.level = base_level + 1
                chain.accumulated_loss = new_accum
                chain.pending_stake = round(new_accum, 4)
        else:
            # A later base-level bet can settle before/after an earlier race.
            # Only clear recovery if this bet represented the current recovery
            # level. A stale L0 win must not wipe losses that arrived meanwhile.
            if bet.recovery_level >= chain.level or chain.accumulated_loss <= 0:
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


async def reconcile_live_settlements(session_id: str, race_id: Optional[str] = None) -> Dict[str, Any]:
    """Check Betfair cleared-order history for unresolved live races.

    This is the authoritative settlement path: no simulated winner, no guesswork.
    It checks actual Betfair cleared orders and closes local races only when every
    matched bet for that race appears in settled history.
    """
    doc = await db.sessions.find_one({"id": session_id}, {"_id": 0})
    if not doc:
        return {"found": False, "settled": 0, "pending": 0, "races": []}

    session = doc_to_session(doc)
    candidates = [
        r for r in session.races
        if r.source == "live"
        and not r.winning_trap
        and r.betfair_bet_ids
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
        if remaining:
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
        settled_count += 1
        results.append({
            "race_id": race.race_id,
            "race_num": race.race_num,
            "market_id": race.market_id,
            "settled": True,
            "settled_count": len(settled_ids),
            "remaining": [],
        })

    return {
        "found": bool(candidates),
        "settled": settled_count,
        "pending": pending_count,
        "races": results,
    }

