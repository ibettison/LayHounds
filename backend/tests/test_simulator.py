"""Backend tests for greyhound lay-betting simulator."""
import os
import pytest
import requests

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/') if os.environ.get('REACT_APP_BACKEND_URL') else None
# Read frontend env if not set
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


# ---------- Session CRUD ----------
def test_root(client):
    r = client.get(f"{API}/", timeout=10)
    assert r.status_code == 200
    assert "message" in r.json()


def test_create_session_recovery_chains(client, cleanup_sessions):
    payload = {"num_favourites": 2, "stop_win": 5, "stop_loss": 5, "max_races": 20, "starting_bank": 10}
    r = client.post(f"{API}/sessions", json=payload, timeout=10)
    assert r.status_code == 200
    s = r.json()
    cleanup_sessions.append(s["id"])
    assert s["config"]["num_favourites"] == 2
    assert set(s["recovery_chains"].keys()) == {"1", "2"}
    for k, v in s["recovery_chains"].items():
        assert v["level"] == 0
        assert v["pending_stake"] == 0.05
        assert v["busted"] is False
    assert s["bank"] == 10
    assert s["status"] == "active"


def test_create_session_4_favs(client, cleanup_sessions):
    r = client.post(f"{API}/sessions", json={"num_favourites": 4}, timeout=10)
    assert r.status_code == 200
    s = r.json()
    cleanup_sessions.append(s["id"])
    assert set(s["recovery_chains"].keys()) == {"1", "2", "3", "4"}


def test_list_get_delete(client, cleanup_sessions):
    r = client.post(f"{API}/sessions", json={"num_favourites": 1}, timeout=10)
    sid = r.json()["id"]
    cleanup_sessions.append(sid)

    rl = client.get(f"{API}/sessions", timeout=10)
    assert rl.status_code == 200
    assert any(x["id"] == sid for x in rl.json())

    rg = client.get(f"{API}/sessions/{sid}", timeout=10)
    assert rg.status_code == 200
    assert rg.json()["id"] == sid

    rd = client.delete(f"{API}/sessions/{sid}", timeout=10)
    assert rd.status_code == 200
    cleanup_sessions.remove(sid)

    rg2 = client.get(f"{API}/sessions/{sid}", timeout=10)
    assert rg2.status_code == 404


# ---------- Race generation ----------
def test_next_race_structure(client, cleanup_sessions):
    r = client.post(f"{API}/sessions", json={"num_favourites": 2, "max_races": 50, "stop_win": 1000, "stop_loss": 1000}, timeout=10)
    sid = r.json()["id"]
    cleanup_sessions.append(sid)

    r2 = client.post(f"{API}/sessions/{sid}/next-race", timeout=15)
    assert r2.status_code == 200
    s = r2.json()
    assert len(s["races"]) == 1
    race = s["races"][0]
    assert len(race["runners"]) == 6
    traps = sorted(r["trap"] for r in race["runners"])
    assert traps == [1, 2, 3, 4, 5, 6]
    # ranks unique 1..6 by ascending odds
    sorted_runners = sorted(race["runners"], key=lambda x: x["odds"])
    for idx, runner in enumerate(sorted_runners):
        assert runner["favourite_rank"] == idx + 1
    # Bets only on rank 1..2
    bets = race["bets"]
    assert len(bets) <= 2
    for b in bets:
        assert b["favourite_rank"] in (1, 2)
        # initial stake
        assert b["recovery_level"] == 0
        assert abs(b["stake"] - 0.05) < 1e-6
        # liability = stake*(odds-1)
        assert abs(b["liability"] - b["stake"] * (b["odds"] - 1)) < 0.01
        assert b["result"] in ("win", "loss")


def test_recovery_chain_transitions(client, cleanup_sessions):
    """Run many races and verify chain math after each."""
    r = client.post(f"{API}/sessions", json={"num_favourites": 2, "max_races": 100, "stop_win": 10000, "stop_loss": 10000, "starting_bank": 1000}, timeout=10)
    sid = r.json()["id"]
    cleanup_sessions.append(sid)

    prev_chains = {"1": {"level": 0, "pending_stake": 0.05, "busted": False},
                   "2": {"level": 0, "pending_stake": 0.05, "busted": False}}

    for _ in range(40):
        r2 = client.post(f"{API}/sessions/{sid}/next-race", timeout=15)
        if r2.status_code == 400:
            break
        assert r2.status_code == 200
        s = r2.json()
        race = s["races"][-1]

        for rank_str in ("1", "2"):
            rank = int(rank_str)
            bet = next((b for b in race["bets"] if b["favourite_rank"] == rank), None)
            new_chain = s["recovery_chains"][rank_str]
            prev = prev_chains[rank_str]

            if bet is None:
                # No bet this race — either the chain was already busted last race,
                # or the liability cap just busted it this race.
                assert prev["busted"] is True or new_chain["busted"] is True
                prev_chains[rank_str] = new_chain
                continue

            # bet stake should equal prev pending_stake
            assert abs(bet["stake"] - prev["pending_stake"]) < 1e-4
            assert bet["recovery_level"] == prev["level"]

            if bet["result"] == "win":
                # Lay won. With default commission_rate=0.05, pnl = stake * 0.95.
                expected_pnl = round(bet["stake"] * (1 - 0.05), 4)
                assert abs(bet["pnl"] - expected_pnl) < 1e-3
                assert new_chain["level"] == 0
                assert abs(new_chain["pending_stake"] - 0.05) < 1e-6
                assert new_chain["busted"] is False
            else:
                # loss
                assert abs(bet["pnl"] + bet["liability"]) < 1e-6
                if prev["level"] >= 3:
                    assert new_chain["busted"] is True
                else:
                    assert new_chain["level"] == prev["level"] + 1
                    expected = round(bet["liability"] + bet["stake"] + 0.05, 4)
                    assert abs(new_chain["pending_stake"] - expected) < 1e-3
            prev_chains[rank_str] = new_chain

        if s["status"] != "active":
            break


def test_stop_session(client, cleanup_sessions):
    r = client.post(f"{API}/sessions", json={"num_favourites": 1}, timeout=10)
    sid = r.json()["id"]
    cleanup_sessions.append(sid)
    rs = client.post(f"{API}/sessions/{sid}/stop", timeout=10)
    assert rs.status_code == 200
    assert rs.json()["status"] == "stopped_manual"
    # next-race should now 400
    r2 = client.post(f"{API}/sessions/{sid}/next-race", timeout=10)
    assert r2.status_code == 400


def test_max_races_stop(client, cleanup_sessions):
    r = client.post(f"{API}/sessions", json={"num_favourites": 1, "max_races": 2, "stop_win": 10000, "stop_loss": 10000, "starting_bank": 1000}, timeout=10)
    sid = r.json()["id"]
    cleanup_sessions.append(sid)
    # Run up to 30 races to allow overrun mode to resolve any active recovery chain
    for _ in range(30):
        rr = client.post(f"{API}/sessions/{sid}/next-race", timeout=15)
        if rr.status_code != 200:
            break
        s = rr.json()
        if s["status"] != "active":
            break
    assert s["races_played"] >= 2
    assert s["status"] == "stopped_max"
    r3 = client.post(f"{API}/sessions/{sid}/next-race", timeout=10)
    assert r3.status_code == 400


def test_404_unknown_session(client):
    assert client.get(f"{API}/sessions/nonexistent-id", timeout=10).status_code == 404
    assert client.delete(f"{API}/sessions/nonexistent-id", timeout=10).status_code == 404
    assert client.post(f"{API}/sessions/nonexistent-id/next-race", timeout=10).status_code == 404
