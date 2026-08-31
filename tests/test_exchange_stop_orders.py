#!/usr/bin/env python3
"""Regressões para stop-orders server-side (SL/trailing/TP na KuCoin).

Cobre:
- SL executado server-side fecha TODOS os slots no DB e cancela TPs (OCO)
- Sync no boot cancela stop-orders órfãs quando não há posição
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
import os
import sys
import types

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))
sys.modules.setdefault("httpx", types.SimpleNamespace(Client=object))
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
        place_stop_loss_order=lambda *a, **kw: {},
        place_take_profit_order=lambda *a, **kw: {},
        cancel_stop_order=lambda *a, **kw: {},
        cancel_all_stop_orders=lambda *a, **kw: {},
        get_stop_orders=lambda *a, **kw: {"success": False, "orders": []},
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

import trading_agent as ta
from trading_agent import BitcoinTradingAgent


def _make_agent(entries):
    agent = BitcoinTradingAgent.__new__(BitcoinTradingAgent)
    agent.symbol = "BTC-USDT"
    agent.db = MagicMock()
    agent._current_profile = lambda: "test"
    agent.state = SimpleNamespace(
        dry_run=False,
        entries=list(entries),
        position=sum(float(e.get("size", 0) or 0) for e in entries),
        entry_price=float(entries[0]["price"]) if entries else 0.0,
        trailing_high=0.0,
        position_value=0.0,
        last_price=90000.0,
    )
    return agent


def test_sl_fired_closes_all_slots_and_cancels_tp(monkeypatch):
    entries = [
        {"trade_id": 11, "price": 80000.0, "size": 0.001},
        {"trade_id": 12, "price": 81000.0, "size": 0.001},
    ]
    entries[0]["exchange_stop_order_id"] = "SL1"
    entries[0]["exchange_stop_price"] = 79000.0
    entries[-1]["exchange_tp_order_id"] = "TP1"
    entries[-1]["exchange_tp_price"] = 88000.0

    agent = _make_agent(entries)

    monkeypatch.setattr(ta, "HAS_STOP_ORDERS", True)
    monkeypatch.setattr(ta, "get_stop_orders", lambda s, status="active": {
        "success": True,
        # SL1 sumiu (executada); TP1 ainda ativa
        "orders": [{"orderId": "TP1"}],
    })
    cancelled = []
    monkeypatch.setattr(ta, "cancel_stop_order",
                        lambda order_id=None, client_oid=None: cancelled.append(order_id))
    alerts = []
    monkeypatch.setattr(ta, "_send_telegram_alert", lambda msg: alerts.append(msg))

    agent._monitor_exchange_stop_orders()

    # Ambos os slots fechados como SELL no preço do stop, com matcher do BUY
    assert agent.db.record_trade.call_count == 2
    for call in agent.db.record_trade.call_args_list:
        assert call.kwargs["side"] == "sell"
        assert call.kwargs["price"] == 79000.0
        meta = call.kwargs["metadata"]
        assert meta["closed_reason"] == "exchange_stop_loss"
        assert meta["slot_buy_trade_id"] in (11, 12)

    # OCO manual: TP restante cancelada
    assert cancelled == ["TP1"]

    # Estado zerado e alerta único
    assert agent.state.entries == []
    assert agent.state.position == 0
    assert len(alerts) == 1
    assert "STOP-LOSS" in alerts[0]


def test_tp_fired_closes_single_slot(monkeypatch):
    entries = [
        {"trade_id": 21, "price": 80000.0, "size": 0.001},
        {"trade_id": 22, "price": 81000.0, "size": 0.001},
    ]
    entries[0]["exchange_stop_order_id"] = "SL9"  # ainda ativa
    entries[0]["exchange_stop_price"] = 79000.0
    entries[-1]["exchange_tp_order_id"] = "TP2"  # executada
    entries[-1]["exchange_tp_price"] = 88000.0

    agent = _make_agent(entries)

    monkeypatch.setattr(ta, "HAS_STOP_ORDERS", True)
    monkeypatch.setattr(ta, "get_stop_orders", lambda s, status="active": {
        "success": True,
        "orders": [{"orderId": "SL9"}],
    })
    monkeypatch.setattr(ta, "cancel_stop_order", lambda order_id=None, client_oid=None: None)
    monkeypatch.setattr(ta, "_send_telegram_alert", lambda msg: None)

    agent._monitor_exchange_stop_orders()

    # Só o slot do TP é fechado; SL permanece no slot remanescente
    assert agent.db.record_trade.call_count == 1
    call = agent.db.record_trade.call_args_list[0]
    assert call.kwargs["metadata"]["closed_reason"] == "exchange_take_profit"
    assert call.kwargs["metadata"]["slot_buy_trade_id"] == 22

    assert len(agent.state.entries) == 1
    assert agent.state.entries[0]["trade_id"] == 21
    assert abs(agent.state.position - 0.001) < 1e-12


def test_boot_sync_cancels_orphan_stops_without_position(monkeypatch):
    agent = _make_agent([])

    monkeypatch.setattr(ta, "HAS_STOP_ORDERS", True)
    monkeypatch.setattr(ta, "get_stop_orders", lambda s, status="active": {
        "success": True,
        "orders": [{"orderId": "ORPHAN1", "clientOid": "btc_sl_1_123"}],
    })
    cancel_all = MagicMock()
    monkeypatch.setattr(ta, "cancel_all_stop_orders", cancel_all)
    alerts = []
    monkeypatch.setattr(ta, "_send_telegram_alert", lambda msg: alerts.append(msg))

    agent._sync_exchange_stop_orders_on_boot()

    cancel_all.assert_called_once_with("BTC-USDT")
    assert len(alerts) == 1


def test_boot_sync_readopts_active_stops_with_position(monkeypatch):
    entries = [{"trade_id": 31, "price": 80000.0, "size": 0.002}]
    agent = _make_agent(entries)

    monkeypatch.setattr(ta, "HAS_STOP_ORDERS", True)
    monkeypatch.setattr(ta, "get_stop_orders", lambda s, status="active": {
        "success": True,
        "orders": [
            {"orderId": "SL-NEW", "clientOid": "btc_sl_5_999", "stopPrice": "79500"},
            {"orderId": "TP-NEW", "clientOid": "btc_tp_5_999", "stopPrice": "88500"},
        ],
    })
    monkeypatch.setattr(ta, "cancel_all_stop_orders", MagicMock())
    monkeypatch.setattr(ta, "_send_telegram_alert", lambda msg: None)

    agent._sync_exchange_stop_orders_on_boot()

    assert agent.state.entries[0]["exchange_stop_order_id"] == "SL-NEW"
    assert agent.state.entries[0]["exchange_stop_price"] == 79500.0
    assert agent.state.entries[0]["exchange_tp_order_id"] == "TP-NEW"
