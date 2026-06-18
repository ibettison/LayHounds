from __future__ import annotations

import argparse
import bz2
import csv
import json
import re
import sys
import tarfile
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models import Greyhound, SessionConfig  # noqa: E402
from services.backtest_analysis import (  # noqa: E402
    FILTERS,
    RaceSnapshot,
    build_analysis_csv,
)

DISTANCE_RE = re.compile(r"(?<!\d)(\d{3,4})\s*m\b", re.IGNORECASE)
TRAP_RE = re.compile(r"^\s*(?:trap|t|no\.?)?\s*([1-9])(?:\D|$)", re.IGNORECASE)


def _parse_trap(name: str, sort_priority: int) -> int:
    if match := TRAP_RE.search(name or ""):
        return int(match.group(1))
    return int(sort_priority or 0)


def _parse_distance(market_name: str, event_name: str) -> int:
    blob = " ".join(filter(None, [market_name or "", event_name or ""]))
    if match := DISTANCE_RE.search(blob):
        return int(match.group(1))
    return 0


def _iter_json_lines(tar: tarfile.TarFile, member: tarfile.TarInfo) -> Iterator[dict]:
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


def _snapshot_from_market(member_name: str, objects: Iterable[dict], race_num: int) -> Optional[RaceSnapshot]:
    latest_definition: Optional[dict] = None
    for obj in objects:
        for market_change in obj.get("mc") or []:
            definition = market_change.get("marketDefinition")
            if definition:
                latest_definition = definition

    if not latest_definition:
        return None
    if latest_definition.get("marketType") != "WIN":
        return None
    if latest_definition.get("status") != "CLOSED":
        return None

    country = latest_definition.get("countryCode") or ""
    venue = latest_definition.get("venue") or latest_definition.get("eventName") or ""
    runners_raw = latest_definition.get("runners") or []
    settled = [
        runner for runner in runners_raw
        if runner.get("status") in {"WINNER", "LOSER"} and float(runner.get("bsp") or 0) > 1.01
    ]
    if len(settled) < 2:
        return None

    winner = next((runner for runner in settled if runner.get("status") == "WINNER"), None)
    if not winner:
        return None

    sorted_by_bsp = sorted(settled, key=lambda runner: float(runner.get("bsp") or 9999))
    rank_by_id = {runner["id"]: idx + 1 for idx, runner in enumerate(sorted_by_bsp)}
    runners = [
        Greyhound(
            trap=_parse_trap(runner.get("name") or "", int(runner.get("sortPriority") or 0)),
            name=runner.get("name") or str(runner.get("id")),
            odds=round(float(runner.get("bsp")), 2),
            favourite_rank=rank_by_id[runner["id"]],
        )
        for runner in settled
    ]
    winning_trap = _parse_trap(winner.get("name") or "", int(winner.get("sortPriority") or 0))
    market_base_rate = float(latest_definition.get("marketBaseRate") or 5.0) / 100.0
    market_name = latest_definition.get("name") or ""
    event_name = latest_definition.get("eventName") or ""
    distance_m = _parse_distance(market_name, event_name)
    venue_label = f"{venue} ({country})" if country else venue
    return RaceSnapshot(
        race_num=race_num,
        venue=venue_label or member_name,
        runners=runners,
        winning_trap=winning_trap,
        distance_m=distance_m,
        commission_rate=market_base_rate,
    )


def load_snapshots(
    archive_path: Path,
    *,
    country_codes: Optional[set[str]] = None,
    limit: Optional[int] = None,
) -> tuple[List[RaceSnapshot], Dict[str, int]]:
    snapshots: List[RaceSnapshot] = []
    stats = {
        "archive_members": 0,
        "market_files": 0,
        "win_markets": 0,
        "settled_snapshots": 0,
        "skipped_country": 0,
    }
    with tarfile.open(archive_path, "r") as tar:
        for member in tar:
            stats["archive_members"] += 1
            name = member.name
            filename = Path(name).name
            if not member.isfile() or not filename.startswith("1.") or not filename.endswith(".bz2"):
                continue
            stats["market_files"] += 1
            objects = list(_iter_json_lines(tar, member))
            latest_definition = None
            for obj in objects:
                for market_change in obj.get("mc") or []:
                    definition = market_change.get("marketDefinition")
                    if definition:
                        latest_definition = definition
            if not latest_definition or latest_definition.get("marketType") != "WIN":
                continue
            stats["win_markets"] += 1
            country = latest_definition.get("countryCode") or ""
            if country_codes and country not in country_codes:
                stats["skipped_country"] += 1
                continue
            snapshot = _snapshot_from_market(name, objects, len(snapshots) + 1)
            if not snapshot:
                continue
            snapshots.append(snapshot)
            stats["settled_snapshots"] += 1
            if limit and len(snapshots) >= limit:
                break
    return snapshots, stats


def _summary_rows(csv_body: str) -> List[dict]:
    return [
        row for row in csv.DictReader(csv_body.splitlines())
        if row.get("row_type") == "summary"
    ]


def write_summary(summary_path: Path, stats: Dict[str, int], csv_body: str) -> None:
    rows = _summary_rows(csv_body)
    lines = ["Betfair historical favourite-lay backtest", ""]
    lines.extend(f"{key}: {value}" for key, value in stats.items())
    lines.append("")
    lines.append(
        "filter,total_races,bets,skipped,fav_win_pct,final_pnl,max_drawdown,"
        "highest_recovery,busts,avg_liability,worst_losing_run"
    )
    for row in rows:
        lines.append(
            ",".join(
                [
                    row["filter_key"],
                    row["total_races_tested"],
                    row["bets_placed"],
                    row["races_skipped"],
                    row["favourite_win_percentage"],
                    row["final_profit_loss"],
                    row["maximum_drawdown"],
                    row["highest_recovery_balance"],
                    row["number_of_busts"],
                    row["average_liability"],
                    row["worst_losing_run"],
                ]
            )
        )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyse Betfair BASIC greyhound historical tar data.")
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, default=Path("betfair-historical-analysis.csv"))
    parser.add_argument("--summary", type=Path, default=Path("betfair-historical-summary.txt"))
    parser.add_argument("--limit", type=int, default=0, help="Limit settled WIN markets for a quick sample.")
    parser.add_argument("--countries", default="", help="Comma-separated country codes, e.g. GB,IE. Empty = all.")
    parser.add_argument("--stake", type=float, default=0.05)
    parser.add_argument("--starting-bank", type=float, default=1000.0)
    parser.add_argument("--stop-loss", type=float, default=1000.0)
    parser.add_argument("--max-liability-cap", type=float, default=0.0)
    parser.add_argument("--max-recovery-level", type=int, default=3)
    parser.add_argument("--include-races", action="store_true")
    args = parser.parse_args()

    countries = {c.strip().upper() for c in args.countries.split(",") if c.strip()}
    snapshots, stats = load_snapshots(
        args.archive,
        country_codes=countries or None,
        limit=args.limit or None,
    )
    config = SessionConfig(
        mode="simulator",
        num_favourites=1,
        stake=args.stake,
        starting_bank=args.starting_bank,
        stop_win=1_000_000,
        stop_loss=args.stop_loss,
        max_races=200,
        max_liability_cap=args.max_liability_cap,
        commission_rate=0.05,
        max_recovery_level=args.max_recovery_level,
    )
    csv_body = build_analysis_csv(
        snapshots,
        config,
        include_races=args.include_races,
        repeat_50_samples=0,
    )
    args.output.write_text(csv_body, encoding="utf-8", newline="")
    write_summary(args.summary, stats, csv_body)
    print(f"settled WIN snapshots: {len(snapshots)}")
    print(f"CSV: {args.output}")
    print(f"summary: {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
