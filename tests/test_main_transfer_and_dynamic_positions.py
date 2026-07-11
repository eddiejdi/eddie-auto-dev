#!/usr/bin/env python3
"""Regressões: transferência MAIN→TRADE no loop e max_positions dinâmico pela IA."""

from pathlib import Path
from types import SimpleNamespace
import os
import sys
import types

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

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
        get_fills_for_order=lambda *a, **kw: {},
        _resolve_telegram_bot_token=lambda: "",
        _resolve_telegram_chat_id=lambda: "",
    ),
)
sys.modules.setdefault(
    "fast_model",
    types.SimpleNamespace(
        FastTradingModel=object,
        MarketState=object,
        Signal=object,
    ),
)
sys.modules.setdefault(
    "training_db",
    types.SimpleNamespace(TrainingDatabase=object, TrainingManager=object),
)

from trading_agent import BitcoinTradingAgent
from market_rag import RegimeAdjuster, RegimeAdjustment


def _agent(symbol: str = "USDT-BRL") -> BitcoinTradingAgent:
    agent = BitcoinTradingAgent.__new__(BitcoinTradingAgent)
    agent.symbol = symbol
    agent.config_name = "config_USDT_BRL_conservative.json"
    agent.state = SimpleNamespace(dry_run=False)
    agent._load_live_config = lambda: {
        "max_positions": 1,
        "max_position_pct": 0.15,
        "min_confidence": 0.6,
        "min_trade_interval": 900,
    }
    return agent


def test_auto_transfer_returns_true_on_success(monkeypatch) -> None:
    agent = _agent()
    calls: list[dict] = []

    def fake_get_balances(account_type: str = "trade"):
        if account_type == "main":
            return [
                {"currency": "USDT", "available": 0.0},
                {"currency": "BRL", "available": 150.0},
            ]
        return []

    def fake_inner_transfer(**kwargs):
        calls.append(kwargs)
        return {"success": True}

    monkeypatch.setattr("trading_agent.get_balances", fake_get_balances)
    monkeypatch.setattr("trading_agent.inner_transfer", fake_inner_transfer)

    transferred = agent._auto_transfer_and_sync()

    assert transferred is True
    assert len(calls) == 1
    assert calls[0]["currency"] == "BRL"
    assert calls[0]["from_account"] == "main"
    assert calls[0]["to_account"] == "trade"


def test_auto_transfer_returns_false_when_main_empty(monkeypatch) -> None:
    agent = _agent()

    monkeypatch.setattr(
        "trading_agent.get_balances",
        lambda account_type="trade": [],
    )

    assert agent._auto_transfer_and_sync() is False


def test_resolve_trade_controls_uses_ai_max_entries_over_static_config() -> None:
    agent = _agent()
    agent.market_rag = SimpleNamespace(
        get_current_adjustment=lambda: SimpleNamespace(
            similar_count=0,
            ai_max_entries=12,
            applied_max_positions=1,
            ollama_mode="shadow",
        )
    )

    controls = agent._resolve_trade_controls()

    assert controls.effective_max_positions == 12
    assert controls.max_positions_cap == 12


def test_resolve_trade_controls_ollama_apply_blends_ai_and_ollama() -> None:
    agent = _agent()
    agent.market_rag = SimpleNamespace(
        get_current_adjustment=lambda: SimpleNamespace(
            similar_count=5,
            ai_min_confidence=0.6,
            ai_min_trade_interval=300,
            ai_max_entries=16,
            applied_min_confidence=0.58,
            applied_min_trade_interval=420,
            applied_max_positions=8,
            applied_max_position_pct=0.12,
            ollama_mode="apply",
        )
    )

    controls = agent._resolve_trade_controls()

    assert controls.effective_max_positions == 8
    assert controls.ai_controlled is True


def test_resolve_trade_controls_scales_with_high_balance_via_rag() -> None:
    adjuster = RegimeAdjuster()
    adj = RegimeAdjustment(
        timestamp=0.0,
        symbol="USDT-BRL",
        suggested_regime="RANGING",
        regime_confidence=0.7,
        ai_aggressiveness=0.5,
    )

    adjuster._calculate_ai_position_size(
        adj,
        current_price=5.45,
        avg_entry_price=0.0,
        position_count=0,
        usdt_balance=1200.0,
    )

    assert adj.ai_max_entries >= 12