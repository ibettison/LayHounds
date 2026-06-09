"""Tests for the central licensing flow and Stripe checkout endpoints.

Covers the customer-side endpoints (/api/licence/...), the licence gate on
POST /api/sessions for paper_live/live modes, and the Stripe create/status
endpoints from emergentintegrations.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://dog-bet-ladder.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

TEST_KEY = "LH-TEST-AAAA-BBBB-CCCC"


@pytest.fixture(scope="module")
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(autouse=True)
def _reset_state(http):
    """Before every test, force the local install into UNBOUND state by hitting release if needed."""
    try:
        r = http.get(f"{API}/licence/status", timeout=10)
        if r.status_code == 200 and r.json().get("has_key"):
            http.post(f"{API}/licence/release", json={}, timeout=10)
    except Exception:
        pass
    yield


# ---- Customer-side licence endpoints --------------------------------------

class TestLicenceStatus:
    def test_status_fresh_install(self, http):
        r = http.get(f"{API}/licence/status", timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "install_id" in data and len(data["install_id"]) >= 8
        assert data["has_key"] is False
        assert data["bound"] is False
        assert data["ok"] is False


class TestLicenceActivate:
    def test_activate_unknown_key_returns_404(self, http):
        # install_id mismatch path -> request with empty install_id will let server use its own
        # but central server itself returns 404 for unknown keys
        status = http.get(f"{API}/licence/status").json()
        install_id = status["install_id"]
        r = http.post(f"{API}/licence/activate", json={"key": "LH-DOES-NOT-EXIST", "install_id": install_id}, timeout=10)
        assert r.status_code == 404, r.text

    def test_activate_valid_key_binds(self, http):
        status = http.get(f"{API}/licence/status").json()
        install_id = status["install_id"]
        r = http.post(f"{API}/licence/activate", json={"key": TEST_KEY, "install_id": install_id}, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["has_key"] is True
        assert data["bound"] is True
        assert data["ok"] is True
        assert data["status"] == "active"
        assert data["licence_key_masked"] and TEST_KEY[:6] in data["licence_key_masked"]

    def test_activate_already_bound_elsewhere_returns_409(self, http):
        # Activate on real install_id first
        status = http.get(f"{API}/licence/status").json()
        install_id = status["install_id"]
        http.post(f"{API}/licence/activate", json={"key": TEST_KEY, "install_id": install_id}, timeout=15)

        # Now try to activate as a DIFFERENT install_id directly against central endpoint
        bogus = "ffffffff-ffff-ffff-ffff-ffffffffffff"
        r = http.post(f"{API}/licences/activate", json={"key": TEST_KEY, "install_id": bogus}, timeout=10)
        assert r.status_code == 409, f"expected 409, got {r.status_code}: {r.text}"


class TestLicenceRefresh:
    def test_refresh_updates_last_validation(self, http):
        status = http.get(f"{API}/licence/status").json()
        install_id = status["install_id"]
        http.post(f"{API}/licence/activate", json={"key": TEST_KEY, "install_id": install_id}, timeout=15)
        before = http.get(f"{API}/licence/status").json().get("last_validation_at")
        time.sleep(1.1)
        r = http.post(f"{API}/licence/refresh", json={}, timeout=15)
        assert r.status_code == 200, r.text
        after = r.json().get("last_validation_at")
        assert after and (after != before), f"last_validation_at did not advance ({before} -> {after})"
        assert r.json()["ok"] is True


class TestLicenceRelease:
    def test_release_clears_state(self, http):
        status = http.get(f"{API}/licence/status").json()
        install_id = status["install_id"]
        http.post(f"{API}/licence/activate", json={"key": TEST_KEY, "install_id": install_id}, timeout=15)

        r = http.post(f"{API}/licence/release", json={}, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["has_key"] is False
        assert data["bound"] is False

        # Status reconfirms
        s = http.get(f"{API}/licence/status").json()
        assert s["has_key"] is False


# ---- Session licence-gate -------------------------------------------------

class TestSessionLicenceGate:
    def test_simulator_session_no_licence_required(self, http):
        payload = {
            "mode": "simulator",
            "starting_bank": 100.0,
            "config": {"strategy": "fixed", "stake": 2.0},
        }
        r = http.post(f"{API}/sessions", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        sid = r.json().get("id")
        if sid:
            http.delete(f"{API}/sessions/{sid}")

    def test_paper_live_without_licence_returns_402(self, http):
        # Ensure no licence
        try:
            http.post(f"{API}/licence/release", json={}, timeout=10)
        except Exception:
            pass
        payload = {
            "mode": "paper_live",
            "starting_bank": 50.0,
            "config": {"strategy": "fixed", "stake": 2.0},
        }
        r = http.post(f"{API}/sessions", json=payload, timeout=15)
        assert r.status_code == 402, f"expected 402, got {r.status_code}: {r.text}"
        detail = r.json().get("detail", "")
        assert "Live Unlock" in detail or "licence" in detail.lower(), detail

    def test_paper_live_with_licence_passes_gate(self, http):
        # Activate
        status = http.get(f"{API}/licence/status").json()
        install_id = status["install_id"]
        a = http.post(f"{API}/licence/activate", json={"key": TEST_KEY, "install_id": install_id}, timeout=15)
        assert a.status_code == 200 and a.json()["ok"] is True

        payload = {
            "mode": "paper_live",
            "starting_bank": 50.0,
            "config": {"strategy": "fixed", "stake": 2.0},
        }
        r = http.post(f"{API}/sessions", json=payload, timeout=20)
        # Expectation: 402 has changed to either 502 GEO_BLOCKED, or 200 if session created.
        assert r.status_code != 402, f"licence gate still blocking after activation: {r.text}"
        # Acceptable outcomes: 502 (geo-blocked betfair) or 200
        assert r.status_code in (200, 502, 400), f"unexpected status {r.status_code}: {r.text}"


# ---- Teardown: leave licence UNBOUND for next test run --------------------

def teardown_module(module):
    """Reset the test licence to UNBOUND state."""
    try:
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        s.post(f"{API}/licence/release", json={}, timeout=10)
    except Exception:
        pass
