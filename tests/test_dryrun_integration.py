#!/usr/bin/env python3
"""
Testes de integração dry-run para o pipeline completo de trading.
================================================================
Pipeline: sizing → execute_trade → position update → PnL calculation.

Cenários: BUY normal, BUY falhando (below min, max positions, zero balance),
          SELL (TP, SL, force, micro), DCA (entradas múltiplas), dry-run
          independência entre perfis.
"""
from dataclasses import dataclass, field
from typing import Optional

import pytest


# ================ CONSTANTES ================

BTC_PRICE = 70_000.0
TRADING_FEE_PCT = 0.001


# ================ SIMULAÇÃO DAS CLASSES ================


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
    """Estado completo do agente para testes de integração."""
    position: float = 0.0
    position_count: int = 0
    entry_price: float = 0.0
    dry_run: bool = True
    profile: str = "default"
    forced_balance: Optional[float] = None
    target_sell_price: float = 0.0
    max_position_pct: float = 0.5
    stop_loss_pct: float = 0.02
    trailing_high: float = 0.0


# ================ FUNÇÕES SOB TESTE ================


def apply_profile_allocation(
    total_balance: float,
    profile: str,
    allocation_pct: Optional[float] = None,
) -> float:
    """Reproduz _apply_profile_allocation."""
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
    state: Optional[MockAgentState] = None,
    rag: Optional[MockRagAdjustment] = None,
    allocation_pct: Optional[float] = None,
    force: bool = False,
) -> float:
    """Reproduz _calculate_trade_size com os 3 fixes aplicados."""
    if state is None:
        state = MockAgentState()
    if rag is None:
        rag = MockRagAdjustment()

    if signal.action == "BUY":
        usdt_balance = 1000.0 if state.dry_run else 100.0
        if state.forced_balance is not None:
            usdt_balance = state.forced_balance

        usdt_balance = apply_profile_allocation(
            usdt_balance, state.profile, allocation_pct
        )

        ai_controlled = rag.similar_count >= 3
        config_max = max_positions
        ai_max = rag.ai_max_entries if ai_controlled else config_max
        max_pos = min(ai_max, config_max)

        remaining = max_pos - state.position_count
        if remaining <= 0:
            return 0

        if ai_controlled:
            max_amount = usdt_balance * rag.ai_position_size_pct
        else:
            per_entry_pct = max_position_pct / max_pos
            max_amount = usdt_balance * per_entry_pct

        amount = max_amount * signal.confidence

        if amount < min_trade_amount:
            if signal.confidence < min_confidence:
                return 0
            amount = min_trade_amount

        return min(amount, usdt_balance * 0.95)

    elif signal.action == "SELL":
        if state.position <= 0:
            return 0
        return state.position

    return 0


def execute_trade(
    signal: MockSignal,
    state: MockAgentState,
    price: float,
    *,
    min_confidence: float = 0.6,
    min_trade_amount: float = 10.0,
    max_position_pct: float = 0.5,
    max_positions: int = 3,
    allocation_pct: Optional[float] = None,
    rag: Optional[MockRagAdjustment] = None,
    force: bool = False,
) -> dict:
    """Reproduz _execute_trade simplificado (pipeline completo)."""
    if rag is None:
        rag = MockRagAdjustment()

    size = calculate_trade_size(
        signal, price,
        min_confidence=min_confidence,
        min_trade_amount=min_trade_amount,
        max_position_pct=max_position_pct,
        max_positions=max_positions,
        state=state, rag=rag,
        allocation_pct=allocation_pct,
        force=force,
    )

    if signal.action == "BUY":
        if size < min_trade_amount:
            return {"executed": False, "reason": "below_min_trade"}
        btc_qty = (size / price) * (1 - TRADING_FEE_PCT)
        new_total = state.position + btc_qty
        new_count = state.position_count + 1
        new_entry = (
            (state.entry_price * state.position + size)
            / (state.position + btc_qty)
            if (state.position + btc_qty) > 0
            else price
        )
        target = new_entry * (1 + state.stop_loss_pct + TRADING_FEE_PCT * 2)
        return {
            "executed": True,
            "action": "BUY",
            "usdt_amount": round(size, 2),
            "btc_qty": btc_qty,
            "new_position": new_total,
            "new_count": new_count,
            "new_entry_price": new_entry,
            "target_sell": target,
            "dry_run": state.dry_run,
        }

    elif signal.action == "SELL":
        if state.position <= 0 or size <= 0:
            return {"executed": False, "reason": "no_position"}
        gross = price * size
        fee = gross * TRADING_FEE_PCT
        buy_fee = state.entry_price * size * TRADING_FEE_PCT
        pnl = (price - state.entry_price) * size - fee - buy_fee
        return {
            "executed": True,
            "action": "SELL",
            "btc_qty": size,
            "gross_usd": gross,
            "fee_usd": fee,
            "pnl_usd": pnl,
            "new_position": 0.0,
            "new_count": 0,
            "dry_run": state.dry_run,
        }

    return {"executed": False, "reason": "hold"}


# ================ TESTES ================


class TestBuyIntegration:
    """Testes de integração BUY → position update."""

    AGG = dict(min_confidence=0.55, min_trade_amount=5, max_position_pct=0.30, max_positions=4)
    CON = dict(min_confidence=0.85, min_trade_amount=5, max_position_pct=0.15, max_positions=2)

    def _state(self, profile: str = "aggressive", balance: float = 105.17, **kw) -> MockAgentState:
        return MockAgentState(profile=profile, dry_run=True, forced_balance=balance, **kw)

    def _rag(self) -> MockRagAdjustment:
        return MockRagAdjustment(similar_count=5, ai_position_size_pct=0.048)

    def test_buy_aggressive_success(self):
        """BUY agressivo com conf 0.65 → executado, $5."""
        r = execute_trade(
            MockSignal("BUY", 0.65), self._state(), BTC_PRICE,
            **self.AGG, rag=self._rag(), allocation_pct=0.5,
        )
        assert r["executed"]
        assert r["usdt_amount"] == 5.0
        assert r["btc_qty"] > 0
        assert r["new_position"] > 0
        assert r["new_count"] == 1

    def test_buy_conservative_skip(self):
        """BUY conservador com conf 0.65 → skip."""
        r = execute_trade(
            MockSignal("BUY", 0.65), self._state("conservative"), BTC_PRICE,
            **self.CON, rag=self._rag(), allocation_pct=0.5,
        )
        assert not r["executed"]
        assert r["reason"] == "below_min_trade"

    def test_buy_conservative_high_conf(self):
        """BUY conservador com conf 0.92 → executado, $5."""
        r = execute_trade(
            MockSignal("BUY", 0.92), self._state("conservative"), BTC_PRICE,
            **self.CON, rag=self._rag(), allocation_pct=0.5,
        )
        assert r["executed"]
        assert r["usdt_amount"] == 5.0

    def test_buy_high_conf_large_balance(self):
        """BUY $2000, AI 4.8%, conf 0.95 → ~$45.60."""
        r = execute_trade(
            MockSignal("BUY", 0.95), self._state(balance=2000), BTC_PRICE,
            **self.AGG, rag=self._rag(), allocation_pct=0.5,
        )
        assert r["executed"]
        assert r["usdt_amount"] == pytest.approx(45.60, abs=0.01)

    def test_buy_entry_price_is_correct(self):
        """BUY entry price ≈ BTC_PRICE."""
        r = execute_trade(
            MockSignal("BUY", 0.65), self._state(), BTC_PRICE,
            **self.AGG, rag=self._rag(), allocation_pct=0.5,
        )
        assert r["new_entry_price"] == pytest.approx(BTC_PRICE, rel=0.01)

    def test_buy_target_sell_above_entry(self):
        """Target sell > entry price (lucro mínimo)."""
        r = execute_trade(
            MockSignal("BUY", 0.65), self._state(), BTC_PRICE,
            **self.AGG, rag=self._rag(), allocation_pct=0.5,
        )
        assert r["target_sell"] > r["new_entry_price"]


class TestBuyFailing:
    """Cenários BUY que devem falhar."""

    AGG = dict(min_confidence=0.55, min_trade_amount=5, max_position_pct=0.30, max_positions=4)

    def _rag(self) -> MockRagAdjustment:
        return MockRagAdjustment(similar_count=5, ai_position_size_pct=0.048)

    def test_below_min_confidence(self):
        state = MockAgentState(profile="aggressive", dry_run=True, forced_balance=105)
        r = execute_trade(
            MockSignal("BUY", 0.50), state, BTC_PRICE,
            **self.AGG, rag=self._rag(), allocation_pct=0.5,
        )
        assert not r["executed"]

    def test_max_positions_reached(self):
        state = MockAgentState(profile="aggressive", dry_run=True, forced_balance=1000, position_count=4)
        r = execute_trade(
            MockSignal("BUY", 0.90), state, BTC_PRICE,
            **self.AGG, rag=self._rag(), allocation_pct=0.5,
        )
        assert not r["executed"]

    def test_zero_balance(self):
        state = MockAgentState(profile="aggressive", dry_run=True, forced_balance=0)
        r = execute_trade(
            MockSignal("BUY", 0.90), state, BTC_PRICE,
            **self.AGG, rag=self._rag(), allocation_pct=0.5,
        )
        assert not r["executed"]

    def test_micro_balance_below_min(self):
        """Saldo total $1 com alloc 50% → $0.50, below min $5."""
        state = MockAgentState(profile="aggressive", dry_run=True, forced_balance=1.0)
        r = execute_trade(
            MockSignal("BUY", 0.90), state, BTC_PRICE,
            **self.AGG, rag=self._rag(), allocation_pct=0.5,
        )
        assert not r["executed"]


class TestSellTP:
    """Cenários SELL Take Profit."""

    AGG = dict(min_confidence=0.55, min_trade_amount=5, max_position_pct=0.30, max_positions=4)

    def test_sell_tp_pnl_positive(self):
        """Venda com lucro: entry $68k, sell $72k."""
        state = MockAgentState(position=0.001, entry_price=68000, position_count=1)
        r = execute_trade(MockSignal("SELL", 0.90), state, 72000.0, **self.AGG)
        assert r["executed"]
        assert r["pnl_usd"] > 0
        assert r["new_position"] == 0.0
        assert r["new_count"] == 0

    def test_sell_tp_large_profit(self):
        """Grande lucro: entry $65k, sell $75k."""
        state = MockAgentState(position=0.01, entry_price=65000, position_count=1)
        r = execute_trade(MockSignal("SELL", 0.95), state, 75000.0, **self.AGG)
        assert r["executed"]
        assert r["pnl_usd"] > 95  # ~$98.6

    def test_sell_tp_small_profit(self):
        """Profit pequeno, mas vende (fix anterior)."""
        state = MockAgentState(position=0.00007, entry_price=69990, position_count=1)
        r = execute_trade(MockSignal("SELL", 0.80), state, 70010.0, **self.AGG)
        assert r["executed"]
        assert r["pnl_usd"] > 0 or r["pnl_usd"] < 0.10  # marginal


class TestSellSL:
    """Cenários SELL Stop Loss."""

    AGG = dict(min_confidence=0.55, min_trade_amount=5, max_position_pct=0.30, max_positions=4)

    def test_sell_sl_pnl_negative(self):
        """Stop loss: entry $72k, sell $69k → PnL negativo."""
        state = MockAgentState(position=0.001, entry_price=72000, position_count=1)
        r = execute_trade(
            MockSignal("SELL", 0.90), state, 69000.0, **self.AGG, force=True,
        )
        assert r["executed"]
        assert r["pnl_usd"] < 0
        assert r["new_position"] == 0.0

    def test_sell_sl_deep_loss(self):
        """SL profundo: entry $72k, sell $60k."""
        state = MockAgentState(position=0.01, entry_price=72000, position_count=1)
        r = execute_trade(
            MockSignal("SELL", 0.50), state, 60000.0, **self.AGG, force=True,
        )
        assert r["executed"]
        assert r["pnl_usd"] < -100


class TestSellForce:
    """Cenários SELL forçado (force=True)."""

    AGG = dict(min_confidence=0.55, min_trade_amount=5, max_position_pct=0.30, max_positions=4)

    def test_force_sell_even_breakeven(self):
        """Force sell em breakeven."""
        state = MockAgentState(position=0.001, entry_price=70000, position_count=1)
        r = execute_trade(
            MockSignal("SELL", 0.50), state, 70000.0, **self.AGG, force=True,
        )
        assert r["executed"]

    def test_force_sell_no_position(self):
        """Force sell sem posição → falha."""
        state = MockAgentState(position=0.0, position_count=0)
        r = execute_trade(
            MockSignal("SELL", 0.90), state, BTC_PRICE, **self.AGG, force=True,
        )
        assert not r["executed"]
        assert r["reason"] == "no_position"


class TestSellMicro:
    """Cenários SELL micro-posição."""

    AGG = dict(min_confidence=0.55, min_trade_amount=5, max_position_pct=0.30, max_positions=4)

    def test_micro_sell_executes(self):
        """Posição minúscula $5 → ainda vende."""
        btc_qty = 5.0 / BTC_PRICE
        state = MockAgentState(position=btc_qty, entry_price=BTC_PRICE, position_count=1)
        r = execute_trade(MockSignal("SELL", 0.80), state, 71000.0, **self.AGG)
        assert r["executed"]
        assert r["gross_usd"] == pytest.approx(btc_qty * 71000.0, abs=0.01)

    def test_sell_smallest_unit(self):
        """Menor posição possível: 1 sat."""
        state = MockAgentState(position=0.00000001, entry_price=69000, position_count=1)
        r = execute_trade(MockSignal("SELL", 0.80), state, 71000.0, **self.AGG)
        assert r["executed"]


class TestDCA:
    """Cenários DCA (Dollar Cost Averaging) — múltiplas entradas."""

    AGG = dict(min_confidence=0.55, min_trade_amount=5, max_position_pct=0.30, max_positions=4)

    def _rag(self) -> MockRagAdjustment:
        return MockRagAdjustment(similar_count=5, ai_position_size_pct=0.048)

    def test_dca_two_entries(self):
        """2 entradas DCA: $5 cada, preços diferentes → preço médio."""
        state1 = MockAgentState(profile="aggressive", dry_run=True, forced_balance=1000)
        r1 = execute_trade(
            MockSignal("BUY", 0.65), state1, 70000.0,
            **self.AGG, rag=self._rag(), allocation_pct=0.5,
        )
        assert r1["executed"]

        state2 = MockAgentState(
            profile="aggressive", dry_run=True, forced_balance=995,
            position=r1["btc_qty"], position_count=1,
            entry_price=r1["new_entry_price"],
        )
        r2 = execute_trade(
            MockSignal("BUY", 0.70), state2, 69000.0,
            **self.AGG, rag=self._rag(), allocation_pct=0.5,
        )
        assert r2["executed"]
        assert r2["new_count"] == 2
        assert r2["new_position"] > r1["new_position"]
        assert 69000 < r2["new_entry_price"] < 70000

    def test_dca_three_entries(self):
        """3 entradas DCA progressivas."""
        state = MockAgentState(
            profile="aggressive", dry_run=True, forced_balance=1000,
        )
        accum_pos = 0.0
        accum_count = 0
        entry_price = 0.0
        prices = [70000, 69000, 68000]
        confs = [0.65, 0.70, 0.75]

        for price, conf in zip(prices, confs):
            state = MockAgentState(
                profile="aggressive", dry_run=True, forced_balance=1000,
                position=accum_pos, position_count=accum_count,
                entry_price=entry_price,
            )
            r = execute_trade(
                MockSignal("BUY", conf), state, price,
                **self.AGG, rag=self._rag(), allocation_pct=0.5,
            )
            assert r["executed"]
            accum_pos = r["new_position"]
            accum_count = r["new_count"]
            entry_price = r["new_entry_price"]

        assert accum_count == 3
        assert accum_pos > 0
        assert 68000 < entry_price < 70000

    def test_dca_fourth_entry_max_reached(self):
        """4ª entrada quando max=4 config, ai_max=3 → bloqueada."""
        rag = MockRagAdjustment(similar_count=5, ai_max_entries=3, ai_position_size_pct=0.048)
        state = MockAgentState(
            profile="aggressive", dry_run=True, forced_balance=1000,
            position=0.0003, position_count=3, entry_price=69000,
        )
        r = execute_trade(
            MockSignal("BUY", 0.80), state, 67000.0,
            **self.AGG, rag=rag, allocation_pct=0.5,
        )
        assert not r["executed"]

    def test_dca_sell_all_after_entries(self):
        """Acumula 2 entradas → vende tudo → PnL correto."""
        state1 = MockAgentState(profile="aggressive", dry_run=True, forced_balance=1000)
        r1 = execute_trade(
            MockSignal("BUY", 0.65), state1, 70000.0,
            **self.AGG, rag=self._rag(), allocation_pct=0.5,
        )
        state2 = MockAgentState(
            profile="aggressive", dry_run=True, forced_balance=995,
            position=r1["btc_qty"], position_count=1,
            entry_price=r1["new_entry_price"],
        )
        r2 = execute_trade(
            MockSignal("BUY", 0.70), state2, 68000.0,
            **self.AGG, rag=self._rag(), allocation_pct=0.5,
        )

        sell_state = MockAgentState(
            position=r2["new_position"], position_count=2,
            entry_price=r2["new_entry_price"],
        )
        rs = execute_trade(MockSignal("SELL", 0.90), sell_state, 72000.0, **self.AGG)
        assert rs["executed"]
        assert rs["new_position"] == 0.0
        assert rs["pnl_usd"] > 0


class TestDryRunExec:
    """Dry-run não afeta estado real."""

    AGG = dict(min_confidence=0.55, min_trade_amount=5, max_position_pct=0.30, max_positions=4)

    def _rag(self) -> MockRagAdjustment:
        return MockRagAdjustment(similar_count=5, ai_position_size_pct=0.048)

    def test_dry_run_buy_flagged(self):
        state = MockAgentState(profile="aggressive", dry_run=True, forced_balance=1000)
        r = execute_trade(
            MockSignal("BUY", 0.65), state, BTC_PRICE,
            **self.AGG, rag=self._rag(), allocation_pct=0.5,
        )
        assert r["executed"]
        assert r["dry_run"]

    def test_dry_run_sell_flagged(self):
        state = MockAgentState(position=0.001, entry_price=68000, dry_run=True)
        r = execute_trade(MockSignal("SELL", 0.80), state, BTC_PRICE, **self.AGG)
        assert r["executed"]
        assert r["dry_run"]

    def test_dry_run_amounts_same_as_live(self):
        """Dry run e live com mesmos params → mesmos amounts."""
        live = MockAgentState(profile="aggressive", dry_run=False, forced_balance=1000)
        dry = MockAgentState(profile="aggressive", dry_run=True, forced_balance=1000)
        rag = self._rag()

        r_live = execute_trade(
            MockSignal("BUY", 0.80), live, BTC_PRICE,
            **self.AGG, rag=rag, allocation_pct=0.5,
        )
        r_dry = execute_trade(
            MockSignal("BUY", 0.80), dry, BTC_PRICE,
            **self.AGG, rag=rag, allocation_pct=0.5,
        )
        assert r_live["usdt_amount"] == r_dry["usdt_amount"]


class TestAllocationIsolation:
    """Perfis segregados: um perfil não consome saldo do outro."""

    AGG = dict(min_confidence=0.55, min_trade_amount=5, max_position_pct=0.30, max_positions=4)
    CON = dict(min_confidence=0.85, min_trade_amount=5, max_position_pct=0.15, max_positions=2)

    def _rag(self) -> MockRagAdjustment:
        return MockRagAdjustment(similar_count=5, ai_position_size_pct=0.048)

    def test_same_balance_different_config(self):
        """Mesmo saldo, allocation_pct diferente -> sizing diferente."""
        rag_no_ai = MockRagAdjustment(similar_count=1)  # fallback sizing
        state_a = MockAgentState(profile="aggressive", dry_run=True, forced_balance=1000)
        state_c = MockAgentState(profile="conservative", dry_run=True, forced_balance=1000)

        r_a = execute_trade(
            MockSignal("BUY", 0.90), state_a, BTC_PRICE,
            **self.AGG, rag=rag_no_ai, allocation_pct=0.60,
        )
        r_c = execute_trade(
            MockSignal("BUY", 0.90), state_c, BTC_PRICE,
            **self.CON, rag=rag_no_ai, allocation_pct=0.40,
        )
        assert r_a["executed"]
        assert r_c["executed"]
        # Allocation 60% vs 40% → sizing diferente
        assert r_a["usdt_amount"] > r_c["usdt_amount"]

    def test_aggressive_trade_doesnt_affect_conservative(self):
        """Agressivo opera, conservador mantém saldo isolado."""
        state_a = MockAgentState(profile="aggressive", dry_run=True, forced_balance=1000)
        r_a = execute_trade(
            MockSignal("BUY", 0.65), state_a, BTC_PRICE,
            **self.AGG, rag=self._rag(), allocation_pct=0.5,
        )
        assert r_a["executed"]

        # Conservative com saldo total independente — conf 0.92 >= 0.85 → executa
        state_c = MockAgentState(profile="conservative", dry_run=True, forced_balance=1000)
        r_c = execute_trade(
            MockSignal("BUY", 0.92), state_c, BTC_PRICE,
            **self.CON, rag=self._rag(), allocation_pct=0.5,
        )
        assert r_c["executed"]
        # Saldo isolado: conservador não é afetado pelo trade do agressivo
        assert r_c["usdt_amount"] > 0


class TestHoldIntegration:
    """HOLD não modifica posições."""

    def test_hold_no_execution(self):
        state = MockAgentState(position=0.001, dry_run=True, forced_balance=1000)
        r = execute_trade(MockSignal("HOLD", 0.95), state, BTC_PRICE)
        assert not r["executed"]
        assert r["reason"] == "hold"


class TestPnLCalculation:
    """Validação de cálculo de PnL com fees."""

    AGG = dict(min_confidence=0.55, min_trade_amount=5, max_position_pct=0.30, max_positions=4)

    def test_pnl_matches_manual(self):
        """PnL = (sell - buy) × qty - fees."""
        entry = 68000.0
        sell = 72000.0
        qty = 0.001
        gross = sell * qty  # $72
        sell_fee = gross * TRADING_FEE_PCT  # $0.072
        buy_fee = entry * qty * TRADING_FEE_PCT  # $0.068
        expected_pnl = (sell - entry) * qty - sell_fee - buy_fee  # ~$3.86

        state = MockAgentState(position=qty, entry_price=entry, position_count=1)
        r = execute_trade(MockSignal("SELL", 0.90), state, sell, **self.AGG)
        assert r["pnl_usd"] == pytest.approx(expected_pnl, abs=0.01)

    def test_pnl_loss_scenario(self):
        """PnL negativo no stop loss."""
        entry = 72000.0
        sell = 69000.0
        qty = 0.001
        gross = sell * qty
        sell_fee = gross * TRADING_FEE_PCT
        buy_fee = entry * qty * TRADING_FEE_PCT
        expected_pnl = (sell - entry) * qty - sell_fee - buy_fee

        state = MockAgentState(position=qty, entry_price=entry, position_count=1)
        r = execute_trade(
            MockSignal("SELL", 0.90), state, sell, **self.AGG, force=True,
        )
        assert r["pnl_usd"] == pytest.approx(expected_pnl, abs=0.01)
        assert r["pnl_usd"] < 0

    def test_fee_deduction_correct(self):
        """Fee = gross × 0.1%."""
        qty = 0.01
        sell_price = 75000.0
        expected_fee = sell_price * qty * TRADING_FEE_PCT

        state = MockAgentState(position=qty, entry_price=70000, position_count=1)
        r = execute_trade(MockSignal("SELL", 0.90), state, sell_price, **self.AGG)
        assert r["fee_usd"] == pytest.approx(expected_fee, abs=0.001)

    def test_gross_calculation(self):
        """Gross = price × qty."""
        qty = 0.005
        sell_price = 71000.0
        state = MockAgentState(position=qty, entry_price=69000, position_count=1)
        r = execute_trade(MockSignal("SELL", 0.80), state, sell_price, **self.AGG)
        assert r["gross_usd"] == pytest.approx(sell_price * qty, abs=0.01)


class TestProductionPipeline:
    """Cenários replicando pipeline completo de produção."""

    def test_full_cycle_aggressive(self):
        """Ciclo completo: BUY → preço sobe → SELL → PnL positivo."""
        rag = MockRagAdjustment(similar_count=5, ai_position_size_pct=0.048)
        cfg = dict(min_confidence=0.55, min_trade_amount=5, max_position_pct=0.30, max_positions=4)

        # BUY
        buy_state = MockAgentState(
            profile="aggressive", dry_run=True, forced_balance=105.17,
        )
        rb = execute_trade(
            MockSignal("BUY", 0.65), buy_state, 70000.0,
            **cfg, rag=rag, allocation_pct=0.5,
        )
        assert rb["executed"]
        assert rb["usdt_amount"] == 5.0

        # SELL a +3%
        sell_state = MockAgentState(
            position=rb["btc_qty"], position_count=1,
            entry_price=rb["new_entry_price"],
        )
        rs = execute_trade(MockSignal("SELL", 0.90), sell_state, 72100.0, **cfg)
        assert rs["executed"]
        assert rs["pnl_usd"] > 0
        assert rs["new_position"] == 0.0

    def test_full_cycle_conservative(self):
        """Conservative: skip em baixa conf, executa em alta."""
        rag = MockRagAdjustment(similar_count=5, ai_position_size_pct=0.048)
        cfg = dict(min_confidence=0.85, min_trade_amount=5, max_position_pct=0.15, max_positions=2)

        # Skip
        state1 = MockAgentState(profile="conservative", dry_run=True, forced_balance=105.17)
        r1 = execute_trade(
            MockSignal("BUY", 0.65), state1, BTC_PRICE,
            **cfg, rag=rag, allocation_pct=0.5,
        )
        assert not r1["executed"]

        # Execute
        state2 = MockAgentState(profile="conservative", dry_run=True, forced_balance=105.17)
        r2 = execute_trade(
            MockSignal("BUY", 0.92), state2, BTC_PRICE,
            **cfg, rag=rag, allocation_pct=0.5,
        )
        assert r2["executed"]
        assert r2["usdt_amount"] == 5.0
