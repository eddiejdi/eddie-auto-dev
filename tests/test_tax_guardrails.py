#!/usr/bin/env python3
"""Testes unitários para clear_trading_agent/tax_guardrails.py.

Cobre: TaxTracker, TaxEvent, MonthlyTaxSummary, AccumulatedLosses,
       GuardrailDecision e todas as regras fiscais B3.
Sem dependências externas — tudo in-memory com tmp paths.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

# ====================== SETUP ======================
_CLEAR_DIR = Path(__file__).resolve().parent.parent / "clear_trading_agent"
if str(_CLEAR_DIR) not in sys.path:
    sys.path.insert(0, str(_CLEAR_DIR))
if str(_CLEAR_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_CLEAR_DIR.parent))

from clear_trading_agent.tax_guardrails import (
    TaxTracker,
    TaxEvent,
    MonthlyTaxSummary,
    AccumulatedLosses,
    GuardrailDecision,
    EQUITY_SWING_EXEMPTION_LIMIT,
    EQUITY_SWING_TAX_RATE,
    EQUITY_DAYTRADE_TAX_RATE,
    FUTURES_SWING_TAX_RATE,
    FUTURES_DAYTRADE_TAX_RATE,
    IRRF_SWING_RATE,
    IRRF_DAYTRADE_RATE,
    DEFAULT_EXEMPTION_SAFETY_MARGIN,
    BRT,
)


# ====================== FIXTURES ======================

@pytest.fixture
def tmp_tax_path(tmp_path: Path) -> Path:
    """Caminho temporário para estado fiscal."""
    return tmp_path / "tax_state.json"


@pytest.fixture
def tracker(tmp_tax_path: Path) -> TaxTracker:
    """TaxTracker padrão com config equity."""
    return TaxTracker(
        config={
            "tax_block_over_20k": True,
            "tax_avoid_daytrade": True,
            "tax_exemption_safety_pct": 0.90,
        },
        persist_path=tmp_tax_path,
    )


@pytest.fixture
def tracker_futures(tmp_tax_path: Path) -> TaxTracker:
    """TaxTracker para futuros (sem isenção R$20k)."""
    return TaxTracker(
        config={
            "tax_block_over_20k": False,
            "tax_avoid_daytrade": False,
            "tax_exemption_safety_pct": 1.0,
        },
        persist_path=tmp_tax_path,
    )


# ====================== MONTHLY TAX SUMMARY ======================

class TestMonthlyTaxSummary:
    """Testes para MonthlyTaxSummary."""

    def test_empty_summary(self) -> None:
        """Summary vazio começa com 0 em tudo."""
        s = MonthlyTaxSummary(year_month="2026-01")
        assert s.equity_swing_sales_total == 0
        assert s.equity_swing_exempt is True
        assert s.equity_swing_remaining == EQUITY_SWING_EXEMPTION_LIMIT
        assert s.total_tax_due == 0

    def test_under_20k_exempt(self) -> None:
        """Vendas abaixo de R$20k → isento."""
        s = MonthlyTaxSummary(year_month="2026-01")
        s.equity_swing_sales_total = 15_000.0
        s.equity_swing_pnl = 1_000.0
        assert s.equity_swing_exempt is True
        assert s.tax_due_equity_swing == 0.0
        assert s.equity_swing_remaining == 5_000.0

    def test_over_20k_taxes(self) -> None:
        """Vendas acima de R$20k → 15% IR."""
        s = MonthlyTaxSummary(year_month="2026-01")
        s.equity_swing_sales_total = 25_000.0
        s.equity_swing_pnl = 2_000.0
        assert s.equity_swing_exempt is False
        assert s.tax_due_equity_swing == 2_000.0 * EQUITY_SWING_TAX_RATE
        assert s.equity_swing_remaining == 0.0

    def test_daytrade_always_taxed(self) -> None:
        """Day trade: 20% sempre, sem isenção."""
        s = MonthlyTaxSummary(year_month="2026-01")
        s.equity_daytrade_pnl = 500.0
        assert s.tax_due_equity_daytrade == 500.0 * EQUITY_DAYTRADE_TAX_RATE

    def test_negative_pnl_no_tax(self) -> None:
        """Prejuízo → sem imposto."""
        s = MonthlyTaxSummary(year_month="2026-01")
        s.equity_swing_sales_total = 30_000.0
        s.equity_swing_pnl = -500.0
        assert s.tax_due_equity_swing == 0.0

    def test_futures_swing_tax(self) -> None:
        """Futuros swing: 15% sobre lucro (sem isenção R$20k)."""
        s = MonthlyTaxSummary(year_month="2026-01")
        s.futures_swing_pnl = 3_000.0
        assert s.tax_due_futures_swing == 3_000.0 * FUTURES_SWING_TAX_RATE

    def test_futures_daytrade_tax(self) -> None:
        """Futuros day trade: 20% sobre lucro."""
        s = MonthlyTaxSummary(year_month="2026-01")
        s.futures_daytrade_pnl = 1_000.0
        assert s.tax_due_futures_daytrade == 1_000.0 * FUTURES_DAYTRADE_TAX_RATE

    def test_total_tax_deducts_irrf(self) -> None:
        """Total de IR deduz IRRF já retido."""
        s = MonthlyTaxSummary(year_month="2026-01")
        s.equity_swing_sales_total = 25_000.0
        s.equity_swing_pnl = 1_000.0
        s.irrf_total = 50.0
        expected = 1_000.0 * EQUITY_SWING_TAX_RATE - 50.0
        assert s.total_tax_due == expected

    def test_total_tax_floor_zero(self) -> None:
        """Total de IR não pode ser negativo."""
        s = MonthlyTaxSummary(year_month="2026-01")
        s.irrf_total = 999.0
        assert s.total_tax_due == 0.0

    def test_to_dict(self) -> None:
        """Serialização funciona."""
        s = MonthlyTaxSummary(year_month="2026-01")
        d = s.to_dict()
        assert d["year_month"] == "2026-01"
        assert "equity_swing_exempt" in d
        assert "events_count" in d


# ====================== ACCUMULATED LOSSES ======================

class TestAccumulatedLosses:
    """Testes para compensação de prejuízo acumulado."""

    def test_apply_loss(self) -> None:
        """Acumula prejuízo corretamente."""
        losses = AccumulatedLosses()
        losses.apply_loss("equity_swing", -500.0)
        assert losses.equity_swing == -500.0
        losses.apply_loss("equity_swing", -300.0)
        assert losses.equity_swing == -800.0

    def test_apply_positive_ignored(self) -> None:
        """Valor positivo não é prejuízo."""
        losses = AccumulatedLosses()
        losses.apply_loss("equity_swing", 100.0)
        assert losses.equity_swing == 0.0

    def test_compensate_full(self) -> None:
        """Compensação total: prejuízo absorve todo ganho."""
        losses = AccumulatedLosses()
        losses.equity_swing = -1000.0
        taxable = losses.compensate("equity_swing", 500.0)
        assert taxable == 0.0
        assert losses.equity_swing == -500.0

    def test_compensate_partial(self) -> None:
        """Compensação parcial: ganho maior que prejuízo."""
        losses = AccumulatedLosses()
        losses.equity_swing = -300.0
        taxable = losses.compensate("equity_swing", 1000.0)
        assert taxable == 700.0
        assert losses.equity_swing == 0.0

    def test_compensate_no_loss(self) -> None:
        """Sem prejuízo: ganho totalmente tributável."""
        losses = AccumulatedLosses()
        taxable = losses.compensate("equity_swing", 1000.0)
        assert taxable == 1000.0

    def test_compensate_zero_gain(self) -> None:
        """Ganho zero ou negativo: retorna 0."""
        losses = AccumulatedLosses()
        losses.equity_swing = -500.0
        assert losses.compensate("equity_swing", 0.0) == 0.0
        assert losses.compensate("equity_swing", -100.0) == 0.0

    def test_cross_category_isolation(self) -> None:
        """Prejuízo de swing NÃO compensa day trade (e vice-versa)."""
        losses = AccumulatedLosses()
        losses.equity_swing = -1000.0
        losses.equity_daytrade = 0.0
        # Day trade gain não usa prejuízo de swing
        taxable = losses.compensate("equity_daytrade", 500.0)
        assert taxable == 500.0
        assert losses.equity_swing == -1000.0  # Inalterado

    def test_to_dict(self) -> None:
        """Serialização funciona."""
        losses = AccumulatedLosses(equity_swing=-123.45)
        d = losses.to_dict()
        assert d["equity_swing"] == -123.45
        assert d["equity_daytrade"] == 0.0


# ====================== GUARDRAIL DECISION ======================

class TestGuardrailDecision:
    """Testes para GuardrailDecision."""

    def test_allowed(self) -> None:
        """Decisão permitida."""
        d = GuardrailDecision(allowed=True, reason="ok", guardrail="none")
        assert d.allowed is True
        assert d.details == {}

    def test_blocked(self) -> None:
        """Decisão bloqueada."""
        d = GuardrailDecision(
            allowed=False,
            reason="limit",
            guardrail="equity_20k_exemption",
            details={"remaining": 1000.0},
        )
        assert d.allowed is False
        assert d.details["remaining"] == 1000.0


# ====================== TAX TRACKER: CLASSIFICATION ======================

class TestTaxTrackerClassification:
    """Testes para classificação swing/day trade."""

    def test_buy_always_swing(self, tracker: TaxTracker) -> None:
        """Compra sempre é classificada como swing."""
        assert tracker.classify_trade_type("PETR4", "buy") == "swing"

    def test_sell_without_buy_is_swing(self, tracker: TaxTracker) -> None:
        """Venda sem registro de compra no mesmo dia = swing."""
        assert tracker.classify_trade_type("PETR4", "sell") == "swing"

    def test_sell_same_day_is_daytrade(self, tracker: TaxTracker) -> None:
        """Compra e venda no mesmo dia = day trade."""
        tracker.record_buy("PETR4", "equity", 100, 30.0)
        trade_type = tracker.classify_trade_type("PETR4", "sell")
        assert trade_type == "daytrade"

    def test_sell_next_day_is_swing(self, tracker: TaxTracker) -> None:
        """Compra hoje, venda amanhã = swing."""
        yesterday = (datetime.now(BRT) - timedelta(days=1)).strftime("%Y-%m-%d")
        tracker._buy_dates["PETR4"] = yesterday
        trade_type = tracker.classify_trade_type("PETR4", "sell")
        assert trade_type == "swing"


# ====================== TAX TRACKER: SELL GUARDRAILS ======================

class TestTaxTrackerSellGuardrails:
    """Testes para guardrails de venda."""

    def test_sell_under_limit_allowed(self, tracker: TaxTracker) -> None:
        """Venda dentro do limite R$20k → permitida."""
        decision = tracker.check_sell_allowed("PETR4", "equity", 100, 150.0)
        assert decision.allowed is True

    def test_sell_over_limit_blocked(self, tracker: TaxTracker) -> None:
        """Venda que ultrapassa margem de segurança (90% de R$20k) → bloqueada."""
        # Simular vendas anteriores próximas ao limite
        month = tracker._get_month()
        month.equity_swing_sales_total = 17_500.0  # Já vendeu R$17.5k
        # Tentar vender mais R$1.500 (total seria R$19k > 90% de R$20k = R$18k efetivo)
        decision = tracker.check_sell_allowed("PETR4", "equity", 100, 15.0)
        assert decision.allowed is False
        assert "TRAVA FISCAL" in decision.reason
        assert decision.guardrail == "equity_20k_exemption"

    def test_sell_at_exact_limit(self, tracker: TaxTracker) -> None:
        """Venda que atinge exatamente o limite → permitida."""
        month = tracker._get_month()
        month.equity_swing_sales_total = 17_000.0
        # Vender mais R$1k → total R$18k = exatamente no limite efetivo (90% de 20k)
        decision = tracker.check_sell_allowed("PETR4", "equity", 100, 10.0)
        assert decision.allowed is True

    def test_daytrade_blocked_equity(self, tracker: TaxTracker) -> None:
        """Day trade de ações → bloqueado quando avoid_daytrade ativo."""
        tracker.record_buy("VALE3", "equity", 200, 70.0)
        decision = tracker.check_sell_allowed("VALE3", "equity", 200, 72.0)
        assert decision.allowed is False
        assert "DAY TRADE" in decision.reason
        assert decision.guardrail == "avoid_daytrade"

    def test_daytrade_allowed_futures(self, tracker_futures: TaxTracker) -> None:
        """Day trade de futuros → permitido quando avoid_daytrade desativo."""
        tracker_futures.record_buy("WINFUT", "futures", 1, 130_000.0)
        decision = tracker_futures.check_sell_allowed("WINFUT", "futures", 1, 130_500.0)
        assert decision.allowed is True

    def test_futures_no_20k_limit(self, tracker_futures: TaxTracker) -> None:
        """Futuros não têm limite de R$20k."""
        month = tracker_futures._get_month()
        month.equity_swing_sales_total = 999_999.0
        decision = tracker_futures.check_sell_allowed("WINFUT", "futures", 1, 130_000.0)
        assert decision.allowed is True

    def test_buy_always_allowed(self, tracker: TaxTracker) -> None:
        """Compras são sempre permitidas."""
        decision = tracker.check_buy_allowed("PETR4", "equity")
        assert decision.allowed is True

    def test_max_sell_exempt_equity(self, tracker: TaxTracker) -> None:
        """Valor máximo para vender isento."""
        month = tracker._get_month()
        month.equity_swing_sales_total = 10_000.0
        effective_limit = EQUITY_SWING_EXEMPTION_LIMIT * 0.90
        remaining = tracker.get_max_sell_value_exempt("equity")
        assert remaining == effective_limit - 10_000.0

    def test_max_sell_exempt_futures(self, tracker: TaxTracker) -> None:
        """Futuros não têm isenção."""
        assert tracker.get_max_sell_value_exempt("futures") == 0.0


# ====================== TAX TRACKER: RECORD EVENTS ======================

class TestTaxTrackerRecordEvents:
    """Testes para registro de eventos fiscais."""

    def test_record_buy(self, tracker: TaxTracker) -> None:
        """Registrar compra atualiza buy_dates."""
        tracker.record_buy("PETR4", "equity", 100, 30.0, commission=0.90)
        today = datetime.now(BRT).strftime("%Y-%m-%d")
        assert tracker._buy_dates["PETR4"] == today
        month = tracker._get_month()
        assert month.commissions_total == 0.90

    def test_record_sell_swing_under_20k(self, tracker: TaxTracker) -> None:
        """Venda swing abaixo de R$20k → isenta."""
        # Compra ontem para ser swing
        yesterday = (datetime.now(BRT) - timedelta(days=1)).strftime("%Y-%m-%d")
        tracker._buy_dates["PETR4"] = yesterday

        event = tracker.record_sell("PETR4", "equity", 100, 35.0, pnl=500.0, commission=1.05)
        assert event.trade_type == "swing"
        assert event.tax_exempt is True
        assert event.gross_value == 100 * 35.0
        assert event.irrf == 100 * 35.0 * IRRF_SWING_RATE

        month = tracker._get_month()
        assert month.equity_swing_sales_total == 3_500.0
        assert month.equity_swing_pnl == 500.0

    def test_record_sell_swing_over_20k(self, tracker: TaxTracker) -> None:
        """Venda swing acima de R$20k → não isenta."""
        yesterday = (datetime.now(BRT) - timedelta(days=1)).strftime("%Y-%m-%d")
        tracker._buy_dates["PETR4"] = yesterday
        month = tracker._get_month()
        month.equity_swing_sales_total = 19_000.0  # Já vendeu R$19k

        event = tracker.record_sell("PETR4", "equity", 100, 15.0, pnl=200.0)
        assert event.tax_exempt is False  # R$19k + R$1.5k = R$20.5k > R$20k

    def test_record_sell_daytrade(self, tracker: TaxTracker) -> None:
        """Venda day trade: IRRF de 1% sobre lucro."""
        tracker.record_buy("VALE3", "equity", 200, 70.0)
        event = tracker.record_sell("VALE3", "equity", 200, 72.0, pnl=400.0)
        assert event.trade_type == "daytrade"
        assert event.irrf == 400.0 * IRRF_DAYTRADE_RATE  # 1% sobre lucro
        assert event.tax_exempt is False

        month = tracker._get_month()
        assert month.equity_daytrade_pnl == 400.0

    def test_record_sell_clears_buy_date(self, tracker: TaxTracker) -> None:
        """Após venda, buy_date é limpa (posição zerada)."""
        tracker.record_buy("PETR4", "equity", 100, 30.0)
        assert "PETR4" in tracker._buy_dates
        tracker.record_sell("PETR4", "equity", 100, 32.0, pnl=200.0)
        assert "PETR4" not in tracker._buy_dates

    def test_record_sell_loss_accumulated(self, tracker: TaxTracker) -> None:
        """Prejuízo é acumulado na categoria correta."""
        yesterday = (datetime.now(BRT) - timedelta(days=1)).strftime("%Y-%m-%d")
        tracker._buy_dates["PETR4"] = yesterday
        tracker.record_sell("PETR4", "equity", 100, 28.0, pnl=-200.0)
        assert tracker._losses.equity_swing == -200.0

    def test_record_sell_futures_pnl(self, tracker_futures: TaxTracker) -> None:
        """Futuros swing: PnL registrado corretamente."""
        yesterday = (datetime.now(BRT) - timedelta(days=1)).strftime("%Y-%m-%d")
        tracker_futures._buy_dates["WINFUT"] = yesterday
        event = tracker_futures.record_sell("WINFUT", "futures", 1, 131_000.0, pnl=1_000.0)
        assert event.trade_type == "swing"
        month = tracker_futures._get_month()
        assert month.futures_swing_pnl == 1_000.0


# ====================== TAX TRACKER: DARF ======================

class TestTaxTrackerDARF:
    """Testes para cálculo de DARF."""

    def test_darf_exempt_month(self, tracker: TaxTracker) -> None:
        """Mês isento (vendas < R$20k) → sem DARF para swing."""
        yesterday = (datetime.now(BRT) - timedelta(days=1)).strftime("%Y-%m-%d")
        tracker._buy_dates["PETR4"] = yesterday
        tracker.record_sell("PETR4", "equity", 100, 35.0, pnl=500.0)

        darf = tracker.get_darf_due()
        assert darf["equity_swing"]["exempt"] is True
        assert darf["equity_swing"]["tax"] == 0.0

    def test_darf_taxable_month(self, tracker: TaxTracker) -> None:
        """Mês acima de R$20k → DARF devida."""
        yesterday = (datetime.now(BRT) - timedelta(days=1)).strftime("%Y-%m-%d")
        tracker._buy_dates["PETR4"] = yesterday
        month = tracker._get_month()
        month.equity_swing_sales_total = 25_000.0
        month.equity_swing_pnl = 2_000.0

        darf = tracker.get_darf_due()
        assert darf["equity_swing"]["exempt"] is False
        assert darf["total_gross_tax"] > 0

    def test_darf_has_due_date(self, tracker: TaxTracker) -> None:
        """DARF tem data de vencimento."""
        darf = tracker.get_darf_due()
        assert "due_date" in darf
        assert darf["due_date"].startswith("20")

    def test_darf_net_deducts_irrf(self, tracker: TaxTracker) -> None:
        """DARF líquida desconta IRRF retido."""
        month = tracker._get_month()
        month.equity_swing_sales_total = 25_000.0
        month.equity_swing_pnl = 2_000.0
        month.irrf_total = 50.0

        darf = tracker.get_darf_due()
        assert darf["irrf_retained"] == 50.0
        assert darf["total_net_tax"] < darf["total_gross_tax"]

    def test_darf_december_to_january(self, tracker: TaxTracker) -> None:
        """DARF de dezembro vence em janeiro do ano seguinte."""
        darf = tracker.get_darf_due("2026-12")
        assert darf["due_date"].startswith("2027-01")


# ====================== TAX TRACKER: PERSISTENCE ======================

class TestTaxTrackerPersistence:
    """Testes para persistência de estado fiscal."""

    def test_save_and_load(self, tmp_tax_path: Path) -> None:
        """Salva e recarrega estado corretamente."""
        t1 = TaxTracker(config={}, persist_path=tmp_tax_path)
        t1._losses.equity_swing = -500.0
        t1._buy_dates["PETR4"] = "2026-01-15"
        month = t1._get_month()
        month.equity_swing_sales_total = 12_000.0
        t1._save_state()

        assert tmp_tax_path.exists()

        t2 = TaxTracker(config={}, persist_path=tmp_tax_path)
        assert t2._losses.equity_swing == -500.0
        assert t2._buy_dates["PETR4"] == "2026-01-15"

    def test_load_missing_file(self, tmp_path: Path) -> None:
        """Arquivo inexistente → estado vazio."""
        t = TaxTracker(config={}, persist_path=tmp_path / "nonexistent.json")
        assert t._losses.equity_swing == 0.0

    def test_load_corrupt_file(self, tmp_tax_path: Path) -> None:
        """Arquivo corrompido → estado vazio."""
        tmp_tax_path.write_text("<<<invalid json>>>")
        t = TaxTracker(config={}, persist_path=tmp_tax_path)
        assert t._losses.equity_swing == 0.0


# ====================== TAX TRACKER: STATUS ======================

class TestTaxTrackerStatus:
    """Testes para status do tracker."""

    def test_get_status(self, tracker: TaxTracker) -> None:
        """Status retorna dados completos."""
        status = tracker.get_status()
        assert "current_month" in status
        assert "accumulated_losses" in status
        assert "guardrails" in status
        assert status["guardrails"]["block_over_20k"] is True
        assert status["guardrails"]["avoid_daytrade"] is True
        assert status["guardrails"]["safety_margin_pct"] == 0.90


# ====================== TAX TRACKER: CONFIG VARIANTS ======================

class TestTaxTrackerConfig:
    """Testes para diferentes configurações."""

    def test_default_config(self, tmp_tax_path: Path) -> None:
        """Config padrão → guardrails ativos."""
        t = TaxTracker(config=None, persist_path=tmp_tax_path)
        assert t._avoid_daytrade is True
        assert t._block_over_20k is True

    def test_disabled_guardrails(self, tmp_tax_path: Path) -> None:
        """Guardrails desativados."""
        t = TaxTracker(
            config={
                "tax_block_over_20k": False,
                "tax_avoid_daytrade": False,
            },
            persist_path=tmp_tax_path,
        )
        # Venda de day trade permitida
        t.record_buy("PETR4", "equity", 100, 30.0)
        decision = t.check_sell_allowed("PETR4", "equity", 100, 32.0)
        assert decision.allowed is True

    def test_custom_safety_margin(self, tmp_tax_path: Path) -> None:
        """Margem de segurança customizada (95%)."""
        t = TaxTracker(
            config={"tax_exemption_safety_pct": 0.95},
            persist_path=tmp_tax_path,
        )
        assert t._effective_limit == EQUITY_SWING_EXEMPTION_LIMIT * 0.95

    def test_safety_margin_100_pct(self, tmp_tax_path: Path) -> None:
        """Margem 100% = usa o limite integral R$20k."""
        t = TaxTracker(
            config={"tax_exemption_safety_pct": 1.0},
            persist_path=tmp_tax_path,
        )
        assert t._effective_limit == EQUITY_SWING_EXEMPTION_LIMIT


# ====================== TAX TRACKER: EDGE CASES ======================

class TestTaxTrackerEdgeCases:
    """Testes de borda."""

    def test_multiple_buys_same_day(self, tracker: TaxTracker) -> None:
        """Duas compras no mesmo dia: primeiro registro mantido."""
        tracker.record_buy("PETR4", "equity", 100, 30.0)
        first_date = tracker._buy_dates["PETR4"]
        tracker.record_buy("PETR4", "equity", 100, 31.0)
        assert tracker._buy_dates["PETR4"] == first_date

    def test_sell_zero_pnl(self, tracker: TaxTracker) -> None:
        """Venda com PnL zero."""
        yesterday = (datetime.now(BRT) - timedelta(days=1)).strftime("%Y-%m-%d")
        tracker._buy_dates["PETR4"] = yesterday
        event = tracker.record_sell("PETR4", "equity", 100, 30.0, pnl=0.0)
        assert event.pnl == 0.0
        assert tracker._losses.equity_swing == 0.0

    def test_many_small_sells_accumulate(self, tracker: TaxTracker) -> None:
        """Muitas vendas pequenas acumulam no total mensal."""
        for i in range(10):
            yesterday = (datetime.now(BRT) - timedelta(days=1)).strftime("%Y-%m-%d")
            tracker._buy_dates[f"SYM{i}"] = yesterday
            tracker.record_sell(f"SYM{i}", "equity", 100, 15.0, pnl=50.0)

        month = tracker._get_month()
        assert month.equity_swing_sales_total == 10 * 100 * 15.0  # R$15k

    def test_irrf_daytrade_only_on_profit(self, tracker: TaxTracker) -> None:
        """IRRF de day trade é 1% sobre LUCRO (não sobre volume)."""
        tracker.record_buy("PETR4", "equity", 100, 30.0)
        # Day trade com lucro
        event = tracker.record_sell("PETR4", "equity", 100, 31.0, pnl=100.0)
        assert event.irrf == 100.0 * IRRF_DAYTRADE_RATE  # R$1.00

    def test_irrf_daytrade_loss_uses_swing_rate(self, tracker: TaxTracker) -> None:
        """IRRF de day trade com prejuízo: usa taxa swing (sobre valor da venda)."""
        tracker.record_buy("PETR4", "equity", 100, 32.0)
        event = tracker.record_sell("PETR4", "equity", 100, 30.0, pnl=-200.0)
        assert event.irrf == 100 * 30.0 * IRRF_SWING_RATE

    def test_concurrent_months(self, tracker: TaxTracker) -> None:
        """Meses diferentes são rastreados separadamente."""
        m1 = tracker._get_month("2026-01")
        m2 = tracker._get_month("2026-02")
        m1.equity_swing_sales_total = 15_000.0
        m2.equity_swing_sales_total = 5_000.0
        assert m1.equity_swing_sales_total != m2.equity_swing_sales_total
