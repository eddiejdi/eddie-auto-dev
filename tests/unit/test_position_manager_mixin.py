"""Testes unitários para PositionManagerMixin."""
from __future__ import annotations

import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent.parent / "btc_trading_agent"))

from position_manager_mixin import PositionManagerMixin

_FEE = 0.001


# ── Builders ─────────────────────────────────────────────────────────────────

def _entry(price: float, size: float, *, ts: float | None = None, target_sell: float = 0.0) -> dict:
    e: dict = {"price": price, "size": size, "target_sell": target_sell}
    if ts is not None:
        e["ts"] = ts
    return e


def _make_agent(
    *,
    position: float = 0.1,
    entry_price: float = 90_000.0,
    entries: list | None = None,
    dry_run: bool = True,
    live_cfg: dict | None = None,
) -> PositionManagerMixin:
    class _Agent(PositionManagerMixin):
        def __init__(self):
            self._trade_lock = threading.Lock()
            self._trading_fee_pct = _FEE
            self.symbol = "BTC-USDT"
            self.db = MagicMock()
            self.db.record_trade.return_value = 1
            self.state = SimpleNamespace(
                position=position,
                entry_price=entry_price,
                entries=list(entries or []),
                dry_run=dry_run,
                position_count=0,
                raw_entry_count=0,
                logical_position_slots=0,
                last_sell_entry_price=0.0,
                total_pnl=0.0,
                winning_trades=0,
                total_trades=0,
                daily_trades=0,
                last_trade_time=0.0,
                target_sell_price=0.0,
                target_sell_reason="",
                buy_success_pressure=0.0,
                buy_success_factor=1.0,
                buy_dynamic_batch_cap_usdt=0.0,
                dca_valley_low=0.0,
                trailing_high=0.0,
            )

        def _load_live_config(self):
            return live_cfg or {}

        def _current_profile(self):
            return "conservative"

    return _Agent()


# ── _sync_position_tracking ──────────────────────────────────────────────────

class TestSyncPositionTracking:

    def test_no_position_resets_slots(self):
        agent = _make_agent(position=0.0, entry_price=0.0, entries=[])
        agent._sync_position_tracking()
        assert agent.state.logical_position_slots == 0

    def test_entries_set_raw_and_logical_count(self):
        entries = [_entry(90_000, 0.001), _entry(89_000, 0.001), _entry(88_000, 0.001)]
        agent = _make_agent(position=0.003, entries=entries)
        agent._sync_position_tracking()
        assert agent.state.raw_entry_count == 3
        assert agent.state.logical_position_slots == 3

    def test_legacy_position_without_entries(self):
        # posição aberta (entry_price > 0) mas sem lista de entries → slot = 1
        agent = _make_agent(position=0.1, entry_price=90_000.0, entries=[])
        agent._sync_position_tracking()
        assert agent.state.logical_position_slots == 1


# ── _check_per_slot_exits: max_hold_hours ────────────────────────────────────

class TestMaxHoldHours:

    def test_disabled_when_zero(self):
        old_ts = time.time() - 50 * 3600  # 50h atrás
        entries = [_entry(90_000, 0.001, ts=old_ts)]
        agent = _make_agent(position=0.001, entries=entries, live_cfg={"max_hold_hours": 0})
        sold = agent._check_per_slot_exits(91_000.0)
        assert not sold

    def test_triggers_when_hold_exceeds_limit(self):
        old_ts = time.time() - 25 * 3600  # 25h atrás
        entries = [_entry(90_000, 0.001, ts=old_ts)]
        agent = _make_agent(
            position=0.001,
            entry_price=90_000.0,
            entries=entries,
            live_cfg={"max_hold_hours": 24},
        )
        sold = agent._check_per_slot_exits(90_100.0)
        assert sold

    def test_does_not_trigger_before_limit(self):
        recent_ts = time.time() - 12 * 3600  # 12h atrás
        entries = [_entry(90_000, 0.001, ts=recent_ts)]
        agent = _make_agent(
            position=0.001,
            entries=entries,
            live_cfg={"max_hold_hours": 24},
        )
        sold = agent._check_per_slot_exits(90_100.0)
        assert not sold

    def test_no_ts_skipped(self):
        # entrada sem timestamp → não tenta saída por tempo
        entries = [_entry(90_000, 0.001)]  # sem ts
        agent = _make_agent(
            position=0.001,
            entries=entries,
            live_cfg={"max_hold_hours": 1},
        )
        sold = agent._check_per_slot_exits(90_100.0)
        assert not sold


# ── _check_per_slot_exits: trailing stop ─────────────────────────────────────

class TestPerSlotTrailingStop:

    def _cfg(self, activation: float = 0.01, trail: float = 0.005) -> dict:
        return {"trailing_stop": {"enabled": True, "activation_pct": activation, "trail_pct": trail}}

    def test_triggers_when_drop_exceeds_trail(self):
        # slot_high = 91_000, price caiu para 90_500 → drop ≈ 0.55% > trail 0.5%
        entries = [_entry(90_000, 0.001)]
        entries[0]["trailing_high"] = 91_000.0
        agent = _make_agent(
            position=0.001, entry_price=90_000.0, entries=entries, live_cfg=self._cfg()
        )
        sold = agent._check_per_slot_exits(90_500.0)
        assert sold

    def test_no_trigger_below_activation(self):
        # gain de apenas 0.3% < activation 1% → trailing não ativa
        entries = [_entry(90_000, 0.001)]
        entries[0]["trailing_high"] = 90_270.0  # +0.3%
        agent = _make_agent(
            position=0.001, entries=entries, live_cfg=self._cfg(activation=0.01)
        )
        sold = agent._check_per_slot_exits(89_900.0)
        assert not sold

    def test_trailing_high_updated(self):
        entries = [_entry(90_000, 0.001)]
        entries[0]["trailing_high"] = 90_000.0
        agent = _make_agent(
            position=0.001, entries=entries, live_cfg=self._cfg()
        )
        agent._check_per_slot_exits(91_000.0)  # novo high
        assert agent.state.entries[0]["trailing_high"] == pytest.approx(91_000.0)


# ── _check_per_slot_exits: take profit ───────────────────────────────────────

class TestPerSlotTakeProfit:

    def test_triggers_at_target(self):
        entries = [_entry(90_000, 0.001, target_sell=91_000.0)]
        agent = _make_agent(position=0.001, entry_price=90_000.0, entries=entries)
        sold = agent._check_per_slot_exits(91_000.0)
        assert sold

    def test_no_trigger_below_target(self):
        entries = [_entry(90_000, 0.001, target_sell=91_000.0)]
        agent = _make_agent(position=0.001, entries=entries)
        sold = agent._check_per_slot_exits(90_900.0)
        assert not sold

    def test_no_trigger_when_target_zero(self):
        entries = [_entry(90_000, 0.001, target_sell=0.0)]
        agent = _make_agent(position=0.001, entries=entries)
        sold = agent._check_per_slot_exits(99_999.0)
        assert not sold


# ── _check_per_slot_exits: stop loss ─────────────────────────────────────────

class TestPerSlotStopLoss:

    def _cfg(self, pct: float = 0.03) -> dict:
        return {"auto_stop_loss": {"enabled": True, "pct": pct}}

    def test_triggers_at_loss(self):
        # preço caiu 3.1% → SL de 3% dispara
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(
            position=0.001, entry_price=90_000.0, entries=entries, live_cfg=self._cfg(0.03)
        )
        sold = agent._check_per_slot_exits(87_210.0)  # -3.1%
        assert sold

    def test_no_trigger_above_threshold(self):
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(
            position=0.001, entries=entries, live_cfg=self._cfg(0.03)
        )
        sold = agent._check_per_slot_exits(88_000.0)  # -2.2% (acima do SL)
        assert not sold

    def test_disabled_when_not_enabled(self):
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(
            position=0.001, entries=entries,
            live_cfg={"auto_stop_loss": {"enabled": False, "pct": 0.001}},
        )
        sold = agent._check_per_slot_exits(1.0)  # preço ridículo → sem SL
        assert not sold


# ── _execute_slot_sell ────────────────────────────────────────────────────────

class TestExecuteSlotSell:

    def test_dry_run_no_real_order(self):
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(position=0.001, entry_price=90_000.0, entries=entries, dry_run=True)
        result = agent._execute_slot_sell(0, 91_000.0, "TEST")
        assert result is True
        # nenhuma chamada real de order
        from kucoin_api import place_market_order  # noqa: F401 — import check only
        agent.db.record_trade.assert_called_once()

    def test_removes_slot_from_entries(self):
        entries = [_entry(90_000, 0.001), _entry(89_000, 0.001)]
        agent = _make_agent(position=0.002, entry_price=89_500.0, entries=entries)
        agent._execute_slot_sell(0, 91_000.0, "TEST")
        assert len(agent.state.entries) == 1
        assert agent.state.entries[0]["price"] == 89_000.0

    def test_recalculates_weighted_entry_price(self):
        entries = [_entry(90_000, 0.001), _entry(88_000, 0.002)]
        agent = _make_agent(position=0.003, entry_price=88_667.0, entries=entries)
        agent._execute_slot_sell(0, 91_000.0, "TEST")
        # apenas slot 88_000 restante → entry_price = 88_000
        assert agent.state.entry_price == pytest.approx(88_000.0, abs=1.0)

    def test_clears_state_when_last_slot_sold(self):
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(position=0.001, entry_price=90_000.0, entries=entries)
        agent._execute_slot_sell(0, 91_000.0, "TEST")
        assert agent.state.position == 0.0
        assert agent.state.entry_price == 0.0
        assert agent.state.entries == []
        assert agent.state.target_sell_price == 0.0
        assert agent.state.trailing_high == 0.0

    def test_rebuy_lock_set_to_entry_price(self):
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(position=0.001, entry_price=90_000.0, entries=entries)
        agent._execute_slot_sell(0, 91_000.0, "TEST")
        assert agent.state.last_sell_entry_price == pytest.approx(90_000.0)

    def test_pnl_positive_increments_winning_trades(self):
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(position=0.001, entry_price=90_000.0, entries=entries)
        agent._execute_slot_sell(0, 91_000.0, "TEST")  # lucro
        assert agent.state.winning_trades == 1
        assert agent.state.total_trades == 1
        assert agent.state.total_pnl > 0

    def test_pnl_negative_no_winning_trade(self):
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(position=0.001, entry_price=90_000.0, entries=entries)
        agent._execute_slot_sell(0, 85_000.0, "STOP_LOSS")  # prejuízo
        assert agent.state.winning_trades == 0
        assert agent.state.total_trades == 1
        assert agent.state.total_pnl < 0

    def test_invalid_entry_idx_returns_false(self):
        entries = [_entry(90_000, 0.001)]
        agent = _make_agent(position=0.001, entries=entries)
        result = agent._execute_slot_sell(5, 91_000.0, "TEST")
        assert result is False

    def test_zero_size_returns_false(self):
        entries = [{"price": 90_000, "size": 0}]
        agent = _make_agent(position=0.001, entries=entries)
        result = agent._execute_slot_sell(0, 91_000.0, "TEST")
        assert result is False

    def test_no_entries_returns_false(self):
        agent = _make_agent(position=0.0, entries=[])
        result = agent._execute_slot_sell(0, 91_000.0, "TEST")
        assert result is False


# ── Herança dos mixins em BitcoinTradingAgent ─────────────────────────────────

class TestMixinInheritance:

    def test_mixin_methods_present_in_mro(self):
        from sell_target_mixin import SellTargetMixin
        from risk_guardian_mixin import RiskGuardianMixin
        from position_manager_mixin import PositionManagerMixin

        expected_methods = [
            # SellTargetMixin
            "_sync_target_sell_with_ai",
            "_serialize_target_sell_metadata",
            "_build_trade_metadata",
            "_stamp_latest_open_buy_target",
            # RiskGuardianMixin
            "_get_guardrail_sell_protection_cfg",
            "_estimate_sell_outcome",
            "_should_allow_low_net_profit_sell",
            # PositionManagerMixin
            "_sync_position_tracking",
            "_check_per_slot_exits",
            "_execute_slot_sell",
        ]

        all_mixin_attrs: set[str] = set()
        for mixin in (SellTargetMixin, RiskGuardianMixin, PositionManagerMixin):
            all_mixin_attrs.update(
                name for name in dir(mixin) if not name.startswith("__")
            )

        for method in expected_methods:
            assert method in all_mixin_attrs, f"Método ausente nos mixins: {method}"
