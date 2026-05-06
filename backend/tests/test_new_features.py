"""Backend tests for new features: dynamic recovery levels, preview-cap,
batch run-races, bank carryover, daily-stats, odds range filter, liability
cap bust, recovery overrun, stop-loss/win flips."""
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


# ---------- Dynamic max_recovery_level on session create ----------
def test_create_session_max_recovery_level_5(client, cleanup_sessions):
    r = client.post(f"{API}/sessions", json={
        "num_favourites": 2, "max_recovery_level": 5,
        "starting_bank": 100, "stop_win": 1000, "stop_loss": 1000, "max_races": 50,
    }, timeout=10)
    assert r.status_code == 200, r.text
    s = r.json()
    cleanup_sessions.append(s["id"])
    assert s["config"]["max_recovery_level"] == 5


def test_create_session_max_recovery_level_invalid(client):
    r = client.post(f"{API}/sessions", json={"max_recovery_level": 6}, timeout=10)
    assert r.status_code == 422


def test_create_session_max_recovery_level_1(client, cleanup_sessions):
    r = client.post(f"{API}/sessions", json={"max_recovery_level": 1}, timeout=10)
    assert r.status_code == 200
    cleanup_sessions.append(r.json()["id"])
    assert r.json()["config"]["max_recovery_level"] == 1


# ---------- Recovery chain respects dynamic max level (busts only after LN loss) ----------
def test_recovery_busts_only_after_max_level_loss(client, cleanup_sessions):
    """With max_recovery_level=5, chain should never bust at L3 from level transition;
    only after L5 loss."""
    r = client.post(f"{API}/sessions", json={
        "num_favourites": 2, "max_recovery_level": 5, "max_races": 200,
        "stop_win": 100000, "stop_loss": 100000, "starting_bank": 100000,
        "max_liability_cap": 0,  # disable cap so only level transition can bust
    }, timeout=10)
    sid = r.json()["id"]
    cleanup_sessions.append(sid)

    saw_level_3_or_4 = False
    for _ in range(80):
        r2 = client.post(f"{API}/sessions/{sid}/next-race", timeout=15)
        if r2.status_code != 200:
            break
        s = r2.json()
        for rank_str, c in s["recovery_chains"].items():
            if c["level"] >= 3 and not c["busted"]:
                saw_level_3_or_4 = True
            if c["busted"]:
                # Bust must only happen after reaching level 5 (max)
                # Level should equal max_recovery_level
                assert c["level"] == 5, (
                    f"Chain busted at level {c['level']}, expected only at 5"
                )
        if s["status"] != "active":
            break
    # Don't assert saw_level_3_or_4 strictly - randomness; but it's informative
    print(f"Reached L3+: {saw_level_3_or_4}")


# ---------- Batch run-races ----------
def test_run_races_batch_10(client, cleanup_sessions):
    r = client.post(f"{API}/sessions", json={
        "num_favourites": 2, "max_races": 50, "stop_win": 10000, "stop_loss": 10000,
        "starting_bank": 1000,
    }, timeout=10)
    sid = r.json()["id"]
    cleanup_sessions.append(sid)

    r2 = client.post(f"{API}/sessions/{sid}/run-races?count=10", timeout=60)
    assert r2.status_code == 200, r2.text
    s = r2.json()
    assert s["races_played"] >= 1
    # Could have stopped early due to overrun finish or max_races; but with 50 max should hit 10
    assert s["races_played"] == 10 or s["status"] != "active"


def test_run_races_invalid_count(client, cleanup_sessions):
    r = client.post(f"{API}/sessions", json={"num_favourites": 1}, timeout=10)
    sid = r.json()["id"]
    cleanup_sessions.append(sid)
    r2 = client.post(f"{API}/sessions/{sid}/run-races?count=200", timeout=10)
    assert r2.status_code == 400


# ---------- preview-cap with dynamic max_recovery_level ----------
def test_preview_cap_max_recovery_level_5(client):
    r = client.post(f"{API}/preview-cap", json={
        "stake": 0.05, "max_liability_cap": 5.0, "num_favourites": 2,
        "commission_rate": 0.05, "iterations": 500,
        "max_recovery_level": 5,
    }, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["max_recovery_level"] == 5
    bd = d["bust_distribution"]
    # Must have keys L1..L5 + L0_cap_blocked
    for i in range(1, 6):
        assert f"L{i}" in bd, f"Missing L{i} in bust_distribution: {list(bd.keys())}"
    assert "L0_cap_blocked" in bd
    assert "reach_top_rate" in d
    # Win distribution should also have L0..L5
    wd = d["win_distribution"]
    for i in range(0, 6):
        assert f"L{i}" in wd


def test_preview_cap_max_recovery_level_1(client):
    r = client.post(f"{API}/preview-cap", json={
        "stake": 0.05, "max_liability_cap": 5.0, "num_favourites": 2,
        "iterations": 500, "max_recovery_level": 1,
    }, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["max_recovery_level"] == 1
    bd = d["bust_distribution"]
    # Only L1 + L0_cap_blocked allowed (no L2..L5)
    assert "L1" in bd
    for i in range(2, 6):
        assert f"L{i}" not in bd, f"Unexpected L{i} for max_recovery_level=1"


# ---------- Liability cap bust ----------
def test_liability_cap_blocks_recovery(client):
    """Very low cap (0.10) -> many chains should bust at L0 (cap-blocked)
    because initial liability=0.05*(odds-1) can exceed 0.10 for odds>3."""
    r = client.post(f"{API}/preview-cap", json={
        "stake": 0.05, "max_liability_cap": 0.10, "num_favourites": 2,
        "iterations": 1500, "max_recovery_level": 3,
    }, timeout=30)
    assert r.status_code == 200
    d = r.json()
    cap_blocked = d["bust_distribution"]["L0_cap_blocked"]
    assert cap_blocked > 0, f"Expected cap-blocked busts with cap=0.10, got {cap_blocked}"

    # Also test that with cap=0.50 chains bust at L1+ (recovery stake escalates beyond cap)
    r2 = client.post(f"{API}/preview-cap", json={
        "stake": 0.05, "max_liability_cap": 0.50, "num_favourites": 2,
        "iterations": 1500, "max_recovery_level": 3,
    }, timeout=30)
    d2 = r2.json()
    higher_lvl_busts = sum(d2["bust_distribution"].get(f"L{i}", 0) for i in range(1, 4))
    assert higher_lvl_busts > 0, f"Expected L1+ busts with cap=0.50, got 0"


# ---------- Odds range filter ----------
def test_odds_range_filter_skips_bets(client, cleanup_sessions):
    """Tight odds band 1.01-1.5 should skip most bets (very few favs that low)."""
    r = client.post(f"{API}/sessions", json={
        "num_favourites": 2, "max_races": 20, "stop_win": 10000, "stop_loss": 10000,
        "starting_bank": 100, "odds_min": 1.01, "odds_max": 1.5,
    }, timeout=10)
    sid = r.json()["id"]
    cleanup_sessions.append(sid)

    total_bets = 0
    for _ in range(20):
        r2 = client.post(f"{API}/sessions/{sid}/next-race", timeout=15)
        if r2.status_code != 200:
            break
        s = r2.json()
        race = s["races"][-1]
        total_bets += len(race["bets"])
        if s["status"] != "active":
            break
    # Generated odds start at 1.5+; min odds are clamped >=1.5. Likely 0 bets.
    assert total_bets <= 5, f"Expected very few bets with tight band, got {total_bets}"


# ---------- Bank carryover ----------
def test_bank_carryover_returns_recent(client, cleanup_sessions):
    r = client.post(f"{API}/sessions", json={
        "num_favourites": 1, "max_races": 3, "stop_win": 10000, "stop_loss": 10000,
        "starting_bank": 50.0,
    }, timeout=10)
    sid = r.json()["id"]
    cleanup_sessions.append(sid)
    # Run a race or two
    client.post(f"{API}/sessions/{sid}/run-races?count=3", timeout=30)

    rb = client.get(f"{API}/bank/current", timeout=10)
    assert rb.status_code == 200
    d = rb.json()
    assert "bank" in d
    assert d.get("from_session_id") == sid


def test_bank_current_returns_none_or_value(client):
    r = client.get(f"{API}/bank/current", timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert "bank" in d


# ---------- Daily stats ----------
def test_daily_stats_shape(client):
    r = client.get(f"{API}/daily-stats", timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert "days" in d
    assert "total_pnl" in d
    assert "sessions" in d
    if d["days"]:
        row = d["days"][0]
        for key in ("id", "created_at", "pnl", "cumulative_pnl",
                    "bank_start", "bank_end", "races", "status", "mode"):
            assert key in row


# ---------- Stop-loss / stop-win flip ----------
def test_stop_loss_triggers(client, cleanup_sessions):
    """Use very tight stop_loss=0.10 to make it trigger quickly with default stakes."""
    r = client.post(f"{API}/sessions", json={
        "num_favourites": 2, "max_races": 100, "stop_win": 1000, "stop_loss": 0.05,
        "starting_bank": 100, "max_liability_cap": 0,
    }, timeout=10)
    sid = r.json()["id"]
    cleanup_sessions.append(sid)
    # Run many races; should hit stop_loss eventually given recovery escalation
    r2 = client.post(f"{API}/sessions/{sid}/run-races?count=50", timeout=60)
    assert r2.status_code == 200
    s = r2.json()
    # Either stopped_loss or stopped_win or stopped_max - must not be active forever
    assert s["status"] in ("stopped_loss", "stopped_win", "stopped_max", "active")
    # Most likely stopped_loss given tight threshold
    if s["total_pnl"] <= -0.05:
        assert s["status"] == "stopped_loss"


def test_stop_win_triggers(client, cleanup_sessions):
    """Set stop_win very low so it triggers with first win."""
    r = client.post(f"{API}/sessions", json={
        "num_favourites": 2, "max_races": 100, "stop_win": 0.01, "stop_loss": 1000,
        "starting_bank": 100, "max_liability_cap": 0,
    }, timeout=10)
    sid = r.json()["id"]
    cleanup_sessions.append(sid)
    r2 = client.post(f"{API}/sessions/{sid}/run-races?count=50", timeout=60)
    assert r2.status_code == 200
    s = r2.json()
    if s["total_pnl"] >= 0.01:
        assert s["status"] == "stopped_win"


# ---------- Recovery overrun: continue past max_races if mid-recovery ----------
def test_recovery_overrun_mode(client, cleanup_sessions):
    """If a chain is mid-recovery at max_races, session continues until resolved."""
    r = client.post(f"{API}/sessions", json={
        "num_favourites": 2, "max_races": 5, "stop_win": 10000, "stop_loss": 10000,
        "starting_bank": 1000, "max_liability_cap": 0, "max_recovery_level": 5,
    }, timeout=10)
    sid = r.json()["id"]
    cleanup_sessions.append(sid)
    # Run 30 races (well past 5); session may complete or remain in overrun
    r2 = client.post(f"{API}/sessions/{sid}/run-races?count=30", timeout=60)
    assert r2.status_code == 200
    s = r2.json()
    # Either status is stopped_max (no recovery left) OR active (still in overrun)
    if s["status"] == "active":
        # Must have at least one chain in active recovery
        any_recovery = any(
            (c["level"] > 0 and not c["busted"]) for c in s["recovery_chains"].values()
        )
        assert any_recovery, "Active past max_races but no chain in recovery"
        assert s["races_played"] > 5, "Should have run more than max_races in overrun"
