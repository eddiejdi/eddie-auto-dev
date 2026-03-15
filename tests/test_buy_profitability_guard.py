#!/usr/bin/env python3
"""Regressões para o buy guard econômico e anti-chase."""

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

from trading_agent import BitcoinTradingAgent, TradeControls


def _sell(pnl: float, pnl_pct: float) -> dict:
    return {
        "side": "sell",
        "pnl": pnl,
        "pnl_pct": pnl_pct,
    }


def _agent(*, profile: str = "conservative", guard_cfg=None, day_pnl: float = 0.0, recent_trades=None) -> BitcoinTradingAgent:
    guard_cfg = guard_cfg or {}
    recent_trades = recent_trades or []
    agent = BitcoinTradingAgent.__new__(BitcoinTradingAgent)
    agent.symbol = "BTC-USDT"
    agent.state = SimpleNamespace(
        profile=profile,
        last_trade_time=0.0,
        position_count=0,
        position=0.0,
        entry_price=0.0,
        dry_run=True,
        last_sell_entry_price=0.0,
        target_sell_price=0.0,
        target_sell_reason="",
    )
    agent.market_rag = SimpleNamespace(
        get_current_adjustment=lambda: SimpleNamespace(
            ai_buy_target_price=100.0,
            ai_buy_target_reason="unit",
            ai_take_profit_pct=0.004,
            ai_max_entries=4,
            suggested_regime="RANGING",
        )
    )
    agent.db = SimpleNamespace(
        count_trades_since=lambda **kwargs: 0,
        get_pnl_since=lambda **kwargs: day_pnl,
        get_recent_trades=lambda **kwargs: list(recent_trades),
    )
    agent._load_live_config = lambda: {
        "profile": profile,
        "max_daily_trades": 99,
        "max_daily_loss": 99,
        "buy_profit_guard": guard_cfg,
    }
    agent._current_profile = lambda: profile
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
    return agent


def _signal(price: float = 100.0) -> SimpleNamespace:
    return SimpleNamespace(
        action="BUY",
        confidence=0.80,
        price=price,
        reason="unit-test",
    )


def test_buy_blocks_when_projected_edge_is_below_guard() -> None:
    agent = _agent(guard_cfg={"min_projected_edge_pct": 0.0050, "min_window_slack_pct": 0.0})
    agent._resolve_buy_gate_limits = lambda rag_adj, signal: {
        "ai_buy_target": 100.0,
        "extra_discount_pct": 0.0,
        "uplift_pct": 0.0,
        "tolerance_pct": 0.0,
        "effective_buy_target": 100.0,
        "effective_buy_ceiling": 100.2,
        "trade_window": {"target_sell": 100.35},
        "window_entry_low": 99.9,
        "window_entry_high": 100.2,
        "used_trade_window": True,
    }

    assert agent._check_can_trade(_signal(price=100.0)) is False


def test_buy_blocks_when_price_is_at_window_ceiling() -> None:
    agent = _agent(guard_cfg={"min_projected_edge_pct": 0.0030, "min_window_slack_pct": 0.0003})
    agent._resolve_buy_gate_limits = lambda rag_adj, signal: {
        "ai_buy_target": 100.0,
        "extra_discount_pct": 0.0,
        "uplift_pct": 0.0,
        "tolerance_pct": 0.0,
        "effective_buy_target": 100.0,
        "effective_buy_ceiling": 100.2,
        "trade_window": {"target_sell": 100.60},
        "window_entry_low": 99.9,
        "window_entry_high": 100.0,
        "used_trade_window": True,
    }

    assert agent._check_can_trade(_signal(price=100.0)) is False


def test_buy_allows_when_edge_and_window_slack_are_sufficient() -> None:
    agent = _agent(guard_cfg={"min_projected_edge_pct": 0.0030, "min_window_slack_pct": 0.0003})
    agent._resolve_buy_gate_limits = lambda rag_adj, signal: {
        "ai_buy_target": 100.0,
        "extra_discount_pct": 0.0,
        "uplift_pct": 0.0,
        "tolerance_pct": 0.0,
        "effective_buy_target": 100.0,
        "effective_buy_ceiling": 100.3,
        "trade_window": {"target_sell": 100.70},
        "window_entry_low": 99.8,
        "window_entry_high": 100.20,
        "used_trade_window": True,
    }

    assert agent._check_can_trade(_signal(price=100.0)) is True


def test_guard_tightens_progressively_with_recent_losses() -> None:
    agent = _agent(
        profile="aggressive",
        day_pnl=-0.0900,
        recent_trades=[
            _sell(-0.0250, -0.12),
            _sell(-0.0210, -0.10),
            _sell(-0.0180, -0.09),
            _sell(0.0040, 0.02),
        ],
        guard_cfg={
            "min_projected_edge_pct": 0.0045,
            "min_window_slack_pct": 0.0002,
            "loss_budget_usd": 0.0600,
            "avg_loss_pct_scale": 0.0010,
        },
    )

    guard = agent._get_profile_buy_profit_guard_cfg()

    assert guard["pressure"] > 0.55
    assert guard["losing_streak"] == 3
    assert guard["min_projected_edge_pct"] > guard["base_min_projected_edge_pct"]
    assert guard["min_window_slack_pct"] > guard["base_min_window_slack_pct"]


def test_guard_stays_at_base_when_recent_performance_is_positive() -> None:
    agent = _agent(
        profile="conservative",
        day_pnl=0.0400,
        recent_trades=[
            _sell(0.0200, 0.10),
            _sell(0.0150, 0.08),
            _sell(0.0080, 0.05),
        ],
        guard_cfg={
            "min_projected_edge_pct": 0.0050,
            "min_window_slack_pct": 0.0003,
            "loss_budget_usd": 0.0500,
        },
    )

    guard = agent._get_profile_buy_profit_guard_cfg()

    assert guard["pressure"] == 0.0
    assert guard["min_projected_edge_pct"] == guard["base_min_projected_edge_pct"]
    assert guard["min_window_slack_pct"] == guard["base_min_window_slack_pct"]


def test_buy_blocks_when_dynamic_loss_pressure_raises_min_edge() -> None:
    agent = _agent(
        profile="aggressive",
        day_pnl=-0.1200,
        recent_trades=[
            _sell(-0.0300, -0.14),
            _sell(-0.0260, -0.11),
            _sell(-0.0240, -0.10),
            _sell(-0.0190, -0.09),
        ],
        guard_cfg={
            "min_projected_edge_pct": 0.0045,
            "min_window_slack_pct": 0.0002,
            "loss_budget_usd": 0.0400,
            "avg_loss_pct_scale": 0.0010,
            "max_extra_projected_edge_pct": 0.0030,
            "max_extra_window_slack_pct": 0.0008,
        },
    )
    agent._resolve_buy_gate_limits = lambda rag_adj, signal: {
        "ai_buy_target": 100.0,
        "extra_discount_pct": 0.0,
        "uplift_pct": 0.0,
        "tolerance_pct": 0.0,
        "effective_buy_target": 100.0,
        "effective_buy_ceiling": 100.4,
        "trade_window": {"target_sell": 100.54},
        "window_entry_low": 99.7,
        "window_entry_high": 100.25,
        "used_trade_window": True,
    }

    assert agent._check_can_trade(_signal(price=100.0)) is False
