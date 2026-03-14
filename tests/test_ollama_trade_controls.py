#!/usr/bin/env python3
"""Testes para shadow/apply dos controles de risco sugeridos pelo Ollama."""

from types import SimpleNamespace
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))

from market_rag import MarketRAG, RegimeAdjustment, VectorStore


@pytest.fixture
def rag(monkeypatch):
    monkeypatch.setattr(MarketRAG, "_save_adjustments", lambda self: None)
    monkeypatch.setattr(VectorStore, "load", lambda self: None)
    instance = MarketRAG("BTC-USDT", profile="aggressive", recalibrate_interval=300, snapshot_interval=30)
    instance._current_adjustment = RegimeAdjustment(
        timestamp=1.0,
        symbol="BTC-USDT",
        ai_min_confidence=0.64,
        ai_min_trade_interval=150,
        ai_max_entries=12,
    )
    instance.set_trading_context(
        avg_entry_price=0.0,
        position_count=0,
        usdt_balance=1000.0,
        max_position_pct=0.30,
        max_positions=4,
        profile="aggressive",
    )
    return instance


def test_profile_uses_isolated_adjustments_file(rag):
    assert rag.adjustments_file.name == "regime_adjustments_aggressive.json"


def test_shadow_mode_preserves_baseline(rag):
    adj = rag.set_ollama_trade_controls(
        {
            "min_confidence": 0.74,
            "min_trade_interval": 240,
            "max_position_pct": 0.25,
            "max_positions": 3,
            "rationale": "shadow test",
        },
        mode="shadow",
        trigger="rss",
        model="phi4-mini:latest",
    )

    assert adj.ollama_mode == "shadow"
    assert adj.baseline_min_confidence == pytest.approx(0.64)
    assert adj.applied_min_confidence == pytest.approx(0.64)
    assert adj.applied_min_trade_interval == 150
    assert adj.applied_max_position_pct == pytest.approx(0.30)
    assert adj.applied_max_positions == 4
    assert adj.ollama_suggested_min_confidence == pytest.approx(0.74)
    assert adj.ollama_suggested_min_trade_interval == 240


def test_apply_mode_blends_and_clamps(rag):
    adj = rag.set_ollama_trade_controls(
        {
            "min_confidence": 0.95,
            "min_trade_interval": 600,
            "max_position_pct": 0.90,
            "max_positions": 10,
            "rationale": "apply test",
        },
        mode="apply",
        trigger="periodic",
        model="phi4-mini:latest",
    )

    assert adj.ollama_mode == "apply"
    assert adj.ollama_suggested_min_confidence == pytest.approx(0.74)
    assert adj.applied_min_confidence == pytest.approx(0.675, abs=1e-3)
    assert adj.ollama_suggested_min_trade_interval == 270
    assert adj.applied_min_trade_interval == 210
    assert adj.ollama_suggested_max_position_pct == pytest.approx(0.30)
    assert adj.applied_max_position_pct == pytest.approx(0.30)
    assert adj.ollama_suggested_max_positions == 4
    assert adj.applied_max_positions == 4


def test_recalibrate_reapplies_last_ollama_controls(rag, monkeypatch):
    rag.set_ollama_trade_controls(
        {
            "min_confidence": 0.70,
            "min_trade_interval": 180,
            "max_position_pct": 0.20,
            "max_positions": 2,
            "rationale": "persist test",
        },
        mode="apply",
        trigger="regime_change",
        model="phi4-mini:latest",
    )

    snapshot = SimpleNamespace(price=70_000.0, to_embedding=lambda: [0.0] * 24)
    monkeypatch.setattr(rag, "_update_outcomes", lambda: None)
    monkeypatch.setattr(rag.collector, "collect_snapshot", lambda: snapshot)
    monkeypatch.setattr(rag.store, "search", lambda query, top_k: [])
    monkeypatch.setattr(
        rag.adjuster,
        "calculate_adjustment",
        lambda current_snapshot, similar_results: RegimeAdjustment(
            timestamp=2.0,
            symbol="BTC-USDT",
            ai_min_confidence=0.60,
            ai_min_trade_interval=180,
            ai_max_entries=12,
        ),
    )
    monkeypatch.setattr(rag.adjuster, "_calculate_ai_buy_target", lambda *args, **kwargs: None)
    monkeypatch.setattr(rag.adjuster, "_calculate_ai_take_profit", lambda *args, **kwargs: None)
    monkeypatch.setattr(rag.adjuster, "_calculate_ai_position_size", lambda *args, **kwargs: None)

    adj = rag.force_recalibrate()

    assert adj.ollama_mode == "apply"
    assert adj.applied_min_confidence > adj.baseline_min_confidence
    assert adj.applied_max_position_pct == pytest.approx(0.20)
    assert adj.applied_max_positions == 2
