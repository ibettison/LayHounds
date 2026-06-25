import random
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from betfair_client import betfair
from models import Greyhound, Session, UK_GREYHOUND_NAMES
from race_categories import (
    RaceCategory,
    detect_category_from_market_name,
    random_category,
    winner_weights,
)

TRAP_FROM_NAME_RE = re.compile(r"^\s*(?:trap|t|no\.?)?\s*([1-6])(?:\D|$)", re.IGNORECASE)


SIMULATOR_VENUES = [
    "Romford", "Hove", "Nottingham", "Sheffield", "Crayford", "Towcester",
    "Newcastle", "Sunderland", "Monmore", "Perry Barr", "Yarmouth", "Oxford",
    "Doncaster", "Swindon", "Kinsley", "Pelaw Grange",
]

BETFAIR_PRICE_STEPS = [
    (2.0, 0.01),
    (3.0, 0.02),
    (4.0, 0.05),
    (6.0, 0.1),
    (10.0, 0.2),
    (20.0, 0.5),
    (30.0, 1.0),
]


def _round_exchange_price(price: float) -> float:
    """Round a simulated price to a familiar Betfair-style ladder step."""
    price = max(1.01, min(float(price), 30.0))
    for upper, step in BETFAIR_PRICE_STEPS:
        if price <= upper:
            return round(round(price / step) * step, 2)
    return round(price)


def _simulated_lay_odds(category: RaceCategory) -> List[float]:
    """Create a plausible six-runner greyhound market.

    We model underlying runner strength, normalise it into a book, then apply a
    small exchange lay-side spread. This gives more natural races than a linear
    odds ladder while keeping the favourite ranks coherent.
    """
    grade = category.grade
    if grade in {"OR", "A1", "A2"}:
        shape, favourite_push = 1.15, 1.22
    elif grade in {"A8", "A9", "A10", "A11", "H1", "H2", "H3"}:
        shape, favourite_push = 1.75, 1.04
    else:
        shape, favourite_push = 1.45, 1.12

    if category.distance_band in {"stayer", "marathon"}:
        shape += 0.2
        favourite_push -= 0.04

    strengths = [random.gammavariate(shape, 1.0) for _ in range(6)]
    strongest = max(range(6), key=lambda idx: strengths[idx])
    strengths[strongest] *= random.uniform(favourite_push, favourite_push + 0.35)

    total_strength = sum(strengths) or 1.0
    fair_probs = [s / total_strength for s in strengths]
    exchange_margin = random.uniform(0.97, 1.04)
    lay_spread = random.uniform(1.015, 1.055)
    odds = [
        _round_exchange_price(1.0 / max(0.045, min(0.62, p * exchange_margin)) * lay_spread)
        for p in fair_probs
    ]

    ranked = sorted(odds)
    for idx in range(1, len(ranked)):
        if ranked[idx] <= ranked[idx - 1]:
            ranked[idx] = _round_exchange_price(ranked[idx - 1] + (0.02 if ranked[idx - 1] < 3 else 0.1))
    random.shuffle(ranked)
    return ranked


def trap_from_runner_name(name: str) -> int:
    """Return a trap number from Betfair runner names like '1. Dog Name'."""
    match = TRAP_FROM_NAME_RE.search(name or "")
    return int(match.group(1)) if match else 0


def fill_missing_traps(priced: List[dict]) -> None:
    """Fill any missing traps without assuming row order for short fields."""
    used = {p["trap"] for p in priced if p.get("trap")}
    unused = iter(trap for trap in range(1, 7) if trap not in used)
    for p in priced:
        if not p.get("trap"):
            p["trap"] = next(unused, 0)


def generate_race(race_num: int) -> tuple[List[Greyhound], str, RaceCategory]:
    venue = random.choice(SIMULATOR_VENUES)
    category = random_category()
    names = random.sample(UK_GREYHOUND_NAMES, 6)
    raw_odds = _simulated_lay_odds(category)
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
            name = meta.get("runnerName", f"Runner {sel_id}")
            trap = int(meta.get("metadata", {}).get("CLOTH_NUMBER") or meta.get("metadata", {}).get("TRAP_NUMBER") or 0)
            priced.append({
                "selection_id": sel_id,
                "name": name,
                "trap": trap or trap_from_runner_name(name),
                "odds": float(odds),
            })
        if len(priced) < 2:
            continue
        fill_missing_traps(priced)
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


async def fetch_market_result(market_id: str) -> Optional[Dict[str, Any]]:
    """Return the winning trap for a settled Betfair market when available."""
    book = await betfair.get_market_book(market_id)
    if not book:
        return None
    market_status = book.get("status")
    winner = next((r for r in book.get("runners", []) if r.get("status") == "WINNER"), None)
    if market_status != "CLOSED" or not winner:
        return None

    try:
        cats = await betfair.list_market_catalogue(market_ids=[market_id])
    except Exception:
        cats = []
    market = cats[0] if cats else {}
    runner_meta = {r.get("selectionId"): r for r in market.get("runners", [])}
    selection_id = winner.get("selectionId")
    meta = runner_meta.get(selection_id, {})
    name = meta.get("runnerName", f"Runner {selection_id}")
    trap = int(
        meta.get("metadata", {}).get("CLOTH_NUMBER")
        or meta.get("metadata", {}).get("TRAP_NUMBER")
        or 0
    )
    return {
        "market_id": market_id,
        "market_status": market_status,
        "selection_id": selection_id,
        "winner_name": name,
        "winning_trap": trap or trap_from_runner_name(name),
        "settled_at": datetime.now(timezone.utc).isoformat(),
    }


def session_to_doc(s: Session) -> dict:
    return s.model_dump()


def doc_to_session(d: dict) -> Session:
    d = {k: v for k, v in d.items() if k != "_id"}
    return Session(**d)


