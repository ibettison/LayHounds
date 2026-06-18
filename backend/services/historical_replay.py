from __future__ import annotations

import bz2
import json
import logging
import os
import random
import re
import tarfile
from dataclasses import dataclass
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional

from models import Greyhound, Session
from race_categories import RaceCategory, detect_category_from_market_name
from services.racing import fill_missing_traps, trap_from_runner_name

logger = logging.getLogger(__name__)

COUNTRIES = {"GB", "IE"}
DISTANCE_RE = re.compile(r"(?<!\d)(\d{3,4})\s*m\b", re.IGNORECASE)
TIME_RE = re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b")


@dataclass(frozen=True)
class HistoricalRace:
    market_id: str
    market_name: str
    event_name: str
    venue: str
    runners: List[Greyhound]
    winning_trap: int
    category: RaceCategory
    historic_start_time: Optional[str]
    replay_start_time: Optional[str]
    commission_rate: float


_loaded_archive: Optional[Path] = None
_days_by_key: Dict[str, List[HistoricalRace]] = {}


def _candidate_archives() -> List[Path]:
    configured = os.environ.get("LAYHOUNDS_HISTORICAL_TAR", "").strip()
    candidates = []
    if configured:
        candidates.append(Path(configured))
    candidates.extend(
        [
            Path("H:/Downloads/data.tar"),
            Path.home() / "Downloads" / "data.tar",
        ]
    )
    return candidates


def _archive_path() -> Optional[Path]:
    for candidate in _candidate_archives():
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


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


def _latest_definition(objects: Iterable[dict]) -> Optional[dict]:
    latest: Optional[dict] = None
    for obj in objects:
        for market_change in obj.get("mc") or []:
            definition = market_change.get("marketDefinition")
            if definition:
                latest = definition
    return latest


def _parse_start_time(definition: dict) -> Optional[datetime]:
    raw = definition.get("marketTime") or definition.get("openDate")
    if raw:
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            pass

    # Some BASIC archive rows omit marketTime/openDate but include the race
    # clock in names like "Towcester 16:16 R4 240m".
    blob = " ".join(
        filter(None, [definition.get("name") or "", definition.get("eventName") or ""])
    )
    match = TIME_RE.search(blob)
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    return datetime(1970, 1, 1, hour, minute)


def _parse_iso_datetime(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def _today_with_historic_time(historic_start: Optional[datetime]) -> Optional[str]:
    if historic_start is None:
        return None
    today = datetime.now().date()
    replay_start = datetime.combine(today, historic_start.time().replace(tzinfo=None))
    return replay_start.isoformat()


def _historical_race_from_definition(member_name: str, definition: dict) -> Optional[HistoricalRace]:
    if definition.get("marketType") != "WIN" or definition.get("status") != "CLOSED":
        return None
    if (definition.get("countryCode") or "").upper() not in COUNTRIES:
        return None

    runners_raw = definition.get("runners") or []
    settled = [
        runner for runner in runners_raw
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
                "name": name,
                "odds": round(float(runner.get("bsp")), 2),
            }
        )
    fill_missing_traps(priced)

    sorted_by_bsp = sorted(priced, key=lambda runner: runner["odds"])
    rank_by_id = {runner["id"]: idx + 1 for idx, runner in enumerate(sorted_by_bsp)}
    runners = [
        Greyhound(
            trap=runner["trap"],
            name=runner["name"],
            odds=runner["odds"],
            favourite_rank=rank_by_id[runner["id"]],
        )
        for runner in priced
    ]

    market_name = definition.get("name") or ""
    event_name = definition.get("eventName") or ""
    venue = definition.get("venue") or event_name or Path(member_name).stem
    country = (definition.get("countryCode") or "").upper()
    historic_start = _parse_start_time(definition)
    historic_start_iso = historic_start.isoformat() if historic_start else None
    market_id = Path(member_name).stem
    category = detect_category_from_market_name(market_name, event_name)

    return HistoricalRace(
        market_id=market_id,
        market_name=market_name,
        event_name=event_name,
        venue=f"{venue} ({country})" if country else venue,
        runners=runners,
        winning_trap=trap_from_runner_name(winner.get("name") or "") or int(winner.get("sortPriority") or 0),
        category=category,
        historic_start_time=historic_start_iso,
        replay_start_time=_today_with_historic_time(historic_start),
        commission_rate=float(definition.get("marketBaseRate") or 5.0) / 100.0,
    )


def _load_days(path: Path) -> Dict[str, List[HistoricalRace]]:
    days: Dict[str, List[HistoricalRace]] = {}
    with tarfile.open(path, "r") as tar:
        for member in tar:
            filename = Path(member.name).name
            if not member.isfile() or not filename.startswith("1.") or not filename.endswith(".bz2"):
                continue
            objects = list(_iter_json_lines(tar, member))
            definition = _latest_definition(objects)
            if not definition:
                continue
            race = _historical_race_from_definition(member.name, definition)
            if not race or not race.historic_start_time:
                continue
            day_key = race.historic_start_time[:10]
            days.setdefault(day_key, []).append(race)

    for races in days.values():
        races.sort(key=lambda race: race.historic_start_time or "")
    return {day: races for day, races in days.items() if races}


def _ensure_loaded() -> Dict[str, List[HistoricalRace]]:
    global _loaded_archive, _days_by_key
    path = _archive_path()
    if not path:
        return {}
    if _loaded_archive == path and _days_by_key:
        return _days_by_key
    try:
        _days_by_key = _load_days(path)
        _loaded_archive = path
        logger.info("Loaded %s historical replay days from %s", len(_days_by_key), path)
    except Exception:
        logger.exception("Could not load historical replay archive %s", path)
        _days_by_key = {}
        _loaded_archive = path
    return _days_by_key


def historical_replay_available() -> bool:
    return bool(_ensure_loaded())


def next_historical_replay_race(session: Session) -> Optional[HistoricalRace]:
    days = _ensure_loaded()
    if not days:
        return None

    day_keys = sorted(days)
    if session.historical_replay_day not in days:
        session.historical_replay_day = random.choice(day_keys)
        session.historical_replay_cursor = 0

    races = days.get(session.historical_replay_day or "") or []
    if session.historical_replay_cursor >= len(races):
        current_day = session.historical_replay_day
        choices = [day for day in day_keys if day != current_day] or day_keys
        session.historical_replay_day = random.choice(choices)
        session.historical_replay_cursor = 0
        races = days.get(session.historical_replay_day or "") or []

    if not races:
        return None

    race = races[session.historical_replay_cursor]
    session.historical_replay_cursor += 1
    return replace(
        race,
        replay_start_time=_today_with_historic_time(_parse_iso_datetime(race.historic_start_time)),
    )
