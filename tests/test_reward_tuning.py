#!/usr/bin/env python3
"""Regressões para reward tuning do trading agent."""

from pathlib import Path
import os
import sys
import types

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

# Mock psycopg2 so the module can be imported in CI without a real DB driver installed.
# __path__ is required so Python treats psycopg2 as a package (enables submodule imports).
if "psycopg2" not in sys.modules or not hasattr(sys.modules["psycopg2"], "__path__"):
    _psycopg2_mock = types.ModuleType("psycopg2")
    _psycopg2_mock.__path__ = []  # marks it as a package
    _psycopg2_mock.__package__ = "psycopg2"
    _psycopg2_extras_mock = types.ModuleType("psycopg2.extras")
    _psycopg2_extras_mock.__package__ = "psycopg2"
    _psycopg2_pool_mock = types.ModuleType("psycopg2.pool")
    _psycopg2_pool_mock.__package__ = "psycopg2"
    setattr(_psycopg2_mock, "extras", _psycopg2_extras_mock)
    setattr(_psycopg2_mock, "pool", _psycopg2_pool_mock)
    sys.modules["psycopg2"] = _psycopg2_mock
    sys.modules["psycopg2.extras"] = _psycopg2_extras_mock
    sys.modules["psycopg2.pool"] = _psycopg2_pool_mock

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
