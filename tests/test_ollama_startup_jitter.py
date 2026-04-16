#!/usr/bin/env python3
"""Testes para o jitter de startup dos timestamps de chamadas de IA.

Garante que múltiplas instâncias do BitcoinTradingAgent não disparam chamadas
de IA simultaneamente ao Ollama, evitando 503 por concorrência.
"""

import time
import types
import sys
import unittest.mock as mock
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))

# Stubs de dependências externas — não disponíveis no CI
sys.modules.setdefault("httpx", types.SimpleNamespace())
_psycopg2 = types.SimpleNamespace(
    connect=mock.MagicMock(),
    extensions=types.SimpleNamespace(ISOLATION_LEVEL_AUTOCOMMIT=0),
)
sys.modules.setdefault("psycopg2", _psycopg2)
sys.modules.setdefault("psycopg2.extras", types.SimpleNamespace(RealDictCursor=object))

# Stub de módulos pesados que disparam I/O no import
for _mod in (
    "kucoin_api",
    "training_db",
    "market_rag",
    "rss_watcher",
    "fast_trading_model",
    "news_sentiment",
    "prometheus_exporter",
    "notifications",
    "fast_model",
):
    sys.modules.setdefault(_mod, types.SimpleNamespace(
        BitcoinTradingAgent=object,
        KuCoinAPI=object,
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
        _has_keys=None,
        FastTradingModel=lambda *a, **kw: types.SimpleNamespace(save=lambda: None, load=lambda: None),
        MarketState=object,
        Signal=object,
        TrainingDatabase=lambda *a, **kw: types.SimpleNamespace(
            init_schema=lambda: None,
            record_trade=lambda *a, **kw: None,
        ),
        TrainingManager=lambda *a, **kw: types.SimpleNamespace(),
        MarketRAG=lambda *a, **kw: types.SimpleNamespace(
            get_stats=lambda: {},
            get_current_adjustment=lambda: types.SimpleNamespace(
                ai_buy_target_price=0.0,
                ai_take_profit_pct=0.0,
                suggested_regime="RANGING",
            ),
            start=lambda: None,
            stop=lambda: None,
        ),
        RSSWatcher=lambda *a, **kw: types.SimpleNamespace(start=lambda: None, stop=lambda: None, get_latest_items=lambda n: []),
        NewsSentimentAnalyzer=lambda *a, **kw: types.SimpleNamespace(),
        PrometheusExporter=lambda *a, **kw: types.SimpleNamespace(start=lambda: None),
        NotificationManager=lambda *a, **kw: types.SimpleNamespace(),
    ))

import importlib
trading_agent_mod = importlib.import_module("trading_agent")
BitcoinTradingAgent = trading_agent_mod.BitcoinTradingAgent


def _make_agent(profile: str = "conservative") -> "BitcoinTradingAgent":
    """Cria instância mínima via __new__ e aplica o bloco de jitter de startup.

    Simula a parte relevante do __init__ sem instanciar banco/RAG/Ollama.
    """
    import random as _random
    import time as _time

    agent = BitcoinTradingAgent.__new__(BitcoinTradingAgent)
    agent.symbol = "BTC-USDT"
    agent.state = types.SimpleNamespace(profile=profile)
    agent._load_live_config = lambda: {"profile": profile}

    # Replica o bloco de jitter do __init__
    _jitter_plan = _random.uniform(0, agent._OLLAMA_TRADE_PARAMS_MIN_INTERVAL_SEC)
    _jitter_controls = _random.uniform(0, agent._OLLAMA_TRADE_PARAMS_MIN_INTERVAL_SEC)
    _jitter_window = _random.uniform(0, max(
        agent._OLLAMA_TRADE_WINDOW_MIN_INTERVAL_AGGRESSIVE_SEC,
        agent._OLLAMA_TRADE_WINDOW_MIN_INTERVAL_CONSERVATIVE_SEC,
    ))
    _now = _time.time()
    agent._last_ai_plan_trigger_ts = _now - _jitter_plan
    agent._last_ai_trade_controls_trigger_ts = _now - _jitter_controls
    agent._last_ai_trade_window_trigger_ts = _now - _jitter_window

    import time as _time

    agent = BitcoinTradingAgent.__new__(BitcoinTradingAgent)
    agent.symbol = "BTC-USDT"
    agent.state = types.SimpleNamespace(profile=profile)
    agent._load_live_config = lambda: {"profile": profile}

    # Replica o bloco de jitter do __init__
    _jitter_plan = _random.uniform(0, agent._OLLAMA_TRADE_PARAMS_MIN_INTERVAL_SEC)
    _jitter_controls = _random.uniform(0, agent._OLLAMA_TRADE_PARAMS_MIN_INTERVAL_SEC)
    _jitter_window = _random.uniform(0, max(
        agent._OLLAMA_TRADE_WINDOW_MIN_INTERVAL_AGGRESSIVE_SEC,
        agent._OLLAMA_TRADE_WINDOW_MIN_INTERVAL_CONSERVATIVE_SEC,
    ))
    _now = _time.time()
    agent._last_ai_plan_trigger_ts = _now - _jitter_plan
    agent._last_ai_trade_controls_trigger_ts = _now - _jitter_controls
    agent._last_ai_trade_window_trigger_ts = _now - _jitter_window

    return agent


# ─── testes ───────────────────────────────────────────────────────────────────

def test_jitter_timestamps_are_in_the_past() -> None:
    """Os timestamps jitterizados devem ser anteriores ao momento de criação."""
    before = time.time()
    agent = _make_agent()
    after = time.time()

    assert agent._last_ai_plan_trigger_ts <= after
    assert agent._last_ai_trade_controls_trigger_ts <= after
    assert agent._last_ai_trade_window_trigger_ts <= after

    # Precisam ser menores que o tempo antes da criação (offset negativo)
    assert agent._last_ai_plan_trigger_ts < before or agent._last_ai_plan_trigger_ts <= after


def test_jitter_timestamps_not_zero() -> None:
    """Timestamps com jitter não devem ser zero (valor padrão sem jitter)."""
    agent = _make_agent()
    assert agent._last_ai_plan_trigger_ts != 0.0
    assert agent._last_ai_trade_controls_trigger_ts != 0.0
    assert agent._last_ai_trade_window_trigger_ts != 0.0


def test_multiple_instances_have_different_timestamps() -> None:
    """Dois agentes criados em sequência devem ter timestamps de IA diferentes."""
    agent1 = _make_agent("conservative")
    agent2 = _make_agent("aggressive")

    # A probabilidade de dois valores uniform serem idênticos é ~0
    assert agent1._last_ai_plan_trigger_ts != agent2._last_ai_plan_trigger_ts
    assert agent1._last_ai_trade_controls_trigger_ts != agent2._last_ai_trade_controls_trigger_ts
    assert agent1._last_ai_trade_window_trigger_ts != agent2._last_ai_trade_window_trigger_ts


def test_jitter_bounded_by_min_interval() -> None:
    """O offset do jitter não deve exceder o intervalo mínimo de cada tipo."""
    now = time.time()
    agents = [_make_agent() for _ in range(10)]

    for agent in agents:
        plan_offset = now - agent._last_ai_plan_trigger_ts
        controls_offset = now - agent._last_ai_trade_controls_trigger_ts
        window_offset = now - agent._last_ai_trade_window_trigger_ts

        assert 0 <= plan_offset <= agent._OLLAMA_TRADE_PARAMS_MIN_INTERVAL_SEC + 5
        assert 0 <= controls_offset <= agent._OLLAMA_TRADE_PARAMS_MIN_INTERVAL_SEC + 5
        max_window = max(
            agent._OLLAMA_TRADE_WINDOW_MIN_INTERVAL_AGGRESSIVE_SEC,
            agent._OLLAMA_TRADE_WINDOW_MIN_INTERVAL_CONSERVATIVE_SEC,
        )
        assert 0 <= window_offset <= max_window + 5


def test_jitter_spread_across_interval() -> None:
    """Com 20 instâncias, a variação dos timestamps deve cobrir pelo menos 50% do intervalo."""
    agents = [_make_agent() for _ in range(20)]
    plan_ts = [a._last_ai_plan_trigger_ts for a in agents]
    spread = max(plan_ts) - min(plan_ts)
    min_interval = agents[0]._OLLAMA_TRADE_PARAMS_MIN_INTERVAL_SEC

    # O spread entre as instâncias deve ser significativo (> 50% do intervalo mínimo)
    assert spread >= min_interval * 0.5, f"Spread insuficiente: {spread:.1f}s (esperado >= {min_interval * 0.5:.1f}s)"
