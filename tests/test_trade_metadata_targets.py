#!/usr/bin/env python3
"""Regressões para persistência de target SELL no metadata das trades."""

from pathlib import Path
from types import SimpleNamespace
import os
import sys
import types

import unittest.mock as _mock


os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))
sys.modules.setdefault("httpx", types.SimpleNamespace())

_numpy_mock = _mock.MagicMock()
_numpy_mock.isscalar = lambda x: isinstance(x, (int, float, complex, bool))
_numpy_mock.bool_ = bool
sys.modules.setdefault("numpy", _numpy_mock)

_psycopg2_mock = types.ModuleType("psycopg2")
_psycopg2_mock.extras = types.SimpleNamespace(RealDictCursor=object)
_psycopg2_mock.pool = types.SimpleNamespace(ThreadedConnectionPool=object)
sys.modules.setdefault("psycopg2", _psycopg2_mock)
sys.modules.setdefault("psycopg2.extras", _psycopg2_mock.extras)
sys.modules.setdefault("psycopg2.pool", _psycopg2_mock.pool)

sys.modules.setdefault(
    "training_db",
    types.SimpleNamespace(
        TrainingDatabase=object,
        TrainingManager=object,
    ),
)
sys.modules.setdefault("market_rag", types.SimpleNamespace(MarketRAG=object))
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

from trading_agent import BitcoinTradingAgent


def _agent() -> BitcoinTradingAgent:
    agent = BitcoinTradingAgent.__new__(BitcoinTradingAgent)
    agent.symbol = "BTC-USDT"
    agent.state = SimpleNamespace(
        dry_run=False,
        profile="conservative",
        position=0.001,
        entry_price=70000.0,
        target_sell_price=71050.0,
        target_sell_reason="rag_tp",
    )
    agent._load_live_config = lambda: {"profile": "conservative"}
    agent._current_profile = lambda: "conservative"
    agent.db = _mock.MagicMock()
    return agent


def test_build_trade_metadata_includes_target_sell_keys() -> None:
    """BUY/SYNC deve persistir target_sell_* no metadata para o dashboard."""
    agent = _agent()

    metadata = agent._build_trade_metadata({"source": "kucoin_live", "orderId": "abc"})

    assert metadata is not None
    assert metadata["source"] == "kucoin_live"
    assert metadata["orderId"] == "abc"
    assert metadata["target_sell_price"] == 71050.0
    assert metadata["target_sell_trigger_price"] == 71050.0
    assert metadata["target_sell_reason"] == "rag_tp"


def test_build_trade_metadata_includes_exit_reason_for_sell() -> None:
    """SELL deve persistir exit_reason para preencher a tabela de trades."""
    agent = _agent()
    signal = SimpleNamespace(reason="AUTO_TAKE_PROFIT (+1.88%, TP=1.50%)")

    metadata = agent._build_trade_metadata(
        {"source": "kucoin_live", "orderId": "sell-1"},
        signal=signal,
        include_exit_reason=True,
    )

    assert metadata is not None
    assert metadata["exit_reason"] == "AUTO_TAKE_PROFIT (+1.88%, TP=1.50%)"
    assert metadata["target_sell_price"] == 71050.0


def test_sync_target_sell_with_ai_stamps_latest_open_buy() -> None:
    """Recalibração da IA deve atualizar o BUY aberto mais recente no DB."""
    agent = _agent()
    agent.state.target_sell_price = 72100.0
    agent.state.target_sell_reason = "older_tp"
    agent.db.get_recent_trades.return_value = [
        {"id": 42, "side": "buy"},
        {"id": 41, "side": "buy"},
    ]
    agent.market_rag = SimpleNamespace(
        get_current_adjustment=lambda: SimpleNamespace(
            ai_take_profit_pct=0.012,
            ai_take_profit_reason="tightened_tp",
            suggested_regime="RANGING",
        )
    )

    agent._sync_target_sell_with_ai("IA")

    agent.db.merge_trade_metadata.assert_called_once()
    trade_id, metadata = agent.db.merge_trade_metadata.call_args.args
    assert trade_id == 42
    assert metadata["target_sell_price"] == 71050.0
    assert metadata["target_sell_trigger_price"] == 71050.0
    assert metadata["target_sell_reason"] == "tightened_tp"