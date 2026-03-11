"""Testes unitários para trailing stop funcional, TP floor e decision logging.

Valida:
- _check_trailing_stop: ativação, drop, sell, atualização de trailing_high
- _check_auto_exit: stop-loss, take-profit, TP floor (PATCH 14)
- Decision logging para auto-exit trades (PATCH 15)
- Integração entre trailing stop e auto-exit

Não usa APIs reais — todo I/O externo é mockado.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# ── Constantes reproduzidas do trading_agent.py ──
TRADING_FEE_PCT = 0.001


# ── Dataclasses reproduzidas do trading_agent.py ──

@dataclass
class AgentState:
    """Estado mínimo do agente para testes."""

    running: bool = False
    symbol: str = "BTC-USDT"
    position: float = 0.0
    position_value: float = 0.0
    entry_price: float = 0.0
    position_count: int = 0
    entries: list = field(default_factory=list)
    last_trade_time: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    total_pnl: float = 0.0
    dry_run: bool = True
    last_sell_entry_price: float = 0.0
    trailing_high: float = 0.0
    sell_count: int = 0
    daily_trades: int = 0
    daily_pnl: float = 0.0
    daily_date: str = ""


@dataclass
class Signal:
    """Sinal de trading mínimo para testes."""

    action: str = "HOLD"
    confidence: float = 0.0
    reason: str = ""
    price: float = 0.0
    features: dict = field(default_factory=dict)


@dataclass
class RAGAdjustment:
    """Ajustes RAG mínimos para testes."""

    similar_count: int = 5
    ai_aggressiveness: float = 0.5
    ai_buy_target_price: float = 68000.0
    ai_take_profit_pct: float = 0.025
    ai_take_profit_reason: str = "config default"
    ai_position_size_pct: float = 0.04
    ai_max_entries: int = 20


# ═══════════════════════════════════════════════════════════════
# Helpers: reproduz lógica dos métodos do trading_agent.py
# ═══════════════════════════════════════════════════════════════


def check_trailing_stop(
    *,
    price: float,
    state: AgentState,
    config: dict,
    execute_trade_fn=None,
    record_decision_fn=None,
    mark_executed_fn=None,
    last_trade_id: int = 0,
) -> bool:
    """Reproduz lógica de _check_trailing_stop do trading_agent.py."""
    if state.position <= 0 or state.entry_price <= 0:
        return False

    ts_cfg = config.get("trailing_stop", {})
    if not ts_cfg.get("enabled", False):
        return False

    activation_pct = ts_cfg.get("activation_pct", 0.015)
    trail_pct = ts_cfg.get("trail_pct", 0.008)

    # Atualiza trailing_high
    if price > state.trailing_high:
        state.trailing_high = price

    # Verifica ativação
    pnl_pct = (state.trailing_high / state.entry_price) - 1
    if pnl_pct < activation_pct:
        return False

    # Trailing stop ativado — verifica drop
    drop_from_high = (state.trailing_high - price) / state.trailing_high
    if drop_from_high >= trail_pct:
        net_pnl_pct = (price / state.entry_price) - 1
        forced_signal = Signal(
            action="SELL",
            confidence=1.0,
            reason=f"TRAILING_STOP (drop {drop_from_high*100:.2f}% from ${state.trailing_high:,.2f})",
            price=price,
            features={},
        )
        state.last_trade_time = 0
        result = True
        if execute_trade_fn:
            result = execute_trade_fn(forced_signal, price, force=True)

        if result and record_decision_fn:
            try:
                dec_id = record_decision_fn(
                    symbol=state.symbol,
                    action="SELL",
                    confidence=1.0,
                    price=price,
                    reason=forced_signal.reason,
                    features={
                        "trigger": "trailing_stop",
                        "trailing_high": round(state.trailing_high, 2),
                        "drop_pct": round(drop_from_high * 100, 2),
                    },
                )
                if mark_executed_fn:
                    mark_executed_fn(dec_id, last_trade_id)
            except Exception:
                pass
        return result

    return False


def check_auto_exit(
    *,
    price: float,
    state: AgentState,
    config: dict,
    rag_adj: RAGAdjustment,
    execute_trade_fn=None,
    record_decision_fn=None,
    mark_executed_fn=None,
    last_trade_id: int = 0,
) -> bool:
    """Reproduz lógica de _check_auto_exit do trading_agent.py."""
    if state.position <= 0 or state.entry_price <= 0:
        return False

    auto_sl = config.get("auto_stop_loss", {})
    auto_tp = config.get("auto_take_profit", {})

    sl_enabled = auto_sl.get("enabled", False)
    tp_enabled = auto_tp.get("enabled", False)

    if not sl_enabled and not tp_enabled:
        return False

    pnl_pct = (price / state.entry_price) - 1

    # Stop-Loss
    if sl_enabled:
        sl_pct = auto_sl.get("pct", 0.02)
        if pnl_pct <= -sl_pct:
            forced_signal = Signal(
                action="SELL",
                confidence=1.0,
                reason=f"AUTO_STOP_LOSS ({pnl_pct*100:.2f}%)",
                price=price,
                features={},
            )
            state.last_trade_time = 0
            result = True
            if execute_trade_fn:
                result = execute_trade_fn(forced_signal, price, force=True)
            if result and record_decision_fn:
                try:
                    dec_id = record_decision_fn(
                        symbol=state.symbol,
                        action="SELL",
                        confidence=1.0,
                        price=price,
                        reason=forced_signal.reason,
                        features={"trigger": "auto_stop_loss", "pnl_pct": round(pnl_pct * 100, 2)},
                    )
                    if mark_executed_fn:
                        mark_executed_fn(dec_id, last_trade_id)
                except Exception:
                    pass
            return result

    # Take-Profit com TP floor
    if tp_enabled:
        ai_has_data = rag_adj.similar_count >= 3

        if ai_has_data:
            tp_pct = rag_adj.ai_take_profit_pct
            tp_source = f"AI:{rag_adj.ai_take_profit_reason}"
        else:
            tp_pct = auto_tp.get("pct", 0.025)
            tp_source = "config_fallback"

        # FIX #14: Floor mínimo para TP
        min_tp_pct = auto_tp.get("min_pct", 0.015)
        if tp_pct < min_tp_pct:
            tp_pct = min_tp_pct
            tp_source += f" (floored to {min_tp_pct*100:.1f}%)"

        if pnl_pct >= tp_pct:
            forced_signal = Signal(
                action="SELL",
                confidence=1.0,
                reason=f"AUTO_TAKE_PROFIT (+{pnl_pct*100:.2f}%, TP={tp_pct*100:.2f}% [{tp_source}])",
                price=price,
                features={},
            )
            state.last_trade_time = 0
            result = True
            if execute_trade_fn:
                result = execute_trade_fn(forced_signal, price, force=True)
            if result and record_decision_fn:
                try:
                    dec_id = record_decision_fn(
                        symbol=state.symbol,
                        action="SELL",
                        confidence=1.0,
                        price=price,
                        reason=forced_signal.reason,
                        features={
                            "trigger": "auto_take_profit",
                            "pnl_pct": round(pnl_pct * 100, 2),
                            "tp_pct": round(tp_pct * 100, 2),
                            "tp_source": tp_source,
                        },
                    )
                    if mark_executed_fn:
                        mark_executed_fn(dec_id, last_trade_id)
                except Exception:
                    pass
            return result

    return False


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture()
def active_state() -> AgentState:
    """Estado com posição ativa."""
    return AgentState(
        position=0.003,
        entry_price=68000.0,
        trailing_high=68000.0,
    )


@pytest.fixture()
def ts_config() -> dict:
    """Config com trailing stop ativado."""
    return {
        "trailing_stop": {
            "enabled": True,
            "activation_pct": 0.015,
            "trail_pct": 0.008,
        },
        "auto_stop_loss": {
            "enabled": True,
            "pct": 0.02,
        },
        "auto_take_profit": {
            "enabled": True,
            "pct": 0.025,
            "min_pct": 0.015,
        },
    }


@pytest.fixture()
def default_rag() -> RAGAdjustment:
    """RAG adjustment padrão com dados suficientes."""
    return RAGAdjustment(
        similar_count=5,
        ai_take_profit_pct=0.025,
        ai_take_profit_reason="momentum positivo",
    )


# ═══════════════════════════════════════════════════════════════
# Testes: Trailing Stop — Ativação
# ═══════════════════════════════════════════════════════════════


class TestTrailingStopActivation:
    """Testa condições de ativação do trailing stop."""

    def test_not_triggered_without_position(self, ts_config: dict) -> None:
        """Sem posição, trailing stop não ativa."""
        state = AgentState(position=0.0, entry_price=0.0)
        result = check_trailing_stop(price=70000.0, state=state, config=ts_config)
        assert result is False

    def test_not_triggered_when_disabled(self, active_state: AgentState) -> None:
        """Trailing stop desativado não ativa."""
        config = {"trailing_stop": {"enabled": False}}
        result = check_trailing_stop(price=70000.0, state=active_state, config=config)
        assert result is False

    def test_not_triggered_below_activation(
        self, active_state: AgentState, ts_config: dict
    ) -> None:
        """Preço abaixo do limiar de ativação (1.5%) não ativa."""
        # entry=68000, activation_pct=1.5% → precisa chegar a 69020
        price = 68500.0  # +0.74% — insuficiente
        result = check_trailing_stop(price=price, state=active_state, config=ts_config)
        assert result is False

    def test_activated_at_threshold(
        self, active_state: AgentState, ts_config: dict
    ) -> None:
        """Preço exatamente no limiar de ativação atualiza trailing_high mas não vende."""
        # entry=68000, 1.5% acima = 69020
        price = 69020.0
        result = check_trailing_stop(price=price, state=active_state, config=ts_config)
        assert result is False  # Atingiu ativação mas sem drop
        assert active_state.trailing_high == price

    def test_trailing_high_updated(
        self, active_state: AgentState, ts_config: dict
    ) -> None:
        """trailing_high deve ser atualizado quando preço sobe."""
        check_trailing_stop(price=69500.0, state=active_state, config=ts_config)
        assert active_state.trailing_high == 69500.0

        check_trailing_stop(price=70000.0, state=active_state, config=ts_config)
        assert active_state.trailing_high == 70000.0

    def test_trailing_high_not_lowered(
        self, active_state: AgentState, ts_config: dict
    ) -> None:
        """trailing_high não deve baixar quando preço cai."""
        check_trailing_stop(price=70000.0, state=active_state, config=ts_config)
        check_trailing_stop(price=69000.0, state=active_state, config=ts_config)
        assert active_state.trailing_high == 70000.0


# ═══════════════════════════════════════════════════════════════
# Testes: Trailing Stop — Trigger de Venda
# ═══════════════════════════════════════════════════════════════


class TestTrailingStopTrigger:
    """Testa o disparo do trailing stop."""

    def test_triggered_after_drop(
        self, active_state: AgentState, ts_config: dict
    ) -> None:
        """Trailing stop dispara quando preço cai trail_pct (0.8%) do high."""
        # Simular: preço sobe para 69500 (ativação +2.2%), depois cai
        active_state.trailing_high = 69500.0  # Já acima da ativação

        # trail_pct=0.8%, drop threshold = 69500 * 0.008 = 556
        # trigger at 69500 - 556 = 68944
        price = 68940.0  # drop > 0.8%
        result = check_trailing_stop(price=price, state=active_state, config=ts_config)
        assert result is True

    def test_not_triggered_small_drop(
        self, active_state: AgentState, ts_config: dict
    ) -> None:
        """Drop insuficiente (< trail_pct) não dispara."""
        active_state.trailing_high = 69500.0

        # trail_pct=0.8%, precisa > 556 de drop
        price = 69200.0  # drop = 0.43% — insuficiente
        result = check_trailing_stop(price=price, state=active_state, config=ts_config)
        assert result is False

    def test_triggered_resets_last_trade_time(
        self, active_state: AgentState, ts_config: dict
    ) -> None:
        """Trailing stop deve zerar last_trade_time para bypass de cooldown."""
        active_state.trailing_high = 69500.0
        active_state.last_trade_time = time.time()

        check_trailing_stop(price=68900.0, state=active_state, config=ts_config)
        assert active_state.last_trade_time == 0

    def test_exact_trail_boundary(
        self, active_state: AgentState, ts_config: dict
    ) -> None:
        """Drop exatamente em trail_pct deve disparar."""
        active_state.trailing_high = 70000.0
        # trail_pct=0.8% → drop threshold = 70000 * 0.008 = 560
        price = 70000.0 * (1 - 0.008)  # exatamente 0.8%
        result = check_trailing_stop(price=price, state=active_state, config=ts_config)
        assert result is True

    def test_full_scenario_rise_and_fall(
        self, active_state: AgentState, ts_config: dict
    ) -> None:
        """Cenário completo: preço sobe gradualmente, depois cai e dispara."""
        # Fase 1: subindo
        for p in [68500, 69000, 69500, 70000, 70500]:
            result = check_trailing_stop(price=float(p), state=active_state, config=ts_config)
            assert result is False, f"Não deve disparar em subida: {p}"

        assert active_state.trailing_high == 70500.0

        # Fase 2: caindo gradualmente
        result = check_trailing_stop(price=70200.0, state=active_state, config=ts_config)
        assert result is False  # drop 0.43%

        result = check_trailing_stop(price=70000.0, state=active_state, config=ts_config)
        assert result is False  # drop 0.71%

        # Fase 3: trigger
        result = check_trailing_stop(price=69900.0, state=active_state, config=ts_config)
        assert result is True  # drop 0.85% >= 0.8%

    def test_trailing_high_stays_after_trigger(
        self, active_state: AgentState, ts_config: dict
    ) -> None:
        """trailing_high não deve ser redefinido após trigger."""
        active_state.trailing_high = 70500.0
        check_trailing_stop(price=69900.0, state=active_state, config=ts_config)
        assert active_state.trailing_high == 70500.0


# ═══════════════════════════════════════════════════════════════
# Testes: Auto Stop-Loss
# ═══════════════════════════════════════════════════════════════


class TestAutoStopLoss:
    """Testa o auto stop-loss."""

    def test_triggered_below_threshold(
        self, active_state: AgentState, ts_config: dict, default_rag: RAGAdjustment
    ) -> None:
        """SL dispara quando pnl_pct <= -sl_pct."""
        # entry=68000, sl_pct=2%, threshold = 68000 * 0.98 = 66640
        price = 66600.0
        result = check_auto_exit(
            price=price, state=active_state, config=ts_config, rag_adj=default_rag
        )
        assert result is True

    def test_not_triggered_above_threshold(
        self, active_state: AgentState, ts_config: dict, default_rag: RAGAdjustment
    ) -> None:
        """SL não dispara quando pnl_pct > -sl_pct."""
        price = 67000.0  # -1.47% — abaixo de 2%
        result = check_auto_exit(
            price=price, state=active_state, config=ts_config, rag_adj=default_rag
        )
        assert result is False

    def test_exact_sl_boundary(
        self, active_state: AgentState, ts_config: dict, default_rag: RAGAdjustment
    ) -> None:
        """Preço exatamente no sl_pct deve disparar."""
        price = 68000.0 * (1 - 0.02)  # exatamente -2%
        result = check_auto_exit(
            price=price, state=active_state, config=ts_config, rag_adj=default_rag
        )
        assert result is True

    def test_not_triggered_when_disabled(
        self, active_state: AgentState, default_rag: RAGAdjustment
    ) -> None:
        """SL desativado não dispara."""
        config = {
            "auto_stop_loss": {"enabled": False, "pct": 0.02},
            "auto_take_profit": {"enabled": False},
        }
        price = 60000.0  # -11.7%
        result = check_auto_exit(
            price=price, state=active_state, config=config, rag_adj=default_rag
        )
        assert result is False

    def test_sl_takes_priority_over_tp(
        self, active_state: AgentState, ts_config: dict, default_rag: RAGAdjustment
    ) -> None:
        """Se ambos SL e TP estão ativos, SL é verificado primeiro."""
        # Price está abaixo do SL — deve disparar SL, não TP
        price = 66000.0
        mock_execute = MagicMock(return_value=True)
        result = check_auto_exit(
            price=price,
            state=active_state,
            config=ts_config,
            rag_adj=default_rag,
            execute_trade_fn=mock_execute,
        )
        assert result is True
        call_args = mock_execute.call_args
        assert "AUTO_STOP_LOSS" in call_args[0][0].reason

    def test_no_position_returns_false(
        self, ts_config: dict, default_rag: RAGAdjustment
    ) -> None:
        """Sem posição, auto exit retorna False."""
        state = AgentState(position=0.0, entry_price=0.0)
        result = check_auto_exit(
            price=70000.0, state=state, config=ts_config, rag_adj=default_rag
        )
        assert result is False


# ═══════════════════════════════════════════════════════════════
# Testes: Auto Take-Profit
# ═══════════════════════════════════════════════════════════════


class TestAutoTakeProfit:
    """Testa o auto take-profit com TP dinâmico."""

    def test_triggered_above_tp(
        self, active_state: AgentState, ts_config: dict, default_rag: RAGAdjustment
    ) -> None:
        """TP dispara quando pnl_pct >= tp_pct."""
        # entry=68000, tp_pct=2.5%, threshold = 68000 * 1.025 = 69700
        price = 69800.0
        result = check_auto_exit(
            price=price, state=active_state, config=ts_config, rag_adj=default_rag
        )
        assert result is True

    def test_not_triggered_below_tp(
        self, active_state: AgentState, ts_config: dict, default_rag: RAGAdjustment
    ) -> None:
        """TP não dispara quando pnl_pct < tp_pct."""
        price = 69000.0  # +1.47%
        result = check_auto_exit(
            price=price, state=active_state, config=ts_config, rag_adj=default_rag
        )
        assert result is False

    def test_uses_rag_tp_when_available(
        self, active_state: AgentState, ts_config: dict
    ) -> None:
        """Usa TP da RAG quando similar_count >= 3."""
        rag = RAGAdjustment(
            similar_count=5,
            ai_take_profit_pct=0.02,  # 2% — mais agressivo
            ai_take_profit_reason="momentum forte",
        )
        # entry=68000, AI tp=2%, threshold = 68000 * 1.02 = 69360
        price = 69400.0
        result = check_auto_exit(
            price=price, state=active_state, config=ts_config, rag_adj=rag
        )
        assert result is True

    def test_uses_config_tp_when_no_rag_data(
        self, active_state: AgentState, ts_config: dict
    ) -> None:
        """Usa TP do config quando similar_count < 3."""
        rag = RAGAdjustment(
            similar_count=1,  # poucos dados
            ai_take_profit_pct=0.01,
        )
        # config tp=2.5%, entry=68000, threshold=69700
        price = 69500.0  # +2.2% — abaixo do config tp
        result = check_auto_exit(
            price=price, state=active_state, config=ts_config, rag_adj=rag
        )
        assert result is False

    def test_tp_source_in_reason(
        self, active_state: AgentState, ts_config: dict, default_rag: RAGAdjustment
    ) -> None:
        """Reason do TP deve conter a fonte (AI ou config_fallback)."""
        price = 70000.0
        mock_execute = MagicMock(return_value=True)
        check_auto_exit(
            price=price,
            state=active_state,
            config=ts_config,
            rag_adj=default_rag,
            execute_trade_fn=mock_execute,
        )
        reason = mock_execute.call_args[0][0].reason
        assert "AI:" in reason


# ═══════════════════════════════════════════════════════════════
# Testes: TP Floor (PATCH 14)
# ═══════════════════════════════════════════════════════════════


class TestTPFloor:
    """Testa o floor mínimo para TP — PATCH 14."""

    def test_tp_floor_prevents_low_ai_tp(
        self, active_state: AgentState, ts_config: dict
    ) -> None:
        """TP floor impede AI de sugerir TP < min_pct (1.5%)."""
        rag = RAGAdjustment(
            similar_count=5,
            ai_take_profit_pct=0.008,  # 0.8% — muito baixo
            ai_take_profit_reason="ranging market",
        )
        # entry=68000, com floor 1.5%, threshold = 68000 * 1.015 = 69020
        # Price entre 0.8% e 1.5% → sem floor, venderia; com floor, NÃO
        price = 68600.0  # +0.88%
        result = check_auto_exit(
            price=price, state=active_state, config=ts_config, rag_adj=rag
        )
        assert result is False, "TP floor deve impedir venda com AI TP=0.8%"

    def test_tp_floor_allows_high_ai_tp(
        self, active_state: AgentState, ts_config: dict
    ) -> None:
        """TP floor não interfere quando AI TP >= min_pct."""
        rag = RAGAdjustment(
            similar_count=5,
            ai_take_profit_pct=0.03,  # 3% — acima do floor
            ai_take_profit_reason="strong trend",
        )
        # entry=68000, tp=3%, threshold = 68000 * 1.03 = 70040
        price = 70100.0
        result = check_auto_exit(
            price=price, state=active_state, config=ts_config, rag_adj=rag
        )
        assert result is True

    def test_tp_floor_applied_at_exact_min(
        self, active_state: AgentState, ts_config: dict
    ) -> None:
        """TP exatamente no mínimo (1.5%) não deve ser floored."""
        rag = RAGAdjustment(
            similar_count=5,
            ai_take_profit_pct=0.015,  # exatamente no mínimo
        )
        # entry=68000, tp=1.5%, threshold = 69020
        price = 69100.0  # +1.62% → acima do threshold
        result = check_auto_exit(
            price=price, state=active_state, config=ts_config, rag_adj=rag
        )
        assert result is True

    def test_tp_floor_reason_contains_floored(
        self, active_state: AgentState, ts_config: dict
    ) -> None:
        """Quando floor é aplicado, reason deve indicar '(floored to ...)'."""
        rag = RAGAdjustment(
            similar_count=5,
            ai_take_profit_pct=0.005,  # 0.5% — floor aplicado
        )
        # entry=68000, floored tp=1.5%, threshold = 69020
        price = 69100.0
        mock_execute = MagicMock(return_value=True)
        check_auto_exit(
            price=price,
            state=active_state,
            config=ts_config,
            rag_adj=rag,
            execute_trade_fn=mock_execute,
        )
        reason = mock_execute.call_args[0][0].reason
        assert "floored" in reason.lower()

    def test_tp_floor_configurable_via_min_pct(
        self, active_state: AgentState
    ) -> None:
        """min_pct configurável muda o floor."""
        rag = RAGAdjustment(
            similar_count=5,
            ai_take_profit_pct=0.018,  # 1.8%
        )
        # Config com min_pct=2.0% → floor vai aplicar
        config = {
            "auto_stop_loss": {"enabled": False},
            "auto_take_profit": {"enabled": True, "pct": 0.025, "min_pct": 0.02},
        }
        # entry=68000, floored tp=2%, threshold = 69360
        price = 69200.0  # +1.76% — abaixo do floor de 2%
        result = check_auto_exit(
            price=price, state=active_state, config=config, rag_adj=rag
        )
        assert result is False

    def test_tp_floor_default_when_not_configured(
        self, active_state: AgentState
    ) -> None:
        """Se min_pct não está no config, default é 0.015 (1.5%)."""
        rag = RAGAdjustment(
            similar_count=5,
            ai_take_profit_pct=0.005,  # muito baixo
        )
        config = {
            "auto_stop_loss": {"enabled": False},
            "auto_take_profit": {"enabled": True, "pct": 0.025},
            # sem min_pct → default 0.015
        }
        # entry=68000, floor=1.5%, threshold=69020
        price = 68800.0  # +1.18% — abaixo do floor de 1.5%
        result = check_auto_exit(
            price=price, state=active_state, config=config, rag_adj=rag
        )
        assert result is False


# ═══════════════════════════════════════════════════════════════
# Testes: Decision Logging (PATCH 15)
# ═══════════════════════════════════════════════════════════════


class TestDecisionLogging:
    """Testa o registro de decisions para auto-exit trades — PATCH 15."""

    def test_trailing_stop_logs_decision(
        self, active_state: AgentState, ts_config: dict
    ) -> None:
        """Trailing stop deve registrar decision com trigger='trailing_stop'."""
        active_state.trailing_high = 70000.0
        mock_record = MagicMock(return_value=42)
        mock_mark = MagicMock()

        check_trailing_stop(
            price=69400.0,  # drop 0.86% > 0.8%
            state=active_state,
            config=ts_config,
            record_decision_fn=mock_record,
            mark_executed_fn=mock_mark,
            last_trade_id=123,
        )

        mock_record.assert_called_once()
        call_kwargs = mock_record.call_args[1]
        assert call_kwargs["action"] == "SELL"
        assert call_kwargs["confidence"] == 1.0
        assert call_kwargs["features"]["trigger"] == "trailing_stop"
        assert "trailing_high" in call_kwargs["features"]
        assert "drop_pct" in call_kwargs["features"]
        mock_mark.assert_called_once_with(42, 123)

    def test_stop_loss_logs_decision(
        self, active_state: AgentState, ts_config: dict, default_rag: RAGAdjustment
    ) -> None:
        """Auto SL deve registrar decision com trigger='auto_stop_loss'."""
        mock_record = MagicMock(return_value=99)
        mock_mark = MagicMock()

        check_auto_exit(
            price=66000.0,  # -2.94%
            state=active_state,
            config=ts_config,
            rag_adj=default_rag,
            record_decision_fn=mock_record,
            mark_executed_fn=mock_mark,
            last_trade_id=456,
        )

        mock_record.assert_called_once()
        call_kwargs = mock_record.call_args[1]
        assert call_kwargs["features"]["trigger"] == "auto_stop_loss"
        assert "pnl_pct" in call_kwargs["features"]
        mock_mark.assert_called_once_with(99, 456)

    def test_take_profit_logs_decision(
        self, active_state: AgentState, ts_config: dict, default_rag: RAGAdjustment
    ) -> None:
        """Auto TP deve registrar decision com trigger='auto_take_profit'."""
        mock_record = MagicMock(return_value=77)
        mock_mark = MagicMock()

        check_auto_exit(
            price=70000.0,  # +2.94%
            state=active_state,
            config=ts_config,
            rag_adj=default_rag,
            record_decision_fn=mock_record,
            mark_executed_fn=mock_mark,
            last_trade_id=789,
        )

        mock_record.assert_called_once()
        call_kwargs = mock_record.call_args[1]
        assert call_kwargs["features"]["trigger"] == "auto_take_profit"
        assert "pnl_pct" in call_kwargs["features"]
        assert "tp_pct" in call_kwargs["features"]
        assert "tp_source" in call_kwargs["features"]
        mock_mark.assert_called_once_with(77, 789)

    def test_decision_not_logged_when_trade_fails(
        self, active_state: AgentState, ts_config: dict, default_rag: RAGAdjustment
    ) -> None:
        """Decision NÃO deve ser logada quando execute_trade retorna False."""
        mock_execute = MagicMock(return_value=False)
        mock_record = MagicMock()

        check_auto_exit(
            price=66000.0,
            state=active_state,
            config=ts_config,
            rag_adj=default_rag,
            execute_trade_fn=mock_execute,
            record_decision_fn=mock_record,
        )

        mock_record.assert_not_called()

    def test_decision_error_does_not_crash(
        self, active_state: AgentState, ts_config: dict, default_rag: RAGAdjustment
    ) -> None:
        """Erro no record_decision não deve interromper o fluxo."""
        mock_record = MagicMock(side_effect=Exception("DB connection error"))

        # Deve completar sem exceção
        result = check_auto_exit(
            price=66000.0,
            state=active_state,
            config=ts_config,
            rag_adj=default_rag,
            record_decision_fn=mock_record,
        )
        assert result is True

    def test_trailing_stop_features_have_correct_types(
        self, active_state: AgentState, ts_config: dict
    ) -> None:
        """Features do trailing stop devem ter tipos corretos."""
        active_state.trailing_high = 70000.0
        mock_record = MagicMock(return_value=1)

        check_trailing_stop(
            price=69400.0,
            state=active_state,
            config=ts_config,
            record_decision_fn=mock_record,
        )

        features = mock_record.call_args[1]["features"]
        assert isinstance(features["trigger"], str)
        assert isinstance(features["trailing_high"], float)
        assert isinstance(features["drop_pct"], float)
        assert features["drop_pct"] > 0


# ═══════════════════════════════════════════════════════════════
# Testes: Config dinâmico (hot-reload)
# ═══════════════════════════════════════════════════════════════


class TestConfigHotReload:
    """Testa comportamento com diferentes configurações."""

    def test_all_disabled_returns_false(
        self, active_state: AgentState, default_rag: RAGAdjustment
    ) -> None:
        """Sem nenhum auto-exit ativado, retorna False."""
        config = {
            "auto_stop_loss": {"enabled": False},
            "auto_take_profit": {"enabled": False},
        }
        result = check_auto_exit(
            price=50000.0, state=active_state, config=config, rag_adj=default_rag
        )
        assert result is False

    def test_only_sl_enabled(
        self, active_state: AgentState, default_rag: RAGAdjustment
    ) -> None:
        """Apenas SL ativado funciona independentemente."""
        config = {
            "auto_stop_loss": {"enabled": True, "pct": 0.01},
            "auto_take_profit": {"enabled": False},
        }
        price = 67300.0  # -1.03% → SL de 1%
        result = check_auto_exit(
            price=price, state=active_state, config=config, rag_adj=default_rag
        )
        assert result is True

    def test_only_tp_enabled(
        self, active_state: AgentState, default_rag: RAGAdjustment
    ) -> None:
        """Apenas TP ativado funciona independentemente."""
        config = {
            "auto_stop_loss": {"enabled": False},
            "auto_take_profit": {"enabled": True, "pct": 0.02, "min_pct": 0.015},
        }
        # default_rag tem tp=2.5%, threshold=68000*1.025=69700
        price = 69800.0  # +2.65% — acima do TP da RAG
        result = check_auto_exit(
            price=price, state=active_state, config=config, rag_adj=default_rag
        )
        assert result is True

    def test_custom_trail_pct(self, active_state: AgentState) -> None:
        """Trail pct customizado é respeitado."""
        config = {
            "trailing_stop": {
                "enabled": True,
                "activation_pct": 0.01,
                "trail_pct": 0.005,  # trail mais curto
            },
        }
        active_state.trailing_high = 69000.0  # +1.47% acima do entry

        # 0.5% drop de 69000 = 345 → trigger at 68655
        price = 68650.0
        result = check_trailing_stop(price=price, state=active_state, config=config)
        assert result is True


# ═══════════════════════════════════════════════════════════════
# Testes: Cenários end-to-end
# ═══════════════════════════════════════════════════════════════


class TestEndToEndScenarios:
    """Testes end-to-end simulando cenários reais de operação."""

    def test_scenario_normal_take_profit(
        self, active_state: AgentState, ts_config: dict, default_rag: RAGAdjustment
    ) -> None:
        """Cenário: preço sobe gradualmente até atingir TP."""
        # Simular ciclos
        for price in [68200, 68500, 68800, 69000, 69300, 69500]:
            result = check_auto_exit(
                price=float(price),
                state=active_state,
                config=ts_config,
                rag_adj=default_rag,
            )
            assert result is False, f"Não deve disparar TP em {price}"

        # Atingiu TP (2.5% acima de 68000 = 69700)
        result = check_auto_exit(
            price=69800.0,
            state=active_state,
            config=ts_config,
            rag_adj=default_rag,
        )
        assert result is True

    def test_scenario_stop_loss_crash(
        self, active_state: AgentState, ts_config: dict, default_rag: RAGAdjustment
    ) -> None:
        """Cenário: crash súbito ativa SL."""
        # Preço cai drasticamente
        result = check_auto_exit(
            price=65000.0,  # -4.4%
            state=active_state,
            config=ts_config,
            rag_adj=default_rag,
        )
        assert result is True

    def test_scenario_trailing_locks_profit(
        self, active_state: AgentState, ts_config: dict
    ) -> None:
        """Cenário: preço sobe, trailing ativa, depois cai e trava lucro."""
        # Fase 1: subida
        prices_up = [68500.0, 69000.0, 69500.0, 70000.0, 70500.0]
        for p in prices_up:
            result = check_trailing_stop(
                price=p, state=active_state, config=ts_config
            )
            assert result is False

        # trailing_high = 70500
        assert active_state.trailing_high == 70500.0

        # Fase 2: queda
        result = check_trailing_stop(
            price=69900.0, state=active_state, config=ts_config
        )
        # drop = (70500 - 69900) / 70500 = 0.85% >= 0.8% → trigger
        assert result is True

        # PnL ao disparar: (69900 / 68000) - 1 = +2.79% → lucro travado!
        pnl_at_exit = (69900.0 / 68000.0) - 1
        assert pnl_at_exit > 0.02, "Trailing stop deve travar lucro > 2%"

    def test_scenario_tp_floor_prevents_micro_profit(
        self, active_state: AgentState, ts_config: dict
    ) -> None:
        """Cenário: AI sugere TP=0.8%, floor impede micro-lucro."""
        rag_low_tp = RAGAdjustment(
            similar_count=5,
            ai_take_profit_pct=0.008,  # 0.8%
        )
        # entry=68000, sem floor: venderia em 68544 (+0.8%)
        # com floor (1.5%): precisa 69020

        # Preço em +1.0% → sem floor venderia, com floor NÃO
        price = 68680.0
        result = check_auto_exit(
            price=price,
            state=active_state,
            config=ts_config,
            rag_adj=rag_low_tp,
        )
        assert result is False, "TP floor deve impedir venda em +1.0%"

        # Preço em +1.6% → acima do floor, VENDE
        price = 69100.0
        result = check_auto_exit(
            price=price,
            state=active_state,
            config=ts_config,
            rag_adj=rag_low_tp,
        )
        assert result is True, "Deve vender quando preço ultrapassa o floor"

    def test_scenario_all_decisions_logged(
        self, active_state: AgentState, ts_config: dict, default_rag: RAGAdjustment
    ) -> None:
        """Cenário: verifica que cada tipo de exit loga corretamente."""
        logged_triggers: list[str] = []
        mock_record = MagicMock(
            side_effect=lambda **kwargs: logged_triggers.append(
                kwargs["features"]["trigger"]
            )
            or len(logged_triggers)
        )

        # 1. SL
        state1 = AgentState(position=0.003, entry_price=68000.0)
        check_auto_exit(
            price=66000.0,
            state=state1,
            config=ts_config,
            rag_adj=default_rag,
            record_decision_fn=mock_record,
        )

        # 2. TP
        state2 = AgentState(position=0.003, entry_price=68000.0)
        check_auto_exit(
            price=70000.0,
            state=state2,
            config=ts_config,
            rag_adj=default_rag,
            record_decision_fn=mock_record,
        )

        # 3. Trailing
        state3 = AgentState(
            position=0.003, entry_price=68000.0, trailing_high=70000.0
        )
        check_trailing_stop(
            price=69400.0,
            state=state3,
            config=ts_config,
            record_decision_fn=mock_record,
        )

        assert "auto_stop_loss" in logged_triggers
        assert "auto_take_profit" in logged_triggers
        assert "trailing_stop" in logged_triggers
        assert len(logged_triggers) == 3
