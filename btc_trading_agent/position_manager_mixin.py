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

from kucoin_api import place_market_order
from slot_exit_policy import (
    PerSlotExitPlanner,
    SignalSellContext,
    SignalSellPolicyResolver,
    SlotExitContext,
    SlotExitDecision,
)

logger = logging.getLogger("btc_trading_agent")

_TRADING_FEE_PCT = 0.001  # 0.1% — espelho da constante em trading_agent.py


class PositionManagerMixin:
    """Mixin que encapsula tracking de posição e saídas automáticas por slot."""

    _per_slot_exit_planner = PerSlotExitPlanner()
    _signal_sell_policy_resolver = SignalSellPolicyResolver()

    def _sync_position_tracking(self) -> None:
        """Mantém contagem bruta e slot lógico coerentes com a posição atual."""
        entries = list(getattr(self.state, "entries", []) or [])
        raw_entry_count = len(entries)
        position = max(float(getattr(self.state, "position", 0.0) or 0.0), 0.0)
        entry_price = max(float(getattr(self.state, "entry_price", 0.0) or 0.0), 0.0)
        has_open_position = position > 0 and (raw_entry_count > 0 or entry_price > 0)
        self.state.position_count = raw_entry_count
        self.state.raw_entry_count = raw_entry_count
        if not has_open_position:
            self.state.logical_position_slots = 0
        elif raw_entry_count > 0:
            self.state.logical_position_slots = raw_entry_count
        else:
            self.state.logical_position_slots = 1

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
        """Executa uma lista de saídas independentes por slot."""
        sold = 0
        for decision in sorted(decisions, key=lambda item: item.entry_idx, reverse=True):
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
        entries = list(getattr(self.state, "entries", []) or [])
        if not entries:
            return 0

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
        sold = self._execute_slot_exit_decisions(price, policy.select(entries, ctx))
        if sold > 0:
            logger.info(
                "📎 SELL multi-slot independente: %d slot(s) realizados em $%.2f (%s)",
                sold,
                price,
                reason,
            )
        return sold

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
                    result = place_market_order(self.symbol, "sell", size=size)
                    if not result.get("success"):
                        logger.error("❌ Slot sell failed: %s", result)
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
            proc = subprocess.run(
                ["python3", self._SELL_NOTIFY_SCRIPT],
                env=os.environ.copy(),
                timeout=45,
                capture_output=True,
            )
            if proc.returncode == 0:
                logger.info("💰 Balance sync pós-venda: OK")
            else:
                logger.warning("Balance sync pós-venda falhou: %s", proc.stderr.decode()[:200])
        except Exception as exc:
            logger.warning("Balance sync pós-venda erro: %s", exc)

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
            from kucoin_api import _resolve_telegram_bot_token, _resolve_telegram_chat_id
            bot_token = _resolve_telegram_bot_token()
            chat_id = _resolve_telegram_chat_id()
            if bot_token and chat_id:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
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
        except Exception as exc:
            logger.warning("Telegram sell notify erro: %s", exc)
