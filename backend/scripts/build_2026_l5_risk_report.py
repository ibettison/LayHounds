from __future__ import annotations

import argparse
import bz2
import csv
import json
import re
import tarfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from itertools import combinations
from pathlib import Path
from typing import Callable, Iterable, Iterator
from zoneinfo import ZoneInfo


COUNTRIES = {"GB", "IE"}
TIME_RE = re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b")
TRAP_RE = re.compile(r"^\s*(?:trap|t|no\.?)?\s*([1-6])(?:\D|$)", re.IGNORECASE)
DIST_RE = re.compile(r"(?<!\d)(\d{3,4})\s*m\b", re.IGNORECASE)
GRADE_RE = re.compile(r"\b(A1[01]?|A[1-9]|D[1-9]|S[1-9]|OR|HP|HT|H[1-3])\b")

DISTANCE_BANDS = {
    "sprint": (0, 320),
    "standard": (321, 499),
    "stayer": (500, 619),
    "marathon": (620, 1200),
}

GAP_BANDS = [
    ("0-5%", 0.00, 0.05),
    ("5-10%", 0.05, 0.10),
    ("10-15%", 0.10, 0.15),
    ("15-20%", 0.15, 0.20),
    ("20%+", 0.20, None),
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
    odds_gap_band: str
    grade: str
    distance_m: int
    distance_band: str


@dataclass
class ChainState:
    consecutive_losses: int = 0
    bets: int = 0
    skips: int = 0
    busts: int = 0


@dataclass(frozen=True)
class Scenario:
    key: str
    label: str
    predicate: Callable[[Race, Runner, int], bool]


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
            timezone_name = definition.get("timezone") or "Europe/London"
            if parsed.tzinfo is not None:
                try:
                    return parsed.astimezone(ZoneInfo(timezone_name)).replace(tzinfo=None)
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
    for band, (lo, hi) in DISTANCE_BANDS.items():
        if lo <= distance_m <= hi:
            return band
    return "standard"


def detect_grade_and_distance(market_name: str, event_name: str) -> tuple[str, int, str]:
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


def gap_band(gap: float) -> str:
    for label, lo, hi in GAP_BANDS:
        if gap >= lo and (hi is None or gap < hi):
            return label
    return "0-5%"


def race_from_definition(member_name: str, definition: dict) -> Race | None:
    if definition.get("marketType") != "WIN" or definition.get("status") != "CLOSED":
        return None
    country = (definition.get("countryCode") or "").upper()
    if country not in COUNTRIES:
        return None

    runners_raw = definition.get("runners") or []
    settled = [
        runner
        for runner in runners_raw
        if runner.get("status") in {"WINNER", "LOSER"} and float(runner.get("bsp") or 0) > 1.01
    ]
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
    odds_gap = (second_favourite_odds - favourite_odds) / favourite_odds if favourite_odds > 0 else 0.0
    grade, distance_m, band = detect_grade_and_distance(market_name, event_name)
    winning_trap = trap_from_runner_name(winner.get("name") or "") or int(winner.get("sortPriority") or 0)
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
        winning_trap=winning_trap,
        favourite_odds=favourite_odds,
        second_favourite_odds=second_favourite_odds,
        odds_gap=odds_gap,
        odds_gap_band=gap_band(odds_gap),
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


def no_filters(_: Race, __: Runner, ___: int) -> bool:
    return True


def variance_rule(race: Race, _: Runner, rank: int) -> bool:
    return not (rank == 1 and race.odds_gap > 0.15)


def sprint_inside_rule(race: Race, runner: Runner, _: int) -> bool:
    return not (race.distance_band == "sprint" and runner.trap in {1, 2})


def odds_min_rule(_: Race, runner: Runner, __: int) -> bool:
    return runner.odds >= 2.0


def both_rules(race: Race, runner: Runner, rank: int) -> bool:
    return variance_rule(race, runner, rank) and sprint_inside_rule(race, runner, rank)


def both_plus_odds(race: Race, runner: Runner, rank: int) -> bool:
    return both_rules(race, runner, rank) and odds_min_rule(race, runner, rank)


def simulate(
    races: list[Race],
    scenario: Scenario,
    *,
    bust_depth: int = 5,
) -> dict:
    chains = {1: ChainState(), 2: ChainState()}
    events: list[dict] = []
    per_rank_seen = Counter()

    for race in races:
        for rank in (1, 2):
            runner = runner_by_rank(race, rank)
            if runner is None:
                continue
            per_rank_seen[rank] += 1
            chain = chains[rank]
            if not scenario.predicate(race, runner, rank):
                chain.skips += 1
                continue

            chain.bets += 1
            if runner.trap == race.winning_trap:
                chain.consecutive_losses += 1
                if chain.consecutive_losses >= bust_depth:
                    chain.busts += 1
                    events.append(
                        {
                            "scenario": scenario.key,
                            "scenario_label": scenario.label,
                            "chain": "favourite" if rank == 1 else "second_favourite",
                            "rank": rank,
                            "date": race.date,
                            "race_time": race.race_time,
                            "market_id": race.market_id,
                            "venue": race.venue,
                            "grade": race.grade,
                            "distance_band": race.distance_band,
                            "distance_m": race.distance_m,
                            "trap": runner.trap,
                            "odds": runner.odds,
                            "favourite_odds": race.favourite_odds,
                            "second_favourite_odds": race.second_favourite_odds,
                            "odds_gap": round(race.odds_gap, 6),
                            "odds_gap_band": race.odds_gap_band,
                            "market_name": race.market_name,
                            "event_name": race.event_name,
                        }
                    )
                    chain.consecutive_losses = 0
            else:
                chain.consecutive_losses = 0

    return {
        "scenario": scenario.key,
        "scenario_label": scenario.label,
        "chains": {
            "favourite": {
                "rank": 1,
                "available_races": per_rank_seen[1],
                "bets": chains[1].bets,
                "skips": chains[1].skips,
                "busts": chains[1].busts,
                "bet_retention_pct": pct(chains[1].bets, per_rank_seen[1]),
            },
            "second_favourite": {
                "rank": 2,
                "available_races": per_rank_seen[2],
                "bets": chains[2].bets,
                "skips": chains[2].skips,
                "busts": chains[2].busts,
                "bet_retention_pct": pct(chains[2].bets, per_rank_seen[2]),
            },
        },
        "events": events,
    }


def pct(numerator: int | float, denominator: int | float) -> float:
    return round((float(numerator) / float(denominator) * 100.0), 2) if denominator else 0.0


def counter_rows(events: list[dict], field: str) -> list[dict]:
    grouped: dict[tuple[str, str, str], int] = defaultdict(int)
    for event in events:
        grouped[(event["scenario"], event["chain"], str(event[field]))] += 1
    return [
        {"scenario": scenario, "chain": chain, field: value, "busts": busts}
        for (scenario, chain, value), busts in sorted(grouped.items(), key=lambda item: (-item[1], item[0]))
    ]


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def scenario_summary_rows(results: list[dict]) -> list[dict]:
    rows = []
    baseline_by_chain = results[0]["chains"]
    for result in results:
        for chain, stats in result["chains"].items():
            baseline = baseline_by_chain[chain]
            rows.append(
                {
                    "scenario": result["scenario"],
                    "scenario_label": result["scenario_label"],
                    "chain": chain,
                    "available_races": stats["available_races"],
                    "bets": stats["bets"],
                    "skips": stats["skips"],
                    "bet_retention_pct": stats["bet_retention_pct"],
                    "busts": stats["busts"],
                    "bust_reduction_vs_no_filters": baseline["busts"] - stats["busts"],
                    "bust_reduction_pct_vs_no_filters": pct(baseline["busts"] - stats["busts"], baseline["busts"]),
                    "bet_reduction_vs_no_filters": baseline["bets"] - stats["bets"],
                    "bet_reduction_pct_vs_no_filters": pct(baseline["bets"] - stats["bets"], baseline["bets"]),
                }
            )
    return rows


def dimensions_for_events(events: list[dict]) -> dict[str, list[dict]]:
    return {
        "daily_bust_counts.csv": counter_rows(events, "date"),
        "venue_bust_counts.csv": counter_rows(events, "venue"),
        "grade_bust_counts.csv": counter_rows(events, "grade"),
        "distance_band_bust_counts.csv": counter_rows(events, "distance_band"),
        "trap_bust_counts.csv": counter_rows(events, "trap"),
        "odds_gap_band_bust_counts.csv": counter_rows(events, "odds_gap_band"),
    }


def opportunities_by_dimension(races: list[Race], base_predicate: Callable[[Race, Runner, int], bool], field: str) -> Counter:
    counts = Counter()
    for race in races:
        value = getattr(race, field)
        for rank in (1, 2):
            runner = runner_by_rank(race, rank)
            if runner and base_predicate(race, runner, rank):
                counts[(rank, value)] += 1
    return counts


def busts_by_dimension(events: list[dict], field: str, scenario: str) -> Counter:
    counts = Counter()
    for event in events:
        if event["scenario"] != scenario:
            continue
        counts[(event["rank"], event[field])] += 1
    return counts


def build_filter_candidates(races: list[Race], events: list[dict], field: str, scenario: str) -> list[dict]:
    opportunities = opportunities_by_dimension(races, both_rules, field)
    busts = busts_by_dimension(events, field, scenario)
    rows = []
    for key, bust_count in busts.items():
        rank, value = key
        opps = opportunities.get(key, 0)
        rows.append(
            {
                "dimension": field,
                "chain": "favourite" if rank == 1 else "second_favourite",
                "rank": rank,
                "value": value,
                "busts_after_both_rules": bust_count,
                "qualified_bets_after_both_rules": opps,
                "busts_per_1000_bets": round(bust_count / opps * 1000.0, 3) if opps else 0.0,
            }
        )
    rows.sort(key=lambda row: (-row["busts_after_both_rules"], row["qualified_bets_after_both_rules"], row["value"]))
    return rows


def greedy_filter_values(
    races: list[Race],
    *,
    field: str,
    candidates: list[dict],
    max_bet_reduction_pct: float = 20.0,
) -> list[str]:
    chosen: list[str] = []
    base = Scenario("both_rules", "15% variance + sprint Trap 1/2", both_rules)
    base_result = simulate(races, base)
    base_busts = sum(stats["busts"] for stats in base_result["chains"].values())
    base_bets = sum(stats["bets"] for stats in base_result["chains"].values())

    while True:
        best = None
        for candidate in candidates:
            value = candidate["value"]
            if value in chosen:
                continue

            test_values = set(chosen + [value])

            def pred(race: Race, runner: Runner, rank: int, values=test_values) -> bool:
                return both_rules(race, runner, rank) and str(getattr(race, field)) not in values

            result = simulate(races, Scenario("candidate", "candidate", pred))
            busts = sum(stats["busts"] for stats in result["chains"].values())
            bets = sum(stats["bets"] for stats in result["chains"].values())
            bust_reduction = base_busts - busts
            bet_reduction_pct = pct(base_bets - bets, base_bets)
            if bet_reduction_pct > max_bet_reduction_pct:
                continue
            score = (bust_reduction, -bet_reduction_pct, -len(test_values))
            if best is None or score > best["score"]:
                best = {
                    "value": value,
                    "score": score,
                    "busts": busts,
                    "bets": bets,
                    "bet_reduction_pct": bet_reduction_pct,
                }

        if best is None:
            break
        if chosen and best["score"][0] <= base_busts - sum(
            stats["busts"]
            for stats in simulate(
                races,
                Scenario(
                    "current",
                    "current",
                    lambda race, runner, rank, values=set(chosen): both_rules(race, runner, rank)
                    and str(getattr(race, field)) not in values,
                ),
            )["chains"].values()
        ):
            break
        chosen.append(str(best["value"]))
        if best["busts"] == 0:
            break
    return chosen


def exhaustive_filter_tradeoffs(
    races: list[Race],
    *,
    field: str,
    values: list[str],
    base_result: dict,
) -> list[dict]:
    base_busts = sum(stats["busts"] for stats in base_result["chains"].values())
    base_bets = sum(stats["bets"] for stats in base_result["chains"].values())
    rows = []
    for size in range(0, len(values) + 1):
        for combo in combinations(values, size):
            result = simulate(races, make_exclusion_scenario("candidate", "candidate", field, set(combo)))
            busts = sum(stats["busts"] for stats in result["chains"].values())
            bets = sum(stats["bets"] for stats in result["chains"].values())
            rows.append(
                {
                    "dimension": field,
                    "excluded_values": "; ".join(combo),
                    "filter_count": size,
                    "bets": bets,
                    "busts": busts,
                    "bust_reduction_vs_both_rules": base_busts - busts,
                    "bust_reduction_pct_vs_both_rules": pct(base_busts - busts, base_busts),
                    "bet_reduction_vs_both_rules": base_bets - bets,
                    "bet_reduction_pct_vs_both_rules": pct(base_bets - bets, base_bets),
                }
            )
    rows.sort(
        key=lambda row: (
            row["busts"],
            row["bet_reduction_pct_vs_both_rules"],
            row["filter_count"],
            row["excluded_values"],
        )
    )
    return rows


def select_balanced_filter_values(tradeoffs: list[dict], *, max_bet_reduction_pct: float = 25.0) -> list[str]:
    viable = [row for row in tradeoffs if row["bet_reduction_pct_vs_both_rules"] <= max_bet_reduction_pct]
    if not viable:
        return []
    viable.sort(
        key=lambda row: (
            row["busts"],
            row["bet_reduction_pct_vs_both_rules"],
            row["filter_count"],
            row["excluded_values"],
        )
    )
    return [value for value in viable[0]["excluded_values"].split("; ") if value]


def make_exclusion_scenario(key: str, label: str, field: str, values: set[str]) -> Scenario:
    def predicate(race: Race, runner: Runner, rank: int) -> bool:
        return both_rules(race, runner, rank) and str(getattr(race, field)) not in values

    return Scenario(key, label, predicate)


def markdown_report(
    *,
    archive: Path,
    output_dir: Path,
    stats: dict,
    summary_rows: list[dict],
    venue_filters: list[str],
    grade_filters: list[str],
    venue_candidates: list[dict],
    grade_candidates: list[dict],
    venue_tradeoffs: list[dict],
    grade_tradeoffs: list[dict],
) -> str:
    def row_for(scenario: str, chain: str) -> dict:
        return next(row for row in summary_rows if row["scenario"] == scenario and row["chain"] == chain)

    lines = [
        "# LayHounds 2026 UK/IE L5 Recovery-Chain Risk Report",
        "",
        f"Source archive: `{archive}`",
        f"Output directory: `{output_dir}`",
        "",
        "## Scope",
        "",
        f"- Archive members scanned: {stats.get('archive_members', 0):,}",
        f"- Betfair market files scanned: {stats.get('market_files', 0):,}",
        f"- UK/IE closed WIN races included: {stats.get('included_uk_ie_races', 0):,}",
        "- Bust definition: five consecutive backed winners against the same lay chain.",
        "- Favourite and second-favourite chains are simulated independently.",
        "- Skipped selections do not advance or reset a chain.",
        "",
        "## Scenario Summary",
        "",
        "| Scenario | Chain | Bets | Retained | Busts | Bust reduction | Bet reduction |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            "| {scenario_label} | {chain} | {bets:,} | {bet_retention_pct:.2f}% | {busts:,} | "
            "{bust_reduction_pct_vs_no_filters:.2f}% | {bet_reduction_pct_vs_no_filters:.2f}% |".format(**row)
        )

    fav_both = row_for("both_rules", "favourite")
    second_both = row_for("both_rules", "second_favourite")
    fav_best = row_for("both_rules_plus_odds_ge_2", "favourite")
    second_best = row_for("both_rules_plus_odds_ge_2", "second_favourite")
    lines.extend(
        [
            "",
            "## Strongest Filters",
            "",
            (
                f"- The combined variance + sprint-inside rule leaves {fav_both['busts']} favourite busts "
                f"and {second_both['busts']} second-favourite busts while retaining "
                f"{fav_both['bet_retention_pct']:.2f}% / {second_both['bet_retention_pct']:.2f}% of opportunities."
            ),
            (
                f"- Adding odds >= 2.0 leaves {fav_best['busts']} favourite busts and "
                f"{second_best['busts']} second-favourite busts, retaining "
                f"{fav_best['bet_retention_pct']:.2f}% / {second_best['bet_retention_pct']:.2f}%."
            ),
            (
                f"- Balanced venue filter set selected: {', '.join(venue_filters) if venue_filters else 'none'}."
            ),
            (
                f"- Balanced grade filter set selected: {', '.join(grade_filters) if grade_filters else 'none'}."
            ),
            (
                f"- Exhaustive venue search over bust-source venues bottoms out at "
                f"{venue_tradeoffs[0]['busts']} remaining busts with "
                f"{venue_tradeoffs[0]['bet_reduction_pct_vs_both_rules']:.2f}% fewer bets."
            ),
            (
                f"- Exhaustive grade search over bust-source grades bottoms out at "
                f"{grade_tradeoffs[0]['busts']} remaining busts with "
                f"{grade_tradeoffs[0]['bet_reduction_pct_vs_both_rules']:.2f}% fewer bets."
            ),
            "",
            "## Recommended 2026 Defaults",
            "",
            "1. Keep the 15% favourite variance rule enabled for the favourite chain.",
            "2. Keep the sprint Trap 1/2 skip enabled for both favourite and second-favourite chains.",
            "3. Keep odds >= 2.0 enabled at least for the favourite chain; it is cheap insurance against very short-priced favourites.",
        ]
    )
    if venue_filters:
        lines.append(f"4. Consider venue exclusions only as a higher-risk mode toggle: {', '.join(venue_filters)}.")
    if grade_filters:
        lines.append(f"5. Consider grade exclusions only if you accept the opportunity loss: {', '.join(grade_filters)}.")

    lines.extend(
        [
            "",
            "## Top Venue Bust Sources After Both Core Rules",
            "",
            "| Chain | Venue | Busts | Qualified bets | Busts / 1000 bets |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for row in venue_candidates[:15]:
        lines.append(
            f"| {row['chain']} | {row['value']} | {row['busts_after_both_rules']} | "
            f"{row['qualified_bets_after_both_rules']} | {row['busts_per_1000_bets']} |"
        )

    lines.extend(
        [
            "",
            "## Top Grade Bust Sources After Both Core Rules",
            "",
            "| Chain | Grade | Busts | Qualified bets | Busts / 1000 bets |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for row in grade_candidates[:15]:
        lines.append(
            f"| {row['chain']} | {row['value']} | {row['busts_after_both_rules']} | "
            f"{row['qualified_bets_after_both_rules']} | {row['busts_per_1000_bets']} |"
        )

    lines.extend(
        [
            "",
            "## Files",
            "",
            "- `summary.json` and `scenario_summary.csv`: headline scenario results.",
            "- `bust_events.csv`: every L5 bust event with race, chain, trap, venue, grade, distance and odds-gap context.",
            "- `daily_bust_counts.csv`, `venue_bust_counts.csv`, `grade_bust_counts.csv`, `distance_band_bust_counts.csv`, `trap_bust_counts.csv`, `odds_gap_band_bust_counts.csv`: requested breakdowns.",
            "- `venue_filter_candidates.csv` and `grade_filter_candidates.csv`: per-value filter trade-off inputs.",
            "- `venue_filter_tradeoffs.csv` and `grade_filter_tradeoffs.csv`: exhaustive combinations over bust-source values.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build 2026 UK/IE LayHounds L5 chain risk reports from Betfair BASIC data.tar.")
    parser.add_argument("archive", type=Path, help="Path to Betfair BASIC data.tar")
    parser.add_argument("--output-dir", type=Path, default=Path("test_reports") / "layhounds_2026_l5_risk")
    parser.add_argument("--limit", type=int, default=0, help="Optional quick-run limit of included races.")
    args = parser.parse_args()

    races, stats = load_races(args.archive, limit=args.limit)
    if not races:
        raise SystemExit(f"No UK/IE races found in {args.archive}")

    base_scenarios = [
        Scenario("no_filters", "No filters", no_filters),
        Scenario("variance_15_only", "15% variance only", variance_rule),
        Scenario("sprint_trap_1_2_only", "Sprint Trap 1/2 only", sprint_inside_rule),
        Scenario("both_rules", "15% variance + sprint Trap 1/2", both_rules),
        Scenario("both_rules_plus_odds_ge_2", "Both rules + odds >= 2.0", both_plus_odds),
    ]
    base_results = [simulate(races, scenario) for scenario in base_scenarios]
    base_events = [event for result in base_results for event in result["events"]]

    venue_candidates = build_filter_candidates(races, base_events, "venue", "both_rules")
    grade_candidates = build_filter_candidates(races, base_events, "grade", "both_rules")
    both_rules_result = next(result for result in base_results if result["scenario"] == "both_rules")
    venue_values = sorted({str(event["venue"]) for event in both_rules_result["events"]})
    grade_values = sorted({str(event["grade"]) for event in both_rules_result["events"]})
    venue_tradeoffs = exhaustive_filter_tradeoffs(
        races,
        field="venue",
        values=venue_values,
        base_result=both_rules_result,
    )
    grade_tradeoffs = exhaustive_filter_tradeoffs(
        races,
        field="grade",
        values=grade_values,
        base_result=both_rules_result,
    )
    venue_filters = select_balanced_filter_values(venue_tradeoffs, max_bet_reduction_pct=25.0)
    grade_filters = select_balanced_filter_values(grade_tradeoffs, max_bet_reduction_pct=25.0)

    extra_scenarios = [
        make_exclusion_scenario(
            "both_rules_plus_venue_filters",
            f"Both rules + venue filters ({', '.join(venue_filters) if venue_filters else 'none'})",
            "venue",
            set(venue_filters),
        ),
        make_exclusion_scenario(
            "both_rules_plus_grade_filters",
            f"Both rules + grade filters ({', '.join(grade_filters) if grade_filters else 'none'})",
            "grade",
            set(grade_filters),
        ),
    ]
    results = base_results + [simulate(races, scenario) for scenario in extra_scenarios]
    events = [event for result in results for event in result["events"]]
    summary_rows = scenario_summary_rows(results)

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "scenario_summary.csv", summary_rows)
    write_csv(output_dir / "bust_events.csv", events)
    write_csv(output_dir / "venue_filter_candidates.csv", venue_candidates)
    write_csv(output_dir / "grade_filter_candidates.csv", grade_candidates)
    write_csv(output_dir / "venue_filter_tradeoffs.csv", venue_tradeoffs)
    write_csv(output_dir / "grade_filter_tradeoffs.csv", grade_tradeoffs)
    for filename, rows in dimensions_for_events(events).items():
        write_csv(output_dir / filename, rows)

    summary = {
        "source_archive": str(args.archive),
        "countries": sorted(COUNTRIES),
        "stats": stats,
        "total_races_scanned": stats.get("market_files", 0),
        "included_uk_ie_races": len(races),
        "scenario_summary": summary_rows,
        "selected_venue_filters": venue_filters,
        "selected_grade_filters": grade_filters,
        "venue_filter_tradeoffs_best": venue_tradeoffs[:10],
        "grade_filter_tradeoffs_best": grade_tradeoffs[:10],
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    report = markdown_report(
        archive=args.archive,
        output_dir=output_dir,
        stats=stats,
        summary_rows=summary_rows,
        venue_filters=venue_filters,
        grade_filters=grade_filters,
        venue_candidates=venue_candidates,
        grade_candidates=grade_candidates,
        venue_tradeoffs=venue_tradeoffs,
        grade_tradeoffs=grade_tradeoffs,
    )
    (output_dir / "historical_risk_report.md").write_text(report, encoding="utf-8")

    print(f"Included UK/IE races: {len(races):,}")
    print(f"Wrote report bundle to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
