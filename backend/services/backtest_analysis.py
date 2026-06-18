from __future__ import annotations

import csv
import io
import random
import statistics
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from models import Greyhound, LayBet, Race, RecoveryChain, Session, SessionConfig
from services.racing import generate_race, get_runner_by_rank, pick_winner
from services.recovery import apply_settled_bet_to_chain, plan_recovery_bet, recovery_total


@dataclass(frozen=True)
class RaceSnapshot:
    race_num: int
    venue: str
    runners: List[Greyhound]
    winning_trap: int
    distance_m: int
    commission_rate: Optional[float] = None


@dataclass(frozen=True)
class AnalysisFilter:
    key: str
    label: str
    should_skip: Callable[[Greyhound, Greyhound, RaceSnapshot], bool]


def _fav_pair(race: RaceSnapshot) -> Tuple[Greyhound, Greyhound]:
    return get_runner_by_rank(race.runners, 1), get_runner_by_rank(race.runners, 2)


def _prob(runner: Greyhound) -> float:
    return round(1.0 / max(runner.odds, 1.01), 6)


def _prob_gap(fav: Greyhound, second: Greyhound) -> float:
    return round(_prob(fav) - _prob(second), 6)


FILTERS = [
    AnalysisFilter("all", "All races", lambda _fav, _second, _race: False),
    AnalysisFilter(
        "exclude_gap_gt_10",
        "Exclude races where probability gap > 10%",
        lambda fav, second, _race: _prob_gap(fav, second) > 0.10,
    ),
    AnalysisFilter(
        "exclude_gap_gt_15",
        "Exclude races where probability gap > 15%",
        lambda fav, second, _race: _prob_gap(fav, second) > 0.15,
    ),
    AnalysisFilter(
        "exclude_gap_gt_20",
        "Exclude races where probability gap > 20%",
        lambda fav, second, _race: _prob_gap(fav, second) > 0.20,
    ),
    AnalysisFilter(
        "exclude_fav_trap_1_or_2",
        "Exclude races where favourite is Trap 1 or 2",
        lambda fav, _second, _race: fav.trap in (1, 2),
    ),
    AnalysisFilter(
        "exclude_fav_trap_1_or_2_sprint",
        "Exclude races where favourite is Trap 1 or 2 and race distance is below 300m",
        lambda fav, _second, race: fav.trap in (1, 2) and race.distance_m < 300,
    ),
    AnalysisFilter(
        "exclude_fav_second_traps_1_and_2",
        "Exclude races where favourite and second favourite are both Trap 1 and Trap 2",
        lambda fav, second, _race: {fav.trap, second.trap} == {1, 2},
    ),
    AnalysisFilter(
        "exclude_5_or_fewer_runners",
        "Exclude races with 5 or fewer runners",
        lambda _fav, _second, race: len(race.runners) <= 5,
    ),
]


SUMMARY_COLUMNS = [
    "row_type",
    "filter_key",
    "filter_label",
    "total_races_tested",
    "bets_placed",
    "races_skipped",
    "favourite_win_percentage",
    "final_profit_loss",
    "maximum_drawdown",
    "highest_recovery_balance",
    "number_of_busts",
    "average_liability",
    "worst_losing_run",
]

RACE_COLUMNS = [
    "race_num",
    "venue",
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
    "bet_placed",
    "skip_reason",
    "stake",
    "liability",
    "lay_profit_loss",
    "recovery_balance_before",
    "recovery_balance_after",
    "bank_balance_after",
]

DIAGNOSTIC_COLUMNS = [
    "sample_size",
    "batch_size",
    "unique_final_profit_loss_count",
    "mean_final_profit_loss",
    "stdev_final_profit_loss",
    "min_final_profit_loss",
    "max_final_profit_loss",
    "deterministic_warning",
]

CSV_COLUMNS = SUMMARY_COLUMNS + RACE_COLUMNS + DIAGNOSTIC_COLUMNS


def generated_race_snapshots(total_races: int, seed: Optional[int] = None) -> List[RaceSnapshot]:
    state = random.getstate() if seed is not None else None
    if seed is not None:
        random.seed(seed)
    try:
        snapshots = []
        for race_num in range(1, total_races + 1):
            runners, venue, category = generate_race(race_num)
            snapshots.append(
                RaceSnapshot(
                    race_num=race_num,
                    venue=venue,
                    runners=runners,
                    winning_trap=pick_winner(runners, category),
                    distance_m=category.distance_m,
                )
            )
        return snapshots
    finally:
        if state is not None:
            random.setstate(state)


def session_race_snapshots(session: Session) -> List[RaceSnapshot]:
    snapshots = []
    for race in session.races:
        if not race.winning_trap:
            continue
        distance_m = race.category.distance_m if race.category else 0
        snapshots.append(
            RaceSnapshot(
                race_num=race.race_num,
                venue=race.venue,
                runners=race.runners,
                winning_trap=race.winning_trap,
                distance_m=distance_m,
            )
        )
    return snapshots


def _net_lay_win(stake: float, commission_rate: float) -> float:
    return round(stake * (1 - commission_rate), 4)


def _remaining_stop_loss_budget(bank_pnl: float, config: SessionConfig) -> float:
    if config.stop_loss <= 0:
        return 0.0
    return round(max(config.stop_loss + bank_pnl, 0.0), 4)


def _floor_money(value: float) -> float:
    return int(max(value, 0.0) * 10000) / 10000


def _blank_row(row_type: str) -> Dict[str, object]:
    row = {col: "" for col in CSV_COLUMNS}
    row["row_type"] = row_type
    return row


def _simulate_filter(
    snapshots: Iterable[RaceSnapshot],
    config: SessionConfig,
    analysis_filter: AnalysisFilter,
    *,
    include_races: bool,
) -> Tuple[Dict[str, object], List[Dict[str, object]]]:
    chain = RecoveryChain(pending_stake=config.stake)
    total_pnl = 0.0
    peak_pnl = 0.0
    max_drawdown = 0.0
    highest_recovery = 0.0
    liabilities: List[float] = []
    race_rows: List[Dict[str, object]] = []
    bets_placed = 0
    skipped = 0
    favourite_wins = 0
    favourite_wins_when_bet = 0
    busts = 0
    current_losing_run = 0
    worst_losing_run = 0

    snapshots = list(snapshots)
    for race in snapshots:
        fav, second = _fav_pair(race)
        fav_won = fav.trap == race.winning_trap
        if fav_won:
            favourite_wins += 1

        recovery_before = round(recovery_total(chain), 4)
        skip_reason = ""
        bet_placed = False
        stake = 0.0
        liability = 0.0
        lay_pnl = 0.0

        if analysis_filter.should_skip(fav, second, race):
            skipped += 1
            skip_reason = analysis_filter.label
            current_losing_run = 0
        elif chain.busted:
            skipped += 1
            skip_reason = "recovery chain busted"
            current_losing_run = 0
        else:
            loss_budget = _remaining_stop_loss_budget(total_pnl, config)
            if loss_budget <= 0:
                skipped += 1
                skip_reason = "stop-loss budget exhausted"
            else:
                bet_plan = plan_recovery_bet(
                    chain,
                    fav.odds,
                    config,
                    stop_loss_budget=loss_budget,
                )
                stake = _floor_money(bet_plan.stake)
                liability = round(stake * (fav.odds - 1), 4)
                if stake <= 0 or liability <= 0:
                    skipped += 1
                    skip_reason = "liability below usable stake"
                else:
                    bet_placed = True
                    bets_placed += 1
                    liabilities.append(liability)
                    if fav_won:
                        favourite_wins_when_bet += 1
                        lay_pnl = -liability
                        current_losing_run += 1
                        worst_losing_run = max(worst_losing_run, current_losing_run)
                    else:
                        commission_rate = (
                            race.commission_rate
                            if race.commission_rate is not None
                            else config.commission_rate
                        )
                        lay_pnl = _net_lay_win(stake, commission_rate)
                        current_losing_run = 0
                    bet = LayBet(
                        favourite_rank=1,
                        dog_trap=fav.trap,
                        dog_name=fav.name,
                        odds=fav.odds,
                        stake=stake,
                        liability=liability,
                        recovery_level=chain.level,
                        result="loss" if fav_won else "win",
                        pnl=lay_pnl,
                    )
                    before_busted = chain.busted
                    apply_settled_bet_to_chain(
                        chain,
                        bet,
                        config,
                        lay_pnl,
                        session_profit=round(total_pnl + lay_pnl, 4),
                    )
                    if chain.busted and not before_busted:
                        busts += 1
                    total_pnl = round(total_pnl + lay_pnl, 4)
                    peak_pnl = max(peak_pnl, total_pnl)
                    max_drawdown = max(max_drawdown, round(peak_pnl - total_pnl, 4))

        recovery_after = round(recovery_total(chain), 4)
        highest_recovery = max(highest_recovery, recovery_before, recovery_after)

        if include_races:
            row = _blank_row("race")
            row.update(
                {
                    "filter_key": analysis_filter.key,
                    "filter_label": analysis_filter.label,
                    "race_num": race.race_num,
                    "venue": race.venue,
                    "favourite_odds": fav.odds,
                    "second_favourite_odds": second.odds,
                    "favourite_implied_probability": _prob(fav),
                    "second_favourite_implied_probability": _prob(second),
                    "implied_probability_gap": _prob_gap(fav, second),
                    "favourite_trap": fav.trap,
                    "second_favourite_trap": second.trap,
                    "race_distance": race.distance_m,
                    "number_of_runners": len(race.runners),
                    "favourite_won": fav_won,
                    "bet_placed": bet_placed,
                    "skip_reason": skip_reason,
                    "stake": round(stake, 4),
                    "liability": round(liability, 4),
                    "lay_profit_loss": round(lay_pnl, 4),
                    "recovery_balance_before": recovery_before,
                    "recovery_balance_after": recovery_after,
                    "bank_balance_after": round(config.starting_bank + total_pnl, 4),
                }
            )
            race_rows.append(row)

    summary = _blank_row("summary")
    summary.update(
        {
            "filter_key": analysis_filter.key,
            "filter_label": analysis_filter.label,
            "total_races_tested": len(snapshots),
            "bets_placed": bets_placed,
            "races_skipped": skipped,
            "favourite_win_percentage": round((favourite_wins_when_bet / max(bets_placed, 1)) * 100, 2),
            "final_profit_loss": round(total_pnl, 4),
            "maximum_drawdown": round(max_drawdown, 4),
            "highest_recovery_balance": round(highest_recovery, 4),
            "number_of_busts": busts,
            "average_liability": round(sum(liabilities) / max(len(liabilities), 1), 4),
            "worst_losing_run": worst_losing_run,
        }
    )
    return summary, race_rows


def _repeat_50_diagnostic(config: SessionConfig, sample_size: int, seed: Optional[int]) -> Dict[str, object]:
    final_pnls = []
    for idx in range(sample_size):
        batch_seed = None if seed is None else seed + idx + 1
        snapshots = generated_race_snapshots(50, batch_seed)
        summary, _rows = _simulate_filter(snapshots, config, FILTERS[0], include_races=False)
        final_pnls.append(float(summary["final_profit_loss"]))
    unique_count = len({round(pnl, 4) for pnl in final_pnls})
    row = _blank_row("repeat_50_diagnostic")
    row.update(
        {
            "sample_size": sample_size,
            "batch_size": 50,
            "unique_final_profit_loss_count": unique_count,
            "mean_final_profit_loss": round(statistics.mean(final_pnls), 4),
            "stdev_final_profit_loss": round(statistics.pstdev(final_pnls), 4),
            "min_final_profit_loss": round(min(final_pnls), 4),
            "max_final_profit_loss": round(max(final_pnls), 4),
            "deterministic_warning": unique_count <= max(2, sample_size // 10),
        }
    )
    return row


def build_analysis_csv(
    snapshots: List[RaceSnapshot],
    config: SessionConfig,
    *,
    include_races: bool = True,
    repeat_50_samples: int = 20,
    seed: Optional[int] = None,
) -> str:
    rows: List[Dict[str, object]] = []
    for analysis_filter in FILTERS:
        summary, race_rows = _simulate_filter(
            snapshots,
            config,
            analysis_filter,
            include_races=include_races,
        )
        rows.append(summary)
        rows.extend(race_rows)
    if repeat_50_samples > 0:
        rows.append(_repeat_50_diagnostic(config, repeat_50_samples, seed))

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
