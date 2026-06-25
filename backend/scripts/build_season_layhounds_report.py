from __future__ import annotations

import argparse
import bz2
import csv
import json
import math
import re
import tarfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Iterator
from zoneinfo import ZoneInfo


COUNTRIES = {"GB", "IE"}
BASE_STAKE = 0.05
COMMISSION = 0.05
NET_FACTOR = 1.0 - COMMISSION
TARGET_PROFIT = round(BASE_STAKE * NET_FACTOR, 4)
RUNAWAY_LIABILITY_LIMIT = 1_000_000.0

TIME_RE = re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b")
TRAP_RE = re.compile(r"^\s*(?:trap|t|no\.?)?\s*([1-6])(?:\D|$)", re.IGNORECASE)
DIST_RE = re.compile(r"(?<!\d)(\d{3,4})\s*m\b", re.IGNORECASE)
GRADE_RE = re.compile(r"\b(A1[0-2]|D1[0-2]|S1[0-2]|A[1-9]|D[1-9]|S[1-9]|OR|HP|HT|H[1-3])\b")

GAP_BUCKETS = [
    ("0-5%", 0.00, 0.05),
    ("5-10%", 0.05, 0.10),
    ("10-15%", 0.10, 0.15),
    ("15-20%", 0.15, 0.20),
    ("20-30%", 0.20, 0.30),
    ("30-40%", 0.30, 0.40),
    ("40%+", 0.40, None),
]


@dataclass(frozen=True)
class Runner:
    runner_id: int | str
    trap: int
    name: str
    odds: float
    favourite_rank: int


@dataclass(frozen=True)
class Race:
    market_id: str
    race_time: str
    date: str
    venue: str
    country: str
    market_name: str
    event_name: str
    runners: tuple[Runner, ...]
    winning_trap: int
    favourite_odds: float
    second_favourite_odds: float
    odds_gap: float
    gap_bucket: str
    grade: str
    distance_m: int
    distance_band: str


@dataclass(frozen=True)
class Strategy:
    key: str
    label: str
    predicate: Callable[[Race, Runner, int], bool]


def money(value: float) -> float:
    return round(float(value) + 1e-12, 4)


def next_recovery_stake(accumulated_loss: float) -> float:
    return money((accumulated_loss + TARGET_PROFIT) / NET_FACTOR)


def pct(numerator: float, denominator: float) -> float:
    return round(numerator / denominator * 100.0, 2) if denominator else 0.0


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * (p / 100.0)
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return ordered[int(k)]
    return ordered[lo] * (hi - k) + ordered[hi] * (k - lo)


def iter_json_lines(tar: tarfile.TarFile, member: tarfile.TarInfo) -> Iterator[dict]:
    handle = tar.extractfile(member)
    if handle is None:
        return
    try:
        text = bz2.decompress(handle.read()).decode("utf-8", errors="replace")
    except OSError:
        return
    for line in text.splitlines():
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def latest_definition(objects: Iterable[dict]) -> dict | None:
    latest = None
    for obj in objects:
        for market_change in obj.get("mc") or []:
            definition = market_change.get("marketDefinition")
            if definition:
                latest = dict(definition)
                if market_change.get("id"):
                    latest["_marketId"] = market_change.get("id")
                if market_change.get("marketStartTime") and not latest.get("marketStartTime"):
                    latest["marketStartTime"] = market_change.get("marketStartTime")
    return latest


def parse_start_time(definition: dict) -> datetime | None:
    raw = definition.get("marketTime") or definition.get("marketStartTime") or definition.get("openDate")
    if raw:
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                tz_name = definition.get("timezone") or "Europe/London"
                try:
                    return parsed.astimezone(ZoneInfo(tz_name)).replace(tzinfo=None)
                except Exception:
                    return parsed.replace(tzinfo=None)
            return parsed
        except Exception:
            return None

    blob = " ".join(filter(None, [definition.get("name") or "", definition.get("eventName") or ""]))
    match = TIME_RE.search(blob)
    if not match:
        return None
    return datetime(1970, 1, 1, int(match.group(1)), int(match.group(2)))


def trap_from_runner_name(name: str) -> int:
    match = TRAP_RE.search(name or "")
    return int(match.group(1)) if match else 0


def fill_missing_traps(priced: list[dict]) -> None:
    used = {runner["trap"] for runner in priced if runner.get("trap")}
    available = iter(trap for trap in range(1, 7) if trap not in used)
    for runner in priced:
        if not runner.get("trap"):
            runner["trap"] = next(available, int(runner.get("sort_priority") or 0))


def distance_band(distance_m: int) -> str:
    if distance_m <= 320:
        return "sprint"
    if distance_m <= 499:
        return "standard"
    if distance_m <= 619:
        return "stayer"
    return "marathon"


def detect_grade_distance(market_name: str, event_name: str) -> tuple[str, int, str]:
    blob = " ".join(filter(None, [market_name or "", event_name or ""]))
    distance_m = 480
    if match := DIST_RE.search(blob):
        try:
            distance_m = int(match.group(1))
        except ValueError:
            distance_m = 480

    grade = "A4"
    if match := GRADE_RE.search(blob.upper()):
        grade = match.group(1)
        if grade in {"HP", "HT"}:
            grade = "H2"
    return grade, distance_m, distance_band(distance_m)


def gap_bucket(gap: float) -> str:
    for label, lo, hi in GAP_BUCKETS:
        if gap >= lo and (hi is None or gap < hi):
            return label
    return "0-5%"


def race_from_definition(member_name: str, definition: dict) -> Race | None:
    if definition.get("marketType") != "WIN" or definition.get("status") != "CLOSED":
        return None
    country = (definition.get("countryCode") or "").upper()
    if country not in COUNTRIES:
        return None

    settled = []
    for runner in definition.get("runners") or []:
        try:
            bsp = float(runner.get("bsp") or 0)
        except (TypeError, ValueError):
            continue
        if runner.get("status") in {"WINNER", "LOSER"} and math.isfinite(bsp) and bsp > 1.01:
            settled.append(runner)
    if len(settled) < 2:
        return None
    winner = next((runner for runner in settled if runner.get("status") == "WINNER"), None)
    if not winner:
        return None

    priced = []
    for runner in settled:
        name = runner.get("name") or str(runner.get("id"))
        priced.append(
            {
                "id": runner.get("id"),
                "trap": trap_from_runner_name(name) or int(runner.get("sortPriority") or 0),
                "sort_priority": int(runner.get("sortPriority") or 0),
                "name": name,
                "odds": round(float(runner.get("bsp")), 2),
            }
        )
    fill_missing_traps(priced)
    sorted_by_bsp = sorted(priced, key=lambda runner: (runner["odds"], runner["trap"]))
    rank_by_id = {runner["id"]: idx + 1 for idx, runner in enumerate(sorted_by_bsp)}
    runners = tuple(
        Runner(
            runner_id=runner["id"],
            trap=int(runner["trap"]),
            name=runner["name"],
            odds=runner["odds"],
            favourite_rank=rank_by_id[runner["id"]],
        )
        for runner in priced
    )

    start = parse_start_time(definition)
    if start is None:
        return None
    market_name = definition.get("name") or ""
    event_name = definition.get("eventName") or ""
    venue = definition.get("venue") or event_name or Path(member_name).stem
    favourite_odds = float(sorted_by_bsp[0]["odds"])
    second_favourite_odds = float(sorted_by_bsp[1]["odds"])
    gap = (second_favourite_odds - favourite_odds) / favourite_odds if favourite_odds > 0 else 0.0
    grade, distance_m, band = detect_grade_distance(market_name, event_name)
    race_time = start.isoformat()

    return Race(
        market_id=str(definition.get("_marketId") or Path(member_name).stem),
        race_time=race_time,
        date=race_time[:10],
        venue=f"{venue} ({country})" if country else venue,
        country=country,
        market_name=market_name,
        event_name=event_name,
        runners=runners,
        winning_trap=trap_from_runner_name(winner.get("name") or "") or int(winner.get("sortPriority") or 0),
        favourite_odds=favourite_odds,
        second_favourite_odds=second_favourite_odds,
        odds_gap=gap,
        gap_bucket=gap_bucket(gap),
        grade=grade,
        distance_m=distance_m,
        distance_band=band,
    )


def load_races(archive: Path, limit: int = 0) -> tuple[list[Race], dict]:
    races: list[Race] = []
    stats = Counter()
    with tarfile.open(archive, "r") as tar:
        for member in tar:
            stats["archive_members"] += 1
            filename = Path(member.name).name
            if not member.isfile() or not filename.startswith("1.") or not filename.endswith(".bz2"):
                continue
            stats["market_files"] += 1
            definition = latest_definition(iter_json_lines(tar, member))
            if not definition:
                stats["missing_definition"] += 1
                continue
            if definition.get("marketType") == "WIN":
                stats["win_markets"] += 1
            if (definition.get("countryCode") or "").upper() not in COUNTRIES:
                stats["non_uk_ie_markets"] += 1
            race = race_from_definition(member.name, definition)
            if race is None:
                stats["excluded_markets"] += 1
                continue
            races.append(race)
            stats["included_uk_ie_races"] += 1
            if limit and len(races) >= limit:
                break
    races.sort(key=lambda race: (race.race_time, race.market_id))
    return races, dict(stats)


def runner_by_rank(race: Race, rank: int) -> Runner | None:
    return next((runner for runner in race.runners if runner.favourite_rank == rank), None)


def sprint_trap_rule(race: Race, runner: Runner, _: int) -> bool:
    return not (race.distance_band == "sprint" and runner.trap in {1, 2})


def no_filters(_: Race, __: Runner, ___: int) -> bool:
    return True


def current_rules(race: Race, runner: Runner, rank: int) -> bool:
    return sprint_trap_rule(race, runner, rank) and (rank != 1 or race.odds_gap <= 0.15)


def proposed_rules(race: Race, runner: Runner, rank: int) -> bool:
    if not sprint_trap_rule(race, runner, rank):
        return False
    if rank == 1:
        return race.odds_gap <= 0.10
    return 0.05 <= race.odds_gap <= 0.30


def make_strategy(
    key: str,
    label: str,
    *,
    sprint: bool = False,
    fav_max_gap: float | None = None,
    second_min_gap: float | None = None,
    second_max_gap: float | None = None,
) -> Strategy:
    def predicate(race: Race, runner: Runner, rank: int) -> bool:
        if sprint and not sprint_trap_rule(race, runner, rank):
            return False
        if rank == 1 and fav_max_gap is not None and race.odds_gap > fav_max_gap:
            return False
        if rank == 2:
            if second_min_gap is not None and race.odds_gap < second_min_gap:
                return False
            if second_max_gap is not None and race.odds_gap > second_max_gap:
                return False
        return True

    return Strategy(key, label, predicate)


def simulate(races: list[Race], strategy: Strategy, *, ranks: tuple[int, ...] = (1, 2)) -> dict:
    states = {
        rank: {"losses": 0, "accum": 0.0, "pending": BASE_STAKE, "streak": [], "disabled": False}
        for rank in ranks
    }
    metrics = {
        "bets": 0,
        "fav_opportunities": 0,
        "second_opportunities": 0,
        "fav_selection_wins": 0,
        "second_selection_wins": 0,
        "winning_lays": 0,
        "losing_lays": 0,
        "total_profit": 0.0,
        "total_loss": 0.0,
        "total_stake": 0.0,
        "total_liability": 0.0,
        "max_liability": 0.0,
        "fav_busts": 0,
        "second_busts": 0,
        "equity": 0.0,
        "peak": 0.0,
        "worst_drawdown": 0.0,
        "runaway_chains": 0,
    }
    bust_drawdowns: list[float] = []
    bust_events: list[dict] = []

    for race in races:
        for rank in ranks:
            runner = runner_by_rank(race, rank)
            if runner is None or not strategy.predicate(race, runner, rank):
                continue
            st = states[rank]
            if st["disabled"]:
                continue
            stake = money(st["pending"])
            liability = money(stake * (runner.odds - 1.0))
            if (
                not math.isfinite(stake)
                or not math.isfinite(liability)
                or liability > RUNAWAY_LIABILITY_LIMIT
                or stake > RUNAWAY_LIABILITY_LIMIT
            ):
                metrics["runaway_chains"] += 1
                metrics["max_liability"] = max(metrics["max_liability"], RUNAWAY_LIABILITY_LIMIT)
                bust_events.append(
                    {
                        "strategy": strategy.key,
                        "chain": "favourite" if rank == 1 else "second_favourite",
                        "date": race.date,
                        "race_time": race.race_time,
                        "venue": race.venue,
                        "grade": race.grade,
                        "distance_m": race.distance_m,
                        "distance_band": race.distance_band,
                        "favourite_odds": race.favourite_odds,
                        "second_favourite_odds": race.second_favourite_odds,
                        "gap_pct": round(race.odds_gap * 100.0, 2),
                        "drawdown": "RUNAWAY",
                        "max_liability": f">{RUNAWAY_LIABILITY_LIMIT:.0f}",
                        "duration": "",
                        "market_id": race.market_id,
                    }
                )
                st["disabled"] = True
                continue
            metrics["bets"] += 1
            if rank == 1:
                metrics["fav_opportunities"] += 1
            if rank == 2:
                metrics["second_opportunities"] += 1
            metrics["total_stake"] = money(metrics["total_stake"] + stake)
            metrics["total_liability"] = money(metrics["total_liability"] + liability)
            metrics["max_liability"] = max(metrics["max_liability"], liability)

            if runner.trap == race.winning_trap:
                metrics["losing_lays"] += 1
                if rank == 1:
                    metrics["fav_selection_wins"] += 1
                else:
                    metrics["second_selection_wins"] += 1
                metrics["total_loss"] = money(metrics["total_loss"] + liability)
                metrics["equity"] = money(metrics["equity"] - liability)
                st["losses"] += 1
                st["accum"] = money(st["accum"] + liability)
                st["streak"].append({"race": race, "runner": runner, "stake": stake, "liability": liability})
                if st["losses"] >= 5:
                    drawdown = money(sum(item["liability"] for item in st["streak"][-5:]))
                    bust_drawdowns.append(drawdown)
                    if rank == 1:
                        metrics["fav_busts"] += 1
                    else:
                        metrics["second_busts"] += 1
                    bust_events.append(
                        {
                            "strategy": strategy.key,
                            "chain": "favourite" if rank == 1 else "second_favourite",
                            "date": race.date,
                            "race_time": race.race_time,
                            "venue": race.venue,
                            "grade": race.grade,
                            "distance_m": race.distance_m,
                            "distance_band": race.distance_band,
                            "favourite_odds": race.favourite_odds,
                            "second_favourite_odds": race.second_favourite_odds,
                            "gap_pct": round(race.odds_gap * 100.0, 2),
                            "drawdown": drawdown,
                            "max_liability": max(item["liability"] for item in st["streak"][-5:]),
                            "duration": duration_label(st["streak"][-5]["race"].race_time, race.race_time),
                            "market_id": race.market_id,
                        }
                    )
                    st.update({"losses": 0, "accum": 0.0, "pending": BASE_STAKE, "streak": []})
                else:
                    st["pending"] = next_recovery_stake(st["accum"])
            else:
                metrics["winning_lays"] += 1
                profit = money(stake * NET_FACTOR)
                metrics["total_profit"] = money(metrics["total_profit"] + profit)
                metrics["equity"] = money(metrics["equity"] + profit)
                remaining = money(max(st["accum"] - profit, 0.0))
                if remaining > 0:
                    st.update({"losses": 0, "accum": remaining, "pending": next_recovery_stake(remaining), "streak": []})
                else:
                    st.update({"losses": 0, "accum": 0.0, "pending": BASE_STAKE, "streak": []})

            metrics["peak"] = max(metrics["peak"], metrics["equity"])
            metrics["worst_drawdown"] = max(metrics["worst_drawdown"], money(metrics["peak"] - metrics["equity"]))

    net_pl = money(metrics["total_profit"] - metrics["total_loss"])
    return {
        **metrics,
        "net_pl": net_pl,
        "roi_pct": pct(net_pl, metrics["total_liability"]),
        "roi_on_stake_pct": pct(net_pl, metrics["total_stake"]),
        "bust_count": metrics["fav_busts"] + metrics["second_busts"],
        "worst_bust_drawdown": money(max(bust_drawdowns) if bust_drawdowns else 0.0),
        "average_bust_drawdown": money(sum(bust_drawdowns) / len(bust_drawdowns)) if bust_drawdowns else 0.0,
        "p95_bust_drawdown": money(percentile(bust_drawdowns, 95)) if bust_drawdowns else 0.0,
        "bust_drawdowns": bust_drawdowns,
        "bust_events": bust_events,
    }


def duration_label(start: str, end: str) -> str:
    delta = datetime.fromisoformat(end) - datetime.fromisoformat(start)
    days = delta.days
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60
    if days:
        return f"{days}d {hours}h {minutes}m"
    return f"{hours}h {minutes}m"


def summary_row(name: str, result: dict, total_races: int) -> dict:
    fav_ops = result["fav_opportunities"]
    second_ops = result["second_opportunities"]
    return {
        "rule_set": name,
        "total_races": total_races,
        "favourite_opportunities": fav_ops,
        "second_favourite_opportunities": second_ops,
        "total_opportunities": fav_ops + second_ops,
        "favourite_win_rate_pct": pct(result["fav_selection_wins"], fav_ops),
        "second_favourite_win_rate_pct": pct(result["second_selection_wins"], second_ops),
        "total_profit": money(result["total_profit"]),
        "total_loss": money(result["total_loss"]),
        "net_pl": money(result["net_pl"]),
        "roi_pct": result["roi_pct"],
        "total_liability_risked": money(result["total_liability"]),
        "l5_busts": result["bust_count"],
        "favourite_busts": result["fav_busts"],
        "second_favourite_busts": result["second_busts"],
        "worst_bust_drawdown": result["worst_bust_drawdown"],
        "worst_equity_drawdown": money(result["worst_drawdown"]),
        "max_liability_reached": money(result["max_liability"]),
        "runaway_chains": result["runaway_chains"],
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys and key not in {"bust_drawdowns", "bust_events"}:
                keys.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def period_split(races: list[Race], train_ratio: float = 0.7) -> tuple[list[Race], list[Race]]:
    split_at = max(1, min(len(races) - 1, int(len(races) * train_ratio)))
    return races[:split_at], races[split_at:]


def candidate_strategies() -> list[Strategy]:
    strategies = [
        Strategy("no_filters", "No filters", no_filters),
        Strategy("current", "Current LayHounds rules", current_rules),
        Strategy("proposed", "Fav <=10% + 2nd 5-30% + sprint", proposed_rules),
    ]
    favs = [0.05, 0.10, 0.12, 0.15, 0.20]
    seconds = [(0.00, 1.0), (0.05, 0.20), (0.05, 0.30), (0.10, 0.30), (0.05, 0.40)]
    for fav in favs:
        for second_min, second_max in seconds:
            strategies.append(
                make_strategy(
                    f"grid_fav_{int(fav*100)}_second_{int(second_min*100)}_{int(second_max*100)}",
                    f"Fav <= {int(fav*100)}%, 2nd {int(second_min*100)}-{int(second_max*100)}%, sprint ON",
                    sprint=True,
                    fav_max_gap=fav,
                    second_min_gap=second_min,
                    second_max_gap=second_max,
                )
            )
    return strategies


def score_profit_to_risk(result: dict) -> float:
    return result["net_pl"] / max(result["worst_drawdown"], result["max_liability"], 1.0)


def build_markdown(output_dir: Path, summary: dict) -> str:
    baseline = summary["baseline"]
    final_modes = summary["final_modes"]
    lines = [
        "# LayHounds Full-Season Risk and Profitability Report",
        "",
        f"Source: `{summary['source_archive']}`",
        f"Included UK/IE races: {summary['total_races']:,}",
        "",
        "## Executive Summary",
        "",
        f"- Highest ROI non-runaway configuration: **{summary['highest_roi']['rule_set']}** ({summary['highest_roi']['roi_pct']}% ROI).",
        f"- Lowest risk non-runaway configuration: **{summary['lowest_risk']['rule_set']}** ({summary['lowest_risk']['l5_busts']} busts, worst drawdown £{summary['lowest_risk']['worst_equity_drawdown']}).",
        f"- Best profit-to-risk configuration: **{summary['best_profit_to_risk']['rule_set']}**.",
        f"- Favourite <=10% and Second Favourite 5%-30% validation: **{summary['proposed_assessment']}**",
        f"- Runaway threshold for reporting: per-bet liability > £{RUNAWAY_LIABILITY_LIMIT:,.0f}. Runaway rows are not treated as valid final configurations.",
        "",
        "## Baseline",
        "",
        "| Rule Set | Opps | Net P/L | ROI | Busts | Worst Bust DD | Max Liability | Runaways |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in baseline:
        lines.append(
            f"| {row['rule_set']} | {row['total_opportunities']:,} | £{row['net_pl']} | {row['roi_pct']}% | "
            f"{row['l5_busts']} | £{row['worst_bust_drawdown']} | £{row['max_liability_reached']} | {row['runaway_chains']} |"
        )
    lines.extend(["", "## Recommended Modes", "", "| Mode | Rules | Opps | Net P/L | ROI | Busts | Worst DD | Max Liability |", "|---|---|---:|---:|---:|---:|---:|---:|"])
    for row in final_modes:
        lines.append(
            f"| {row['mode']} | {row['rules']} | {row['total_opportunities']:,} | £{row['net_pl']} | "
            f"{row['roi_pct']}% | {row['l5_busts']} | £{row['worst_equity_drawdown']} | £{row['max_liability_reached']} |"
        )
    lines.extend(
        [
            "",
            "## Files",
            "",
            "- `baseline.csv`, `filter_validation.csv`, `grade_analysis.csv`, `venue_analysis.csv`",
            "- `gap_analysis.csv`, `trap_analysis.csv`, `recovery_busts.csv`, `walk_forward.csv`",
            "- `final_recommendations.csv`, `summary.json`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build full-season LayHounds risk/profitability reports.")
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("test_reports") / "layhounds_season_risk")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    races, stats = load_races(args.archive, args.limit)
    if not races:
        raise SystemExit(f"No UK/IE races found in {args.archive}")
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    baseline_strategies = [
        Strategy("no_filters", "No filters", no_filters),
        Strategy("current", "Current LayHounds rules", current_rules),
    ]
    baseline_results = [(s, simulate(races, s)) for s in baseline_strategies]
    baseline_rows = [summary_row(s.label, result, len(races)) for s, result in baseline_results]
    write_csv(output_dir / "baseline.csv", baseline_rows)

    validation_strategies = [
        make_strategy("sprint_only", "Sprint Trap Rule only", sprint=True),
        make_strategy("fav_gap_15", "Favourite <=15% gap", fav_max_gap=0.15),
        make_strategy("fav_gap_10", "Favourite <=10% gap", fav_max_gap=0.10),
        make_strategy("fav_gap_5", "Favourite <=5% gap", fav_max_gap=0.05),
        make_strategy("second_5_30", "Second Favourite 5%-30%", second_min_gap=0.05, second_max_gap=0.30),
        make_strategy("second_5_20", "Second Favourite 5%-20%", second_min_gap=0.05, second_max_gap=0.20),
        make_strategy("second_10_30", "Second Favourite 10%-30%", second_min_gap=0.10, second_max_gap=0.30),
    ]
    filter_rows = []
    for strategy in validation_strategies:
        result = simulate(races, strategy)
        row = summary_row(strategy.label, result, len(races))
        row["opportunity_retention_pct"] = pct(row["total_opportunities"], len(races) * 2)
        filter_rows.append(row)
    write_csv(output_dir / "filter_validation.csv", filter_rows)

    grade_rows = []
    for grade in sorted({race.grade for race in races}):
        subset = [race for race in races if race.grade == grade]
        result = simulate(subset, Strategy(f"grade_{grade}", grade, no_filters))
        row = summary_row(grade, result, len(subset))
        row["grade"] = grade
        row["race_count"] = len(subset)
        row["average_liability"] = money(result["total_liability"] / result["bets"]) if result["bets"] else 0.0
        row["average_bust_drawdown"] = result["average_bust_drawdown"]
        row["risk_score"] = round(result["bust_count"] * 1000 / max(result["bets"], 1) + max(0, -result["roi_pct"]), 4)
        grade_rows.append(row)
    grade_rows.sort(key=lambda row: (row["risk_score"], -row["roi_pct"]))
    write_csv(output_dir / "grade_analysis.csv", grade_rows)

    venue_rows = []
    for venue in sorted({race.venue for race in races}):
        subset = [race for race in races if race.venue == venue]
        result = simulate(subset, Strategy(f"venue_{venue}", venue, no_filters))
        row = summary_row(venue, result, len(subset))
        row["venue"] = venue
        row["race_count"] = len(subset)
        row["risk_score"] = round(result["bust_count"] * 1000 / max(result["bets"], 1) + result["worst_drawdown"] / 100, 4)
        venue_rows.append(row)
    write_csv(output_dir / "venue_analysis.csv", venue_rows)
    write_csv(output_dir / "venue_most_profitable.csv", sorted(venue_rows, key=lambda row: row["net_pl"], reverse=True))
    write_csv(output_dir / "venue_highest_roi.csv", sorted(venue_rows, key=lambda row: row["roi_pct"], reverse=True))
    write_csv(output_dir / "venue_highest_risk.csv", sorted(venue_rows, key=lambda row: row["risk_score"], reverse=True))
    write_csv(output_dir / "venue_largest_drawdowns.csv", sorted(venue_rows, key=lambda row: row["worst_equity_drawdown"], reverse=True))

    gap_rows = []
    for label, lo, hi in GAP_BUCKETS:
        for rank in (1, 2):
            subset_strategy = Strategy(
                f"gap_{label}_{rank}",
                label,
                lambda race, runner, rnk, lo=lo, hi=hi, rank=rank: rnk == rank
                and race.odds_gap >= lo
                and (hi is None or race.odds_gap < hi),
            )
            result = simulate(races, subset_strategy, ranks=(rank,))
            gap_rows.append(
                {
                    "chain": "favourite" if rank == 1 else "second_favourite",
                    "gap_bucket": label,
                    "opportunities": result["bets"],
                    "win_rate_pct": pct(result["fav_selection_wins"] if rank == 1 else result["second_selection_wins"], result["bets"]),
                    "roi_pct": result["roi_pct"],
                    "bust_count": result["bust_count"],
                    "total_drawdown": money(sum(result["bust_drawdowns"])),
                    "worst_drawdown": result["worst_bust_drawdown"],
                    "net_pl": result["net_pl"],
                }
            )
    write_csv(output_dir / "gap_analysis.csv", gap_rows)

    trap_rows = []
    bands = ["all", "sprint", "standard", "stayer", "marathon"]
    for band in bands:
        for trap in range(1, 7):
            for rank in (1, 2):
                strategy = Strategy(
                    f"trap_{band}_{trap}_{rank}",
                    f"{band} trap {trap} rank {rank}",
                    lambda race, runner, rnk, band=band, trap=trap, rank=rank: rnk == rank
                    and runner.trap == trap
                    and (band == "all" or race.distance_band == band),
                )
                result = simulate(races, strategy, ranks=(rank,))
                trap_rows.append(
                    {
                        "distance_band": band,
                        "trap": trap,
                        "chain": "favourite" if rank == 1 else "second_favourite",
                        "opportunities": result["bets"],
                        "selection_wins": result["fav_selection_wins"] if rank == 1 else result["second_selection_wins"],
                        "win_rate_pct": pct(result["fav_selection_wins"] if rank == 1 else result["second_selection_wins"], result["bets"]),
                        "roi_pct": result["roi_pct"],
                        "bust_count": result["bust_count"],
                    }
                )
    write_csv(output_dir / "trap_analysis.csv", trap_rows)

    current_result = baseline_results[1][1]
    write_csv(output_dir / "recovery_busts.csv", current_result["bust_events"])

    train, validation = period_split(races)
    wf_rows = []
    candidate_results = []
    for strategy in candidate_strategies():
        train_result = simulate(train, strategy)
        candidate_results.append((strategy, train_result))
        wf_rows.append({"period": "training", **summary_row(strategy.label, train_result, len(train)), "score_profit_to_risk": round(score_profit_to_risk(train_result), 4)})
    best_strategy, best_train = max(candidate_results, key=lambda item: score_profit_to_risk(item[1]))
    validation_result = simulate(validation, best_strategy)
    wf_rows.append({"period": "validation_selected", **summary_row(best_strategy.label, validation_result, len(validation)), "score_profit_to_risk": round(score_profit_to_risk(validation_result), 4)})
    write_csv(output_dir / "walk_forward.csv", wf_rows)

    mode_strategies = [
        ("Conservative", "Fav <=5%, 2nd 5-20%, sprint ON", make_strategy("conservative", "Conservative", sprint=True, fav_max_gap=0.05, second_min_gap=0.05, second_max_gap=0.20)),
        ("Balanced", "Fav <=10%, 2nd 5-30%, sprint ON", Strategy("balanced", "Balanced", proposed_rules)),
        ("Aggressive", "Fav <=15%, 2nd 5-40%, sprint ON", make_strategy("aggressive", "Aggressive", sprint=True, fav_max_gap=0.15, second_min_gap=0.05, second_max_gap=0.40)),
    ]
    final_rows = []
    for mode, rules, strategy in mode_strategies:
        result = simulate(races, strategy)
        row = summary_row(mode, result, len(races))
        row["mode"] = mode
        row["rules"] = rules
        final_rows.append(row)
    write_csv(output_dir / "final_recommendations.csv", final_rows)

    all_named_rows = baseline_rows + filter_rows + final_rows
    highest_roi = max(all_named_rows, key=lambda row: row["roi_pct"])
    lowest_risk = min(all_named_rows, key=lambda row: (row["l5_busts"], row["worst_equity_drawdown"], -row["net_pl"]))
    best_profit_to_risk = max(all_named_rows, key=lambda row: row["net_pl"] / max(row["worst_equity_drawdown"], row["max_liability_reached"], 1.0))
    proposed_row = next(row for row in final_rows if row["mode"] == "Balanced")
    current_row = next(row for row in baseline_rows if row["rule_set"] == "Current LayHounds rules")
    proposed_assessment = (
        "Yes, it improves ROI and reduces bust/drawdown versus Current"
        if proposed_row["roi_pct"] > current_row["roi_pct"] and proposed_row["l5_busts"] <= current_row["l5_busts"]
        else "Mixed; review validation metrics before adopting as default"
    )

    summary = {
        "source_archive": str(args.archive),
        "stats": stats,
        "total_races": len(races),
        "date_range": {"first": races[0].date, "last": races[-1].date},
        "baseline": baseline_rows,
        "filter_validation": filter_rows,
        "final_modes": final_rows,
        "walk_forward_selected_strategy": best_strategy.label,
        "walk_forward_training": summary_row(best_strategy.label, best_train, len(train)),
        "walk_forward_validation": summary_row(best_strategy.label, validation_result, len(validation)),
        "highest_roi": highest_roi,
        "lowest_risk": lowest_risk,
        "best_profit_to_risk": best_profit_to_risk,
        "proposed_assessment": proposed_assessment,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output_dir / "executive_summary.md").write_text(build_markdown(output_dir, summary), encoding="utf-8")

    print(f"Included UK/IE races: {len(races):,}")
    print(f"Date range: {races[0].date} to {races[-1].date}")
    print(f"Wrote report bundle to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
