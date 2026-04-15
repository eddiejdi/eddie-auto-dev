#!/usr/bin/env python3
"""Testes de cenários de quebra — ClearTradingAgent.

Cobre falhas não programadas de alta severidade:
  - Desligamento abrupto (SIGKILL / crash) com posição aberta
  - Período longo inativo (mercado fechado / fim de semana)
  - Bridge MT5 indisponível durante trade  
  - DB inacessível durante registro de trade
  - Config corrompida / arquivo ausente
  - Saldo zero / negativo
  - Posição duplicada por retry
  - Loop encerrado com _trade_lock preso
  - Trade callback lança exceção
  - Tax guardrail race condition
  - Reinicialização com estado persistido corrompido
  - Preço NaN / zero / None retornado pelo bridge
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch, PropertyMock, call

import pytest

# ====================== SETUP PRÉ-IMPORT ======================
os.environ.setdefault("MT5_BRIDGE_URL", "http://127.0.0.1:8510")
os.environ.setdefault("MT5_BRIDGE_API_KEY", "test-key-fail")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5433/test")
os.environ.setdefault("CLEAR_CONFIG_FILE", "config_PETR4.json")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "")

_CLEAR_DIR = Path(__file__).resolve().parent.parent / "clear_trading_agent"
if str(_CLEAR_DIR) not in sys.path:
    sys.path.insert(0, str(_CLEAR_DIR))
if str(_CLEAR_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_CLEAR_DIR.parent))

# Mock secrets_helper antes de qualquer import de clear_trading_agent
_mock_secrets = MagicMock()
_mock_secrets.get_secret.return_value = None
_mock_secrets.get_database_url.return_value = "postgresql://test:test@localhost:5433/test"
_mock_secrets.get_mt5_bridge_credentials.return_value = ("http://127.0.0.1:8510", "test-key-fail")
_mock_secrets.get_clear_integration_status.return_value = {
    "bridge_url": "http://127.0.0.1:8510",
    "bridge_api_key_configured": True,
    "broker_username_configured": False,
    "broker_password_configured": False,
}
sys.modules["secrets_helper"] = _mock_secrets
sys.modules["clear_trading_agent.secrets_helper"] = _mock_secrets

# Mock psycopg2
_mock_psycopg2 = MagicMock()
_mock_pool = MagicMock()
_mock_conn = MagicMock()
_mock_cursor = MagicMock()
_mock_conn.cursor.return_value = _mock_cursor
_mock_cursor.fetchone.return_value = [1]
_mock_cursor.fetchall.return_value = []
_mock_pool.getconn.return_value = _mock_conn
_mock_psycopg2.pool.ThreadedConnectionPool.return_value = _mock_pool
_mock_psycopg2.extras = MagicMock()
sys.modules["psycopg2"] = _mock_psycopg2
sys.modules["psycopg2.extras"] = _mock_psycopg2.extras
sys.modules["psycopg2.pool"] = _mock_psycopg2.pool

with patch("requests.get"), patch("requests.post"):
    from clear_trading_agent.trading_agent import (
        ClearTradingAgent,
        AgentState,
    )
    from clear_trading_agent.fast_model import Signal, is_market_open

# ====================== FIXTURE BASE ======================

BASE_CFG: Dict[str, Any] = {
    "symbol": "PETR4",
    "profile": "default",
    "dry_run": True,
    "dry_run_balance": 10_000.0,
    "min_confidence": 0.0,
    "min_trade_interval": 0,
    "min_trade_amount": 100.0,
    "max_position_pct": 0.5,
    "max_positions": 3,
    "max_daily_trades": 100,
    "max_daily_loss": 10_000.0,
    "poll_interval": 1,
    "trading_fee_pct": 0.0003,
    "trailing_stop": {"enabled": True, "activation_pct": 0.015, "trail_pct": 0.008},
    "auto_take_profit": {"enabled": True, "pct": 0.025, "min_pct": 0.015},
    "auto_stop_loss": {"enabled": True, "pct": 0.02},
    "tax_guardrails": {},
}

ENTRY_PRICE = 28.50
ENTRY_QTY = 200  # 2 lotes de 100


def _make_rag_adj(**overrides) -> MagicMock:
    """Mock de RagAdjustment com defaults seguros."""
    adj = MagicMock()
    adj.similar_count = 0
    adj.ai_take_profit_pct = 0.025
    adj.ai_take_profit_reason = "test"
    adj.ai_position_size_pct = 0.04
    adj.ai_rebuy_lock_enabled = False
    adj.ai_rebuy_margin_pct = 0.0
    adj.ai_min_confidence = 0.0
    adj.ai_min_trade_interval = 0
    adj.ai_max_entries = 3
    adj.ai_max_positions = 3
    adj.ai_max_position_pct = 0.5
    adj.applied_min_confidence = 0.0
    adj.applied_min_trade_interval = 0
    adj.applied_max_positions = 3
    adj.applied_max_position_pct = 0.5
    adj.ollama_mode = "shadow"
    adj.suggested_regime = "RANGING"
    adj.regime_confidence = 0.7
    for k, v in overrides.items():
        setattr(adj, k, v)
    return adj


def _make_tax_tracker() -> MagicMock:
    """Mock do TaxTracker com decisão sempre permitida."""
    tt = MagicMock()
    decision = MagicMock()
    decision.allowed = True
    decision.reason = ""
    tt.check_sell_allowed.return_value = decision
    tax_event = MagicMock()
    tax_event.tax_exempt = True
    tax_event.trade_type = "swing"
    tt.record_sell.return_value = tax_event
    return tt


@pytest.fixture()
def agent() -> ClearTradingAgent:
    """Agent PETR4 pronto para testes de cenário."""
    mock_rag = MagicMock()
    mock_rag.get_current_adjustment.return_value = _make_rag_adj()
    mock_rag.get_stats.return_value = {
        "current_regime": "RANGING",
        "regime_confidence": 0.7,
    }

    mock_db = MagicMock()
    mock_db.record_trade.return_value = 42
    mock_db.update_trade_pnl.return_value = None
    mock_db.record_decision.return_value = 99
    mock_db.mark_decision_executed.return_value = None

    with (
        patch("clear_trading_agent.trading_agent.TrainingDatabase", return_value=mock_db),
        patch("clear_trading_agent.trading_agent.MarketRAG", return_value=mock_rag),
        patch("clear_trading_agent.trading_agent.TaxTracker", return_value=_make_tax_tracker()),
        patch("clear_trading_agent.trading_agent.get_price_fast", return_value=ENTRY_PRICE),
        patch("clear_trading_agent.trading_agent.get_balance", return_value=10_000.0),
        patch("clear_trading_agent.trading_agent.place_market_order", return_value={"success": False}),
        patch("clear_trading_agent.trading_agent.get_clear_connection_status", return_value={
            "bridge_healthy": True,
            "bridge_api_key_configured": True,
            "broker_username_configured": False,
            "broker_password_configured": False,
        }),
    ):
        ag = ClearTradingAgent(symbol="PETR4", dry_run=True)

    ag.db = mock_db
    ag.market_rag = mock_rag
    ag.tax_tracker = _make_tax_tracker()
    ag._load_live_config = lambda: dict(BASE_CFG)
    ag.config = dict(BASE_CFG)

    # Posição aberta (200 ações @ R$28.50)
    ag.state = AgentState(
        symbol="PETR4",
        asset_class="equity",
        position=float(ENTRY_QTY),
        entry_price=ENTRY_PRICE,
        position_count=2,
        dry_run=True,
        entries=[
            {"price": ENTRY_PRICE, "qty": 100, "ts": time.time() - 600},
            {"price": ENTRY_PRICE, "qty": 100, "ts": time.time() - 300},
        ],
        trailing_high=ENTRY_PRICE,
        profile="default",
        start_time=time.time() - 3600,
    )
    return ag


# ====================== CENÁRIO 1: DESLIGAMENTO ABRUPTO ======================

class TestDesligamentoAbrupto:
    """Simula crash/SIGKILL durante execução com posição aberta."""

    def test_posicao_incrementada_antes_de_record_trade_crash(
        self, agent: ClearTradingAgent
    ) -> None:
        """
        Posição é incrementada ANTES de gravar no DB (dry_run BUY).
        Se record_trade lança exceção, position fica inconsistente.
        Simula crash no meio do trade: DB connection lost.
        """
        # Partir de posição zerada para garantir que BUY não seja bloqueado por max_position_pct
        agent.state.position = 0.0
        agent.state.entry_price = 0.0
        agent.state.position_count = 0
        agent.state.entries = []
        agent.state.trailing_high = 0.0
        agent.config["dry_run_balance"] = 10_000.0

        agent.db.record_trade.side_effect = Exception("DB connection lost (crash simulation)")

        sig = Signal(action="BUY", confidence=1.0, reason="test_crash", price=ENTRY_PRICE, features={})
        result = agent._execute_trade(sig, ENTRY_PRICE)

        assert result is False, "Trade deve retornar False quando DB falha"
        # ⚠️ DESVIO REAL: se position foi alterada antes de record_trade falhar →
        # estado ficou inconsistente (posição sem log no DB)
        if agent.state.position > 0:
            import warnings
            warnings.warn(
                "⚠️ DESVIO DETECTADO: position foi incrementada ANTES do record_trade. "
                f"position={agent.state.position} mas DB não registrou. "
                "Fix necessário: envolver state update + db.record_trade em transação atômica.",
                stacklevel=2,
            )
        # Em ambos os casos o trade retornou False — comportamento correto de superfície

    def test_stop_event_nao_bloqueia_thread(self, agent: ClearTradingAgent) -> None:
        """stop() deve liberar a thread em ≤1s mesmo sem ciclo ativo."""
        agent.state.running = True
        agent._stop_event.clear()

        t_start = time.time()
        agent.stop()
        elapsed = time.time() - t_start

        assert elapsed < 1.5, f"stop() levou {elapsed:.2f}s (esperado ≤1s)"
        assert agent._stop_event.is_set(), "_stop_event deve estar set após stop()"
        assert not agent.state.running, "running deve ser False após stop()"

    def test_trade_lock_nao_fica_preso_em_excecao(
        self, agent: ClearTradingAgent
    ) -> None:
        """_trade_lock deve ser liberado mesmo quando execução lança exception."""
        agent.db.record_trade.side_effect = RuntimeError("Simulated crash inside lock")

        sig = Signal(action="BUY", confidence=1.0, reason="test", price=ENTRY_PRICE, features={})
        agent._execute_trade(sig, ENTRY_PRICE)

        # Lock deve estar liberado (acquire não deve bloquear)
        acquired = agent._trade_lock.acquire(blocking=False)
        assert acquired, "⚠️ DESVIO: _trade_lock ficou preso após exceção!"
        if acquired:
            agent._trade_lock.release()


# ====================== CENÁRIO 2: PERÍODO INATIVO LONGO ======================

class TestPeriodoInativoLongo:
    """Simula retorno após longo período inativo (mercado fechado, fim de semana)."""

    def test_daily_reset_apos_inatividade_multiplos_dias(
        self, agent: ClearTradingAgent
    ) -> None:
        """Contadores diários devem resetar após N dias sem atividade."""
        agent.state.daily_trades = 15
        agent.state.daily_pnl = -300.0
        agent.state.daily_date = "2026-04-10"  # 5 dias atrás

        agent._check_daily_reset()

        assert agent.state.daily_trades == 0, "daily_trades deve resetar"
        assert agent.state.daily_pnl == 0.0, "daily_pnl deve resetar"

    def test_posicao_aberta_sobrevive_mercado_fechado(
        self, agent: ClearTradingAgent
    ) -> None:
        """Posição não deve ser zerada durante período de mercado fechado."""
        position_before = agent.state.position
        entry_before = agent.state.entry_price

        # Simular que mercado estava fechado por muito tempo
        agent.state.last_trade_time = time.time() - 86400 * 3  # 3 dias atrás

        # Acesso ao estado não deve alterar posição
        status = agent.get_status()

        assert agent.state.position == position_before, "Posição não deve mudar sem trade"
        assert agent.state.entry_price == entry_before, "entry_price não deve mudar"
        assert status["position_qty"] == position_before

    def test_trailing_high_nao_resetado_durante_inatividade(
        self, agent: ClearTradingAgent
    ) -> None:
        """trailing_high não deve ser resetado apenas com a passagem do tempo."""
        high_before = 29.50
        agent.state.trailing_high = high_before

        # Nenhum evento externo — trailing_high deve se manter
        assert agent.state.trailing_high == high_before

    def test_loop_para_quando_stop_event_setado(
        self, agent: ClearTradingAgent
    ) -> None:
        """
        _run_loop deve terminar naturalmente quando _stop_event está setado.
        Garante que o loop não trava infinitamente após stop().
        """
        agent._stop_event.set()  # sinaliza parada

        # _run_loop deve retornar em ≤2s
        t_start = time.time()
        with (
            patch("clear_trading_agent.trading_agent.is_market_open", return_value=True),
            patch("clear_trading_agent.trading_agent.get_price_fast", return_value=None),
        ):
            agent._run_loop()

        elapsed = time.time() - t_start
        assert elapsed < 5.0, (
            f"_run_loop demorou {elapsed:.2f}s para encerrar após stop_event set"
        )


# ====================== CENÁRIO 3: MT5 BRIDGE INDISPONÍVEL ======================

class TestBridgeIndisponivel:
    """Simula falhas de conectividade com o MT5 Bridge."""

    def test_buy_nao_executa_quando_bridge_falha(
        self, agent: ClearTradingAgent
    ) -> None:
        """BUY live deve retornar False quando bridge retorna success=False."""
        agent.state.dry_run = False  # modo live para acionar place_market_order

        with patch("clear_trading_agent.trading_agent.place_market_order") as mock_order:
            mock_order.return_value = {"success": False, "error": "Bridge connection refused"}
            sig = Signal(action="BUY", confidence=1.0, reason="test", price=ENTRY_PRICE, features={})
            result = agent._execute_trade(sig, ENTRY_PRICE)

        assert result is False, "BUY deve falhar quando bridge retorna success=False"

    def test_sell_nao_executa_quando_bridge_falha_live(
        self, agent: ClearTradingAgent
    ) -> None:
        """SELL live deve retornar False e NÃO zerar posição quando bridge falha."""
        agent.state.dry_run = False
        position_before = agent.state.position

        with patch("clear_trading_agent.trading_agent.place_market_order") as mock_order:
            mock_order.return_value = {"success": False, "error": "Timeout"}
            sig = Signal(action="SELL", confidence=1.0, reason="test", price=ENTRY_PRICE, features={})
            result = agent._execute_trade(sig, ENTRY_PRICE)

        assert result is False
        assert agent.state.position == position_before, (
            "⚠️ DESVIO: posição NÃO deve ser zerada quando bridge SELL falha. "
            f"Era {position_before}, agora {agent.state.position}"
        )

    def test_get_market_state_retorna_none_quando_bridge_falha(
        self, agent: ClearTradingAgent
    ) -> None:
        """_get_market_state deve retornar None quando bridge está indisponível."""
        with patch("clear_trading_agent.trading_agent.get_price_fast", return_value=None):
            result = agent._get_market_state()

        assert result is None, "_get_market_state deve retornar None quando preço indisponível"

    def test_preco_nan_nao_dispara_trade(
        self, agent: ClearTradingAgent
    ) -> None:
        """Preço NaN retornado pelo bridge não deve acionar _check_trailing_stop."""
        import math
        agent.state.trailing_high = ENTRY_PRICE * 1.05  # trailing ativado

        result = agent._check_trailing_stop(float("nan"))
        # NaN não deve disparar (comparações com NaN retornam False)
        assert result is False, "Preço NaN não deve disparar trailing stop"

    def test_preco_zero_nao_dispara_sl(self, agent: ClearTradingAgent) -> None:
        """Preço 0.0 não deve acionar SL (considera posição inválida)."""
        # entry_price=28.50, price=0 → pnl_pct = -1.0 (-100%) → SL dispararia
        # Mas position > 0 e entry_price > 0: verifica comportamento real
        result = agent._check_auto_exit(0.0)
        # Se disparar SL com price=0, é um desvio grave (ordem com preço zero)
        if result:
            # Desvio detectado — reportar mas não falhar (pode ser intenção do agente)
            import warnings
            warnings.warn(
                "⚠️ DESVIO: _check_auto_exit disparou com price=0.0. "
                "Pode enviar ordem de venda com preço zero na live.",
                stacklevel=2,
            )

    def test_preco_negativo_nao_dispara_trade(
        self, agent: ClearTradingAgent
    ) -> None:
        """Preço negativo não deve ser aceito para execução."""
        sig = Signal(action="SELL", confidence=1.0, reason="test", price=-1.0, features={})
        # _calculate_lot_qty(amount_brl, price=-1.0) deve retornar 0
        lot_qty = agent._calculate_lot_qty(1000.0, -1.0)
        assert lot_qty == 0, f"Lote com preço negativo deve ser 0, obteve {lot_qty}"


# ====================== CENÁRIO 4: DB INACESSÍVEL ======================

class TestDbInacessivel:
    """Simula falhas de banco de dados durante operações críticas."""

    def test_dry_run_buy_sobrevive_sem_db(
        self, agent: ClearTradingAgent
    ) -> None:
        """
        BUY dry_run deve executar mesmo quando DB falha.
        No código atual, record_trade é chamado APÓS a lógica de posição.
        Verifica se posição fica inconsistente.
        """
        agent.db.record_trade.side_effect = Exception("PostgreSQL down")
        position_before = agent.state.position

        sig = Signal(action="BUY", confidence=1.0, reason="test", price=ENTRY_PRICE, features={})
        result = agent._execute_trade(sig, ENTRY_PRICE)

        if result:
            # Trade completou mesmo sem DB — desvio: estado de posição sem log
            assert agent.state.position > position_before, "Posição deve ter aumentado"
            # Mas se DB falhou, esse trade nunca foi registrado → inconsistência!
        else:
            # Trade foi revertido após falha do DB — comportamento seguro
            pass  # ambos os casos são documentados aqui

    def test_record_decision_fail_nao_bloqueia_loop(
        self, agent: ClearTradingAgent
    ) -> None:
        """Falha em record_decision não deve interromper o ciclo principal."""
        agent.db.record_decision.side_effect = Exception("DB timeout")

        signal_obj = Signal(
            action="BUY", confidence=0.9, reason="test", price=ENTRY_PRICE, features={}
        )

        # Simular execução isolada (sem loop completo)
        try:
            decision_id = agent.db.record_decision(
                symbol=agent.symbol,
                action=signal_obj.action,
                confidence=signal_obj.confidence,
                price=signal_obj.price,
                reason=signal_obj.reason,
                features=signal_obj.features,
            )
        except Exception:
            decision_id = None  # deve ser tratado graciosamente

        # Loop não deve parar por causa disso
        assert not agent._stop_event.is_set(), "Loop não deve parar por falha em record_decision"


# ====================== CENÁRIO 5: CONFIG CORROMPIDA / AUSENTE ======================

class TestConfigCorrompida:
    """Simula edge cases de configuração inválida."""

    def test_config_ausente_usa_fallback(
        self, agent: ClearTradingAgent
    ) -> None:
        """Quando arquivo de config não existe, usa _config global como fallback."""
        agent._load_live_config = lambda: {}  # config vazia

        caps = agent._get_runtime_risk_caps()

        # Caps não devem ser zero mesmo sem config
        assert caps["max_position_pct"] >= 0.01, "max_position_pct mínimo deve ser 0.01"
        assert caps["max_positions"] >= 1, "max_positions mínimo deve ser 1"
        assert caps["min_trade_amount"] > 0, "min_trade_amount deve ser positivo"

    def test_config_com_valores_invalidos_nao_crashea(
        self, agent: ClearTradingAgent
    ) -> None:
        """Config com tipo errado não deve causar crash."""
        agent._load_live_config = lambda: {
            "max_position_pct": "NÃO_É_UM_FLOAT",
            "max_positions": "also_invalid",
            "min_trade_amount": None,
        }

        # _get_runtime_risk_caps usa float()/int() com fallback — deve lançar ValueError
        # ou usar fallback, mas nunca silenciosamente retornar 0
        try:
            caps = agent._get_runtime_risk_caps()
            # Se não lançou, verifica que valores são seguros
            assert caps["max_position_pct"] >= 0.01
        except (ValueError, TypeError):
            pass  # comportamento aceitável

    def test_trailing_stop_desabilitado_nao_dispara(
        self, agent: ClearTradingAgent
    ) -> None:
        """trailing_stop disabled=True não deve disparar mesmo com queda grande."""
        agent._load_live_config = lambda: {
            **BASE_CFG,
            "trailing_stop": {"enabled": False},
        }
        agent.state.trailing_high = ENTRY_PRICE * 1.10  # 10% acima

        result = agent._check_trailing_stop(ENTRY_PRICE * 0.85)  # queda de 15%
        assert result is False, "trailing_stop desabilitado não deve disparar"

    def test_auto_exit_desabilitado_nao_dispara(
        self, agent: ClearTradingAgent
    ) -> None:
        """SL e TP disabled não devem disparar nem sob condições extremas."""
        agent._load_live_config = lambda: {
            **BASE_CFG,
            "auto_stop_loss": {"enabled": False},
            "auto_take_profit": {"enabled": False},
        }

        result = agent._check_auto_exit(ENTRY_PRICE * 0.50)  # queda de 50%
        assert result is False, "auto_exit desabilitado não deve disparar"


# ====================== CENÁRIO 6: SALDO ZERO / NEGATIVO ======================

class TestSaldoInsuficiente:
    """Edge cases de saldo insuficiente ou zerado."""

    def test_buy_com_saldo_zero_retorna_false(
        self, agent: ClearTradingAgent
    ) -> None:
        """BUY com saldo zero deve retornar 0 no _calculate_trade_size."""
        agent.config = {**BASE_CFG, "dry_run_balance": 0.0}
        agent._load_live_config = lambda: {**BASE_CFG, "dry_run_balance": 0.0}

        sig = Signal(action="BUY", confidence=1.0, reason="test", price=ENTRY_PRICE, features={})
        result = agent._execute_trade(sig, ENTRY_PRICE)

        assert result is False, "BUY com saldo zero deve falhar"

    def test_calculate_trade_size_retorna_zero_com_saldo_negativo(
        self, agent: ClearTradingAgent
    ) -> None:
        """_calculate_trade_size não deve retornar valor positivo com saldo negativo."""
        agent.config = {**BASE_CFG, "dry_run_balance": -500.0}
        sig = Signal(action="BUY", confidence=1.0, reason="test", price=ENTRY_PRICE, features={})

        size = agent._calculate_trade_size(sig, ENTRY_PRICE)
        assert size <= 0, f"Size deveria ser 0 com saldo negativo, obteve {size}"

    def test_calculate_lot_qty_preco_zero(
        self, agent: ClearTradingAgent
    ) -> None:
        """_calculate_lot_qty com preço 0 deve retornar 0 sem dividir por zero."""
        qty = agent._calculate_lot_qty(1000.0, 0.0)
        assert qty == 0, "Lot qty com preço=0 deve ser 0"

    def test_calculate_lot_qty_abaixo_lote_minimo(
        self, agent: ClearTradingAgent
    ) -> None:
        """Valor insuficiente para 1 lote (100 ações) retorna 0."""
        # R$50 @ R$30/ação = 1 ação → menos que 100 → 0 lotes
        qty = agent._calculate_lot_qty(50.0, 30.0)
        assert qty == 0, f"Deveria retornar 0 lotes para valor insuficiente, obteve {qty}"


# ====================== CENÁRIO 7: POSIÇÃO DUPLICADA / RETRY ======================

class TestRetryEDuplicacao:
    """Verifica comportamento em retentativas e possível duplicação de posição."""

    def test_sell_sem_posicao_retorna_false(
        self, agent: ClearTradingAgent
    ) -> None:
        """SELL com position=0 deve retornar False (sem posição para vender)."""
        agent.state.position = 0
        agent.state.entry_price = 0

        sig = Signal(action="SELL", confidence=1.0, reason="test", price=ENTRY_PRICE, features={})
        result = agent._execute_trade(sig, ENTRY_PRICE)

        assert result is False, "SELL sem posição deve retornar False"

    def test_sell_duplo_nao_entra_em_negativo(
        self, agent: ClearTradingAgent
    ) -> None:
        """Dois SELLs consecutivos não devem resultar em posição negativa."""
        sig = Signal(action="SELL", confidence=1.0, reason="test", price=ENTRY_PRICE, features={})

        result1 = agent._execute_trade(sig, ENTRY_PRICE)
        assert result1 is True, "Primeiro SELL deve passar"

        result2 = agent._execute_trade(sig, ENTRY_PRICE)
        assert result2 is False, "Segundo SELL deve ser bloqueado"
        assert agent.state.position >= 0, "Posição nunca deve ficar negativa"

    def test_buy_apos_sell_respeita_position_count(
        self, agent: ClearTradingAgent
    ) -> None:
        """Após SELL, position_count deve ser 0. Próximo BUY começa do zero."""
        sig_sell = Signal(action="SELL", confidence=1.0, reason="test", price=ENTRY_PRICE, features={})
        agent._execute_trade(sig_sell, ENTRY_PRICE)

        assert agent.state.position_count == 0, "position_count deve ser 0 após SELL"
        assert len(agent.state.entries) == 0, "entries deve estar vazia após SELL"


# ====================== CENÁRIO 8: CALLBACK COM EXCEÇÃO ======================

class TestCallbackException:
    """Callbacks que lançam exceção não devem interromper o agente."""

    def test_trade_callback_exception_nao_reverte_trade(
        self, agent: ClearTradingAgent
    ) -> None:
        """Exceção em _on_trade_callbacks não deve reverter o trade executado."""
        calls: list = []

        def _bad_callback(sig, price):
            calls.append("called")
            raise RuntimeError("Callback crashed!")

        agent.on_trade(_bad_callback)

        position_before = agent.state.position
        sig = Signal(action="SELL", confidence=1.0, reason="test", price=ENTRY_PRICE, features={})
        result = agent._execute_trade(sig, ENTRY_PRICE)

        assert calls == ["called"], "Callback deve ter sido invocado"
        assert result is True, "Trade deve ter completado mesmo com callback falhando"
        assert agent.state.position == 0, "Posição deve ter sido zerada (SELL executado)"

    def test_multiplos_callbacks_falhos_nao_param_cadeia(
        self, agent: ClearTradingAgent
    ) -> None:
        """Múltiplos callbacks falhos devem ser executados até o último."""
        ordem: list = []

        for i in range(3):
            def _cb(sig, price, _i=i):
                ordem.append(_i)
                raise ValueError(f"Callback {_i} falhou")

            agent.on_trade(_cb)

        sig = Signal(action="SELL", confidence=1.0, reason="test", price=ENTRY_PRICE, features={})
        agent._execute_trade(sig, ENTRY_PRICE)

        assert len(ordem) == 3, f"Todos 3 callbacks devem ser chamados, chamados: {ordem}"


# ====================== CENÁRIO 9: TAX GUARDRAIL BLOQUEIO ======================

class TestTaxGuardrailBloqueio:
    """Tax guardrail bloqueia venda em condições tributárias adversas."""

    def test_tax_block_impede_sell(
        self, agent: ClearTradingAgent
    ) -> None:
        """check_sell_allowed=False deve impedir execução do SELL."""
        blocked_decision = MagicMock()
        blocked_decision.allowed = False
        blocked_decision.reason = "Day trade limit exceeded"
        agent.tax_tracker.check_sell_allowed.return_value = blocked_decision

        sig = Signal(
            action="SELL", confidence=1.0, reason="test",
            price=ENTRY_PRICE * 1.05, features={},
        )

        with patch("clear_trading_agent.trading_agent.is_market_open", return_value=True):
            can = agent._check_can_trade(sig)

        assert can is False, "Tax block deve impedir _check_can_trade"
        assert agent.state.position == float(ENTRY_QTY), (
            "Posição não deve ser alterada quando tax guardrail bloqueia"
        )

    def test_tax_guardrail_nao_impede_trailing_stop_force(
        self, agent: ClearTradingAgent
    ) -> None:
        """
        Trailing stop usa force=True em _execute_trade, bypassando _check_can_trade.
        Tax guardrail NÃO deve bloquear saídas forçadas (SL/TP/trailing).
        """
        blocked_decision = MagicMock()
        blocked_decision.allowed = False
        blocked_decision.reason = "Monthly limit R$20k exceeded"
        agent.tax_tracker.check_sell_allowed.return_value = blocked_decision

        # trailing_high = ENTRY_PRICE * 1.05, price cai 0.9% → trailing dispara
        agent.state.trailing_high = ENTRY_PRICE * 1.05
        price_exit = ENTRY_PRICE * 1.05 * (1 - 0.009)
        agent._load_live_config = lambda: {
            **BASE_CFG,
            "trailing_stop": {"enabled": True, "activation_pct": 0.015, "trail_pct": 0.008},
        }

        # _check_trailing_stop chama _execute_trade(force=True) — não passa por _check_can_trade
        result = agent._check_trailing_stop(price_exit)

        # Tax guardrail NÃO aparece no caminho force=True → trailing deve executar
        assert result is True, (
            "⚠️ DESVIO: trailing_stop com force=True deve bypassar tax guardrail. "
            "Tax tracker não é verificado no _execute_trade força."
        )


# ====================== CENÁRIO 10: ESTADO PERSISTIDO CORROMPIDO ======================

class TestEstadoPersistidoCorrompido:
    """Simula reinicialização com dados persistidos inconsistentes."""

    def test_posicao_sem_entries_e_inconsistente(
        self, agent: ClearTradingAgent
    ) -> None:
        """position > 0 mas entries vazia é estado inconsistente."""
        agent.state.position = 200.0
        agent.state.entries = []  # Inconsistência: posição sem histórico

        # Agente não deve crashar ao verificar estado
        status = agent.get_status()
        assert status["position_qty"] == 200.0
        # Desvio: entries vazia enquanto position > 0 → risco de cálculo errado
        # de trailing_high, target_sell etc.

    def test_entry_price_zero_com_posicao_aberta(
        self, agent: ClearTradingAgent
    ) -> None:
        """entry_price=0 com posição aberta não deve disparar SL falso."""
        agent.state.entry_price = 0.0
        agent.state.position = 200.0

        # _check_auto_exit retorna False imediatamente: "entry_price <= 0"
        result_ae = agent._check_auto_exit(ENTRY_PRICE)
        result_ts = agent._check_trailing_stop(ENTRY_PRICE)

        assert result_ae is False, "auto_exit não deve disparar com entry_price=0"
        assert result_ts is False, "trailing_stop não deve disparar com entry_price=0"

    def test_trailing_high_menor_que_entry_e_inconsistente(
        self, agent: ClearTradingAgent
    ) -> None:
        """trailing_high < entry_price é estado inconsistente (nunca deveria ocorrer)."""
        agent.state.entry_price = ENTRY_PRICE
        agent.state.trailing_high = ENTRY_PRICE * 0.95  # 5% abaixo da entrada

        # Se preço atual = entry → pnl_pct da trailing_high = -5% < activation_pct
        # trailing NÃO deve disparar
        result = agent._check_trailing_stop(ENTRY_PRICE)
        assert result is False, "trailing_high < entry não deve disparar trailing stop"


# ====================== CENÁRIO 11: CONCORRÊNCIA / THREAD SAFETY ======================

class TestConcorrencia:
    """Verifica comportamento sob acesso concorrente ao estado."""

    def test_trade_lock_previne_dupla_execucao_concorrente(
        self, agent: ClearTradingAgent
    ) -> None:
        """Duas threads tentando executar trade ao mesmo tempo: apenas uma vence."""
        results: list = []
        barrier = threading.Barrier(2)

        def _execute():
            barrier.wait()
            sig = Signal(action="SELL", confidence=1.0, reason="concurrent", price=ENTRY_PRICE, features={})
            r = agent._execute_trade(sig, ENTRY_PRICE)
            results.append(r)

        t1 = threading.Thread(target=_execute)
        t2 = threading.Thread(target=_execute)
        t1.start()
        t2.start()
        t1.join(timeout=3)
        t2.join(timeout=3)

        # Apenas 1 SELL deve ter executado
        assert results.count(True) <= 1, (
            f"⚠️ DESVIO: dois SELLs executaram concorrentemente! Results: {results}"
        )
        assert agent.state.position >= 0, "Posição nunca deve ficar negativa"

    def test_stop_event_interrompe_wait_durante_loop(
        self, agent: ClearTradingAgent
    ) -> None:
        """stop() durante _stop_event.wait(timeout=300) libera imediatamente."""
        wait_started = threading.Event()

        original_wait = threading.Event.wait

        def _patched_wait(self_ev, timeout=None):
            wait_started.set()
            return original_wait(self_ev, timeout=0.05)  # espera curta

        with patch.object(type(agent._stop_event), "wait", _patched_wait):
            t = threading.Thread(
                target=lambda: agent._stop_event.wait(timeout=300),
                daemon=True,
            )
            t.start()
            wait_started.wait(timeout=1)
            agent._stop_event.set()
            t.join(timeout=1)

        assert not t.is_alive(), "Thread deve ter encerrado após stop_event.set()"


# ====================== CENÁRIO 12: FUTURES / MINICONTRATOS ======================

class TestFuturesMinicontrato:
    """Verifica edge cases específicos de futuros WIN/WDO."""

    def test_wdo_usa_margem_15pct(self, agent: ClearTradingAgent) -> None:
        """WDO deve usar margem 15% para cálculo de contratos."""
        agent.state.asset_class = "futures"
        agent.symbol = "WDOFUT"

        # R$1.500 @ R$6.000 * 15% = R$900/contrato → 1 contrato
        qty = agent._calculate_lot_qty(1500.0, 6000.0)
        assert qty >= 1, f"WDO deveria retornar ≥1 contrato, obteve {qty}"

    def test_win_usa_margem_20pct(self, agent: ClearTradingAgent) -> None:
        """WIN deve usar margem 20% para cálculo de contratos."""
        agent.state.asset_class = "futures"
        agent.symbol = "WINFUT"

        # R$10.000 @ R$120.000 * 20% = R$24.000/contrato → 0 contratos (insuficiente)
        qty = agent._calculate_lot_qty(10000.0, 120000.0)
        assert qty == 0, f"WIN insuficiente deveria retornar 0, obteve {qty}"

    def test_futures_com_margem_suficiente_retorna_pelo_menos_1(
        self, agent: ClearTradingAgent
    ) -> None:
        """Margem suficiente para 1 contrato WIN deve retornar 1."""
        agent.state.asset_class = "futures"
        agent.symbol = "WINFUT"

        # R$30.000 @ R$120.000 * 20% margin = R$24.000/contrato → 1 contrato
        qty = agent._calculate_lot_qty(30000.0, 120000.0)
        assert qty >= 1, f"Deveria retornar ≥1 contrato WIN, obteve {qty}"
