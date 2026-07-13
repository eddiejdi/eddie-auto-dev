#!/usr/bin/env python3
"""Testes do módulo track_record_confidence."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))

from track_record_confidence import (
    TrackRecordConfidence,
    apply_confidence_adjustment,
    compute_snapshot_from_sells,
    compute_streaks,
    merge_track_record_cfg,
)


def _sell(pnl: float) -> dict:
    return {"side": "sell", "pnl": pnl, "pnl_pct": pnl * 100}


def test_neutral_when_insufficient_samples() -> None:
    sells = [_sell(0.02), _sell(0.01), _sell(-0.01)]
    snap = compute_snapshot_from_sells(sells, merge_track_record_cfg({"min_sell_samples": 5}))
    assert snap.trs == 0.0
    assert snap.boost == 0.0
    assert snap.sell_count == 3


def test_positive_boost_on_strong_track_record() -> None:
    sells = [_sell(0.03), _sell(0.02), _sell(0.015), _sell(0.01), _sell(0.008)]
    snap = compute_snapshot_from_sells(sells, merge_track_record_cfg())
    assert snap.trs > 0.5
    assert snap.boost > 0.05
    assert snap.winning_streak == 5


def test_negative_penalty_on_losing_streak() -> None:
    sells = [_sell(-0.03), _sell(-0.02), _sell(-0.015), _sell(-0.01), _sell(0.005)]
    snap = compute_snapshot_from_sells(sells, merge_track_record_cfg())
    assert snap.trs < 0
    assert snap.boost < 0
    assert snap.losing_streak == 4


def test_asymmetric_caps() -> None:
    cfg = merge_track_record_cfg({"max_boost": 0.10, "max_penalty": 0.08})
    winning = [_sell(0.05)] * 8
    losing = [_sell(-0.05)] * 8
    win_snap = compute_snapshot_from_sells(winning, cfg)
    lose_snap = compute_snapshot_from_sells(losing, cfg)
    assert win_snap.boost <= 0.10 + 1e-9
    assert lose_snap.boost >= -0.08 - 1e-9
    assert abs(win_snap.boost) > abs(lose_snap.boost)


def test_apply_confidence_adjustment_clips() -> None:
    sells = [_sell(0.03)] * 6
    snap = compute_snapshot_from_sells(sells, merge_track_record_cfg())
    adjusted = apply_confidence_adjustment(0.58, snap)
    assert 0.58 < adjusted <= 0.99


def test_compute_streaks_mixed() -> None:
    sells = [_sell(0.01), _sell(0.02), _sell(-0.01), _sell(0.03)]
    wins, losses = compute_streaks(sells)
    assert wins == 2
    assert losses == 0


def test_track_record_confidence_uses_db() -> None:
    class FakeDb:
        def get_profile_realized_sells(self, **kwargs):
            return [_sell(0.02)] * 6

    engine = TrackRecordConfidence(FakeDb())
    snap = engine.get_snapshot(
        "BTC-USDT",
        "conservative",
        dry_run=False,
        cfg=merge_track_record_cfg({"enabled": True}),
    )
    assert snap.sell_count == 6
    assert snap.boost > 0


def test_merge_profile_pnl_scale() -> None:
    cons = merge_track_record_cfg({"pnl_scale_usd": 0}, profile="conservative")
    aggr = merge_track_record_cfg({"pnl_scale_usd": 0}, profile="aggressive")
    assert cons["pnl_scale_usd"] == 2.0
    assert aggr["pnl_scale_usd"] == 5.0