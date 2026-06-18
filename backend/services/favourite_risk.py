from __future__ import annotations

from typing import List, Optional

from models import Greyhound, SessionConfig
from services.racing import get_runner_by_rank


FAVOURITE_RISK_LABELS = {
    "strong_favourite_gap": "Favourite probability gap is above 15%",
    "fav_inside_trap": "Favourite is Trap 1 or 2",
    "fav_inside_trap_sprint": "Favourite is Trap 1 or 2 below 300m",
    "second_fav_inside_trap_sprint": "Second favourite is Trap 1 or 2 below 300m",
}

STRONG_FAVOURITE_GAP_THRESHOLD = 0.15


def implied_probability(runner: Greyhound) -> float:
    return round(1.0 / max(runner.odds, 1.01), 6)


def favourite_probability_gap(favourite: Greyhound, second_favourite: Greyhound) -> float:
    return round(implied_probability(favourite) - implied_probability(second_favourite), 6)


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

    gap = favourite_probability_gap(favourite, second_favourite)
    reasons: List[str] = []
    if gap > STRONG_FAVOURITE_GAP_THRESHOLD:
        reasons.append("strong_favourite_gap")

    if favourite.trap in (1, 2) and distance_m is not None and distance_m < 300:
        reasons.append("fav_inside_trap_sprint")

    if second_favourite.trap in (1, 2) and distance_m is not None and distance_m < 300:
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
    if "strong_favourite_gap" in reasons or "fav_inside_trap_sprint" in reasons:
        ranks = [rank for rank in ranks if rank != 1]
        if "strong_favourite_gap" in reasons and 2 not in ranks:
            ranks.insert(0, 2)

    if "second_fav_inside_trap_sprint" in reasons:
        ranks = [rank for rank in ranks if rank != 2]

    return ranks, reasons


def format_skip_reasons(reasons: List[str]) -> List[str]:
    return [FAVOURITE_RISK_LABELS.get(reason, reason) for reason in reasons]
