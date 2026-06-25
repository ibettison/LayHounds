from __future__ import annotations

from typing import List, Optional

from models import Greyhound, SessionConfig
from services.racing import get_runner_by_rank


FAVOURITE_RISK_LABELS = {
    "favourite_gap_above_threshold": "Favourite/second favourite odds gap is above the configured threshold",
    "second_favourite_gap_below_threshold": "Second favourite odds gap is below the configured threshold",
    "second_favourite_gap_above_threshold": "Second favourite odds gap is above the configured threshold",
    "fav_inside_trap_sprint": "Favourite is Trap 1 or 2 in a sprint",
    "second_fav_inside_trap_sprint": "Second favourite is Trap 1 or 2 in a sprint",
}

DEFAULT_FAVOURITE_GAP_THRESHOLD = 0.10
DEFAULT_SECOND_FAVOURITE_GAP_MIN = 0.05
DEFAULT_SECOND_FAVOURITE_GAP_MAX = 0.30


def implied_probability(runner: Greyhound) -> float:
    return round(1.0 / max(runner.odds, 1.01), 6)


def favourite_probability_gap(favourite: Greyhound, second_favourite: Greyhound) -> float:
    return round(implied_probability(favourite) - implied_probability(second_favourite), 6)


def favourite_odds_gap(favourite: Greyhound, second_favourite: Greyhound) -> float:
    if favourite.odds <= 0:
        return 0.0
    return round((second_favourite.odds - favourite.odds) / favourite.odds, 6)


def is_sprint(distance_m: Optional[int]) -> bool:
    return distance_m is not None and distance_m <= 320


def favourite_risk_skip_reasons(
    runners: List[Greyhound],
    config: SessionConfig,
    *,
    distance_m: Optional[int] = None,
) -> List[str]:
    guard = getattr(config, "favourite_risk_guard", "strict") or "strict"
    if guard == "off":
        return []

    try:
        favourite = get_runner_by_rank(runners, 1)
        second_favourite = get_runner_by_rank(runners, 2)
    except ValueError:
        return []

    gap = favourite_odds_gap(favourite, second_favourite)
    fav_gap = getattr(config, "favourite_gap_threshold", DEFAULT_FAVOURITE_GAP_THRESHOLD)
    second_min = getattr(config, "second_favourite_gap_min", DEFAULT_SECOND_FAVOURITE_GAP_MIN)
    second_max = getattr(config, "second_favourite_gap_max", DEFAULT_SECOND_FAVOURITE_GAP_MAX)
    reasons: List[str] = []
    if gap > fav_gap:
        reasons.append("favourite_gap_above_threshold")
    if gap < second_min:
        reasons.append("second_favourite_gap_below_threshold")
    if gap > second_max:
        reasons.append("second_favourite_gap_above_threshold")

    if favourite.trap in (1, 2) and is_sprint(distance_m):
        reasons.append("fav_inside_trap_sprint")

    if second_favourite.trap in (1, 2) and is_sprint(distance_m):
        reasons.append("second_fav_inside_trap_sprint")
    return reasons


def favourite_risk_bet_plan(
    runners: List[Greyhound],
    config: SessionConfig,
    *,
    distance_m: Optional[int] = None,
) -> tuple[List[int], List[str]]:
    base_ranks = list(range(1, config.num_favourites + 1))
    guard = getattr(config, "favourite_risk_guard", "strict") or "strict"
    if guard == "off":
        return base_ranks, []

    reasons = favourite_risk_skip_reasons(runners, config, distance_m=distance_m)
    if not reasons:
        return base_ranks, []

    ranks = list(base_ranks)
    if "favourite_gap_above_threshold" in reasons or "fav_inside_trap_sprint" in reasons:
        ranks = [rank for rank in ranks if rank != 1]

    if (
        "second_favourite_gap_below_threshold" in reasons
        or "second_favourite_gap_above_threshold" in reasons
        or "second_fav_inside_trap_sprint" in reasons
    ):
        ranks = [rank for rank in ranks if rank != 2]

    return ranks, reasons


def format_skip_reasons(reasons: List[str]) -> List[str]:
    return [FAVOURITE_RISK_LABELS.get(reason, reason) for reason in reasons]
