#!/usr/bin/env python3
"""Regressões para reward tuning do trading agent."""

from pathlib import Path
import os
import sys

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))

from backfill_retro_rewards import retro_score_sample
from training_db import TrainingManager


def _state(*, price: float = 100.0, trend: float = 0.0, rsi: float = 50.0,
           momentum: float = 0.0, imbalance: float = 0.0, flow: float = 0.0,
           volatility: float = 0.01) -> dict:
    return {
        "price": price,
        "trend": trend,
        "rsi": rsi,
        "momentum": momentum,
        "orderbook_imbalance": imbalance,
        "trade_flow": flow,
        "volatility": volatility,
    }


def test_buy_reward_prefers_regime_alignment() -> None:
    bullish_state = _state(trend=0.25, rsi=32, momentum=0.02, imbalance=0.20, flow=0.15)
    bearish_state = _state(trend=-0.25, rsi=32, momentum=0.02, imbalance=0.20, flow=0.15)
    next_state = _state(price=100.8)

    _, bullish_reward, bullish_ctx = TrainingManager._retro_score_sample(bullish_state, next_state)
    _, bearish_reward, bearish_ctx = TrainingManager._retro_score_sample(bearish_state, next_state)

    assert bullish_ctx["regime"] == "BULLISH"
    assert bearish_ctx["regime"] == "BEARISH"
    assert bullish_reward > bearish_reward
    assert "regime_aligned" in bullish_ctx["bonuses"]
    assert "counter_regime_buy" in bearish_ctx["penalties"]


def test_hold_reward_is_promoted_in_ranging_regime() -> None:
    current = _state(trend=0.01, momentum=0.0004, imbalance=0.01, flow=0.01)
    next_state = _state(price=100.1)

    action, reward, ctx = TrainingManager._retro_score_sample(current, next_state)

    assert action == 0
    assert ctx["regime"] == "RANGING"
    assert reward >= 0.07
    assert "range_patience" in ctx["bonuses"]


def test_backfill_scoring_matches_training_manager() -> None:
    current = _state(trend=-0.20, rsi=69, momentum=-0.03, imbalance=-0.2, flow=-0.2, volatility=0.03)
    next_state = _state(price=99.1)

    action, reward, ctx = TrainingManager._retro_score_sample(current, next_state)
    retro = retro_score_sample(current, next_state)

    assert retro.best_action == action
    assert retro.reward == reward
    assert retro.penalties == ctx["penalties"]
    assert retro.bonuses == ctx["bonuses"]
