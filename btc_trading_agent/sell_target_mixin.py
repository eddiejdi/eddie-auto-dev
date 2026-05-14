"""SellTargetMixin — gerencia o target de venda por IA.

Responsabilidades:
- Sincronizar target_sell_price com a previsão direta da trade window (alvo primário)
- Usar entry × ai_tp apenas como teto (MAX cap), não como alvo fixo
- Aplicar cap por regime (ranging_max_tp_pct) lido do config, nunca hardcoded
- Serializar e persistir o target no DB para auditoria
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("btc_trading_agent")


class SellTargetMixin:
    """Mixin que encapsula toda a lógica de target_sell_price."""

    def _sync_target_sell_with_ai(self, reason_prefix: str = "IA") -> None:
        """Sincroniza o target de venda com a previsão direta da IA.

        Hierarquia de fontes (do mais ao menos preciso):
        1. target_sell da trade window ativa — previsão de preço direta da IA
        2. entry_price × ai_take_profit_pct do RAG — fallback quando janela expirou

        O valor calculado pelo RAG funciona como teto (MAX cap), não como alvo fixo.
        Em regime RANGING o teto é reduzido via ranging_max_tp_pct (config, sem hardcode).
        O target pode ser ajustado para cima ou para baixo conforme novas previsões da IA.
        """
        if self.state.position <= 0 or self.state.entry_price <= 0:
            return

        try:
            rag_adj = self.market_rag.get_current_adjustment()
            live_cfg = self._load_live_config()
            base_cfg = getattr(self, "_module_config", {})

            ai_tp = rag_adj.ai_take_profit_pct
            _atp_cfg = live_cfg.get(
                "auto_take_profit",
                base_cfg.get("auto_take_profit", {}),
            )
            _min_tp = float(
                _atp_cfg.get(
                    "min_pct",
                    live_cfg.get("min_tp_pct", base_cfg.get("min_tp_pct", 0.001)),
                )
            )
            if ai_tp < _min_tp:
                ai_tp = _min_tp

            # Cap por regime — valor vem sempre do config, nunca hardcoded no código
            _regime = getattr(rag_adj, "suggested_regime", "RANGING")
            if _regime == "RANGING":
                _ranging_cap = float(
                    live_cfg.get(
                        "ranging_max_tp_pct",
                        base_cfg.get("ranging_max_tp_pct", ai_tp),
                    )
                )
                if _ranging_cap > 0 and ai_tp > _ranging_cap:
                    ai_tp = _ranging_cap

            # Teto (MAX cap): entry × ai_tp — limite superior, não alvo primário
            max_cap_target = self.state.entry_price * (1 + ai_tp)

            # Alvo primário: previsão direta de preço da trade window ativa
            trade_window = self._get_fresh_ai_trade_window()
            window_target = float((trade_window or {}).get("target_sell", 0.0) or 0.0)

            if window_target > self.state.entry_price:
                # IA tem previsão concreta → é o alvo (respeitando teto)
                new_target = min(window_target, max_cap_target)
                target_source = (
                    f"AI_WINDOW=${window_target:,.2f} cap=${max_cap_target:,.2f}"
                )
            else:
                # Janela expirada/ausente → teto vira o alvo (comportamento legado)
                new_target = max_cap_target
                target_source = rag_adj.ai_take_profit_reason

            old_target = self.state.target_sell_price

            if old_target <= 0:
                self.state.target_sell_price = new_target
                self.state.target_sell_reason = target_source
                self._stamp_latest_open_buy_target()
                logger.info(
                    "🎯 Target SELL inicializado pela %s: $%.2f "
                    "(regime=%s, ai_tp=%.2f%%, source=%s)",
                    reason_prefix, new_target, _regime, ai_tp * 100, target_source,
                )
                return

            if abs(new_target - old_target) > 0.01:
                direction = "↓" if new_target < old_target else "↑"
                self.state.target_sell_price = new_target
                self.state.target_sell_reason = target_source
                self._stamp_latest_open_buy_target()
                logger.info(
                    "🔄 Target SELL %s pela %s: $%.2f → $%.2f "
                    "(regime=%s, source=%s)",
                    direction, reason_prefix,
                    old_target, new_target, _regime, target_source,
                )
        except Exception as e:
            logger.debug("Target SELL sync error: %s", e)

    def _serialize_target_sell_metadata(self) -> Dict[str, Any]:
        """Serializa o target SELL atual para persistência em metadata."""
        if self.state.target_sell_price <= 0:
            return {}

        metadata: Dict[str, Any] = {
            "target_sell_price": round(float(self.state.target_sell_price), 2),
            "target_sell_trigger_price": round(float(self.state.target_sell_price), 2),
        }
        if self.state.target_sell_reason:
            metadata["target_sell_reason"] = self.state.target_sell_reason
        return metadata

    def _build_trade_metadata(
        self,
        base_metadata: Optional[Dict[str, Any]] = None,
        *,
        signal=None,
        include_exit_reason: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Monta metadata persistida por trade com target e motivo de saída."""
        metadata: Dict[str, Any] = dict(base_metadata or {})
        metadata.update(self._serialize_target_sell_metadata())

        if include_exit_reason:
            exit_reason = (getattr(signal, "reason", "") or "").strip()
            if exit_reason:
                metadata["exit_reason"] = exit_reason[:240]

        return metadata or None

    def _stamp_latest_open_buy_target(self) -> None:
        """Atualiza o BUY aberto mais recente com o target SELL vigente."""
        target_metadata = self._serialize_target_sell_metadata()
        if not target_metadata:
            return

        try:
            trades = self.db.get_recent_trades(
                symbol=self.symbol,
                limit=50,
                include_dry=self.state.dry_run,
                profile=self._current_profile(),
            )
            for trade in trades:
                if trade.get("side") == "sell":
                    break
                if trade.get("side") == "buy" and trade.get("id"):
                    self.db.merge_trade_metadata(int(trade["id"]), target_metadata)
                    return
        except Exception as e:
            logger.debug("Target SELL stamp error: %s", e)
