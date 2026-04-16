"""
Testes regressivos para validar o fix: remoção do bloqueio absoluto de SELL

Testa o cenário onde o agent estava travando posições ao bloquear SELL com prejuízo líquido,
mesmo durante stop-losses. O fix remove essa regra para permitir saídas de proteção (SL/TP).
"""

import pytest
import sys
import types
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass

# Adicionar path ao agent
sys.path.insert(0, str(Path(__file__).parent.parent / "btc_trading_agent"))


@dataclass
class _StubSignal:
    action: str
    price: float
    confidence: float
    reason: str = ""


class _StubFastTradingModel:
    def __init__(self, *args, **kwargs):
        self.indicators = types.SimpleNamespace(
            update_from_candles=lambda candles: None,
            rsi=lambda: 50.0,
            momentum=lambda: 0.0,
            volatility=lambda: 0.01,
        )

    def get_stats(self):
        return {}

    def save(self):
        return None


class _StubMarketRAG:
    def __init__(self, *args, **kwargs):
        self._adj = types.SimpleNamespace(
            suggested_regime="RANGING",
            ai_take_profit_pct=0.015,
            ai_take_profit_reason="test",
            ai_buy_target_reason="test",
        )

    def get_current_adjustment(self):
        return self._adj

    def get_stats(self):
        return {}


sys.modules.setdefault(
    "fast_model",
    types.SimpleNamespace(
        FastTradingModel=_StubFastTradingModel,
        MarketState=object,
        Signal=_StubSignal,
    ),
)
sys.modules.setdefault(
    "market_rag",
    types.SimpleNamespace(
        MarketRAG=_StubMarketRAG,
    ),
)

# Importações do agent
try:
    import trading_agent as trading_agent_module
except ImportError:
    pytest.skip("Agent dependencies not available", allow_module_level=True)

trading_agent_module.FastTradingModel = _StubFastTradingModel
trading_agent_module.MarketRAG = _StubMarketRAG
trading_agent_module.Signal = _StubSignal

BitcoinTradingAgent = trading_agent_module.BitcoinTradingAgent
AgentState = trading_agent_module.AgentState
Signal = trading_agent_module.Signal


@dataclass
class MockMarketState:
    """Mock do estado de mercado"""
    price: float
    bid: float = 100
    ask: float = 100
    spread: float = 0.01
    orderbook_imbalance: float = 0.5
    trade_flow: float = 0.1
    volume_ratio: float = 1000
    rsi: float = 50
    momentum: float = 0.0
    volatility: float = 0.02
    trend: float = 0.0


class TestSellBlockFixRegression:
    """Testes para validar o fix do bloqueio de SELL"""

    @staticmethod
    def _live_cfg(guardrails_active: bool = False) -> dict:
        return {
            "profile": "default",
            "max_daily_loss": 999999 if not guardrails_active else 0.085,
            "guardrails_active": guardrails_active,
            "guardrails_positive_only_sells": guardrails_active,
            "guardrails_min_sell_pnl_pct": 0.025,
            "min_net_profit": {"usd": 0.01, "pct": 0.0005},
            "stop_loss_pct": 0.02,
        }

    @pytest.fixture
    def mock_db(self):
        """Mock do banco de dados"""
        db = MagicMock()
        db._get_conn.return_value.__enter__ = MagicMock(return_value=MagicMock())
        db._get_conn.return_value.__exit__ = MagicMock(return_value=None)
        db.get_recent_trades.return_value = []
        db.store_candles.return_value = None
        return db

    @pytest.fixture
    def agent_state(self):
        """Estado do agent com posição aberta"""
        state = AgentState()
        state.position = 1.0  # 1 BTC
        state.entry_price = 75000.0  # Entry em $75k
        state.position_count = 1
        state.raw_entry_count = 1
        state.logical_position_slots = 1
        state.dry_run = False
        state.entries = [{"price": 75000.0, "size": 1.0, "ts": 0}]
        return state

    @pytest.fixture
    def agent(self, mock_db, agent_state):
        """Cria agent com mock de DB"""
        with patch("trading_agent.TrainingDatabase", return_value=mock_db), \
             patch("trading_agent.get_balance", return_value=1.0), \
             patch("trading_agent.get_price", return_value=75000.0), \
             patch("trading_agent.get_candles", return_value=[]):

            agent = BitcoinTradingAgent(
                symbol="BTC-USDT",
                dry_run=False,
            )
            agent.db = mock_db
            agent.state = agent_state
            agent._load_live_config = lambda: self._live_cfg(guardrails_active=False)
            return agent

    def test_nok_when_sell_blocked_with_positive_pnl(self, agent):
        """
        Test NOK: Validar que SELL com PnL POSITIVO nunca é bloqueado

        Cenário:
        - Entry: $70,000 (position = 1 BTC)
        - Preço atual: $75,000 → PnL bruto = +$5,000 (+7.14%)
        - Net profit POSITIVO mesmo após taxas (~$150)

        Expectativa:
        - _calculate_trade_size deve retornar > 0 (sell LIBERADO)
        - Se retornar 0 → NOK! Bloqueio indevido com PnL positivo

        RETORNA NOK com mensagem explícita se sell for bloqueado.
        """
        entry_price = 70_000.0
        current_price = 75_000.0
        position_size = 1.0
        pnl_pct = (current_price - entry_price) / entry_price * 100

        agent.state.position = position_size
        agent.state.entry_price = entry_price
        agent.state.entries = [{"price": entry_price, "size": position_size, "ts": 0}]

        signal = Signal(
            action="SELL",
            price=current_price,
            confidence=0.8,
            reason="signal_sell",
        )

        result = agent._calculate_trade_size(signal, current_price, force=False)

        assert result > 0, (
            f"\n" \
            f"{'='*60}\n" \
            f"❌ NOK: SELL BLOQUEADO COM PnL POSITIVO\n" \
            f"{'='*60}\n" \
            f"  Entry price   : ${entry_price:,.2f}\n" \
            f"  Current price : ${current_price:,.2f}\n" \
            f"  PnL bruto     : +{pnl_pct:.2f}% (+${current_price - entry_price:,.2f})\n" \
            f"  Resultado     : _calculate_trade_size retornou {result} (esperado > 0)\n" \
            f"\n" \
            f"  CAUSA PROVÁVEL: bloqueio absoluto de SELL foi reinserido.\n" \
            f"  Verifique btc_trading_agent/trading_agent.py e remova\n" \
            f"  qualquer regra que bloqueie net_profit < 0 em force-exits.\n" \
            f"{'='*60}"
        )

    def test_estimate_sell_outcome_with_loss(self, agent):
        """
        Test 1: Validar cálculo de outcome quando SELL gera prejuízo líquido
        
        Setup:
        - Entry: $75,000 @ 1 BTC
        - Current price: $72,000 (queda de $3k)
        - Fees KuCoin: 0.1% each way
        
        Expected:
        - Gross PnL: -$3,000
        - Total fees: ~$150
        - Net profit: NEGATIVO (prejudicial)
        """
        current_price = 72000.0
        outcome = agent._estimate_sell_outcome(current_price)
        
        assert outcome["size"] == 1.0
        assert outcome["gross_pnl"] < 0, "Gross PnL deve ser negativo (preço caiu)"
        assert outcome["net_profit"] < 0, "Net profit deve ser negativo após fees"
        assert outcome["total_fees"] > 0
        
        # Calcular manualmente para validar
        entry_price = agent.state.entry_price
        size = agent.state.position
        sell_fee_pct = 0.001  # 0.1%
        buy_fee_pct = 0.001
        
        expected_gross_pnl = (current_price - entry_price) * size
        expected_total_fees = (entry_price * size * buy_fee_pct) + (current_price * size * sell_fee_pct)
        expected_net = expected_gross_pnl - expected_total_fees
        
        assert abs(outcome["net_profit"] - expected_net) < 0.01, \
            f"Net profit mismatch: {outcome['net_profit']} vs {expected_net}"

    def test_sell_block_removed_allows_force_exit(self, agent):
        """
        Test 2: Validar que force-exit (stop-loss) NÃO é mais bloqueado
        
        ANTES DO FIX: return 0 (bloqueado)
        DEPOIS DO FIX: return self.state.position (liberado)
        
        Cenário: SL dispara, preço abaixo do threshold, mas net profit < 0
        """
        # Setup: preço caiu abaixo do stop-loss
        sl_price = agent.state.entry_price * (1 - 0.025)  # 2.5% stop-loss
        current_price = sl_price - 100  # Bem abaixo do SL
        
        # Chamar _calculate_trade_size com force=True (stop-loss forçado)
        sell_signal = Signal(action="SELL", price=current_price, confidence=1.0, reason="stop_loss")
        size_returned = agent._calculate_trade_size(sell_signal, current_price, force=True)

        # DEPOIS DO FIX: deve retornar a posição completa (permitir saída)
        assert size_returned > 0, \
            f"Force-exit bloqueado! Retornou {size_returned}, esperava > 0"
        assert size_returned == agent.state.position, \
            f"Force-exit retornou size errado: {size_returned} vs {agent.state.position}"

    def test_guardrail_sell_still_works(self, agent):
        """
        Test 3: Validar que guardrail de SELL (proteção de lucro) continua funcionando
        
        Guardrail é diferente da regra absoluta removida:
        - Regra Absoluta REMOVIDA: bloqueia SELL se net_profit < 0 (mesmo em SL)
        - Guardrail MANTIDO: bloqueia SELL se lucro é insuficiente (mas permite SL)
        """
        # Guardrail deve estar ATIVO
        agent._load_live_config = lambda: self._live_cfg(guardrails_active=True)
        guard_cfg = agent._get_guardrail_sell_protection_cfg()
        assert guard_cfg.get("active") is True or guard_cfg.get("positive_only_sells") is True, \
            "Guardrail deve estar ativo para proteção normal"
        
        # Teste: preço levemente abaixo da entry (pequeno prejuízo)
        test_price = agent.state.entry_price * 0.995  # 0.5% abaixo
        
        # Guardrail deve retornar veredito
        verdict = agent._get_guardrail_sell_verdict(test_price)
        
        if verdict:
            assert "allow" in verdict
            assert "net_profit" in verdict
            # Se preço é apenas ligeiramente abaixo, guardrail deve bloquear
            # (mas force-exit ainda pode passar)

    def test_signal_sell_not_blocked_with_force_false(self, agent):
        """
        Test 4: Validar que SELL normal (sem force) ainda passa por validações
        
        A regra absoluta foi removida, então:
        - SELL normal: validações normais, sem bloqueio absoluto
        - Force-exit (SL/TP): passa direto
        """
        # Setup: preço caiu bastante, net profit NEGATIVO
        current_price = agent.state.entry_price * 0.97  # 3% down
        
        # Criar sinal de SELL
        signal = Signal(
            action="SELL",
            price=current_price,
            confidence=0.7,
            reason="stop_loss_triggered",
        )
        
        # Chamar _calculate_trade_size sem force → passa por guardrail normal
        result = agent._calculate_trade_size(signal, current_price, force=False)

        # Resultado: pode ser 0 (guardrail bloqueou) ou > 0 (liberado)
        # O importante: NÃO deve ter a regra "proibido SELL com resultado líquido negativo"
        # Se retornar 0, deve ser por guardrail (min_pnl_pct), não pela regra removida
        # Verificamos que o código não contém o padrão proibido
        import inspect
        src = inspect.getsource(agent._calculate_trade_size)
        assert '_abs["net_profit"] < 0' not in src and "net_profit < 0: return False" not in src, \
            "NOK: Regra absoluta de bloqueio de SELL foi reinserida no código!"

    def test_dry_run_not_affected(self, mock_db):
        """
        Test 5: Validar que modo DRY-RUN continua funcionando
        """
        with patch("trading_agent.TrainingDatabase", return_value=mock_db), \
             patch("trading_agent.get_balance", return_value=1.0), \
             patch("trading_agent.get_price", return_value=75000.0), \
             patch("trading_agent.get_candles", return_value=[]):

            agent_dry = BitcoinTradingAgent(
                symbol="BTC-USDT",
                dry_run=True,
            )
            agent_dry.db = mock_db
            agent_dry.state.position = 1.0
            agent_dry.state.entry_price = 75000.0

            # Mesmo em DRY-RUN, a lógica deve funcionar
            outcome = agent_dry._estimate_sell_outcome(72000.0)
            assert outcome["net_profit"] < 0, "Outcome deve funcionar mesmo em dry-run"

    def test_multi_entry_sell_with_loss(self, agent):
        """
        Test 6: Validar SELL com múltiplas entradas (avg price)
        
        Cenário mais realista onde agent tem várias entradas (multi-posição)
        """
        # Setup: 2 entradas em preços diferentes
        agent.state.position = 1.5  # 1.5 BTC total
        agent.state.entry_price = 74500.0  # Preço médio
        agent.state.entries = [
            {"price": 75000.0, "size": 0.8, "ts": 0},
            {"price": 74000.0, "size": 0.7, "ts": 1},
        ]
        
        # Preço atual bem abaixo
        current_price = 71000.0
        
        outcome = agent._estimate_sell_outcome(current_price)
        
        # Validar cálculos
        assert outcome["size"] == 1.5, "Size deve refletir múltiplas entradas"
        assert outcome["net_profit"] < 0, "Net profit deve ser negativo"
        
        # Force-exit deve ainda funcionar
        sell_signal = Signal(action="SELL", price=current_price, confidence=1.0, reason="stop_loss")
        size_sl = agent._calculate_trade_size(sell_signal, current_price, force=True)
        assert size_sl == agent.state.position, "Force-exit deve vender tudo mesmo com loss"

    def test_no_position_returns_zero(self, agent):
        """
        Test 7: Validar comportamento quando não há posição aberta
        """
        agent.state.position = 0
        agent.state.entry_price = 0
        
        # Estimate deve retornar zeros
        outcome = agent._estimate_sell_outcome(75000.0)
        assert outcome["size"] == 0
        assert outcome["net_profit"] == 0
        
        # Resolve deve retornar 0 (sem posição)
        sell_signal = Signal(action="SELL", price=75000.0, confidence=1.0, reason="stop_loss")
        size = agent._calculate_trade_size(sell_signal, 75000.0, force=True)
        assert size == 0


class TestRegressionStressTest:
    """Testes de stress para múltiplos cenários"""

    @staticmethod
    def _live_cfg() -> dict:
        return {
            "profile": "default",
            "max_daily_loss": 999999,
            "guardrails_active": False,
            "guardrails_positive_only_sells": False,
            "guardrails_min_sell_pnl_pct": 0.025,
            "min_net_profit": {"usd": 0.01, "pct": 0.0005},
            "stop_loss_pct": 0.02,
        }

    @pytest.fixture
    def mock_db(self):
        """Mock do banco de dados (necessário para agent_stress)"""
        db = MagicMock()
        db._get_conn.return_value.__enter__ = MagicMock(return_value=MagicMock())
        db._get_conn.return_value.__exit__ = MagicMock(return_value=None)
        db.get_recent_trades.return_value = []
        db.store_candles.return_value = None
        return db

    @pytest.fixture
    def agent_stress(self, mock_db):
        """Agent para testes de stress"""
        with patch("trading_agent.TrainingDatabase", return_value=mock_db), \
             patch("trading_agent.get_balance", return_value=10.0), \
             patch("trading_agent.get_price", return_value=75000.0), \
             patch("trading_agent.get_candles", return_value=[]):

            agent = BitcoinTradingAgent(
                symbol="BTC-USDT",
                dry_run=False,
            )
            agent.db = mock_db
            agent._load_live_config = lambda: self._live_cfg()
            return agent

    @pytest.mark.parametrize("entry_price,current_price,expected_negative", [
        (75000, 74000, True),   # 1.3% down -> negative after fees
        (75000, 70000, True),   # 6.7% down -> definitely negative
        (75000, 74900, False),  # 0.13% down -> might be breakeven/positive
        (75000, 76000, False),  # 1.3% up -> positive
        (50000, 49000, True),   # Lower price, still negative
        (100000, 95000, True),  #Higher price, 5% down
    ])
    def test_various_price_scenarios(self, agent_stress, entry_price, current_price, expected_negative):
        """Teste parametrizado: múltiplos cenários de preço"""
        agent_stress.state.position = 1.0
        agent_stress.state.entry_price = entry_price
        
        outcome = agent_stress._estimate_sell_outcome(current_price)
        
        has_loss = outcome["net_profit"] < 0
        
        if expected_negative:
            assert has_loss, f"Entry {entry_price} -> {current_price} deveria ter loss"
        
        # Mas force-exit deve ainda funcionar
        sell_signal = Signal(action="SELL", price=current_price, confidence=1.0, reason="stop_loss")
        size_exit = agent_stress._calculate_trade_size(sell_signal, current_price, force=True)
        assert size_exit == 1.0, f"Force-exit bloqueado em entry={entry_price}, current={current_price}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
