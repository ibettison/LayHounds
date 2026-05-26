"""Unit tests for the Betfair price-ladder helpers (`_snap_to_tick`, `count_ticks`).

Verifies the slippage-tick computation against published Betfair ladder steps.
"""
from __future__ import annotations

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from betfair_client import BetfairClient  # noqa: E402


class TestSnapToTick:
    @pytest.mark.parametrize("inp,expected_ge", [
        (1.005, 1.01),  # clamp lower bound
        (2.51, 2.52),   # 2-3 band uses 0.02
        (4.13, 4.20),   # 4-6 band uses 0.10
        (10.7, 11.0),   # 10-20 band uses 0.50
    ])
    def test_snaps_up_for_lay_safety(self, inp, expected_ge):
        snapped = BetfairClient._snap_to_tick(inp)
        # We snap upward for LAYs — the snapped price must be >= the input
        assert snapped >= inp, f"snap({inp})={snapped} < input"
        # And it must equal the expected next tick
        assert snapped == expected_ge


class TestCountTicks:
    @pytest.mark.parametrize("a,b,expected", [
        # Within 2-3 band: step 0.02
        (2.50, 2.52, 1),    # +1 tick higher
        (2.50, 2.48, -1),   # 1 tick lower
        (2.50, 2.56, 3),    # +3 ticks
        (2.56, 2.50, -3),   # symmetry
        # Within 1.01-2.0 band: step 0.01
        (1.50, 1.53, 3),
        (1.99, 1.95, -4),
        # Across band boundaries (1.98 → 2.04 = 0.02 + 0.04 = 2 + 2 = 4 ticks)
        (1.98, 2.04, 4),
        # 3-4 band: step 0.05
        (3.10, 3.30, 4),
        # No movement
        (2.50, 2.50, 0),
        # 6-10 band: step 0.20
        (7.00, 7.60, 3),
    ])
    def test_signed_tick_count(self, a, b, expected):
        assert BetfairClient.count_ticks(a, b) == expected

    def test_zero_on_invalid_inputs(self):
        assert BetfairClient.count_ticks(None, 2.5) == 0
        assert BetfairClient.count_ticks(2.5, None) == 0
        assert BetfairClient.count_ticks(0, 2.5) == 0
        assert BetfairClient.count_ticks(-1, 2.5) == 0

    def test_cross_band_symmetric(self):
        """Crossing the 2.0 boundary should give the same magnitude in both directions."""
        forward = BetfairClient.count_ticks(1.96, 2.10)
        backward = BetfairClient.count_ticks(2.10, 1.96)
        assert forward == -backward
        # 1.96→2.00 (4 ticks) + 2.00→2.10 (5 ticks) = 9
        assert forward == 9
