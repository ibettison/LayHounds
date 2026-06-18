from models import Greyhound, SessionConfig
from services.favourite_risk import (
    favourite_probability_gap,
    favourite_risk_bet_plan,
    favourite_risk_skip_reasons,
)


def _runners(fav_trap=3, fav_odds=2.0, second_trap=4, second_odds=3.0, count=6):
    runners = [
        Greyhound(trap=fav_trap, name="Favourite", odds=fav_odds, favourite_rank=1),
        Greyhound(trap=second_trap, name="Second", odds=second_odds, favourite_rank=2),
    ]
    for idx in range(3, count + 1):
        runners.append(Greyhound(trap=idx + 10, name=f"Runner {idx}", odds=5.0 + idx, favourite_rank=idx))
    return runners


def test_probability_gap_uses_implied_probabilities():
    fav, second = _runners(fav_odds=2.0, second_odds=4.0)[:2]

    assert favourite_probability_gap(fav, second) == 0.25


def test_strict_guard_reports_rank_specific_reasons():
    config = SessionConfig(favourite_risk_guard="strict")

    reasons = favourite_risk_skip_reasons(_runners(fav_trap=1, fav_odds=2.0, second_odds=4.0, count=5), config, distance_m=285)

    assert reasons == ["strong_favourite_gap", "fav_inside_trap_sprint"]


def test_strict_guard_allows_inside_traps_on_normal_and_longer_races():
    config = SessionConfig(favourite_risk_guard="strict")

    assert favourite_risk_skip_reasons(_runners(fav_trap=1, fav_odds=3.0, second_odds=3.2), config, distance_m=480) == []


def test_balanced_guard_only_skips_inside_trap_on_short_sprints():
    config = SessionConfig(favourite_risk_guard="balanced")

    assert favourite_risk_skip_reasons(_runners(fav_trap=1, fav_odds=3.0, second_odds=3.2), config, distance_m=480) == []
    assert favourite_risk_skip_reasons(_runners(fav_trap=1, fav_odds=3.0, second_odds=3.2), config, distance_m=285) == ["fav_inside_trap_sprint"]


def test_guard_off_never_skips():
    config = SessionConfig(favourite_risk_guard="off")

    assert favourite_risk_skip_reasons(_runners(fav_trap=1, fav_odds=1.5, second_odds=5.0, count=5), config, distance_m=240) == []


def test_strict_guard_places_second_favourite_for_gap_without_replacement():
    config = SessionConfig(favourite_risk_guard="strict", num_favourites=1)

    ranks, reasons = favourite_risk_bet_plan(_runners(fav_trap=3, fav_odds=2.0, second_trap=4, second_odds=3.0), config, distance_m=480)

    assert ranks == [2]
    assert reasons == ["strong_favourite_gap"]


def test_guard_blocks_gap_fallback_when_second_favourite_is_inside_short_sprint():
    config = SessionConfig(favourite_risk_guard="strict", num_favourites=1)

    ranks, reasons = favourite_risk_bet_plan(_runners(fav_trap=3, fav_odds=2.0, second_trap=1, second_odds=3.0), config, distance_m=285)

    assert ranks == []
    assert reasons == ["strong_favourite_gap", "second_fav_inside_trap_sprint"]


def test_guard_keeps_third_and_fourth_when_first_and_second_are_filtered():
    config = SessionConfig(favourite_risk_guard="strict", num_favourites=4)

    ranks, reasons = favourite_risk_bet_plan(_runners(fav_trap=3, fav_odds=2.0, second_trap=1, second_odds=3.0), config, distance_m=285)

    assert ranks == [3, 4]
    assert reasons == ["strong_favourite_gap", "second_fav_inside_trap_sprint"]


def test_guard_does_not_skip_small_fields_by_itself():
    config = SessionConfig(favourite_risk_guard="strict", num_favourites=1)

    ranks, reasons = favourite_risk_bet_plan(_runners(fav_trap=3, fav_odds=3.0, second_trap=4, second_odds=3.2, count=5), config, distance_m=480)

    assert ranks == [1]
    assert reasons == []
