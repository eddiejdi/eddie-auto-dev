#!/usr/bin/env python3
"""Testes para shadow/apply dos controles de risco sugeridos pelo Ollama."""

from types import SimpleNamespace
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))

# Se numpy não estiver instalado, pula o módulo inteiro (testes rodam no CI onde numpy está disponível)
try:
    import numpy as _np_check  # noqa: F401
except ModuleNotFoundError:
    pytest.skip("numpy não disponível neste ambiente", allow_module_level=True)

# Remove stub de numpy que test_ai_trade_window.py pode ter inserido via setdefault
# (MagicMock retorna True para qualquer hasattr; usar isinstance para detectar mock)
import unittest.mock as _mock_mod
if isinstance(sys.modules.get("numpy"), _mock_mod.MagicMock):
    sys.modules.pop("numpy", None)

# Remove stub que testes anteriores podem ter inserido para que a importação real aconteça
sys.modules.pop("market_rag", None)

from market_rag import MarketRAG, RegimeAdjustment, VectorStore


@pytest.fixture
def rag(monkeypatch):
    monkeypatch.setattr(MarketRAG, "_save_adjustments", lambda self: None)
    monkeypatch.setattr(VectorStore, "load", lambda self, *a, **kw: False)
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
    # Isolamento por símbolo+perfil (evita contaminação BTC/ETH/SOL/DOGE)
    assert rag.adjustments_file.name == "regime_adjustments_BTC-USDT_aggressive.json"


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
    assert adj.ollama_suggested_max_positions == 10
    assert adj.applied_max_positions == 10


def test_apply_mode_allows_ai_to_raise_max_positions_above_baseline(rag):
    adj = rag.set_ollama_trade_controls(
        {
            "min_confidence": 0.68,
            "min_trade_interval": 180,
            "max_position_pct": 0.25,
            "max_positions": 9,
            "rationale": "raise max positions",
        },
        mode="apply",
        trigger="periodic",
        model="phi4-mini:latest",
    )

    assert adj.baseline_max_positions == 4
    assert adj.ollama_suggested_max_positions == 9
    assert adj.applied_max_positions == 9


def test_aggressive_ai_authority_full_blend_applies_suggestion(rag):
    """Perfil aggressive em teste: blend=1.0 → applied == suggested (clamped)."""
    rag.set_trading_context(
        avg_entry_price=0.0,
        position_count=0,
        usdt_balance=1000.0,
        max_position_pct=0.30,
        max_positions=4,
        profile="aggressive",
        guardrails_min_sell_pnl_pct=0.003,
        ai_trade_controls={
            "enabled": True,
            "mode": "apply",
            "apply_blend_confidence": 1.0,
            "apply_blend_interval": 1.0,
            "apply_blend_sell_pnl": 1.0,
            "min_confidence_delta": 0.15,
            "min_confidence_floor": 0.45,
            "min_confidence_ceiling": 0.80,
            "min_sell_pnl_pct_floor": 0.002,
            "min_sell_pnl_pct_ceiling": 0.008,
            "test_label": "aggressive_ai_authority_test",
        },
    )

    adj = rag.set_ollama_trade_controls(
        {
            "min_confidence": 0.48,
            "min_trade_interval": 90,
            "max_position_pct": 0.20,
            "max_positions": 6,
            "min_sell_pnl_pct": 0.002,
            "rationale": "more turnover",
        },
        mode="apply",
        trigger="periodic",
        model="trading-analyst",
    )

    # baseline conf 0.64, delta 0.15 → floor max(0.45, 0.49)=0.49
    assert adj.ollama_suggested_min_confidence == pytest.approx(0.49, abs=1e-3)
    assert adj.applied_min_confidence == pytest.approx(adj.ollama_suggested_min_confidence, abs=1e-3)
    assert adj.applied_min_trade_interval == adj.ollama_suggested_min_trade_interval
    assert adj.applied_min_sell_pnl_pct == pytest.approx(0.002, abs=1e-6)
    assert "ai_authority:aggressive_ai_authority_test" in (adj.ollama_reason or "")


def test_default_policy_keeps_historical_blend_without_config(rag):
    """Sem bloco ai_trade_controls: mantém blend histórico 35%/50%."""
    rag.set_trading_context(
        avg_entry_price=0.0,
        position_count=0,
        usdt_balance=1000.0,
        max_position_pct=0.30,
        max_positions=4,
        profile="conservative",
    )
    policy = rag._resolve_ai_trade_control_policy()
    assert policy["enabled"] is False
    assert policy["apply_blend_confidence"] == pytest.approx(0.35)
    assert policy["apply_blend_sell_pnl"] == pytest.approx(0.50)


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
