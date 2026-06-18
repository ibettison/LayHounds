from __future__ import annotations

import bz2
import io
import json
import tarfile
from datetime import datetime

from models import Session, SessionConfig
from services import historical_replay
from services.historical_replay import next_historical_replay_race


def _write_market_archive(path, definition):
    payload = json.dumps({"mc": [{"marketDefinition": definition}]}) + "\n"
    data = bz2.compress(payload.encode("utf-8"))
    info = tarfile.TarInfo("BASIC/2026/Jan/1/123/1.234567890.bz2")
    info.size = len(data)
    with tarfile.open(path, "w") as tar:
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
    assert race.replay_start_time[:10] == datetime.now().date().isoformat()
    assert "19:24:00" in race.replay_start_time
    assert session.historical_replay_day == "2026-01-01"
    assert session.historical_replay_cursor == 1
