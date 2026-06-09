#!/usr/bin/env python3
"""Testes para SELL com múltiplas entradas no BTC agent."""
from __future__ import annotations

import sys
import threading
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))

sys.modules.setdefault("httpx", types.SimpleNamespace())
sys.modules.setdefault(
    "kucoin_api",
    types.SimpleNamespace(
        get_price=None,
        get_price_fast=None,
        get_orderbook=None,
        get_candles=None,
        get_recent_trades=None,
        get_balances=None,
        get_balance=None,
        place_market_order=None,
        analyze_orderbook=None,
        analyze_trade_flow=None,
        inner_transfer=None,
        _has_keys=lambda: False,
        _resolve_telegram_bot_token=lambda: "",
        _resolve_telegram_chat_id=lambda: "",
    ),
)
sys.modules.setdefault(
    "fast_model",
    types.SimpleNamespace(FastTradingModel=object, MarketState=object, Signal=object),
)
sys.modules.setdefault(
    "training_db",
    types.SimpleNamespace(TrainingDatabase=object, TrainingManager=object),
)
sys.modules.setdefault("market_rag", types.SimpleNamespace(MarketRAG=object))

from slot_exit_policy import SlotExitDecision
from trading_agent import BitcoinTradingAgent


def _make_agent(
    entries: list[dict],
    *,
    dry_run: bool = True,
    live_cfg: dict | None = None,
) -> BitcoinTradingAgent:
    agent = BitcoinTradingAgent.__new__(BitcoinTradingAgent)
    total_position = sum(float(entry["size"]) for entry in entries)
    weighted_cost = sum(float(entry["size"]) * float(entry["price"]) for entry in entries)

    agent.symbol = "BTC-USDT"
    agent._trade_lock = threading.Lock()
    agent._on_trade_callbacks = []
    agent._last_trade_id = 0
    agent.db = MagicMock()
    agent.db.record_trade.return_value = 101
    agent.db.update_trade_pnl.return_value = None
    agent._current_profile = lambda: "aggressive"
    agent._get_guardrail_sell_verdict = lambda price: None
    # Desabilita o guardrail per-slot também; testes que precisam do guardrail
    # devem usar _make_agent_with_guardrail().
    agent._get_guardrail_sell_protection_cfg = lambda: {
        "active": False,
        "positive_only_sells": False,
        "min_sell_pnl_pct": 0.003,
    }
    agent._block_trade = MagicMock()
    agent._load_live_config = lambda: dict(live_cfg or {})
    agent.config = dict(live_cfg or {})
    agent.state = SimpleNamespace(
        position=total_position,
        entry_price=weighted_cost / total_position if total_position else 0.0,
        entries=[dict(entry) for entry in entries],
        dry_run=dry_run,
        total_pnl=0.0,
        winning_trades=0,
        total_trades=0,
        daily_trades=0,
        last_trade_time=0.0,
        trailing_high=0.0,
        target_sell_price=0.0,
        target_sell_reason="",
        position_count=len(entries),
        raw_entry_count=len(entries),
        logical_position_slots=len(entries),
        last_sell_entry_price=0.0,
        buy_success_pressure=0.0,
        buy_success_factor=1.0,
        buy_dynamic_batch_cap_usdt=0.0,
        dca_valley_low=0.0,
    )
    return agent


def test_normal_sell_with_multi_entry_realizes_only_profitable_slots() -> None:
    agent = _make_agent(
        [
            {"price": 90_000.0, "size": 0.001, "ts": 1.0},
            {"price": 100_000.0, "size": 0.001, "ts": 2.0},
        ]
    )
    signal = SimpleNamespace(
        action="SELL",
        confidence=0.80,
        reason="MODEL_EXIT",
        price=92_000.0,
        features={},
    )

    result = agent._execute_trade(signal, 92_000.0, force=False)

    assert result is True
    assert agent.state.position == pytest.approx(0.001)
    assert len(agent.state.entries) == 1
    assert agent.state.entries[0]["price"] == pytest.approx(100_000.0)
    assert agent.db.record_trade.call_count == 1


def test_normal_sell_with_multi_entry_blocks_until_slot_target_is_reached() -> None:
    agent = _make_agent(
        [
            {"price": 90_000.0, "size": 0.001, "ts": 1.0, "target_sell": 92_000.0},
            {"price": 100_000.0, "size": 0.001, "ts": 2.0, "target_sell": 103_000.0},
        ]
    )
    signal = SimpleNamespace(
        action="SELL",
        confidence=0.80,
        reason="MODEL_EXIT",
        price=91_500.0,
        features={},
    )

    result = agent._execute_trade(signal, 91_500.0, force=False)

    assert result is False
    assert agent.state.position == pytest.approx(0.002)
    assert len(agent.state.entries) == 2
    assert agent.db.record_trade.call_count == 0


def test_normal_sell_with_multi_entry_sells_slot_after_target_and_net_profit() -> None:
    agent = _make_agent(
        [
            {"price": 90_000.0, "size": 0.001, "ts": 1.0, "target_sell": 91_400.0},
            {"price": 100_000.0, "size": 0.001, "ts": 2.0, "target_sell": 103_000.0},
        ]
    )
    signal = SimpleNamespace(
        action="SELL",
        confidence=0.80,
        reason="MODEL_EXIT",
        price=91_500.0,
        features={},
    )

    result = agent._execute_trade(signal, 91_500.0, force=False)

    assert result is True
    assert agent.state.position == pytest.approx(0.001)
    assert len(agent.state.entries) == 1
    assert agent.state.entries[0]["price"] == pytest.approx(100_000.0)
    assert agent.db.record_trade.call_count == 1


def test_forced_stop_loss_with_multi_entry_sells_only_losing_slots() -> None:
    agent = _make_agent(
        [
            {"price": 90_000.0, "size": 0.001, "ts": 1.0},
            {"price": 100_000.0, "size": 0.001, "ts": 2.0},
        ],
        live_cfg={"auto_stop_loss": {"enabled": True, "pct": 0.03}},
    )
    agent._get_guardrail_sell_verdict = lambda price: None
    signal = SimpleNamespace(
        action="SELL",
        confidence=1.0,
        reason="AUTO_STOP_LOSS",
        price=92_000.0,
        features={},
    )

    result = agent._execute_trade(signal, 92_000.0, force=True)

    assert result is True
    assert agent.state.position == pytest.approx(0.001)
    assert len(agent.state.entries) == 1
    assert agent.state.entries[0]["price"] == pytest.approx(90_000.0)
    assert agent.db.record_trade.call_count == 1


def test_forced_take_profit_with_multi_entry_sells_only_profitable_slots() -> None:
    agent = _make_agent(
        [
            {"price": 90_000.0, "size": 0.001, "ts": 1.0},
            {"price": 100_000.0, "size": 0.001, "ts": 2.0},
        ]
    )
    signal = SimpleNamespace(
        action="SELL",
        confidence=1.0,
        reason="AUTO_TAKE_PROFIT",
        price=92_000.0,
        features={},
    )

    result = agent._execute_trade(signal, 92_000.0, force=True)

    assert result is True
    assert agent.state.position == pytest.approx(0.001)
    assert len(agent.state.entries) == 1
    assert agent.state.entries[0]["price"] == pytest.approx(100_000.0)
    assert agent.db.record_trade.call_count == 1


def test_global_auto_exit_is_ignored_for_multi_entry_positions() -> None:
    agent = _make_agent(
        [
            {"price": 90_000.0, "size": 0.001, "ts": 1.0, "target_sell": 93_000.0},
            {"price": 100_000.0, "size": 0.001, "ts": 2.0, "target_sell": 103_000.0},
        ],
        live_cfg={
            "auto_stop_loss": {"enabled": True, "pct": 0.02},
            "auto_take_profit": {"enabled": True, "pct": 0.02, "min_pct": 0.015},
        },
    )

    result = agent._check_auto_exit(92_000.0)

    assert result is False
    assert agent.db.record_trade.call_count == 0
    assert len(agent.state.entries) == 2


def test_global_trailing_stop_is_ignored_for_multi_entry_positions() -> None:
    agent = _make_agent(
        [
            {"price": 90_000.0, "size": 0.001, "ts": 1.0, "trailing_high": 95_000.0},
            {"price": 100_000.0, "size": 0.001, "ts": 2.0, "trailing_high": 95_000.0},
        ],
        live_cfg={"trailing_stop": {"enabled": True, "activation_pct": 0.01, "trail_pct": 0.01}},
    )
    agent.state.trailing_high = 95_000.0

    result = agent._check_trailing_stop(93_500.0)

    assert result is False
    assert agent.db.record_trade.call_count == 0
    assert len(agent.state.entries) == 2


# ── Regression tests para bugs introduzidos em 3dad5b60 (2026-05-18) ──────────
#
# Bug 1: _block_trade("sell_multi_entry_no_eligible_slot", ..., reason=signal.reason)
#   → TypeError: got multiple values for argument 'reason'
#   Fix: renomear kwarg para signal_reason=
#
# Bug 2: emergency exit aprovado pelo guardrail mas ProfitOnlySignalSellPolicy
#   seleciona zero slots (todos negativos) → _emergency_exit_pending nunca drena.
#   Fix: EmergencyExitSignalSellPolicy vende todos os slots; flag set em
#   _check_emergency_exit_override, consumido em _execute_trade.

def test_no_eligible_slots_block_trade_does_not_raise_typeerror() -> None:
    """_block_trade não deve receber 'reason' como kwarg duplicado (Bug 1)."""
    agent = _make_agent(
        [
            {"price": 81_000.0, "size": 0.001, "ts": 1.0},
            {"price": 82_000.0, "size": 0.001, "ts": 2.0},
        ]
    )
    # Remove o mock para usar o _block_trade real — o mock aceita qualquer arg
    # e mascararia o TypeError que ocorre em produção.
    del agent._block_trade

    signal = SimpleNamespace(
        action="SELL",
        confidence=0.80,
        reason="MODEL_EXIT",
        price=75_000.0,
        features={},
    )

    # Não deve lançar TypeError: got multiple values for argument 'reason'
    result = agent._execute_trade(signal, 75_000.0, force=False)

    assert result is False
    assert len(agent.state.entries) == 2  # nada foi vendido


def _make_agent_with_guardrail(
    entries: list[dict],
    *,
    min_sell_pnl_pct: float = 0.003,
    dry_run: bool = True,
) -> BitcoinTradingAgent:
    """Cria agente com guardrail per-slot ativo (positive_only_sells=True)."""
    agent = _make_agent(entries, dry_run=dry_run)
    # Substitui o mock do guardrail agregado pelo config real via stub
    agent._get_guardrail_sell_protection_cfg = lambda: {
        "active": True,
        "positive_only_sells": True,
        "min_sell_pnl_pct": min_sell_pnl_pct,
    }
    return agent


# ── Regressão: bug introduzido em 3fc0d0ce (2026-05-02) ──────────────────────
#
# _check_per_slot_exits() chamava _execute_slot_sell() diretamente sem passar
# pelo guardrail (positive_only_sells / min_sell_pnl_pct). Qualquer saída por
# MaxHold, TrailingStop ou TakeProfit podia vender um slot underwater.
#
# Fix: _execute_slot_exit_decisions() é agora o único choke point e chama
# _guardrail_allows_slot_sell() para cada decisão com bypass_guardrail=False.


def test_per_slot_tp_guardrail_blocks_underwater_slot() -> None:
    """TP autônomo não deve vender slot underwater quando guardrail ativo."""
    agent = _make_agent_with_guardrail(
        [{"price": 100_000.0, "size": 0.001, "ts": 1.0, "target_sell": 98_000.0}]
    )
    decisions = [
        SlotExitDecision(
            entry_idx=0,
            expected_entry_price=100_000.0,
            reason="PER_SLOT_TP slot#1 (-2.00%)",
            bypass_guardrail=False,
        )
    ]

    sold = agent._execute_slot_exit_decisions(98_000.0, decisions)

    assert sold == 0
    assert agent.state.position == pytest.approx(0.001)
    assert agent.db.record_trade.call_count == 0


def test_per_slot_trailing_guardrail_blocks_underwater_slot() -> None:
    """TrailingStop autônomo não deve vender slot underwater quando guardrail ativo."""
    agent = _make_agent_with_guardrail(
        [{"price": 100_000.0, "size": 0.001, "ts": 1.0, "trailing_high": 101_000.0}]
    )
    decisions = [
        SlotExitDecision(
            entry_idx=0,
            expected_entry_price=100_000.0,
            reason="TRAILING_STOP slot#1 (drop 1.50% from $101000.00)",
            bypass_guardrail=False,
        )
    ]

    sold = agent._execute_slot_exit_decisions(99_485.0, decisions)

    assert sold == 0
    assert agent.state.position == pytest.approx(0.001)
    assert agent.db.record_trade.call_count == 0


def test_per_slot_sl_bypasses_guardrail_and_sells() -> None:
    """StopLoss deve executar mesmo com slot underwater — bypass_guardrail=True."""
    agent = _make_agent_with_guardrail(
        [{"price": 100_000.0, "size": 0.001, "ts": 1.0}]
    )
    decisions = [
        SlotExitDecision(
            entry_idx=0,
            expected_entry_price=100_000.0,
            reason="PER_SLOT_SL slot#1 (-5.50%)",
            bypass_guardrail=True,
        )
    ]

    sold = agent._execute_slot_exit_decisions(94_500.0, decisions)

    assert sold == 1
    assert agent.state.position == pytest.approx(0.0)
    assert agent.db.record_trade.call_count == 1


def test_per_slot_tp_guardrail_allows_profitable_slot() -> None:
    """Guardrail ativo não deve bloquear slot genuinamente lucrativo."""
    agent = _make_agent_with_guardrail(
        [{"price": 90_000.0, "size": 0.001, "ts": 1.0, "target_sell": 92_000.0}]
    )
    decisions = [
        SlotExitDecision(
            entry_idx=0,
            expected_entry_price=90_000.0,
            reason="PER_SLOT_TP slot#1 (+2.22%)",
            bypass_guardrail=False,
        )
    ]

    sold = agent._execute_slot_exit_decisions(92_000.0, decisions)

    assert sold == 1
    assert agent.state.position == pytest.approx(0.0)
    assert agent.db.record_trade.call_count == 1


def test_new_slot_exit_rule_default_bypass_is_false() -> None:
    """Contrato: SlotExitDecision criada sem bypass_guardrail usa False por padrão."""
    decision = SlotExitDecision(
        entry_idx=0,
        expected_entry_price=100_000.0,
        reason="QUALQUER_NOVA_REGRA slot#1",
    )
    assert decision.bypass_guardrail is False, (
        "Novas regras herdam proteção do guardrail por padrão. "
        "Para bypasear, setar bypass_guardrail=True explicitamente."
    )
