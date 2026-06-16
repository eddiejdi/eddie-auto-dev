"""OO policies for independent slot exits and multi-entry SELL handling."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SlotSnapshot:
    """Immutable view of one open slot."""

    index: int
    entry_price: float
    size: float
    trailing_high: float
    target_sell: float
    ts: float

    @classmethod
    def from_entry(cls, index: int, entry: dict[str, Any]) -> "SlotSnapshot":
        entry_price = float(entry.get("price", 0) or 0)
        return cls(
            index=index,
            entry_price=entry_price,
            size=float(entry.get("size", 0) or 0),
            trailing_high=float(entry.get("trailing_high", entry_price) or entry_price),
            target_sell=float(entry.get("target_sell", 0) or 0),
            ts=float(entry.get("ts", 0) or 0),
        )


@dataclass(frozen=True)
class SlotExitContext:
    """Runtime data shared across slot exit rules."""

    price: float
    live_cfg: dict[str, Any]
    now: float


@dataclass(frozen=True)
class SlotExitDecision:
    """One independent slot SELL decision.

    bypass_guardrail: True para stop-loss e saídas de emergência — saídas de
    proteção de risco que devem executar independentemente de PnL.  Qualquer
    nova regra que precise bypasear o guardrail DEVE setar este campo
    explicitamente; o padrão False garante que novas regras herdem a proteção.
    """

    entry_idx: int
    expected_entry_price: float
    reason: str
    bypass_guardrail: bool = False


@dataclass
class SlotPlanResult:
    """Planner output with updated entries plus SELL decisions."""

    updated_entries: list[dict[str, Any]]
    decisions: list[SlotExitDecision]


class SlotExitRule(ABC):
    """Base class for one per-slot exit rule."""

    @abstractmethod
    def evaluate(
        self,
        slot: SlotSnapshot,
        ctx: SlotExitContext,
    ) -> SlotExitDecision | None:
        """Return a SELL decision for this slot, or None."""


class MaxHoldRule(SlotExitRule):
    """Forces exit when a slot exceeds the configured holding time."""

    def evaluate(
        self,
        slot: SlotSnapshot,
        ctx: SlotExitContext,
    ) -> SlotExitDecision | None:
        max_hold_hours = float(ctx.live_cfg.get("max_hold_hours", 0) or 0)
        if max_hold_hours <= 0 or slot.ts <= 0:
            return None

        hold_hours = (ctx.now - slot.ts) / 3600
        if hold_hours < max_hold_hours:
            return None

        return SlotExitDecision(
            entry_idx=slot.index,
            expected_entry_price=slot.entry_price,
            reason=f"MAX_HOLD slot#{slot.index + 1} ({hold_hours:.1f}h held)",
        )


class TrailingStopRule(SlotExitRule):
    """Triggers per-slot trailing stop once the slot-specific high rolls over."""

    def evaluate(
        self,
        slot: SlotSnapshot,
        ctx: SlotExitContext,
    ) -> SlotExitDecision | None:
        ts_cfg = ctx.live_cfg.get("trailing_stop", {})
        if not bool(ts_cfg.get("enabled", False)):
            return None

        activation_pct = float(ts_cfg.get("activation_pct", 0.01) or 0.01)
        trail_pct = float(ts_cfg.get("trail_pct", 0.005) or 0.005)
        if slot.entry_price <= 0 or slot.trailing_high <= 0:
            return None

        gain = (slot.trailing_high / slot.entry_price) - 1
        if gain < activation_pct:
            return None

        drop = (slot.trailing_high - ctx.price) / slot.trailing_high
        if drop < trail_pct:
            return None

        return SlotExitDecision(
            entry_idx=slot.index,
            expected_entry_price=slot.entry_price,
            reason=(
                f"TRAILING_STOP slot#{slot.index + 1} "
                f"(drop {drop * 100:.2f}% from ${slot.trailing_high:,.2f})"
            ),
        )


class TakeProfitRule(SlotExitRule):
    """Triggers when the current price reaches the slot-specific target."""

    def evaluate(
        self,
        slot: SlotSnapshot,
        ctx: SlotExitContext,
    ) -> SlotExitDecision | None:
        if slot.target_sell <= 0 or ctx.price < slot.target_sell or slot.entry_price <= 0:
            return None

        pnl_pct = (ctx.price / slot.entry_price - 1) * 100
        return SlotExitDecision(
            entry_idx=slot.index,
            expected_entry_price=slot.entry_price,
            reason=f"PER_SLOT_TP slot#{slot.index + 1} (+{pnl_pct:.2f}%)",
        )


class StopLossRule(SlotExitRule):
    """Triggers when one slot breaches the configured stop-loss threshold."""

    def evaluate(
        self,
        slot: SlotSnapshot,
        ctx: SlotExitContext,
    ) -> SlotExitDecision | None:
        auto_sl = ctx.live_cfg.get("auto_stop_loss", {})
        if not bool(auto_sl.get("enabled", False)) or slot.entry_price <= 0:
            return None

        sl_pct = float(auto_sl.get("pct", 0.05) or 0.05)
        pnl_pct = (ctx.price / slot.entry_price) - 1
        if pnl_pct > -sl_pct:
            return None

        return SlotExitDecision(
            entry_idx=slot.index,
            expected_entry_price=slot.entry_price,
            reason=f"PER_SLOT_SL slot#{slot.index + 1} ({pnl_pct * 100:.2f}%)",
            bypass_guardrail=True,
        )


class PerSlotExitPlanner:
    """Evaluates per-slot exit rules independently for the full position."""

    def __init__(self, rules: list[SlotExitRule] | None = None):
        self.rules = rules or [
            MaxHoldRule(),
            TrailingStopRule(),
            TakeProfitRule(),
            StopLossRule(),
        ]

    def plan(
        self,
        entries: list[dict[str, Any]],
        ctx: SlotExitContext,
    ) -> SlotPlanResult:
        updated_entries = [dict(entry) for entry in entries]
        decisions: list[SlotExitDecision] = []

        for index, entry in enumerate(updated_entries):
            slot = SlotSnapshot.from_entry(index, entry)
            if slot.entry_price <= 0 or slot.size <= 0:
                continue

            if ctx.price > slot.trailing_high:
                entry["trailing_high"] = ctx.price
                slot = SlotSnapshot.from_entry(index, entry)

            for rule in self.rules:
                decision = rule.evaluate(slot, ctx)
                if decision:
                    decisions.append(decision)
                    break

        return SlotPlanResult(updated_entries=updated_entries, decisions=decisions)


@dataclass(frozen=True)
class SignalSellContext:
    """Runtime input for multi-entry SELL signal policies."""

    price: float
    reason: str
    force: bool
    live_cfg: dict[str, Any]
    fee_pct: float


class SignalSellPolicy(ABC):
    """Base strategy for SELL signals when multiple slots are open."""

    @abstractmethod
    def select(
        self,
        entries: list[dict[str, Any]],
        ctx: SignalSellContext,
    ) -> list[SlotExitDecision]:
        """Return one decision per independent slot to be sold."""

    def _net_pnl(self, entry: dict[str, Any], price: float, fee_pct: float) -> float:
        entry_price = float(entry.get("price", 0) or 0)
        size = float(entry.get("size", 0) or 0)
        gross_pnl = (price - entry_price) * size
        sell_fee = price * size * fee_pct
        buy_fee = entry_price * size * fee_pct
        return gross_pnl - sell_fee - buy_fee


class ProfitOnlySignalSellPolicy(SignalSellPolicy):
    """Realizes only slots with positive net PnL."""

    def __init__(self, reason_prefix: str = "MODEL_PROFIT_LOCK"):
        self.reason_prefix = reason_prefix

    def select(
        self,
        entries: list[dict[str, Any]],
        ctx: SignalSellContext,
    ) -> list[SlotExitDecision]:
        decisions: list[SlotExitDecision] = []
        for index, entry in enumerate(entries):
            entry_price = float(entry.get("price", 0) or 0)
            size = float(entry.get("size", 0) or 0)
            if entry_price <= 0 or size <= 0:
                continue

            target_sell = float(entry.get("target_sell", 0) or 0)
            if target_sell > 0 and ctx.price < target_sell:
                continue

            pnl = self._net_pnl(entry, ctx.price, ctx.fee_pct)
            if pnl <= 0:
                continue

            reason = f"{self.reason_prefix} {ctx.reason} (net_pnl=${pnl:.4f})"
            if target_sell > 0:
                reason = (
                    f"{self.reason_prefix} {ctx.reason} "
                    f"(target=${target_sell:,.2f}, net_pnl=${pnl:.4f})"
                )
            decisions.append(
                SlotExitDecision(
                    entry_idx=index,
                    expected_entry_price=entry_price,
                    reason=reason,
                )
            )
        return decisions


class StopLossSignalSellPolicy(SignalSellPolicy):
    """Cuts only the slots that individually violated stop-loss."""

    def select(
        self,
        entries: list[dict[str, Any]],
        ctx: SignalSellContext,
    ) -> list[SlotExitDecision]:
        auto_sl = ctx.live_cfg.get("auto_stop_loss", {})
        if not bool(auto_sl.get("enabled", False)):
            return []

        sl_pct = float(auto_sl.get("pct", 0.05) or 0.05)
        decisions: list[SlotExitDecision] = []
        for index, entry in enumerate(entries):
            entry_price = float(entry.get("price", 0) or 0)
            size = float(entry.get("size", 0) or 0)
            if entry_price <= 0 or size <= 0:
                continue
            pnl_pct = (ctx.price / entry_price) - 1
            if pnl_pct > -sl_pct:
                continue
            decisions.append(
                SlotExitDecision(
                    entry_idx=index,
                    expected_entry_price=entry_price,
                    reason=f"PER_SLOT_SL slot#{index + 1} ({pnl_pct * 100:.2f}%)",
                    bypass_guardrail=True,
                )
            )
        return decisions


class SignalSellPolicyResolver:
    """Resolves the OO policy used for multi-entry SELL handling."""

    def resolve(self, ctx: SignalSellContext) -> SignalSellPolicy:
        if ctx.force and ctx.reason.startswith("AUTO_STOP_LOSS"):
            return StopLossSignalSellPolicy()
        return ProfitOnlySignalSellPolicy()
