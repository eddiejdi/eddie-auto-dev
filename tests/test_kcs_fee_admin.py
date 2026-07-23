"""Testes do administrador de buffer KCS (owner USDT_BRL)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))

from kcs_fee_admin import (
    KcsSnapshot,
    execute_actions,
    plan_actions,
)


def _snap(**kwargs) -> KcsSnapshot:
    base = KcsSnapshot(
        trade_kcs=0.0,
        trade_usdt=20.0,
        trade_brl=0.0,
        main_kcs=0.0,
        redeeming_kcs=0.0,
        held_earn_kcs=0.0,
        earn_status="none",
        kcs_price=6.6,
        usdt_brl_price=5.2,
        sub_kcs={
            "BTCAgressive": 0.0,
            "BTCConservative": 0.0,
            "ETHAgressive": 0.0,
            "ETHConservative": 0.0,
        },
        sub_uids={
            "BTCAgressive": "1",
            "BTCConservative": "2",
            "ETHAgressive": "3",
            "ETHConservative": "4",
        },
    )
    for k, v in kwargs.items():
        setattr(base, k, v)
    return base


CFG = {
    "min_trade_kcs": 0.5,
    "target_trade_kcs": 1.5,
    "max_buy_usdt": 15,
    "reserve_usdt": 1.0,
    "min_buy_usdt": 2,
    "skip_buy_if_redeeming": False,
    "distribute_to_subs": True,
    "fund_usdt_from_brl": True,
    "max_brl_for_kcs": 120,
    "reserve_brl": 50,
    "min_brl_convert": 15,
    "sub_min_kcs": 0.2,
    "sub_target_kcs": 0.25,
    "keep_master_min_kcs": 0.4,
    "subs": [
        "BTCAgressive",
        "BTCConservative",
        "ETHAgressive",
        "ETHConservative",
    ],
}


def test_plan_still_buys_when_redeeming_because_redeem_cannot_pay_fees():
    """REDEEMING não paga fee — precisa KCS livre no TRADE."""
    snap = _snap(trade_kcs=0.0, redeeming_kcs=1.36, trade_usdt=20.0)
    acts = plan_actions(CFG, snap)
    kinds = [a.kind for a in acts]
    assert "wait_redeem" in kinds
    assert "buy" in kinds


def test_plan_skip_buy_if_redeeming_flag():
    cfg = dict(CFG)
    cfg["skip_buy_if_redeeming"] = True
    snap = _snap(trade_kcs=0.0, redeeming_kcs=1.36, trade_usdt=20.0)
    acts = plan_actions(cfg, snap)
    assert "buy" not in [a.kind for a in acts]


def test_plan_buys_when_low_and_usdt_available():
    snap = _snap(trade_kcs=0.1, redeeming_kcs=0.0, trade_usdt=20.0, kcs_price=6.6)
    acts = plan_actions(CFG, snap)
    buys = [a for a in acts if a.kind == "buy"]
    assert len(buys) == 1
    assert buys[0].usdt >= 2.0
    assert buys[0].usdt <= 15.0


def test_plan_funds_from_brl_when_usdt_low():
    snap = _snap(
        trade_kcs=0.0,
        redeeming_kcs=0.0,
        trade_usdt=0.9,
        trade_brl=1000.0,
        kcs_price=6.6,
        usdt_brl_price=5.2,
    )
    acts = plan_actions(CFG, snap)
    kinds = [a.kind for a in acts]
    assert "fund_usdt_from_brl" in kinds
    assert "buy" in kinds
    fund = next(a for a in acts if a.kind == "fund_usdt_from_brl")
    assert fund.brl >= 15.0


def test_plan_main_sweep():
    snap = _snap(trade_kcs=0.0, main_kcs=1.2, trade_usdt=20.0)
    acts = plan_actions(CFG, snap)
    assert any(a.kind == "transfer_main" and a.amount >= 1.2 for a in acts)


def test_plan_no_buy_without_usdt_or_brl():
    snap = _snap(trade_kcs=0.0, redeeming_kcs=0.0, trade_usdt=0.5, trade_brl=10.0)
    acts = plan_actions(CFG, snap)
    assert not any(a.kind == "buy" for a in acts)


def test_plan_distributes_to_subs():
    snap = _snap(
        trade_kcs=3.0,
        redeeming_kcs=0.0,
        trade_usdt=10.0,
        sub_kcs={
            "BTCAgressive": 0.0,
            "BTCConservative": 0.4,
            "ETHAgressive": 0.0,
            "ETHConservative": 0.0,
        },
    )
    acts = plan_actions(CFG, snap)
    transfers = [a for a in acts if a.kind == "transfer_sub"]
    assert transfers
    assert all(a.amount >= 0.05 for a in transfers)
    names = {a.sub_name for a in transfers}
    assert "BTCAgressive" in names
    assert "BTCConservative" not in names  # already above sub_min


def test_execute_dry_run_does_not_call_order():
    snap = _snap(trade_kcs=0.0, trade_usdt=20.0)
    acts = plan_actions(CFG, snap)
    called = {"order": 0}

    def place(*_a, **_k):
        called["order"] += 1
        return {"success": True, "orderId": "x"}

    out = execute_actions(acts, snap, dry_run=True, place_order_fn=place)
    assert called["order"] == 0
    assert any(a.kind == "buy" and a.dry_run for a in out)


def test_execute_live_buy():
    snap = _snap(trade_kcs=0.0, trade_usdt=20.0)
    acts = [a for a in plan_actions(CFG, snap) if a.kind == "buy"]
    assert acts

    def place(symbol, side, funds=None, **_k):
        assert symbol == "KCS-USDT"
        assert side == "buy"
        assert funds and funds >= 2
        return {"success": True, "orderId": "oid-1"}

    out = execute_actions(
        acts,
        snap,
        dry_run=False,
        place_order_fn=place,
        sleep_fn=lambda _s: None,
    )
    assert out[0].executed is True
    assert out[0].order_id == "oid-1"


def test_execute_fund_then_buy_order():
    snap = _snap(
        trade_kcs=0.0,
        trade_usdt=0.5,
        trade_brl=500.0,
        kcs_price=6.6,
        usdt_brl_price=5.0,
    )
    acts = plan_actions(CFG, snap)
    orders = []

    def place(symbol, side, funds=None, **_k):
        orders.append((symbol, side, funds))
        return {"success": True, "orderId": f"oid-{len(orders)}"}

    out = execute_actions(
        acts,
        snap,
        dry_run=False,
        place_order_fn=place,
        sleep_fn=lambda _s: None,
    )
    assert any(a.kind == "fund_usdt_from_brl" and a.executed for a in out)
    assert orders[0][0] == "USDT-BRL"
    assert orders[0][1] == "buy"
