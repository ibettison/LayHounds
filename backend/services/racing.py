import random
import re
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


def session_to_doc(s: Session) -> dict:
    return s.model_dump()


def doc_to_session(d: dict) -> Session:
    d = {k: v for k, v in d.items() if k != "_id"}
    return Session(**d)


