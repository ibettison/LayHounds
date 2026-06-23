from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from build_season_layhounds_report import (
    BASE_STAKE,
    COMMISSION,
    NET_FACTOR,
    RUNAWAY_LIABILITY_LIMIT,
    TARGET_PROFIT,
    Race,
    money,
    proposed_rules,
    runner_by_rank,
)
from build_temporal_balanced_report import load_races


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", default="test_reports/layhounds_cache/races_2025_2026.jsonl")
    parser.add_argument("--output-dir", default="test_reports/layhounds_weekly_pnl_elastic75")
    return parser.parse_args()


def race_datetime(race: Race) -> datetime:
    return datetime.fromisoformat(race.race_time.replace("Z", "+00:00")).replace(tzinfo=None)


def week_bounds(year: int, week: int) -> tuple[date, date]:
    start = date.fromisocalendar(year, week, 1)
    return start, start + timedelta(days=6)


def iso_week_key(race: Race) -> tuple[int, int]:
    iso = race_datetime(race).isocalendar()
    return int(iso.year), int(iso.week)


def elastic_fraction(balance: float) -> float:
    if balance < 5:
        return 1.0
    if balance < 15:
        return 0.75
    if balance < 30:
        return 0.50
    return 0.25


def stake_for(balance: float, model: str) -> float:
    if balance <= 0:
        return BASE_STAKE
    fraction = 1.0 if model == "current" else elastic_fraction(balance)
    return money((balance * fraction + TARGET_PROFIT) / NET_FACTOR)


def cap_stake(stake: float, odds: float, liability_cap: float) -> float:
    if liability_cap <= 0 or odds <= 1.0:
        return stake
    liability = money(stake * (odds - 1.0))
    if liability <= liability_cap:
        return stake
    return money(liability_cap / (odds - 1.0))


@dataclass
class ChainState:
    balance: float = 0.0
    consecutive_losses: int = 0


@dataclass
class WeekMetrics:
    year: int
    iso_week: int
    week_start_date: str
    week_end_date: str
    opportunities: int = 0
    favourite_opportunities: int = 0
    second_favourite_opportunities: int = 0
    total_profit: float = 0.0
    total_loss: float = 0.0
    total_liability: float = 0.0
    net_pl: float = 0.0
    equity: float = 0.0
    peak: float = 0.0
    worst_drawdown: float = 0.0
    max_liability: float = 0.0
    busts: int = 0
    favourite_busts: int = 0
    second_favourite_busts: int = 0
    closing_recovery_debt: float = 0.0
    unresolved_chains: int = 0

    def record_result(self, pnl: float, liability: float) -> None:
        self.net_pl = money(self.net_pl + pnl)
        if pnl >= 0:
            self.total_profit = money(self.total_profit + pnl)
        else:
            self.total_loss = money(self.total_loss + abs(pnl))
        self.total_liability = money(self.total_liability + liability)
        self.max_liability = max(self.max_liability, liability)
        self.equity = money(self.equity + pnl)
        self.peak = max(self.peak, self.equity)
        self.worst_drawdown = max(self.worst_drawdown, money(self.peak - self.equity))

    def to_row(self) -> dict:
        return {
            "year": self.year,
            "iso_week": self.iso_week,
            "week_start_date": self.week_start_date,
            "week_end_date": self.week_end_date,
            "opportunities": self.opportunities,
            "favourite_opportunities": self.favourite_opportunities,
            "second_favourite_opportunities": self.second_favourite_opportunities,
            "net_pl": money(self.net_pl),
            "roi_pct": round(self.net_pl / self.total_liability * 100.0, 2) if self.total_liability else 0.0,
            "busts": self.busts,
            "favourite_busts": self.favourite_busts,
            "second_favourite_busts": self.second_favourite_busts,
            "worst_drawdown": money(self.worst_drawdown),
            "max_liability": money(self.max_liability),
            "closing_recovery_debt": money(self.closing_recovery_debt),
            "unresolved_chains": self.unresolved_chains,
            "any_chain_unresolved": "yes" if self.unresolved_chains else "no",
            "total_liability": money(self.total_liability),
            "total_profit": money(self.total_profit),
            "total_loss": money(self.total_loss),
        }


def blank_week(year: int, week: int) -> WeekMetrics:
    start, end = week_bounds(year, week)
    return WeekMetrics(
        year=year,
        iso_week=week,
        week_start_date=start.isoformat(),
        week_end_date=end.isoformat(),
    )


def finalise_week(
    weeks: dict[tuple[int, int], WeekMetrics],
    key: tuple[int, int],
    states: dict[int, ChainState],
) -> None:
    if key not in weeks:
        return
    debt = money(sum(state.balance for state in states.values()))
    weeks[key].closing_recovery_debt = debt
    weeks[key].unresolved_chains = sum(1 for state in states.values() if state.balance > 0)


def simulate_weekly(races: list[Race], *, model: str, liability_cap: float = 0.0) -> list[dict]:
    states = {1: ChainState(), 2: ChainState()}
    weeks: dict[tuple[int, int], WeekMetrics] = {}
    current_week: tuple[int, int] | None = None

    for race in races:
        key = iso_week_key(race)
        if current_week is not None and key != current_week:
            finalise_week(weeks, current_week, states)
        current_week = key
        if key not in weeks:
            weeks[key] = blank_week(*key)

        for rank in (1, 2):
            runner = runner_by_rank(race, rank)
            if runner is None or not proposed_rules(race, runner, rank):
                continue

            state = states[rank]
            stake = cap_stake(stake_for(state.balance, model), runner.odds, liability_cap)
            liability = money(stake * (runner.odds - 1.0))
            if (
                not math.isfinite(stake)
                or not math.isfinite(liability)
                or stake > RUNAWAY_LIABILITY_LIMIT
                or liability > RUNAWAY_LIABILITY_LIMIT
            ):
                state.balance = 0.0
                state.consecutive_losses = 0
                continue

            week = weeks[key]
            week.opportunities += 1
            if rank == 1:
                week.favourite_opportunities += 1
            else:
                week.second_favourite_opportunities += 1

            selected_won = runner.trap == race.winning_trap
            if selected_won:
                state.balance = money(state.balance + liability)
                state.consecutive_losses += 1
                week.record_result(-liability, liability)
                if state.consecutive_losses >= 5:
                    week.busts += 1
                    if rank == 1:
                        week.favourite_busts += 1
                    else:
                        week.second_favourite_busts += 1
                    state.balance = 0.0
                    state.consecutive_losses = 0
            else:
                profit = money(stake * NET_FACTOR)
                week.record_result(profit, liability)
                if state.balance > 0:
                    state.balance = money(max(state.balance - profit, 0.0))
                    state.consecutive_losses = 0
                    if state.balance <= 0:
                        state.balance = 0.0
                else:
                    state.consecutive_losses = 0

    if current_week is not None:
        finalise_week(weeks, current_week, states)

    return [weeks[key].to_row() for key in sorted(weeks)]


def write_csv(path: Path, rows: list[dict]) -> None:
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def compare_rows(current_rows: list[dict], elastic_rows: list[dict]) -> list[dict]:
    by_key = {(row["year"], row["iso_week"]): row for row in current_rows}
    rows = []
    for elastic in elastic_rows:
        key = (elastic["year"], elastic["iso_week"])
        current = by_key[key]
        rows.append(
            {
                "year": elastic["year"],
                "iso_week": elastic["iso_week"],
                "week_start_date": elastic["week_start_date"],
                "week_end_date": elastic["week_end_date"],
                "current_opportunities": current["opportunities"],
                "elastic_opportunities": elastic["opportunities"],
                "current_net_pl": current["net_pl"],
                "elastic_net_pl": elastic["net_pl"],
                "net_pl_delta_elastic_minus_current": money(elastic["net_pl"] - current["net_pl"]),
                "current_roi_pct": current["roi_pct"],
                "elastic_roi_pct": elastic["roi_pct"],
                "roi_delta_pct_points": round(elastic["roi_pct"] - current["roi_pct"], 2),
                "current_busts": current["busts"],
                "elastic_busts": elastic["busts"],
                "bust_delta": elastic["busts"] - current["busts"],
                "current_worst_drawdown": current["worst_drawdown"],
                "elastic_worst_drawdown": elastic["worst_drawdown"],
                "worst_drawdown_delta": money(elastic["worst_drawdown"] - current["worst_drawdown"]),
                "current_max_liability": current["max_liability"],
                "elastic_max_liability": elastic["max_liability"],
                "max_liability_delta": money(elastic["max_liability"] - current["max_liability"]),
                "current_closing_recovery_debt": current["closing_recovery_debt"],
                "elastic_closing_recovery_debt": elastic["closing_recovery_debt"],
                "current_any_chain_unresolved": current["any_chain_unresolved"],
                "elastic_any_chain_unresolved": elastic["any_chain_unresolved"],
            }
        )
    return rows


def money_fmt(value: float) -> str:
    if value < 0:
        return f"-£{abs(value):,.2f}"
    return f"£{value:,.2f}"


def week_label(row: dict) -> str:
    return f"{row['year']}-W{int(row['iso_week']):02d} ({row['week_start_date']} to {row['week_end_date']})"


def seasonal_notes(rows: list[dict]) -> list[str]:
    bad = [row for row in rows if row["elastic_net_pl"] < 0]
    by_month: dict[str, dict] = defaultdict(lambda: {"weeks": 0, "net_pl": 0.0, "busts": 0})
    for row in bad:
        month = row["week_start_date"][5:7]
        by_month[month]["weeks"] += 1
        by_month[month]["net_pl"] = money(by_month[month]["net_pl"] + row["elastic_net_pl"])
        by_month[month]["busts"] += row["elastic_busts"]
    ranked = sorted(by_month.items(), key=lambda item: (item[1]["net_pl"], -item[1]["weeks"]))
    return [
        f"Month {month}: {data['weeks']} losing weeks, Elastic net P/L {money_fmt(data['net_pl'])}, busts {data['busts']}"
        for month, data in ranked[:5]
    ]


def build_markdown(elastic_rows: list[dict], comparison_rows: list[dict], output_dir: Path) -> str:
    best = max(elastic_rows, key=lambda row: row["net_pl"])
    worst = min(elastic_rows, key=lambda row: row["net_pl"])
    volatile = max(elastic_rows, key=lambda row: row["worst_drawdown"])
    improved = [row for row in comparison_rows if row["net_pl_delta_elastic_minus_current"] > 0]
    worsened = [row for row in comparison_rows if row["net_pl_delta_elastic_minus_current"] < 0]
    total = {
        "opportunities": sum(row["opportunities"] for row in elastic_rows),
        "fav": sum(row["favourite_opportunities"] for row in elastic_rows),
        "second": sum(row["second_favourite_opportunities"] for row in elastic_rows),
        "net_pl": money(sum(row["net_pl"] for row in elastic_rows)),
        "liability": money(sum(row["total_liability"] for row in elastic_rows)),
        "busts": sum(row["busts"] for row in elastic_rows),
        "fav_busts": sum(row["favourite_busts"] for row in elastic_rows),
        "second_busts": sum(row["second_favourite_busts"] for row in elastic_rows),
        "max_liability": max(row["max_liability"] for row in elastic_rows),
        "worst_drawdown": max(row["worst_drawdown"] for row in elastic_rows),
    }
    roi = round(total["net_pl"] / total["liability"] * 100.0, 2) if total["liability"] else 0.0
    top_improvements = sorted(improved, key=lambda row: row["net_pl_delta_elastic_minus_current"], reverse=True)[:10]
    top_worsened = sorted(worsened, key=lambda row: row["net_pl_delta_elastic_minus_current"])[:10]

    lines = [
        "# Weekly P&L - Elastic £75 vs Current",
        "",
        "Rules: favourite gap <=10%, second favourite gap 5%-30%, sprint Trap 1/2 exclusion ON, base stake £0.05, 5% commission.",
        "Elastic model: debt-band recovery with £75 liability cap.",
        "",
        "## Elastic £75 Totals",
        "",
        f"- Weeks covered: {len(elastic_rows)}",
        f"- Opportunities: {total['opportunities']:,} ({total['fav']:,} favourite, {total['second']:,} second favourite)",
        f"- Net P/L: {money_fmt(total['net_pl'])}",
        f"- ROI: {roi:.2f}%",
        f"- Busts: {total['busts']} ({total['fav_busts']} favourite, {total['second_busts']} second favourite)",
        f"- Worst weekly drawdown: {money_fmt(total['worst_drawdown'])}",
        f"- Max liability: {money_fmt(total['max_liability'])}",
        "",
        "## Key Weeks",
        "",
        f"- Best week: {week_label(best)} - {money_fmt(best['net_pl'])}, ROI {best['roi_pct']:.2f}%, busts {best['busts']}",
        f"- Worst week: {week_label(worst)} - {money_fmt(worst['net_pl'])}, ROI {worst['roi_pct']:.2f}%, busts {worst['busts']}",
        f"- Most volatile week: {week_label(volatile)} - worst drawdown {money_fmt(volatile['worst_drawdown'])}, net P/L {money_fmt(volatile['net_pl'])}",
        "",
        "## Current vs Elastic £75",
        "",
        f"- Elastic improved P/L in {len(improved)} weeks.",
        f"- Elastic worsened P/L in {len(worsened)} weeks.",
        f"- Unchanged weeks: {len(comparison_rows) - len(improved) - len(worsened)}.",
        "",
        "### Top Elastic Improvements",
        "",
        "| Week | Current P/L | Elastic P/L | Delta | Current Max Liability | Elastic Max Liability |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in top_improvements:
        lines.append(
            f"| {week_label(row)} | {money_fmt(row['current_net_pl'])} | {money_fmt(row['elastic_net_pl'])} | "
            f"{money_fmt(row['net_pl_delta_elastic_minus_current'])} | {money_fmt(row['current_max_liability'])} | {money_fmt(row['elastic_max_liability'])} |"
        )
    lines.extend(
        [
            "",
            "### Top Elastic Worsening Weeks",
            "",
            "| Week | Current P/L | Elastic P/L | Delta | Current Closing Debt | Elastic Closing Debt |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in top_worsened:
        lines.append(
            f"| {week_label(row)} | {money_fmt(row['current_net_pl'])} | {money_fmt(row['elastic_net_pl'])} | "
            f"{money_fmt(row['net_pl_delta_elastic_minus_current'])} | {money_fmt(row['current_closing_recovery_debt'])} | {money_fmt(row['elastic_closing_recovery_debt'])} |"
        )
    lines.extend(
        [
            "",
            "## Repeated Bad Seasonal Periods",
            "",
        ]
    )
    notes = seasonal_notes(comparison_rows)
    lines.extend([f"- {note}" for note in notes] if notes else ["- No repeated losing month clusters found."])
    lines.extend(
        [
            "",
            "## Output Files",
            "",
            f"- `{(output_dir / 'weekly_pnl_elastic75.csv').as_posix()}`",
            f"- `{(output_dir / 'weekly_pnl_current_vs_elastic75.csv').as_posix()}`",
            f"- `{(output_dir / 'weekly_pnl_summary.md').as_posix()}`",
            "",
            "Note: weekly recovery state is continuous across week boundaries. Weekly P/L is grouped by race off-time ISO week; closing recovery debt is the outstanding chain debt after the final qualifying opportunity in that week.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    races = load_races(Path(args.cache))

    current_rows = simulate_weekly(races, model="current", liability_cap=0.0)
    elastic_rows = simulate_weekly(races, model="elastic", liability_cap=75.0)
    comparison_rows = compare_rows(current_rows, elastic_rows)

    write_csv(output_dir / "weekly_pnl_elastic75.csv", elastic_rows)
    write_csv(output_dir / "weekly_pnl_current_vs_elastic75.csv", comparison_rows)
    (output_dir / "weekly_pnl_summary.md").write_text(
        build_markdown(elastic_rows, comparison_rows, output_dir),
        encoding="utf-8",
    )
    (output_dir / "summary.json").write_text(
        json.dumps(
            {
                "source_cache": args.cache,
                "output_dir": str(output_dir),
                "rules": {
                    "favourite_gap_max": 0.10,
                    "second_favourite_gap_min": 0.05,
                    "second_favourite_gap_max": 0.30,
                    "sprint_trap_1_2_exclusion": True,
                    "recovery_mode": "elastic",
                    "liability_cap": 75.0,
                    "base_stake": BASE_STAKE,
                    "commission": COMMISSION,
                },
                "weeks": len(elastic_rows),
                "elastic_totals": {
                    "opportunities": sum(row["opportunities"] for row in elastic_rows),
                    "net_pl": money(sum(row["net_pl"] for row in elastic_rows)),
                    "busts": sum(row["busts"] for row in elastic_rows),
                    "max_liability": max(row["max_liability"] for row in elastic_rows),
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote weekly report bundle to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
