"""Testes unitários para _restore_position — persistência de target_sell por slot.

Verifica que após restart o agente reconstrói state.entries com target_sell
lido do metadata do trade, habilitando o per-slot TP sem intervenção manual.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# ── Env mínimo antes de qualquer import do módulo ──
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5433/test")
os.environ.setdefault("COIN_CONFIG_FILE", "config_BTC_USDT_aggressive.json")

_BTC_DIR = Path(__file__).resolve().parent.parent / "btc_trading_agent"
if str(_BTC_DIR) not in sys.path:
    sys.path.insert(0, str(_BTC_DIR))
if str(_BTC_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_BTC_DIR.parent))


# ── Stubs de dependências externas ──
def _make_stubs() -> None:
    """Injeta stubs somente para módulos sem dependência no venv."""
    import types

    for mod_name in ["kucoin", "kucoin.client"]:
        if mod_name not in sys.modules:
            sys.modules[mod_name] = types.ModuleType(mod_name)


_make_stubs()


def _make_trade(
    trade_id: int,
    side: str,
    price: float,
    size: float,
    profile: str = "aggressive",
    target_sell_price: float = 0.0,
    target_sell_reason: str = "",
) -> dict:
    """Cria um trade dict equivalente ao retorno de get_recent_trades."""
    meta: dict = {}
    if target_sell_price > 0:
        meta["target_sell_price"] = round(target_sell_price, 2)
        if target_sell_reason:
            meta["target_sell_reason"] = target_sell_reason
    return {
        "id": trade_id,
        "symbol": "BTC-USDT",
        "side": side,
        "price": price,
        "size": size,
        "funds": round(price * size, 2),
        "timestamp": time.time() - (100 - trade_id),
        "dry_run": False,
        "profile": profile,
        "pnl": None,
        "pnl_pct": None,
        "order_id": f"order-{trade_id}",
        "status": "executed",
        "metadata": meta,
    }


# ── Fixture: instância mínima do TradingAgent sem conexões reais ──
@pytest.fixture()
def agent(tmp_path, monkeypatch):
    """Retorna um TradingAgent totalmente mockado, pronto para testar _restore_position."""
    import btc_trading_agent.trading_agent as ta_mod  # noqa: PLC0415

    config_path = _BTC_DIR / "config_BTC_USDT_aggressive.json"
    if not config_path.exists():
        config_path = tmp_path / "config_BTC_USDT_aggressive.json"
        config_path.write_text(
            json.dumps({
                "symbol": "BTC-USDT",
                "dry_run": True,
                "profile": "aggressive",
                "auto_stop_loss": {"enabled": False, "pct": 0.05},
                "auto_take_profit": {"enabled": True, "pct": 0.015, "min_pct": 0.013},
                "guardrails_active": True,
                "guardrails_min_sell_pnl_pct": 0.003,
                "guardrails_positive_only_sells": True,
            }),
            encoding="utf-8",
        )

    mock_db = MagicMock()
    mock_rag = MagicMock()
    mock_model = MagicMock()

    monkeypatch.setattr(ta_mod, "get_balance", MagicMock(return_value=0.0))
    monkeypatch.setattr(ta_mod, "get_price", MagicMock(return_value=80_000.0))

    ag = ta_mod.BitcoinTradingAgent.__new__(ta_mod.BitcoinTradingAgent)
    ag.state = ta_mod.AgentState()
    ag.state.dry_run = True
    ag.symbol = "BTC-USDT"
    ag.config = json.loads(config_path.read_text())
    ag.db = mock_db
    ag.market_rag = mock_rag
    ag.model = mock_model
    ag._trade_lock = __import__("threading").Lock()

    mock_rag.get_current_adjustment.return_value = SimpleNamespace(
        similar_count=0,
        ai_take_profit_pct=0.015,
        ai_take_profit_reason="test",
        ai_min_confidence=0.55,
        ai_min_trade_interval=600,
        ai_max_entries=15,
        ai_position_size_pct=0.1,
        ai_aggressiveness=0.5,
        ai_buy_target_reason="",
        suggested_regime="RANGING",
        regime_confidence=0.5,
        avg_return_15m=0.0,
        ollama_mode="shadow",
        applied_min_confidence=0.55,
        applied_min_trade_interval=600,
        applied_max_positions=15,
        applied_max_position_pct=1.0,
        applied_min_sell_pnl_pct=0.003,
    )
    yield ag


# ── Testes ──

class TestRestorePositionTargetSell:
    """Verifica que _restore_position restaura target_sell de cada slot."""

    def test_target_sell_restored_from_metadata(self, agent):
        """Slots com target_sell_price no metadata devem ter target_sell > 0 após restore."""
        trades = [
            _make_trade(3, "buy", 80_500.0, 0.001, target_sell_price=81_557.75, target_sell_reason="bull:base_1.3%"),
            _make_trade(2, "buy", 80_000.0, 0.001, target_sell_price=81_040.0, target_sell_reason="ranging:base_1.3%"),
            _make_trade(1, "buy", 79_500.0, 0.001, target_sell_price=80_523.5, target_sell_reason="ranging:base_1.3%"),
        ]
        agent.db.get_recent_trades.return_value = trades

        with patch.object(agent, "_sync_position_tracking"):
            agent._restore_position()

        assert len(agent.state.entries) == 3
        # Ordem cronológica após reversed()
        assert agent.state.entries[0]["target_sell"] == pytest.approx(80_523.5)
        assert agent.state.entries[1]["target_sell"] == pytest.approx(81_040.0)
        assert agent.state.entries[2]["target_sell"] == pytest.approx(81_557.75)

    def test_target_sell_reason_restored(self, agent):
        """target_sell_reason também deve ser restaurado do metadata."""
        trades = [
            _make_trade(1, "buy", 80_000.0, 0.001, target_sell_price=81_040.0, target_sell_reason="bull:base_1.3%"),
        ]
        agent.db.get_recent_trades.return_value = trades

        with patch.object(agent, "_sync_position_tracking"):
            agent._restore_position()

        assert agent.state.entries[0].get("target_sell_reason") == "bull:base_1.3%"

    def test_target_sell_zero_when_metadata_absent(self, agent):
        """Slots sem target_sell_price no metadata devem ter target_sell = 0 (legado)."""
        trades = [
            _make_trade(1, "buy", 80_000.0, 0.001),  # sem target_sell_price
        ]
        agent.db.get_recent_trades.return_value = trades

        with patch.object(agent, "_sync_position_tracking"):
            agent._restore_position()

        assert agent.state.entries[0]["target_sell"] == 0.0

    def test_trailing_high_initialized_to_entry_price(self, agent):
        """trailing_high deve ser inicializado ao preço de entrada (baseline conservador)."""
        trades = [
            _make_trade(1, "buy", 79_000.0, 0.001, target_sell_price=80_027.0),
        ]
        agent.db.get_recent_trades.return_value = trades

        with patch.object(agent, "_sync_position_tracking"):
            agent._restore_position()

        assert agent.state.entries[0]["trailing_high"] == pytest.approx(79_000.0)

    def test_restore_stops_at_sell(self, agent):
        """_restore_position deve ignorar BUYs anteriores ao último SELL."""
        trades = [
            _make_trade(5, "buy",  80_100.0, 0.001, target_sell_price=81_141.3),
            _make_trade(4, "sell", 80_000.0, 0.002),  # fecha posição anterior
            _make_trade(3, "buy",  79_000.0, 0.001),
            _make_trade(2, "buy",  78_500.0, 0.001),
        ]
        agent.db.get_recent_trades.return_value = trades

        with patch.object(agent, "_sync_position_tracking"):
            agent._restore_position()

        # Só o BUY após o SELL deve estar em entries
        assert len(agent.state.entries) == 1
        assert agent.state.entries[0]["price"] == pytest.approx(80_100.0)
        assert agent.state.entries[0]["target_sell"] == pytest.approx(81_141.3)

    def test_metadata_as_json_string_parsed(self, agent):
        """metadata chegando como string JSON (fallback) deve ser parseado corretamente."""
        trade = _make_trade(1, "buy", 80_000.0, 0.001, target_sell_price=81_040.0)
        # Simular metadata como string (comportamento antigo do psycopg2 sem JSONB cast)
        trade["metadata"] = json.dumps(trade["metadata"])
        agent.db.get_recent_trades.return_value = [trade]

        with patch.object(agent, "_sync_position_tracking"):
            agent._restore_position()

        assert agent.state.entries[0]["target_sell"] == pytest.approx(81_040.0)

    def test_avg_entry_price_recalculated_correctly(self, agent):
        """Preço médio ponderado deve ser recalculado independente do target_sell."""
        trades = [
            _make_trade(2, "buy", 82_000.0, 0.001, target_sell_price=83_066.0),
            _make_trade(1, "buy", 80_000.0, 0.001, target_sell_price=81_040.0),
        ]
        agent.db.get_recent_trades.return_value = trades

        with patch.object(agent, "_sync_position_tracking"):
            agent._restore_position()

        # avg = (80000*0.001 + 82000*0.001) / 0.002 = 81000
        assert agent.state.entry_price == pytest.approx(81_000.0)
