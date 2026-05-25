"""In-process Server-Sent-Events bus for live trading feedback.

Each session can have N concurrent SSE listeners (typically 1 — the user's
browser). The race-execution code calls `publish(session_id, event)` whenever
something interesting happens (bet placed, settlement received, bank updated,
recovery level changed). The listener task fans out to every queue currently
attached to that session.

We deliberately keep this in-process (no Redis) because:
  - the app runs on a single uvicorn worker behind nginx;
  - reconnect/refresh is gracefully handled by EventSource on the browser side;
  - persistent history of events is already in the Session document — SSE is
    purely a real-time push channel, not a queue of record.

Events emitted (event name + JSON payload shape):
  bet_placed     {race_num, bets:[{rank,trap,name,odds,stake,liability,recovery_level}], market_id}
  bet_settled    {race_num, bets:[{rank,trap,pnl,won}], winning_trap, pnl_change, bank_after}
  race_resulted  {race_num, winning_trap, winner_name, pnl_change, bank_after}
  bank_updated   {bank, starting_bank}
  poll_status    {race_num, attempt, max_attempts, market_status}
  chain_update   {rank, level, busted, pending_stake}
  error          {message, context}
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict
from typing import Any, AsyncIterator, Dict, List

logger = logging.getLogger("session_events")

# session_id -> list of subscriber queues
_subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
# Optional small ring-buffer of the last N events per session so a late-attaching
# listener (page refresh during a race) catches up quickly.
_recent: Dict[str, List[dict]] = defaultdict(list)
_RECENT_MAX = 30


async def publish(session_id: str, event: str, data: Any) -> None:
    """Broadcast an event to all attached listeners + add to recent ring."""
    payload = {"ts": time.time(), "event": event, "data": data}
    _recent[session_id].append(payload)
    if len(_recent[session_id]) > _RECENT_MAX:
        _recent[session_id] = _recent[session_id][-_RECENT_MAX:]
    queues = list(_subscribers.get(session_id, []))
    logger.debug("publish %s.%s -> %d listeners", session_id[:8], event, len(queues))
    for q in queues:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            logger.warning("Listener queue full for session %s — dropping event %s", session_id[:8], event)


async def subscribe(session_id: str, replay_recent: bool = True) -> AsyncIterator[dict]:
    """Yield events for `session_id` until the consumer disconnects.

    If `replay_recent` is True, immediately re-emit the last _RECENT_MAX events
    so a freshly-connected client sees the most recent state.
    """
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    _subscribers[session_id].append(q)
    try:
        # Replay recent first
        if replay_recent:
            for ev in _recent.get(session_id, [])[-_RECENT_MAX:]:
                yield ev
        # Then live-stream
        while True:
            ev = await q.get()
            yield ev
    finally:
        try:
            _subscribers[session_id].remove(q)
        except ValueError:
            pass


def format_sse(event_dict: dict) -> bytes:
    """Encode a dict as a single SSE frame (`event:` + `data:` + double newline)."""
    name = event_dict.get("event", "message")
    data = json.dumps(event_dict.get("data", {}), default=str)
    return f"event: {name}\ndata: {data}\n\n".encode("utf-8")


def clear_session(session_id: str) -> None:
    """Drop subscribers + recent buffer when a session is deleted."""
    _subscribers.pop(session_id, None)
    _recent.pop(session_id, None)
