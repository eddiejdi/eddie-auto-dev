"""Leitura de saldo da subconta: key de sub não lista /sub-accounts."""
from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import patch

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
        get_balances=lambda **_k: [],
        get_balance=lambda *_a, **_k: 0.0,
        get_sub_account_balances=lambda: [],
        place_market_order=None,
        _has_keys=lambda: False,
        _send_telegram_alert=lambda *a, **kw: None,
    ),
)
sys.modules.setdefault("fast_model", types.SimpleNamespace(FastTradingModel=object, MarketState=object, Signal=object))
sys.modules.setdefault("training_db", types.SimpleNamespace(TrainingDatabase=object, TrainingManager=object))
sys.modules.setdefault("market_rag", types.SimpleNamespace(MarketRAG=object))

from position_manager_mixin import PositionManagerMixin


def _agent(sub: str = "BTCAgressive") -> PositionManagerMixin:
    agent = PositionManagerMixin.__new__(PositionManagerMixin)
    agent.symbol = "BTC-USDT"
    agent.config = {"kucoin_subaccount_name": sub}
    agent._load_live_config = lambda: agent.config
    return agent


def test_empty_master_listing_falls_back_to_authenticated_trade() -> None:
    agent = _agent()
    trade_rows = [
        {"currency": "USDT", "available": 30.0, "balance": 30.0, "holds": 0.0},
        {"currency": "BTC", "available": 0.0, "balance": 0.0, "holds": 0.0},
    ]
    with patch("kucoin_api.get_sub_account_balances", return_value=[]), patch(
        "kucoin_api.get_balances", return_value=trade_rows
    ) as gb:
        quote, base = agent._read_subaccount_spot_balances("USDT")
    assert quote == 30.0
    assert base == 0.0
    gb.assert_called_with(account_type="trade")


def test_master_listing_uses_named_sub() -> None:
    agent = _agent("BTCAgressive")
    rows = [
        {
            "sub_name": "BTCAgressive",
            "account_type": "trade",
            "currency": "USDT",
            "available": 29.5,
        },
        {
            "sub_name": "ETHAgressive",
            "account_type": "trade",
            "currency": "USDT",
            "available": 99.0,
        },
    ]
    with patch("kucoin_api.get_sub_account_balances", return_value=rows), patch(
        "kucoin_api.get_balances"
    ) as gb:
        quote, _base = agent._read_subaccount_spot_balances("USDT")
    assert quote == 29.5
    gb.assert_not_called()
