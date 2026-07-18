"""Execução sequencial de pernas de conversão (market orders)."""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional

from route_graph import RoutePlan

logger = logging.getLogger(__name__)


@dataclass
class LegResult:
    leg_index: int
    symbol: str
    side: str
    amount_in: float
    amount_out: float
    fee: float
    order_id: str
    status: str  # ok | failed | simulated
    error: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionResult:
    success: bool
    status: str  # done | partial | failed | simulated
    plan: RoutePlan
    legs: List[LegResult] = field(default_factory=list)
    amount_out: float = 0.0
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status,
            "amount_out": self.amount_out,
            "error": self.error,
            "plan": self.plan.to_dict(),
            "legs": [leg.to_dict() for leg in self.legs],
        }


def simulate(plan: RoutePlan) -> ExecutionResult:
    """Dry-run: confia no RoutePlan já estimado."""
    legs = [
        LegResult(
            leg_index=i,
            symbol=leg.symbol,
            side=leg.side,
            amount_in=leg.amount_in,
            amount_out=leg.est_out,
            fee=leg.amount_in * leg.fee_pct if leg.side == "sell" else leg.est_out * leg.fee_pct,
            order_id="",
            status="simulated",
        )
        for i, leg in enumerate(plan.legs)
    ]
    return ExecutionResult(
        success=True,
        status="simulated",
        plan=plan,
        legs=legs,
        amount_out=plan.est_out,
    )


def execute(
    plan: RoutePlan,
    *,
    dry_run: bool = True,
    place_order_fn: Optional[Callable[..., Dict[str, Any]]] = None,
    get_fills_fn: Optional[Callable[..., Dict[str, Any]]] = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    fill_wait_sec: float = 1.0,
) -> ExecutionResult:
    """Executa pernas em sequência. Em falha parcial: status=partial (sem unwind)."""
    if dry_run:
        return simulate(plan)

    if place_order_fn is None:
        from kucoin_api import place_market_order as place_order_fn  # type: ignore
    if get_fills_fn is None:
        from kucoin_api import get_fills_for_order as get_fills_fn  # type: ignore

    results: List[LegResult] = []
    current_amount = float(plan.amount_in)

    for i, leg in enumerate(plan.legs):
        try:
            if leg.side == "buy":
                order = place_order_fn(leg.symbol, "buy", funds=current_amount)
            else:
                order = place_order_fn(leg.symbol, "sell", size=current_amount)
        except Exception as exc:
            results.append(
                LegResult(
                    leg_index=i,
                    symbol=leg.symbol,
                    side=leg.side,
                    amount_in=current_amount,
                    amount_out=0.0,
                    fee=0.0,
                    order_id="",
                    status="failed",
                    error=str(exc),
                )
            )
            return ExecutionResult(
                success=False,
                status="partial" if results[:-1] else "failed",
                plan=plan,
                legs=results,
                amount_out=results[-2].amount_out if len(results) > 1 else 0.0,
                error=str(exc),
            )

        if not order.get("success"):
            err = str(order.get("error") or "order_failed")
            results.append(
                LegResult(
                    leg_index=i,
                    symbol=leg.symbol,
                    side=leg.side,
                    amount_in=current_amount,
                    amount_out=0.0,
                    fee=0.0,
                    order_id=str(order.get("orderId") or ""),
                    status="failed",
                    error=err,
                    raw=order,
                )
            )
            return ExecutionResult(
                success=False,
                status="partial" if i > 0 else "failed",
                plan=plan,
                legs=results,
                amount_out=results[i - 1].amount_out if i > 0 else 0.0,
                error=err,
            )

        order_id = str(order.get("orderId") or "")
        sleep_fn(fill_wait_sec)
        fill = {}
        try:
            fill = get_fills_fn(order_id, symbol=leg.symbol) or {}
        except Exception as exc:
            logger.warning("fill lookup failed order=%s: %s", order_id, exc)

        if leg.side == "buy":
            amount_out = float(fill.get("fill_size") or leg.est_out)
            # after fee on base, fill_size usually already net of? use fill if present
        else:
            amount_out = float(fill.get("fill_funds") or leg.est_out)

        fee = float(fill.get("fill_fee") or 0.0)
        results.append(
            LegResult(
                leg_index=i,
                symbol=leg.symbol,
                side=leg.side,
                amount_in=current_amount,
                amount_out=amount_out,
                fee=fee,
                order_id=order_id,
                status="ok",
                raw={"order": order, "fill": fill},
            )
        )
        current_amount = amount_out
        if current_amount <= 0:
            return ExecutionResult(
                success=False,
                status="partial",
                plan=plan,
                legs=results,
                amount_out=0.0,
                error="zero_output_after_leg",
            )

    return ExecutionResult(
        success=True,
        status="done",
        plan=plan,
        legs=results,
        amount_out=current_amount,
    )
