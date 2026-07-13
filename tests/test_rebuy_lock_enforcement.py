#!/usr/bin/env python3
"""Testes — lógica BUY vs REBUY vs DCA:

  BUY  (position=0, sem histórico de venda): livre, segue regras de mercado
  REBUY (position=0, após fechar posição):   bloqueado se preço >= entrada da última venda
  DCA  (position>0, adicionando slot):       não tem rebuy lock; segue valley bounce
"""
from types import SimpleNamespace
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))

import types
sys.modules.setdefault("httpx", types.SimpleNamespace(Client=object))
sys.modules.setdefault("kucoin_api", types.SimpleNamespace(
    get_price=None, get_price_fast=None, get_orderbook=None, get_candles=None,
    get_recent_trades=None, get_balances=None, get_balance=None,
    place_market_order=None, analyze_orderbook=None, analyze_trade_flow=None,
    inner_transfer=None, _has_keys=lambda: False,
    get_fills_for_order=lambda *a, **kw: {},
    _resolve_telegram_bot_token=lambda: "",
    _resolve_telegram_chat_id=lambda: "",
))
sys.modules.setdefault("fast_model", types.SimpleNamespace(
    FastTradingModel=object, MarketState=object, Signal=object))
sys.modules.setdefault("training_db", types.SimpleNamespace(
    TrainingDatabase=object, TrainingManager=object))
sys.modules.setdefault("market_rag", types.SimpleNamespace(MarketRAG=object))

from trading_agent import BitcoinTradingAgent


def _make_agent(
    position=0.0,
    entry_price=0.0,
    last_sell_entry_price=0.0,
    *,
    ai_rebuy_lock_enabled=False,
    ai_rebuy_margin_pct=0.0,
    ai_controlled=False,
    rebuy_lock_enabled=None,
):
    agent = BitcoinTradingAgent.__new__(BitcoinTradingAgent)
    agent.symbol = "BTC-USDT"
    agent.state = SimpleNamespace(
        last_sell_entry_price=last_sell_entry_price,
        position=position,
        entry_price=entry_price,
        last_trade_time=0.0,
        target_sell_price=0.0,
        target_sell_reason="",
        entries=[{"price": entry_price, "size": 0.001, "ts": 0.0}] if position > 0 else [],
        dry_run=False,
        profile="default",
        dca_valley_low=0.0,
        logical_position_slots=1 if position > 0 else 0,
        raw_entry_count=1 if position > 0 else 0,
    )
    rag_adj = SimpleNamespace(
        ai_rebuy_lock_enabled=ai_rebuy_lock_enabled,
        ai_rebuy_margin_pct=ai_rebuy_margin_pct,
    )
    agent.market_rag = SimpleNamespace(get_current_adjustment=lambda: rag_adj)
    agent._clear_trade_block = lambda: None
    agent._resolve_trade_controls = lambda rag_adj=None: SimpleNamespace(
        min_confidence=0.5, min_trade_interval=0, max_position_pct=0.5,
        max_positions_cap=4, effective_max_positions=4,
        ai_controlled=ai_controlled, ollama_mode="shadow",
    )
    agent._analyze_signal_context = lambda rag_adj, signal: dict(
        penalty_score=0.0, bonus_score=0.0, strong_bearish=False,
        hard_block_buy=False, net_score=0.0, penalties=[], bonuses=[],
    )
    agent._get_guardrail_sell_verdict = lambda price: None
    agent._resolve_buy_gate_limits = lambda rag_adj, signal: dict(
        ai_buy_target=0.0, extra_discount_pct=0.0, uplift_pct=0.0,
        tolerance_pct=0.0, effective_buy_target=0.0, base_buy_ceiling=0.0,
        effective_buy_ceiling=0.0, trade_window=None,
        window_entry_low=0.0, window_entry_high=0.0, used_trade_window=False,
    )
    agent._get_profile_buy_profit_guard_cfg = lambda current_price=None: dict(
        min_projected_edge_pct=0.0, min_window_slack_pct=0.0,
        pressure=0.0, recent_pnl=0.0, losing_streak=0,
    )
    agent.db = SimpleNamespace(
        count_trades_since=lambda **kw: 0, get_pnl_since=lambda **kw: 0.0)
    cfg = {}
    if rebuy_lock_enabled is not None:
        cfg["rebuy_lock_enabled"] = rebuy_lock_enabled
    agent._load_live_config = lambda: cfg
    agent._current_profile = lambda: "default"
    agent._sync_target_sell_with_ai = lambda reason_prefix="IA": None
    agent._get_rebuy_discount_pct = lambda: 0.003
    return agent


# ── BUY fresco (sem histórico de venda) ─────────────────────────────────────

def test_fresh_buy_no_sell_history_allowed():
    """Primeira entrada: sem histórico de venda → BUY livre."""
    agent = _make_agent(position=0.0, last_sell_entry_price=0.0)
    sig = SimpleNamespace(action="BUY", price=70000.0, confidence=0.9, reason="unit")
    assert agent._check_can_trade(sig) is True


# ── REBUY (position=0, após fechar posição) ──────────────────────────────────

def test_rebuy_blocked_when_price_equal_to_last_sell_entry():
    """Reentrada ao mesmo preço da entrada da posição vendida: bloqueado."""
    agent = _make_agent(position=0.0, last_sell_entry_price=70000.0)
    sig = SimpleNamespace(action="BUY", price=70000.0, confidence=0.9, reason="unit")
    result = agent._check_can_trade(sig)
    assert result is False
    assert agent.state.last_trade_block_reason == "buy_rebuy_lock_last_sell"


def test_rebuy_blocked_when_price_above_last_sell_entry():
    """Reentrada acima da entrada da posição vendida: bloqueado."""
    agent = _make_agent(position=0.0, last_sell_entry_price=70000.0)
    sig = SimpleNamespace(action="BUY", price=71000.0, confidence=0.9, reason="unit")
    result = agent._check_can_trade(sig)
    assert result is False
    assert agent.state.last_trade_block_reason == "buy_rebuy_lock_last_sell"


def test_rebuy_allowed_when_price_below_last_sell_entry():
    """Reentrada abaixo da entrada da posição vendida: permitido."""
    agent = _make_agent(position=0.0, last_sell_entry_price=70000.0)
    sig = SimpleNamespace(action="BUY", price=69500.0, confidence=0.9, reason="unit")
    assert agent._check_can_trade(sig) is True


# ── DCA (position>0, adicionando novo slot) ──────────────────────────────────

def test_dca_no_rebuy_lock_applies():
    """Com posição aberta e last_sell_entry_price > 0, rebuy lock se aplica a DCA também."""
    # last_sell_entry_price=70000, price=70000 → rebuy lock bloqueia (price >= last_sell)
    agent = _make_agent(position=0.001, entry_price=70000.0, last_sell_entry_price=70000.0)
    sig = SimpleNamespace(action="BUY", price=70000.0, confidence=0.9, reason="unit")
    result = agent._check_can_trade(sig)
    assert result is False
    assert agent.state.last_trade_block_reason == "buy_rebuy_lock_last_sell"


def test_dca_allowed_below_discount_trigger_with_bounce():
    """DCA permitido quando preço caiu abaixo do last_sell E do desconto mínimo E houve bounce do vale."""
    agent = _make_agent(position=0.001, entry_price=70000.0, last_sell_entry_price=70000.0)
    # Rebuy lock: price=69400 < last_sell=70000 → passa
    # Gatilho desconto = 70000 * (1 - 0.003) = 69790
    # Vale = 69000; bounce_trigger = 69000 * (1 + DCA_VALLEY_BOUNCE_PCT=0.004) = 69276
    # Preço = 69400 → <= 69790 (rebuy_discount ✓) e >= 69276 (valley bounce ✓)
    agent.state.dca_valley_low = 69000.0
    sig = SimpleNamespace(action="BUY", price=69400.0, confidence=0.9, reason="unit")
    assert agent._check_can_trade(sig) is True


def test_rebuy_blocked_even_with_open_position():
    """REBUY bloqueado mesmo com posição aberta — lock se aplica a todos os BUYs."""
    # Tem 1 slot aberto, mas last_sell_entry_price > 0 (outro slot foi vendido)
    agent = _make_agent(position=0.001, entry_price=68000.0, last_sell_entry_price=70000.0)
    sig = SimpleNamespace(action="BUY", price=70000.0, confidence=0.9, reason="unit")
    result = agent._check_can_trade(sig)
    assert result is False
    assert agent.state.last_trade_block_reason == "buy_rebuy_lock_last_sell"


def test_rebuy_allowed_even_with_open_position_when_below_last_sell():
    """REBUY permitido com posição aberta quando preço < entrada da última venda."""
    agent = _make_agent(position=0.001, entry_price=68000.0, last_sell_entry_price=70000.0)
    # price < 70000 AND price <= rebuy_trigger (68000*0.997=67796)
    # → rebuy lock passes, but valley bounce may block (check separately)
    sig = SimpleNamespace(action="BUY", price=69500.0, confidence=0.9, reason="unit")
    result = agent._check_can_trade(sig)
    # rebuy lock: 69500 < 70000 → passes
    # rebuy_discount: entry=68000, trigger=67796, price=69500 > 67796 → blocked by buy_rebuy_discount
    assert result is False
    assert agent.state.last_trade_block_reason == "buy_rebuy_discount"


# ── REBUY via IA (RAG) com config estático desligado ─────────────────────────

def test_ai_rebuy_blocks_when_config_disabled_but_rag_enabled():
    """rebuy_lock_enabled=false não impede trava quando IA ativa rebuy."""
    agent = _make_agent(
        position=0.0,
        last_sell_entry_price=70000.0,
        ai_rebuy_lock_enabled=True,
        ai_rebuy_margin_pct=0.0,
        ai_controlled=True,
        rebuy_lock_enabled=False,
    )
    sig = SimpleNamespace(action="BUY", price=70000.0, confidence=0.9, reason="unit")
    assert agent._check_can_trade(sig) is False
    assert agent.state.last_trade_block_reason == "buy_rebuy_lock_last_sell"


def test_ai_rebuy_margin_requires_deeper_discount():
    """Margem IA exige preço abaixo de last_sell * (1 - margin_pct)."""
    agent = _make_agent(
        position=0.0,
        last_sell_entry_price=70000.0,
        ai_rebuy_lock_enabled=True,
        ai_rebuy_margin_pct=0.01,
        ai_controlled=True,
        rebuy_lock_enabled=False,
    )
    # 70000 * 0.99 = 69300 — abaixo disso permitido
    sig_block = SimpleNamespace(action="BUY", price=69500.0, confidence=0.9, reason="unit")
    assert agent._check_can_trade(sig_block) is False
    assert agent.state.last_trade_block_reason == "buy_rebuy_lock_last_sell"

    sig_ok = SimpleNamespace(action="BUY", price=69200.0, confidence=0.9, reason="unit")
    assert agent._check_can_trade(sig_ok) is True


def test_ai_rebuy_off_allows_reentry_when_config_disabled():
    """Sem IA nem config, reentrada após venda é livre."""
    agent = _make_agent(
        position=0.0,
        last_sell_entry_price=70000.0,
        ai_rebuy_lock_enabled=False,
        ai_controlled=True,
        rebuy_lock_enabled=False,
    )
    sig = SimpleNamespace(action="BUY", price=71000.0, confidence=0.9, reason="unit")
    assert agent._check_can_trade(sig) is True
