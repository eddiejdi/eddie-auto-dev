"""Testes do estimador de fee/spread (book mock)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))

from fee_spread_estimator import clear_fee_cache, estimate_leg, get_fee_pct


def test_get_fee_pct_fallback_and_cache():
    clear_fee_cache()
    fee = get_fee_pct("ETH-BTC", use_live=False, fallback=0.001)
    assert fee == 0.001
    fee2 = get_fee_pct("ETH-BTC", use_live=False, fallback=0.002)
    assert fee2 == 0.001  # cache


def test_estimate_leg_sell_walks_bids():
    clear_fee_cache()

    def fake_ob(symbol, depth=20):
        return {
            "bids": [(0.03, 2.0), (0.029, 5.0)],
            "asks": [(0.0301, 2.0)],
        }

    est = estimate_leg(
        "ETH-BTC",
        "sell",
        1.0,
        currency_in="ETH",
        currency_out="BTC",
        fee_pct=0.001,
        slip_buffer_pct=0.0,
        use_live_fees=False,
        get_orderbook_fn=fake_ob,
        get_symbol_meta_fn=lambda _s: {"baseMinSize": "0.0001"},
    )
    assert est.min_ok
    assert est.est_out > 0
    # 1 ETH @ 0.03 bid = 0.03 BTC gross * (1-0.001)
    assert abs(est.est_out - 0.03 * 0.999) < 1e-9


def test_estimate_leg_buy_walks_asks():
    clear_fee_cache()

    def fake_ob(symbol, depth=20):
        return {
            "bids": [(100.0, 1.0)],
            "asks": [(100.0, 10.0)],
        }

    est = estimate_leg(
        "BTC-USDT",
        "buy",
        100.0,  # USDT
        currency_in="USDT",
        currency_out="BTC",
        fee_pct=0.001,
        slip_buffer_pct=0.0,
        use_live_fees=False,
        get_orderbook_fn=fake_ob,
        get_symbol_meta_fn=lambda _s: {"minFunds": "1"},
    )
    assert est.min_ok
    # 100 USDT / 100 = 1 BTC gross * 0.999 fee
    assert abs(est.est_out - 0.999) < 1e-9
