import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from betfair_client import betfair, BetfairError
from db import db
from models import Session
from services.racing import doc_to_session, session_to_doc
from session_events import publish as sse_publish

logger = logging.getLogger(__name__)

async def poll_live_settlement(session_id: str, race_id: str, market_id: str,
                                bet_ids: List[str]):
    """Background task: poll Betfair for settled-order results on a live race.

    Runs for up to ~30 minutes after a live bet is placed. Once Betfair returns
    SETTLED rows for every bet_id, we close the race in the local session
    (winning_trap, pnl_change, recovery chain updates) and emit a
    `race_resulted` SSE so the UI animates. While we're still waiting, emits
    a heartbeat `poll_status` SSE every poll so the UI shows "Waiting for
    Betfair settlement…" with a live attempt counter.
    """
    if not bet_ids:
        return
    POLL_INTERVAL = 10  # seconds
    MAX_ATTEMPTS = 180  # 30 minutes; Betfair greyhound settlement can lag.
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
                "market_status": (
                    "market_closed_waiting_settlement"
                    if remaining
                    else "settled"
                ),
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
            "message": "Settlement polling timed out (30 min) - refresh manually.",
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
            new_accum = round(
                chain.accumulated_loss
                + bet.liability
                + session.config.stake,
                4,
            )
            if chain.level >= session.config.max_recovery_level:
                chain.busted = True
                chain.level = session.config.max_recovery_level
                chain.pending_stake = session.config.stake
                chain.accumulated_loss = new_accum
            else:
                chain.level += 1
                chain.accumulated_loss = new_accum
                chain.pending_stake = round(new_accum, 4)
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

