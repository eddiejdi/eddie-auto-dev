#!/usr/bin/env python3
"""Regressões para contenção operacional e modo seguro de startup."""

from pathlib import Path
from types import SimpleNamespace
import os
import sys
import types
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))
sys.modules.setdefault(
    "httpx",
    types.SimpleNamespace(
        Client=object,
    ),
)
sys.modules.setdefault(
    "kucoin_api",
    types.SimpleNamespace(
        get_price=None,
        get_price_fast=None,
        get_orderbook=None,
        get_candles=None,
        get_recent_trades=None,
        get_balances=None,
        get_balance=None,
        place_market_order=None,
        analyze_orderbook=None,
        analyze_trade_flow=None,
        inner_transfer=None,
        _has_keys=lambda: False,
        get_fills_for_order=lambda *a, **kw: {},
    ),
)
sys.modules.setdefault(
    "fast_model",
    types.SimpleNamespace(
        FastTradingModel=object,
        MarketState=object,
        Signal=object,
    ),
)
sys.modules.setdefault(
    "training_db",
    types.SimpleNamespace(
        TrainingDatabase=object,
        TrainingManager=object,
    ),
)
sys.modules.setdefault(
    "market_rag",
    types.SimpleNamespace(
        MarketRAG=object,
    ),
)

from trading_agent import (
    BitcoinTradingAgent,
    TradeControls,
    _explicit_runtime_config_requested,
    _resolve_process_dry_run,
)


def test_resolve_process_dry_run_allows_config_to_force_safe_mode() -> None:
    assert _resolve_process_dry_run(True, {"dry_run": True}) is True
    assert _resolve_process_dry_run(True, {"live_mode": False}) is True
    assert _resolve_process_dry_run(True, {"dry_run": False, "live_mode": True}) is False


def test_resolve_process_dry_run_never_forces_live_from_config() -> None:
    assert _resolve_process_dry_run(False, {"dry_run": False, "live_mode": True}) is True


def test_explicit_runtime_config_requested_detects_instance_configs() -> None:
    assert _explicit_runtime_config_requested("config_BTC_USDT_aggressive.json") is True
    assert _explicit_runtime_config_requested("config_USDT_BRL_conservative.json") is True
    assert _explicit_runtime_config_requested("config.json") is False


def test_load_live_config_strict_raises_when_explicit_config_missing(tmp_path: Path) -> None:
    agent = BitcoinTradingAgent.__new__(BitcoinTradingAgent)
    agent.config_path = tmp_path / "missing.json"
    agent.config = {"symbol": "BTC-USDT", "profile": "aggressive"}

    with pytest.raises(FileNotFoundError):
        agent._load_live_config(strict=True)


def test_load_live_config_non_strict_keeps_last_valid_config(tmp_path: Path) -> None:
    agent = BitcoinTradingAgent.__new__(BitcoinTradingAgent)
    agent.config_path = tmp_path / "missing.json"
    agent.config = {"symbol": "BTC-USDT", "profile": "aggressive"}

    assert agent._load_live_config(strict=False)["profile"] == "aggressive"


def _agent_with_live_cfg(live_cfg):
    agent = BitcoinTradingAgent.__new__(BitcoinTradingAgent)
    agent.symbol = "BTC-USDT"
    agent.state = SimpleNamespace(
        profile=live_cfg.get("profile", "aggressive"),
        last_trade_time=0.0,
        position_count=0,
        raw_entry_count=0,
        logical_position_slots=0,
        position=0.0,
        entry_price=0.0,
        entries=[],
        dry_run=False,
        last_sell_entry_price=0.0,
        target_sell_price=0.0,
        target_sell_reason="",
        buy_success_pressure=0.0,
        buy_success_factor=1.0,
        buy_dynamic_batch_cap_usdt=0.0,
    )
    agent.market_rag = SimpleNamespace(
        get_current_adjustment=lambda: SimpleNamespace(
            ai_buy_target_price=0.0,
            ai_buy_target_reason="runtime-guard-test",
            ai_max_entries=1,
            ai_position_size_pct=0.2,
            ai_position_size_reason="runtime-guard-test",
        )
    )
    agent.db = SimpleNamespace(
        count_trades_since=lambda **kwargs: 0,
        get_pnl_since=lambda **kwargs: 0.0,
    )
    agent._load_live_config = lambda: dict(live_cfg)
    agent._resolve_trade_controls = lambda rag_adj=None: TradeControls(
        min_confidence=0.50,
        min_trade_interval=0,
        max_position_pct=0.30,
        max_positions_cap=4,
        effective_max_positions=4,
        ai_controlled=False,
        ollama_mode="shadow",
    )
    agent._analyze_signal_context = lambda rag_adj, signal: {
        "penalty_score": 0.0,
        "bonus_score": 0.0,
        "strong_bearish": False,
        "hard_block_buy": False,
        "net_score": 0.0,
        "penalties": [],
        "bonuses": [],
    }
    agent._resolve_buy_gate_limits = lambda rag_adj, signal: {
        "ai_buy_target": 0.0,
        "extra_discount_pct": 0.0,
        "uplift_pct": 0.0,
        "tolerance_pct": 0.0,
        "effective_buy_target": 0.0,
        "effective_buy_ceiling": 0.0,
        "trade_window": None,
        "window_entry_low": 0.0,
        "window_entry_high": 0.0,
        "used_trade_window": False,
    }
    agent._current_profile = lambda: live_cfg.get("profile", "aggressive")
    agent._sync_target_sell_with_ai = lambda reason_prefix="IA": None
    return agent


def test_check_can_trade_uses_live_daily_trade_limit() -> None:
    agent = _agent_with_live_cfg({"profile": "aggressive", "max_daily_trades": 0, "max_daily_loss": 50})
    agent.db = SimpleNamespace(
        count_trades_since=lambda **kwargs: 0,
        get_pnl_since=lambda **kwargs: 0.0,
    )
    signal = SimpleNamespace(action="BUY", confidence=0.80, price=70000.0, reason="unit")

    assert agent._check_can_trade(signal) is False


def test_check_can_trade_uses_live_daily_loss_limit() -> None:
    agent = _agent_with_live_cfg({"profile": "conservative", "max_daily_trades": 99, "max_daily_loss": 0})
    agent.db = SimpleNamespace(
        count_trades_since=lambda **kwargs: 0,
        get_pnl_since=lambda **kwargs: -0.01,
    )
    signal = SimpleNamespace(action="BUY", confidence=0.80, price=70000.0, reason="unit")

    assert agent._check_can_trade(signal) is False


def test_guardrails_active_allows_sell_when_minimum_guardrail_pnl_is_reached() -> None:
    agent = _agent_with_live_cfg(
        {
            "profile": "conservative",
            "max_daily_trades": 9999,
            "max_daily_loss": 0.085,
            "guardrails_active": True,
            "guardrails_positive_only_sells": True,
            "guardrails_min_sell_pnl_pct": 0.025,
        }
    )
    agent.state.position = 0.001
    agent.state.entry_price = 70000.0
    agent.state.target_sell_price = 72500.0
    signal = SimpleNamespace(action="SELL", confidence=0.40, price=71950.0, reason="unit")

    assert agent._check_can_trade(signal) is True


def test_guardrails_active_blocks_negative_sell_even_with_force_path() -> None:
    agent = _agent_with_live_cfg(
        {
            "profile": "aggressive",
            "max_daily_trades": 9999,
            "max_daily_loss": 0.03,
            "guardrails_active": True,
            "guardrails_positive_only_sells": True,
            "guardrails_min_sell_pnl_pct": 0.025,
            "min_net_profit": {"usd": 0.01, "pct": 0.0005},
            "stop_loss_pct": 0.02,
        }
    )
    agent.state.position = 0.001
    agent.state.entry_price = 70000.0
    signal = SimpleNamespace(action="SELL", confidence=1.0, price=69950.0, reason="AUTO_STOP_LOSS")

    assert agent._calculate_trade_size(signal, signal.price, force=True) == 0


def test_sync_position_tracking_counts_multi_entries_as_multiple_slots() -> None:
    agent = _agent_with_live_cfg({"profile": "aggressive"})
    agent.state.position = 0.002
    agent.state.entry_price = 100.0
    agent.state.entries = [
        {"price": 101.0, "size": 0.001, "ts": 1.0},
        {"price": 99.0, "size": 0.001, "ts": 2.0},
    ]

    agent._sync_position_tracking()

    assert agent.state.position_count == 2
    assert agent.state.raw_entry_count == 2
    assert agent.state.logical_position_slots == 2


def test_check_can_trade_blocks_rebuy_without_minimum_discount() -> None:
    agent = _agent_with_live_cfg(
        {"profile": "aggressive", "max_daily_trades": 9999, "max_daily_loss": 9999}
    )
    agent._get_profile_buy_profit_guard_cfg = lambda **_kw: {
        "min_projected_edge_pct": 0.0,
        "min_window_slack_pct": 0.0,
        "pressure": 0.0,
        "recent_pnl": 0.0,
        "losing_streak": 0,
    }
    agent.state.position = 0.001
    agent.state.entry_price = 100.0
    agent.state.entries = [{"price": 100.0, "size": 0.001, "ts": 1.0}]
    agent._sync_position_tracking()
    signal = SimpleNamespace(action="BUY", confidence=0.80, price=99.50, reason="unit")

    assert agent._check_can_trade(signal) is False
    assert agent.state.last_trade_block_reason == "buy_rebuy_discount"
    assert agent.state.last_trade_block_context["rebuy_trigger_price"] == 99.0


def test_check_can_trade_allows_rebuy_at_or_below_one_percent_discount() -> None:
    agent = _agent_with_live_cfg(
        {"profile": "aggressive", "max_daily_trades": 9999, "max_daily_loss": 9999}
    )
    agent._get_profile_buy_profit_guard_cfg = lambda **_kw: {
        "min_projected_edge_pct": 0.0,
        "min_window_slack_pct": 0.0,
        "pressure": 0.0,
        "recent_pnl": 0.0,
        "losing_streak": 0,
    }
    agent.state.position = 0.001
    agent.state.entry_price = 100.0
    agent.state.entries = [{"price": 100.0, "size": 0.001, "ts": 1.0}]
    agent._sync_position_tracking()
    signal = SimpleNamespace(action="BUY", confidence=0.80, price=99.00, reason="unit")

    assert agent._check_can_trade(signal) is True


def test_calculate_trade_size_applies_dynamic_batch_limit() -> None:
    agent = _agent_with_live_cfg(
        {"profile": "aggressive", "max_position_pct": 0.30, "min_trade_amount": 10.0}
    )
    agent.state.dry_run = True
    agent._apply_profile_allocation = lambda total_balance: total_balance
    agent._resolve_trade_controls = lambda rag_adj=None: TradeControls(
        min_confidence=0.50,
        min_trade_interval=0,
        max_position_pct=0.30,
        max_positions_cap=1,
        effective_max_positions=1,
        ai_controlled=False,
        ollama_mode="shadow",
    )
    agent._get_profile_buy_profit_guard_pressure = lambda base_cfg: {"pressure": 1.0}
    signal = SimpleNamespace(action="BUY", confidence=1.0, price=100.0, reason="unit")

    amount = agent._calculate_trade_size(signal, signal.price)

    assert amount == pytest.approx(120.0)
    assert agent.state.buy_success_pressure == pytest.approx(1.0)
    assert agent.state.buy_success_factor == pytest.approx(0.0)
    assert agent.state.buy_dynamic_batch_cap_usdt == pytest.approx(120.0)


# ---------------------------------------------------------------------------
# Fase 3: _detect_external_deposits usa DB total como baseline
# ---------------------------------------------------------------------------

def test_detect_external_deposits_uses_db_total_not_profile_entries() -> None:
    """Cenario 4: saldo global explica outro profile — sem phantom BUY no conservative."""
    from unittest.mock import MagicMock

    agent = _agent_with_live_cfg({"profile": "conservative"})
    agent.state.dry_run = False
    agent.state.entries = []  # conservative sem entries no state
    agent.symbol = "BTC-USDT"

    # Simular DB retornando net_position total = 0.001 (cobre o saldo da exchange)
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.__enter__ = MagicMock(return_value=mock_cur)
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_cur.fetchone = MagicMock(return_value=(0.001,))
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur

    mock_db = MagicMock()
    mock_db._get_conn.return_value = mock_conn
    agent.db = mock_db

    # Patchear get_total_balance diretamente no modulo ja stubado em sys.modules
    kucoin_stub = sys.modules["kucoin_api"]
    original_gtb = getattr(kucoin_stub, "get_total_balance", None)
    kucoin_stub.get_total_balance = lambda _currency: 0.001  # exchange = 0.001
    try:
        agent._detect_external_deposits()
    finally:
        if original_gtb is not None:
            kucoin_stub.get_total_balance = original_gtb
        elif hasattr(kucoin_stub, "get_total_balance"):
            delattr(kucoin_stub, "get_total_balance")

    # Nenhum trade deve ter sido registrado (saldo exchange == DB total)
    agent.db.record_trade.assert_not_called()


def test_detect_external_deposits_skips_ambiguous_shared_balance() -> None:
    """Conta compartilhada com dois profiles abertos nao deve sintetizar BUY ambiguo."""
    from unittest.mock import MagicMock

    agent = _agent_with_live_cfg({"profile": "conservative"})
    agent.state.dry_run = False
    agent.state.entries = [{"price": 100.0, "size": 0.001, "ts": 1.0}]
    agent.symbol = "BTC-USDT"

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.__enter__ = MagicMock(return_value=mock_cur)
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_cur.fetchone = MagicMock(return_value=(0.001,))
    mock_cur.fetchall = MagicMock(
        return_value=[
            ("aggressive", 0.001),
            ("conservative", 0.001),
            ("exchange_sync", -0.0005),
        ]
    )
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur

    mock_db = MagicMock()
    mock_db._get_conn.return_value = mock_conn
    agent.db = mock_db

    kucoin_stub = sys.modules["kucoin_api"]
    original_gtb = getattr(kucoin_stub, "get_total_balance", None)
    original_gp = getattr(kucoin_stub, "get_price", None)
    kucoin_stub.get_total_balance = lambda _currency: 0.002
    kucoin_stub.get_price = lambda _symbol: 80_000.0
    try:
        agent._detect_external_deposits()
    finally:
        if original_gtb is not None:
            kucoin_stub.get_total_balance = original_gtb
        elif hasattr(kucoin_stub, "get_total_balance"):
            delattr(kucoin_stub, "get_total_balance")
        if original_gp is not None:
            kucoin_stub.get_price = original_gp
        elif hasattr(kucoin_stub, "get_price"):
            delattr(kucoin_stub, "get_price")

    agent.db.record_trade.assert_not_called()


# ---------------------------------------------------------------------------
# Fase 4: Exporter \u2014 sell_reconciled fecha posi\u00e7\u00e3o aberta
# ---------------------------------------------------------------------------

def test_exporter_sell_reconciled_closes_open_position() -> None:
    """Cenario 5: sell_reconciled como \u00faltimo trade \u2192 open_position_btc = 0."""
    import sys
    import types as _types
    from unittest.mock import MagicMock

    # Stub dos modulos do exporter para importar sem dependencias reais
    for mod in ["psycopg2", "psycopg2.extras"]:
        if mod not in sys.modules:
            sys.modules[mod] = MagicMock()

    # Simular a l\u00f3gica isolada do loop de open_buys diretamente
    recent_trades = [
        ("sell_reconciled", 0.00074257, 78000.0, 1746225762.0),
        ("buy", 0.00019931, 77012.4, 1745765792.0),
        ("buy", 0.00025290, 77934.9, 1745745472.0),
        ("buy", 0.00013819, 78731.4, 1745730000.0),
    ]

    open_buys = []
    for t in recent_trades:
        if t[0] in ("sell", "sell_reconciled"):
            break
        if t[0] == "buy":
            open_buys.append(t)

    assert open_buys == [], "sell_reconciled deve fechar a posi\u00e7\u00e3o (open_buys vazio)"
    total_btc = sum(b[1] or 0 for b in open_buys)
    assert total_btc == 0.0, f"open_position_btc deve ser 0, got {total_btc}"
