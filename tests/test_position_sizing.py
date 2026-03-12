#!/usr/bin/env python3
"""
Testes unitários para cálculo de tamanho de posição (position sizing).
=====================================================================
Valida os 3 fixes aplicados no _calculate_trade_size:
  - Fix #1: Remoção de dupla aplicação de profile allocation
  - Fix #2: MIN_CONFIDENCE vem da config (não hardcoded 0.7)
  - Fix #3: Efeito combinado permite trades com saldo < $1000

Cenários: BUY (agressivo, conservador, default), SELL, HOLD, edge cases,
          AI control, DCA, dry run, alocação por perfil.
"""
from dataclasses import dataclass
from typing import Optional

import pytest


# ================ SIMULAÇÃO DAS CLASSES ================

BTC_PRICE = 70_000.0


@dataclass
class MockSignal:
    """Sinal de trading simulado."""
    action: str
    confidence: float


@dataclass
class MockRagAdjustment:
    """RAGAdjustment simulado."""
    similar_count: int = 0
    ai_max_entries: int = 3
    ai_position_size_pct: float = 0.048
    ai_position_size_reason: str = "test"


@dataclass
class MockAgentState:
    """AgentState simplificado para testes de sizing."""
    position: float = 0.0
    position_count: int = 0
    entry_price: float = 0.0
    dry_run: bool = True
    profile: str = "default"
    forced_balance: Optional[float] = None


# ================ FUNÇÕES SOB TESTE ================


def apply_profile_allocation(
    total_balance: float,
    profile: str,
    allocation_pct: Optional[float] = None,
) -> float:
    """Reproduz _apply_profile_allocation do trading_agent.py."""
    if profile == "default":
        return total_balance
    if allocation_pct is not None:
        return total_balance * allocation_pct
    return total_balance * 0.5


def calculate_trade_size(
    signal: MockSignal,
    price: float,
    *,
    min_confidence: float = 0.6,
    min_trade_amount: float = 10.0,
    max_position_pct: float = 0.5,
    max_positions: int = 3,
    trading_fee_pct: float = 0.001,
    state: Optional[MockAgentState] = None,
    rag: Optional[MockRagAdjustment] = None,
    allocation_pct: Optional[float] = None,
    force: bool = False,
    min_net_profit_usd: float = 0.01,
    min_net_profit_pct: float = 0.0005,
    stop_loss_pct: float = 0.02,
) -> float:
    """Reproduz _calculate_trade_size com os fixes aplicados."""
    if state is None:
        state = MockAgentState()
    if rag is None:
        rag = MockRagAdjustment()

    if signal.action == "BUY":
        usdt_balance = 1000.0 if state.dry_run else 100.0
        if state.forced_balance is not None:
            usdt_balance = state.forced_balance

        # Profile allocation: ÚNICA VEZ (fix bug #1)
        usdt_balance = apply_profile_allocation(
            usdt_balance, state.profile, allocation_pct
        )

        ai_controlled = rag.similar_count >= 3
        config_max = max_positions
        ai_max = rag.ai_max_entries if ai_controlled else config_max
        max_pos = min(ai_max, config_max)

        remaining_entries = max_pos - state.position_count
        if remaining_entries <= 0:
            return 0

        if ai_controlled:
            max_amount = usdt_balance * rag.ai_position_size_pct
        else:
            per_entry_pct = max_position_pct / max_pos
            max_amount = usdt_balance * per_entry_pct

        amount = max_amount * signal.confidence

        # FIX #2: usa min_confidence da config, não hardcoded 0.7
        if amount < min_trade_amount:
            if signal.confidence < min_confidence:
                return 0
            amount = min_trade_amount

        return min(amount, usdt_balance * 0.95)

    elif signal.action == "SELL":
        size = state.position
        if size <= 0:
            return 0
        if force:
            return state.position

        gross_sell = price * size
        sell_fee = gross_sell * trading_fee_pct
        buy_fee_approx = state.entry_price * size * trading_fee_pct
        total_fees = sell_fee + buy_fee_approx
        pnl = (price - state.entry_price) * size
        net_profit = pnl - total_fees

        min_pct_val = gross_sell * min_net_profit_pct
        min_required = max(min_net_profit_usd, min_pct_val)

        # Permite venda mesmo com baixo net profit (fix anterior)
        return state.position

    return 0


# ================ TESTES ================


class TestBuyAggressive:
    """Cenários BUY com perfil agressivo (min_conf=0.55, min_trade=$5)."""

    CFG = dict(min_confidence=0.55, min_trade_amount=5, max_position_pct=0.30, max_positions=4)

    def _state(self, balance: float = 105.17, **kw) -> MockAgentState:
        return MockAgentState(profile="aggressive", dry_run=False, forced_balance=balance, **kw)

    def _rag(self, **kw) -> MockRagAdjustment:
        defaults = dict(similar_count=5, ai_position_size_pct=0.048)
        defaults.update(kw)
        return MockRagAdjustment(**defaults)

    def test_floor_to_min_when_conf_above_threshold(self):
        """Saldo $105, alloc 50%, AI 4.8%, conf 0.65 → floor to $5."""
        r = calculate_trade_size(
            MockSignal("BUY", 0.65), BTC_PRICE,
            **self.CFG, state=self._state(), rag=self._rag(), allocation_pct=0.5,
        )
        assert r == pytest.approx(5.0, abs=0.01)

    def test_skip_when_conf_below_threshold(self):
        """Conf 0.50 < min 0.55 → skip."""
        r = calculate_trade_size(
            MockSignal("BUY", 0.50), BTC_PRICE,
            **self.CFG, state=self._state(), rag=self._rag(), allocation_pct=0.5,
        )
        assert r == 0

    def test_conf_at_exact_threshold(self):
        """Conf 0.55 = min_confidence → floor to $5."""
        r = calculate_trade_size(
            MockSignal("BUY", 0.55), BTC_PRICE,
            **self.CFG, state=self._state(), rag=self._rag(), allocation_pct=0.5,
        )
        assert r == pytest.approx(5.0, abs=0.01)

    def test_high_conf_low_balance_still_floors(self):
        """Conf alta 0.95 mas saldo baixo → floor to $5."""
        r = calculate_trade_size(
            MockSignal("BUY", 0.95), BTC_PRICE,
            **self.CFG, state=self._state(), rag=self._rag(), allocation_pct=0.5,
        )
        assert r == pytest.approx(5.0, abs=0.01)

    def test_large_balance_normal_sizing(self):
        """Saldo $1000, AI 4.8%, conf 0.80 → $19.20."""
        r = calculate_trade_size(
            MockSignal("BUY", 0.80), BTC_PRICE,
            **self.CFG, state=self._state(1000), rag=self._rag(), allocation_pct=0.5,
        )
        assert r == pytest.approx(19.20, abs=0.01)

    def test_large_ai_sizing_capped_at_95pct(self):
        """AI sizing 90%, conf 0.99, saldo $10k → capped at 95%."""
        rag = self._rag(ai_position_size_pct=0.90)
        r = calculate_trade_size(
            MockSignal("BUY", 0.99), BTC_PRICE,
            **self.CFG, state=self._state(10000), rag=rag, allocation_pct=0.5,
        )
        assert r == pytest.approx(4455.0, abs=1.0)

    def test_micro_balance_cap_95(self):
        """Saldo $5, alloc 50% → cap 95% < min_trade → limitado."""
        r = calculate_trade_size(
            MockSignal("BUY", 0.90), BTC_PRICE,
            **self.CFG, state=self._state(5.0), rag=self._rag(), allocation_pct=0.5,
        )
        assert r == pytest.approx(2.375, abs=0.01)

    def test_zero_balance(self):
        """Saldo $0 → $0."""
        r = calculate_trade_size(
            MockSignal("BUY", 0.90), BTC_PRICE,
            **self.CFG, state=self._state(0.0), rag=self._rag(), allocation_pct=0.5,
        )
        assert r == pytest.approx(0.0, abs=0.01)

    def test_max_positions_reached(self):
        """4/4 positions → 0."""
        r = calculate_trade_size(
            MockSignal("BUY", 0.90), BTC_PRICE,
            **self.CFG, state=self._state(1000, position_count=4),
            rag=self._rag(), allocation_pct=0.5,
        )
        assert r == 0

    def test_one_remaining_entry(self):
        """3/4 positions, ai_max=4 → último slot, ainda opera."""
        rag = self._rag(ai_max_entries=4)
        r = calculate_trade_size(
            MockSignal("BUY", 0.90), BTC_PRICE,
            **self.CFG, state=self._state(1000, position_count=3),
            rag=rag, allocation_pct=0.5,
        )
        assert r > 5.0


class TestBuyConservative:
    """Cenários BUY com perfil conservador (min_conf=0.85, min_trade=$5)."""

    CFG = dict(min_confidence=0.85, min_trade_amount=5, max_position_pct=0.15, max_positions=2)

    def _state(self, balance: float = 105.17, **kw) -> MockAgentState:
        return MockAgentState(profile="conservative", dry_run=False, forced_balance=balance, **kw)

    def _rag(self) -> MockRagAdjustment:
        return MockRagAdjustment(similar_count=5, ai_position_size_pct=0.048)

    def test_skip_low_conf(self):
        """Conf 0.65 < 0.85 → skip."""
        r = calculate_trade_size(
            MockSignal("BUY", 0.65), BTC_PRICE,
            **self.CFG, state=self._state(), rag=self._rag(), allocation_pct=0.5,
        )
        assert r == 0

    def test_conf_at_threshold_floors(self):
        """Conf 0.85 = min → floor to $5."""
        r = calculate_trade_size(
            MockSignal("BUY", 0.85), BTC_PRICE,
            **self.CFG, state=self._state(), rag=self._rag(), allocation_pct=0.5,
        )
        assert r == pytest.approx(5.0, abs=0.01)

    def test_high_conf_large_balance(self):
        """Conf 0.95, saldo $2000 → $45.60."""
        r = calculate_trade_size(
            MockSignal("BUY", 0.95), BTC_PRICE,
            **self.CFG, state=self._state(2000), rag=self._rag(), allocation_pct=0.5,
        )
        assert r == pytest.approx(45.60, abs=0.01)

    def test_skip_just_below_threshold(self):
        """Conf 0.84 → skip."""
        r = calculate_trade_size(
            MockSignal("BUY", 0.84), BTC_PRICE,
            **self.CFG, state=self._state(), rag=self._rag(), allocation_pct=0.5,
        )
        assert r == 0

    def test_max_positions_conservative(self):
        """2/2 → 0."""
        r = calculate_trade_size(
            MockSignal("BUY", 0.95), BTC_PRICE,
            **self.CFG, state=self._state(5000, position_count=2),
            rag=self._rag(), allocation_pct=0.5,
        )
        assert r == 0


class TestBuyDefault:
    """Cenários BUY com perfil default (sem split de alocação)."""

    CFG = dict(min_confidence=0.6, min_trade_amount=10, max_position_pct=0.5, max_positions=3)

    def test_floor_to_min_trade_amount(self):
        """Default usa 100% do saldo, floor to $10."""
        state = MockAgentState(profile="default", dry_run=False, forced_balance=105.17)
        rag = MockRagAdjustment(similar_count=5, ai_position_size_pct=0.048)
        r = calculate_trade_size(
            MockSignal("BUY", 0.70), BTC_PRICE,
            **self.CFG, state=state, rag=rag,
        )
        assert r == pytest.approx(10.0, abs=0.01)

    def test_fallback_sizing_no_ai(self):
        """Sem AI control (similar_count=1), saldo $5000."""
        state = MockAgentState(profile="default", dry_run=False, forced_balance=5000)
        rag = MockRagAdjustment(similar_count=1)
        r = calculate_trade_size(
            MockSignal("BUY", 0.80), BTC_PRICE,
            **self.CFG, state=state, rag=rag,
        )
        assert r == pytest.approx(666.67, abs=1.0)

    def test_skip_low_conf(self):
        """Conf 0.30 < 0.60 → skip."""
        state = MockAgentState(profile="default", dry_run=False, forced_balance=500)
        rag = MockRagAdjustment(similar_count=5, ai_position_size_pct=0.048)
        r = calculate_trade_size(
            MockSignal("BUY", 0.30), BTC_PRICE,
            **self.CFG, state=state, rag=rag,
        )
        assert r == 0


class TestBuyNoAIControl:
    """Cenários sem AI control (similar_count < 3)."""

    CFG = dict(min_confidence=0.55, min_trade_amount=5, max_position_pct=0.30, max_positions=4)

    def test_fallback_sizing(self):
        """similar_count=1 → fallback sizing."""
        state = MockAgentState(profile="aggressive", dry_run=False, forced_balance=1000)
        rag = MockRagAdjustment(similar_count=1)
        r = calculate_trade_size(
            MockSignal("BUY", 0.75), BTC_PRICE,
            **self.CFG, state=state, rag=rag, allocation_pct=0.5,
        )
        assert r == pytest.approx(28.125, abs=0.01)

    def test_similar_count_2_still_fallback(self):
        """similar_count=2 → still fallback."""
        state = MockAgentState(profile="aggressive", dry_run=False, forced_balance=1000)
        rag = MockRagAdjustment(similar_count=2)
        r = calculate_trade_size(
            MockSignal("BUY", 0.75), BTC_PRICE,
            **self.CFG, state=state, rag=rag, allocation_pct=0.5,
        )
        assert r == pytest.approx(28.125, abs=0.01)

    def test_similar_count_3_activates_ai(self):
        """similar_count=3 → AI sizing ativado."""
        state = MockAgentState(profile="aggressive", dry_run=False, forced_balance=1000)
        rag = MockRagAdjustment(similar_count=3, ai_position_size_pct=0.048)
        r = calculate_trade_size(
            MockSignal("BUY", 0.75), BTC_PRICE,
            **self.CFG, state=state, rag=rag, allocation_pct=0.5,
        )
        assert r == pytest.approx(18.0, abs=0.01)


class TestBuyAIMaxEntries:
    """Cenários de AI max_entries vs config max_positions."""

    CFG = dict(min_confidence=0.55, min_trade_amount=5, max_position_pct=0.30, max_positions=4)

    def test_ai_cap_below_config(self):
        """AI max=2, config=4 → usa 2."""
        state = MockAgentState(profile="aggressive", dry_run=False, forced_balance=1000, position_count=1)
        rag = MockRagAdjustment(similar_count=5, ai_max_entries=2, ai_position_size_pct=0.10)
        r = calculate_trade_size(
            MockSignal("BUY", 0.80), BTC_PRICE,
            **self.CFG, state=state, rag=rag, allocation_pct=0.5,
        )
        assert r == pytest.approx(40.0, abs=0.01)

    def test_ai_cap_reached(self):
        """AI max=2 atingido (2/2) → 0."""
        state = MockAgentState(profile="aggressive", dry_run=False, forced_balance=1000, position_count=2)
        rag = MockRagAdjustment(similar_count=5, ai_max_entries=2, ai_position_size_pct=0.10)
        r = calculate_trade_size(
            MockSignal("BUY", 0.80), BTC_PRICE,
            **self.CFG, state=state, rag=rag, allocation_pct=0.5,
        )
        assert r == 0

    def test_config_cap_limits_ai(self):
        """AI max=10, config=4, position_count=3 → remaining=1."""
        state = MockAgentState(profile="aggressive", dry_run=False, forced_balance=1000, position_count=3)
        rag = MockRagAdjustment(similar_count=5, ai_max_entries=10, ai_position_size_pct=0.10)
        r = calculate_trade_size(
            MockSignal("BUY", 0.80), BTC_PRICE,
            **self.CFG, state=state, rag=rag, allocation_pct=0.5,
        )
        assert r == pytest.approx(40.0, abs=0.01)


class TestBuyDryRun:
    """Cenários em dry_run (saldo simulado $1000)."""

    CFG = dict(min_confidence=0.55, min_trade_amount=5, max_position_pct=0.30, max_positions=4)

    def test_dry_run_with_profile(self):
        """Dry run, alloc 50%, AI 4.8%, conf 0.80 → $19.20."""
        state = MockAgentState(profile="aggressive", dry_run=True)
        rag = MockRagAdjustment(similar_count=5, ai_position_size_pct=0.048)
        r = calculate_trade_size(
            MockSignal("BUY", 0.80), BTC_PRICE,
            **self.CFG, state=state, rag=rag, allocation_pct=0.5,
        )
        assert r == pytest.approx(19.20, abs=0.01)

    def test_dry_run_default_no_split(self):
        """Dry run, profile default → no split, full $1000."""
        state = MockAgentState(profile="default", dry_run=True)
        rag = MockRagAdjustment(similar_count=5, ai_position_size_pct=0.048)
        r = calculate_trade_size(
            MockSignal("BUY", 0.80), BTC_PRICE,
            **self.CFG, state=state, rag=rag,
        )
        assert r == pytest.approx(38.40, abs=0.01)


class TestBuyAllocationVariations:
    """Cenários de alocação por perfil."""

    CFG = dict(min_confidence=0.55, min_trade_amount=5, max_position_pct=0.30, max_positions=4)

    def _run(self, alloc_pct: Optional[float]) -> float:
        state = MockAgentState(profile="aggressive", dry_run=False, forced_balance=1000)
        rag = MockRagAdjustment(similar_count=5, ai_position_size_pct=0.10)
        return calculate_trade_size(
            MockSignal("BUY", 0.80), BTC_PRICE,
            **self.CFG, state=state, rag=rag, allocation_pct=alloc_pct,
        )

    def test_alloc_70(self):
        assert self._run(0.70) == pytest.approx(56.0, abs=0.01)

    def test_alloc_20(self):
        assert self._run(0.20) == pytest.approx(16.0, abs=0.01)

    def test_alloc_100(self):
        assert self._run(1.0) == pytest.approx(80.0, abs=0.01)

    def test_alloc_none_fallback_50(self):
        """None → fallback 50%."""
        assert self._run(None) == pytest.approx(40.0, abs=0.01)


class TestSell:
    """Cenários SELL."""

    CFG = dict(min_confidence=0.55, min_trade_amount=5, max_position_pct=0.30, max_positions=4)

    def test_sell_full_position(self):
        state = MockAgentState(position=0.001, entry_price=68000.0, profile="aggressive")
        r = calculate_trade_size(
            MockSignal("SELL", 0.80), BTC_PRICE, **self.CFG, state=state,
        )
        assert r == pytest.approx(0.001, abs=1e-8)

    def test_sell_no_position(self):
        state = MockAgentState(position=0.0, profile="aggressive")
        r = calculate_trade_size(
            MockSignal("SELL", 0.80), BTC_PRICE, **self.CFG, state=state,
        )
        assert r == 0

    def test_force_sell(self):
        state = MockAgentState(position=0.005, entry_price=72000.0, profile="aggressive")
        r = calculate_trade_size(
            MockSignal("SELL", 0.50), BTC_PRICE, **self.CFG, state=state, force=True,
        )
        assert r == pytest.approx(0.005, abs=1e-8)

    def test_sell_marginal_profit(self):
        """Vende mesmo com lucro marginal (fix anterior)."""
        state = MockAgentState(position=0.00007, entry_price=69990.0, profile="aggressive")
        r = calculate_trade_size(
            MockSignal("SELL", 0.70), BTC_PRICE, **self.CFG, state=state,
        )
        assert r == pytest.approx(0.00007, abs=1e-8)

    def test_sell_in_loss(self):
        state = MockAgentState(position=0.001, entry_price=72000.0, profile="aggressive")
        r = calculate_trade_size(
            MockSignal("SELL", 0.90), 68000.0, **self.CFG, state=state,
        )
        assert r == pytest.approx(0.001, abs=1e-8)

    def test_force_sell_no_position(self):
        state = MockAgentState(position=0.0, profile="aggressive")
        r = calculate_trade_size(
            MockSignal("SELL", 0.80), BTC_PRICE, **self.CFG, state=state, force=True,
        )
        assert r == 0


class TestHold:
    """Signal HOLD sempre retorna 0."""

    def test_hold(self):
        state = MockAgentState(position=0.001, dry_run=False, forced_balance=1000)
        r = calculate_trade_size(MockSignal("HOLD", 0.95), BTC_PRICE, state=state)
        assert r == 0


class TestEdgeCases:
    """Edge cases e boundary conditions."""

    CFG = dict(min_confidence=0.55, min_trade_amount=5, max_position_pct=0.30, max_positions=4)

    def _state(self, balance: float = 1000.0, **kw) -> MockAgentState:
        return MockAgentState(profile="aggressive", dry_run=False, forced_balance=balance, **kw)

    def _rag(self, **kw) -> MockRagAdjustment:
        defaults = dict(similar_count=5, ai_position_size_pct=0.10)
        defaults.update(kw)
        return MockRagAdjustment(**defaults)

    def test_conf_zero(self):
        r = calculate_trade_size(
            MockSignal("BUY", 0.0), BTC_PRICE,
            **self.CFG, state=self._state(), rag=self._rag(), allocation_pct=0.5,
        )
        assert r == 0

    def test_conf_one(self):
        r = calculate_trade_size(
            MockSignal("BUY", 1.0), BTC_PRICE,
            **self.CFG, state=self._state(), rag=self._rag(), allocation_pct=0.5,
        )
        assert r == pytest.approx(50.0, abs=0.01)

    def test_ai_sizing_zero(self):
        """AI sizing 0% → floor to min_trade."""
        rag = self._rag(ai_position_size_pct=0.0)
        r = calculate_trade_size(
            MockSignal("BUY", 0.90), BTC_PRICE,
            **self.CFG, state=self._state(), rag=rag, allocation_pct=0.5,
        )
        assert r == pytest.approx(5.0, abs=0.01)

    def test_ai_sizing_100(self):
        """AI sizing 100% → $450."""
        rag = self._rag(ai_position_size_pct=1.0)
        r = calculate_trade_size(
            MockSignal("BUY", 0.90), BTC_PRICE,
            **self.CFG, state=self._state(), rag=rag, allocation_pct=0.5,
        )
        assert r == pytest.approx(450.0, abs=0.01)

    def test_negative_conf(self):
        r = calculate_trade_size(
            MockSignal("BUY", -0.5), BTC_PRICE,
            **self.CFG, state=self._state(), rag=self._rag(), allocation_pct=0.5,
        )
        assert r == 0

    def test_very_large_balance(self):
        r = calculate_trade_size(
            MockSignal("BUY", 0.80), BTC_PRICE,
            **self.CFG, state=self._state(1_000_000), rag=self._rag(), allocation_pct=0.5,
        )
        assert r == pytest.approx(40000.0, abs=1.0)

    def test_min_trade_amount_zero(self):
        """min_trade_amount=0 → amount passthrough."""
        r = calculate_trade_size(
            MockSignal("BUY", 0.20), BTC_PRICE,
            min_confidence=0.55, min_trade_amount=0, max_position_pct=0.30, max_positions=4,
            state=self._state(100), rag=self._rag(), allocation_pct=0.5,
        )
        assert r == pytest.approx(1.0, abs=0.01)


class TestDoubleAllocationPrevention:
    """Verifica que allocation é aplicada APENAS 1x (bug fixado)."""

    CFG = dict(min_confidence=0.55, min_trade_amount=5, max_position_pct=0.30, max_positions=4)

    def test_alloc_applied_once_50pct(self):
        """Correto: $1000 × 0.5 = $500 × 0.10 × 1.0 = $50 (não $25 do bug)."""
        state = MockAgentState(profile="aggressive", dry_run=False, forced_balance=1000)
        rag = MockRagAdjustment(similar_count=5, ai_position_size_pct=0.10)
        r = calculate_trade_size(
            MockSignal("BUY", 1.0), BTC_PRICE,
            **self.CFG, state=state, rag=rag, allocation_pct=0.5,
        )
        assert r == pytest.approx(50.0, abs=0.01)

    def test_alloc_applied_once_30pct(self):
        """Correto: $1000 × 0.30 = $300 × 0.10 × 1.0 = $30 (não $9 do bug)."""
        state = MockAgentState(profile="aggressive", dry_run=False, forced_balance=1000)
        rag = MockRagAdjustment(similar_count=5, ai_position_size_pct=0.10)
        r = calculate_trade_size(
            MockSignal("BUY", 1.0), BTC_PRICE,
            **self.CFG, state=state, rag=rag, allocation_pct=0.30,
        )
        assert r == pytest.approx(30.0, abs=0.01)


class TestConfidenceThresholdFix:
    """Verifica que MIN_CONFIDENCE vem da config (não hardcoded 0.7)."""

    def _state(self, balance: float = 105.17) -> MockAgentState:
        return MockAgentState(profile="aggressive", dry_run=False, forced_balance=balance)

    def _rag(self) -> MockRagAdjustment:
        return MockRagAdjustment(similar_count=5, ai_position_size_pct=0.048)

    def test_aggressive_065_floors(self):
        """Antes: skip (0.65 < hardcoded 0.7). Depois: floor (0.65 >= 0.55)."""
        r = calculate_trade_size(
            MockSignal("BUY", 0.65), BTC_PRICE,
            min_confidence=0.55, min_trade_amount=5, max_position_pct=0.30, max_positions=4,
            state=self._state(), rag=self._rag(), allocation_pct=0.5,
        )
        assert r == pytest.approx(5.0, abs=0.01)

    def test_aggressive_060_floors(self):
        """Antes: skip (0.60 < 0.7). Depois: floor (0.60 >= 0.55)."""
        r = calculate_trade_size(
            MockSignal("BUY", 0.60), BTC_PRICE,
            min_confidence=0.55, min_trade_amount=5, max_position_pct=0.30, max_positions=4,
            state=self._state(), rag=self._rag(), allocation_pct=0.5,
        )
        assert r == pytest.approx(5.0, abs=0.01)

    def test_conservative_070_skips(self):
        """Conservative: conf 0.70 < min 0.85 → skip."""
        state = MockAgentState(profile="conservative", dry_run=False, forced_balance=105.17)
        r = calculate_trade_size(
            MockSignal("BUY", 0.70), BTC_PRICE,
            min_confidence=0.85, min_trade_amount=5, max_position_pct=0.15, max_positions=2,
            state=state, rag=self._rag(), allocation_pct=0.5,
        )
        assert r == 0


class TestSellFeeCheck:
    """Cenários detalhados do fee check no SELL."""

    CFG = dict(min_confidence=0.55, min_trade_amount=5, max_position_pct=0.30, max_positions=4)

    def test_sell_large_profit(self):
        state = MockAgentState(position=0.01, entry_price=71000.0)
        r = calculate_trade_size(
            MockSignal("SELL", 0.85), 75000.0, **self.CFG, state=state,
        )
        assert r == pytest.approx(0.01, abs=1e-8)

    def test_force_sl_sell(self):
        state = MockAgentState(position=0.001, entry_price=72000.0)
        r = calculate_trade_size(
            MockSignal("SELL", 0.50), 69500.0, **self.CFG, state=state, force=True,
        )
        assert r == pytest.approx(0.001, abs=1e-8)

    def test_force_tp_sell(self):
        state = MockAgentState(position=0.001, entry_price=68000.0)
        r = calculate_trade_size(
            MockSignal("SELL", 0.50), 72500.0, **self.CFG, state=state, force=True,
        )
        assert r == pytest.approx(0.001, abs=1e-8)


class TestProductionScenario:
    """Cenários que replicam condições reais de produção."""

    def test_aggressive_prod_floors(self):
        """$105.17, alloc 50%, AI 4.8%, conf 0.65 → floor $5."""
        state = MockAgentState(profile="aggressive", dry_run=False, forced_balance=105.17)
        rag = MockRagAdjustment(similar_count=5, ai_position_size_pct=0.048)
        r = calculate_trade_size(
            MockSignal("BUY", 0.65), 70000.0,
            min_confidence=0.55, min_trade_amount=5, max_position_pct=0.30, max_positions=4,
            state=state, rag=rag, allocation_pct=0.5,
        )
        assert r == pytest.approx(5.0, abs=0.01)

    def test_conservative_prod_skips(self):
        """Mesmas condições, conservador (conf 0.65 < 0.85) → skip."""
        state = MockAgentState(profile="conservative", dry_run=False, forced_balance=105.17)
        rag = MockRagAdjustment(similar_count=5, ai_position_size_pct=0.048)
        r = calculate_trade_size(
            MockSignal("BUY", 0.65), 70000.0,
            min_confidence=0.85, min_trade_amount=5, max_position_pct=0.15, max_positions=2,
            state=state, rag=rag, allocation_pct=0.5,
        )
        assert r == 0

    def test_conservative_high_conf_floors(self):
        """Conservador com conf 0.92 → floor $5."""
        state = MockAgentState(profile="conservative", dry_run=False, forced_balance=105.17)
        rag = MockRagAdjustment(similar_count=5, ai_position_size_pct=0.048)
        r = calculate_trade_size(
            MockSignal("BUY", 0.92), 70000.0,
            min_confidence=0.85, min_trade_amount=5, max_position_pct=0.15, max_positions=2,
            state=state, rag=rag, allocation_pct=0.5,
        )
        assert r == pytest.approx(5.0, abs=0.01)

    def test_aggressive_second_entry(self):
        """2ª entrada com position_count=1 → floor $5."""
        state = MockAgentState(profile="aggressive", dry_run=False, forced_balance=100, position_count=1)
        rag = MockRagAdjustment(similar_count=5, ai_position_size_pct=0.048)
        r = calculate_trade_size(
            MockSignal("BUY", 0.70), 70000.0,
            min_confidence=0.55, min_trade_amount=5, max_position_pct=0.30, max_positions=4,
            state=state, rag=rag, allocation_pct=0.5,
        )
        assert r == pytest.approx(5.0, abs=0.01)
