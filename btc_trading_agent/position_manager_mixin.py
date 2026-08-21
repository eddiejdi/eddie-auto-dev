"""PositionManagerMixin — gerenciamento de posições e saídas por slot.

Responsabilidades:
- Manter contagens de posição coerentes (raw_entry_count, logical_position_slots)
- Verificar e disparar saídas automáticas por slot: trailing, TP, SL, max_hold_hours
- Executar venda de slot individual com contabilidade e persistência
- Trailing stop global (posição agregada)

Nota: max_hold_hours é opt-in via config (padrão 0 = desativado).
"""

import logging
import os
import subprocess
import threading
import time
from typing import Any, Dict

from kucoin_api import place_market_order, _send_telegram_alert
from position_reconstruction import infer_logical_slots
from slot_exit_policy import (
    PerSlotExitPlanner,
    SignalSellContext,
    SignalSellPolicyResolver,
    SlotExitContext,
    SlotExitDecision,
)

logger = logging.getLogger("btc_trading_agent")

_TRADING_FEE_PCT = 0.001  # 0.1% — espelho da constante em trading_agent.py

# Pré-checagem de saldo: evita enviar ordens SELL que a exchange rejeitará
# com "Balance insufficient" (código 200004) e impede re-tentativas imediatas
# de slots fantasma enquanto o reconcile está em andamento.
_BALANCE_CHECK_TOLERANCE_PCT = 0.005  # 0.5% de tolerância size vs saldo
_BALANCE_INSUFFICIENT_COOLDOWN_S = 60  # cooldown após falha de saldo


class PositionManagerMixin:
    """Mixin que encapsula tracking de posição e saídas automáticas por slot."""

    _per_slot_exit_planner = PerSlotExitPlanner()
    _signal_sell_policy_resolver = SignalSellPolicyResolver()

    def _min_tradeable_dust(self) -> float:
        """Pó abaixo do mínimo negociável da exchange."""
        try:
            live_cfg = self._load_live_config()
        except Exception:
            live_cfg = getattr(self, "config", {}) or {}
        if not isinstance(live_cfg, dict):
            live_cfg = {}
        return float(live_cfg.get("min_tradeable_balance", 0.00001) or 0.00001)

    def _read_subaccount_spot_balances(self, quote_cur: str) -> tuple[float, float]:
        """Saldo disponível (quote, base) da subconta TRADE configurada.

        Sem subconta, usa a conta TRADE autenticada. Não vende nada.
        """
        base_cur = str(self.symbol).split("-")[0]
        try:
            live_cfg = self._load_live_config()
        except Exception:
            live_cfg = getattr(self, "config", {}) or {}
        subaccount = (
            str(live_cfg.get("kucoin_subaccount_name") or "").strip()
            if isinstance(live_cfg, dict)
            else ""
        )
        def _from_trade_accounts() -> tuple[float, float]:
            from kucoin_api import get_balances

            rows = get_balances(account_type="trade")
            by_ccy = {
                str(row.get("currency") or ""): float(row.get("available", 0) or 0)
                for row in rows
            }
            return by_ccy.get(quote_cur, 0.0), by_ccy.get(base_cur, 0.0)

        if subaccount:
            from kucoin_api import get_sub_account_balances

            try:
                rows = get_sub_account_balances()
            except Exception as exc:
                logger.info(
                    "📐 sub-account listing failed (%s); using authenticated TRADE "
                    "balances (sub API key? sub=%s)",
                    exc,
                    subaccount,
                )
                return _from_trade_accounts()

            want = subaccount.casefold()

            def _sum(currency: str) -> float:
                return sum(
                    float(account.get("available", 0) or 0)
                    for account in rows
                    if str(account.get("sub_name") or "").casefold() == want
                    and account.get("account_type") == "trade"
                    and account.get("currency") == currency
                )

            quote, base = _sum(quote_cur), _sum(base_cur)
            if quote > 0 or base > 0:
                return quote, base
            # Key de subconta: /api/v1/sub-accounts (master) volta vazio e
            # o equity ia a $0 (BTC aggressive 2026-08-20). A key autenticada
            # JÁ É a TRADE da subconta.
            logger.info(
                "📐 sub-account listing empty for %s; using authenticated TRADE balances",
                subaccount,
            )
            return _from_trade_accounts()

        from kucoin_api import get_balance

        return float(get_balance(quote_cur) or 0.0), float(get_balance(base_cur) or 0.0)

    def _align_position_to_exchange(self, price: float = 0.0) -> None:
        """Copia o saldo base da subconta para ``state.position`` sem flatten.

        Entries extra não são inventadas e nenhuma ordem é enviada.
        """
        if getattr(self.state, "dry_run", False):
            self._sync_position_tracking()
            return

        quote_cur = str(self.symbol).split("-")[1]
        try:
            _quote, base_qty = self._read_subaccount_spot_balances(quote_cur)
        except Exception as exc:
            logger.debug("Position align skipped (balance read failed): %s", exc)
            self._sync_position_tracking()
            return

        dust = self._min_tradeable_dust()
        tracked = max(float(getattr(self.state, "position", 0.0) or 0.0), 0.0)
        aligned = 0.0 if base_qty < dust else max(float(base_qty), 0.0)
        if abs(aligned - tracked) > max(dust, tracked * 0.005):
            logger.info(
                "📐 Position aligned to subaccount: tracked=%.8f -> exchange=%.8f "
                "(no flatten, no synthetic entries)",
                tracked,
                aligned,
            )
        self.state.position = aligned
        if price > 0:
            self.state.position_value = aligned * float(price)
        self._sync_position_tracking()

    def _read_base_balance_available(self) -> float:
        """Lê saldo disponível da moeda base (ex: SOL, BTC) da subconta TRADE.

        Retorna -1.0 quando não é possível ler (desativando a pré-checagem)
        ou em dry_run (sem saldo real). Usado pelo guard de SELL para evitar
        ordens que a KuCoin rejeitaria com código 200004 (Balance insufficient).
        """
        if getattr(self.state, "dry_run", False):
            return -1.0
        base_currency = str(self.symbol).split("-")[0]
        quote_currency = str(self.symbol).split("-")[1]
        try:
            _, base_qty = self._read_subaccount_spot_balances(quote_currency)
            return float(base_qty or 0.0)
        except Exception as exc:
            logger.debug(
                "Saldo %s indisponível para pré-checagem SELL: %s",
                base_currency, exc,
            )
            return -1.0

    def _sync_position_tracking(self) -> None:
        """Mantém contagem bruta e slot lógico coerentes com a posição atual."""
        entries = list(getattr(self.state, "entries", []) or [])
        raw_entry_count = len(entries)
        position = max(float(getattr(self.state, "position", 0.0) or 0.0), 0.0)
        self.state.position_count = raw_entry_count
        self.state.raw_entry_count = raw_entry_count
        self.state.logical_position_slots = infer_logical_slots(
            exchange_qty=position,
            entries=entries,
            dust=self._min_tradeable_dust(),
        )

    def _check_per_slot_exits(self, price: float) -> bool:
        """Verifica saída independente por slot: TP, trailing, SL e max_hold_hours."""
        entries = list(getattr(self.state, "entries", []) or [])
        if not entries:
            return False

        try:
            live_cfg = self._load_live_config()
        except Exception:
            live_cfg = self.config

        plan = self._per_slot_exit_planner.plan(
            entries,
            SlotExitContext(price=price, live_cfg=live_cfg, now=time.time()),
        )
        self.state.entries = plan.updated_entries
        return self._execute_slot_exit_decisions(price, plan.decisions) > 0

    def _execute_slot_exit_decisions(
        self,
        price: float,
        decisions: list[SlotExitDecision],
    ) -> int:
        """Executa uma lista de saídas independentes por slot.

        CONTRATO DE GUARDRAIL: este é o único choke point para toda venda de
        slot — tanto saídas por sinal (ProfitOnly, StopLoss, Emergency) quanto
        saídas autônomas (TP, trailing, MaxHold, SL por PerSlotExitPlanner).
        O guardrail é verificado aqui para cada decisão via
        _guardrail_allows_slot_sell().

        Novas regras em slot_exit_policy.py NÃO precisam chamar o guardrail
        diretamente — basta passar bypass_guardrail=True quando a regra for
        explicitamente de proteção de risco (stop-loss, emergency exit).
        """
        sold = 0
        for decision in sorted(decisions, key=lambda item: item.entry_idx, reverse=True):
            # Guard de cooldown após "Balance insufficient": se um slot acabou de
            # falhar por saldo (200004) ou pré-checagem, o reconcile síncrono foi
            # disparado e o estado pode ainda conter slots fantasma. Parar o
            # processamento dos próximos slots evita bombardear a exchange com
            # ordens inválidas no mesmo ciclo.
            cooldown_until = getattr(self, "_sell_balance_cooldown_until", 0.0)
            if time.time() < cooldown_until:
                logger.info(
                    "🔒 Batch SELL abortado: cooldown saldo insuficiente ativo "
                    "(restam %.1fs, %d slot(s) pendente(s) não tentados)",
                    cooldown_until - time.time(),
                    len(decisions) - sold,
                )
                break
            if not decision.bypass_guardrail:
                entries = list(getattr(self.state, "entries", []) or [])
                entry = next(
                    (
                        e for e in entries
                        if abs(float(e.get("price", 0) or 0) - decision.expected_entry_price) <= 1.0
                    ),
                    None,
                )
                size = float(entry.get("size", 0) or 0) if entry else 0.0
                if not self._guardrail_allows_slot_sell(
                    decision.expected_entry_price, size, price
                ):
                    continue
            if self._execute_slot_sell(
                decision.entry_idx,
                price,
                decision.reason,
                decision.expected_entry_price,
            ):
                sold += 1
        return sold

    def _execute_signal_slot_sells(self, price: float, reason: str, *, force: bool) -> int:
        """Aplica a política OO de SELL para multi-entry sem usar posição agregada."""
        decisions = self._select_signal_slot_sells(price, reason, force=force)
        sold = self._execute_slot_exit_decisions(price, decisions)
        if sold > 0:
            logger.info(
                "📎 SELL multi-slot independente: %d slot(s) realizados em $%.2f (%s)",
                sold,
                price,
                reason,
            )
        return sold

    def _select_signal_slot_sells(
        self,
        price: float,
        reason: str,
        *,
        force: bool,
    ) -> list[SlotExitDecision]:
        """Seleciona slots elegíveis para SELL sem executar as ordens."""
        entries = list(getattr(self.state, "entries", []) or [])
        if not entries:
            return []


        try:
            live_cfg = self._load_live_config()
        except Exception:
            live_cfg = getattr(self, "config", {})

        fee_pct = getattr(self, "_trading_fee_pct", _TRADING_FEE_PCT)
        ctx = SignalSellContext(
            price=price,
            reason=reason,
            force=force,
            live_cfg=live_cfg,
            fee_pct=fee_pct,
        )
        policy = self._signal_sell_policy_resolver.resolve(ctx)
        return policy.select(entries, ctx)

    def _execute_slot_sell(
        self, entry_idx: int, price: float, reason: str, expected_entry_price: float = 0.0
    ) -> bool:
        """Executa venda de um único slot independente.

        expected_entry_price: preço da entrada esperada (do loop em _check_per_slot_exits).
        Usado para re-validar o índice dentro do lock — protege contra double-sell por
        chamadas concorrentes onde índices se deslocam após sells anteriores.
        """
        fee_pct = getattr(self, "_trading_fee_pct", _TRADING_FEE_PCT)

        with self._trade_lock:
            try:
                entries = list(getattr(self.state, "entries", []) or [])
                if not entries:
                    return False

                # ── Guard anti-double-sell: re-valida o índice pelo preço esperado ──
                # Se outro thread/ciclo já vendeu este slot, o índice aponta para
                # um entry diferente. Buscamos pelo preço (tolerância $1) como chave.
                if expected_entry_price > 0 and entry_idx < len(entries):
                    actual_price = float(entries[entry_idx].get("price", 0) or 0)
                    if abs(actual_price - expected_entry_price) > 1.0:
                        # Índice deslocou — procura o entry pelo preço esperado
                        found = next(
                            (j for j, e in enumerate(entries)
                             if abs(float(e.get("price", 0) or 0) - expected_entry_price) <= 1.0),
                            None,
                        )
                        if found is None:
                            logger.warning(
                                "⚠️ Slot sell abortado: entry_price=%.2f não encontrado "
                                "no state (já vendido por ciclo concorrente?)",
                                expected_entry_price,
                            )
                            return False
                        logger.debug(
                            "🔄 Slot sell: índice corrigido %d→%d (price mismatch %.2f→%.2f)",
                            entry_idx, found, actual_price, expected_entry_price,
                        )
                        entry_idx = found

                if entry_idx >= len(entries):
                    return False

                entry = entries[entry_idx]
                entry_price = float(entry.get("price", 0) or 0)
                size = float(entry.get("size", 0) or 0)
                if entry_price <= 0 or size <= 0:
                    return False

                # ── Pré-checagem de saldo (modo real): abortar SELL antes de
                # enviar ordem inválida. Slots fantasma no state (após venda de
                # subconta compartilhada ou reconciliação incompleta) levariam
                # a rejeições 200004 pela exchange e, sem este guard, a
                # re-tentativas imediatas no ciclo seguinte.
                if not self.state.dry_run:
                    cooldown_until = getattr(
                        self, "_sell_balance_cooldown_until", 0.0
                    )
                    if time.time() < cooldown_until:
                        logger.info(
                            "🔒 SELL slot #%d abortado (cooldown saldo insuficiente): "
                            "size=%.8f — aguardando reconcile",
                            entry_idx + 1, size,
                        )
                        return False

                    available = self._read_base_balance_available()
                    if available >= 0:
                        dust = self._min_tradeable_dust()
                        tolerance = max(size * _BALANCE_CHECK_TOLERANCE_PCT, dust)
                        if size > available + tolerance:
                            base_cur = str(self.symbol).split("-")[0]
                            logger.warning(
                                "⚠️ SELL slot #%d abortado por pré-checagem: "
                                "size=%.8f %s > saldo real=%.8f %s (tol=%.8f). "
                                "Disparando reconcile síncrono + cooldown %ds.",
                                entry_idx + 1, size, base_cur,
                                available, base_cur, tolerance,
                                _BALANCE_INSUFFICIENT_COOLDOWN_S,
                            )
                            try:
                                self._reconcile_position_with_exchange(price)
                            except Exception as exc:
                                logger.debug(
                                    "reconcile síncrono após pré-check falhou: %s",
                                    exc,
                                )
                            self._sell_balance_cooldown_until = (
                                time.time() + _BALANCE_INSUFFICIENT_COOLDOWN_S
                            )
                            return False

                gross_pnl = (price - entry_price) * size
                sell_fee = price * size * fee_pct
                buy_fee = entry_price * size * fee_pct
                pnl = gross_pnl - sell_fee - buy_fee
                pnl_pct = (
                    (price * (1 - fee_pct)) / (entry_price * (1 + fee_pct)) - 1
                ) * 100

                order_id = None
                if self.state.dry_run:
                    logger.info(
                        "🔴 [DRY] SELL slot #%d %s BTC @ $%.2f "
                        "(PnL $%.4f / %.2f%%) — %s",
                        entry_idx + 1, f"{size:.6f}", price, pnl, pnl_pct, reason,
                    )
                else:
                    result = place_market_order(
                        self.symbol, "sell", size=size,
                        notify_extra={
                            "invested": entry_price * size,
                            "proceeds": price * size,
                            "pnl": pnl,
                            "pnl_pct": pnl_pct,
                        },
                    )
                    if not result.get("success"):
                        err_code = str(
                            (result.get("raw") or result).get("code", "")
                        )
                        if err_code == "dust_skip" or result.get("skip_notify"):
                            logger.warning(
                                "🧹 SELL dust skip silencioso slot #%d size=%.8f — "
                                "removendo slot do state (sem Telegram).",
                                entry_idx + 1, size,
                            )
                            try:
                                buy_trade_id = entry.get("trade_id")
                                if buy_trade_id:
                                    self.db.merge_trade_metadata(
                                        int(buy_trade_id),
                                        {"closed_reason": "dust_below_minsize"},
                                    )
                            except Exception as exc:
                                logger.debug("dust metadata: %s", exc)
                            entries.pop(entry_idx)
                            self.state.entries = entries
                            self.state.position = max(0.0, self.state.position - size)
                            if entries:
                                total_sz = sum(float(e.get("size", 0) or 0) for e in entries)
                                total_ct = sum(
                                    float(e.get("size", 0) or 0) * float(e.get("price", 0) or 0)
                                    for e in entries
                                )
                                self.state.entry_price = total_ct / total_sz if total_sz > 0 else 0.0
                            else:
                                self.state.entry_price = 0.0
                                self.state.entries = []
                                self.state.position = 0.0
                            self._sync_position_tracking()
                            return True
                        logger.error("❌ Slot sell failed: %s", result)
                        if err_code == "200004":  # Balance insufficient
                            # Reconcile SÍNCRONO: slots fantasma precisam ser
                            # saneados antes do próximo ciclo disparar novas
                            # ordens inválidas. Thread daemon deixava o state
                            # desincronizado por vários ciclos de polling.
                            logger.warning(
                                "⚠️ SELL rejeitado (Balance insufficient): "
                                "size=%.8f, slot #%d. Reconcile síncrono + "
                                "cooldown %ds ativados.",
                                size, entry_idx + 1,
                                _BALANCE_INSUFFICIENT_COOLDOWN_S,
                            )
                            try:
                                self._reconcile_position_with_exchange(price)
                            except Exception as exc:
                                logger.debug(
                                    "reconcile síncrono após 200004 falhou: %s",
                                    exc,
                                )
                            self._sell_balance_cooldown_until = (
                                time.time() + _BALANCE_INSUFFICIENT_COOLDOWN_S
                            )
                        return False
                    order_id = result.get("orderId")
                    logger.info(
                        "🔴 SELL slot #%d %s BTC @ $%.2f "
                        "(PnL $%.4f / %.2f%%) — %s",
                        entry_idx + 1, f"{size:.6f}", price, pnl, pnl_pct, reason,
                    )

                # ── Remover slot e recalcular posição ──
                entries.pop(entry_idx)
                self.state.entries = entries
                self.state.position = max(0.0, self.state.position - size)

                if entries:
                    total_sz = sum(float(e.get("size", 0) or 0) for e in entries)
                    total_ct = sum(
                        float(e.get("size", 0) or 0) * float(e.get("price", 0) or 0)
                        for e in entries
                    )
                    self.state.entry_price = total_ct / total_sz if total_sz > 0 else 0.0
                else:
                    self.state.entry_price = 0.0
                    self.state.entries = []
                    self.state.position = 0.0
                    self.state.target_sell_price = 0.0
                    self.state.target_sell_reason = ""
                    self.state.buy_success_pressure = 0.0
                    self.state.buy_success_factor = 1.0
                    self.state.buy_dynamic_batch_cap_usdt = 0.0
                    self.state.dca_valley_low = 0.0
                    self.state.trailing_high = 0.0

                self._sync_position_tracking()

                self.state.last_sell_entry_price = entry_price
                self.state.last_sell_ts = time.time()
                logger.info(
                    "🔒 REBUY lock: próxima compra deve ser < $%.2f (entrada slot #%d)",
                    entry_price, entry_idx + 1,
                )

                self.state.total_pnl += pnl
                if pnl > 0:
                    self.state.winning_trades += 1
                self.state.total_trades += 1
                self.state.daily_trades += 1
                self.state.last_trade_time = time.time()

                try:
                    meta: Dict[str, Any] = {
                        "slot_exit_reason": reason,
                        "slot_entry_price": entry_price,
                        "slots_remaining": len(entries),
                        "source": "kucoin_live" if not self.state.dry_run else "dry_run",
                    }
                    # slot_buy_trade_id: chave exata para matching no SQL do painel
                    # evita falha de join por imprecisão de float no slot_entry_price
                    buy_trade_id = entry.get("trade_id")
                    if buy_trade_id:
                        meta["slot_buy_trade_id"] = buy_trade_id
                    if order_id:
                        meta["orderId"] = order_id
                    trade_id = self.db.record_trade(
                        symbol=self.symbol,
                        side="sell",
                        price=price,
                        size=size,
                        funds=round(price * size, 2),
                        order_id=order_id,
                        dry_run=self.state.dry_run,
                        metadata=meta,
                        profile=self._current_profile(),
                    )
                    self.db.update_trade_pnl(trade_id, pnl, pnl_pct)
                    self._last_trade_id = trade_id
                except Exception as e:
                    logger.debug("Slot sell DB error: %s", e)

                # Trigger pós-venda: sync de balanço + notificação Telegram via Ollama
                if not self.state.dry_run:
                    self._post_sell_notify(
                        entry_price=entry_price,
                        sell_price=price,
                        size=size,
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        reason=reason,
                        slots_remaining=len(entries),
                    )

                return True

            except Exception as e:
                logger.error("❌ Slot sell error: %s", e)
                return False

    def _execute_profitable_slot_sells(self, price: float, reason: str) -> int:
        """Vende apenas os slots com PnL líquido positivo no preço atual.

        Usado no caminho de SELL normal do modelo para evitar liquidar toda a
        posição agregada quando apenas parte das entradas está em lucro.

        Returns:
            Quantidade de slots vendidos com sucesso.
        """
        sold = self._execute_signal_slot_sells(price, reason, force=False)
        if sold <= 0:
            logger.info(
                "📎 SELL normal preservado: nenhum slot com lucro líquido em $%.2f",
                price,
            )
        return sold

    # ── Post-sell: balance sync + Telegram via Ollama GPU1 ──────────────────

    _SELL_NOTIFY_SCRIPT = os.getenv(
        "KUCOIN_SYNC_SCRIPT",
        "/apps/crypto-trader/trading/scripts/kucoin_postgres_sync.py",
    )
    _SELL_NOTIFY_OLLAMA_HOST = os.getenv("OLLAMA_PLAN_HOST", "http://192.168.15.2:11437")
    _SELL_NOTIFY_OLLAMA_MODEL = os.getenv("OLLAMA_SELL_NOTIFY_MODEL", "trading-analyst:latest")

    def _post_sell_notify(
        self,
        entry_price: float,
        sell_price: float,
        size: float,
        pnl: float,
        pnl_pct: float,
        reason: str,
        slots_remaining: int,
    ) -> None:
        """Dispara thread daemon: sync KuCoin → balance snapshot + Telegram via Ollama."""
        t = threading.Thread(
            target=self._post_sell_notify_worker,
            args=(entry_price, sell_price, size, pnl, pnl_pct, reason, slots_remaining),
            daemon=True,
            name="sell-notify",
        )
        t.start()

    def _post_sell_notify_worker(
        self,
        entry_price: float,
        sell_price: float,
        size: float,
        pnl: float,
        pnl_pct: float,
        reason: str,
        slots_remaining: int,
    ) -> None:
        """Executa em background: sync balanço KuCoin → Ollama GPU1 → Telegram."""
        # 1. Sync exchange balance snapshot
        try:
            # O sync precisa das credenciais MASTER para enxergar todas as
            # contas; herdar KUCOIN_SECRET_NAMES da subconta do perfil gerava
            # snapshots parciais (~$50) que derrubavam o gráfico patrimonial.
            sync_env = os.environ.copy()
            sync_env.pop("KUCOIN_SECRET_NAMES", None)
            proc = subprocess.run(
                ["python3", self._SELL_NOTIFY_SCRIPT],
                env=sync_env,
                timeout=45,
                capture_output=True,
            )
            if proc.returncode == 0:
                logger.info("💰 Balance sync pós-venda: OK")
            else:
                logger.warning("Balance sync pós-venda falhou: %s", proc.stderr.decode()[:200])
        except Exception as exc:
            logger.warning("Balance sync pós-venda erro: %s", exc)

        # 1b. Reconciliação pós-venda: detecta slots fantasma após venda real
        if slots_remaining > 0:
            self._reconcile_position_with_exchange(sell_price)

        # 2. Gerar mensagem via Ollama GPU1
        profile = self._current_profile() if callable(getattr(self, "_current_profile", None)) else self.symbol
        sign = "+" if pnl >= 0 else ""
        fallback_msg = (
            f"🔴 *Venda executada* — {profile}\n"
            f"*Motivo:* {reason}\n"
            f"*Entrada:* ${entry_price:,.2f}  →  *Saída:* ${sell_price:,.2f}\n"
            f"*Tamanho:* {size:.6f} BTC\n"
            f"*PnL:* {sign}${pnl:.4f} ({sign}{pnl_pct:.2f}%)\n"
            f"*Slots restantes:* {slots_remaining}"
        )
        try:
            import requests as _req
            prompt = (
                f"Você é o assistente do bot de trading BTC do Eddie. "
                f"Gere um comunicado curto (máx 6 linhas) sobre esta venda, com emojis. "
                f"Seja direto, sem explicar conceitos.\n\n"
                f"Perfil: {profile}\n"
                f"Motivo da saída: {reason}\n"
                f"Preço de entrada: ${entry_price:,.2f}\n"
                f"Preço de saída: ${sell_price:,.2f}\n"
                f"Tamanho: {size:.6f} BTC\n"
                f"PnL: {sign}${pnl:.4f} ({sign}{pnl_pct:.2f}%)\n"
                f"Slots restantes na posição: {slots_remaining}\n\n"
                f"Comunicado:"
            )
            resp = _req.post(
                f"{self._SELL_NOTIFY_OLLAMA_HOST}/api/generate",
                json={"model": self._SELL_NOTIFY_OLLAMA_MODEL, "prompt": prompt, "stream": False},
                timeout=30,
            )
            msg = resp.json().get("response", "").strip() if resp.ok else fallback_msg
        except Exception as exc:
            logger.warning("Ollama sell notify erro: %s", exc)
            msg = fallback_msg

        # 3. Enviar via Telegram — usa proxy Squid se TELEGRAM_PROXY_URL configurado
        try:
            import requests as _req
            from kucoin_api import (
                _resolve_telegram_bot_token,
                _resolve_telegram_chat_id,
                _resolve_telegram_thread_id,
                _get_extra_telegram_chat_ids,
            )
            bot_token = _resolve_telegram_bot_token()
            chat_id = _resolve_telegram_chat_id()
            thread_id = _resolve_telegram_thread_id()
            if bot_token and chat_id:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
                if thread_id:
                    payload["message_thread_id"] = int(thread_id)
                proxy_url = (os.getenv("TELEGRAM_PROXY_URL", "") or "").strip()
                response = None

                if proxy_url:
                    try:
                        response = _req.post(
                            url,
                            json=payload,
                            proxies={"https": proxy_url, "http": proxy_url},
                            timeout=10,
                        )
                    except Exception as exc:
                        logger.warning(
                            "Telegram sell notify via proxy falhou, retry direto: %s", exc
                        )

                if response is None:
                    response = _req.post(url, json=payload, timeout=10)

                if getattr(response, "ok", True):
                    logger.info("📨 Telegram sell notify enviado")
                else:
                    logger.warning(
                        "Telegram sell notify rejeitado: status=%s body=%s",
                        getattr(response, "status_code", "?"),
                        getattr(response, "text", "")[:200],
                    )
                # Enviar para destinatários extras (sem tópico)
                for _extra in _get_extra_telegram_chat_ids():
                    try:
                        _req.post(
                            f"https://api.telegram.org/bot{bot_token}/sendMessage",
                            json={"chat_id": _extra, "text": msg, "parse_mode": "Markdown"},
                            timeout=10,
                        )
                    except Exception as _ex:
                        logger.warning("Telegram extra notify falhou (%s): %s", _extra, _ex)
        except Exception as exc:
            logger.warning("Telegram sell notify erro: %s", exc)

    # ── Reconciliação de posição com a exchange ──────────────────────────────

    def _has_exclusive_exchange_balance(self, subaccount: str = "") -> bool:
        """True se o saldo da exchange consultado pertence só a este profile.

        Conta compartilhada (master kucoin/homelab, vários agents no mesmo
        book) continua só-alerta. Subconta nomeada, flag de credencial
        dedicada ou KUCOIN_SECRET_NAMES=kucoin/sub-* único = exclusivo.
        """
        if str(subaccount or "").strip():
            return True
        try:
            live_cfg = self._load_live_config()
        except Exception:
            live_cfg = getattr(self, "config", {}) or {}
        if not isinstance(live_cfg, dict):
            live_cfg = {}
        if live_cfg.get("kucoin_require_dedicated_credentials"):
            return True
        secrets = os.environ.get("KUCOIN_SECRET_NAMES", "")
        names = [part.strip() for part in secrets.split(",") if part.strip()]
        if len(names) == 1 and "/sub-" in names[0].lower():
            return True
        return False

    def _restore_persistent_reconciliation_candidate(
        self,
        real_balance: float,
        db_position: float,
        tolerance: float,
        profile: str,
        subaccount: str,
        *,
        exclusive: bool = False,
    ) -> bool:
        """Readota um único BUY persistente que explica o excesso na exchange.

        Sem subconta nomeada só segue se o saldo da exchange for exclusivo
        deste profile (credencial kucoin/sub-* dedicada).
        """
        if not subaccount and not exclusive:
            return False

        excess = real_balance - db_position
        if excess <= tolerance:
            return False

        try:
            candidates = self.db.get_reconciliable_open_buys(
                self.symbol, profile, subaccount,
            )
        except Exception as exc:
            logger.warning("[reconcile] Persistent candidate lookup failed: %s", exc)
            return False

        # Reconciliações pós-compra/pós-venda rodam em background. Serializar a
        # seleção e a readopção impede que dois threads anexem o mesmo BUY.
        with self._trade_lock:
            entries = list(getattr(self.state, "entries", []) or [])
            represented_ids = {
                int(entry["trade_id"])
                for entry in entries
                if entry.get("trade_id") is not None
            }
            represented_orders = {
                str(entry["order_id"])
                for entry in entries
                if entry.get("order_id")
            }
            matching = []
            for candidate in candidates:
                trade_id = candidate.get("id")
                order_id = str(candidate.get("order_id") or "")
                size = float(candidate.get("size", 0) or 0)
                entry_price = float(candidate.get("price", 0) or 0)
                if not trade_id or not order_id or size <= 0 or entry_price <= 0:
                    continue
                if int(trade_id) in represented_ids or order_id in represented_orders:
                    continue
                if abs(excess - size) <= tolerance:
                    matching.append(candidate)

            if len(matching) != 1:
                return False

            candidate = matching[0]
            trade_id = int(candidate["id"])
            order_id = str(candidate["order_id"])
            entry_price = float(candidate["price"])
            try:
                persisted = self.db.mark_open_buy_restored(
                    trade_id, self.symbol, profile, subaccount, order_id,
                )
            except Exception as exc:
                logger.warning("[reconcile] Persistent candidate claim failed: %s", exc)
                return False
            if not persisted:
                return False

            metadata = candidate.get("metadata") or {}
            if not isinstance(metadata, dict):
                metadata = {}
            entries.append({
                "price": entry_price,
                "size": float(candidate["size"]),
                "ts": float(candidate.get("timestamp", 0) or time.time()),
                "trade_id": trade_id,
                "order_id": order_id,
                "target_sell": float(metadata.get("target_sell_price") or 0),
                "target_sell_reason": str(metadata.get("target_sell_reason") or ""),
                "trailing_high": entry_price,
                "dry_run": False,
            })
            self.state.entries = entries
            total_size = sum(float(entry.get("size", 0) or 0) for entry in entries)
            total_cost = sum(
                float(entry.get("size", 0) or 0) * float(entry.get("price", 0) or 0)
                for entry in entries
            )
            self.state.position = total_size
            self.state.entry_price = total_cost / total_size if total_size > 0 else 0.0
            self._sync_position_tracking()
        logger.warning(
            "[reconcile] Restored persistent BUY #%s for %s/%s: %.8f %s "
            "(order_id=%s, exchange excess=%.8f)",
            trade_id,
            self.symbol,
            profile,
            float(candidate["size"]),
            self.symbol.split("-")[0],
            order_id,
            excess,
        )
        return True

    def _adopt_untracked_exchange_excess(
        self,
        *,
        excess: float,
        real_balance: float,
        db_position: float,
        current_price: float,
        profile: str,
        subaccount: str,
        base_currency: str,
        tolerance: float,
    ) -> bool:
        """Incorpora excesso exclusivo no state e no DB (lote ou fill)."""
        dust = self._min_tradeable_dust()
        if excess <= max(dust, 0.0):
            return False

        price = float(current_price or 0.0)
        if price <= 0:
            entries = list(getattr(self.state, "entries", []) or [])
            if entries:
                price = float(entries[-1].get("price", 0) or 0)
        if price <= 0:
            try:
                from kucoin_api import get_price
                price = float(get_price(self.symbol) or 0.0)
            except Exception:
                price = 0.0
        if price <= 0:
            logger.warning("[reconcile] Sem preço para adotar excesso %.8f %s", excess, base_currency)
            return False

        meta = {
            "reconciled_exchange_excess": True,
            "reconcile_real_balance": round(real_balance, 8),
            "reconcile_db_position_before": round(db_position, 8),
            "kucoin_subaccount": subaccount or None,
        }

        with self._trade_lock:
            entries = list(getattr(self.state, "entries", []) or [])
            db_now = sum(float(e.get("size", 0) or 0) for e in entries)
            if real_balance <= db_now + tolerance:
                return True
            excess_now = real_balance - db_now
            if excess_now <= max(dust, 0.0):
                return False

            adopted_via = "new_lot"
            trade_id = None
            if entries:
                last = dict(entries[-1])
                last_price = float(last.get("price", 0) or 0) or price
                last_size = float(last.get("size", 0) or 0)
                last_id = last.get("trade_id")
                if last_id and last_size > 0 and last_price > 0:
                    new_size = last_size + excess_now
                    try:
                        updated = self.db.update_trade_fill(
                            int(last_id),
                            new_size,
                            last_price,
                            funds=new_size * last_price,
                        )
                    except Exception as exc:
                        logger.warning("[reconcile] update_trade_fill failed: %s", exc)
                        updated = False
                    if updated:
                        try:
                            self.db.merge_trade_metadata(int(last_id), meta)
                        except Exception as exc:
                            logger.warning("[reconcile] merge metadata failed: %s", exc)
                        last["size"] = new_size
                        entries[-1] = last
                        trade_id = int(last_id)
                        adopted_via = "fill_adjust"
                if adopted_via != "fill_adjust":
                    adopted_via = "new_lot"

            if adopted_via == "new_lot":
                order_id = f"reconcile-{profile}-{int(time.time())}"
                try:
                    trade_id = self.db.record_trade(
                        self.symbol,
                        "buy",
                        price,
                        size=excess_now,
                        funds=price * excess_now,
                        order_id=order_id,
                        dry_run=False,
                        metadata=meta,
                        profile=profile,
                    )
                except Exception as exc:
                    logger.warning("[reconcile] record_trade do excesso falhou: %s", exc)
                    return False
                entries.append({
                    "price": price,
                    "size": excess_now,
                    "ts": time.time(),
                    "trade_id": trade_id,
                    "order_id": order_id,
                    "target_sell": 0.0,
                    "target_sell_reason": "reconciled_exchange_excess",
                    "trailing_high": price,
                    "dry_run": False,
                })

            self.state.entries = entries
            total_size = sum(float(e.get("size", 0) or 0) for e in entries)
            total_cost = sum(
                float(e.get("size", 0) or 0) * float(e.get("price", 0) or 0)
                for e in entries
            )
            self.state.position = total_size
            self.state.entry_price = total_cost / total_size if total_size > 0 else 0.0
            self._sync_position_tracking()

        logger.warning(
            "✅ [reconcile] Excesso adotado (%s) %s/%s: +%.8f %s via %s trade_id=%s "
            "(DB %.8f → exchange %.8f)",
            adopted_via, self.symbol, profile, excess_now, base_currency,
            adopted_via, trade_id, db_now, real_balance,
        )
        _send_telegram_alert(
            f"✅ *Reconciliação efetiva* `{self.symbol}`/`{profile}`\n"
            f"Excesso da exchange *adotado* ({adopted_via}):\n"
            f"+`{excess_now:.8f}` {base_currency} @ `${price:.2f}`\n"
            f"DB era `{db_now:.8f}` → agora `{self.state.position:.8f}` "
            f"(exchange `{real_balance:.8f}`)"
        )
        return True

    def _reconcile_position_with_exchange(self, current_price: float = 0.0) -> int:
        """Reconcilia os slots do DB com o saldo real de BTC na exchange.

        Detecta slots fantasma criados por race condition entre agentes que
        compartilham a mesma conta KuCoin: quando o agente aggressive vende BTC
        que o conservative acredita ser seu, o conservative fica com posição
        registrada no DB mas sem BTC na exchange.

        Ao detectar essa divergência (DB > exchange), fecha os slots excedentes
        do state (sem gravar sell sintético no DB), do slot mais recente para
        o mais antigo, até que DB == saldo real ± tolerância.

        Na direção oposta (exchange > DB), se o saldo for exclusivo deste
        profile (subconta ou credencial kucoin/sub-*), a reconciliação é
        efetiva: readota BUY persistente ou incorpora o excesso no lote.
        Conta compartilhada continua só-alerta.

        Chamado:
        - Em background quando sell falha com código 200004 (Balance insufficient)
        - Em background após cada venda bem-sucedida com slots restantes
        - Em background após cada compra bem-sucedida

        Returns:
            Número de slots fechados por reconciliação (0 = consistente,
            readopção, adoção de excesso ou alerta em conta compartilhada).
        """
        if self.state.dry_run:
            return 0

        base_currency = self.symbol.split("-")[0]

        entries = list(getattr(self.state, "entries", []) or [])

        profile = self._current_profile() if callable(getattr(self, "_current_profile", None)) else "default"
        try:
            live_cfg = self._load_live_config()
        except Exception:
            live_cfg = getattr(self, "config", {}) or {}
        subaccount = (
            str(live_cfg.get("kucoin_subaccount_name") or "").strip()
            if isinstance(live_cfg, dict) else ""
        )
        exclusive = self._has_exclusive_exchange_balance(subaccount)
        if not entries and not exclusive:
            return 0

        try:
            if subaccount:
                from kucoin_api import get_sub_account_balances

                matching_balances = [
                    account
                    for account in get_sub_account_balances()
                    if account.get("sub_name") == subaccount
                    and account.get("account_type") == "trade"
                    and account.get("currency") == base_currency
                ]
                if not matching_balances:
                    raise RuntimeError(
                        f"saldo {base_currency} da subconta {subaccount} indisponível"
                    )
                real_balance = sum(
                    float(account.get("available", 0) or 0)
                    for account in matching_balances
                )
            else:
                from kucoin_api import get_balance
                real_balance = get_balance(base_currency)
        except Exception as exc:
            logger.warning("⚠️ Reconciliação: falha ao consultar saldo KuCoin — %s", exc)
            return 0

        db_position = sum(float(e.get("size", 0) or 0) for e in entries)
        # Tolerância de 0.5% ou 1 satoshi — evita falsos positivos por arredondamento
        tolerance = max(db_position * 0.005, 0.000_000_01)

        if real_balance > db_position + tolerance:
            if self._restore_persistent_reconciliation_candidate(
                real_balance, db_position, tolerance, profile, subaccount,
                exclusive=exclusive,
            ):
                return 0
            excess = real_balance - db_position
            if exclusive and self._adopt_untracked_exchange_excess(
                excess=excess,
                real_balance=real_balance,
                db_position=db_position,
                current_price=current_price,
                profile=profile,
                subaccount=subaccount,
                base_currency=base_currency,
                tolerance=tolerance,
            ):
                return 0
            logger.warning(
                "⚠️ [reconcile] Exchange tem mais %s do que o DB conhece (%s/%s): "
                "DB=%.8f | Exchange=%.8f | excesso=%.8f — %s",
                base_currency, self.symbol, profile, db_position, real_balance, excess,
                "adotar falhou" if exclusive else "conta compartilhada, sem ação automática",
            )
            _send_telegram_alert(
                f"⚠️ *Reconciliação* `{self.symbol}`/`{profile}`\n"
                f"Exchange tem *mais* {base_currency} do que o DB sabe:\n"
                f"DB: `{db_position:.8f}` | Exchange: `{real_balance:.8f}` | "
                f"excesso: `{excess:.8f}`\n"
                + (
                    "Adoção automática falhou — verificar logs."
                    if exclusive
                    else (
                        "Sem ação automática (risco de atribuir saldo de outro "
                        "profile na mesma subconta) — verificar manualmente."
                    )
                )
            )
            return 0

        if real_balance >= db_position - tolerance:
            return 0  # consistente, nada a fazer

        logger.warning(
            "⚠️ [reconcile] Divergência detectada (pré-lock): DB=%.8f %s | Exchange=%.8f %s | "
            "phantom~%.8f %s — confirmando dentro do lock antes de fechar slots",
            db_position, base_currency,
            real_balance, base_currency,
            db_position - real_balance, base_currency,
        )

        if not current_price or current_price <= 0:
            try:
                from kucoin_api import get_price
                current_price = get_price(self.symbol) or 0.0
            except Exception:
                pass

        fee_pct = getattr(self, "_trading_fee_pct", _TRADING_FEE_PCT)

        closed = 0
        # Fecha do slot mais recente para o mais antigo até eliminar o excesso.
        with self._trade_lock:
            # Recomputa db_position/tolerance/phantom a partir de uma leitura
            # FRESCA de entries feita já dentro do lock — os valores calculados
            # acima (pré-lock) só servem para decidir se vale a pena buscar
            # current_price e entrar aqui. Usá-los para a decisão de quais/quantos
            # slots fechar seria uma condição de corrida (TOCTOU): outro trade
            # pode ter mutado self.state.entries entre aquela leitura e a
            # aquisição do lock, tornando phantom_btc/tolerance obsoletos.
            entries = list(getattr(self.state, "entries", []) or [])
            db_position = sum(float(e.get("size", 0) or 0) for e in entries)
            tolerance = max(db_position * 0.005, 0.000_000_01)
            phantom_btc = db_position - real_balance

            if phantom_btc <= tolerance:
                return 0  # já consistente no momento em que o lock foi obtido

            logger.warning(
                "⚠️ [reconcile] Divergência confirmada dentro do lock: DB=%.8f %s | "
                "Exchange=%.8f %s | phantom=%.8f %s — fechando slots excedentes",
                db_position, base_currency, real_balance, base_currency,
                phantom_btc, base_currency,
            )

            for idx in range(len(entries) - 1, -1, -1):
                if phantom_btc <= tolerance:
                    break

                entry = entries[idx]
                entry_price = float(entry.get("price", 0) or 0)
                size = float(entry.get("size", 0) or 0)
                if size <= 0 or entry_price <= 0:
                    continue

                close_price = current_price if current_price > 0 else entry_price
                gross_pnl = (close_price - entry_price) * size
                sell_fee = close_price * size * fee_pct
                buy_fee = entry_price * size * fee_pct
                pnl = gross_pnl - sell_fee - buy_fee
                pnl_pct = (
                    (close_price * (1 - fee_pct)) / (entry_price * (1 + fee_pct)) - 1
                ) * 100 if entry_price > 0 else 0.0

                # Fecha o slot apenas no state — NÃO grava sell sintético no DB.
                # Sells sem order_id corrompem cumulative_pnl e o histórico de trades.
                # O buy correspondente é marcado como 'closed' no DB pelo close_open_buys.
                try:
                    buy_trade_id = entry.get("trade_id")
                    if buy_trade_id:
                        self.db.merge_trade_metadata(
                            int(buy_trade_id),
                            {
                                "closed_reason": "reconciled_phantom",
                                "phantom_close_price": round(close_price, 2),
                                "phantom_pnl": round(pnl, 6),
                                "phantom_real_balance": round(real_balance, 8),
                                "phantom_db_position": round(db_position, 8),
                            },
                        )
                    logger.warning(
                        "🔧 [reconcile] Slot #%d removido do state: %.8f BTC @ $%.2f "
                        "(PnL estimado: $%.4f / %.2f%%) [buy_trade_id=%s, sem sell sintético no DB]",
                        idx + 1, size, close_price, pnl, pnl_pct, buy_trade_id,
                    )
                except Exception as exc:
                    logger.error("❌ [reconcile] metadata error slot #%d: %s", idx + 1, exc)

                entries.pop(idx)
                phantom_btc -= size
                closed += 1

            # Atualizar state dentro do lock
            self.state.entries = entries
            if entries:
                total_sz = sum(float(e.get("size", 0) or 0) for e in entries)
                total_ct = sum(
                    float(e.get("size", 0) or 0) * float(e.get("price", 0) or 0)
                    for e in entries
                )
                self.state.position = total_sz
                self.state.entry_price = total_ct / total_sz if total_sz > 0 else 0.0
            else:
                self.state.position = 0.0
                self.state.entry_price = 0.0
                self.state.entries = []
                self.state.target_sell_price = 0.0
                self.state.target_sell_reason = ""
                self.state.trailing_high = 0.0

            self._sync_position_tracking()

        if closed > 0:
            logger.warning(
                "🔧 [reconcile] %d slot(s) fantasma fechados. "
                "Posição final: %.8f BTC (%d entries)",
                closed, self.state.position, len(self.state.entries),
            )

        self._sanitize_stale_positions()
        return closed

    def _sanitize_stale_positions(self) -> None:
        """Scan DB for stale BUY positions and close them.

        Runs after every reconciliation cycle. Detects:
        1. Shadow simulation positions (dry_run=True) without closed_reason
        2. Positions older than 30 days (orphan safety net)
        3. Positions from inactive profiles (service stopped)

        Each detection rule is independent (OR logic). Closed positions get
        a `closed_reason` in metadata so they're excluded from future scans
        and don't appear in Grafana dashboards.
        """
        try:
            profile = (
                self._current_profile()
                if callable(getattr(self, "_current_profile", None))
                else "default"
            )
        except Exception:
            profile = "default"

        try:
            live_cfg = self._load_live_config()
        except Exception:
            live_cfg = getattr(self, "config", {}) or {}

        # Determine which profiles are active (have a running service)
        # by checking if this agent's profile matches. Other profiles
        # that we know about but aren't running are "inactive".
        active_profiles = {profile}

        # Profiles that this agent instance knows are definitely running
        # (aggressive instance knows aggressive is active, etc.)
        # Conservative profiles are handled by separate instances —
        # don't mark them stale if they might have their own agent running.
        # Only mark profiles that are clearly dead (no service, balance=0).
        inactive_candidates = []
        try:
            if hasattr(self, "db") and self.db:
                # Check if conservative profiles have any recent activity
                for candidate_profile in ("conservative", "default", "exchange_sync"):
                    if candidate_profile == profile:
                        continue
                    recent = self.db.count_trades_since(
                        self.symbol,
                        time.time() - 86400,  # last 24h
                        dry_run=False,
                        profile=candidate_profile,
                    )
                    if recent == 0:
                        inactive_candidates.append(candidate_profile)
        except Exception:
            pass

        try:
            if hasattr(self, "db") and self.db:
                results = self.db.sanitize_stale_positions(
                    self.symbol,
                    max_age_days=30,
                    exclude_profiles=inactive_candidates if inactive_candidates else None,
                )
                if results:
                    total = sum(results.values())
                    reasons_str = ", ".join(
                        f"{k}={v}" for k, v in sorted(results.items())
                    )
                    logger.warning(
                        "🧹 [sanitize] %d stale position(s) closed: %s",
                        total, reasons_str,
                    )
        except Exception as exc:
            logger.debug("[sanitize] skip: %s", exc)
