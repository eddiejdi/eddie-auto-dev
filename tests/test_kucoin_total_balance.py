#!/usr/bin/env python3
"""Testes para a correção de detecção de depósitos em contas MAIN e TRADE."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, Mock

_BTC_DIR = Path(__file__).resolve().parent.parent / "btc_trading_agent"
if str(_BTC_DIR) not in sys.path:
    sys.path.insert(0, str(_BTC_DIR))

import kucoin_api


def test_get_total_balance_sums_main_and_trade() -> None:
    """get_total_balance deve somar MAIN + TRADE accounts."""
    with patch.object(kucoin_api, "get_balances") as mock_balances:
        def side_effect(account_type: str = "trade"):
            if account_type == "main":
                return [{"currency": "BTC", "available": 0.5}]
            elif account_type == "trade":
                return [{"currency": "BTC", "available": 0.3}]
            return []

        mock_balances.side_effect = side_effect
        total = kucoin_api.get_total_balance("BTC")

    assert total == 0.8, f"Expected 0.8 BTC, got {total}"


def test_get_total_balance_handles_missing_currency() -> None:
    """get_total_balance deve retornar 0 se currency não encontrada."""
    with patch.object(kucoin_api, "get_balances") as mock_balances:
        mock_balances.return_value = []
        total = kucoin_api.get_total_balance("XYZ")

    assert total == 0.0


def test_get_balance_still_uses_trade_only() -> None:
    """get_balance original deve continuar usando TRADE apenas."""
    with patch.object(kucoin_api, "get_balances") as mock_balances:
        def side_effect(account_type: str = "trade"):
            if account_type == "main":
                return [{"currency": "BTC", "available": 0.5}]
            elif account_type == "trade":
                return [{"currency": "BTC", "available": 0.3}]
            return []

        mock_balances.side_effect = side_effect
        balance = kucoin_api.get_balance("BTC")

    # get_balance should call get_balances() without specifying account_type,
    # which defaults to "trade"
    assert balance == 0.3, f"Expected 0.3 BTC (TRADE only), got {balance}"
