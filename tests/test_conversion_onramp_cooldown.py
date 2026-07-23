"""Testes: cooldown/dedupe do on-ramp BRL e diagnóstico no_route."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))

from conversion_mixin import ConversionMixin  # noqa: E402
from fee_spread_estimator import LegEstimate  # noqa: E402
from route_graph import (  # noqa: E402
    RouteGraph,
    RouteOptions,
    diagnose_routes,
    find_best_route,
)


class _Agent(ConversionMixin):
    def __init__(self, config, db, profile="conservative", symbol="USDT-BRL"):
        self.config = config
        self.db = db
        self.state = SimpleNamespace(profile=profile, dry_run=False)
        self.symbol = symbol


def test_onramp_skips_when_pending():
    db = MagicMock()
    db.has_pending_conversion.return_value = True
    agent = _Agent({"conversion": {"enabled": True, "role": "owner"}}, db)
    reason = agent._onramp_should_skip("USDT", 900.0, cooldown_seconds=3600, balance_delta_pct=5.0)
    assert reason == "pending_exists"
    db.get_recent_conversion.assert_not_called()


def test_onramp_skips_within_cooldown_same_balance():
    db = MagicMock()
    db.has_pending_conversion.return_value = False
    db.get_recent_conversion.return_value = {
        "id": 99,
        "amount_in": 948.68,
        "status": "failed",
    }
    agent = _Agent({"conversion": {"enabled": True, "role": "owner"}}, db)
    reason = agent._onramp_should_skip("USDT", 948.68, cooldown_seconds=21600, balance_delta_pct=5.0)
    assert reason is not None
    assert "cooldown" in reason
    assert "99" in reason


def test_onramp_allows_when_balance_delta_exceeds_threshold():
    db = MagicMock()
    db.has_pending_conversion.return_value = False
    db.get_recent_conversion.return_value = {
        "id": 99,
        "amount_in": 900.0,
        "status": "done",
    }
    agent = _Agent({"conversion": {"enabled": True, "role": "owner"}}, db)
    # +10% balance => new deposit
    reason = agent._onramp_should_skip("USDT", 1000.0, cooldown_seconds=21600, balance_delta_pct=5.0)
    assert reason is None


def test_onramp_enqueue_live_dry_run_false(monkeypatch):
    db = MagicMock()
    db.has_pending_conversion.return_value = False
    db.get_recent_conversion.return_value = None
    db.enqueue_conversion.return_value = 777

    monkeypatch.setattr(
        "kucoin_api.get_balance",
        lambda asset: 200.0 if asset == "BRL" else 0.0,
        raising=False,
    )
    # conversion_mixin imports get_balance inside the method
    import conversion_mixin as cm

    monkeypatch.setattr(cm, "logger", MagicMock())

    # Patch the import used inside the method via kucoin_api module
    import types

    fake_kucoin = types.ModuleType("kucoin_api")
    fake_kucoin.get_balance = lambda asset: 200.0 if asset == "BRL" else 0.0
    monkeypatch.setitem(sys.modules, "kucoin_api", fake_kucoin)

    agent = _Agent(
        {
            "conversion": {
                "enabled": True,
                "role": "owner",
                "dry_run": False,
                "min_brl_onramp": 50,
            }
        },
        db,
    )
    agent._maybe_enqueue_brl_onramp()
    db.enqueue_conversion.assert_called_once()
    kwargs = db.enqueue_conversion.call_args.kwargs
    assert kwargs.get("dry_run") is False or (
        len(db.enqueue_conversion.call_args.args) == 0
        and db.enqueue_conversion.call_args.kwargs["dry_run"] is False
    )
    # amount_in is positional or kw
    call = db.enqueue_conversion.call_args
    assert call.kwargs.get("dry_run") is False
    assert call.kwargs.get("requested_by") == "deposit_onramp"


def _brl_symbols():
    return [
        {
            "symbol": "USDT-BRL",
            "baseCurrency": "USDT",
            "quoteCurrency": "BRL",
            "enableTrading": True,
        },
        {
            "symbol": "BTC-USDT",
            "baseCurrency": "BTC",
            "quoteCurrency": "USDT",
            "enableTrading": True,
        },
        {
            "symbol": "BTC-BRL",
            "baseCurrency": "BTC",
            "quoteCurrency": "BRL",
            "enableTrading": True,
        },
    ]


def _est_costly_brl(symbol, side, amount_in, currency_in, currency_out, **kwargs):
    fee = 0.001
    if symbol == "USDT-BRL":
        # ~45 bps total cost — above old 40bps limit, under new 80bps
        cost = 0.0045
        spread = 28.0
        est_out = amount_in / 5.1 * (1 - cost)
    else:
        cost = 0.05
        spread = 200.0
        est_out = amount_in * 0.01
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
        slip_bps=5.0,
        est_out=est_out,
        cost_pct=cost,
        min_ok=True,
    )


def test_diagnose_routes_reports_cost_rejection():
    g = RouteGraph(symbols=_brl_symbols())
    tight = RouteOptions(
        min_pair_vol_usd=0,
        max_spread_bps=50,
        max_route_cost_pct=0.004,
        use_live_fees=False,
        hubs=("USDT", "BTC", "ETH"),
    )
    diag = diagnose_routes(
        "BRL", "USDT", 900.0, opts=tight, graph=g, estimate_leg_fn=_est_costly_brl
    )
    assert any(not d["accepted"] and "cost_pct" in str(d.get("reason")) for d in diag)
    assert find_best_route(
        "BRL", "USDT", 900.0, opts=tight, graph=g, estimate_leg_fn=_est_costly_brl
    ) is None

    loose = RouteOptions(
        min_pair_vol_usd=0,
        max_spread_bps=50,
        max_route_cost_pct=0.008,
        use_live_fees=False,
        hubs=("USDT", "BTC", "ETH"),
    )
    best = find_best_route(
        "BRL", "USDT", 900.0, opts=loose, graph=g, estimate_leg_fn=_est_costly_brl
    )
    assert best is not None
    assert best.via == "direct"


def test_config_owner_is_live():
    import json

    path = Path(__file__).resolve().parents[1] / "btc_trading_agent" / "config_USDT_BRL_conservative.json"
    cfg = json.loads(path.read_text())
    conv = cfg["conversion"]
    assert conv["dry_run"] is False
    assert conv["enabled"] is True
    assert conv["role"] == "owner"
    assert float(conv["max_route_cost_pct"]) >= 0.008
    assert float(conv["max_spread_bps"]) >= 50
    assert int(conv.get("onramp_cooldown_seconds", 0)) >= 3600
