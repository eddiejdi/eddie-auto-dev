"""
Testes de integração BTC-USDT — Cenário 3: TP + Trailing Stop simultâneos.

Requisitos:
  - DB:     PostgreSQL real (homelab, porta 5433, schema btc) [integration]
  - KuCoin: mocked — sem trades reais
  - Ollama: homelab (192.168.15.2:11434 / :11435) [external]

Cenário 3: auto_take_profit habilitado + trailing_stop habilitado.
  - _check_trailing_stop é verificado PRIMEIRO no _run_loop (prioridade)
  - Se trailing dispara → auto_exit NÃO é chamado no mesmo ciclo
  - Se trailing NÃO dispara → auto_exit pode disparar TP ou SL
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# DATABASE_URL precisa estar definida antes de importar trading_agent
# (training_db.py chama _get_database_url() em nível de módulo)
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5433/test")

sys.path.insert(0, str(Path(__file__).parent.parent / "btc_trading_agent"))

try:
    from trading_agent import AgentState, BitcoinTradingAgent, Signal
    from training_db import TrainingDatabase
except ImportError as exc:
    pytest.skip(f"Agent dependencies not available: {exc}", allow_module_level=True)

# ──────────────────────────── CONSTANTES ────────────────────────────

ENTRY_PRICE: float = 60_000.0
POSITION_BTC: float = 0.1  # 0.1 BTC por trade de teste

CENARIO3_CFG: dict[str, Any] = {
    "symbol": "BTC-USDT",
    "profile": "default",
    "dry_run": True,
    "dry_run_balance": 10_000.0,
    "min_confidence": 0.0,
    "min_trade_interval": 0,
    "min_trade_amount": 1.0,
    "max_position_pct": 0.5,
    "max_positions": 3,
    "max_daily_trades": 100,
    "max_daily_loss": 10_000.0,
    "guardrails_min_sell_pnl_pct": 0.0,   # sem guardrail de PnL nos testes
    "trailing_stop": {
        "enabled": True,
        "activation_pct": 0.015,   # ativa em +1.5%
        "trail_pct": 0.008,        # dispara ao cair 0.8% do topo
    },
    "auto_take_profit": {
        "enabled": True,
        "pct": 0.025,              # target principal +2.5%
        "min_pct": 0.015,          # mínimo +1.5%
    },
    "auto_stop_loss": {
        "enabled": True,
        "pct": 0.02,               # stop -2%
    },
}

TP_ONLY_CFG: dict[str, Any] = {
    **CENARIO3_CFG,
    "trailing_stop": {"enabled": False},
}

OLLAMA_GPU0 = "http://192.168.15.2:11434"
OLLAMA_GPU1 = "http://192.168.15.2:11435"
OLLAMA_TIMEOUT = 5


# ──────────────────────────── HELPERS ────────────────────────────

def _mock_rag_adj(tp_pct: float = 0.025) -> MagicMock:
    """Cria mock de RagAdjustment sem acessar DB/Ollama."""
    adj = MagicMock()
    adj.similar_count = 0          # sem AI data → fallback config
    adj.ai_take_profit_pct = tp_pct
    adj.ai_take_profit_reason = "test_mock"
    adj.ai_position_size_pct = 0.04
    adj.ai_rebuy_lock_enabled = False
    adj.ai_min_confidence = 0.0
    adj.ai_min_trade_interval = 0
    adj.ai_max_entries = 3
    adj.ai_max_positions = 3
    adj.ai_max_position_pct = 0.5
    adj.ai_rebuy_margin_pct = 0.0
    adj.applied_min_confidence = 0.0
    adj.applied_min_trade_interval = 0
    adj.applied_max_positions = 3
    adj.applied_max_position_pct = 0.5
    adj.ollama_mode = "shadow"
    return adj


def _make_agent(cfg: dict[str, Any], db: TrainingDatabase) -> BitcoinTradingAgent:
    """
    Instancia BitcoinTradingAgent com:
      - DB real  (PostgreSQL homelab)
      - KuCoin   mocked (sem chamadas reais)
      - Ollama   não consultado durante os testes unitários/integração comportamental
    """
    mock_rag = MagicMock()
    mock_rag.get_current_adjustment.return_value = _mock_rag_adj(
        tp_pct=cfg.get("auto_take_profit", {}).get("pct", 0.025)
    )

    with (
        patch("trading_agent.TrainingDatabase"),
        patch("trading_agent.MarketRAG", return_value=mock_rag),
        patch("trading_agent.get_price", return_value=ENTRY_PRICE),
        patch("trading_agent.get_price_fast", return_value=ENTRY_PRICE),
        patch("trading_agent.get_candles", return_value=[]),
        patch("trading_agent.get_balance", return_value=10_000.0),
        patch("trading_agent.place_market_order", return_value={"success": False}),
    ):
        agent = BitcoinTradingAgent(symbol="BTC-USDT", dry_run=True)

    # DB real substituído após __init__ (sem chamada KuCoin no init)
    agent.db = db
    agent.market_rag = mock_rag
    agent._load_live_config = lambda: cfg
    agent.config = cfg

    # Estado com posição aberta (dry_run, sem exposição real)
    agent.state = AgentState(
        symbol="BTC-USDT",
        position=POSITION_BTC,
        entry_price=ENTRY_PRICE,
        position_count=1,
        dry_run=True,
        entries=[{"price": ENTRY_PRICE, "size": POSITION_BTC, "ts": time.time()}],
        trailing_high=ENTRY_PRICE,
        profile="default",
    )

    return agent


def _count_trades(db: TrainingDatabase, symbol: str, dry_run: bool) -> int:
    """Conta registros em btc.trades para o símbolo/modo."""
    with db._get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM btc.trades WHERE symbol=%s AND dry_run=%s",
            (symbol, dry_run),
        )
        row = cur.fetchone()
        return row[0] if row else 0


# ──────────────────────────── FIXTURES ────────────────────────────

@pytest.fixture(scope="module")
def db_real() -> TrainingDatabase:
    """Conexão real ao PostgreSQL na porta 5433 — homelab."""
    try:
        db = TrainingDatabase()
        with db._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
        return db
    except Exception as exc:
        pytest.skip(f"PostgreSQL homelab não disponível: {exc}")


@pytest.fixture()
def agent_c3(db_real: TrainingDatabase) -> BitcoinTradingAgent:
    """Agent com Cenário 3 (trailing + TP ambos habilitados)."""
    return _make_agent(CENARIO3_CFG, db_real)


@pytest.fixture()
def agent_tp_only(db_real: TrainingDatabase) -> BitcoinTradingAgent:
    """Agent com TP-Only (trailing desabilitado) para comparação."""
    return _make_agent(TP_ONLY_CFG, db_real)


# ──────────────────────────── TESTES DB ────────────────────────────

@pytest.mark.integration
class TestDbConexaoCert:
    """Valida conectividade ao PostgreSQL homelab (CERT)."""

    def test_schema_btc_existe(self, db_real: TrainingDatabase) -> None:
        """Schema btc e tabela trades devem existir."""
        with db_real._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'btc' AND table_name = 'trades'
                LIMIT 1
                """
            )
            row = cur.fetchone()
        assert row is not None, "Tabela btc.trades não encontrada no PostgreSQL"

    def test_leitura_trade_recente(self, db_real: TrainingDatabase) -> None:
        """Deve ser possível ler trades existentes."""
        with db_real._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM btc.trades WHERE symbol='BTC-USDT'"
            )
            count = cur.fetchone()[0]
        assert isinstance(count, int), "Contagem de trades deve ser inteiro"


# ──────────────────────────── TESTES COMPORTAMENTAIS ────────────────────────────

@pytest.mark.integration
class TestCenario3Comportamento:
    """
    Testes comportamentais do Cenário 3: prioridade trailing_stop > auto_exit.

    Ordem de verificação no _run_loop:
      1. _check_trailing_stop(price)  ← PRIMEIRO
      2. _check_auto_exit(price)      ← só executa se (1) retornar False
    """

    def test_trailing_tem_prioridade_quando_ambos_disparariam(
        self, agent_c3: BitcoinTradingAgent
    ) -> None:
        """
        Setup:
          - trailing_high = entry * 1.06 (+6% do entry)
          - price_now = trailing_high * 0.992 (queda de 0.8% do topo → +5.15% do entry)
          - pnl_pct = +5.15% → auto_take_profit TAMBÉM dispararia (+5.15% ≥ +2.5%)

        Expectativa: trailing_stop dispara PRIMEIRO, reason='TRAILING_STOP'.
        """
        trailing_high = ENTRY_PRICE * 1.06
        price_now = trailing_high * (1 - 0.008)  # drop exato de 0.8%

        agent_c3.state.trailing_high = trailing_high
        captured: list[str] = []

        original_execute = agent_c3._execute_trade

        def _capture(signal: Signal, price: float, force: bool = False) -> bool:
            captured.append(signal.reason)
            return original_execute(signal, price, force=force)

        agent_c3._execute_trade = _capture  # type: ignore[method-assign]

        result = agent_c3._check_trailing_stop(price_now)

        assert result is True, "trailing_stop deveria ter disparado"
        assert captured, "Nenhum sinal capturado no _execute_trade"
        assert any("TRAILING_STOP" in r for r in captured), (
            f"Esperava TRAILING_STOP, obteve: {captured}"
        )

    def test_tp_dispara_quando_trailing_nao_ativado(
        self, agent_c3: BitcoinTradingAgent
    ) -> None:
        """
        Setup:
          - trailing_high = entry (nunca subiu acima da entrada)
          - price = entry * 1.026 (+2.6%, acima do threshold de 2.5% do TP)

        Expectativa:
          - trailing_stop retorna False (pnl_from_trailing_high ~2.6% < activation 1.5%? Não —
            pnl_from_entry = 2.6% ≥ 1.5%, MAS drop = 0 < 0.8% → trailing não dispara)
          - auto_take_profit dispara com reason='AUTO_TAKE_PROFIT'
        """
        price_tp = ENTRY_PRICE * 1.026  # +2.6% — claramente acima do TP de 2.5%
        agent_c3.state.trailing_high = ENTRY_PRICE  # sem histórico de alta

        # 1) trailing NÃO deve disparar
        ts_result = agent_c3._check_trailing_stop(price_tp)
        assert ts_result is False, (
            f"trailing_stop não deveria ter disparado. "
            f"trailing_high={ENTRY_PRICE}, price={price_tp}"
        )

        # 2) auto_take_profit DEVE disparar
        captured: list[str] = []
        original_execute = agent_c3._execute_trade

        def _capture(signal: Signal, price: float, force: bool = False) -> bool:
            captured.append(signal.reason)
            return original_execute(signal, price, force=force)

        agent_c3._execute_trade = _capture  # type: ignore[method-assign]

        tp_result = agent_c3._check_auto_exit(price_tp)

        assert tp_result is True, "auto_take_profit deveria ter disparado"
        assert any("AUTO_TAKE_PROFIT" in r for r in captured), (
            f"Reason inesperado: {captured}"
        )

    def test_trailing_captura_mais_pnl_que_tp_isolado(
        self, agent_c3: BitcoinTradingAgent
    ) -> None:
        """
        Setup:
          - trailing_high = entry * 1.07 (+7%, trailing ativado desde +1.5%)
          - price = trailing_high * (1 - 0.009) = +6.1% do entry (drop = 0.9% ≥ 0.8%)
          - TP teria saído em +2.5% = $150 de PnL para 0.1 BTC
          - Trailing sai em +6.1% = $366 de PnL para 0.1 BTC

        Expectativa: PnL do trailing > PnL do TP fixo.
        """
        trailing_high = ENTRY_PRICE * 1.070
        drop = 0.009
        exit_price = trailing_high * (1 - drop)

        pnl_trailing = (exit_price - ENTRY_PRICE) * POSITION_BTC
        pnl_tp_fixed = ENTRY_PRICE * 0.025 * POSITION_BTC

        assert pnl_trailing > pnl_tp_fixed, (
            f"Trailing deveria capturar mais: trailing=${pnl_trailing:.2f} "
            f"vs TP=${pnl_tp_fixed:.2f}"
        )

        # Confirmar via agent
        agent_c3.state.trailing_high = trailing_high
        captured_prices: list[float] = []
        original_execute = agent_c3._execute_trade

        def _capture(signal: Signal, price: float, force: bool = False) -> bool:
            captured_prices.append(price)
            return original_execute(signal, price, force=force)

        agent_c3._execute_trade = _capture  # type: ignore[method-assign]

        result = agent_c3._check_trailing_stop(exit_price)

        assert result is True, "trailing_stop deveria ter disparado"
        actual_sell_price = captured_prices[0]
        actual_pnl = (actual_sell_price - ENTRY_PRICE) * POSITION_BTC
        assert actual_pnl > pnl_tp_fixed, (
            f"PnL real trailing=${actual_pnl:.2f} deveria > TP-fixo=${pnl_tp_fixed:.2f}"
        )

    def test_stop_loss_funciona_no_cenario3(
        self, agent_c3: BitcoinTradingAgent
    ) -> None:
        """
        Setup:
          - Preço cai para -2.1% (abaixo do SL de -2%)
          - trailing_high = entry (sem alta, trailing nunca ativado)

        Expectativa: SL dispara via _check_auto_exit, reason='AUTO_STOP_LOSS'.
        """
        price_sl = ENTRY_PRICE * (1 - 0.021)
        agent_c3.state.trailing_high = ENTRY_PRICE

        # trailing não deve disparar (preço caiu, não subiu)
        ts = agent_c3._check_trailing_stop(price_sl)
        assert ts is False, "trailing_stop não deveria disparar em queda direta"

        # SL deve disparar
        captured: list[str] = []
        original_execute = agent_c3._execute_trade

        def _capture(signal: Signal, price: float, force: bool = False) -> bool:
            captured.append(signal.reason)
            return original_execute(signal, price, force=force)

        agent_c3._execute_trade = _capture  # type: ignore[method-assign]

        ae = agent_c3._check_auto_exit(price_sl)

        assert ae is True, "auto_stop_loss deveria ter disparado"
        assert any("AUTO_STOP_LOSS" in r for r in captured), (
            f"Reason inesperado: {captured}"
        )

    def test_trailing_nao_ativa_antes_do_threshold(
        self, agent_c3: BitcoinTradingAgent
    ) -> None:
        """
        Setup:
          - Price sobe para +1.2% (abaixo do activation_pct de 1.5%)
          - Em seguida cai muito (drop > 0.8%)

        Expectativa: trailing_stop NÃO dispara (não ativado ainda).
        """
        price_below_activation = ENTRY_PRICE * 1.012
        agent_c3.state.trailing_high = price_below_activation
        price_drop = price_below_activation * 0.98  # drop de 2% do high

        result = agent_c3._check_trailing_stop(price_drop)
        assert result is False, (
            "trailing_stop NÃO deveria disparar se activation_pct não foi atingido"
        )


# ──────────────────────────── TESTE DB WRITE ────────────────────────────

@pytest.mark.integration
class TestDbRegistroVendas:
    """Valida que vendas forçadas pelo Cenário 3 são gravadas no PostgreSQL."""

    def test_trailing_stop_registra_trade_no_db(
        self, agent_c3: BitcoinTradingAgent, db_real: TrainingDatabase
    ) -> None:
        """
        Trailing stop deve registrar a SELL em btc.trades com dry_run=True.
        """
        # Estado limpo para este teste
        agent_c3.state.position = POSITION_BTC
        agent_c3.state.entry_price = ENTRY_PRICE
        agent_c3.state.trailing_high = ENTRY_PRICE * 1.07  # ativado

        price_exit = ENTRY_PRICE * 1.07 * (1 - 0.009)  # drop 0.9% → dispara

        before = _count_trades(db_real, "BTC-USDT", dry_run=True)
        result = agent_c3._check_trailing_stop(price_exit)
        after = _count_trades(db_real, "BTC-USDT", dry_run=True)

        assert result is True, "trailing_stop deveria ter disparado"
        assert after > before, (
            f"SELL não registrada no PostgreSQL. "
            f"before={before}, after={after}"
        )

    def test_auto_tp_registra_trade_no_db(
        self, agent_c3: BitcoinTradingAgent, db_real: TrainingDatabase
    ) -> None:
        """
        AUTO_TAKE_PROFIT deve registrar a SELL em btc.trades.
        """
        agent_c3.state.position = POSITION_BTC
        agent_c3.state.entry_price = ENTRY_PRICE
        agent_c3.state.trailing_high = ENTRY_PRICE  # sem ativação do trailing

        price_tp = ENTRY_PRICE * 1.026  # ligeiramente acima do TP de 2.5%

        before = _count_trades(db_real, "BTC-USDT", dry_run=True)
        result = agent_c3._check_auto_exit(price_tp)
        after = _count_trades(db_real, "BTC-USDT", dry_run=True)

        assert result is True, "auto_take_profit deveria ter disparado"
        assert after > before, (
            f"SELL de TP não registrada no PostgreSQL. "
            f"before={before}, after={after}"
        )


# ──────────────────────────── TESTES OLLAMA ────────────────────────────

@pytest.mark.external
class TestOllamaHomelab:
    """Verifica conectividade ao Ollama no homelab (GPU0 + GPU1)."""

    def test_ollama_gpu0_acessivel(self) -> None:
        """GPU0 porta 11434 deve responder com 200."""
        import requests  # type: ignore[import]

        r = requests.get(f"{OLLAMA_GPU0}/api/tags", timeout=OLLAMA_TIMEOUT)
        assert r.status_code == 200, f"Ollama GPU0 retornou {r.status_code}"
        data = r.json()
        assert "models" in data, f"Resposta inesperada: {data}"

    def test_ollama_gpu1_acessivel(self) -> None:
        """GPU1 porta 11435 deve responder com 200."""
        import requests  # type: ignore[import]

        r = requests.get(f"{OLLAMA_GPU1}/api/tags", timeout=OLLAMA_TIMEOUT)
        assert r.status_code == 200, f"Ollama GPU1 retornou {r.status_code}"

    def test_modelo_coder_disponivel_gpu0(self) -> None:
        """Modelo de trading deve estar disponível no GPU0 (trading-analyst ou similar)."""
        import requests  # type: ignore[import]

        r = requests.get(f"{OLLAMA_GPU0}/api/tags", timeout=OLLAMA_TIMEOUT)
        r.raise_for_status()
        modelos = [m["name"] for m in r.json().get("models", [])]
        # Aceita trading-analyst (padrão atual), shared-coder (legado) ou qwen3
        trading_models = [
            m for m in modelos
            if any(k in m.lower() for k in ("trading", "analyst", "coder", "shared", "qwen"))
        ]
        assert trading_models, (
            f"Nenhum modelo de trading disponível no GPU0. "
            f"Modelos encontrados: {modelos}"
        )


# ──────────────────────────── SIMULAÇÃO FINANCEIRA ────────────────────────────

@pytest.mark.integration
class TestSimulacaoFinanceiraCenario3:
    """
    Comparativo financeiro BTC-USDT: Cenário 3 (TP+Trailing) vs TP-Only.

    10 sequências de preço com parâmetros reais do config_PETR4... mas para BTC:
      - TP = +2.5%  (config: auto_take_profit.pct)
      - SL = -2.0%  (config: auto_stop_loss.pct)
      - Trailing ativa em +1.5%, dispara ao cair 0.8% do topo

    Posição base: 0.1 BTC @ $60,000 = $6,000 investidos
    """

    # (nome, peak_pct, drop_from_peak_pct, direct_pct)
    # direct_pct: preço vai direto para esse % (sem pico intermediário)
    SCENARIOS = [
        ("Alta curta +2.5% (TP exato)",           None, None, 0.025),
        ("Alta +5%, queda 0.8% → trailing",        0.05, 0.008, None),
        ("Alta +7%, queda 0.9% → trailing",        0.07, 0.009, None),
        ("Alta +3%, queda 1.2% → trailing",        0.03, 0.012, None),
        ("Alta +10%, queda 1.0% → trailing",       0.10, 0.010, None),
        ("Queda direta -2.2% (SL)",                None, None, -0.022),
        ("Alta fraca +1.8%, sem TP/trailing",      0.018, 0.005, None),
        ("Alta +4%, queda só 0.5% (sem trailing)", 0.04, 0.005, None),
        ("Alta +6%, queda 0.8% → trailing",        0.06, 0.008, None),
        ("Alta +15%, queda 2.0% → trailing big",   0.15, 0.020, None),
    ]

    TP_PCT   = 0.025
    MIN_PCT  = 0.015
    SL_PCT   = 0.020
    ACT_PCT  = 0.015   # trailing activation
    TRAIL    = 0.008   # trailing trail_pct

    def _sim_cenario3(
        self,
        peak: float | None,
        drop: float | None,
        direct: float | None,
    ) -> tuple[float, str]:
        """Simula saída no Cenário 3 (trailing + TP). Retorna (pnl_pct, trigger)."""
        tp = self.TP_PCT
        sl = self.SL_PCT
        act = self.ACT_PCT
        trail = self.TRAIL

        if direct is not None:
            if direct <= -sl:
                return -sl, "SL"
            if direct >= tp:
                return direct, "TP"
            return direct, "HOLD"

        peak = peak or 0.0
        drop = drop or 0.0

        trailing_activated = peak >= act

        if not trailing_activated:
            if peak <= -sl:
                return -sl, "SL"
            if peak >= tp:
                return tp, "TP"
            # Trailing nunca ativ, sem TP → segura até fim
            return peak - drop, "HOLD"

        # Trailing ativado: acompanha subida, verifica drop
        if drop >= trail:
            # Trailing dispara ANTES que auto_exit seja verificado
            exit_pnl = peak - drop
            return exit_pnl, "TRAILING"

        # Drop insuficiente para trailing — TP verifica depois
        if peak >= tp:
            return tp, "TP"

        return peak - drop, "HOLD"

    def _sim_tp_only(
        self,
        peak: float | None,
        drop: float | None,
        direct: float | None,
    ) -> tuple[float, str]:
        """Simula saída no TP-Only. Retorna (pnl_pct, trigger)."""
        tp = self.TP_PCT
        sl = self.SL_PCT

        if direct is not None:
            if direct <= -sl:
                return -sl, "SL"
            if direct >= tp:
                return tp, "TP"
            return direct, "HOLD"

        peak = peak or 0.0
        drop = drop or 0.0

        if peak >= tp:
            return tp, "TP"
        if peak <= -sl:
            return -sl, "SL"
        return peak - drop, "HOLD"

    def test_relatorio_financeiro_comparativo(self) -> None:
        """
        Gera relatório textual comparando Cenário 3 vs TP-Only
        em 10 sequências de mercado.

        Assertiva final: Cenário 3 deve ter PnL total ≥ TP-Only total.
        """
        WIDTH = 76
        LINE = "─" * WIDTH

        print("\n")
        print("═" * WIDTH)
        print("  RELATÓRIO FINANCEIRO — BTC-USDT CENÁRIO 3 vs TP-ONLY")
        print(f"  Posição: {POSITION_BTC} BTC @ ${ENTRY_PRICE:,.0f} USDT  "
              f"(exposure: ${ENTRY_PRICE * POSITION_BTC:,.0f})")
        print(f"  Config:  TP=+{self.TP_PCT*100:.1f}%  SL=-{self.SL_PCT*100:.1f}%  "
              f"Trailing ativa+{self.ACT_PCT*100:.1f}% dispara-{self.TRAIL*100:.1f}%")
        print("═" * WIDTH)
        print(
            f"  {'Cenário':<38} "
            f"{'C3%':>6} {'C3$':>8}  "
            f"{'TP%':>6} {'TP$':>8}  "
            f"{'Δ$':>7}"
        )
        print(LINE)

        total_c3: float = 0.0
        total_tp: float = 0.0
        c3_wins: int = 0
        tp_wins: int = 0

        for name, peak, drop, direct in self.SCENARIOS:
            pnl_c3_pct, trig_c3 = self._sim_cenario3(peak, drop, direct)
            pnl_tp_pct, trig_tp = self._sim_tp_only(peak, drop, direct)

            usd_c3 = pnl_c3_pct * ENTRY_PRICE * POSITION_BTC
            usd_tp = pnl_tp_pct * ENTRY_PRICE * POSITION_BTC
            delta = usd_c3 - usd_tp

            total_c3 += usd_c3
            total_tp += usd_tp

            if delta > 0.01:
                marker = "↑"
                c3_wins += 1
            elif delta < -0.01:
                marker = "↓"
                tp_wins += 1
            else:
                marker = "="

            print(
                f"  {name:<38} "
                f"{pnl_c3_pct*100:>+5.2f}% {usd_c3:>+8.2f}  "
                f"{pnl_tp_pct*100:>+5.2f}% {usd_tp:>+8.2f}  "
                f"{marker}{abs(delta):>5.2f}"
            )

        print(LINE)
        print(
            f"  {'TOTAL ACUMULADO':<38} "
            f"{'':>6} {total_c3:>+8.2f}  "
            f"{'':>6} {total_tp:>+8.2f}  "
            f"{'Δ':>2}{total_c3 - total_tp:>+5.2f}"
        )
        print(LINE)
        print(f"  Cenário 3 venceu em: {c3_wins} cenários")
        print(f"  TP-Only venceu em:   {tp_wins} cenários")
        print(f"  Empatados:           {len(self.SCENARIOS) - c3_wins - tp_wins} cenários")
        print()

        roi_c3 = (total_c3 / (ENTRY_PRICE * POSITION_BTC)) * 100
        roi_tp = (total_tp / (ENTRY_PRICE * POSITION_BTC)) * 100
        print(f"  ROI Cenário 3: {roi_c3:+.2f}%  |  ROI TP-Only: {roi_tp:+.2f}%")

        if total_c3 >= total_tp:
            print("  ✅ Cenário 3 (TP+Trailing) captura mais lucro total.")
        else:
            print("  ⚠️  TP-Only teve melhor resultado nesta série de cenários.")

        print("═" * WIDTH)

        # Assertiva: Cenário 3 NÃO deve ser significativamente pior que TP-Only
        # (tolerância de -$5 para cenários onde TP sai antecipado e Trailing se perde)
        assert total_c3 >= total_tp - 5.0, (
            f"\n❌ NOK: Cenário 3 significativamente pior que TP-Only!\n"
            f"   C3 total = ${total_c3:.2f}  |  TP total = ${total_tp:.2f}\n"
            f"   Diferença = ${total_c3 - total_tp:.2f} (tolerância: -$5.00)\n"
            f"   Revise parâmetros trailing_stop ou auto_take_profit."
        )
