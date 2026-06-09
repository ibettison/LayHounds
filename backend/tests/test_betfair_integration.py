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


# All paper_live + live session-creation paths now require an active licence
# (gate added in iter-5). Seed the test licence and bind it to this install
# for the duration of the module so the Betfair-error paths are still reachable.
@pytest.fixture(scope="module", autouse=True)
def _ensure_test_licence_active():
    import asyncio
    import os as _os
    from pathlib import Path
    from datetime import timedelta
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    from motor.motor_asyncio import AsyncIOMotorClient
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    try:
        from licence_server import Licence, _now  # noqa: E402
    except ImportError:
        pytest.skip("Private licence_server module is not installed in this public app build")

    async def setup():
        c = AsyncIOMotorClient(_os.environ['MONGO_URL'])
        db = c[_os.environ['DB_NAME']]
        await db.licences.delete_many({'licence_key': 'LH-TEST-AAAA-BBBB-CCCC'})
        lic = Licence(
            licence_key='LH-TEST-AAAA-BBBB-CCCC',
            email='test@layhounds.test',
            provider='manual',
            status='active',
            current_period_end=_now() + timedelta(days=30),
        )
        await db.licences.insert_one(lic.model_dump(mode='json'))
        c.close()
    asyncio.run(setup())
    # Activate via the running server so install_id binding is correct
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    s.post(f"{API}/licence/activate", json={"key": "LH-TEST-AAAA-BBBB-CCCC", "install_id": ""}, timeout=10)
    yield
    s.post(f"{API}/licence/release", timeout=10)


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
def test_create_paper_live_session_returns_502_when_betfair_blocked(client, cleanup_sessions):
    """In preview pod, paper_live session creation must surface the Betfair error
    (502) rather than silently creating a session with bank=0."""
    r = client.post(f"{API}/sessions", json={
        "num_favourites": 2, "max_races": 5, "stop_win": 1000, "stop_loss": 1000,
        "starting_bank": 100, "mode": "paper_live",
    }, timeout=20)
    assert r.status_code == 502, f"Expected 502, got {r.status_code}: {r.text}"
    detail = r.json().get("detail", "")
    assert "Betfair" in detail or "GEO_BLOCKED" in detail


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
    assert r.status_code == 502, f"Expected 502, got {r.status_code}: {r.text}"


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
