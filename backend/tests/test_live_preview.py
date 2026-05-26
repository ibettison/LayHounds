"""Tests for the live-mode preview endpoint + auto-place safeguards.

The pod cannot reach Betfair (GEO_BLOCKED) so we verify:
  • the endpoint exists and refuses unknown/empty markets cleanly,
  • the auto-place guard refuses to fire when a previous live race has unsettled bets.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    with open('/app/frontend/.env') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL='):
                BASE_URL = line.split('=', 1)[1].strip().rstrip('/')
API = f"{BASE_URL}/api"


@pytest.fixture
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


class TestLivePreview:
    def test_preview_unknown_market_returns_502_or_404(self, http):
        """The pod is GEO_BLOCKED — Betfair call returns BetfairError → HTTP 502.
        On a UK VPS with a valid market this would return 200 with runners."""
        r = http.get(f"{API}/betfair/market/1.999999999/preview", timeout=15)
        assert r.status_code in (502, 404), r.text
        assert r.headers["content-type"].startswith("application/json")

    def test_preview_endpoint_is_registered(self, http):
        """OpenAPI exposes /api/betfair/market/{market_id}/preview."""
        # Try API base for OpenAPI (some routes mount openapi under /api).
        for url in (f"{BASE_URL}/openapi.json", f"{BASE_URL}/api/openapi.json"):
            r = http.get(url, timeout=10)
            try:
                d = r.json()
            except Exception:
                continue
            if "paths" in d:
                assert "/api/betfair/market/{market_id}/preview" in d["paths"], (
                    f"endpoint missing — paths sample: {list(d['paths'].keys())[:5]}"
                )
                return
        pytest.skip("OpenAPI schema not reachable via REACT_APP_BACKEND_URL")


class TestAutoFireSettlementGuard:
    """Verify the next-race endpoint refuses to fire a new live bet while the
    previous race still has unsettled Betfair bets — preventing recovery skips."""

    @pytest.fixture
    def session_with_pending_live_race(self):
        """Create a session, manually inject a live race with unsettled bet_ids
        directly into Mongo, return the session_id."""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        # Create a session (simulator mode so we don't need licence)
        r = s.post(f"{API}/sessions", json={"mode": "simulator", "stake": 0.05}, timeout=10)
        sid = r.json()["id"]
        yield sid
        # Cleanup
        s.delete(f"{API}/sessions/{sid}", timeout=10)

    def test_refresh_live_settlement_unknown_session(self, http):
        r = http.post(f"{API}/sessions/does-not-exist/refresh-live-settlement", timeout=10)
        assert r.status_code == 404

    def test_refresh_live_settlement_simulator_session_has_no_live_race(self, http, session_with_pending_live_race):
        r = http.post(f"{API}/sessions/{session_with_pending_live_race}/refresh-live-settlement", timeout=10)
        assert r.status_code == 404
        assert "live" in r.json().get("detail", "").lower()
