#!/usr/bin/env python3
"""Testes — lógica BUY vs REBUY vs DCA:

  BUY  (position=0, sem histórico de venda): livre, segue regras de mercado
  REBUY (position=0, após fechar posição):   bloqueado se preço >= teto do envelope
  DCA  (position>0, adicionando slot):       não tem rebuy lock; segue valley bounce

Envelope determinístico (2026-07-16): o REBUY lock é um envelope mecânico
sempre ativo — fase grace (teto = last_sell), fase decay (teto sobe
decay_pct_per_hour) e expiração (max_premium_pct). A IA só pode APERTAR o
teto (ai_rebuy_margin_pct); falha da IA ou rebuy_lock_enabled=false no
config NUNCA desligam o envelope (fix do incidente "falha da IA = falha do
freio"). Contrato antigo em que ai_rebuy_lock_enabled=False liberava a
recompra foi intencionalmente invertido.
"""
import time
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
    last_sell_age_hours=0.0,
    rebuy_envelope=None,
):
    agent = BitcoinTradingAgent.__new__(BitcoinTradingAgent)
    agent.symbol = "BTC-USDT"
    agent.state = SimpleNamespace(
        last_sell_entry_price=last_sell_entry_price,
        last_sell_ts=(
            time.time() - last_sell_age_hours * 3600.0
            if last_sell_entry_price > 0 else 0.0
        ),
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
    if rebuy_envelope is not None:
        cfg["rebuy_envelope"] = rebuy_envelope
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
    """Margem IA exige preço abaixo de last_sell * (1 - margin_pct).

    Novo contrato: a margem da IA só se aplica com rebuy_lock_enabled=True
    (config false desliga apenas a margem — ver
    test_config_disabled_only_strips_ai_margin)."""
    agent = _make_agent(
        position=0.0,
        last_sell_entry_price=70000.0,
        ai_rebuy_lock_enabled=True,
        ai_rebuy_margin_pct=0.01,
        ai_controlled=True,
        rebuy_lock_enabled=True,
    )
    # 70000 * 0.99 = 69300 — abaixo disso permitido
    sig_block = SimpleNamespace(action="BUY", price=69500.0, confidence=0.9, reason="unit")
    assert agent._check_can_trade(sig_block) is False
    assert agent.state.last_trade_block_reason == "buy_rebuy_lock_last_sell"

    sig_ok = SimpleNamespace(action="BUY", price=69200.0, confidence=0.9, reason="unit")
    assert agent._check_can_trade(sig_ok) is True


def test_envelope_blocks_in_grace_even_with_ai_off_and_config_off():
    """CONTRATO INVERTIDO (fix do incidente): BULLISH (ai_rebuy_lock_enabled=False)
    + config desligado NÃO liberam mais a recompra durante a graça — o envelope
    mecânico continua valendo."""
    agent = _make_agent(
        position=0.0,
        last_sell_entry_price=70000.0,
        ai_rebuy_lock_enabled=False,
        ai_controlled=True,
        rebuy_lock_enabled=False,
    )
    sig = SimpleNamespace(action="BUY", price=71000.0, confidence=0.9, reason="unit")
    assert agent._check_can_trade(sig) is False
    assert agent.state.last_trade_block_reason == "buy_rebuy_lock_last_sell"


# ── Envelope determinístico: grace → decay → expired ─────────────────────────

def test_envelope_blocks_when_ai_cold_and_config_disabled():
    """Regressão do incidente 'falha da IA = falha do freio': IA fria
    (ai_controlled=False) + rebuy_lock_enabled=false → envelope ainda bloqueia."""
    agent = _make_agent(
        position=0.0,
        last_sell_entry_price=70000.0,
        ai_controlled=False,
        rebuy_lock_enabled=False,
    )
    sig = SimpleNamespace(action="BUY", price=70000.0, confidence=0.9, reason="unit")
    assert agent._check_can_trade(sig) is False
    assert agent.state.last_trade_block_reason == "buy_rebuy_lock_last_sell"
    assert agent.state.last_trade_block_context["rebuy_phase"] == "grace"


def test_envelope_decay_raises_ceiling():
    """Após a graça o teto sobe decay_pct_per_hour: 6h de idade, graça 2h,
    0.25%/h → prêmio 1%. Preço +0.5% permitido; +1.5% bloqueado."""
    kwargs = dict(
        position=0.0,
        last_sell_entry_price=70000.0,
        last_sell_age_hours=6.0,
        rebuy_envelope={"grace_hours": 2, "decay_pct_per_hour": 0.25, "max_premium_pct": 5.0},
    )
    agent = _make_agent(**kwargs)
    sig_ok = SimpleNamespace(action="BUY", price=70000.0 * 1.005, confidence=0.9, reason="unit")
    assert agent._check_can_trade(sig_ok) is True

    agent = _make_agent(**kwargs)
    sig_block = SimpleNamespace(action="BUY", price=70000.0 * 1.015, confidence=0.9, reason="unit")
    assert agent._check_can_trade(sig_block) is False
    assert agent.state.last_trade_block_reason == "buy_rebuy_lock_last_sell"
    assert agent.state.last_trade_block_context["rebuy_phase"] == "decay"


def test_envelope_expires_after_max_premium():
    """Idade 23h (graça 2h + 21h×0.25%/h = 5.25% ≥ 5%): envelope expira,
    BUY permitido e lock limpo do estado."""
    agent = _make_agent(
        position=0.0,
        last_sell_entry_price=70000.0,
        last_sell_age_hours=23.0,
    )
    sig = SimpleNamespace(action="BUY", price=75000.0, confidence=0.9, reason="unit")
    assert agent._check_can_trade(sig) is True
    assert agent.state.last_sell_entry_price == 0.0
    assert agent.state.last_sell_ts == 0.0


def test_ai_margin_tightens_within_decay_envelope():
    """Margem da IA aperta o teto decaído: 6h → envelope +1%; margem 1% →
    teto efetivo = last_sell×1.01×0.99. Preço entre os dois tetos: bloqueado."""
    agent = _make_agent(
        position=0.0,
        last_sell_entry_price=70000.0,
        last_sell_age_hours=6.0,
        ai_rebuy_lock_enabled=True,
        ai_rebuy_margin_pct=0.01,
        ai_controlled=True,
        rebuy_lock_enabled=True,
    )
    envelope_ceiling = 70000.0 * 1.01          # 70700
    effective = envelope_ceiling * 0.99        # 69993
    between = (effective + envelope_ceiling) / 2
    sig = SimpleNamespace(action="BUY", price=between, confidence=0.9, reason="unit")
    assert agent._check_can_trade(sig) is False
    assert agent.state.last_trade_block_reason == "buy_rebuy_lock_last_sell"
    assert agent.state.last_trade_block_context["rebuy_margin_pct"] == 0.01


def test_config_disabled_only_strips_ai_margin():
    """rebuy_lock_enabled=false remove apenas a margem da IA — o envelope fica.
    Na graça: preço == last_sell bloqueado; preço 0.5% abaixo permitido
    (a margem de 1% da IA teria bloqueado, mas foi desligada pelo config)."""
    kwargs = dict(
        position=0.0,
        last_sell_entry_price=70000.0,
        ai_rebuy_lock_enabled=True,
        ai_rebuy_margin_pct=0.01,
        ai_controlled=True,
        rebuy_lock_enabled=False,
    )
    agent = _make_agent(**kwargs)
    sig_block = SimpleNamespace(action="BUY", price=70000.0, confidence=0.9, reason="unit")
    assert agent._check_can_trade(sig_block) is False

    agent = _make_agent(**kwargs)
    sig_ok = SimpleNamespace(action="BUY", price=70000.0 * 0.995, confidence=0.9, reason="unit")
    assert agent._check_can_trade(sig_ok) is True


def test_missing_ts_self_heals_to_grace():
    """Estado legado (last_sell_entry_price>0 sem last_sell_ts): self-heal —
    assume 'agora' como âncora (graça) e bloqueia."""
    agent = _make_agent(position=0.0, last_sell_entry_price=70000.0)
    agent.state.last_sell_ts = 0.0  # simula estado antigo sem âncora
    sig = SimpleNamespace(action="BUY", price=70000.0, confidence=0.9, reason="unit")
    assert agent._check_can_trade(sig) is False
    assert agent.state.last_sell_ts > 0  # âncora self-healed


def test_block_context_reports_phase_and_ceiling():
    """Contexto do bloqueio (→ decisions.features) carrega fase, teto e idade."""
    agent = _make_agent(
        position=0.0,
        last_sell_entry_price=70000.0,
        last_sell_age_hours=6.0,
    )
    sig = SimpleNamespace(action="BUY", price=72000.0, confidence=0.9, reason="unit")
    assert agent._check_can_trade(sig) is False
    ctx = agent.state.last_trade_block_context
    assert ctx["rebuy_phase"] == "decay"
    assert ctx["rebuy_max_price"] > 70000.0            # teto decaído acima do last_sell
    assert ctx["rebuy_envelope_ceiling"] >= ctx["rebuy_max_price"]
    assert 5.5 < ctx["rebuy_elapsed_hours"] < 6.5
