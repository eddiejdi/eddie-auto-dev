"""Testes unitários para SellTargetMixin."""
from __future__ import annotations

import sys
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent.parent / "btc_trading_agent"))

from sell_target_mixin import SellTargetMixin


# ── Fixture helpers ──────────────────────────────────────────────────────────

def _make_rag(
    *,
    ai_tp: float = 0.02,
    reason: str = "rag_reason",
    regime: str = "RANGING",
) -> MagicMock:
    adj = MagicMock()
    adj.ai_take_profit_pct = ai_tp
    adj.ai_take_profit_reason = reason
    adj.suggested_regime = regime
    adj.ollama_mode = "shadow"
    return adj


def _make_agent(
    *,
    position: float = 0.1,
    entry_price: float = 90_000.0,
    target_sell_price: float = 0.0,
    target_sell_reason: str = "",
    live_cfg: dict | None = None,
    rag_adj=None,
    window_target: float = 0.0,
) -> SellTargetMixin:
    class _Agent(SellTargetMixin):
        def __init__(self):
            self.state = SimpleNamespace(
                position=position,
                entry_price=entry_price,
                target_sell_price=target_sell_price,
                target_sell_reason=target_sell_reason,
            )
            self.symbol = "BTC-USDT"
            self._module_config = {}
            self._trading_fee_pct = 0.001
            self.db = MagicMock()

        def _load_live_config(self):
            return live_cfg or {}

        def _current_profile(self):
            return "conservative"

        def _stamp_latest_open_buy_target(self):
            pass

        @property
        def market_rag(self):
            m = MagicMock()
            m.get_current_adjustment.return_value = rag_adj or _make_rag()
            return m

        def _get_fresh_ai_trade_window(self):
            if window_target > 0:
                return {"target_sell": window_target}
            return None

    return _Agent()


# ── _sync_target_sell_with_ai ────────────────────────────────────────────────

class TestSyncTargetSellWithAI:

    def test_no_position_is_noop(self):
        agent = _make_agent(position=0.0)
        agent._sync_target_sell_with_ai()
        assert agent.state.target_sell_price == 0.0

    def test_no_entry_price_is_noop(self):
        agent = _make_agent(entry_price=0.0)
        agent._sync_target_sell_with_ai()
        assert agent.state.target_sell_price == 0.0

    def test_ai_window_is_primary_target(self):
        # window_target < cap → window é o alvo
        entry = 90_000.0
        window = 90_500.0   # +0.56%
        cap    = entry * 1.02  # +2%
        agent = _make_agent(
            entry_price=entry,
            rag_adj=_make_rag(ai_tp=0.02),
            window_target=window,
        )
        agent._sync_target_sell_with_ai()
        assert agent.state.target_sell_price == pytest.approx(window, abs=0.01)

    def test_ai_window_clamped_by_cap(self):
        # window_target > cap → target = cap
        entry = 90_000.0
        window = 92_000.0   # +2.22%, acima do cap de +2%
        cap    = entry * 1.02
        agent = _make_agent(
            entry_price=entry,
            rag_adj=_make_rag(ai_tp=0.02),
            window_target=window,
        )
        agent._sync_target_sell_with_ai()
        assert agent.state.target_sell_price == pytest.approx(cap, abs=0.01)

    def test_fallback_to_formula_when_no_window(self):
        # sem window (window_target <= entry) → teto vira alvo
        entry = 90_000.0
        cap   = entry * 1.02
        agent = _make_agent(
            entry_price=entry,
            rag_adj=_make_rag(ai_tp=0.02),
            window_target=0.0,
        )
        agent._sync_target_sell_with_ai()
        assert agent.state.target_sell_price == pytest.approx(cap, abs=0.01)

    def test_ranging_cap_reduces_ai_tp(self):
        # RANGING + ranging_max_tp_pct=0.004 → ai_tp é reduzido para 0.4%
        entry = 90_000.0
        agent = _make_agent(
            entry_price=entry,
            rag_adj=_make_rag(ai_tp=0.02, regime="RANGING"),
            window_target=0.0,
            live_cfg={"ranging_max_tp_pct": 0.004},
        )
        agent._sync_target_sell_with_ai()
        expected_cap = entry * (1 + 0.004)
        assert agent.state.target_sell_price == pytest.approx(expected_cap, abs=0.01)

    def test_ranging_cap_not_applied_outside_ranging(self):
        # BULLISH → ranging_max_tp_pct ignorado
        entry = 90_000.0
        agent = _make_agent(
            entry_price=entry,
            rag_adj=_make_rag(ai_tp=0.02, regime="BULLISH"),
            window_target=0.0,
            live_cfg={"ranging_max_tp_pct": 0.004},
        )
        agent._sync_target_sell_with_ai()
        expected_cap = entry * 1.02
        assert agent.state.target_sell_price == pytest.approx(expected_cap, abs=0.01)

    def test_target_updates_upward(self):
        entry = 90_000.0
        old_target = entry * 1.005  # target baixo
        new_window  = entry * 1.01  # AI prevê mais alto
        agent = _make_agent(
            entry_price=entry,
            target_sell_price=old_target,
            rag_adj=_make_rag(ai_tp=0.02, regime="BULLISH"),
            window_target=new_window,
        )
        agent._sync_target_sell_with_ai()
        assert agent.state.target_sell_price > old_target

    def test_target_updates_downward(self):
        entry = 90_000.0
        old_target = entry * 1.02
        new_window  = entry * 1.005  # AI rebaixa previsão
        agent = _make_agent(
            entry_price=entry,
            target_sell_price=old_target,
            rag_adj=_make_rag(ai_tp=0.02, regime="BULLISH"),
            window_target=new_window,
        )
        agent._sync_target_sell_with_ai()
        assert agent.state.target_sell_price < old_target

    def test_no_update_when_diff_below_threshold(self):
        entry = 90_000.0
        cap = entry * 1.02
        # target já igual ao cap → diff = 0 → sem log/update
        agent = _make_agent(
            entry_price=entry,
            target_sell_price=cap,
            rag_adj=_make_rag(ai_tp=0.02),
            window_target=0.0,
        )
        agent._sync_target_sell_with_ai()
        assert agent.state.target_sell_price == pytest.approx(cap, abs=0.01)

    def test_min_tp_floor_applied(self):
        # ai_tp abaixo do min_pct → eleva para min_pct
        entry = 90_000.0
        agent = _make_agent(
            entry_price=entry,
            rag_adj=_make_rag(ai_tp=0.0001, regime="BULLISH"),
            window_target=0.0,
            live_cfg={"auto_take_profit": {"min_pct": 0.005}},
        )
        agent._sync_target_sell_with_ai()
        expected = entry * (1 + 0.005)
        assert agent.state.target_sell_price == pytest.approx(expected, abs=0.01)


# ── _serialize_target_sell_metadata ─────────────────────────────────────────

class TestSerializeTargetSellMetadata:

    def test_returns_empty_when_no_target(self):
        agent = _make_agent(target_sell_price=0.0)
        assert agent._serialize_target_sell_metadata() == {}

    def test_returns_price_fields(self):
        target = 91_000.0
        agent = _make_agent(target_sell_price=target, target_sell_reason="AI_WINDOW")
        meta = agent._serialize_target_sell_metadata()
        assert meta["target_sell_price"] == pytest.approx(target, abs=0.01)
        assert meta["target_sell_trigger_price"] == pytest.approx(target, abs=0.01)
        assert meta["target_sell_reason"] == "AI_WINDOW"

    def test_reason_omitted_when_empty(self):
        agent = _make_agent(target_sell_price=91_000.0, target_sell_reason="")
        meta = agent._serialize_target_sell_metadata()
        assert "target_sell_reason" not in meta


# ── _build_trade_metadata ────────────────────────────────────────────────────

class TestBuildTradeMetadata:

    def test_merges_base_and_target(self):
        agent = _make_agent(target_sell_price=91_000.0, target_sell_reason="TEST")
        meta = agent._build_trade_metadata({"custom_key": "value"})
        assert meta["custom_key"] == "value"
        assert "target_sell_price" in meta

    def test_includes_exit_reason(self):
        signal = SimpleNamespace(reason="MAX_HOLD slot#1 (25.0h held)")
        agent = _make_agent(target_sell_price=91_000.0)
        meta = agent._build_trade_metadata(signal=signal, include_exit_reason=True)
        assert meta["exit_reason"] == "MAX_HOLD slot#1 (25.0h held)"

    def test_exit_reason_truncated_at_240(self):
        signal = SimpleNamespace(reason="X" * 300)
        agent = _make_agent(target_sell_price=91_000.0)
        meta = agent._build_trade_metadata(signal=signal, include_exit_reason=True)
        assert len(meta["exit_reason"]) == 240

    def test_no_exit_reason_by_default(self):
        signal = SimpleNamespace(reason="should_not_appear")
        agent = _make_agent(target_sell_price=91_000.0)
        meta = agent._build_trade_metadata(signal=signal)
        assert "exit_reason" not in meta
