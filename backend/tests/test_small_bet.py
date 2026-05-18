"""Unit tests for the Betfair small-bet ("parking") technique.

We cannot hit Betfair from the preview pod (GEO_BLOCKED), but we CAN exercise
the orchestration logic of `place_small_lay_bet` by monkey-patching `_rpc`.

The test confirms:
  • All 3 RPC calls fire in order (placeOrders → cancelOrders → replaceOrders).
  • cancelOrders is called with the correct sizeReduction.
  • replaceOrders is called with the realistic target_price.
  • Failures at each step trigger clean-up of the parked order.
  • Input-validation guards reject illegal target_size / target_price values.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from betfair_client import BetfairClient, BetfairError  # noqa: E402


def _make_client_with_rpc(side_effects):
    client = BetfairClient()
    client._rpc = AsyncMock(side_effect=side_effects)
    return client


# ---- Happy path -----------------------------------------------------------

class TestHappyPath:
    def test_three_step_orchestration(self):
        place_resp = {
            "status": "SUCCESS",
            "instructionReports": [{"status": "SUCCESS", "betId": "BET123"}],
        }
        cancel_resp = {"status": "SUCCESS"}
        replace_resp = {
            "status": "SUCCESS",
            "instructionReports": [{
                "placeInstructionReport": {"betId": "BET456"},
            }],
        }
        client = _make_client_with_rpc([place_resp, cancel_resp, replace_resp])

        result = asyncio.run(client.place_small_lay_bet(
            market_id="1.234", selection_id=99,
            target_price=2.5, target_size=0.05,
            customer_order_ref="test-ref",
        ))

        assert client._rpc.await_count == 3
        methods = [call.args[0] for call in client._rpc.call_args_list]
        assert methods == ["placeOrders", "cancelOrders", "replaceOrders"]

        # placeOrders should park £2 at price 1000
        place_params = client._rpc.call_args_list[0].args[1]
        instr = place_params["instructions"][0]
        assert instr["side"] == "LAY"
        assert instr["limitOrder"]["price"] == 1000.0
        assert instr["limitOrder"]["size"] == 2.00
        assert instr["customerOrderRef"].startswith("test-ref")

        # cancelOrders should size-reduce by exactly (2 - 0.05) = 1.95
        cancel_params = client._rpc.call_args_list[1].args[1]
        cinstr = cancel_params["instructions"][0]
        assert cinstr["betId"] == "BET123"
        assert cinstr["sizeReduction"] == 1.95

        # replaceOrders should set the realistic target_price (snapped to tick)
        replace_params = client._rpc.call_args_list[2].args[1]
        rinstr = replace_params["instructions"][0]
        assert rinstr["betId"] == "BET123"
        # _snap_to_tick rounds up for LAY safety — 2.50 in the 2-3 band (step 0.02) snaps up to 2.52
        assert rinstr["newPrice"] == 2.52

        assert result["final_bet_id"] == "BET456"
        assert result["matched_size"] == 0.05
        assert result["matched_at_price"] == 2.52

    def test_price_snaps_to_betfair_tick(self):
        """target_price=2.51 must snap to a valid Betfair tick (2.52 inside 2-3 range)."""
        client = _make_client_with_rpc([
            {"status": "SUCCESS", "instructionReports": [{"status": "SUCCESS", "betId": "B"}]},
            {"status": "SUCCESS"},
            {"status": "SUCCESS", "instructionReports": [{"placeInstructionReport": {"betId": "B"}}]},
        ])
        asyncio.run(client.place_small_lay_bet("1.1", 1, target_price=2.51, target_size=0.05))
        rinstr = client._rpc.call_args_list[2].args[1]["instructions"][0]
        # _snap_to_tick rounds to nearest valid Betfair tick; 2.51 is not valid (2-3 step = 0.02)
        assert rinstr["newPrice"] in (2.50, 2.52)


# ---- Input-validation guards ---------------------------------------------

class TestInputGuards:
    @pytest.mark.parametrize("size", [-0.01, 0.0, 0.005])
    def test_rejects_microscopic_size(self, size):
        client = _make_client_with_rpc([])
        with pytest.raises(BetfairError, match="target_size|Target size"):
            asyncio.run(client.place_small_lay_bet("1.1", 1, target_price=2.0, target_size=size))
        assert client._rpc.await_count == 0  # didn't even call Betfair

    @pytest.mark.parametrize("size", [1.0, 1.5, 99.0])
    def test_rejects_oversized(self, size):
        client = _make_client_with_rpc([])
        with pytest.raises(BetfairError, match="place_lay_bet"):
            asyncio.run(client.place_small_lay_bet("1.1", 1, target_price=2.0, target_size=size))

    def test_rejects_invalid_price(self):
        client = _make_client_with_rpc([])
        with pytest.raises(BetfairError, match="Target price"):
            asyncio.run(client.place_small_lay_bet("1.1", 1, target_price=1.0, target_size=0.05))


# ---- Failure paths trigger park clean-up ---------------------------------

class TestCleanUpOnFailure:
    def test_park_failure_no_cleanup_needed(self):
        client = _make_client_with_rpc([
            {"status": "FAILURE", "errorCode": "INSUFFICIENT_FUNDS",
             "instructionReports": [{"status": "FAILURE"}]},
        ])
        with pytest.raises(BetfairError, match="park failed"):
            asyncio.run(client.place_small_lay_bet("1.1", 1, target_price=2.0, target_size=0.05))
        assert client._rpc.await_count == 1  # only the park attempt

    def test_size_reduce_failure_triggers_cancel(self):
        client = _make_client_with_rpc([
            {"status": "SUCCESS", "instructionReports": [{"status": "SUCCESS", "betId": "B1"}]},
            {"status": "FAILURE", "errorCode": "BET_TAKEN_OR_LAPSED"},
            {"status": "SUCCESS"},  # the clean-up cancel
        ])
        with pytest.raises(BetfairError, match="size-reduce failed"):
            asyncio.run(client.place_small_lay_bet("1.1", 1, target_price=2.0, target_size=0.05))
        assert client._rpc.await_count == 3
        # Last RPC must be a full cancel of the parked order
        last = client._rpc.call_args_list[-1]
        assert last.args[0] == "cancelOrders"
        assert last.args[1]["instructions"][0]["betId"] == "B1"
        assert "sizeReduction" not in last.args[1]["instructions"][0]

    def test_replace_failure_triggers_cancel(self):
        client = _make_client_with_rpc([
            {"status": "SUCCESS", "instructionReports": [{"status": "SUCCESS", "betId": "B1"}]},
            {"status": "SUCCESS"},
            {"status": "FAILURE", "errorCode": "INVALID_PRICE"},
            {"status": "SUCCESS"},  # the clean-up cancel
        ])
        with pytest.raises(BetfairError, match="price-replace failed"):
            asyncio.run(client.place_small_lay_bet("1.1", 1, target_price=2.0, target_size=0.05))
        assert client._rpc.await_count == 4
        last = client._rpc.call_args_list[-1]
        assert last.args[0] == "cancelOrders"
