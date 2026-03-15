#!/usr/bin/env python3
"""Regressões para contenção operacional e modo seguro de startup."""

from pathlib import Path
from types import SimpleNamespace
import os
import sys
import types

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))
sys.modules.setdefault(
    "httpx",
    types.SimpleNamespace(
        Client=object,
    ),
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
    types.SimpleNamespace(
        FastTradingModel=object,
        MarketState=object,
        Signal=object,
    ),
)

from trading_agent import BitcoinTradingAgent, TradeControls, _resolve_process_dry_run


def test_resolve_process_dry_run_allows_config_to_force_safe_mode() -> None:
    assert _resolve_process_dry_run(True, {"dry_run": True}) is True
    assert _resolve_process_dry_run(True, {"live_mode": False}) is True
    assert _resolve_process_dry_run(True, {"dry_run": False, "live_mode": True}) is False


def test_resolve_process_dry_run_never_forces_live_from_config() -> None:
    assert _resolve_process_dry_run(False, {"dry_run": False, "live_mode": True}) is True


def _agent_with_live_cfg(live_cfg):
    agent = BitcoinTradingAgent.__new__(BitcoinTradingAgent)
    agent.symbol = "BTC-USDT"
    agent.state = SimpleNamespace(
        profile=live_cfg.get("profile", "aggressive"),
        last_trade_time=0.0,
        position_count=0,
        position=0.0,
        entry_price=0.0,
        dry_run=False,
        last_sell_entry_price=0.0,
        target_sell_price=0.0,
        target_sell_reason="",
    )
    agent.market_rag = SimpleNamespace(
        get_current_adjustment=lambda: SimpleNamespace(
            ai_buy_target_price=0.0,
            ai_buy_target_reason="runtime-guard-test",
            ai_max_entries=1,
        )
    )
    agent.db = SimpleNamespace(
        count_trades_since=lambda **kwargs: 0,
        get_pnl_since=lambda **kwargs: 0.0,
    )
    agent._load_live_config = lambda: dict(live_cfg)
    agent._resolve_trade_controls = lambda rag_adj=None: TradeControls(
        min_confidence=0.50,
        min_trade_interval=0,
        max_position_pct=0.30,
        max_positions_cap=4,
        effective_max_positions=4,
        ai_controlled=False,
        ollama_mode="shadow",
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
    agent._resolve_buy_gate_limits = lambda rag_adj, signal: {
        "ai_buy_target": 0.0,
        "extra_discount_pct": 0.0,
        "uplift_pct": 0.0,
        "tolerance_pct": 0.0,
        "effective_buy_target": 0.0,
        "effective_buy_ceiling": 0.0,
        "trade_window": None,
        "window_entry_low": 0.0,
        "window_entry_high": 0.0,
        "used_trade_window": False,
    }
    agent._current_profile = lambda: live_cfg.get("profile", "aggressive")
    agent._sync_target_sell_with_ai = lambda reason_prefix="IA": None
    return agent


def test_check_can_trade_uses_live_daily_trade_limit() -> None:
    agent = _agent_with_live_cfg({"profile": "aggressive", "max_daily_trades": 0, "max_daily_loss": 50})
    agent.db = SimpleNamespace(
        count_trades_since=lambda **kwargs: 0,
        get_pnl_since=lambda **kwargs: 0.0,
    )
    signal = SimpleNamespace(action="BUY", confidence=0.80, price=70000.0, reason="unit")

    assert agent._check_can_trade(signal) is False


def test_check_can_trade_uses_live_daily_loss_limit() -> None:
    agent = _agent_with_live_cfg({"profile": "conservative", "max_daily_trades": 99, "max_daily_loss": 0})
    agent.db = SimpleNamespace(
        count_trades_since=lambda **kwargs: 0,
        get_pnl_since=lambda **kwargs: -0.01,
    )
    signal = SimpleNamespace(action="BUY", confidence=0.80, price=70000.0, reason="unit")

    assert agent._check_can_trade(signal) is False


def test_guardrails_active_allows_sell_when_minimum_guardrail_pnl_is_reached() -> None:
    agent = _agent_with_live_cfg(
        {
            "profile": "conservative",
            "max_daily_trades": 9999,
            "max_daily_loss": 0.085,
            "guardrails_active": True,
            "guardrails_positive_only_sells": True,
            "guardrails_min_sell_pnl_pct": 0.025,
        }
    )
    agent.state.position = 0.001
    agent.state.entry_price = 70000.0
    agent.state.target_sell_price = 72500.0
    signal = SimpleNamespace(action="SELL", confidence=0.40, price=71950.0, reason="unit")

    assert agent._check_can_trade(signal) is True


def test_guardrails_active_blocks_negative_sell_even_with_force_path() -> None:
    agent = _agent_with_live_cfg(
        {
            "profile": "aggressive",
            "max_daily_trades": 9999,
            "max_daily_loss": 0.03,
            "guardrails_active": True,
            "guardrails_positive_only_sells": True,
            "guardrails_min_sell_pnl_pct": 0.025,
            "min_net_profit": {"usd": 0.01, "pct": 0.0005},
            "stop_loss_pct": 0.02,
        }
    )
    agent.state.position = 0.001
    agent.state.entry_price = 70000.0
    signal = SimpleNamespace(action="SELL", confidence=1.0, price=69950.0, reason="AUTO_STOP_LOSS")

    assert agent._calculate_trade_size(signal, signal.price, force=True) == 0
