"""Estimativa de custo por perna (fee + spread + slip) para rotas intermoedas.

Usa book público + fees (live com cache, fallback 0.1% VIP0).
Sem side-effects de ordem.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_TAKER_FEE_PCT = 0.001  # VIP0 Class A
FEE_CACHE_TTL_SEC = 600.0
_fee_cache: Dict[str, Tuple[float, float]] = {}  # symbol -> (fee_pct, expires_at)


@dataclass
class LegEstimate:
    symbol: str
    side: str  # buy | sell
    amount_in: float
    currency_in: str
    currency_out: str
    mid: float
    bid: float
    ask: float
    spread_bps: float
    fee_pct: float
    slip_bps: float
    est_out: float
    cost_pct: float
    min_ok: bool
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def clear_fee_cache() -> None:
    _fee_cache.clear()


def get_fee_pct(
    symbol: str,
    *,
    use_live: bool = True,
    fallback: float = DEFAULT_TAKER_FEE_PCT,
    get_trade_fees_fn: Optional[Callable[[str], List[Dict[str, Any]]]] = None,
) -> float:
    """Retorna taker fee rate para o symbol (cache TTL)."""
    sym = (symbol or "").upper()
    now = time.time()
    cached = _fee_cache.get(sym)
    if cached and cached[1] > now:
        return cached[0]

    fee = fallback
    if use_live:
        try:
            if get_trade_fees_fn is None:
                from kucoin_api import get_trade_fees as get_trade_fees_fn  # type: ignore
            rows = get_trade_fees_fn(sym) or []
            for row in rows:
                if str(row.get("symbol") or "").upper() == sym:
                    fee = float(row.get("takerFeeRate") or fallback)
                    break
            else:
                if rows:
                    fee = float(rows[0].get("takerFeeRate") or fallback)
        except Exception as exc:
            logger.debug("fee live miss for %s: %s — fallback %.4f", sym, exc, fallback)
            fee = fallback

    _fee_cache[sym] = (fee, now + FEE_CACHE_TTL_SEC)
    return fee


def _walk_book(
    levels: List[Tuple[float, float]],
    amount: float,
    *,
    is_buy: bool,
) -> Tuple[float, float, float]:
    """Walk order book.

    For sell: amount is base size → returns (quote_out, vwap, filled_base)
    For buy: amount is quote funds → returns (base_out, vwap, filled_quote)
    """
    remaining = float(amount)
    filled_primary = 0.0
    notional = 0.0
    if remaining <= 0 or not levels:
        return 0.0, 0.0, 0.0

    for price, size in levels:
        if price <= 0 or size <= 0:
            continue
        if is_buy:
            # spend quote for base
            level_cost = price * size
            take_quote = min(remaining, level_cost)
            take_base = take_quote / price
            notional += take_quote
            filled_primary += take_base
            remaining -= take_quote
        else:
            # sell base for quote
            take_base = min(remaining, size)
            take_quote = take_base * price
            notional += take_quote
            filled_primary += take_base
            remaining -= take_base
        if remaining <= 1e-12:
            break

    spent_or_sold = float(amount) - remaining
    if filled_primary <= 0 or spent_or_sold <= 0:
        return 0.0, 0.0, 0.0
    if is_buy:
        vwap = notional / filled_primary
        return filled_primary, vwap, spent_or_sold
    vwap = notional / filled_primary
    return notional, vwap, filled_primary


def estimate_leg(
    symbol: str,
    side: str,
    amount_in: float,
    *,
    currency_in: str,
    currency_out: str,
    fee_pct: Optional[float] = None,
    slip_buffer_pct: float = 0.0005,
    use_live_fees: bool = True,
    get_orderbook_fn: Optional[Callable[..., Dict[str, Any]]] = None,
    get_symbol_meta_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
) -> LegEstimate:
    """Estima output e custo de uma perna market taker."""
    side_l = (side or "").lower()
    if side_l not in ("buy", "sell"):
        raise ValueError(f"side must be buy|sell, got {side}")

    if get_orderbook_fn is None:
        from kucoin_api import get_orderbook as get_orderbook_fn  # type: ignore

    ob = get_orderbook_fn(symbol, depth=20) or {}
    bids = list(ob.get("bids") or [])
    asks = list(ob.get("asks") or [])
    bid = float(bids[0][0]) if bids else 0.0
    ask = float(asks[0][0]) if asks else 0.0
    mid = (bid + ask) / 2.0 if bid > 0 and ask > 0 else (bid or ask or 0.0)
    spread_bps = ((ask - bid) / mid * 10000.0) if mid > 0 and bid > 0 and ask > 0 else 9999.0

    fee = float(fee_pct) if fee_pct is not None else get_fee_pct(symbol, use_live=use_live_fees)

    # Optional min checks
    min_ok = True
    reason = ""
    if get_symbol_meta_fn is None:
        try:
            from kucoin_api import get_symbols

            def get_symbol_meta_fn(sym: str) -> Dict[str, Any]:
                for item in get_symbols():
                    if str(item.get("symbol") or "").upper() == sym.upper():
                        return item
                return {}

        except Exception:
            get_symbol_meta_fn = lambda _s: {}  # noqa: E731

    meta = get_symbol_meta_fn(symbol) or {}
    base_min = float(meta.get("baseMinSize") or 0) or 0.0
    quote_min = float(meta.get("quoteMinSize") or 0) or 0.0
    min_funds = float(meta.get("minFunds") or 0) or 0.0

    if side_l == "sell":
        out_gross, vwap, filled = _walk_book(bids, amount_in, is_buy=False)
        if filled <= 0 or out_gross <= 0:
            return LegEstimate(
                symbol=symbol,
                side=side_l,
                amount_in=amount_in,
                currency_in=currency_in,
                currency_out=currency_out,
                mid=mid,
                bid=bid,
                ask=ask,
                spread_bps=spread_bps,
                fee_pct=fee,
                slip_bps=0.0,
                est_out=0.0,
                cost_pct=1.0,
                min_ok=False,
                reason="empty_or_thin_book",
            )
        if base_min and amount_in < base_min:
            min_ok = False
            reason = f"below_baseMinSize={base_min}"
        # ideal out at mid without fee
        ideal = amount_in * mid if mid > 0 else out_gross
        out_net = out_gross * (1.0 - fee)
        slip_bps = max(0.0, (ideal - out_gross) / ideal * 10000.0) if ideal > 0 else 0.0
    else:
        out_gross, vwap, filled_quote = _walk_book(asks, amount_in, is_buy=True)
        if out_gross <= 0 or filled_quote <= 0:
            return LegEstimate(
                symbol=symbol,
                side=side_l,
                amount_in=amount_in,
                currency_in=currency_in,
                currency_out=currency_out,
                mid=mid,
                bid=bid,
                ask=ask,
                spread_bps=spread_bps,
                fee_pct=fee,
                slip_bps=0.0,
                est_out=0.0,
                cost_pct=1.0,
                min_ok=False,
                reason="empty_or_thin_book",
            )
        if quote_min and amount_in < quote_min:
            min_ok = False
            reason = f"below_quoteMinSize={quote_min}"
        if min_funds and amount_in < min_funds:
            min_ok = False
            reason = f"below_minFunds={min_funds}"
        ideal_base = amount_in / mid if mid > 0 else out_gross
        out_net = out_gross * (1.0 - fee)
        slip_bps = max(0.0, (ideal_base - out_gross) / ideal_base * 10000.0) if ideal_base > 0 else 0.0

    # cost vs mid-path without fee
    half_spread = (spread_bps / 10000.0) / 2.0 if spread_bps < 9000 else 0.0
    cost_pct = fee + half_spread + (slip_bps / 10000.0) + float(slip_buffer_pct)

    return LegEstimate(
        symbol=symbol,
        side=side_l,
        amount_in=float(amount_in),
        currency_in=currency_in.upper(),
        currency_out=currency_out.upper(),
        mid=mid,
        bid=bid,
        ask=ask,
        spread_bps=spread_bps,
        fee_pct=fee,
        slip_bps=slip_bps,
        est_out=float(out_net),
        cost_pct=float(cost_pct),
        min_ok=min_ok,
        reason=reason,
    )
