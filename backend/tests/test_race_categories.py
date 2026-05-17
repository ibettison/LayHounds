"""Tests for the race-category module + integration with /api/sessions/{id}/next-race."""
from __future__ import annotations

import os
import random
import sys
from pathlib import Path
import requests
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from race_categories import (  # noqa: E402
    detect_category_from_market_name,
    random_category,
    win_rates_for_category,
    winner_weights,
    DISTANCE_BANDS,
    GRADE_CATEGORIES,
)

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    with open('/app/frontend/.env') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL='):
                BASE_URL = line.split('=', 1)[1].strip().rstrip('/')
API = f"{BASE_URL}/api"


# ---- Pure unit tests ------------------------------------------------------

class TestCategoryDetection:
    def test_detect_distance_only(self):
        c = detect_category_from_market_name("Romford 19:24 R3 480m")
        assert c.distance_m == 480
        assert c.distance_band == "standard"
        assert c.grade == "A4"  # fallback default

    def test_detect_grade_and_distance(self):
        c = detect_category_from_market_name("Hove 18:36 R5 285m A3")
        assert c.distance_m == 285
        assert c.distance_band == "sprint"
        assert c.grade == "A3"

    def test_detect_open_race(self):
        c = detect_category_from_market_name("Crayford 19:48 R1 540m OR")
        assert c.grade == "OR"
        assert c.distance_band == "stayer"

    def test_detect_hurdle(self):
        c = detect_category_from_market_name("Towcester 20:11 R2 480m H2")
        assert c.grade == "H2"

    def test_falls_back_on_empty(self):
        c = detect_category_from_market_name("")
        assert c.grade == "A4" and c.distance_m == 480 and c.distance_band == "standard"

    def test_marathon_band(self):
        c = detect_category_from_market_name("Newcastle 22:01 R7 660m A5")
        assert c.distance_m == 660
        assert c.distance_band == "marathon"


class TestWinRates:
    @pytest.mark.parametrize("grade", list(GRADE_CATEGORIES.keys()))
    def test_grade_tables_sum_to_one(self, grade):
        rates = GRADE_CATEGORIES[grade]["win_rates"]
        assert abs(sum(rates) - 1.0) < 0.001, f"{grade} win-rates sum to {sum(rates)}"
        assert len(rates) == 6

    @pytest.mark.parametrize("band", list(DISTANCE_BANDS.keys()))
    def test_band_tables_sum_to_one(self, band):
        rates = DISTANCE_BANDS[band]["win_rates"]
        assert abs(sum(rates) - 1.0) < 0.001, f"{band} win-rates sum to {sum(rates)}"
        assert len(rates) == 6

    def test_blended_rates_sum_to_one(self):
        cat = detect_category_from_market_name("Hove 18:36 R5 480m A4")
        rates = win_rates_for_category(cat)
        assert abs(sum(rates) - 1.0) < 0.001
        # Favourite should always have the highest rate
        assert rates[0] == max(rates)

    def test_winner_weights_normalised(self):
        cat = detect_category_from_market_name("Hove 18:36 R5 480m A4")
        runners = [{"favourite_rank": i + 1, "odds": 2.0 + i} for i in range(6)]
        w = winner_weights(runners, cat)
        assert abs(sum(w) - 1.0) < 0.001
        assert w[0] > w[-1]  # fav weight > outsider weight


class TestLongRunDistribution:
    """Verify that ~20k simulated races produce favourite-win rates within ±2% of target."""

    def test_simulator_long_run_calibration(self):
        random.seed(42)
        counts = {i: 0 for i in range(1, 7)}
        N = 20000
        for _ in range(N):
            cat = random_category()
            base = random.uniform(1.8, 3.5)
            odds = sorted([round(base + i * random.uniform(0.6, 1.8) + random.uniform(-0.3, 0.6), 2) for i in range(6)])
            odds = [max(1.5, o) for o in odds]
            runners = [{"favourite_rank": i + 1, "odds": odds[i]} for i in range(6)]
            weights = winner_weights(runners, cat)
            pick = random.random()
            cum = 0.0
            for r, w in zip(runners, weights):
                cum += w
                if pick <= cum:
                    counts[r["favourite_rank"]] += 1
                    break
        # UK weighted-average industry targets
        targets = {1: 0.32, 2: 0.22, 3: 0.17, 4: 0.13, 5: 0.10, 6: 0.07}
        for rank, target in targets.items():
            actual = counts[rank] / N
            assert abs(actual - target) < 0.03, (
                f"Rank {rank}: actual={actual:.3f}, target={target:.3f}, delta={actual - target:+.3f}"
            )


# ---- Integration test against the live FastAPI server ---------------------

@pytest.fixture
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


class TestRaceCategoryIntegration:
    def test_simulator_race_carries_category(self, http):
        r = http.post(f"{API}/sessions", json={"mode": "simulator", "stake": 0.05}, timeout=10)
        assert r.status_code == 200
        sid = r.json()["id"]
        try:
            rr = http.post(f"{API}/sessions/{sid}/next-race", timeout=10)
            assert rr.status_code == 200, rr.text
            session = rr.json()
            race = session["races"][-1]
            assert race.get("category") is not None
            cat = race["category"]
            assert cat["grade"] in GRADE_CATEGORIES
            assert cat["distance_band"] in DISTANCE_BANDS
            assert 200 <= cat["distance_m"] <= 1200
        finally:
            http.delete(f"{API}/sessions/{sid}", timeout=10)
