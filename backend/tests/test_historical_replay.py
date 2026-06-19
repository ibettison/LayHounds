from __future__ import annotations

import bz2
import io
import json
import tarfile
from models import Session, SessionConfig
from services import historical_replay
from services.historical_replay import next_historical_replay_race


def _write_market_archive(path, definition):
    _write_market_archive_many(path, [("BASIC/2026/Jan/1/123/1.234567890.bz2", definition)])


def _write_market_archive_many(path, definitions):
    with tarfile.open(path, "w") as tar:
        for member_name, definition in definitions:
            payload = json.dumps({"mc": [{"id": definition.get("marketId"), "marketDefinition": definition}]}) + "\n"
            data = bz2.compress(payload.encode("utf-8"))
            info = tarfile.TarInfo(member_name)
            info.size = len(data)
            tar.addfile(info, fileobj=io.BytesIO(data))


def test_historical_replay_uses_real_market_and_rewrites_date(monkeypatch, tmp_path):
    archive = tmp_path / "data.tar"
    _write_market_archive(
        archive,
        {
            "marketType": "WIN",
            "status": "CLOSED",
            "countryCode": "GB",
            "venue": "Romford",
            "name": "R3 400m A4",
            "eventName": "Romford 1st Jan",
            "marketTime": "2026-01-01T19:24:00.000Z",
            "marketBaseRate": 5.0,
            "runners": [
                {"status": "LOSER", "sortPriority": 1, "bsp": 3.5, "id": 1, "name": "1. Swift One"},
                {"status": "WINNER", "sortPriority": 2, "bsp": 2.2, "id": 2, "name": "2. Fast Two"},
                {"status": "LOSER", "sortPriority": 3, "bsp": 5.0, "id": 3, "name": "3. Honest Three"},
            ],
        },
    )
    monkeypatch.setenv("LAYHOUNDS_HISTORICAL_TAR", str(archive))
    historical_replay._loaded_archive = None
    historical_replay._days_by_key = {}
    historical_replay._next_day_index = 0

    session = Session(config=SessionConfig(mode="simulator"), bank=10)
    race = next_historical_replay_race(session)

    assert race is not None
    assert race.venue == "Romford (GB)"
    assert race.category.distance_m == 400
    assert race.category.grade == "A4"
    assert race.winning_trap == 2
    assert [(runner.trap, runner.name, runner.odds, runner.favourite_rank) for runner in race.runners] == [
        (1, "1. Swift One", 3.5, 2),
        (2, "2. Fast Two", 2.2, 1),
        (3, "3. Honest Three", 5.0, 3),
    ]
    assert race.replay_start_time is not None
    assert race.replay_start_time[:10] == "2026-01-01"
    assert "19:24:00" in race.replay_start_time
    assert race.market_time_label == "19:24"
    assert session.historical_replay_day == "2026-01-01"
    assert session.historical_replay_cursor == 1


def test_historical_replay_converts_market_time_to_track_timezone(monkeypatch, tmp_path):
    archive = tmp_path / "data.tar"
    _write_market_archive(
        archive,
        {
            "marketType": "WIN",
            "status": "CLOSED",
            "countryCode": "GB",
            "venue": "Towcester",
            "name": "A6 240m",
            "eventName": "Towcester 1st Jun",
            "marketTime": "2026-06-01T15:16:00.000Z",
            "timezone": "Europe/London",
            "marketBaseRate": 5.0,
            "runners": [
                {"status": "WINNER", "sortPriority": 1, "bsp": 2.5, "id": 1, "name": "1. Swift One"},
                {"status": "LOSER", "sortPriority": 2, "bsp": 3.2, "id": 2, "name": "2. Fast Two"},
            ],
        },
    )
    monkeypatch.setenv("LAYHOUNDS_HISTORICAL_TAR", str(archive))
    historical_replay._loaded_archive = None
    historical_replay._days_by_key = {}
    historical_replay._next_day_index = 0

    session = Session(config=SessionConfig(mode="simulator"), bank=10)
    race = next_historical_replay_race(session)

    assert race is not None
    assert race.replay_start_time is not None
    assert race.replay_start_time[:10] == "2026-06-01"
    assert "16:16:00" in race.replay_start_time
    assert race.market_time_label == "16:16"


def _definition(market_id, market_time, venue="Romford", winner=2):
    return {
        "marketId": market_id,
        "marketType": "WIN",
        "status": "CLOSED",
        "countryCode": "GB",
        "venue": venue,
        "name": "R3 400m A4",
        "eventName": f"{venue} 1st Jan",
        "marketTime": market_time,
        "marketBaseRate": 5.0,
        "runners": [
            {
                "status": "WINNER" if winner == 1 else "LOSER",
                "sortPriority": 1,
                "bsp": 3.5,
                "id": 1,
                "name": "1. Swift One",
            },
            {
                "status": "WINNER" if winner == 2 else "LOSER",
                "sortPriority": 2,
                "bsp": 2.2,
                "id": 2,
                "name": "2. Fast Two",
            },
            {
                "status": "WINNER" if winner == 3 else "LOSER",
                "sortPriority": 3,
                "bsp": 5.0,
                "id": 3,
                "name": "3. Honest Three",
            },
        ],
    }


def test_historical_replay_sorts_races_by_race_time_before_simulation(monkeypatch, tmp_path):
    archive = tmp_path / "data.tar"
    _write_market_archive_many(
        archive,
        [
            (
                "BASIC/2026/Jan/1/123/1.333333333.bz2",
                _definition("1.333333333", "2026-01-01T20:15:00.000Z", venue="Late"),
            ),
            (
                "BASIC/2026/Jan/1/123/1.111111111.bz2",
                _definition("1.111111111", "2026-01-01T18:05:00.000Z", venue="Early"),
            ),
            (
                "BASIC/2026/Jan/1/123/1.222222222.bz2",
                _definition("1.222222222", "2026-01-01T19:10:00.000Z", venue="Middle"),
            ),
        ],
    )
    monkeypatch.setenv("LAYHOUNDS_HISTORICAL_TAR", str(archive))
    historical_replay._loaded_archive = None
    historical_replay._days_by_key = {}
    historical_replay._next_day_index = 0

    session = Session(config=SessionConfig(mode="simulator"), bank=10)

    first = next_historical_replay_race(session)
    second = next_historical_replay_race(session)
    third = next_historical_replay_race(session)

    assert [first.market_id, second.market_id, third.market_id] == [
        "1.111111111",
        "1.222222222",
        "1.333333333",
    ]
    assert [first.race_time, second.race_time, third.race_time] == sorted(
        [first.race_time, second.race_time, third.race_time]
    )
    assert [first.venue, second.venue, third.venue] == ["Early (GB)", "Middle (GB)", "Late (GB)"]


def test_historical_replay_selects_different_days_for_new_sessions(monkeypatch, tmp_path):
    archive = tmp_path / "data.tar"
    _write_market_archive_many(
        archive,
        [
            (
                "BASIC/2026/Jan/1/123/1.111111111.bz2",
                _definition("1.111111111", "2026-01-01T10:05:00.000Z", venue="Day One"),
            ),
            (
                "BASIC/2026/Jan/2/123/1.222222222.bz2",
                _definition("1.222222222", "2026-01-02T10:05:00.000Z", venue="Day Two"),
            ),
        ],
    )
    monkeypatch.setenv("LAYHOUNDS_HISTORICAL_TAR", str(archive))
    historical_replay._loaded_archive = None
    historical_replay._days_by_key = {}
    historical_replay._next_day_index = 0

    first_session = Session(config=SessionConfig(mode="simulator"), bank=10)
    second_session = Session(config=SessionConfig(mode="simulator"), bank=10)

    first_race = next_historical_replay_race(first_session)
    second_race = next_historical_replay_race(second_session)

    assert first_race.market_id == "1.111111111"
    assert second_race.market_id == "1.222222222"
    assert first_session.historical_replay_day == "2026-01-01"
    assert second_session.historical_replay_day == "2026-01-02"
