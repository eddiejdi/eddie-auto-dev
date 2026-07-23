"""Mixin: owner de conversão intermoedas (perfil USDT_BRL_conservative)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _conversion_cfg(config: Dict[str, Any]) -> Dict[str, Any]:
    raw = config.get("conversion") or {}
    return raw if isinstance(raw, dict) else {}


class ConversionMixin:
    """Processa fila de conversão e on-ramp BRL com rota de menor custo.

    Ativado quando config.conversion.enabled e role=owner.
    """

    def _conversion_enabled(self) -> bool:
        cfg = _conversion_cfg(getattr(self, "config", {}) or {})
        return bool(cfg.get("enabled")) and str(cfg.get("role") or "").lower() == "owner"

    def _conversion_options(self):
        from route_graph import RouteOptions

        cfg = _conversion_cfg(self.config)
        return RouteOptions(
            max_hops=int(cfg.get("max_hops", 2)),
            hubs=tuple(cfg.get("hubs") or ["USDT", "BTC", "ETH"]),
            allow_exotic_hubs=bool(cfg.get("allow_exotic_hubs", False)),
            prefer_direct_slack_bps=float(cfg.get("prefer_direct_slack_bps", 5)),
            min_pair_vol_usd=float(cfg.get("min_pair_vol_usd", 50_000)),
            max_spread_bps=float(cfg.get("max_spread_bps", 50)),
            max_route_cost_pct=float(cfg.get("max_route_cost_pct", 0.008)),
            slip_buffer_pct=float(cfg.get("slippage_buffer_pct", 0.0005)),
            use_live_fees=bool(cfg.get("use_live_fees", True)),
        )

    def _conversion_dry_run(self) -> bool:
        cfg = _conversion_cfg(self.config)
        if "dry_run" in cfg:
            return bool(cfg.get("dry_run"))
        return bool(getattr(self.state, "dry_run", True))

    def _conversion_whitelist(self) -> List[str]:
        cfg = _conversion_cfg(self.config)
        raw = cfg.get("assets_whitelist") or ["BRL", "USDT", "BTC", "ETH", "SOL", "DOGE"]
        return [str(x).upper() for x in raw]

    def _conversion_transfer_currencies(self) -> List[str]:
        """Moedas para MAIN→TRADE além de base/quote do par."""
        if not self._conversion_enabled():
            return []
        return self._conversion_whitelist()

    def _maybe_run_conversions(self, cycle: int) -> None:
        if not self._conversion_enabled():
            return
        cfg = _conversion_cfg(self.config)
        every = max(1, int(cfg.get("poll_conversions_every_cycles", 12)))
        if cycle % every != 0:
            return
        try:
            self._process_conversion_queue()
        except Exception as exc:
            logger.error("⚠️ conversion queue error: %s", exc, exc_info=True)
        try:
            jobs = cfg.get("jobs") or []
            for job in jobs:
                if not isinstance(job, dict) or not job.get("enabled"):
                    continue
                if job.get("type") == "deposit_onramp":
                    self._maybe_enqueue_brl_onramp()
        except Exception as exc:
            logger.error("⚠️ conversion jobs error: %s", exc, exc_info=True)

    def _onramp_should_skip(
        self,
        asset_out: str,
        brl: float,
        *,
        cooldown_seconds: int,
        balance_delta_pct: float,
    ) -> Optional[str]:
        """Retorna motivo de skip, ou None se pode enfileirar."""
        if self.db.has_pending_conversion("BRL", asset_out):
            return "pending_exists"

        get_recent = getattr(self.db, "get_recent_conversion", None)
        if not callable(get_recent):
            return None

        recent = get_recent(
            "BRL",
            asset_out,
            within_seconds=int(cooldown_seconds),
            requested_by="deposit_onramp",
        )
        if not recent:
            return None

        status = str(recent.get("status") or "")
        prev_amount = float(recent.get("amount_in") or 0.0)
        # Se o saldo mudou o bastante (novo depósito), permite re-fila mesmo no cooldown.
        if prev_amount > 0 and balance_delta_pct > 0:
            delta_pct = abs(brl - prev_amount) / prev_amount * 100.0
            if delta_pct >= balance_delta_pct:
                return None

        # Falha recente: respeita cooldown (evita spam no_route).
        # done/simulated recente com saldo estável: também cooldown (dry-run ou live já tentou).
        return f"cooldown status={status} id={recent.get('id')} prev_amount={prev_amount:.4f}"

    def _maybe_enqueue_brl_onramp(self) -> None:
        """Se há BRL livre acima do mínimo, enfileira BRL→USDT (target on_brl_deposit)."""
        cfg = _conversion_cfg(self.config)
        targets = cfg.get("targets") or {}
        asset_out = str(targets.get("on_brl_deposit") or "USDT").upper()
        min_notional = float(cfg.get("min_notional_usdt", 15))
        # BRL threshold ~ min_notional * rough FX; use min_notional as BRL floor too
        min_brl = float(cfg.get("min_brl_onramp", min_notional))
        cooldown_seconds = int(cfg.get("onramp_cooldown_seconds", 21600))  # 6h
        balance_delta_pct = float(cfg.get("onramp_balance_delta_pct", 5.0))

        try:
            from kucoin_api import get_balance

            brl = float(get_balance("BRL") or 0.0)
        except Exception as exc:
            logger.error("brl balance read failed: %s", exc, exc_info=True)
            return
        if brl < min_brl:
            return

        skip_reason = self._onramp_should_skip(
            asset_out,
            brl,
            cooldown_seconds=cooldown_seconds,
            balance_delta_pct=balance_delta_pct,
        )
        if skip_reason:
            logger.info("⏭ BRL onramp skip: %s (brl=%.4f)", skip_reason, brl)
            return

        dry = self._conversion_dry_run()
        req_id = self.db.enqueue_conversion(
            asset_in="BRL",
            asset_out=asset_out,
            amount_in=brl,
            requested_by="deposit_onramp",
            dry_run=dry,
            profile=getattr(self.state, "profile", "conservative"),
            symbol_owner=self.symbol,
        )
        logger.info(
            "📥 Enqueued BRL onramp conversion id=%s amount=%.4f → %s dry_run=%s",
            req_id,
            brl,
            asset_out,
            dry,
        )

    def _ensure_trade_funds(self, currency: str, amount_needed: float) -> float:
        """Garante fundos em TRADE (MAIN→TRADE) e devolve available TRADE."""
        currency = str(currency).upper()
        try:
            from kucoin_api import get_balance, get_balances, inner_transfer
        except Exception as exc:
            logger.error("kucoin_api import for conversion funds failed: %s", exc, exc_info=True)
            return 0.0

        # Sweep MAIN → TRADE for this currency
        try:
            main_balances = get_balances(account_type="main") or []
            main_avail = 0.0
            for b in main_balances:
                if str(b.get("currency") or "").upper() == currency:
                    main_avail = float(b.get("available") or 0.0)
                    break
            if main_avail > 0.01:
                result = inner_transfer(
                    currency=currency,
                    amount=main_avail,
                    from_account="main",
                    to_account="trade",
                )
                if result.get("success"):
                    logger.info(
                        "💸 conversion fund sweep %s main→trade amount=%.8f",
                        currency,
                        main_avail,
                    )
                else:
                    logger.error(
                        "conversion fund sweep failed %s: %s",
                        currency,
                        result.get("error") or result,
                    )
        except Exception as exc:
            logger.error("conversion MAIN→TRADE sweep error: %s", exc, exc_info=True)

        try:
            trade_avail = float(get_balance(currency) or 0.0)
        except Exception as exc:
            logger.error("conversion trade balance read failed: %s", exc, exc_info=True)
            return 0.0

        if trade_avail + 1e-12 < float(amount_needed):
            logger.error(
                "conversion TRADE funds short %s need=%.8f available=%.8f",
                currency,
                amount_needed,
                trade_avail,
            )
        return trade_avail

    def _process_conversion_queue(self) -> None:
        pending = self.db.list_pending_conversions(limit=5)
        if not pending:
            return

        from hop_executor import execute
        from route_graph import (
            compare_routes,
            diagnose_routes,
            find_best_route,
            savings_vs_usdt_bps,
        )

        opts = self._conversion_options()
        dry = self._conversion_dry_run()

        for req in pending:
            req_id = req["id"]
            asset_in = str(req["asset_in"]).upper()
            asset_out = str(req["asset_out"]).upper()
            amount_in = float(req["amount_in"])

            lock_owner = f"{self.symbol}:{self.state.profile}"
            # stale 120s: processo morto no meio da execução não trava a fila
            if not self.db.try_acquire_conversion_lock(owner=lock_owner, stale_seconds=120):
                logger.info("🔒 conversion lock held — skip queue")
                return

            try:
                if not dry:
                    trade_avail = self._ensure_trade_funds(asset_in, amount_in)
                    # KuCoin rejeita funds == 100% available com frequência (200004).
                    spendable = max(0.0, min(amount_in, trade_avail * 0.999))
                    if spendable <= 0:
                        self.db.update_conversion_request(
                            req_id,
                            status="failed",
                            result_json={
                                "error": "insufficient_trade_balance",
                                "asset_in": asset_in,
                                "amount_in": amount_in,
                                "trade_available": trade_avail,
                            },
                        )
                        logger.error(
                            "❌ conversion %s: insufficient TRADE %s need=%.8f avail=%.8f",
                            req_id,
                            asset_in,
                            amount_in,
                            trade_avail,
                        )
                        continue
                    if spendable + 1e-9 < amount_in:
                        logger.warning(
                            "conversion %s capping amount_in %.8f → %.8f (trade_avail=%.8f)",
                            req_id,
                            amount_in,
                            spendable,
                            trade_avail,
                        )
                        amount_in = spendable

                logger.info(
                    "🔎 conversion planning id=%s %s→%s amount=%.8f dry=%s",
                    req_id,
                    asset_in,
                    asset_out,
                    amount_in,
                    dry,
                )
                candidates = compare_routes(asset_in, asset_out, amount_in, opts=opts)
                plan = find_best_route(asset_in, asset_out, amount_in, opts=opts)
                if plan is None:
                    try:
                        diagnostics = diagnose_routes(asset_in, asset_out, amount_in, opts=opts)
                    except Exception as diag_exc:
                        logger.error(
                            "conversion %s diagnose_routes failed: %s",
                            req_id,
                            diag_exc,
                            exc_info=True,
                        )
                        diagnostics = [{"reason": f"diagnose_error:{diag_exc}"}]
                    result_payload = {
                        "error": "no_route",
                        "max_route_cost_pct": opts.max_route_cost_pct,
                        "max_spread_bps": opts.max_spread_bps,
                        "diagnostics": diagnostics[:8],
                    }
                    self.db.update_conversion_request(
                        req_id,
                        status="failed",
                        plan_json=None,
                        result_json=result_payload,
                    )
                    top_reasons = [
                        d.get("reason") for d in diagnostics if not d.get("accepted")
                    ][:3]
                    logger.error(
                        "❌ conversion %s: no route %s→%s amount=%.8f reasons=%s",
                        req_id,
                        asset_in,
                        asset_out,
                        amount_in,
                        top_reasons,
                    )
                    continue

                sav = savings_vs_usdt_bps(plan, candidates)
                plan_dict = plan.to_dict()
                plan_dict["savings_vs_usdt_bps"] = sav
                self.db.update_conversion_request(
                    req_id,
                    status="planned",
                    plan_json=plan_dict,
                )

                result = execute(plan, dry_run=dry)
                if result.status == "simulated":
                    final_status = "done"
                elif result.success:
                    final_status = "done"
                else:
                    final_status = result.status  # partial | failed

                self.db.update_conversion_request(
                    req_id,
                    status=final_status,
                    plan_json=plan_dict,
                    result_json=result.to_dict(),
                )
                for leg in result.legs:
                    self.db.insert_conversion_leg(
                        request_id=req_id,
                        leg_index=leg.leg_index,
                        symbol=leg.symbol,
                        side=leg.side,
                        amount_in=leg.amount_in,
                        amount_out=leg.amount_out,
                        fee=leg.fee,
                        order_id=leg.order_id or None,
                        status=leg.status,
                    )
                log_fn = logger.info if final_status == "done" else logger.error
                log_fn(
                    "🔀 conversion %s %s→%s status=%s hops=%s cost=%.2fbps out=%.8f dry=%s",
                    req_id,
                    asset_in,
                    asset_out,
                    final_status,
                    plan.hops,
                    plan.total_cost_pct * 10000,
                    result.amount_out,
                    dry,
                )
            finally:
                self.db.release_conversion_lock(owner=lock_owner)
