#!/usr/bin/env python3
"""Ajuste de confiança baseado no histórico realizado de SELLs por profile."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Protocol


DEFAULT_TRACK_RECORD_CFG: Dict[str, Any] = {
    "enabled": False,
    "mode": "apply",
    "lookback_hours": 72.0,
    "min_sell_samples": 5,
    "recent_sell_window": 20,
    "max_boost": 0.10,
    "max_penalty": 0.08,
    "pnl_scale_usd": 2.0,
    "streak_cap": 4,
    "cache_ttl_sec": 30.0,
    "wr_weight": 0.45,
    "pnl_weight": 0.30,
    "streak_weight": 0.25,
}


@dataclass(frozen=True)
class TrackRecordSnapshot:
    sell_count: int
    win_rate: float
    recent_pnl_usd: float
    winning_streak: int
    losing_streak: int
    lookback_hours: float
    sample_confidence: float
    trs: float
    boost: float

    def as_features(self) -> Dict[str, float]:
        return {
            "track_record_sell_count": float(self.sell_count),
            "track_record_wr": round(self.win_rate, 4),
            "track_record_pnl_usd": round(self.recent_pnl_usd, 6),
            "track_record_winning_streak": float(self.winning_streak),
            "track_record_losing_streak": float(self.losing_streak),
            "track_record_trs": round(self.trs, 4),
            "track_record_boost": round(self.boost, 4),
        }


class TrackRecordDb(Protocol):
    def get_profile_realized_sells(
        self,
        symbol: str,
        profile: str,
        since: float,
        *,
        dry_run: bool = False,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        ...


def merge_track_record_cfg(
    raw: Optional[Mapping[str, Any]] = None,
    *,
    profile: str = "default",
) -> Dict[str, Any]:
    cfg = dict(DEFAULT_TRACK_RECORD_CFG)
    if raw:
        cfg.update(raw)
    pnl_scale = float(cfg.get("pnl_scale_usd", 0.0) or 0.0)
    if pnl_scale <= 0.0:
        if profile == "aggressive":
            cfg["pnl_scale_usd"] = 5.0
        elif profile == "conservative":
            cfg["pnl_scale_usd"] = 2.0
        else:
            cfg["pnl_scale_usd"] = 3.0
    return cfg


def compute_streaks(sells: List[Dict[str, Any]]) -> tuple[int, int]:
    """Calcula streaks a partir de SELLs ordenados do mais recente ao mais antigo."""
    winning_streak = 0
    losing_streak = 0
    for trade in sells:
        pnl = float(trade.get("pnl", 0.0) or 0.0)
        if pnl > 0:
            if losing_streak:
                break
            winning_streak += 1
        elif pnl < 0:
            if winning_streak:
                break
            losing_streak += 1
        else:
            break
    return winning_streak, losing_streak


def compute_snapshot_from_sells(
    sells: List[Dict[str, Any]],
    cfg: Mapping[str, Any],
) -> TrackRecordSnapshot:
    lookback_hours = max(1.0, float(cfg.get("lookback_hours", 72.0) or 72.0))
    min_sell_samples = max(1, int(cfg.get("min_sell_samples", 5) or 5))
    max_boost = max(0.0, float(cfg.get("max_boost", 0.10) or 0.10))
    max_penalty = max(0.0, float(cfg.get("max_penalty", 0.08) or 0.08))
    pnl_scale_usd = max(0.0001, float(cfg.get("pnl_scale_usd", 2.0) or 2.0))
    streak_cap = max(1, int(cfg.get("streak_cap", 4) or 4))
    wr_weight = float(cfg.get("wr_weight", 0.45) or 0.45)
    pnl_weight = float(cfg.get("pnl_weight", 0.30) or 0.30)
    streak_weight = float(cfg.get("streak_weight", 0.25) or 0.25)

    sell_count = len(sells)
    if sell_count == 0:
        return TrackRecordSnapshot(
            sell_count=0,
            win_rate=0.0,
            recent_pnl_usd=0.0,
            winning_streak=0,
            losing_streak=0,
            lookback_hours=lookback_hours,
            sample_confidence=0.0,
            trs=0.0,
            boost=0.0,
        )

    winning_sells = sum(1 for trade in sells if float(trade.get("pnl", 0.0) or 0.0) > 0)
    win_rate = winning_sells / sell_count
    recent_pnl_usd = sum(float(trade.get("pnl", 0.0) or 0.0) for trade in sells)
    winning_streak, losing_streak = compute_streaks(sells)

    sample_confidence = min(1.0, sell_count / min_sell_samples)
    if sell_count < min_sell_samples:
        return TrackRecordSnapshot(
            sell_count=sell_count,
            win_rate=win_rate,
            recent_pnl_usd=recent_pnl_usd,
            winning_streak=winning_streak,
            losing_streak=losing_streak,
            lookback_hours=lookback_hours,
            sample_confidence=sample_confidence,
            trs=0.0,
            boost=0.0,
        )

    wr_score = max(-1.0, min(1.0, (win_rate - 0.5) * 2.0))
    pnl_score = math.tanh(recent_pnl_usd / pnl_scale_usd)
    streak_score = max(
        -1.0,
        min(1.0, (winning_streak - losing_streak) / float(streak_cap)),
    )
    raw_trs = (
        wr_score * wr_weight
        + pnl_score * pnl_weight
        + streak_score * streak_weight
    )
    trs = max(-1.0, min(1.0, sample_confidence * raw_trs))
    if trs >= 0:
        boost = trs * max_boost
    else:
        boost = trs * max_penalty

    return TrackRecordSnapshot(
        sell_count=sell_count,
        win_rate=win_rate,
        recent_pnl_usd=recent_pnl_usd,
        winning_streak=winning_streak,
        losing_streak=losing_streak,
        lookback_hours=lookback_hours,
        sample_confidence=sample_confidence,
        trs=trs,
        boost=boost,
    )


def apply_confidence_adjustment(
    raw_confidence: float,
    snapshot: TrackRecordSnapshot,
    *,
    floor: float = 0.01,
    ceiling: float = 0.99,
) -> float:
    adjusted = raw_confidence + snapshot.boost
    return max(floor, min(ceiling, adjusted))


class TrackRecordConfidence:
    """Calcula boost/penalty de confiança a partir de SELLs realizados."""

    def __init__(self, db: TrackRecordDb):
        self.db = db
        self._cache: Dict[tuple, Dict[str, Any]] = {}

    def get_snapshot(
        self,
        symbol: str,
        profile: str,
        dry_run: bool,
        cfg: Mapping[str, Any],
    ) -> TrackRecordSnapshot:
        merged = merge_track_record_cfg(cfg, profile=profile)
        if not merged.get("enabled", False):
            return compute_snapshot_from_sells([], merged)

        now = time.time()
        cache_ttl_sec = max(5.0, float(merged.get("cache_ttl_sec", 30.0) or 30.0))
        lookback_hours = max(1.0, float(merged.get("lookback_hours", 72.0) or 72.0))
        recent_sell_window = max(4, int(merged.get("recent_sell_window", 20) or 20))
        cache_key = (symbol, profile, bool(dry_run), round(lookback_hours, 2), recent_sell_window)
        cached = self._cache.get(cache_key)
        if cached and float(cached.get("expires_at", 0.0) or 0.0) > now:
            return cached["snapshot"]

        since = now - (lookback_hours * 3600.0)
        sells = self.db.get_profile_realized_sells(
            symbol=symbol,
            profile=profile,
            since=since,
            dry_run=dry_run,
            limit=recent_sell_window,
        )
        snapshot = compute_snapshot_from_sells(sells, merged)
        self._cache[cache_key] = {
            "expires_at": now + cache_ttl_sec,
            "snapshot": snapshot,
        }
        return snapshot