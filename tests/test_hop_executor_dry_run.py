"""Hop executor dry-run tests."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))

from hop_executor import execute, simulate
from route_graph import RouteLeg, RoutePlan


def _plan():
    return RoutePlan(
        asset_in="ETH",
        asset_out="BTC",
        amount_in=1.0,
        est_out=0.0299,
        total_cost_pct=0.0015,
        hops=1,
        path_assets=["ETH", "BTC"],
        legs=[
            RouteLeg(
                symbol="ETH-BTC",
                side="sell",
                currency_in="ETH",
                currency_out="BTC",
                amount_in=1.0,
                est_out=0.0299,
                cost_pct=0.0015,
                spread_bps=3.0,
                fee_pct=0.001,
                slip_bps=1.0,
            )
        ],
        via="direct",
        score=0.0015,
    )


def test_simulate_marks_simulated():
    res = simulate(_plan())
    assert res.success
    assert res.status == "simulated"
    assert res.amount_out == 0.0299
    assert res.legs[0].status == "simulated"


def test_execute_dry_run_delegates_to_simulate():
    res = execute(_plan(), dry_run=True)
    assert res.status == "simulated"
