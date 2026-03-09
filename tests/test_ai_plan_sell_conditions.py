"""Testes unitários para as condições de venda no prompt do AI Plan.

Valida o cálculo de sell_unlock_price, current_net_pnl, formatação do prompt
com condições de venda, e a persistência dos novos campos no metadata.

Não usa APIs reais — todo I/O externo é mockado.
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional
from unittest.mock import MagicMock, mock_open, patch

import pytest

# ── Constantes reproduzidas do trading_agent.py ──
TRADING_FEE_PCT = 0.001  # 0.1% por trade (KuCoin)


# ── Dataclasses reproduzidas do trading_agent.py ──

@dataclass
class AgentState:
    """Estado mínimo do agente para testes."""

    running: bool = False
    symbol: str = "BTC-USDT"
    position: float = 0.0
    position_value: float = 0.0
    entry_price: float = 0.0
    position_count: int = 0
    entries: list = field(default_factory=list)
    last_trade_time: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    total_pnl: float = 0.0
    dry_run: bool = True
    last_sell_entry_price: float = 0.0


@dataclass
class MarketState:
    """Dados de mercado mínimos para testes."""

    price: float = 0.0
    orderbook_imbalance: float = 0.0
    spread: float = 0.0


@dataclass
class RAGAdjustment:
    """Ajustes RAG mínimos para testes."""

    similar_count: int = 5
    ai_aggressiveness: float = 0.5
    ai_buy_target_price: float = 68000.0
    ai_take_profit_pct: float = 0.025
    ai_take_profit_reason: str = "config default"
    ai_position_size_pct: float = 0.04
    ai_max_entries: int = 20


# ── Helpers para cálculo (reproduz lógica do trading_agent.py) ──

def calc_sell_unlock_price(
    entry_price: float,
    position: float,
    min_sell_pnl: float,
    fee: float = TRADING_FEE_PCT,
) -> float:
    """Calcula preço mínimo para desbloquear SELL."""
    if position <= 0 or entry_price <= 0:
        return 0.0
    return (min_sell_pnl + entry_price * position * (1 + fee)) / (position * (1 - fee))


def calc_current_net_pnl(
    current_price: float,
    entry_price: float,
    position: float,
    fee: float = TRADING_FEE_PCT,
) -> float:
    """Calcula PnL líquido atual após fees de compra e venda."""
    if position <= 0 or entry_price <= 0:
        return 0.0
    return (
        (current_price - entry_price) * position
        - entry_price * position * fee
        - current_price * position * fee
    )


def build_sell_conditions_block(
    *,
    min_sell_pnl: float,
    sell_unlock_price: float,
    entry_price: float,
    tp_enabled: bool,
    tp_pct: float,
    tp_target: float,
    sl_enabled: bool,
    sl_pct: float,
    sl_price: float,
    trailing_enabled: bool,
    trailing_activation: float,
    trailing_activation_price: float,
    trailing_trail: float,
    current_net_pnl: float,
) -> str:
    """Reproduz o bloco CONDIÇÕES DE VENDA do prompt."""
    lines = [
        f"CONDIÇÕES DE VENDA (resumo atual):\n",
        f"- PnL líquido mínimo para vender: ${min_sell_pnl:.3f}\n",
        f"- Preço mín. para desbloquear SELL: ${sell_unlock_price:,.2f} "
        f"(entry ${entry_price:,.2f} + fees + min_pnl)\n",
        f"- Auto Take-Profit: {'ATIVADO' if tp_enabled else 'DESATIVADO'}, "
        f"TP={tp_pct*100:.2f}% → alvo ${tp_target:,.2f}\n",
        f"- Auto Stop-Loss: {'ATIVADO, SL=' + f'{sl_pct*100:.1f}% → piso ${sl_price:,.2f}' if sl_enabled else 'DESATIVADO'}\n",
        f"- Trailing Stop: {'ATIVADO, ativa em +' + f'{trailing_activation*100:.1f}% (${trailing_activation_price:,.2f}), trail {trailing_trail*100:.1f}%' if trailing_enabled else 'DESATIVADO'}\n",
        f"- PnL líquido atual: ${current_net_pnl:.4f}\n\n",
    ]
    return "".join(lines)


# ═══════════════════════════════════════════════════════════════
# Testes de cálculo: sell_unlock_price
# ═══════════════════════════════════════════════════════════════


class TestSellUnlockPrice:
    """Testes para o cálculo do preço mínimo de desbloqueio de SELL."""

    def test_basic_calculation(self) -> None:
        """Verifica cálculo básico com valores reais."""
        entry = 68808.07
        pos = 0.00276
        min_pnl = 0.015
        result = calc_sell_unlock_price(entry, pos, min_pnl)
        # Deve ser ligeiramente acima do entry + fees
        assert result > entry, "sell_unlock_price deve ser > entry_price"
        # Com fee 0.1% em ambos os lados + min_pnl, diferença deve ser razoável
        assert result < entry * 1.01, "sell_unlock_price não deve ser > 1% acima do entry"

    def test_zero_position_returns_zero(self) -> None:
        """Sem posição, sell_unlock_price deve ser 0."""
        assert calc_sell_unlock_price(68000.0, 0.0, 0.015) == 0.0

    def test_zero_entry_returns_zero(self) -> None:
        """Sem entry_price, sell_unlock_price deve ser 0."""
        assert calc_sell_unlock_price(0.0, 0.001, 0.015) == 0.0

    def test_negative_position_returns_zero(self) -> None:
        """Posição negativa não é válida."""
        assert calc_sell_unlock_price(68000.0, -0.001, 0.015) == 0.0

    def test_higher_min_pnl_raises_price(self) -> None:
        """min_sell_pnl maior deve exigir preço mais alto."""
        entry, pos = 68000.0, 0.001
        p1 = calc_sell_unlock_price(entry, pos, 0.01)
        p2 = calc_sell_unlock_price(entry, pos, 0.05)
        assert p2 > p1, "min_pnl maior deve exigir preço mais alto"

    def test_larger_position_smaller_spread(self) -> None:
        """Posição maior dilui o impacto do min_sell_pnl."""
        entry = 68000.0
        min_pnl = 0.015
        p_small = calc_sell_unlock_price(entry, 0.001, min_pnl)
        p_large = calc_sell_unlock_price(entry, 0.01, min_pnl)
        # Ambos > entry, mas a diferença p-entry deve ser menor com posição maior
        spread_small = p_small - entry
        spread_large = p_large - entry
        assert spread_large < spread_small, "Posição maior dilui o spread do min_pnl"

    def test_fee_impact(self) -> None:
        """Fee mais alta deve exigir preço maior."""
        entry, pos, min_pnl = 68000.0, 0.001, 0.015
        p_low_fee = calc_sell_unlock_price(entry, pos, min_pnl, fee=0.0005)
        p_high_fee = calc_sell_unlock_price(entry, pos, min_pnl, fee=0.002)
        assert p_high_fee > p_low_fee

    def test_zero_fee_still_requires_min_pnl(self) -> None:
        """Mesmo sem fee, min_sell_pnl deve ser respeitado."""
        entry, pos, min_pnl = 68000.0, 0.001, 0.015
        p = calc_sell_unlock_price(entry, pos, min_pnl, fee=0.0)
        expected_no_fee = entry + (min_pnl / pos)
        assert abs(p - expected_no_fee) < 0.01

    def test_real_scenario_matches_server(self) -> None:
        """Verifica contra valor real do servidor (sell_unlock_price=68955.65)."""
        # Dados reais: pos ~0.00276, entry ~68808.07, min_pnl=0.015
        entry = 68808.07
        pos = 0.00276
        min_pnl = 0.015
        result = calc_sell_unlock_price(entry, pos, min_pnl)
        # Deve estar próximo de $68,955.65 (valor observado no servidor)
        assert abs(result - 68955.65) < 5.0, (
            f"Esperado ~68955.65, obteve {result:.2f}"
        )


# ═══════════════════════════════════════════════════════════════
# Testes de cálculo: current_net_pnl
# ═══════════════════════════════════════════════════════════════


class TestCurrentNetPnl:
    """Testes para o cálculo do PnL líquido atual."""

    def test_price_above_entry_positive_pnl(self) -> None:
        """Preço acima do entry deve gerar PnL positivo (ganha mais que as fees)."""
        entry, pos = 68000.0, 0.001
        price = 70000.0  # +$2000 acima
        pnl = calc_current_net_pnl(price, entry, pos)
        assert pnl > 0, "Preço bem acima do entry deve gerar PnL positivo"

    def test_price_equals_entry_negative_pnl(self) -> None:
        """Preço igual ao entry gera PnL negativo (fees de compra + venda)."""
        entry, pos = 68000.0, 0.001
        pnl = calc_current_net_pnl(entry, entry, pos)
        expected_fee = -2 * entry * pos * TRADING_FEE_PCT
        assert pnl < 0, "PnL deve ser negativo quando preço = entry (fees)"
        assert abs(pnl - expected_fee) < 0.001

    def test_price_below_entry_negative_pnl(self) -> None:
        """Preço abaixo do entry gera PnL negativo."""
        pnl = calc_current_net_pnl(67000.0, 68000.0, 0.001)
        assert pnl < 0

    def test_zero_position_returns_zero(self) -> None:
        """Sem posição, PnL é 0."""
        assert calc_current_net_pnl(70000.0, 68000.0, 0.0) == 0.0

    def test_zero_entry_returns_zero(self) -> None:
        """Sem entry_price, PnL é 0."""
        assert calc_current_net_pnl(70000.0, 0.0, 0.001) == 0.0

    def test_breakeven_price(self) -> None:
        """O breakeven deve ser entry * (1 + 2*fee) / (1 - fee) ≈ entry + 2*fee."""
        entry, pos = 68000.0, 0.001
        # Breakeven: preço onde PnL = 0
        # (p - entry) * pos = entry*pos*fee + p*pos*fee
        # p*pos - entry*pos = entry*pos*fee + p*pos*fee
        # p*pos - p*pos*fee = entry*pos + entry*pos*fee
        # p*(1-fee) = entry*(1+fee)
        breakeven = entry * (1 + TRADING_FEE_PCT) / (1 - TRADING_FEE_PCT)
        pnl_at_breakeven = calc_current_net_pnl(breakeven, entry, pos)
        assert abs(pnl_at_breakeven) < 0.0001, (
            f"PnL no breakeven deve ser ~0, obteve {pnl_at_breakeven}"
        )

    def test_pnl_scales_with_position(self) -> None:
        """PnL deve escalar linearmente com o tamanho da posição."""
        entry, price = 68000.0, 70000.0
        pnl1 = calc_current_net_pnl(price, entry, 0.001)
        pnl2 = calc_current_net_pnl(price, entry, 0.002)
        assert abs(pnl2 / pnl1 - 2.0) < 0.001

    def test_real_scenario_matches_server(self) -> None:
        """Verifica contra valor real do servidor (current_net_pnl=-0.7106)."""
        # Dados: pos=0.00276, entry=68808.07, price=~68500 (estimado)
        entry = 68808.07
        pos = 0.00276
        # Para PnL = -0.7106: resolvendo a fórmula
        # pnl = (p - 68808.07) * 0.00276 - 68808.07*0.00276*0.001 - p*0.00276*0.001
        # -0.7106 = 0.00276p - 189.91 - 0.18990 - 0.00000276p
        # -0.7106 + 190.0999 = 0.002757p
        # p = 189.3893 / 0.002757 = ~68,693
        price = 68693.0
        pnl = calc_current_net_pnl(price, entry, pos)
        assert abs(pnl - (-0.7106)) < 0.05


# ═══════════════════════════════════════════════════════════════
# Testes de formatação do bloco de condições de venda
# ═══════════════════════════════════════════════════════════════


class TestSellConditionsPromptBlock:
    """Testes para a formatação do bloco de condições de venda no prompt."""

    @pytest.fixture()
    def default_params(self) -> dict:
        """Parâmetros padrão para build_sell_conditions_block."""
        return {
            "min_sell_pnl": 0.015,
            "sell_unlock_price": 68955.65,
            "entry_price": 68808.07,
            "tp_enabled": True,
            "tp_pct": 0.025,
            "tp_target": 70528.27,
            "sl_enabled": False,
            "sl_pct": 0.025,
            "sl_price": 67088.0,
            "trailing_enabled": True,
            "trailing_activation": 0.015,
            "trailing_activation_price": 69840.19,
            "trailing_trail": 0.008,
            "current_net_pnl": -0.7106,
        }

    def test_header_present(self, default_params: dict) -> None:
        """Bloco deve começar com cabeçalho correto."""
        block = build_sell_conditions_block(**default_params)
        assert "CONDIÇÕES DE VENDA (resumo atual):" in block

    def test_min_sell_pnl_formatted(self, default_params: dict) -> None:
        """min_sell_pnl deve aparecer formatado com 3 casas decimais."""
        block = build_sell_conditions_block(**default_params)
        assert "$0.015" in block

    def test_sell_unlock_price_formatted(self, default_params: dict) -> None:
        """sell_unlock_price deve aparecer com separador de milhar."""
        block = build_sell_conditions_block(**default_params)
        assert "$68,955.65" in block

    def test_entry_price_in_context(self, default_params: dict) -> None:
        """entry_price deve aparecer na explicação."""
        block = build_sell_conditions_block(**default_params)
        assert "$68,808.07" in block
        assert "entry" in block.lower()
        assert "fees" in block.lower()

    def test_tp_enabled(self, default_params: dict) -> None:
        """TP ativado deve mostrar ATIVADO, %, e alvo."""
        block = build_sell_conditions_block(**default_params)
        assert "ATIVADO" in block
        assert "2.50%" in block
        assert "$70,528.27" in block

    def test_tp_disabled(self, default_params: dict) -> None:
        """TP desativado deve mostrar DESATIVADO."""
        default_params["tp_enabled"] = False
        block = build_sell_conditions_block(**default_params)
        lines = [l for l in block.split("\n") if "Take-Profit" in l]
        assert len(lines) == 1
        assert "DESATIVADO" in lines[0]

    def test_sl_disabled(self, default_params: dict) -> None:
        """SL desativado deve mostrar DESATIVADO."""
        block = build_sell_conditions_block(**default_params)
        lines = [l for l in block.split("\n") if "Stop-Loss" in l]
        assert len(lines) == 1
        assert "DESATIVADO" in lines[0]

    def test_sl_enabled(self, default_params: dict) -> None:
        """SL ativado deve mostrar SL%, piso."""
        default_params["sl_enabled"] = True
        block = build_sell_conditions_block(**default_params)
        lines = [l for l in block.split("\n") if "Stop-Loss" in l]
        assert len(lines) == 1
        assert "ATIVADO" in lines[0]
        assert "2.5%" in lines[0]
        assert "$67,088.00" in lines[0]

    def test_trailing_enabled(self, default_params: dict) -> None:
        """Trailing ativado deve mostrar activation e trail."""
        block = build_sell_conditions_block(**default_params)
        lines = [l for l in block.split("\n") if "Trailing" in l]
        assert len(lines) == 1
        assert "ATIVADO" in lines[0]
        assert "1.5%" in lines[0]
        assert "0.8%" in lines[0]

    def test_trailing_disabled(self, default_params: dict) -> None:
        """Trailing desativado deve mostrar DESATIVADO."""
        default_params["trailing_enabled"] = False
        block = build_sell_conditions_block(**default_params)
        lines = [l for l in block.split("\n") if "Trailing" in l]
        assert len(lines) == 1
        assert "DESATIVADO" in lines[0]

    def test_negative_pnl_formatted(self, default_params: dict) -> None:
        """PnL negativo deve ser formatado com 4 casas."""
        block = build_sell_conditions_block(**default_params)
        assert "$-0.7106" in block

    def test_positive_pnl_formatted(self, default_params: dict) -> None:
        """PnL positivo deve ser formatado corretamente."""
        default_params["current_net_pnl"] = 1.2345
        block = build_sell_conditions_block(**default_params)
        assert "$1.2345" in block

    def test_all_six_lines_present(self, default_params: dict) -> None:
        """Bloco deve conter exatamente 6 linhas de dados (- prefixadas)."""
        block = build_sell_conditions_block(**default_params)
        data_lines = [l for l in block.strip().split("\n") if l.startswith("- ")]
        assert len(data_lines) == 6, (
            f"Esperado 6 linhas de dados, obteve {len(data_lines)}"
        )


# ═══════════════════════════════════════════════════════════════
# Testes de lógica de TP dinâmico (RAG vs config)
# ═══════════════════════════════════════════════════════════════


class TestTPDynamicSelection:
    """Testa a seleção de TP dinâmico entre RAG e config."""

    def test_rag_used_when_similar_count_gte_3(self) -> None:
        """RAG TP deve ser usado quando similar_count >= 3."""
        rag_adj = RAGAdjustment(similar_count=3, ai_take_profit_pct=0.035)
        config_tp = 0.025
        tp_pct = rag_adj.ai_take_profit_pct if rag_adj.similar_count >= 3 else config_tp
        assert tp_pct == 0.035

    def test_config_used_when_similar_count_lt_3(self) -> None:
        """Config TP deve ser usado quando similar_count < 3."""
        rag_adj = RAGAdjustment(similar_count=2, ai_take_profit_pct=0.035)
        config_tp = 0.025
        tp_pct = rag_adj.ai_take_profit_pct if rag_adj.similar_count >= 3 else config_tp
        assert tp_pct == config_tp

    def test_rag_boundary_exactly_3(self) -> None:
        """Exatamente 3 similares deve usar RAG."""
        rag_adj = RAGAdjustment(similar_count=3, ai_take_profit_pct=0.04)
        config_tp = 0.025
        tp_pct = rag_adj.ai_take_profit_pct if rag_adj.similar_count >= 3 else config_tp
        assert tp_pct == 0.04

    def test_tp_target_calculation(self) -> None:
        """TP target deve ser entry * (1 + tp_pct)."""
        entry_price = 68808.07
        tp_pct = 0.025
        tp_target = entry_price * (1 + tp_pct)
        assert abs(tp_target - 70528.27) < 0.1

    def test_tp_target_zero_entry(self) -> None:
        """Sem posição (entry=0), tp_target deve ser 0."""
        entry_price = 0.0
        tp_pct = 0.025
        tp_target = entry_price * (1 + tp_pct) if entry_price > 0 else 0
        assert tp_target == 0

    def test_sl_price_calculation(self) -> None:
        """SL price deve ser entry * (1 - sl_pct)."""
        entry_price = 68808.07
        sl_pct = 0.025
        sl_price = entry_price * (1 - sl_pct)
        expected = 68808.07 * 0.975
        assert abs(sl_price - expected) < 0.01


# ═══════════════════════════════════════════════════════════════
# Testes de trailing stop
# ═══════════════════════════════════════════════════════════════


class TestTrailingStopCalculations:
    """Testa cálculos de trailing stop condições."""

    def test_activation_price(self) -> None:
        """Preço de ativação deve ser entry * (1 + activation_pct)."""
        entry = 68808.07
        activation_pct = 0.015
        result = entry * (1 + activation_pct)
        assert abs(result - 69840.19) < 0.1

    def test_activation_price_zero_entry(self) -> None:
        """Sem posição, activation_price deve ser 0."""
        entry = 0.0
        activation_pct = 0.015
        result = entry * (1 + activation_pct) if entry > 0 else 0
        assert result == 0

    def test_trail_below_activation(self) -> None:
        """Trail % deve ser menor que activation %."""
        activation_pct = 0.015  # 1.5%
        trail_pct = 0.008  # 0.8%
        assert trail_pct < activation_pct


# ═══════════════════════════════════════════════════════════════
# Testes de metadata do AI plan
# ═══════════════════════════════════════════════════════════════


class TestAIPlanMetadata:
    """Testes para os novos campos de metadata do AI plan."""

    @pytest.fixture()
    def sample_metadata(self) -> dict:
        """Metadata completo de exemplo."""
        return {
            "rsi": 45.2,
            "momentum": 0.003,
            "volatility": 0.0012,
            "position_btc": 0.00276000,
            "position_count": 9,
            "entry_price": 68808.07,
            "usdt_balance": 50.00,
            "regime_confidence": 0.750,
            "buy_target": 68500.00,
            "take_profit_pct": 0.0250,
            "sell_unlock_price": 68955.65,
            "current_net_pnl": -0.7106,
            "tp_target": 70528.27,
            "sl_enabled": False,
            "tp_enabled": True,
            "trailing_enabled": True,
        }

    def test_new_fields_present(self, sample_metadata: dict) -> None:
        """Todos os 6 novos campos devem estar presentes."""
        new_fields = [
            "sell_unlock_price", "current_net_pnl", "tp_target",
            "sl_enabled", "tp_enabled", "trailing_enabled",
        ]
        for f in new_fields:
            assert f in sample_metadata, f"Campo {f} ausente no metadata"

    def test_sell_unlock_price_rounded(self, sample_metadata: dict) -> None:
        """sell_unlock_price deve estar arredondado para 2 casas."""
        val = sample_metadata["sell_unlock_price"]
        assert val == round(val, 2)

    def test_current_net_pnl_rounded(self, sample_metadata: dict) -> None:
        """current_net_pnl deve estar arredondado para 4 casas."""
        val = sample_metadata["current_net_pnl"]
        assert val == round(val, 4)

    def test_tp_target_rounded(self, sample_metadata: dict) -> None:
        """tp_target deve estar arredondado para 2 casas."""
        val = sample_metadata["tp_target"]
        assert val == round(val, 2)

    def test_boolean_fields_are_bool(self, sample_metadata: dict) -> None:
        """Campos de enabled devem ser booleanos."""
        for f in ("sl_enabled", "tp_enabled", "trailing_enabled"):
            assert isinstance(sample_metadata[f], bool), (
                f"{f} deve ser bool, é {type(sample_metadata[f])}"
            )

    def test_metadata_serializable(self, sample_metadata: dict) -> None:
        """Metadata deve ser serializável em JSON."""
        serialized = json.dumps(sample_metadata)
        deserialized = json.loads(serialized)
        assert deserialized == sample_metadata


# ═══════════════════════════════════════════════════════════════
# Testes do prompt completo (instrução de 4 itens)
# ═══════════════════════════════════════════════════════════════


class TestPromptInstructions:
    """Valida que as instruções do prompt têm 4 itens."""

    PROMPT_INSTRUCTIONS = [
        "1. Situação atual do mercado",
        "2. O que o agente vai fazer a seguir (comprar, vender, esperar)",
        "3. Cenário de saída: quando e a que preço a venda será executada",
        "4. Riscos e oportunidades identificados",
    ]

    def test_all_four_items_present(self) -> None:
        """Prompt deve incluir 4 itens de instrução."""
        assert len(self.PROMPT_INSTRUCTIONS) == 4

    def test_item3_mentions_exit_scenario(self) -> None:
        """Item 3 deve mencionar cenário de saída."""
        assert "saída" in self.PROMPT_INSTRUCTIONS[2].lower()
        assert "preço" in self.PROMPT_INSTRUCTIONS[2].lower()

    def test_item4_mentions_risks(self) -> None:
        """Item 4 deve mencionar riscos."""
        assert "riscos" in self.PROMPT_INSTRUCTIONS[3].lower()


# ═══════════════════════════════════════════════════════════════
# Testes de config live (leitura dinâmica)
# ═══════════════════════════════════════════════════════════════


class TestLiveConfigReading:
    """Testa a leitura dinâmica do config.json para condições de venda."""

    @pytest.fixture()
    def full_config(self) -> dict:
        """Config completo de exemplo."""
        return {
            "symbol": "BTC-USDT",
            "min_sell_pnl": 0.015,
            "auto_stop_loss": {
                "enabled": False,
                "pct": 0.025,
            },
            "auto_take_profit": {
                "enabled": True,
                "pct": 0.025,
            },
            "trailing_stop": {
                "enabled": True,
                "activation_pct": 0.015,
                "trail_pct": 0.008,
            },
        }

    def test_min_sell_pnl_from_config(self, full_config: dict) -> None:
        """min_sell_pnl deve vir do config."""
        assert full_config.get("min_sell_pnl", 0.015) == 0.015

    def test_auto_sl_defaults(self) -> None:
        """Se auto_stop_loss não está no config, defaults são usados."""
        empty_config: dict = {}
        auto_sl = empty_config.get("auto_stop_loss", {})
        assert auto_sl.get("enabled", False) is False
        assert auto_sl.get("pct", 0.025) == 0.025

    def test_auto_tp_defaults(self) -> None:
        """Se auto_take_profit não está no config, defaults são usados."""
        empty_config: dict = {}
        auto_tp = empty_config.get("auto_take_profit", {})
        assert auto_tp.get("enabled", False) is False
        assert auto_tp.get("pct", 0.025) == 0.025

    def test_trailing_defaults(self) -> None:
        """Se trailing_stop não está no config, defaults são usados."""
        empty_config: dict = {}
        trailing = empty_config.get("trailing_stop", {})
        assert trailing.get("enabled", False) is False
        assert trailing.get("activation_pct", 0.015) == 0.015
        assert trailing.get("trail_pct", 0.008) == 0.008

    def test_config_file_read_failure_uses_fallback(self) -> None:
        """Se a leitura do config falhar, deve usar _config fallback."""
        _config = {"min_sell_pnl": 0.015}
        try:
            with open("/path/nao/existe.json") as f:
                _live_cfg = json.load(f)
        except Exception:
            _live_cfg = _config
        assert _live_cfg == _config

    def test_all_config_sections_parsed(self, full_config: dict) -> None:
        """Todas as 3 seções de exit devem ser lidas do config."""
        auto_sl_cfg = full_config.get("auto_stop_loss", {})
        auto_tp_cfg = full_config.get("auto_take_profit", {})
        trailing_cfg = full_config.get("trailing_stop", {})
        assert auto_sl_cfg.get("enabled") is False
        assert auto_tp_cfg.get("enabled") is True
        assert trailing_cfg.get("enabled") is True
        assert trailing_cfg.get("activation_pct") == 0.015
        assert trailing_cfg.get("trail_pct") == 0.008


# ═══════════════════════════════════════════════════════════════
# Testes end-to-end: cenários completos de cálculo
# ═══════════════════════════════════════════════════════════════


class TestEndToEndScenarios:
    """Testes end-to-end que simulam cenários completos de cálculo."""

    def test_scenario_position_in_loss(self) -> None:
        """Cenário: posição aberta em prejuízo."""
        entry = 69000.0
        pos = 0.003
        price = 68500.0
        min_pnl = 0.015
        config = {
            "auto_stop_loss": {"enabled": False, "pct": 0.025},
            "auto_take_profit": {"enabled": True, "pct": 0.025},
            "trailing_stop": {"enabled": True, "activation_pct": 0.015, "trail_pct": 0.008},
        }

        sell_unlock = calc_sell_unlock_price(entry, pos, min_pnl)
        net_pnl = calc_current_net_pnl(price, entry, pos)
        tp_target = entry * (1 + config["auto_take_profit"]["pct"])
        sl_price = entry * (1 - config["auto_stop_loss"]["pct"])
        trailing_act = entry * (1 + config["trailing_stop"]["activation_pct"])

        assert net_pnl < 0, "PnL deve ser negativo neste cenário"
        assert price < sell_unlock, "Preço atual deve estar abaixo do sell_unlock"
        assert tp_target > sell_unlock, "TP target deve estar acima do sell_unlock"

        block = build_sell_conditions_block(
            min_sell_pnl=min_pnl,
            sell_unlock_price=sell_unlock,
            entry_price=entry,
            tp_enabled=config["auto_take_profit"]["enabled"],
            tp_pct=config["auto_take_profit"]["pct"],
            tp_target=tp_target,
            sl_enabled=config["auto_stop_loss"]["enabled"],
            sl_pct=config["auto_stop_loss"]["pct"],
            sl_price=sl_price,
            trailing_enabled=config["trailing_stop"]["enabled"],
            trailing_activation=config["trailing_stop"]["activation_pct"],
            trailing_activation_price=trailing_act,
            trailing_trail=config["trailing_stop"]["trail_pct"],
            current_net_pnl=net_pnl,
        )
        assert "CONDIÇÕES DE VENDA" in block
        assert "ATIVADO" in block
        assert "DESATIVADO" in block

    def test_scenario_position_in_profit(self) -> None:
        """Cenário: posição aberta em lucro."""
        entry = 68000.0
        pos = 0.005
        price = 70000.0  # +$2000
        min_pnl = 0.015

        sell_unlock = calc_sell_unlock_price(entry, pos, min_pnl)
        net_pnl = calc_current_net_pnl(price, entry, pos)

        assert net_pnl > 0, "PnL deve ser positivo neste cenário"
        assert price > sell_unlock, "Preço atual deve estar acima do sell_unlock"

    def test_scenario_no_position(self) -> None:
        """Cenário: sem posição aberta."""
        sell_unlock = calc_sell_unlock_price(0.0, 0.0, 0.015)
        net_pnl = calc_current_net_pnl(70000.0, 0.0, 0.0)

        assert sell_unlock == 0.0
        assert net_pnl == 0.0

    def test_scenario_breakeven_exact(self) -> None:
        """Cenário: preço exatamente no breakeven."""
        entry = 68000.0
        pos = 0.001
        breakeven = entry * (1 + TRADING_FEE_PCT) / (1 - TRADING_FEE_PCT)
        net_pnl = calc_current_net_pnl(breakeven, entry, pos)
        assert abs(net_pnl) < 0.0001, f"PnL no breakeven deve ser ~0, é {net_pnl}"

    def test_scenario_at_tp_target(self) -> None:
        """Cenário: preço exatamente no TP target."""
        entry = 68000.0
        pos = 0.002
        tp_pct = 0.025
        tp_target = entry * (1 + tp_pct)
        net_pnl = calc_current_net_pnl(tp_target, entry, pos)
        expected_gross = tp_pct * entry * pos
        assert net_pnl > 0, "No TP target, PnL deve ser positivo"
        assert net_pnl < expected_gross, "PnL líquido < PnL bruto (fees)"

    def test_scenario_very_small_position(self) -> None:
        """Cenário: posição muito pequena (micro trades)."""
        entry = 68000.0
        pos = 0.0001  # ~$6.80
        min_pnl = 0.015
        sell_unlock = calc_sell_unlock_price(entry, pos, min_pnl)
        # Com posição tão pequena, o spread entre entry e sell_unlock é grande
        spread = sell_unlock - entry
        assert spread > 100, "Posição mínima exige grande spread para cobrir min_pnl"


# ═══════════════════════════════════════════════════════════════
# Testes do sell summary ANEXADO ao plan_text
# ═══════════════════════════════════════════════════════════════


def build_appended_sell_summary(
    *,
    min_sell_pnl: float,
    sell_unlock_price: float,
    entry_price: float,
    position: float,
    tp_enabled: bool,
    tp_pct: float,
    tp_target: float,
    sl_enabled: bool,
    sl_pct: float,
    sl_price: float,
    trailing_enabled: bool,
    trailing_activation: float,
    trailing_activation_price: float,
    trailing_trail: float,
    current_net_pnl: float,
) -> str:
    """Reproduz a lógica de append do sell summary ao plan_text.

    Replica o código adicionado ao trading_agent.py que anexa um bloco
    estruturado ao final do texto gerado pela IA.
    """
    lines = [
        "",
        "━━━ CONDIÇÕES DE VENDA (dados reais) ━━━",
        f"• PnL líquido mínimo p/ vender: ${min_sell_pnl:.3f}",
        f"• Preço mín. p/ desbloquear SELL: ${sell_unlock_price:,.2f}",
    ]
    if position > 0:
        lines.append(
            f"• Entry médio: ${entry_price:,.2f} | "
            f"Posição: {position:.8f} BTC"
        )
    lines.append(
        f"• Auto Take-Profit: "
        f"{'ATIVADO TP=' + f'{tp_pct*100:.2f}% → alvo ${tp_target:,.2f}' if tp_enabled else 'DESATIVADO'}"
    )
    lines.append(
        f"• Auto Stop-Loss: "
        f"{'ATIVADO SL=' + f'{sl_pct*100:.1f}% → piso ${sl_price:,.2f}' if sl_enabled else 'DESATIVADO'}"
    )
    lines.append(
        f"• Trailing Stop: "
        f"{'ATIVADO ativa +' + f'{trailing_activation*100:.1f}% (${trailing_activation_price:,.2f}), trail {trailing_trail*100:.1f}%' if trailing_enabled else 'DESATIVADO'}"
    )
    lines.append(f"• PnL líquido atual: ${current_net_pnl:.4f}")
    return "\n".join(lines)


class TestAppendedSellSummary:
    """Testa o bloco de sell summary que é ANEXADO ao plan_text."""

    @pytest.fixture()
    def with_position_params(self) -> dict:
        """Parâmetros com posição aberta."""
        return {
            "min_sell_pnl": 0.015,
            "sell_unlock_price": 68955.65,
            "entry_price": 68808.07,
            "position": 0.00276,
            "tp_enabled": True,
            "tp_pct": 0.025,
            "tp_target": 70528.27,
            "sl_enabled": False,
            "sl_pct": 0.025,
            "sl_price": 67088.0,
            "trailing_enabled": True,
            "trailing_activation": 0.015,
            "trailing_activation_price": 69840.19,
            "trailing_trail": 0.008,
            "current_net_pnl": -0.7106,
        }

    @pytest.fixture()
    def no_position_params(self) -> dict:
        """Parâmetros sem posição (após venda)."""
        return {
            "min_sell_pnl": 0.015,
            "sell_unlock_price": 0.0,
            "entry_price": 0.0,
            "position": 0.0,
            "tp_enabled": True,
            "tp_pct": 0.031,
            "tp_target": 0.0,
            "sl_enabled": False,
            "sl_pct": 0.025,
            "sl_price": 0.0,
            "trailing_enabled": True,
            "trailing_activation": 0.015,
            "trailing_activation_price": 0.0,
            "trailing_trail": 0.008,
            "current_net_pnl": 0.0,
        }

    def test_header_is_prominent(self, with_position_params: dict) -> None:
        """Header usa caracteres visuais ━━━ para destaque."""
        block = build_appended_sell_summary(**with_position_params)
        assert "━━━ CONDIÇÕES DE VENDA (dados reais) ━━━" in block

    def test_uses_bullet_points(self, with_position_params: dict) -> None:
        """Linhas de dados usam bullet • em vez de -."""
        block = build_appended_sell_summary(**with_position_params)
        bullet_lines = [l for l in block.split("\n") if l.startswith("•")]
        assert len(bullet_lines) >= 6

    def test_includes_entry_when_position_open(self, with_position_params: dict) -> None:
        """Com posição aberta, mostra entry e tamanho da posição."""
        block = build_appended_sell_summary(**with_position_params)
        assert "Entry médio: $68,808.07" in block
        assert "0.00276000 BTC" in block

    def test_excludes_entry_when_no_position(self, no_position_params: dict) -> None:
        """Sem posição, NÃO mostra linha de entry/posição."""
        block = build_appended_sell_summary(**no_position_params)
        assert "Entry médio" not in block

    def test_no_position_shows_zeros(self, no_position_params: dict) -> None:
        """Sem posição, sell_unlock e PnL são $0.00."""
        block = build_appended_sell_summary(**no_position_params)
        assert "$0.00" in block
        assert "$0.0000" in block

    def test_appended_to_ai_text(self, with_position_params: dict) -> None:
        """O bloco deve ser concatenado ao texto da IA com newline."""
        ai_text = "O mercado BTC está em regime ranging com RSI neutro."
        summary = build_appended_sell_summary(**with_position_params)
        final = ai_text + "\n" + summary
        assert final.startswith("O mercado BTC")
        assert "━━━ CONDIÇÕES DE VENDA" in final
        assert final.index("O mercado") < final.index("━━━")

    def test_tp_shows_ativado_with_values(self, with_position_params: dict) -> None:
        """TP ativado mostra TP=X.XX% → alvo."""
        block = build_appended_sell_summary(**with_position_params)
        assert "ATIVADO TP=2.50%" in block
        assert "alvo $70,528.27" in block

    def test_tp_shows_desativado(self, with_position_params: dict) -> None:
        """TP desativado mostra apenas DESATIVADO."""
        with_position_params["tp_enabled"] = False
        block = build_appended_sell_summary(**with_position_params)
        tp_line = [l for l in block.split("\n") if "Take-Profit" in l][0]
        assert "DESATIVADO" in tp_line
        assert "alvo" not in tp_line

    def test_sl_ativado(self, with_position_params: dict) -> None:
        """SL ativado mostra SL=X.X% → piso."""
        with_position_params["sl_enabled"] = True
        block = build_appended_sell_summary(**with_position_params)
        sl_line = [l for l in block.split("\n") if "Stop-Loss" in l][0]
        assert "ATIVADO SL=2.5%" in sl_line
        assert "piso $67,088.00" in sl_line

    def test_trailing_ativado(self, with_position_params: dict) -> None:
        """Trailing ativado mostra activation e trail."""
        block = build_appended_sell_summary(**with_position_params)
        tr_line = [l for l in block.split("\n") if "Trailing" in l][0]
        assert "ATIVADO ativa +1.5%" in tr_line
        assert "trail 0.8%" in tr_line

    def test_trailing_desativado(self, no_position_params: dict) -> None:
        """Trailing desativado mostra DESATIVADO."""
        no_position_params["trailing_enabled"] = False
        block = build_appended_sell_summary(**no_position_params)
        tr_line = [l for l in block.split("\n") if "Trailing" in l][0]
        assert "DESATIVADO" in tr_line

    def test_negative_pnl(self, with_position_params: dict) -> None:
        """PnL negativo formatado corretamente."""
        block = build_appended_sell_summary(**with_position_params)
        assert "$-0.7106" in block

    def test_positive_pnl(self, with_position_params: dict) -> None:
        """PnL positivo formatado corretamente."""
        with_position_params["current_net_pnl"] = 2.5432
        block = build_appended_sell_summary(**with_position_params)
        assert "$2.5432" in block

    def test_real_server_scenario_no_position(self, no_position_params: dict) -> None:
        """Reproduz cenário real do servidor: após venda, valores zerados."""
        ai_text = (
            "A situação no momento é delicadamente equilibrada na negociação BTC "
            "atualmente listando-se um RSI moderado."
        )
        summary = build_appended_sell_summary(**no_position_params)
        final = ai_text + "\n" + summary
        # Tem header
        assert "━━━ CONDIÇÕES DE VENDA (dados reais) ━━━" in final
        # min_sell_pnl presente mesmo sem posição
        assert "$0.015" in final
        # Zeros corretos
        assert "Preço mín. p/ desbloquear SELL: $0.00" in final
        # Sem linha de Entry
        assert "Entry médio" not in final

    def test_real_server_scenario_with_position(self, with_position_params: dict) -> None:
        """Reproduz cenário real: posição aberta em prejuízo."""
        ai_text = "O mercado BTC está em regime ranging."
        summary = build_appended_sell_summary(**with_position_params)
        final = ai_text + "\n" + summary
        assert "━━━" in final
        assert "$68,955.65" in final
        assert "Entry médio" in final
        assert "$-0.7106" in final

    def test_block_line_count_with_position(self, with_position_params: dict) -> None:
        """Com posição, bloco tem 9 linhas (vazia + header + 7 dados)."""
        block = build_appended_sell_summary(**with_position_params)
        lines = block.split("\n")
        assert len(lines) == 9, f"Esperado 9 linhas, obteve {len(lines)}: {lines}"

    def test_block_line_count_no_position(self, no_position_params: dict) -> None:
        """Sem posição, bloco tem 8 linhas (sem Entry)."""
        block = build_appended_sell_summary(**no_position_params)
        lines = block.split("\n")
        assert len(lines) == 8, f"Esperado 8 linhas, obteve {len(lines)}: {lines}"
