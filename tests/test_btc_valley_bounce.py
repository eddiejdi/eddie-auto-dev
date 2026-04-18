#!/usr/bin/env python3
"""Testes unitários — valley bounce DCA (btc_trading_agent).

Cobre:
- AgentState.dca_valley_low inicializado corretamente
- DCA_VALLEY_BOUNCE_PCT constante padrão 0.004
- Bloqueio quando preço acima do gatilho de 1%
- Bloqueio quando preço abaixo do gatilho mas sem bounce suficiente
- Rastreamento do mínimo do vale (atualiza apenas para novos mínimos)
- Liberação após bounce >= bounce_pct do fundo
- Reset de dca_valley_low quando preço sobe acima do gatilho
- Parâmetro bounce_pct configurável
- Serialização de dca_valley_low em to_dict()
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ── Setup de ambiente e sys.path antes dos imports ──
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5433/test")

_REPO_DIR = Path(__file__).resolve().parent.parent
_BTC_DIR = _REPO_DIR / "btc_trading_agent"
for _p in [str(_BTC_DIR), str(_REPO_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Mocks de dependências externas (antes dos imports alvo) ──
_m_psycopg2 = MagicMock()
_m_psycopg2.pool = MagicMock()
sys.modules["psycopg2"] = _m_psycopg2
sys.modules["psycopg2.extras"] = MagicMock()
sys.modules["psycopg2.pool"] = MagicMock()

_m_secrets = MagicMock()
_m_secrets.get_database_url.return_value = "postgresql://test:test@localhost:5433/test"
_m_secrets.get_kucoin_credentials_with_source.return_value = ("k", "s", "p", "env")
_m_secrets.get_secret.return_value = None
sys.modules["secrets_helper"] = _m_secrets

_m_kucoin_api = MagicMock()
_m_kucoin_api.API_KEY = "k"
_m_kucoin_api.API_SECRET = "s"
_m_kucoin_api.API_PASSPHRASE = "p"
sys.modules["kucoin_api"] = _m_kucoin_api
sys.modules["kucoin"] = MagicMock()
sys.modules["kucoin.client"] = MagicMock()
sys.modules["prometheus_client"] = MagicMock()
sys.modules["market_rag"] = MagicMock()

# ── Imports alvo ──
from trading_agent import AgentState, DCA_VALLEY_BOUNCE_PCT  # noqa: E402


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def _open_position(state: AgentState, entry_price: float, qty: float = 0.001) -> None:
    """Configura estado com posição aberta."""
    state.position = qty
    state.entry_price = entry_price
    state.entries = [{"price": entry_price, "size": qty, "ts": time.time()}]
    state.raw_entry_count = 1
    state.logical_position_slots = 1
    state.position_count = 1


def _valley_gate(
    state: AgentState,
    signal_price: float,
    bounce_pct: float = 0.004,
    rebuy_discount_pct: float = 0.01,
) -> bool:
    """Reimplementação isolada do valley bounce gate — retorna True se bloqueado.

    Espelha a lógica em trading_agent.py sem depender de I/O externo.
    """
    rebuy_trigger_price = state.entry_price * (1.0 - rebuy_discount_pct)

    # Acima do gatilho: discount não atingido → reset + bloquear
    if signal_price > rebuy_trigger_price:
        state.dca_valley_low = 0.0
        return True

    # Atualizar mínimo do vale
    if state.dca_valley_low <= 0 or signal_price < state.dca_valley_low:
        state.dca_valley_low = signal_price

    # Verificar se bounce mínimo foi confirmado
    valley_bounce_trigger = state.dca_valley_low * (1.0 + bounce_pct)
    return signal_price < valley_bounce_trigger


# ─────────────────────────────────────────────
#  Testes de estado/constante
# ─────────────────────────────────────────────

class TestAgentStateValleyField:
    """Testa a presença e inicialização de dca_valley_low em AgentState."""

    def test_field_exists_and_default_zero(self):
        s = AgentState()
        assert hasattr(s, "dca_valley_low")
        assert s.dca_valley_low == 0.0

    def test_constant_default_value(self):
        assert DCA_VALLEY_BOUNCE_PCT == pytest.approx(0.004)

    def test_to_dict_serializes_valley_low(self):
        s = AgentState()
        s.dca_valley_low = 74_480.0
        d = s.to_dict()
        assert "dca_valley_low" in d
        assert d["dca_valley_low"] == pytest.approx(74_480.0)


# ─────────────────────────────────────────────
#  Testes de lógica do gate
# ─────────────────────────────────────────────

class TestDcaValleyBounceGate:
    """Testa a lógica do valley bounce gate isoladamente."""

    def test_blocked_above_rebuy_trigger(self):
        """DCA bloqueado quando preço > avg * 0.99 (1% discount não atingido)."""
        s = AgentState()
        _open_position(s, 76_000.0)
        # 75.800 = apenas 0.26% abaixo — não atinge 1%
        assert _valley_gate(s, 75_800.0) is True
        assert s.dca_valley_low == 0.0  # vale não inicia quando acima do gatilho

    def test_valley_low_reset_when_price_returns_above_trigger(self):
        """dca_valley_low é zerado quando preço sobe acima do gatilho."""
        s = AgentState()
        _open_position(s, 76_000.0)
        s.dca_valley_low = 74_480.0  # mínimo previamente registrado
        # Preço sobe para 75.500 (apenas 0.66% abaixo) — acima do gatilho de 1%
        _valley_gate(s, 75_500.0)
        assert s.dca_valley_low == 0.0

    def test_blocked_at_trigger_no_bounce_yet(self):
        """DCA bloqueado quando preço cruzou o gatilho mas ainda caindo."""
        s = AgentState()
        _open_position(s, 76_000.0)
        # 74.860 ≈ 1.5% abaixo: cruzou o gatilho, mas sem bounce confirmado
        assert _valley_gate(s, 74_860.0) is True
        assert s.dca_valley_low == pytest.approx(74_860.0)

    def test_valley_low_tracks_minimum(self):
        """dca_valley_low atualiza apenas para novos mínimos."""
        s = AgentState()
        _open_position(s, 76_000.0)

        _valley_gate(s, 74_860.0)          # 1ª queda
        assert s.dca_valley_low == pytest.approx(74_860.0)

        _valley_gate(s, 74_500.0)          # novo mínimo
        assert s.dca_valley_low == pytest.approx(74_500.0)

        _valley_gate(s, 74_600.0)          # leve subida — mínimo NÃO sobe
        assert s.dca_valley_low == pytest.approx(74_500.0)

    def test_allowed_after_sufficient_bounce(self):
        """DCA liberado após bounce >= 0.4% do fundo do vale."""
        s = AgentState()
        _open_position(s, 76_000.0)
        s.dca_valley_low = 74_480.0
        # bounce_trigger = 74480 * 1.004 = 74778.12
        # 74.790 > 74778.12 → deve liberar
        assert _valley_gate(s, 74_790.0) is False

    def test_blocked_below_bounce_trigger(self):
        """DCA bloqueado quando bounce é insuficiente."""
        s = AgentState()
        _open_position(s, 76_000.0)
        s.dca_valley_low = 74_480.0
        # bounce_trigger = 74480 * 1.004 = 74778.12
        # 74.650 < 74778.12 → deve bloquear
        assert _valley_gate(s, 74_650.0) is True

    def test_bounce_exactly_at_trigger(self):
        """Preço exatamente no bounce trigger deve ser liberado (boundary)."""
        s = AgentState()
        _open_position(s, 76_000.0)
        bounce_pct = 0.004
        s.dca_valley_low = 74_480.0
        trigger = 74_480.0 * (1.0 + bounce_pct)  # 74778.12
        assert _valley_gate(s, trigger, bounce_pct=bounce_pct) is False

    def test_conservative_bounce_pct_blocks_earlier_bounce(self):
        """bounce_pct = 1% (conservador) bloqueia onde 0.4% liberaria."""
        s = AgentState()
        _open_position(s, 76_000.0)
        s.dca_valley_low = 74_480.0
        # 74.790 seria liberado com 0.4% mas é bloqueado com 1%
        assert _valley_gate(s, 74_790.0, bounce_pct=0.004) is False  # liberado
        s2 = AgentState()
        _open_position(s2, 76_000.0)
        s2.dca_valley_low = 74_480.0
        assert _valley_gate(s2, 74_790.0, bounce_pct=0.01) is True   # bloqueado

    def test_aggressive_bounce_pct_allows_earlier_release(self):
        """bounce_pct = 0.1% (agressivo) libera com bounce menor."""
        s = AgentState()
        _open_position(s, 76_000.0)
        s.dca_valley_low = 74_480.0
        # 74.560 seria bloqueado com 0.4% mas liberado com 0.1%
        assert _valley_gate(s, 74_560.0, bounce_pct=0.004) is True   # bloqueado
        s2 = AgentState()
        _open_position(s2, 76_000.0)
        s2.dca_valley_low = 74_480.0
        assert _valley_gate(s2, 74_560.0, bounce_pct=0.001) is False  # liberado
