"""Testes do planejador de rotas intermoedas (sem rede)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))

from fee_spread_estimator import LegEstimate
from route_graph import RouteGraph, RouteOptions, compare_routes, find_best_route


def _symbols():
    return [
        {"symbol": "ETH-BTC", "baseCurrency": "ETH", "quoteCurrency": "BTC", "enableTrading": True},
        {"symbol": "ETH-USDT", "baseCurrency": "ETH", "quoteCurrency": "USDT", "enableTrading": True},
        {"symbol": "BTC-USDT", "baseCurrency": "BTC", "quoteCurrency": "USDT", "enableTrading": True},
        {"symbol": "SOL-USDT", "baseCurrency": "SOL", "quoteCurrency": "USDT", "enableTrading": True},
        {"symbol": "DOGE-BTC", "baseCurrency": "DOGE", "quoteCurrency": "BTC", "enableTrading": True},
        {"symbol": "DOGE-USDT", "baseCurrency": "DOGE", "quoteCurrency": "USDT", "enableTrading": True},
        {"symbol": "SOL-KCS", "baseCurrency": "SOL", "quoteCurrency": "KCS", "enableTrading": True},
        {"symbol": "BTC-KCS", "baseCurrency": "BTC", "quoteCurrency": "KCS", "enableTrading": True},
    ]


def _fake_estimate(symbol, side, amount_in, currency_in, currency_out, **kwargs):
    """Custos sintéticos: direto ETH-BTC barato; via USDT mais caro; KCS caro/fino."""
    fee = 0.001
    # encode preference in cost via est_out relative efficiency
    if symbol == "ETH-BTC" and side == "sell":
        # 1 ETH -> 0.03 BTC net of low friction
        est_out = amount_in * 0.03 * (1 - fee) * 0.999  # tiny slip
        cost = fee + 0.0003
        spread = 3.0
    elif symbol == "ETH-USDT" and side == "sell":
        est_out = amount_in * 2000 * (1 - fee)
        cost = fee + 0.00005
        spread = 0.5
    elif symbol == "BTC-USDT" and side == "buy":
        # spend USDT for BTC
        est_out = (amount_in / 65000) * (1 - fee)
        cost = fee + 0.00005
        spread = 0.5
    elif symbol == "SOL-USDT" and side == "sell":
        est_out = amount_in * 100 * (1 - fee)
        cost = fee + 0.0001
        spread = 1.0
    elif symbol == "DOGE-BTC" and side == "sell":
        est_out = amount_in * 1e-6 * (1 - fee) * 0.98  # worse slip
        cost = fee + 0.002
        spread = 20.0
    elif symbol == "DOGE-USDT" and side == "sell":
        est_out = amount_in * 0.08 * (1 - fee)
        cost = fee + 0.0001
        spread = 1.0
    elif symbol.endswith("-KCS") or symbol.startswith("KCS"):
        est_out = amount_in * 0.5 * (1 - fee)
        cost = fee + 0.01
        spread = 40.0
    else:
        # generic mid conversion
        est_out = amount_in * 0.99 * (1 - fee)
        cost = fee + 0.001
        spread = 5.0

    return LegEstimate(
        symbol=symbol,
        side=side,
        amount_in=amount_in,
        currency_in=currency_in,
        currency_out=currency_out,
        mid=1.0,
        bid=0.999,
        ask=1.001,
        spread_bps=spread,
        fee_pct=fee,
        slip_bps=cost * 5000,
        est_out=est_out,
        cost_pct=cost,
        min_ok=True,
    )


def test_eth_to_btc_prefers_direct_pair():
    g = RouteGraph(symbols=_symbols())
    opts = RouteOptions(min_pair_vol_usd=0, max_spread_bps=50, use_live_fees=False)
    best = find_best_route(
        "ETH", "BTC", 1.0, opts=opts, graph=g, estimate_leg_fn=_fake_estimate
    )
    assert best is not None
    assert best.hops == 1
    assert best.legs[0].symbol == "ETH-BTC"
    assert best.via == "direct"


def test_sol_to_btc_uses_usdt_not_kcs_when_exotic_off():
    g = RouteGraph(symbols=_symbols())
    opts = RouteOptions(
        min_pair_vol_usd=0,
        max_spread_bps=50,
        allow_exotic_hubs=False,
        use_live_fees=False,
        hubs=("USDT", "BTC", "ETH"),
    )
    best = find_best_route(
        "SOL", "BTC", 10.0, opts=opts, graph=g, estimate_leg_fn=_fake_estimate
    )
    assert best is not None
    assert best.hops == 2
    assert "USDT" in best.path_assets
    assert "KCS" not in best.path_assets


def test_compare_routes_returns_sorted_candidates():
    g = RouteGraph(symbols=_symbols())
    opts = RouteOptions(min_pair_vol_usd=0, max_spread_bps=50, use_live_fees=False)
    cands = compare_routes(
        "ETH", "BTC", 1.0, opts=opts, graph=g, estimate_leg_fn=_fake_estimate
    )
    assert len(cands) >= 2  # direct + via USDT
    scores = [c.score for c in cands]
    assert scores == sorted(scores)
