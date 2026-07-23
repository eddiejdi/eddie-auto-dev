"""Testes do sync de taxa taker live."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))

from fee_rate_sync import apply_fee_pct, resolve_live_fee_pct


def test_resolve_prefers_trade_fees():
    def fake_trade_fees(sym):
        return [{"symbol": "BTC-USDT", "takerFeeRate": "0.0008", "makerFeeRate": "0.0008"}]

    fee, src = resolve_live_fee_pct(
        "BTC-USDT",
        fallback=0.001,
        get_trade_fees_fn=fake_trade_fees,
        get_base_fee_fn=lambda _t: {"success": True, "takerFeeRate": 0.001},
    )
    assert abs(fee - 0.0008) < 1e-12
    assert src == "trade_fees"


def test_resolve_falls_back_to_base_fee():
    fee, src = resolve_live_fee_pct(
        "BTC-USDT",
        fallback=0.001,
        get_trade_fees_fn=lambda _s: [],
        get_base_fee_fn=lambda _t: {"success": True, "takerFeeRate": 0.0009},
    )
    assert abs(fee - 0.0009) < 1e-12
    assert src == "base_fee"


def test_resolve_fallback():
    fee, src = resolve_live_fee_pct(
        "BTC-USDT",
        fallback=0.001,
        get_trade_fees_fn=lambda _s: (_ for _ in ()).throw(RuntimeError("x")),
        get_base_fee_fn=lambda _t: {"success": False},
    )
    assert fee == 0.001
    assert src == "fallback"


def test_apply_fee_pct_change_and_clamp():
    v, ch = apply_fee_pct(0.001, 0.0008)
    assert ch is True
    assert abs(v - 0.0008) < 1e-12
    v2, ch2 = apply_fee_pct(0.001, 0.5)  # invalid high
    assert ch2 is False
    assert abs(v2 - 0.001) < 1e-12
