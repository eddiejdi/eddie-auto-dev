#!/usr/bin/env python3
"""Regressões para _reconcile_buy_fill — correção do size estimado do BUY.

O size do BUY é gravado como estimativa (``funds / ticker``) e fica menor que o
dealSize real, porque a fee é cobrada em USDT (BTC creditado bruto) e o ticker
não é o preço de execução. Como o SELL vende ``entries[].size``, cada ciclo
deixava dust na exchange — origem dos falsos positivos de reconciliação.
"""

from pathlib import Path
from types import SimpleNamespace
import os
import sys
import threading
import types

import unittest.mock as _mock


os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))
sys.modules.setdefault("httpx", types.SimpleNamespace())

_numpy_mock = _mock.MagicMock()
_numpy_mock.isscalar = lambda x: isinstance(x, (int, float, complex, bool))
_numpy_mock.bool_ = bool
sys.modules.setdefault("numpy", _numpy_mock)

_psycopg2_mock = types.ModuleType("psycopg2")
_psycopg2_mock.extras = types.SimpleNamespace(RealDictCursor=object)
_psycopg2_mock.pool = types.SimpleNamespace(
    ThreadedConnectionPool=object,
    SimpleConnectionPool=object,
)
sys.modules.setdefault("psycopg2", _psycopg2_mock)
sys.modules.setdefault("psycopg2.extras", _psycopg2_mock.extras)
sys.modules.setdefault("psycopg2.pool", _psycopg2_mock.pool)

# Don't mock training_db module globally - it breaks other test files
# We'll mock TrainingDatabase on the agent instance instead
sys.modules.setdefault("market_rag", types.SimpleNamespace(MarketRAG=object))
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
        get_fills_for_order=lambda *a, **kw: {},
        _resolve_telegram_bot_token=lambda: "",
        _resolve_telegram_chat_id=lambda: "",
        _send_telegram_alert=lambda *a, **kw: None,
    ),
)
sys.modules.setdefault(
    "fast_model",
    types.SimpleNamespace(FastTradingModel=object, MarketState=object, Signal=object),
)

import trading_agent as ta_mod
from trading_agent import BitcoinTradingAgent


# ── Dados reais capturados da API KuCoin (subconta BTCConservative) ──────────
# Trade #3833: ticker $63.400,95 / fill real $63.443,50, dealSize 0.00023643.
# O size estimado grava 0.00023635 — 8 satoshis a menos.
REAL_TICKER = 63_400.95
REAL_FILL_PRICE = 63_443.5
REAL_DEAL_SIZE = 0.00023643
EST_SIZE = 15.0 / REAL_TICKER * (1 - 0.001)  # fórmula atual: 0.00023635...
ORDER_ID = "6a7132756b3c7c0007927616"
TRADE_ID = 3833


def _fill(size=REAL_DEAL_SIZE, price=REAL_FILL_PRICE, funds=15.0):
    return {
        "fill_price": price,
        "fill_size": size,
        "fill_funds": funds,
        "fill_fee": 0.00999989,
        "fee_currency": "USDT",
        "fee_rate": 0.001,
        "liquidity": "taker",
        "fills_count": 1,
    }


def _agent(entries=None, *, position=None) -> BitcoinTradingAgent:
    agent = BitcoinTradingAgent.__new__(BitcoinTradingAgent)
    agent.symbol = "BTC-USDT"
    agent._trade_lock = threading.Lock()
    entries = list(entries if entries is not None else [_entry()])
    total = sum(e["size"] for e in entries)
    agent.state = SimpleNamespace(
        dry_run=False,
        profile="conservative",
        position=position if position is not None else total,
        entry_price=REAL_TICKER,
        entries=entries,
        position_count=len(entries),
        raw_entry_count=len(entries),
        logical_position_slots=len(entries),
    )
    agent.db = _mock.MagicMock()
    agent.db.update_trade_fill.return_value = True
    return agent


def _entry(size=EST_SIZE, price=REAL_TICKER, trade_id=TRADE_ID, order_id=ORDER_ID):
    return {
        "price": price,
        "size": size,
        "ts": 1_784_000_000.0,
        "target_sell": 0.0,
        "trailing_high": price,
        "trade_id": trade_id,
        "order_id": order_id,
    }


def _run(agent, fill_value, *, est_size=EST_SIZE, est_price=REAL_TICKER):
    """Executa _reconcile_buy_fill sem o sleep(3) de espera do fill."""
    with (
        _mock.patch.object(ta_mod, "get_fills_for_order", return_value=fill_value),
        _mock.patch.object(ta_mod.time, "sleep"),
    ):
        agent._reconcile_buy_fill(ORDER_ID, TRADE_ID, est_price, est_size)


# ── Correção do size ────────────────────────────────────────────────────────

def test_entry_size_corrected_to_real_deal_size() -> None:
    """entries[].size passa a valer o dealSize real — sem isso o SELL deixa dust."""
    agent = _agent()
    assert agent.state.entries[0]["size"] == EST_SIZE  # pré-condição

    _run(agent, _fill())

    assert agent.state.entries[0]["size"] == REAL_DEAL_SIZE
    assert agent.state.entries[0]["price"] == REAL_FILL_PRICE


def test_dust_eliminated_end_to_end() -> None:
    """O que o SELL venderia passa a casar com o que a exchange creditou."""
    agent = _agent()
    dust_antes = REAL_DEAL_SIZE - agent.state.entries[0]["size"]
    assert dust_antes > 0  # a estimativa subestima

    _run(agent, _fill())

    assert REAL_DEAL_SIZE - agent.state.entries[0]["size"] == 0


def test_db_updated_with_fill_and_metadata() -> None:
    agent = _agent()

    _run(agent, _fill())

    agent.db.update_trade_fill.assert_called_once()
    args, kwargs = agent.db.update_trade_fill.call_args
    assert args[0] == TRADE_ID
    assert args[1] == REAL_DEAL_SIZE
    assert args[2] == REAL_FILL_PRICE
    assert kwargs["funds"] == 15.0

    meta = agent.db.merge_trade_metadata.call_args[0][1]
    assert meta["fill_reconciled"] is True
    assert meta["fill_size"] == REAL_DEAL_SIZE
    assert meta["estimated_size"] == EST_SIZE
    assert meta["size_correction"] > 0
    assert meta["fee_currency"] == "USDT"


def test_position_and_avg_price_recomputed() -> None:
    """Posição e preço médio refletem o fill, não a estimativa."""
    other = _entry(size=0.0002, price=60_000.0, trade_id=999, order_id="other")
    agent = _agent(entries=[other, _entry()])

    _run(agent, _fill())

    expected_total = 0.0002 + REAL_DEAL_SIZE
    assert agent.state.position == expected_total
    expected_avg = (
        0.0002 * 60_000.0 + REAL_DEAL_SIZE * REAL_FILL_PRICE
    ) / expected_total
    assert agent.state.entry_price == expected_avg
    assert other["size"] == 0.0002  # slot alheio intocado


def test_matches_slot_by_order_id_when_trade_id_absent() -> None:
    entry = _entry()
    del entry["trade_id"]
    agent = _agent(entries=[entry])

    _run(agent, _fill())

    assert agent.state.entries[0]["size"] == REAL_DEAL_SIZE


# ── Robustez ────────────────────────────────────────────────────────────────

def test_no_fill_keeps_estimate_and_skips_db() -> None:
    """Fill indisponível: mantém a estimativa em vez de corromper o estado."""
    agent = _agent()

    _run(agent, {})

    assert agent.state.entries[0]["size"] == EST_SIZE
    agent.db.update_trade_fill.assert_not_called()
    agent.db.merge_trade_metadata.assert_not_called()


def test_zero_size_fill_is_ignored() -> None:
    agent = _agent()

    _run(agent, _fill(size=0.0))

    assert agent.state.entries[0]["size"] == EST_SIZE
    agent.db.update_trade_fill.assert_not_called()


def test_slot_already_sold_still_corrects_db() -> None:
    """Slot vendido antes do fill aparecer: DB é corrigido, sem KeyError."""
    agent = _agent(entries=[], position=0.0)

    _run(agent, _fill())

    agent.db.update_trade_fill.assert_called_once()
    assert agent.state.entries == []


def test_db_failure_does_not_raise() -> None:
    agent = _agent()
    agent.db.update_trade_fill.side_effect = RuntimeError("db down")

    _run(agent, _fill())  # não deve propagar

    # entries já foi corrigido antes da escrita no DB
    assert agent.state.entries[0]["size"] == REAL_DEAL_SIZE


def test_holds_trade_lock_while_mutating_entries() -> None:
    """A mutação de entries acontece sob _trade_lock (evita TOCTOU)."""
    agent = _agent()
    observed = []

    real_lock = agent._trade_lock

    class _SpyLock:
        def __enter__(self):
            observed.append("acquired")
            return real_lock.__enter__()

        def __exit__(self, *a):
            observed.append("released")
            return real_lock.__exit__(*a)

    agent._trade_lock = _SpyLock()

    _run(agent, _fill())

    assert observed == ["acquired", "released"]
