"""Equity da subconta e slots lógicos — sem flatten."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BTC = Path(__file__).resolve().parent.parent / "btc_trading_agent"
if str(_BTC) not in sys.path:
    sys.path.insert(0, str(_BTC))

from position_reconstruction import compute_exposure_budget, infer_logical_slots


class TestComputeExposureBudget:
    def test_empty_account(self) -> None:
        budget = compute_exposure_budget(
            quote_balance=100.0, base_qty=0.0, price=65000.0, max_position_pct=0.15,
        )
        assert budget["equity"] == pytest.approx(100.0)
        assert budget["open_exposure"] == 0.0
        assert budget["max_total_exposure"] == pytest.approx(15.0)
        assert budget["remaining_exposure"] == pytest.approx(15.0)

    def test_uses_full_inventory_not_one_slot(self) -> None:
        """Dois lotes de ~$15 + $15 USDT: cap sobre $45, não sobre um slot."""
        budget = compute_exposure_budget(
            quote_balance=15.71,
            base_qty=0.000458,
            price=63764.0,
            max_position_pct=0.15,
        )
        assert budget["equity"] == pytest.approx(15.71 + 0.000458 * 63764.0)
        assert budget["open_exposure"] == pytest.approx(0.000458 * 63764.0)
        assert budget["open_exposure"] > budget["max_total_exposure"]
        assert budget["remaining_exposure"] == 0.0

    def test_one_slot_with_room_on_real_equity(self) -> None:
        """$200 livres + um lote de $15 a 15% ainda cabe outro lote."""
        budget = compute_exposure_budget(
            quote_balance=200.0,
            base_qty=0.000231,
            price=65000.0,
            max_position_pct=0.15,
        )
        assert budget["open_exposure"] == pytest.approx(15.015)
        assert budget["remaining_exposure"] > 15.0

    def test_old_self_referential_cap_was_tighter_only_if_quote_is_residual(self) -> None:
        """Mesmos números do incidente: 1 lote + $15 USDT a 15% continua sem room."""
        budget = compute_exposure_budget(
            quote_balance=15.71,
            base_qty=0.00023081,
            price=63600.0,
            max_position_pct=0.15,
        )
        assert budget["remaining_exposure"] == 0.0


class TestInferLogicalSlots:
    def test_empty(self) -> None:
        assert infer_logical_slots(exchange_qty=0.0, entries=[]) == 0

    def test_legacy_position_no_entries(self) -> None:
        assert infer_logical_slots(exchange_qty=0.1, entries=[]) == 1

    def test_entries_match_exchange(self) -> None:
        entries = [{"size": 0.00023}, {"size": 0.00023}]
        assert infer_logical_slots(exchange_qty=0.00046, entries=entries) == 2

    def test_exchange_has_untracked_lots(self) -> None:
        entries = [{"size": 0.00023}]
        slots = infer_logical_slots(exchange_qty=0.00269, entries=entries)
        assert slots >= 11
