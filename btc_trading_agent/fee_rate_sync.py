"""Sincroniza a taxa taker live da KuCoin para o agent.

Usado no loop do trading_agent para atualizar ``_trading_fee_pct`` quando
VIP / Pay Fees with KCS / promo mudam a taxa efetiva.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_FEE_PCT = 0.001  # VIP0 Class A fallback


def resolve_live_fee_pct(
    symbol: str,
    *,
    fallback: float = DEFAULT_FEE_PCT,
    get_trade_fees_fn: Optional[Callable[[str], Any]] = None,
    get_base_fee_fn: Optional[Callable[..., Dict[str, Any]]] = None,
) -> Tuple[float, str]:
    """Resolve taker fee rate para o symbol.

    Ordem:
      1. GET /trade-fees?symbols=SYMBOL → takerFeeRate
      2. GET /base-fee → takerFeeRate
      3. fallback

    Returns:
        (fee_pct, source) onde source é trade_fees|base_fee|fallback
    """
    sym = (symbol or "").upper().strip()
    fb = float(fallback) if fallback and fallback > 0 else DEFAULT_FEE_PCT

    if get_trade_fees_fn is None:
        try:
            from kucoin_api import get_trade_fees as get_trade_fees_fn  # type: ignore
        except Exception:
            get_trade_fees_fn = None

    if get_trade_fees_fn is not None and sym:
        try:
            rows = get_trade_fees_fn(sym) or []
            for row in rows:
                if str(row.get("symbol") or "").upper() == sym:
                    rate = float(row.get("takerFeeRate") or 0)
                    if rate > 0:
                        return rate, "trade_fees"
            if rows:
                rate = float(rows[0].get("takerFeeRate") or 0)
                if rate > 0:
                    return rate, "trade_fees"
        except Exception as exc:
            logger.debug("trade-fees miss for %s: %s", sym, exc)

    if get_base_fee_fn is None:
        try:
            from kucoin_api import get_base_fee as get_base_fee_fn  # type: ignore
        except Exception:
            get_base_fee_fn = None

    if get_base_fee_fn is not None:
        try:
            base = get_base_fee_fn("1") or {}
            if base.get("success") is False:
                pass
            else:
                rate = float(base.get("takerFeeRate") or 0)
                if rate > 0:
                    return rate, "base_fee"
        except Exception as exc:
            logger.debug("base-fee miss: %s", exc)

    return fb, "fallback"


def apply_fee_pct(
    current: float,
    new_fee: float,
    *,
    min_pct: float = 1e-6,
    max_pct: float = 0.05,
    rel_change_log: float = 0.01,
) -> Tuple[float, bool]:
    """Sanitiza e compara fee. Returns (value, changed)."""
    try:
        fee = float(new_fee)
    except (TypeError, ValueError):
        return float(current), False
    if fee < min_pct or fee > max_pct:
        logger.warning("⚠️ fee_rate_sync: fee fora da faixa (%.6f) — ignorado", fee)
        return float(current), False
    cur = float(current) if current and current > 0 else DEFAULT_FEE_PCT
    changed = abs(fee - cur) / cur >= rel_change_log if cur > 0 else abs(fee - cur) > 1e-9
    # Always adopt if different beyond float noise
    if abs(fee - cur) > 1e-12:
        return fee, True
    return cur, False
