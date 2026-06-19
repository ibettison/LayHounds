from __future__ import annotations

import bz2
import json
import logging
import os
import re
import tarfile
from dataclasses import dataclass
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional
from zoneinfo import ZoneInfo

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
    race_time: str
    runners: List[Greyhound]
    favourite_odds: float
    second_favourite_odds: float
    winning_trap: int
    result: int
    category: RaceCategory
    historic_start_time: Optional[str]
    replay_start_time: Optional[str]
    market_time_label: Optional[str]
    commission_rate: float


_loaded_archive: Optional[Path] = None
_loaded_replay_pack: Optional[Path] = None
_days_by_key: Dict[str, List[HistoricalRace]] = {}
_next_day_index = 0

BUNDLED_REPLAY_PACK = Path(__file__).resolve().parents[1] / "data" / "historical_replay_sample.json"


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


def _candidate_replay_packs() -> List[Path]:
    configured = os.environ.get("LAYHOUNDS_HISTORICAL_REPLAY_PACK", "").strip()
    candidates = []
    if configured:
        candidates.append(Path(configured))
    candidates.append(BUNDLED_REPLAY_PACK)
    return candidates


def _replay_pack_path() -> Optional[Path]:
    for candidate in _candidate_replay_packs():
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
                latest = dict(definition)
                if market_change.get("id"):
                    latest["_marketId"] = market_change.get("id")
                if market_change.get("marketStartTime") and not latest.get("marketStartTime"):
                    latest["marketStartTime"] = market_change.get("marketStartTime")
    return latest


def _parse_start_time(definition: dict) -> Optional[datetime]:
    raw = definition.get("marketTime") or definition.get("marketStartTime") or definition.get("openDate")
    if raw:
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            timezone_name = definition.get("timezone") or "Europe/London"
            if parsed.tzinfo is not None:
                return parsed.astimezone(ZoneInfo(timezone_name)).replace(tzinfo=None)
            return parsed
        except ValueError:
            pass
        except Exception:
            return parsed.replace(tzinfo=None) if "parsed" in locals() else None

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


def _historical_start_time(historic_start: Optional[datetime]) -> Optional[str]:
    if historic_start is None:
        return None
    return historic_start.isoformat()


def _time_label(historic_start: Optional[datetime]) -> Optional[str]:
    return historic_start.strftime("%H:%M") if historic_start else None


def race_to_replay_pack_dict(race: HistoricalRace) -> dict:
    return {
        "market_id": race.market_id,
        "market_name": race.market_name,
        "event_name": race.event_name,
        "venue": race.venue,
        "race_time": race.race_time,
        "runners": [runner.model_dump() for runner in race.runners],
        "favourite_odds": race.favourite_odds,
        "second_favourite_odds": race.second_favourite_odds,
        "winning_trap": race.winning_trap,
        "result": race.result,
        "category": race.category.model_dump(),
        "historic_start_time": race.historic_start_time,
        "replay_start_time": race.replay_start_time,
        "market_time_label": race.market_time_label,
        "commission_rate": race.commission_rate,
    }


def _race_from_replay_pack_dict(payload: dict) -> Optional[HistoricalRace]:
    try:
        historic_start = _parse_iso_datetime(payload.get("historic_start_time") or payload.get("race_time"))
        historic_start_iso = historic_start.isoformat() if historic_start else payload.get("race_time")
        if not historic_start_iso:
            return None
        return HistoricalRace(
            market_id=str(payload["market_id"]),
            market_name=str(payload.get("market_name") or ""),
            event_name=str(payload.get("event_name") or ""),
            venue=str(payload.get("venue") or ""),
            race_time=str(payload.get("race_time") or historic_start_iso),
            runners=[Greyhound(**runner) for runner in payload.get("runners") or []],
            favourite_odds=float(payload.get("favourite_odds") or 0.0),
            second_favourite_odds=float(payload.get("second_favourite_odds") or 0.0),
            winning_trap=int(payload.get("winning_trap") or payload.get("result") or 0),
            result=int(payload.get("result") or payload.get("winning_trap") or 0),
            category=RaceCategory(**(payload.get("category") or {})),
            historic_start_time=historic_start_iso,
            replay_start_time=_historical_start_time(historic_start),
            market_time_label=payload.get("market_time_label") or _time_label(historic_start),
            commission_rate=float(payload.get("commission_rate") or 0.05),
        )
    except Exception:
        logger.exception("Skipping invalid historical replay pack race: %s", payload.get("market_id"))
        return None


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
    if not historic_start_iso:
        return None
    market_id = str(definition.get("_marketId") or Path(member_name).stem)
    category = detect_category_from_market_name(market_name, event_name)
    favourite_odds = round(sorted_by_bsp[0]["odds"], 2)
    second_favourite_odds = round(sorted_by_bsp[1]["odds"], 2)
    winning_trap = trap_from_runner_name(winner.get("name") or "") or int(winner.get("sortPriority") or 0)

    return HistoricalRace(
        market_id=market_id,
        market_name=market_name,
        event_name=event_name,
        venue=f"{venue} ({country})" if country else venue,
        race_time=historic_start_iso,
        runners=runners,
        favourite_odds=favourite_odds,
        second_favourite_odds=second_favourite_odds,
        winning_trap=winning_trap,
        result=winning_trap,
        category=category,
        historic_start_time=historic_start_iso,
        replay_start_time=_historical_start_time(historic_start),
        market_time_label=_time_label(historic_start),
        commission_rate=float(definition.get("marketBaseRate") or 5.0) / 100.0,
    )


def _load_days(path: Path) -> Dict[str, List[HistoricalRace]]:
    days: Dict[str, List[HistoricalRace]] = {}
    loaded_count = 0
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
            logger.info(
                "Historical market loaded: market_id=%s race_time=%s",
                race.market_id,
                race.race_time,
            )
            day_key = race.race_time[:10]
            days.setdefault(day_key, []).append(race)
            loaded_count += 1

    for day_key, races in days.items():
        races.sort(key=lambda race: race.race_time)
        logger.info(
            "First 10 historical races after sorting for %s: %s",
            day_key,
            [
                {
                    "market_id": race.market_id,
                    "race_time": race.race_time,
                    "venue": race.venue,
                }
                for race in races[:10]
            ],
        )

    logger.info("Loaded %s historical markets across %s historical days", loaded_count, len(days))
    return {day: races for day, races in days.items() if races}


def _load_replay_pack_days(path: Path) -> Dict[str, List[HistoricalRace]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    raw_races = payload.get("races") or []
    days: Dict[str, List[HistoricalRace]] = {}
    loaded_count = 0
    for raw_race in raw_races:
        race = _race_from_replay_pack_dict(raw_race)
        if not race or not race.historic_start_time:
            continue
        logger.info(
            "Historical replay pack market loaded: market_id=%s race_time=%s",
            race.market_id,
            race.race_time,
        )
        days.setdefault(race.race_time[:10], []).append(race)
        loaded_count += 1

    for day_key, races in days.items():
        races.sort(key=lambda race: race.race_time)
        logger.info(
            "First 10 historical replay pack races after sorting for %s: %s",
            day_key,
            [
                {
                    "market_id": race.market_id,
                    "race_time": race.race_time,
                    "venue": race.venue,
                }
                for race in races[:10]
            ],
        )

    logger.info("Loaded %s bundled historical replay markets across %s days", loaded_count, len(days))
    return {day: races for day, races in days.items() if races}


def _ensure_loaded() -> Dict[str, List[HistoricalRace]]:
    global _loaded_archive, _loaded_replay_pack, _days_by_key, _next_day_index
    path = _archive_path()
    if path:
        if _loaded_archive == path and _days_by_key:
            return _days_by_key
        try:
            _days_by_key = _load_days(path)
            _loaded_archive = path
            _loaded_replay_pack = None
            _next_day_index = 0
            logger.info(
                "Loaded historical replay archive from %s with %s markets across %s days",
                path,
                sum(len(races) for races in _days_by_key.values()),
                len(_days_by_key),
            )
            return _days_by_key
        except Exception:
            logger.exception("Could not load historical replay archive %s", path)
            _days_by_key = {}
            _loaded_archive = path

    replay_pack = _replay_pack_path()
    if not replay_pack:
        return {}
    if _loaded_replay_pack == replay_pack and _days_by_key:
        return _days_by_key
    try:
        _days_by_key = _load_replay_pack_days(replay_pack)
        _loaded_archive = None
        _loaded_replay_pack = replay_pack
        _next_day_index = 0
        logger.info(
            "Loaded bundled historical replay pack from %s with %s markets across %s days",
            replay_pack,
            sum(len(races) for races in _days_by_key.values()),
            len(_days_by_key),
        )
    except Exception:
        logger.exception("Could not load bundled historical replay pack %s", replay_pack)
        _days_by_key = {}
        _loaded_replay_pack = replay_pack
    return _days_by_key


def historical_replay_available() -> bool:
    return bool(_ensure_loaded())


def historical_replay_summary() -> dict:
    days = _ensure_loaded()
    day_summaries = []
    for day_key in sorted(days):
        races = days[day_key]
        if not races:
            continue
        day_summaries.append(
            {
                "date": day_key,
                "race_count": len(races),
                "first_race_time": races[0].race_time,
                "last_race_time": races[-1].race_time,
            }
        )

    source = "none"
    source_name = None
    if _loaded_archive:
        source = "archive"
        source_name = _loaded_archive.name
    elif _loaded_replay_pack:
        source = "bundled_replay_pack"
        source_name = _loaded_replay_pack.name

    return {
        "available": bool(day_summaries),
        "source": source,
        "source_name": source_name,
        "countries": sorted(COUNTRIES),
        "day_count": len(day_summaries),
        "race_count": sum(day["race_count"] for day in day_summaries),
        "first_day": day_summaries[0] if day_summaries else None,
        "last_day": day_summaries[-1] if day_summaries else None,
        "days": day_summaries,
    }


def _select_next_day(day_keys: List[str], *, avoid_day: Optional[str] = None) -> str:
    global _next_day_index
    if not day_keys:
        return ""
    if len(day_keys) == 1:
        return day_keys[0]

    for _ in range(len(day_keys)):
        day = day_keys[_next_day_index % len(day_keys)]
        _next_day_index += 1
        if day != avoid_day:
            return day
    return day_keys[0]


def next_historical_replay_race(session: Session) -> Optional[HistoricalRace]:
    days = _ensure_loaded()
    if not days:
        return None

    day_keys = sorted(days)
    if session.historical_replay_day not in days:
        session.historical_replay_day = _select_next_day(day_keys)
        session.historical_replay_cursor = 0
        logger.info(
            "Historical replay selected day=%s for session=%s (%s races)",
            session.historical_replay_day,
            session.id[:8],
            len(days.get(session.historical_replay_day, [])),
        )

    races = days.get(session.historical_replay_day or "") or []
    if session.historical_replay_cursor >= len(races):
        previous_day = session.historical_replay_day
        session.historical_replay_day = _select_next_day(day_keys, avoid_day=previous_day)
        session.historical_replay_cursor = 0
        races = days.get(session.historical_replay_day or "") or []
        logger.info(
            "Historical replay moved from day=%s to day=%s for session=%s (%s races)",
            previous_day,
            session.historical_replay_day,
            session.id[:8],
            len(races),
        )

    if not races:
        return None

    race = races[session.historical_replay_cursor]
    logger.info(
        "Passing historical race into simulator: day=%s order=%s market_id=%s race_time=%s",
        session.historical_replay_day,
        session.historical_replay_cursor + 1,
        race.market_id,
        race.race_time,
    )
    session.historical_replay_cursor += 1
    return replace(
        race,
        replay_start_time=_historical_start_time(_parse_iso_datetime(race.historic_start_time)),
        market_time_label=_time_label(_parse_iso_datetime(race.historic_start_time)),
    )
