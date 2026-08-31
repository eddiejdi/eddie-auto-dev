#!/usr/bin/env python3
"""Testes do guard de pré-checagem de saldo em SELL.

Valida que o agente não tenta re-vender slots que a exchange rejeitaria
com "Balance insufficient" (código 200004). Cobre:

1. Pré-checagem: size > saldo disponível aborta a ordem ANTES de enviá-la.
2. Cooldown: após uma falha de saldo, vendas subsequentes no mesmo ciclo
   são abortadas sem chamar place_market_order.
3. Erro 200004 da exchange dispara reconcile síncrono + cooldown e não
   reenvia a ordem imediatamente.
"""
from __future__ import annotations

import sys
import threading
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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
        get_balances=lambda account_type="trade": [],
        get_balance=lambda currency="USDT": 0.0,
        get_total_balance=lambda currency="USDT": 0.0,
        place_market_order=None,
        analyze_orderbook=None,
        analyze_trade_flow=None,
        inner_transfer=None,
        get_fills_for_order=None,
        _has_keys=lambda: False,
        _resolve_telegram_bot_token=lambda: "",
        _resolve_telegram_chat_id=lambda: "",
        _send_telegram_alert=lambda *a, **kw: None,
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

from position_manager_mixin import (
    PositionManagerMixin,
    _BALANCE_CHECK_TOLERANCE_PCT,
    _BALANCE_INSUFFICIENT_COOLDOWN_S,
)
from slot_exit_policy import SlotExitDecision


def _make_agent(entries: list[dict], *, dry_run: bool = False) -> PositionManagerMixin:
    """Constrói um mixin puro para SELL (não precisa do agente completo)."""
    agent = PositionManagerMixin.__new__(PositionManagerMixin)
    agent.symbol = "SOL-USDT"
    agent._trade_lock = threading.Lock()
    agent._last_trade_id = 0
    agent.db = MagicMock()
    agent.db.record_trade.return_value = 1
    agent.db.update_trade_pnl.return_value = None
    agent.db.merge_trade_metadata.return_value = None
    agent._current_profile = lambda: "aggressive"
    agent._get_guardrail_sell_verdict = lambda price: None
    agent._guardrail_allows_slot_sell = lambda *a, **kw: True
    agent._get_guardrail_sell_protection_cfg = lambda: {
        "active": False,
        "positive_only_sells": False,
        "min_sell_pnl_pct": -1.0,
    }
    agent._block_trade = MagicMock()
    agent._load_live_config = lambda: {"guardrails_active": False}
    agent.config = {"guardrails_active": False}
    total_position = sum(float(e["size"]) for e in entries)
    weighted_cost = (
        sum(float(e["size"]) * float(e["price"]) for e in entries)
        if total_position
        else 0.0
    )
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
        last_sell_entry_price=0.0,
        last_sell_ts=0.0,
        trailing_high=0.0,
        target_sell_price=0.0,
        target_sell_reason="",
        position_count=len(entries),
        raw_entry_count=len(entries),
        logical_position_slots=len(entries),
        buy_success_pressure=0.0,
        buy_success_factor=1.0,
        buy_dynamic_batch_cap_usdt=0.0,
        dca_valley_low=0.0,
        position_value=0.0,
    )
    agent._trading_fee_pct = 0.001
    return agent


def _decision(entry_idx: int, entry_price: float) -> SlotExitDecision:
    return SlotExitDecision(
        entry_idx=entry_idx,
        reason="TP_HIT",
        expected_entry_price=entry_price,
        bypass_guardrail=False,
    )


def test_pre_balance_check_aborts_sell_when_size_exceeds_available() -> None:
    """size > saldo real deve abortar a ordem ANTES de enviá-la à exchange."""
    agent = _make_agent(
        [
            {"price": 77.27, "size": 0.129, "ts": 1.0},
            {"price": 77.30, "size": 0.129, "ts": 2.0},
        ]
    )

    # Saldo real insuficiente: slots somam 0.258, mas só há 0.0005 na exchange
    # (após venda concorrente — exatamente o cenário da regressão 19/08).
    agent._read_base_balance_available = lambda: 0.0005
    agent._min_tradeable_dust = lambda: 0.0001
    agent._reconcile_position_with_exchange = MagicMock()

    place_mock = MagicMock(
        return_value={"success": True, "orderId": "must-not-be-called", "raw": {}}
    )

    decisions = sorted(
        [_decision(1, 77.30), _decision(0, 77.27)],
        key=lambda d: d.entry_idx,
        reverse=True,
    )

    with patch("position_manager_mixin.place_market_order", place_mock):
        sold = agent._execute_slot_exit_decisions(78.5, decisions)

    assert sold == 0, "nenhuma venda deve ocorrer com saldo insuficiente"
    place_mock.assert_not_called(), (
        "place_market_order NÃO deve ser chamado quando size > saldo real"
    )
    agent._reconcile_position_with_exchange.assert_called_once_with(78.5)
    assert agent._sell_balance_cooldown_until > 0, (
        "cooldown deve ser ativado após pré-checagem falhar"
    )


def test_cooldown_aborts_subsequent_sells_in_same_cycle() -> None:
    """Após a primeira falha de saldo, o cooldown bloqueia vendas seguintes."""
    agent = _make_agent(
        [
            {"price": 77.27, "size": 0.129, "ts": 1.0},
            {"price": 77.30, "size": 0.129, "ts": 2.0},
        ]
    )

    # Primeira venda: saldo suficiente para 0.129 mas não para os dois.
    # Simula saldo caindo para 0 após a primeira venda (race com exchange).
    call_count = {"n": 0}

    def _read_bal():
        # Primeira chamada: tem saldo. Depois: saldo zero (já foi vendido).
        call_count["n"] += 1
        if call_count["n"] == 1:
            return 0.13
        return 0.0

    agent._read_base_balance_available = _read_bal
    agent._min_tradeable_dust = lambda: 0.0001
    agent._reconcile_position_with_exchange = MagicMock()

    place_mock = MagicMock(
        side_effect=[
            {"success": True, "orderId": "ok-1", "raw": {"code": "200000"}},
        ]
    )

    decisions = sorted(
        [_decision(1, 77.30), _decision(0, 77.27)],
        key=lambda d: d.entry_idx,
        reverse=True,
    )

    with patch("position_manager_mixin.place_market_order", place_mock):
        sold = agent._execute_slot_exit_decisions(78.5, decisions)

    # Primeiro slot vendido, segundo abortado pela pré-checagem de saldo.
    assert sold == 1, f"esperado 1 venda, obtido {sold}"
    assert place_mock.call_count == 1, (
        f"esperado 1 chamada à exchange, obtido {place_mock.call_count}"
    )


def test_exchange_200004_triggers_sync_reconcile_and_cooldown() -> None:
    """Erro 200004 da KuCoin dispara reconcile síncrono + cooldown 60s."""
    agent = _make_agent([{"price": 77.27, "size": 0.129, "ts": 1.0}])

    agent._read_base_balance_available = lambda: 1.0  # pré-checagem passa
    agent._min_tradeable_dust = lambda: 0.0001
    agent._reconcile_position_with_exchange = MagicMock()

    place_mock = MagicMock(
        return_value={
            "success": False,
            "error": "Balance insufficient!",
            "raw": {"code": "200004", "msg": "Balance insufficient!"},
        }
    )

    with patch("position_manager_mixin.place_market_order", place_mock):
        sold = agent._execute_slot_exit_decisions(78.5, [_decision(0, 77.27)])

    assert sold == 0
    agent._reconcile_position_with_exchange.assert_called_once_with(78.5)
    assert agent._sell_balance_cooldown_until > 0


def test_cooldown_blocks_second_decision_without_place_market_call() -> None:
    """Cooldown ativo: decisões subsequentes no mesmo ciclo não enviam ordem."""
    agent = _make_agent(
        [
            {"price": 77.27, "size": 0.129, "ts": 1.0},
            {"price": 77.30, "size": 0.129, "ts": 2.0},
        ]
    )

    # Pré-set cooldown ativo.
    import time as _time

    agent._sell_balance_cooldown_until = _time.time() + 60.0
    agent._read_base_balance_available = lambda: 0.0001
    agent._min_tradeable_dust = lambda: 0.0001

    place_mock = MagicMock()

    decisions = sorted(
        [_decision(1, 77.30), _decision(0, 77.27)],
        key=lambda d: d.entry_idx,
        reverse=True,
    )

    with patch("position_manager_mixin.place_market_order", place_mock):
        sold = agent._execute_slot_exit_decisions(78.5, decisions)

    assert sold == 0
    place_mock.assert_not_called()


def test_balance_check_skipped_in_dry_run() -> None:
    """Em dry_run, pré-checagem de saldo real não deve bloquear vendas."""
    agent = _make_agent(
        [{"price": 77.27, "size": 0.129, "ts": 1.0}], dry_run=True
    )

    # Mesmo com saldo "0", dry_run não consulta saldo real.
    agent._read_base_balance_available = lambda: -1.0  # não chamado em dry_run
    agent._min_tradeable_dust = lambda: 0.0001

    place_mock = MagicMock()

    with patch("position_manager_mixin.place_market_order", place_mock):
        sold = agent._execute_slot_exit_decisions(78.5, [_decision(0, 77.27)])

    assert sold == 1
    place_mock.assert_not_called()  # dry_run não envia ordens reais


def test_pre_check_tolerance_allows_small_rounding_diff() -> None:
    """Diferenças < tolerância (0.5% do size) não devem abortar a venda."""
    agent = _make_agent([{"price": 77.27, "size": 0.129, "ts": 1.0}])

    # Saldo ligeiramente abaixo do size, dentro da tolerância.
    size = 0.129
    tolerance = max(size * _BALANCE_CHECK_TOLERANCE_PCT, 0.0001)
    available = size - tolerance / 2  # dentro da tolerância
    agent._read_base_balance_available = lambda: available
    agent._min_tradeable_dust = lambda: 0.0001
    agent._reconcile_position_with_exchange = MagicMock()

    place_mock = MagicMock(
        return_value={"success": True, "orderId": "ok-1", "raw": {"code": "200000"}}
    )

    with patch("position_manager_mixin.place_market_order", place_mock):
        sold = agent._execute_slot_exit_decisions(78.5, [_decision(0, 77.27)])

    assert sold == 1, "venda deve ocorrer se diferença está dentro da tolerância"
    agent._reconcile_position_with_exchange.assert_not_called()


def test_dust_skip_removes_slot_silently() -> None:
    """dust_skip não reenvia ordem e remove o slot do state (sem Telegram)."""
    agent = _make_agent([{"price": 77.27, "size": 0.00044457, "ts": 1.0, "trade_id": 3960}])
    agent._read_base_balance_available = lambda: 0.00044457
    agent._min_tradeable_dust = lambda: 0.0001
    agent._reconcile_position_with_exchange = MagicMock()

    place_mock = MagicMock(
        return_value={
            "success": False,
            "error": "Dust size 0.00044457 below baseIncrement 0.001",
            "raw": {"code": "dust_skip", "msg": "Quantity below base increment"},
            "skip_notify": True,
        }
    )

    with patch("position_manager_mixin.place_market_order", place_mock):
        sold = agent._execute_slot_exit_decisions(78.5, [_decision(0, 77.27)])

    assert sold == 1
    place_mock.assert_called_once()
    assert agent.state.entries == []
    agent.db.merge_trade_metadata.assert_called()
    args = agent.db.merge_trade_metadata.call_args
    assert args[0][0] == 3960
    assert args[0][1]["closed_reason"] == "dust_below_minsize"


# ── Cross-profile guard tests ────────────────────────────────────────────


def test_cross_profile_guard_aborts_when_exchange_total_below_db() -> None:
    """Cross-profile: DB tem 0.196 SOL mas exchange só tem 0.090.

    Cenário real: aggressive vendeu 0.196 SOL (comprou 0.098 + shadow 0.098),
    mas shadow ainda tem entry de 0.096 no DB. O guard deve abortar o SELL
    e disparar reconcile para limpar slots fantasma.
    """
    agent = _make_agent(
        [
            {"price": 103.60, "size": 0.096, "ts": 1.0},
            {"price": 101.85, "size": 0.100, "ts": 2.0},
        ]
    )

    # Saldo disponível caiu (já foi vendido por outro profile)
    agent._read_base_balance_available = lambda: 0.080
    agent._min_tradeable_dust = lambda: 0.0001
    agent._reconcile_position_with_exchange = MagicMock()

    # Mock get_total_balance: exchange só tem 0.090, mas DB tem 0.196
    import kucoin_api as _ka
    original_gt = _ka.get_total_balance
    _ka.get_total_balance = lambda currency: 0.090

    try:
        place_mock = MagicMock(
            return_value={"success": True, "orderId": "must-not-be-called", "raw": {}}
        )
        with patch("position_manager_mixin.place_market_order", place_mock):
            sold = agent._execute_slot_exit_decisions(
                105.0, [_decision(1, 101.85), _decision(0, 103.60)]
            )

        assert sold == 0, "cross-profile guard deve abortar SELL"
        place_mock.assert_not_called()
        agent._reconcile_position_with_exchange.assert_called_once()
    finally:
        _ka.get_total_balance = original_gt


def test_cross_profile_guard_allows_sell_when_exchange_covers_size() -> None:
    """Cross-profile: DB tem 0.196 mas exchange tem 0.2 — SELL de 0.096 é OK."""
    agent = _make_agent(
        [
            {"price": 103.60, "size": 0.096, "ts": 1.0},
        ]
    )

    agent._read_base_balance_available = lambda: 0.2
    agent._min_tradeable_dust = lambda: 0.0001
    agent._reconcile_position_with_exchange = MagicMock()

    import kucoin_api as _ka
    original_gt = _ka.get_total_balance
    _ka.get_total_balance = lambda currency: 0.2

    try:
        place_mock = MagicMock(
            return_value={"success": True, "orderId": "ok-1", "raw": {"code": "200000"}}
        )
        with patch("position_manager_mixin.place_market_order", place_mock):
            sold = agent._execute_slot_exit_decisions(
                105.0, [_decision(0, 103.60)]
            )

        assert sold == 1, "SELL deve prosseguir quando exchange cobre o size"
    finally:
        _ka.get_total_balance = original_gt


def test_get_balance_reads_main_and_trade() -> None:
    """get_balance soma MAIN + TRADE (regressão SOL-USDT).

    Verifica que a lógica de get_balance foi alterada para somar
    MAIN + TRADE em vez de só TRADE.
    """
    # Simula a lógica corrigida de get_balance
    def get_balance_fixed(currency, get_balances_fn):
        total = 0.0
        for acct_type in ("trade", "main"):
            for b in get_balances_fn(account_type=acct_type):
                if b["currency"] == currency:
                    total += b["available"]
        return total

    def mock_get_balances(account_type="trade"):
        if account_type == "main":
            return [{"currency": "SOL", "balance": 0.196, "available": 0.196, "holds": 0.0}]
        return [{"currency": "SOL", "balance": 0.0, "available": 0.0, "holds": 0.0}]

    result = get_balance_fixed("SOL", mock_get_balances)
    assert abs(result - 0.196) < 1e-8, f"esperado 0.196, obtido {result}"


def test_read_subaccount_spot_balances_checks_main_and_trade() -> None:
    """_read_subaccount_spot_balances soma MAIN+TRADE sem subconta."""
    agent = _make_agent([{"price": 103.60, "size": 0.096, "ts": 1.0}])

    # Replace the mock kucoin_api's get_balances with our test version
    import kucoin_api as _ka
    original_gb = _ka.get_balances
    _ka.get_balances = lambda account_type="trade": (
        [{"currency": "SOL", "balance": 0.196, "available": 0.196, "holds": 0.0}]
        if account_type == "main"
        else [{"currency": "SOL", "balance": 0.0, "available": 0.0, "holds": 0.0}]
    )
    try:
        quote, base = agent._read_subaccount_spot_balances("USDT")
        assert abs(base - 0.196) < 1e-8, f"esperado 0.196, obtido {base}"
    finally:
        _ka.get_balances = original_gb
