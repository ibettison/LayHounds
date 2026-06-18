import csv
from io import StringIO

from models import SessionConfig
from services.backtest_analysis import build_analysis_csv, generated_race_snapshots


def _rows(csv_body):
    return list(csv.DictReader(StringIO(csv_body)))


def test_backtest_csv_contains_filter_summaries_and_race_fields():
    config = SessionConfig(
        mode="simulator",
        num_favourites=1,
        stake=0.05,
        starting_bank=100.0,
        stop_loss=1000.0,
        max_liability_cap=0,
        commission_rate=0.05,
    )
    snapshots = generated_race_snapshots(25, seed=123)

    rows = _rows(build_analysis_csv(snapshots, config, include_races=True, repeat_50_samples=3, seed=123))

    summary_rows = [r for r in rows if r["row_type"] == "summary"]
    race_rows = [r for r in rows if r["row_type"] == "race"]
    diagnostic_rows = [r for r in rows if r["row_type"] == "repeat_50_diagnostic"]

    assert len(summary_rows) == 8
    assert len(race_rows) == 25 * 8
    assert len(diagnostic_rows) == 1

    first_race = race_rows[0]
    for key in (
        "favourite_odds",
        "second_favourite_odds",
        "favourite_implied_probability",
        "second_favourite_implied_probability",
        "implied_probability_gap",
        "favourite_trap",
        "second_favourite_trap",
        "race_distance",
        "number_of_runners",
        "favourite_won",
        "lay_profit_loss",
        "recovery_balance_before",
        "recovery_balance_after",
        "bank_balance_after",
    ):
        assert first_race[key] != ""


def test_backtest_uses_actual_settled_pnl_not_target_profit_formula():
    config = SessionConfig(
        mode="simulator",
        num_favourites=1,
        stake=0.05,
        starting_bank=100.0,
        stop_loss=1000.0,
        max_liability_cap=0,
        commission_rate=0.05,
    )
    snapshots = generated_race_snapshots(80, seed=456)

    rows = _rows(build_analysis_csv(snapshots, config, include_races=True, repeat_50_samples=0, seed=456))
    all_summary = next(r for r in rows if r["row_type"] == "summary" and r["filter_key"] == "all")
    all_races = [r for r in rows if r["row_type"] == "race" and r["filter_key"] == "all"]

    settled_total = round(sum(float(r["lay_profit_loss"]) for r in all_races), 4)
    formula_total = round(int(all_summary["bets_placed"]) * config.stake * (1 - config.commission_rate), 4)

    assert round(float(all_summary["final_profit_loss"]), 4) == settled_total
    assert settled_total != formula_total


def test_unseeded_generation_advances_between_calls():
    first = generated_race_snapshots(5)
    second = generated_race_snapshots(5)

    first_signature = [(r.venue, r.winning_trap, [runner.odds for runner in r.runners]) for r in first]
    second_signature = [(r.venue, r.winning_trap, [runner.odds for runner in r.runners]) for r in second]

    assert first_signature != second_signature
