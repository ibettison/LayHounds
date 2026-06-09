"""Backend tests for new Betfair-integration endpoints (iteration 4).

These tests run against a GEO-blocked preview pod where Betfair is configured
but every Account/Betting API call returns BetfairError -> HTTP 502 with a
GEO_BLOCKED message. That is the *expected and correct* behaviour for these
tests; the user's UK VPS will return real funds data.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    with open('/app/frontend/.env') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL='):
                BASE_URL = line.split('=', 1)[1].strip().rstrip('/')
API = f"{BASE_URL}/api"


@pytest.fixture
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s

@pytest.fixture
def cleanup_sessions(client):
    created = []
    yield created
    for sid in created:
        try:
            client.delete(f"{API}/sessions/{sid}", timeout=10)
        except Exception:
            pass


# ---------- Betfair status (regression) ----------
def test_betfair_status_reports_geo_blocked(client):
    r = client.get(f"{API}/betfair/status", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["configured"] is True
    # In preview pod it will be GEO_BLOCKED. On UK VPS this would be logged_in=true.
    if not d["logged_in"]:
        assert "GEO_BLOCKED" in (d.get("reason") or "")


# ---------- NEW: GET /api/betfair/funds ----------
def test_betfair_funds_returns_502_geo_blocked(client):
    """In preview pod the Betfair Account API is unreachable -> 502 with helpful message."""
    r = client.get(f"{API}/betfair/funds", timeout=20)
    assert r.status_code == 502, f"Expected 502, got {r.status_code}: {r.text}"
    d = r.json()
    assert "detail" in d
    assert "GEO_BLOCKED" in d["detail"] or "Betfair" in d["detail"]


# ---------- NEW: POST /api/sessions/{id}/refresh-bank ----------
def test_refresh_bank_rejects_simulator_session(client, cleanup_sessions):
    """Simulator-mode sessions cannot be refreshed from Betfair — must be 400."""
    r = client.post(f"{API}/sessions", json={
        "num_favourites": 2, "max_races": 5, "stop_win": 1000, "stop_loss": 1000,
        "starting_bank": 100, "mode": "simulator",
    }, timeout=10)
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    cleanup_sessions.append(sid)

    rr = client.post(f"{API}/sessions/{sid}/refresh-bank", timeout=15)
    assert rr.status_code == 400, f"Expected 400, got {rr.status_code}: {rr.text}"
    detail = rr.json().get("detail", "")
    assert "live" in detail.lower(), detail


def test_refresh_bank_404_on_missing_session(client):
    r = client.post(f"{API}/sessions/nonexistent-id/refresh-bank", timeout=15)
    assert r.status_code == 404


# ---------- NEW: create_session with paper_live propagates Betfair 502 ----------
def test_create_paper_live_session_is_gated_or_surfaces_betfair_error(client, cleanup_sessions):
    """Paper-live is gated in public installs unless a licence is active.

    If the test environment already has an active licence, the Betfair call may
    be reached and return the preview pod's GEO_BLOCKED 502.
    """
    r = client.post(f"{API}/sessions", json={
        "num_favourites": 2, "max_races": 5, "stop_win": 1000, "stop_loss": 1000,
        "starting_bank": 100, "mode": "paper_live",
    }, timeout=20)
    assert r.status_code in (402, 502), f"Expected 402 or 502, got {r.status_code}: {r.text}"
    detail = r.json().get("detail", "")
    assert "licence" in detail.lower() or "Live Unlock" in detail or "Betfair" in detail or "GEO_BLOCKED" in detail


def test_create_live_session_requires_risk_acceptance_first(client):
    """Live mode without risk_accepted should be rejected with 400 BEFORE
    even attempting the Betfair fetch."""
    r = client.post(f"{API}/sessions", json={
        "num_favourites": 2, "max_races": 5, "stop_win": 1000, "stop_loss": 1000,
        "starting_bank": 100, "mode": "live", "risk_accepted": False,
    }, timeout=20)
    assert r.status_code == 400


def test_create_live_session_with_risk_returns_502_when_betfair_blocked(client):
    r = client.post(f"{API}/sessions", json={
        "num_favourites": 2, "max_races": 5, "stop_win": 1000, "stop_loss": 1000,
        "starting_bank": 100, "mode": "live", "risk_accepted": True,
    }, timeout=20)
    assert r.status_code in (402, 502), f"Expected 402 or 502, got {r.status_code}: {r.text}"


# ---------- Regression: simulator mode bypasses Betfair fetch entirely ----------
def test_create_simulator_session_uses_user_supplied_bank(client, cleanup_sessions):
    r = client.post(f"{API}/sessions", json={
        "num_favourites": 2, "max_races": 5, "stop_win": 1000, "stop_loss": 1000,
        "starting_bank": 77.77, "mode": "simulator",
    }, timeout=10)
    assert r.status_code == 200, r.text
    s = r.json()
    cleanup_sessions.append(s["id"])
    assert s["bank"] == 77.77
    assert s["config"]["starting_bank"] == 77.77
    assert s["config"]["mode"] == "simulator"
