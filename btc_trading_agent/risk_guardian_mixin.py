"""RiskGuardianMixin — proteção de risco nas decisões de SELL.

Responsabilidades:
- Resolver configuração ativa de guardrail (positive_only, min_pnl_pct)
- Estimar resultado líquido de um SELL antes de executar
- Decidir se um SELL com baixo lucro é permitido (stop-loss, regime bearish)

Nota: o veredito final do guardrail permanece em trading_agent.py (hook de proteção ativo).
"""

import logging
from typing import Any, Dict

logger = logging.getLogger("btc_trading_agent")

_TRADING_FEE_PCT = 0.001  # 0.1% — espelho da constante em trading_agent.py


class RiskGuardianMixin:
    """Mixin com suporte à proteção de risco de SELL (configuração, estimativa e permissão)."""

    def _get_guardrail_sell_protection_cfg(self) -> Dict[str, Any]:
        """Resolve a proteção de SELL quando os guardrails estão ativos."""
        live_cfg = self._load_live_config()
        explicit_active = live_cfg.get("guardrails_active")
        if explicit_active is None:
            day_limits = self._get_runtime_trade_day_limits()
            active = day_limits["max_daily_loss"] < 1000.0
        else:
            active = bool(explicit_active)

        positive_only = bool(live_cfg.get("guardrails_positive_only_sells", active))
        config_pnl_pct = max(
            0.0,
            float(live_cfg.get("guardrails_min_sell_pnl_pct", 0.025) or 0.025),
        )

        try:
            rag_adj = self.market_rag.get_current_adjustment()
            if str(getattr(rag_adj, "ollama_mode", "shadow")) == "apply":
                applied = float(
                    getattr(rag_adj, "applied_min_sell_pnl_pct", config_pnl_pct)
                    or config_pnl_pct
                )
                min_pnl_pct = max(0.002, applied)
            else:
                min_pnl_pct = config_pnl_pct
        except Exception:
            min_pnl_pct = config_pnl_pct

        return {
            "active": active,
            "positive_only_sells": positive_only,
            "min_sell_pnl_pct": min_pnl_pct,
        }

    def _estimate_sell_outcome(self, price: float) -> Dict[str, float]:
        """Estima o resultado líquido de um SELL da posição atual."""
        fee_pct = getattr(self, "_trading_fee_pct", _TRADING_FEE_PCT)
        size = max(float(getattr(self.state, "position", 0.0) or 0.0), 0.0)
        entry_price = max(float(getattr(self.state, "entry_price", 0.0) or 0.0), 0.0)
        gross_sell = price * size
        sell_fee = gross_sell * fee_pct
        buy_fee = entry_price * size * fee_pct
        gross_pnl = (price - entry_price) * size
        total_fees = sell_fee + buy_fee
        net_profit = gross_pnl - total_fees
        return {
            "size": size,
            "gross_sell": gross_sell,
            "gross_pnl": gross_pnl,
            "total_fees": total_fees,
            "net_profit": net_profit,
        }

    def _guardrail_allows_slot_sell(
        self,
        entry_price: float,
        size: float,
        current_price: float,
        *,
        bypass_guardrail: bool = False,
    ) -> bool:
        """True quando o guardrail permite a venda de um slot individual.

        Ponto de verificação centralizado para todas as saídas per-slot.
        bypass_guardrail=True: stop-loss e emergency exit passam direto —
        são saídas de proteção de risco que executam independente de PnL.
        """
        if bypass_guardrail:
            return True

        guard_cfg = self._get_guardrail_sell_protection_cfg()
        if not guard_cfg["active"] or not guard_cfg["positive_only_sells"]:
            return True

        fee_pct = getattr(self, "_trading_fee_pct", _TRADING_FEE_PCT)
        gross_sell = current_price * size
        if gross_sell <= 0:
            return True

        gross_pnl = (current_price - entry_price) * size
        sell_fee = gross_sell * fee_pct
        buy_fee = entry_price * size * fee_pct
        net_profit = gross_pnl - sell_fee - buy_fee
        net_pnl_pct = net_profit / gross_sell

        min_pnl = guard_cfg["min_sell_pnl_pct"]
        if net_pnl_pct < min_pnl:
            logger.info(
                "🛡️ Guardrail bloqueou saída per-slot: entry=$%.2f price=$%.2f "
                "net_pnl=%.3f%% < min=%.3f%%",
                entry_price,
                current_price,
                net_pnl_pct * 100,
                min_pnl * 100,
            )
            return False
        return True

    def _should_allow_low_net_profit_sell(
        self,
        price: float,
        signal,
        rag_adj,
        force: bool = False,
    ) -> bool:
        """Permite SELL fraco só em contexto de proteção real."""
        if force:
            return True

        live_cfg = self._load_live_config()
        base_cfg = getattr(self, "_module_config", {})
        stop_loss_pct = float(
            live_cfg.get("stop_loss_pct", base_cfg.get("stop_loss_pct", 0.02))
        )
        stop_loss_price = self.state.entry_price * (1 - stop_loss_pct)
        if price <= stop_loss_price:
            return True

        if rag_adj is None:
            return False

        context = self._analyze_signal_context(rag_adj, signal)
        regime = getattr(rag_adj, "suggested_regime", "RANGING")
        return regime == "BEARISH" or context["strong_bearish"]
