#!/usr/bin/env python3
"""Teste: garantir que BUY não é permitido quando preço >= last_sell_entry_price
"""
from types import SimpleNamespace
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))

# Stubs para evitar imports/IO externos ao importar trading_agent
import types
sys.modules.setdefault(
    "httpx",
    types.SimpleNamespace(Client=object),
)
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
sys.modules.setdefault(
    "market_rag",
    types.SimpleNamespace(MarketRAG=object),
)

from trading_agent import BitcoinTradingAgent


def _agent_stub():
    agent = BitcoinTradingAgent.__new__(BitcoinTradingAgent)
    agent.symbol = "BTC-USDT"
    agent.state = SimpleNamespace(
        last_sell_entry_price=70000.0,
        position=0.0,
        last_trade_time=0.0,
        entry_price=0.0,
        target_sell_price=0.0,
        target_sell_reason="",
        entries=[],
        dry_run=False,
        profile="default",
    )
    agent.market_rag = SimpleNamespace(get_current_adjustment=lambda: SimpleNamespace())
    agent._clear_trade_block = lambda: None
    agent._resolve_trade_controls = lambda rag_adj=None: SimpleNamespace(
        min_confidence=0.5, min_trade_interval=0, max_position_pct=0.5,
        max_positions_cap=3, effective_max_positions=3, ai_controlled=False, ollama_mode="shadow"
    )
    agent._analyze_signal_context = lambda rag_adj, signal: {
        "penalty_score": 0.0,
        "bonus_score": 0.0,
        "strong_bearish": False,
        "hard_block_buy": False,
        "net_score": 0.0,
        "penalties": [],
        "bonuses": [],
    }
    agent._get_guardrail_sell_verdict = lambda price: None
    agent._resolve_buy_gate_limits = lambda rag_adj, signal: {
        "ai_buy_target": 0.0,
        "extra_discount_pct": 0.0,
        "uplift_pct": 0.0,
        "tolerance_pct": 0.0,
        "effective_buy_target": 0.0,
        "base_buy_ceiling": 0.0,
        "effective_buy_ceiling": 0.0,
        "trade_window": None,
        "window_entry_low": 0.0,
        "window_entry_high": 0.0,
        "used_trade_window": False,
    }
    agent._get_profile_buy_profit_guard_cfg = lambda: {
        "min_projected_edge_pct": 0.0,
        "min_window_slack_pct": 0.0,
        "pressure": 0.0,
        "recent_pnl": 0.0,
        "losing_streak": 0,
    }
    agent.db = SimpleNamespace(count_trades_since=lambda **kwargs: 0, get_pnl_since=lambda **kwargs: 0.0)
    agent._load_live_config = lambda: {}
    agent._current_profile = lambda: "default"
    agent._sync_target_sell_with_ai = lambda reason_prefix="IA": None
    return agent


def test_block_buy_when_price_not_lower_than_last_sell():
    agent = _agent_stub()
    signal = SimpleNamespace(action="BUY", price=70000.0, confidence=0.9, reason="unit")

    assert agent._check_can_trade(signal) is False


def test_allow_buy_when_price_lower_than_last_sell():
    agent = _agent_stub()
    signal = SimpleNamespace(action="BUY", price=69999.0, confidence=0.9, reason="unit")

    assert agent._check_can_trade(signal) is True
