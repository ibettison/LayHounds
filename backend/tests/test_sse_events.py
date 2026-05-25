"""SSE (Server-Sent Events) endpoint tests for session real-time feedback.

Covers:
  - GET /api/sessions/{id}/events: text/event-stream + 'ready' frame
  - POST /api/sessions/{id}/next-race emits race_resulted + bank_updated
  - 404 on unknown session
  - POST /api/sessions/{id}/refresh-live-settlement: 404 when no live race
  - Disconnect mid-stream does not crash the backend
"""
from __future__ import annotations

import json
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    with open("/app/frontend/.env") as _f:
        for _line in _f:
            if _line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = _line.split("=", 1)[1].strip()
                break
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def session_id():
    """Create a fresh simulator session and return its id."""
    payload = {
        "mode": "simulator",
        "config": {
            "starting_bank": 200.0,
            "min_odds": 2.0,
            "max_odds": 6.0,
            "max_races": 50,
        },
    }
    r = requests.post(f"{API}/sessions", json=payload, timeout=10)
    assert r.status_code == 200, f"Failed to create session: {r.status_code} {r.text}"
    data = r.json()
    assert "id" in data
    return data["id"]


class TestSSEEndpoint:
    """Validates the /sessions/{id}/events stream itself."""

    def test_events_returns_event_stream_content_type(self, session_id):
        # Stream with short timeout — we only need headers + first 'ready' frame.
        with requests.get(
            f"{API}/sessions/{session_id}/events",
            stream=True,
            timeout=5,
        ) as r:
            assert r.status_code == 200
            ctype = r.headers.get("content-type", "")
            assert "text/event-stream" in ctype, f"Wrong content-type: {ctype}"
            # Read the first chunk — should contain the 'ready' event.
            first = b""
            for chunk in r.iter_content(chunk_size=512):
                first += chunk
                if b"\n\n" in first:
                    break
                if len(first) > 4096:
                    break
            text = first.decode("utf-8", errors="ignore")
            assert "event: ready" in text, f"Missing ready frame: {text!r}"
            assert "session_id" in text
            assert session_id in text

    def test_events_returns_404_for_unknown_session(self):
        # NOTE: this is a streaming endpoint, but FastAPI still raises 404
        # before opening the stream when the session doesn't exist.
        r = requests.get(
            f"{API}/sessions/00000000-0000-0000-0000-000000000000/events",
            stream=True,
            timeout=5,
        )
        assert r.status_code == 404
        r.close()

    def test_client_disconnect_does_not_break_backend(self, session_id):
        """Open + immediately close the SSE stream, then verify backend still serves."""
        with requests.get(
            f"{API}/sessions/{session_id}/events",
            stream=True,
            timeout=3,
        ) as r:
            assert r.status_code == 200
            # Read one chunk then bail.
            for _ in r.iter_content(chunk_size=256):
                break
        # Sanity: backend still responsive.
        r2 = requests.get(f"{API}/sessions/{session_id}", timeout=5)
        assert r2.status_code == 200


class TestNextRaceEmitsSSE:
    """Run a simulator race and verify SSE events fire over the stream."""

    def test_next_race_emits_race_resulted_and_bank_updated(self, session_id):
        """Open stream in a thread-style loop, trigger next-race, collect events."""
        import threading

        collected: list[dict] = []
        stop = threading.Event()

        def reader():
            try:
                with requests.get(
                    f"{API}/sessions/{session_id}/events",
                    stream=True,
                    timeout=15,
                ) as r:
                    buf = b""
                    for chunk in r.iter_content(chunk_size=256):
                        if stop.is_set():
                            break
                        if not chunk:
                            continue
                        buf += chunk
                        # SSE frames separated by \n\n
                        while b"\n\n" in buf:
                            frame, buf = buf.split(b"\n\n", 1)
                            ev_name = None
                            data_str = None
                            for line in frame.decode("utf-8", errors="ignore").splitlines():
                                if line.startswith("event:"):
                                    ev_name = line.split(":", 1)[1].strip()
                                elif line.startswith("data:"):
                                    data_str = line.split(":", 1)[1].strip()
                            collected.append({"event": ev_name, "data": data_str})
                            if ev_name in ("race_resulted", "bank_updated"):
                                # Got what we need; allow loop to exit.
                                pass
            except Exception:
                pass

        t = threading.Thread(target=reader, daemon=True)
        t.start()
        # Give the reader a moment to connect + receive 'ready'.
        time.sleep(1.0)

        # Trigger a simulator race.
        r = requests.post(f"{API}/sessions/{session_id}/next-race", timeout=15)
        assert r.status_code == 200, f"next-race failed: {r.status_code} {r.text}"

        # Allow SSE to deliver events.
        time.sleep(2.0)
        stop.set()
        t.join(timeout=3)

        event_names = [c["event"] for c in collected]
        assert "ready" in event_names, f"No ready frame received. Got: {event_names}"
        assert "race_resulted" in event_names, f"No race_resulted event. Got: {event_names}"
        assert "bank_updated" in event_names, f"No bank_updated event. Got: {event_names}"

        # Validate race_resulted payload shape.
        rr = next(c for c in collected if c["event"] == "race_resulted")
        payload = json.loads(rr["data"])
        for field in ("race_num", "winning_trap", "winner_name", "bank_after"):
            assert field in payload, f"race_resulted missing field {field}: {payload}"


class TestRefreshLiveSettlement:
    """Manual settlement refresh endpoint — should 404 when no live races."""

    def test_404_when_no_live_races(self, session_id):
        r = requests.post(
            f"{API}/sessions/{session_id}/refresh-live-settlement",
            timeout=10,
        )
        # Simulator-only session has no live races → 404.
        assert r.status_code == 404
        body = r.json()
        assert "detail" in body
        assert "live" in body["detail"].lower()

    def test_404_for_unknown_session(self):
        r = requests.post(
            f"{API}/sessions/00000000-0000-0000-0000-000000000000/refresh-live-settlement",
            timeout=10,
        )
        assert r.status_code == 404


class TestBackendRegression:
    """Confirm core endpoints still return 200 and unchanged shapes."""

    def test_licence_status_200(self):
        r = requests.get(f"{API}/licence/status", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert "install_id" in d
        assert "has_key" in d

    def test_licence_diag_200(self):
        r = requests.get(f"{API}/licence/diag", timeout=10)
        assert r.status_code == 200

    def test_betfair_status_200(self):
        r = requests.get(f"{API}/betfair/status", timeout=10)
        assert r.status_code == 200
        d = r.json()
        # status payload should still have a "connected" or similar flag.
        assert isinstance(d, dict)

    def test_simulator_session_create_200(self):
        r = requests.post(
            f"{API}/sessions",
            json={"mode": "simulator", "config": {"starting_bank": 100.0}},
            timeout=10,
        )
        assert r.status_code == 200
        d = r.json()
        assert "id" in d and "bank" in d and "config" in d
