#!/usr/bin/env python3
"""
Tax Guardrails — Otimização tributária para operações B3.

Regras fiscais brasileiras implementadas como guardrails automáticos:

AÇÕES (Swing Trade):
  - 15% IR sobre lucro líquido
  - ISENTO se total de vendas no mês ≤ R$20.000
  - IRRF (dedo-duro): 0,005% sobre valor da venda
  - Prejuízo swing só compensa lucro swing

AÇÕES (Day Trade):
  - 20% IR sobre lucro líquido — SEM isenção de R$20k
  - IRRF (dedo-duro): 1% sobre o lucro
  - Prejuízo day trade só compensa lucro day trade

MINICONTRATOS/FUTUROS (Swing):
  - 15% IR sobre lucro — SEM isenção de R$20k
  - IRRF: 0,005% sobre valor do ajuste

MINICONTRATOS/FUTUROS (Day Trade):
  - 20% IR sobre lucro
  - IRRF: 1% sobre o lucro

Guardrails implementados:
  1. Trava de R$20k: bloqueia vendas de ações swing quando total mensal atingir limiar
  2. Preferência swing: evita day trades (comprar e vender no mesmo dia)
  3. Tracking de prejuízo acumulado por categoria (swing/day trade)
  4. Alerta de DARF pendente
  5. Tax-aware position sizing
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ====================== CONSTANTES FISCAIS ======================
BRT = timezone(timedelta(hours=-3))

# Limites fiscais
EQUITY_SWING_EXEMPTION_LIMIT = 20_000.00  # R$20k vendas/mês → isenção IR
EQUITY_SWING_TAX_RATE = 0.15              # 15% sobre lucro líquido
EQUITY_DAYTRADE_TAX_RATE = 0.20           # 20% sobre lucro líquido
FUTURES_SWING_TAX_RATE = 0.15             # 15% sobre lucro líquido
FUTURES_DAYTRADE_TAX_RATE = 0.20          # 20% sobre lucro líquido

# IRRF (dedo-duro) — retido na fonte pela corretora
IRRF_SWING_RATE = 0.00005                 # 0,005% sobre valor da venda
IRRF_DAYTRADE_RATE = 0.01                 # 1% sobre o LUCRO

# Margem de segurança para não estourar o limite de R$20k
DEFAULT_EXEMPTION_SAFETY_MARGIN = 0.90    # Usar 90% do limite = R$18k


# ====================== DATA CLASSES ======================
@dataclass
class TaxEvent:
    """Evento fiscal associado a uma operação."""

    timestamp: float
    symbol: str
    asset_class: str            # "equity" ou "futures"
    trade_type: str             # "swing" ou "daytrade"
    side: str                   # "buy" ou "sell"
    volume: float               # Quantidade
    price: float                # Preço de execução
    gross_value: float          # volume * price
    pnl: float = 0.0           # PnL líquido (vendas)
    commission: float = 0.0     # Custo operacional
    irrf: float = 0.0          # IRRF retido
    tax_exempt: bool = False    # Dentro da isenção de R$20k?
    buy_date: Optional[str] = None  # Data da compra (para classificar swing/day)


@dataclass
class MonthlyTaxSummary:
    """Resumo fiscal do mês."""

    year_month: str                  # "2026-04"
    equity_swing_sales_total: float = 0.0   # Total vendas ações swing
    equity_swing_pnl: float = 0.0           # PnL ações swing
    equity_daytrade_pnl: float = 0.0        # PnL ações day trade
    futures_swing_pnl: float = 0.0          # PnL futuros swing
    futures_daytrade_pnl: float = 0.0       # PnL futuros day trade
    irrf_total: float = 0.0                 # IRRF retido no mês
    commissions_total: float = 0.0          # Total de custos operacionais
    events: List[TaxEvent] = field(default_factory=list)

    @property
    def equity_swing_exempt(self) -> bool:
        """Vendas de ações swing dentro do limite de isenção?"""
        return self.equity_swing_sales_total <= EQUITY_SWING_EXEMPTION_LIMIT

    @property
    def equity_swing_remaining(self) -> float:
        """Quanto ainda pode vender em ações swing sem pagar IR."""
        return max(0, EQUITY_SWING_EXEMPTION_LIMIT - self.equity_swing_sales_total)

    @property
    def tax_due_equity_swing(self) -> float:
        """IR devido sobre ações swing (0 se isento)."""
        if self.equity_swing_exempt or self.equity_swing_pnl <= 0:
            return 0.0
        return self.equity_swing_pnl * EQUITY_SWING_TAX_RATE

    @property
    def tax_due_equity_daytrade(self) -> float:
        """IR devido sobre ações day trade."""
        if self.equity_daytrade_pnl <= 0:
            return 0.0
        return self.equity_daytrade_pnl * EQUITY_DAYTRADE_TAX_RATE

    @property
    def tax_due_futures_swing(self) -> float:
        """IR devido sobre futuros swing."""
        if self.futures_swing_pnl <= 0:
            return 0.0
        return self.futures_swing_pnl * FUTURES_SWING_TAX_RATE

    @property
    def tax_due_futures_daytrade(self) -> float:
        """IR devido sobre futuros day trade."""
        if self.futures_daytrade_pnl <= 0:
            return 0.0
        return self.futures_daytrade_pnl * FUTURES_DAYTRADE_TAX_RATE

    @property
    def total_tax_due(self) -> float:
        """Total de IR a pagar no mês (menos IRRF já retido)."""
        gross = (
            self.tax_due_equity_swing
            + self.tax_due_equity_daytrade
            + self.tax_due_futures_swing
            + self.tax_due_futures_daytrade
        )
        return max(0, gross - self.irrf_total)

    def to_dict(self) -> Dict[str, Any]:
        """Serializa para dicionário."""
        return {
            "year_month": self.year_month,
            "equity_swing_sales_total": round(self.equity_swing_sales_total, 2),
            "equity_swing_pnl": round(self.equity_swing_pnl, 2),
            "equity_daytrade_pnl": round(self.equity_daytrade_pnl, 2),
            "futures_swing_pnl": round(self.futures_swing_pnl, 2),
            "futures_daytrade_pnl": round(self.futures_daytrade_pnl, 2),
            "irrf_total": round(self.irrf_total, 4),
            "commissions_total": round(self.commissions_total, 2),
            "equity_swing_exempt": self.equity_swing_exempt,
            "equity_swing_remaining": round(self.equity_swing_remaining, 2),
            "total_tax_due": round(self.total_tax_due, 2),
            "events_count": len(self.events),
        }


@dataclass
class AccumulatedLosses:
    """Prejuízos acumulados por categoria (podem ser compensados futuramente)."""

    equity_swing: float = 0.0
    equity_daytrade: float = 0.0
    futures_swing: float = 0.0
    futures_daytrade: float = 0.0

    def apply_loss(self, category: str, loss: float) -> None:
        """Acumula prejuízo (loss deve ser negativo)."""
        if loss >= 0:
            return
        current = getattr(self, category, 0.0)
        setattr(self, category, current + loss)

    def compensate(self, category: str, gain: float) -> float:
        """Compensa ganho com prejuízo acumulado. Retorna ganho tributável residual."""
        if gain <= 0:
            return 0.0
        accumulated = getattr(self, category, 0.0)
        if accumulated >= 0:
            return gain
        compensable = min(gain, abs(accumulated))
        setattr(self, category, accumulated + compensable)
        return gain - compensable

    def to_dict(self) -> Dict[str, float]:
        """Serializa para dicionário."""
        return {
            "equity_swing": round(self.equity_swing, 2),
            "equity_daytrade": round(self.equity_daytrade, 2),
            "futures_swing": round(self.futures_swing, 2),
            "futures_daytrade": round(self.futures_daytrade, 2),
        }


# ====================== GUARDRAIL DECISIONS ======================
@dataclass
class GuardrailDecision:
    """Resultado de uma verificação de guardrail fiscal."""

    allowed: bool
    reason: str
    guardrail: str              # Nome do guardrail que atuou
    details: Dict[str, Any] = field(default_factory=dict)


# ====================== TAX TRACKER ======================
class TaxTracker:
    """Rastreador fiscal para operações B3.

    Mantém estado mensal de vendas, PnL por categoria e aplica guardrails
    automáticos para minimizar tributação.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        persist_path: Optional[Path] = None,
    ) -> None:
        cfg = config or {}
        self._safety_margin = float(cfg.get(
            "tax_exemption_safety_pct", DEFAULT_EXEMPTION_SAFETY_MARGIN,
        ))
        self._effective_limit = EQUITY_SWING_EXEMPTION_LIMIT * self._safety_margin
        self._avoid_daytrade = bool(cfg.get("tax_avoid_daytrade", True))
        self._block_over_20k = bool(cfg.get("tax_block_over_20k", True))
        self._loss_harvest = bool(cfg.get("tax_loss_harvest", False))

        self._persist_path = persist_path or (
            Path(__file__).parent / "data" / "tax_state.json"
        )
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)

        # Estado
        self._monthly: Dict[str, MonthlyTaxSummary] = {}
        self._losses = AccumulatedLosses()
        self._buy_dates: Dict[str, str] = {}  # symbol → date da compra mais antiga

        self._load_state()

    # ====================== PERSISTÊNCIA ======================

    def _load_state(self) -> None:
        """Carrega estado fiscal persistido."""
        if not self._persist_path.exists():
            return
        try:
            with open(self._persist_path) as f:
                data = json.load(f)
            # Losses
            losses = data.get("accumulated_losses", {})
            self._losses = AccumulatedLosses(
                equity_swing=float(losses.get("equity_swing", 0)),
                equity_daytrade=float(losses.get("equity_daytrade", 0)),
                futures_swing=float(losses.get("futures_swing", 0)),
                futures_daytrade=float(losses.get("futures_daytrade", 0)),
            )
            # Monthly summaries (apenas meses recentes)
            for ym, mdata in data.get("monthly", {}).items():
                summary = MonthlyTaxSummary(year_month=ym)
                summary.equity_swing_sales_total = float(mdata.get("equity_swing_sales_total", 0))
                summary.equity_swing_pnl = float(mdata.get("equity_swing_pnl", 0))
                summary.equity_daytrade_pnl = float(mdata.get("equity_daytrade_pnl", 0))
                summary.futures_swing_pnl = float(mdata.get("futures_swing_pnl", 0))
                summary.futures_daytrade_pnl = float(mdata.get("futures_daytrade_pnl", 0))
                summary.irrf_total = float(mdata.get("irrf_total", 0))
                summary.commissions_total = float(mdata.get("commissions_total", 0))
                self._monthly[ym] = summary
            # Buy dates
            self._buy_dates = data.get("buy_dates", {})
            logger.info("📋 Tax state loaded: losses=%s", self._losses.to_dict())
        except Exception as e:
            logger.warning("⚠️ Failed to load tax state: %s", e)

    def _save_state(self) -> None:
        """Persiste estado fiscal."""
        try:
            data = {
                "accumulated_losses": self._losses.to_dict(),
                "monthly": {
                    ym: s.to_dict() for ym, s in self._monthly.items()
                },
                "buy_dates": self._buy_dates,
                "last_updated": datetime.now(BRT).isoformat(),
            }
            tmp = self._persist_path.with_suffix(".tmp")
            with open(tmp, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            tmp.replace(self._persist_path)
        except Exception as e:
            logger.warning("⚠️ Failed to save tax state: %s", e)

    # ====================== CLASSIFICAÇÃO ======================

    def _current_month(self) -> str:
        """Retorna mês atual no formato YYYY-MM."""
        return datetime.now(BRT).strftime("%Y-%m")

    def _get_month(self, year_month: Optional[str] = None) -> MonthlyTaxSummary:
        """Obtém ou cria summary do mês."""
        ym = year_month or self._current_month()
        if ym not in self._monthly:
            self._monthly[ym] = MonthlyTaxSummary(year_month=ym)
        return self._monthly[ym]

    def classify_trade_type(self, symbol: str, side: str) -> str:
        """Classifica a operação como 'swing' ou 'daytrade'.

        Day trade = compra E venda do MESMO ativo no MESMO dia.
        Se o símbolo tem posição comprada hoje e agora está vendendo, é day trade.
        """
        if side == "buy":
            return "swing"  # Compra nunca é day trade por si só

        today = datetime.now(BRT).strftime("%Y-%m-%d")
        buy_date = self._buy_dates.get(symbol)
        if buy_date == today:
            return "daytrade"
        return "swing"

    def _tax_category(self, asset_class: str, trade_type: str) -> str:
        """Retorna chave de categoria fiscal."""
        return f"{asset_class}_{trade_type}"

    # ====================== GUARDRAILS ======================

    def check_sell_allowed(
        self,
        symbol: str,
        asset_class: str,
        volume: float,
        price: float,
    ) -> GuardrailDecision:
        """Verifica se uma venda é fiscal-mente permitida/recomendada.

        Guardrails aplicados:
        1. Trava R$20k: bloqueia venda swing de ações se ultrapassa limite mensal
        2. Preferência swing: avisa se operação seria day trade
        """
        trade_type = self.classify_trade_type(symbol, "sell")
        sell_value = volume * price
        month = self._get_month()

        # Guardrail 1: Trava de R$20k (apenas ações swing)
        if (
            self._block_over_20k
            and asset_class == "equity"
            and trade_type == "swing"
        ):
            projected = month.equity_swing_sales_total + sell_value
            if projected > self._effective_limit:
                remaining = self._effective_limit - month.equity_swing_sales_total
                return GuardrailDecision(
                    allowed=False,
                    reason=(
                        f"🚫 TRAVA FISCAL R$20k: venda de R${sell_value:,.2f} ultrapassaria "
                        f"limite mensal (já vendido: R${month.equity_swing_sales_total:,.2f}, "
                        f"restante seguro: R${remaining:,.2f})"
                    ),
                    guardrail="equity_20k_exemption",
                    details={
                        "current_sales": month.equity_swing_sales_total,
                        "projected_sales": projected,
                        "effective_limit": self._effective_limit,
                        "remaining": remaining,
                        "sell_value": sell_value,
                    },
                )

        # Guardrail 2: Alerta day trade (ações)
        if (
            self._avoid_daytrade
            and asset_class == "equity"
            and trade_type == "daytrade"
        ):
            return GuardrailDecision(
                allowed=False,
                reason=(
                    f"⚠️ DAY TRADE detectado em {symbol}! "
                    f"Compra e venda no mesmo dia → IR de 20% sem isenção. "
                    f"Segure até amanhã para swing (15% com possível isenção)."
                ),
                guardrail="avoid_daytrade",
                details={
                    "symbol": symbol,
                    "trade_type": trade_type,
                    "swing_rate": EQUITY_SWING_TAX_RATE,
                    "daytrade_rate": EQUITY_DAYTRADE_TAX_RATE,
                },
            )

        # Guardrail 3: Alerta de proximidade ao limite
        if asset_class == "equity" and trade_type == "swing":
            projected = month.equity_swing_sales_total + sell_value
            warn_threshold = EQUITY_SWING_EXEMPTION_LIMIT * 0.80
            if projected > warn_threshold and projected <= self._effective_limit:
                logger.warning(
                    "⚠️ TAX: Vendas swing se aproximando do limite R$20k "
                    "(projetado: R$%.2f)", projected,
                )

        return GuardrailDecision(
            allowed=True,
            reason="✅ Operação fiscal-mente OK",
            guardrail="none",
            details={
                "trade_type": trade_type,
                "sell_value": sell_value,
            },
        )

    def check_buy_allowed(
        self,
        symbol: str,
        asset_class: str,
    ) -> GuardrailDecision:
        """Verifica se uma compra deve ser ajustada por razões fiscais.

        Atualmente apenas registra data da compra para classificação day/swing.
        """
        return GuardrailDecision(
            allowed=True,
            reason="✅ Compra fiscal-mente OK",
            guardrail="none",
        )

    def get_max_sell_value_exempt(self, asset_class: str) -> float:
        """Retorna valor máximo que pode ser vendido no mês com isenção.

        Para ações swing: R$20k - vendas já realizadas (com margem de segurança).
        Para futuros: 0 (futuros não têm isenção).
        """
        if asset_class != "equity":
            return 0.0
        month = self._get_month()
        return max(0, self._effective_limit - month.equity_swing_sales_total)

    # ====================== REGISTRO DE EVENTOS ======================

    def record_buy(
        self,
        symbol: str,
        asset_class: str,
        volume: float,
        price: float,
        commission: float = 0.0,
    ) -> None:
        """Registra uma compra para rastreamento fiscal."""
        today = datetime.now(BRT).strftime("%Y-%m-%d")
        # Registra date da compra só se não tem posição anterior
        if symbol not in self._buy_dates:
            self._buy_dates[symbol] = today

        month = self._get_month()
        month.commissions_total += commission
        self._save_state()

        logger.debug(
            "📋 TAX BUY: %s %s %.0f @ R$%.2f (buy_date=%s)",
            symbol, asset_class, volume, price, today,
        )

    def record_sell(
        self,
        symbol: str,
        asset_class: str,
        volume: float,
        price: float,
        pnl: float,
        commission: float = 0.0,
    ) -> TaxEvent:
        """Registra uma venda e calcula impacto fiscal.

        Returns:
            TaxEvent com detalhes da tributação.
        """
        trade_type = self.classify_trade_type(symbol, "sell")
        sell_value = volume * price
        month = self._get_month()

        # IRRF (dedo-duro)
        if trade_type == "daytrade" and pnl > 0:
            irrf = pnl * IRRF_DAYTRADE_RATE
        else:
            irrf = sell_value * IRRF_SWING_RATE

        # Isenção de R$20k
        tax_exempt = False
        if (
            asset_class == "equity"
            and trade_type == "swing"
            and (month.equity_swing_sales_total + sell_value) <= EQUITY_SWING_EXEMPTION_LIMIT
        ):
            tax_exempt = True

        # Evento fiscal
        event = TaxEvent(
            timestamp=time.time(),
            symbol=symbol,
            asset_class=asset_class,
            trade_type=trade_type,
            side="sell",
            volume=volume,
            price=price,
            gross_value=sell_value,
            pnl=pnl,
            commission=commission,
            irrf=irrf,
            tax_exempt=tax_exempt,
            buy_date=self._buy_dates.get(symbol),
        )

        # Atualizar summary mensal
        month.irrf_total += irrf
        month.commissions_total += commission
        month.events.append(event)

        category = self._tax_category(asset_class, trade_type)

        if asset_class == "equity" and trade_type == "swing":
            month.equity_swing_sales_total += sell_value
            month.equity_swing_pnl += pnl
        elif asset_class == "equity" and trade_type == "daytrade":
            month.equity_daytrade_pnl += pnl
        elif asset_class == "futures" and trade_type == "swing":
            month.futures_swing_pnl += pnl
        elif asset_class == "futures" and trade_type == "daytrade":
            month.futures_daytrade_pnl += pnl

        # Prejuízo acumulado
        if pnl < 0:
            self._losses.apply_loss(category, pnl)
        elif pnl > 0 and not tax_exempt:
            # Compensar com prejuízo anterior
            taxable = self._losses.compensate(category, pnl)
            if taxable < pnl:
                logger.info(
                    "💰 TAX: Compensando R$%.2f de prejuízo acumulado (%s)",
                    pnl - taxable, category,
                )

        # Limpar buy_date (posição zerada)
        if symbol in self._buy_dates:
            del self._buy_dates[symbol]

        self._save_state()

        # Log
        exempt_tag = " [ISENTO]" if tax_exempt else ""
        dt_tag = f" [DAY TRADE 20%]" if trade_type == "daytrade" else ""
        logger.info(
            "📋 TAX SELL: %s %s %.0f @ R$%.2f = R$%.2f PnL "
            "(IRRF=R$%.4f, sales_mth=R$%.2f)%s%s",
            symbol, asset_class, volume, price, pnl,
            irrf, month.equity_swing_sales_total if asset_class == "equity" else 0,
            exempt_tag, dt_tag,
        )

        return event

    # ====================== CONSULTAS ======================

    def get_monthly_summary(self, year_month: Optional[str] = None) -> MonthlyTaxSummary:
        """Retorna resumo fiscal do mês."""
        return self._get_month(year_month)

    def get_accumulated_losses(self) -> AccumulatedLosses:
        """Retorna prejuízos acumulados por categoria."""
        return self._losses

    def get_darf_due(self, year_month: Optional[str] = None) -> Dict[str, Any]:
        """Calcula DARF devida para o mês (pagar até último dia útil mês seguinte).

        Returns:
            Dict com valores de DARF por categoria e data de vencimento.
        """
        month = self._get_month(year_month)
        ym = month.year_month
        year, mon = int(ym[:4]), int(ym[5:7])

        # Próximo mês = vencimento
        if mon == 12:
            due_year, due_month = year + 1, 1
        else:
            due_year, due_month = year, mon + 1

        # Último dia útil do mês seguinte (simplificado: dia 28)
        due_date = f"{due_year}-{due_month:02d}-28"

        # Categorias
        result: Dict[str, Any] = {
            "year_month": ym,
            "due_date": due_date,
        }

        # Equity swing
        if month.equity_swing_exempt:
            result["equity_swing"] = {
                "pnl": round(month.equity_swing_pnl, 2),
                "tax": 0.0,
                "exempt": True,
                "reason": f"Vendas R${month.equity_swing_sales_total:,.2f} ≤ R$20k",
            }
        else:
            # Compensar com prejuízo acumulado
            taxable = self._losses.compensate(
                "equity_swing",
                max(0, month.equity_swing_pnl),
            )
            tax = taxable * EQUITY_SWING_TAX_RATE if taxable > 0 else 0
            result["equity_swing"] = {
                "pnl": round(month.equity_swing_pnl, 2),
                "taxable": round(taxable, 2),
                "tax": round(tax, 2),
                "exempt": False,
            }

        # Equity day trade
        taxable_dt = self._losses.compensate(
            "equity_daytrade",
            max(0, month.equity_daytrade_pnl),
        )
        result["equity_daytrade"] = {
            "pnl": round(month.equity_daytrade_pnl, 2),
            "taxable": round(taxable_dt, 2),
            "tax": round(taxable_dt * EQUITY_DAYTRADE_TAX_RATE if taxable_dt > 0 else 0, 2),
        }

        # Futures swing
        taxable_fs = self._losses.compensate(
            "futures_swing",
            max(0, month.futures_swing_pnl),
        )
        result["futures_swing"] = {
            "pnl": round(month.futures_swing_pnl, 2),
            "taxable": round(taxable_fs, 2),
            "tax": round(taxable_fs * FUTURES_SWING_TAX_RATE if taxable_fs > 0 else 0, 2),
        }

        # Futures day trade
        taxable_fd = self._losses.compensate(
            "futures_daytrade",
            max(0, month.futures_daytrade_pnl),
        )
        result["futures_daytrade"] = {
            "pnl": round(month.futures_daytrade_pnl, 2),
            "taxable": round(taxable_fd, 2),
            "tax": round(taxable_fd * FUTURES_DAYTRADE_TAX_RATE if taxable_fd > 0 else 0, 2),
        }

        # IRRF já retido
        result["irrf_retained"] = round(month.irrf_total, 4)
        result["commissions_deductible"] = round(month.commissions_total, 2)

        # Total
        total_tax = sum(
            cat.get("tax", 0)
            for key, cat in result.items()
            if isinstance(cat, dict) and "tax" in cat
        )
        result["total_gross_tax"] = round(total_tax, 2)
        result["total_net_tax"] = round(max(0, total_tax - month.irrf_total), 2)
        result["accumulated_losses"] = self._losses.to_dict()

        return result

    def get_status(self) -> Dict[str, Any]:
        """Retorna status completo do tracker fiscal."""
        month = self._get_month()
        return {
            "current_month": month.to_dict(),
            "accumulated_losses": self._losses.to_dict(),
            "guardrails": {
                "block_over_20k": self._block_over_20k,
                "avoid_daytrade": self._avoid_daytrade,
                "effective_limit": self._effective_limit,
                "equity_swing_remaining": month.equity_swing_remaining,
                "safety_margin_pct": self._safety_margin,
            },
        }
