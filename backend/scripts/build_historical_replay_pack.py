from __future__ import annotations

import argparse
import bz2
import json
import re
import tarfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BACKEND_DIR = Path(__file__).resolve().parents[1]
COUNTRIES = {"GB", "IE"}
TIME_RE = re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b")
TRAP_RE = re.compile(r"^\s*(?:trap\s*)?([1-6])[\.\-\s]+", re.IGNORECASE)
DIST_RE = re.compile(r"(?<!\d)(\d{3,4})\s*m\b", re.IGNORECASE)
GRADE_RE = re.compile(r"\b(A1[01]?|A[1-9]|OR|HP|HT|H[1-3])\b")

GRADE_LABELS = {
    "A1": "A1 - Top Grade",
    "A2": "A2",
    "A3": "A3",
    "A4": "A4",
    "A5": "A5",
    "A6": "A6",
    "A7": "A7",
    "A8": "A8",
    "A9": "A9 - Maiden",
    "A10": "A10 - Maiden",
    "A11": "A11 - Novice",
    "OR": "OR - Open Race",
    "H1": "H1 - Hurdle",
    "H2": "H2 - Hurdle",
    "H3": "H3 - Hurdle",
}

DISTANCE_BANDS = {
    "sprint": {"label": "Sprint", "range_m": (0, 320)},
    "standard": {"label": "Standard", "range_m": (321, 499)},
    "stayer": {"label": "Stayer", "range_m": (500, 619)},
    "marathon": {"label": "Marathon", "range_m": (620, 1200)},
}


def iter_json_lines(tar: tarfile.TarFile, member: tarfile.TarInfo):
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


def latest_definition(objects) -> dict | None:
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


def trap_from_runner_name(name: str) -> int | None:
    match = TRAP_RE.search(name or "")
    if not match:
        return None
    return int(match.group(1))


def fill_missing_traps(priced: list[dict]) -> None:
    used = {runner["trap"] for runner in priced if runner.get("trap")}
    available = [trap for trap in range(1, 7) if trap not in used]
    for runner in priced:
        if runner.get("trap"):
            continue
        runner["trap"] = available.pop(0) if available else int(runner.get("sort_priority") or 0)


def band_for_distance(distance_m: int) -> str:
    for band, meta in DISTANCE_BANDS.items():
        lo, hi = meta["range_m"]
        if lo <= distance_m <= hi:
            return band
    return "standard"


def detect_category(market_name: str, event_name: str) -> dict:
    blob = " ".join(filter(None, [market_name or "", event_name or ""]))
    distance_m = 480
    if match := DIST_RE.search(blob):
        try:
            distance_m = int(match.group(1))
        except ValueError:
            distance_m = 480

    grade = "A4"
    if match := GRADE_RE.search(blob.upper()):
        grade_raw = match.group(1)
        if grade_raw in ("HP", "HT"):
            grade_raw = "H2"
        if grade_raw in GRADE_LABELS:
            grade = grade_raw

    band = band_for_distance(distance_m)
    return {
        "grade": grade,
        "grade_label": GRADE_LABELS[grade],
        "distance_m": distance_m,
        "distance_band": band,
        "distance_band_label": DISTANCE_BANDS[band]["label"],
    }


def race_from_definition(member_name: str, definition: dict) -> dict | None:
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

    sorted_by_bsp = sorted(priced, key=lambda runner: runner["odds"])
    rank_by_id = {runner["id"]: idx + 1 for idx, runner in enumerate(sorted_by_bsp)}
    runners = [
        {
            "trap": runner["trap"],
            "name": runner["name"],
            "odds": runner["odds"],
            "favourite_rank": rank_by_id[runner["id"]],
        }
        for runner in priced
    ]

    market_name = definition.get("name") or ""
    event_name = definition.get("eventName") or ""
    venue = definition.get("venue") or event_name or Path(member_name).stem
    historic_start = parse_start_time(definition)
    if not historic_start:
        return None
    historic_start_iso = historic_start.isoformat()
    market_id = str(definition.get("_marketId") or Path(member_name).stem)
    winning_trap = trap_from_runner_name(winner.get("name") or "") or int(winner.get("sortPriority") or 0)

    return {
        "market_id": market_id,
        "market_name": market_name,
        "event_name": event_name,
        "venue": f"{venue} ({country})",
        "race_time": historic_start_iso,
        "runners": runners,
        "favourite_odds": round(sorted_by_bsp[0]["odds"], 2),
        "second_favourite_odds": round(sorted_by_bsp[1]["odds"], 2),
        "winning_trap": winning_trap,
        "result": winning_trap,
        "category": detect_category(market_name, event_name),
        "historic_start_time": historic_start_iso,
        "replay_start_time": historic_start_iso,
        "market_time_label": historic_start.strftime("%H:%M"),
        "commission_rate": float(definition.get("marketBaseRate") or 5.0) / 100.0,
    }


def build_pack(archive: Path, output: Path, days: int, min_races_per_day: int) -> dict:
    races_by_day = defaultdict(list)
    scanned_markets = 0

    with tarfile.open(archive, "r") as tar:
        for member in tar:
            filename = Path(member.name).name
            if not member.isfile() or not filename.startswith("1.") or not filename.endswith(".bz2"):
                continue
            scanned_markets += 1
            definition = latest_definition(iter_json_lines(tar, member))
            if not definition:
                continue
            race = race_from_definition(member.name, definition)
            if not race:
                continue
            races_by_day[race["race_time"][:10]].append(race)

    selected_days = []
    for day in sorted(races_by_day):
        day_races = sorted(races_by_day[day], key=lambda race: race["race_time"])
        if len(day_races) < min_races_per_day:
            continue
        selected_days.append((day, day_races))
        if len(selected_days) >= days:
            break

    if not selected_days:
        raise SystemExit(
            f"No UK/IE historical replay days with at least {min_races_per_day} races were found in {archive}"
        )

    packed_races = [race for _, day_races in selected_days for race in day_races]
    payload = {
        "schema_version": 1,
        "description": "Compact UK/IE LayHounds Historical Replay sample extracted from Betfair BASIC data.",
        "source_archive_name": archive.name,
        "countries": sorted(COUNTRIES),
        "days": [
            {
                "date": day,
                "race_count": len(day_races),
                "first_race_time": day_races[0]["race_time"],
                "last_race_time": day_races[-1]["race_time"],
            }
            for day, day_races in selected_days
        ],
        "scanned_markets": scanned_markets,
        "included_markets": len(packed_races),
        "races": packed_races,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a compact UK/IE-only Historical Replay JSON pack from a Betfair BASIC data.tar archive."
    )
    parser.add_argument("archive", type=Path, help="Path to Betfair BASIC data.tar")
    parser.add_argument(
        "--output",
        type=Path,
        default=BACKEND_DIR / "data" / "historical_replay_sample.json",
        help="Output JSON replay pack path",
    )
    parser.add_argument("--days", type=int, default=5, help="Number of full historical days to include")
    parser.add_argument(
        "--min-races-per-day",
        type=int,
        default=20,
        help="Only include days with at least this many UK/IE races",
    )
    args = parser.parse_args()

    payload = build_pack(args.archive, args.output, args.days, args.min_races_per_day)
    print(
        f"Wrote {payload['included_markets']} UK/IE markets across {len(payload['days'])} days "
        f"to {args.output}"
    )


if __name__ == "__main__":
    main()
