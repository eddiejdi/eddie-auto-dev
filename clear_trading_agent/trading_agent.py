#!/usr/bin/env python3
"""
Clear Trading Agent — Agente de trading para B3 (Clear/MT5).

Agente autônomo que opera ações e minicontratos na bolsa brasileira
via MetaTrader 5 Bridge durante horário de pregão (10:00–17:55 BRT).

Adaptado do btc_trading_agent/trading_agent.py com foco em:
  - Horário de mercado B3
  - Valores em BRL
  - Volume em lotes (não fracionário como crypto)
  - Integração MT5 Bridge REST
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

# Adicionar o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clear_trading_agent.mt5_api import (
    get_price,
    get_price_fast,
    get_candles,
    place_market_order,
    place_limit_order,
    get_positions,
    get_account_info,
    get_balance,
    get_equity,
    analyze_spread,
    analyze_trade_flow,
    get_clear_connection_status,
)
from clear_trading_agent.fast_model import (
    FastTradingModel,
    MarketState,
    Signal,
    is_market_open,
    minutes_to_market_open,
)
from clear_trading_agent.training_db import TrainingDatabase
from clear_trading_agent.market_rag import MarketRAG
from clear_trading_agent.tax_guardrails import TaxTracker

# ====================== CONFIGURAÇÃO ======================
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "agent.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def _resolve_process_dry_run(cli_live: bool, loaded_cfg: Optional[Dict[str, Any]] = None) -> bool:
    """Resolve o modo efetivo do processo com override seguro pelo config."""
    requested_dry_run = not cli_live
    if requested_dry_run:
        return True
    cfg = loaded_cfg or {}
    if cfg.get("dry_run") is True:
        return True
    if "live_mode" in cfg and not bool(cfg.get("live_mode")):
        return True
    return False


# ====================== CONSTANTES ======================
_config_file = os.environ.get("CLEAR_CONFIG_FILE", "config.json")
_config_path = Path(__file__).parent / _config_file
try:
    with open(_config_path) as _cf:
        _config = json.load(_cf)
    DEFAULT_SYMBOL = _config.get("symbol", "PETR4")
except Exception as _e:
    logging.getLogger(__name__).debug("Config load fallback: %s", _e)
    _config = {}
    DEFAULT_SYMBOL = "PETR4"

POLL_INTERVAL = _config.get("poll_interval", 5)
MIN_TRADE_INTERVAL = _config.get("min_trade_interval", 180)
MIN_CONFIDENCE = _config.get("min_confidence", 0.6)
MIN_TRADE_AMOUNT = _config.get("min_trade_amount", 100)  # R$100 mínimo
MAX_POSITION_PCT = _config.get("max_position_pct", 0.5)
TRADING_FEE_PCT = _config.get("trading_fee_pct", 0.0003)  # Clear: ~0.03% (corretagem)
MAX_DAILY_TRADES = _config.get("max_daily_trades", 30)
MAX_DAILY_LOSS = _config.get("max_daily_loss", 500)  # R$500
MAX_POSITIONS = _config.get("max_positions", 3)
PROFILE = _config.get("profile", "default")


# ====================== ESTADO DO AGENTE ======================
@dataclass
class AgentState:
    """Estado atual do agente de trading B3."""

    running: bool = False
    symbol: str = DEFAULT_SYMBOL
    asset_class: str = "equity"  # "equity" ou "futures"
    position: float = 0.0       # Quantidade (ações / contratos)
    position_value: float = 0.0 # Valor em BRL
    entry_price: float = 0.0    # Preço médio ponderado
    position_count: int = 0     # Número de entradas
    entries: list = field(default_factory=list)
    last_trade_time: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    total_pnl: float = 0.0
    dry_run: bool = True
    last_sell_entry_price: float = 0.0
    trailing_high: float = 0.0
    target_sell_price: float = 0.0
    target_sell_reason: str = ""
    sell_count: int = 0
    daily_trades: int = 0
    daily_pnl: float = 0.0
    daily_date: str = ""
    profile: str = "default"
    start_time: float = 0.0

    def to_dict(self) -> Dict:
        """Serializa estado para dicionário."""
        return {
            "running": self.running,
            "symbol": self.symbol,
            "asset_class": self.asset_class,
            "position_qty": self.position,
            "position_brl": self.position_value,
            "entry_price": self.entry_price,
            "position_count": self.position_count,
            "entries": self.entries,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "win_rate": self.winning_trades / max(self.total_trades, 1),
            "total_pnl": self.total_pnl,
            "dry_run": self.dry_run,
            "last_sell_entry_price": self.last_sell_entry_price,
            "target_sell_price": self.target_sell_price,
            "target_sell_reason": self.target_sell_reason,
            "profile": self.profile,
            "daily_trades": self.daily_trades,
            "daily_pnl": self.daily_pnl,
        }


@dataclass
class TradeControls:
    """Controles de risco efetivos usados pelo trading loop."""

    min_confidence: float
    min_trade_interval: int
    max_position_pct: float
    max_positions_cap: int
    effective_max_positions: int
    ai_controlled: bool
    ollama_mode: str = "shadow"


# ====================== AGENTE PRINCIPAL ======================
class ClearTradingAgent:
    """Agente de trading para B3 — ações e minicontratos via MT5 Bridge."""

    def __init__(
        self,
        symbol: str = DEFAULT_SYMBOL,
        dry_run: bool = True,
        config_name: Optional[str] = None,
    ) -> None:
        self.symbol = symbol
        self.config_name = config_name or os.environ.get("CLEAR_CONFIG_FILE", _config_file)
        self.config_path = Path(__file__).parent / self.config_name
        self.config = self._load_live_config()

        # Determinar classe de ativo
        asset_class = self.config.get("asset_class", "equity")
        if symbol.startswith(("WIN", "WDO", "IND", "DOL")):
            asset_class = "futures"

        self.state = AgentState(
            symbol=symbol,
            dry_run=dry_run,
            profile=self.config.get("profile", PROFILE),
            asset_class=asset_class,
        )
        self.model = FastTradingModel(symbol)
        self.db = TrainingDatabase()

        # Market RAG
        rag_recalibrate = self.config.get("rag_recalibrate_interval", 300)
        rag_snapshot = self.config.get("rag_snapshot_interval", 30)
        self.market_rag = MarketRAG(
            symbol=symbol,
            profile=self.config.get("profile", PROFILE),
            recalibrate_interval=rag_recalibrate,
            snapshot_interval=rag_snapshot,
        )
        self._rag_apply_cycle = 0

        # Tax Guardrails — otimização tributária B3
        tax_cfg = self.config.get("tax_guardrails", {})
        self.tax_tracker = TaxTracker(
            config=tax_cfg,
            persist_path=Path(__file__).parent / "data" / f"tax_state_{symbol}.json",
        )

        # Threading
        self._stop_event = threading.Event()
        self._trade_lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._last_trade_id = 0

        # Callbacks
        self._on_signal_callbacks: list = []
        self._on_trade_callbacks: list = []

        self.state.start_time = time.time()
        self._log_clear_integration_status()
        logger.info(
            "🤖 Clear Agent initialized: %s (%s, dry_run=%s, profile=%s)",
            symbol, asset_class, dry_run, self.state.profile,
        )

    def _log_clear_integration_status(self) -> None:
        """Registra status sanitizado da integração com a Clear/MT5."""
        try:
            status = get_clear_connection_status(check_bridge_health=False)
            logger.info(
                "🔐 Clear integration: bridge_healthy=%s api_key=%s broker_user=%s broker_pass=%s",
                status.get("bridge_healthy", False),
                status.get("bridge_api_key_configured", False),
                status.get("broker_username_configured", False),
                status.get("broker_password_configured", False),
            )
        except Exception as exc:
            logger.warning("⚠️ Falha ao validar integração Clear: %s", exc)

    def _load_live_config(self) -> Dict:
        """Carrega config ativo da instância."""
        try:
            with open(self.config_path) as cfg_file:
                return json.load(cfg_file)
        except Exception as e:
            logger.debug("Config live reload fallback: %s", e)
            return dict(_config)

    def _get_runtime_risk_caps(self) -> Dict[str, Any]:
        """Retorna caps/configs ativos da instância."""
        live_cfg = self._load_live_config()
        return {
            "min_confidence": float(live_cfg.get("min_confidence", MIN_CONFIDENCE)),
            "min_trade_interval": int(live_cfg.get("min_trade_interval", MIN_TRADE_INTERVAL)),
            "min_trade_amount": float(live_cfg.get("min_trade_amount", MIN_TRADE_AMOUNT)),
            "max_position_pct": max(0.01, float(live_cfg.get("max_position_pct", MAX_POSITION_PCT))),
            "max_positions": max(1, int(live_cfg.get("max_positions", MAX_POSITIONS))),
        }

    def _get_runtime_trade_day_limits(self) -> Dict[str, float]:
        """Retorna limites diários ativos."""
        live_cfg = self._load_live_config()
        return {
            "max_daily_trades": max(0, int(live_cfg.get("max_daily_trades", MAX_DAILY_TRADES))),
            "max_daily_loss": max(0.0, float(live_cfg.get("max_daily_loss", MAX_DAILY_LOSS))),
        }

    def _resolve_trade_controls(self, rag_adj=None) -> TradeControls:
        """Resolve controles efetivos de trade a partir de config e RAG."""
        rag_adj = rag_adj or self.market_rag.get_current_adjustment()
        caps = self._get_runtime_risk_caps()
        ai_controlled = rag_adj.similar_count >= 3

        if ai_controlled:
            min_confidence = float(getattr(rag_adj, "applied_min_confidence", rag_adj.ai_min_confidence))
            min_trade_interval = int(getattr(rag_adj, "applied_min_trade_interval", rag_adj.ai_min_trade_interval))
            max_positions_cap = int(getattr(rag_adj, "applied_max_positions", caps["max_positions"]) or caps["max_positions"])
            effective_max_positions = min(max_positions_cap, int(rag_adj.ai_max_entries or max_positions_cap))
            max_position_pct = float(getattr(rag_adj, "applied_max_position_pct", caps["max_position_pct"]) or caps["max_position_pct"])
        else:
            min_confidence = caps["min_confidence"]
            min_trade_interval = caps["min_trade_interval"]
            max_positions_cap = caps["max_positions"]
            effective_max_positions = caps["max_positions"]
            max_position_pct = caps["max_position_pct"]

        return TradeControls(
            min_confidence=max(0.0, min_confidence),
            min_trade_interval=max(1, min_trade_interval),
            max_position_pct=max(0.01, min(max_position_pct, caps["max_position_pct"])),
            max_positions_cap=max(1, max_positions_cap),
            effective_max_positions=max(1, effective_max_positions),
            ai_controlled=ai_controlled,
            ollama_mode=str(getattr(rag_adj, "ollama_mode", "shadow") or "shadow"),
        )

    # ====================== MARKET STATE ======================

    def _get_market_state(self) -> Optional[MarketState]:
        """Coleta estado atual do mercado via MT5 Bridge."""
        try:
            price = get_price_fast(self.symbol, timeout=3)
            if not price:
                return None

            # Atualizar indicadores
            self.model.update(price)

            # Candles para indicadores (uma vez a cada 100 ciclos)
            if self._rag_apply_cycle % 100 == 1:
                try:
                    candles = get_candles(self.symbol, "1m", limit=200)
                    if candles:
                        self.model.update_from_candles(candles)
                except Exception as e:
                    logger.debug("Candles fetch: %s", e)

            # Spread analysis
            spread_data = {}
            try:
                spread_data = analyze_spread(self.symbol)
            except Exception as e:
                logger.debug("Spread analysis: %s", e)

            # Trade flow
            flow_data = {}
            try:
                flow_data = analyze_trade_flow(self.symbol)
            except Exception as e:
                logger.debug("Trade flow: %s", e)

            return self.model.get_market_state(
                price=price,
                bid=spread_data.get("bid", 0),
                ask=spread_data.get("ask", 0),
                trade_flow=flow_data.get("flow_bias", 0),
            )

        except Exception as e:
            logger.warning("⚠️ Market state error: %s", e)
            return None

    # ====================== TRADE CHECKS ======================

    def _check_daily_reset(self) -> None:
        """Reset contadores diários se mudou de dia."""
        today = str(date.today())
        if self.state.daily_date != today:
            if self.state.daily_date:
                logger.info(
                    "📅 Day reset (%s → %s): trades=%d, pnl=R$%.2f",
                    self.state.daily_date, today,
                    self.state.daily_trades, self.state.daily_pnl,
                )
            self.state.daily_trades = 0
            self.state.daily_pnl = 0.0
            self.state.daily_date = today

    def _check_can_trade(self, signal: Signal) -> bool:
        """Verifica se pode executar o trade."""
        self._check_daily_reset()

        # Horário de mercado
        if not is_market_open():
            return False

        rag_adj = self.market_rag.get_current_adjustment()
        controls = self._resolve_trade_controls(rag_adj)

        # Confiança mínima
        if signal.confidence < controls.min_confidence:
            return False

        # Cooldown entre trades
        elapsed = time.time() - self.state.last_trade_time
        if elapsed < controls.min_trade_interval:
            return False

        # Limites diários
        day_limits = self._get_runtime_trade_day_limits()
        if self.state.daily_trades >= day_limits["max_daily_trades"]:
            logger.warning("⚠️ Daily trade limit reached: %d", self.state.daily_trades)
            return False
        if self.state.daily_pnl <= -day_limits["max_daily_loss"]:
            logger.warning("⚠️ Daily loss limit reached: R$%.2f", self.state.daily_pnl)
            return False

        # BUY-specific checks
        if signal.action == "BUY":
            if self.state.position_count >= controls.effective_max_positions:
                return False
            # Rebuy lock
            if rag_adj.ai_rebuy_lock_enabled and self.state.last_sell_entry_price > 0:
                margin = self.state.last_sell_entry_price * (1 - rag_adj.ai_rebuy_margin_pct)
                if signal.price >= margin:
                    return False

        # SELL-specific checks
        if signal.action == "SELL":
            if self.state.position <= 0:
                return False
            # Tax guardrail: trava R$20k e day trade
            tax_decision = self.tax_tracker.check_sell_allowed(
                symbol=self.symbol,
                asset_class=self.state.asset_class,
                volume=self.state.position,
                price=signal.price,
            )
            if not tax_decision.allowed:
                logger.warning("🏛️ TAX BLOCK: %s", tax_decision.reason)
                return False

        return True

    # ====================== TRADE SIZE ======================

    def _calculate_trade_size(self, signal: Signal, price: float) -> float:
        """Calcula o tamanho do trade em BRL.

        Returns:
            Valor em BRL para o trade ou 0 se insuficiente.
        """
        try:
            if signal.action == "SELL":
                return self.state.position  # Vender tudo

            # BUY: calcular com base no saldo e AI sizing
            if self.state.dry_run:
                brl_balance = float(self.config.get("dry_run_balance", 10_000))
            else:
                brl_balance = get_balance()

            if brl_balance <= 0:
                return 0

            rag_adj = self.market_rag.get_current_adjustment()
            size_pct = rag_adj.ai_position_size_pct if rag_adj.similar_count >= 3 else 0.04
            amount_brl = brl_balance * size_pct

            # Cap por max_position_pct
            caps = self._get_runtime_risk_caps()
            max_total = brl_balance * caps["max_position_pct"]
            current_value = self.state.position * price if self.state.position > 0 else 0
            available = max_total - current_value
            amount_brl = min(amount_brl, available)

            # Mínimo
            if amount_brl < caps["min_trade_amount"]:
                return 0

            return amount_brl

        except Exception as e:
            logger.warning("⚠️ Trade size calculation error: %s", e)
            return 0

    def _calculate_lot_qty(self, amount_brl: float, price: float) -> int:
        """Converte valor BRL em quantidade de lotes inteiros.

        Para ações: lote mínimo = 100 ações (padrão B3).
        Para minicontratos: 1 contrato.
        """
        if price <= 0:
            return 0

        if self.state.asset_class == "futures":
            # Minicontratos: margem de garantia
            # WIN: ~20% do valor | WDO: ~15% do valor
            margin_pct = 0.20 if self.symbol.startswith("WIN") else 0.15
            contracts = int(amount_brl / (price * margin_pct))
            return max(1, contracts) if amount_brl >= price * margin_pct else 0

        # Equities: lote de 100 ações
        shares = int(amount_brl / price)
        lot_qty = (shares // 100) * 100
        return lot_qty if lot_qty >= 100 else 0

    # ====================== TRADE EXECUTION ======================

    def _execute_trade(self, signal: Signal, price: float, force: bool = False) -> bool:
        """Executa trade no MT5 Bridge."""
        with self._trade_lock:
            try:
                if signal.action == "BUY":
                    amount_brl = self._calculate_trade_size(signal, price)
                    if amount_brl <= 0:
                        logger.warning("⚠️ Trade amount insuficiente: R$%.2f", amount_brl)
                        return False

                    qty = self._calculate_lot_qty(amount_brl, price)
                    if qty <= 0:
                        logger.warning("⚠️ Quantidade insuficiente para lote mínimo")
                        return False

                    order_id = None
                    actual_price = price

                    if self.state.dry_run:
                        cost = qty * price * (1 + TRADING_FEE_PCT)
                        logger.info(
                            "🔵 [DRY] BUY #%d %d %s @ R$%.2f (R$%.2f, fee=%.2f%%)",
                            self.state.position_count + 1, qty, self.symbol,
                            price, cost, TRADING_FEE_PCT * 100,
                        )
                    else:
                        result = place_market_order(self.symbol, "buy", volume=float(qty))
                        if not result.get("success"):
                            logger.error("❌ Order failed: %s", result)
                            return False
                        order_id = result.get("order_id")
                        actual_price = result.get("price", price)

                    # Acumular posição
                    old_pos = self.state.position
                    old_entry = self.state.entry_price
                    self.state.position += qty
                    if old_pos > 0 and old_entry > 0:
                        self.state.entry_price = (old_pos * old_entry + qty * actual_price) / self.state.position
                    else:
                        self.state.entry_price = actual_price
                    self.state.position_count += 1
                    self.state.entries.append({
                        "price": actual_price, "qty": qty, "ts": time.time(),
                    })

                    logger.info(
                        "📊 Position: %d %s (%d entries, avg R$%.2f)",
                        int(self.state.position), self.symbol,
                        self.state.position_count, self.state.entry_price,
                    )

                    # Target de lucro (IA)
                    rag_adj = self.market_rag.get_current_adjustment()
                    ai_tp = max(rag_adj.ai_take_profit_pct, 0.015)
                    tp_target = self.state.entry_price * (1 + ai_tp)
                    self.state.target_sell_price = tp_target
                    self.state.target_sell_reason = rag_adj.ai_take_profit_reason
                    logger.info(
                        "🎯 Target SELL: R$%.2f (+%.2f%% sobre avg R$%.2f)",
                        tp_target, ai_tp * 100, self.state.entry_price,
                    )

                    # Registrar
                    trade_id = self.db.record_trade(
                        symbol=self.symbol,
                        side="buy",
                        price=actual_price,
                        volume=qty,
                        order_type="market",
                        order_id=str(order_id) if order_id else None,
                        dry_run=self.state.dry_run,
                        asset_class=self.state.asset_class,
                        commission=qty * actual_price * TRADING_FEE_PCT,
                    )
                    self._last_trade_id = trade_id
                    self.state.trailing_high = actual_price

                    # Tax: registrar compra
                    self.tax_tracker.record_buy(
                        symbol=self.symbol,
                        asset_class=self.state.asset_class,
                        volume=qty,
                        price=actual_price,
                        commission=qty * actual_price * TRADING_FEE_PCT,
                    )

                elif signal.action == "SELL":
                    qty = int(self.state.position)
                    if qty <= 0:
                        return False

                    # PnL líquido
                    gross_pnl = (price - self.state.entry_price) * qty
                    sell_fee = price * qty * TRADING_FEE_PCT
                    buy_fee = self.state.entry_price * qty * TRADING_FEE_PCT
                    pnl = gross_pnl - sell_fee - buy_fee
                    pnl_pct = ((price / self.state.entry_price) - 1) * 100 if self.state.entry_price > 0 else 0

                    order_id = None
                    if self.state.dry_run:
                        logger.info(
                            "🔴 [DRY] SELL %d %s @ R$%.2f (PnL: R$%.2f / %.2f%%)",
                            qty, self.symbol, price, pnl, pnl_pct,
                        )
                    else:
                        result = place_market_order(self.symbol, "sell", volume=float(qty))
                        if not result.get("success"):
                            logger.error("❌ Order failed: %s", result)
                            return False
                        order_id = result.get("order_id")

                    # Registrar
                    trade_id = self.db.record_trade(
                        symbol=self.symbol,
                        side="sell",
                        price=price,
                        volume=qty,
                        order_type="market",
                        order_id=str(order_id) if order_id else None,
                        dry_run=self.state.dry_run,
                        asset_class=self.state.asset_class,
                        commission=sell_fee,
                    )
                    self.db.update_trade_pnl(trade_id, pnl, pnl_pct)
                    self._last_trade_id = trade_id

                    # Tax: registrar venda com impacto fiscal
                    tax_event = self.tax_tracker.record_sell(
                        symbol=self.symbol,
                        asset_class=self.state.asset_class,
                        volume=qty,
                        price=price,
                        pnl=pnl,
                        commission=sell_fee,
                    )
                    if tax_event.tax_exempt:
                        logger.info("💰 ISENTO de IR: vendas no mês ≤ R$20k")
                    if tax_event.trade_type == "daytrade":
                        logger.warning("⚠️ DAY TRADE: IR de 20%% sobre lucro")

                    # Atualizar estado
                    self.state.total_pnl += pnl
                    self.state.daily_pnl += pnl
                    if pnl > 0:
                        self.state.winning_trades += 1

                    # Rebuy lock
                    self.state.last_sell_entry_price = self.state.entry_price
                    logger.info(
                        "🔒 Rebuy lock: próximo BUY só quando price < R$%.2f",
                        self.state.entry_price,
                    )

                    # Resetar posição
                    self.state.position = 0
                    self.state.entry_price = 0
                    self.state.position_count = 0
                    self.state.entries = []
                    self.state.target_sell_price = 0.0
                    self.state.target_sell_reason = ""
                    self.state.sell_count += 1

                # Estado comum
                self.state.total_trades += 1
                self.state.daily_trades += 1
                self.state.last_trade_time = time.time()

                # Callbacks
                for cb in self._on_trade_callbacks:
                    try:
                        cb(signal, price)
                    except Exception as e:
                        logger.warning("⚠️ Trade callback error: %s", e)

                return True

            except Exception as e:
                logger.error("❌ Trade execution error: %s", e)
                return False

    # ====================== AUTO EXIT ======================

    def _check_trailing_stop(self, price: float) -> bool:
        """Trailing stop: ativa quando preço sobe acima da entrada, vende se cai."""
        if self.state.position <= 0 or self.state.entry_price <= 0:
            return False

        live_cfg = self._load_live_config()
        ts_cfg = live_cfg.get("trailing_stop", {})
        if not ts_cfg.get("enabled", False):
            return False

        activation_pct = ts_cfg.get("activation_pct", 0.015)
        trail_pct = ts_cfg.get("trail_pct", 0.008)

        if price > self.state.trailing_high:
            self.state.trailing_high = price

        pnl_pct = (self.state.trailing_high / self.state.entry_price) - 1
        if pnl_pct < activation_pct:
            return False

        drop_from_high = (self.state.trailing_high - price) / self.state.trailing_high
        if drop_from_high >= trail_pct:
            logger.warning(
                "📉 TRAILING STOP! High=R$%.2f, now=R$%.2f (drop=%.2f%%)",
                self.state.trailing_high, price, drop_from_high * 100,
            )
            forced = Signal(
                action="SELL", confidence=1.0,
                reason=f"TRAILING_STOP (drop {drop_from_high*100:.2f}%)",
                price=price, features={},
            )
            self.state.last_trade_time = 0
            return self._execute_trade(forced, price, force=True)

        return False

    def _check_auto_exit(self, price: float) -> bool:
        """Auto stop-loss e take-profit dinâmico."""
        if self.state.position <= 0 or self.state.entry_price <= 0:
            return False

        live_cfg = self._load_live_config()
        auto_sl = live_cfg.get("auto_stop_loss", {})
        auto_tp = live_cfg.get("auto_take_profit", {})

        sl_enabled = auto_sl.get("enabled", False)
        tp_enabled = auto_tp.get("enabled", False)

        if not sl_enabled and not tp_enabled:
            return False

        pnl_pct = (price / self.state.entry_price) - 1

        # Stop-Loss
        if sl_enabled:
            sl_pct = auto_sl.get("pct", 0.02)
            if pnl_pct <= -sl_pct:
                logger.warning(
                    "🛑 STOP-LOSS! Price R$%.2f is %.2f%% below entry R$%.2f",
                    price, pnl_pct * 100, self.state.entry_price,
                )
                forced = Signal(
                    action="SELL", confidence=1.0,
                    reason=f"AUTO_STOP_LOSS ({pnl_pct*100:.2f}%)",
                    price=price, features={},
                )
                self.state.last_trade_time = 0
                return self._execute_trade(forced, price, force=True)

        # Take-Profit (IA)
        if tp_enabled:
            rag_adj = self.market_rag.get_current_adjustment()
            ai_has_data = rag_adj.similar_count >= 3
            tp_pct = rag_adj.ai_take_profit_pct if ai_has_data else auto_tp.get("pct", 0.025)
            min_tp_pct = auto_tp.get("min_pct", 0.015)
            tp_pct = max(tp_pct, min_tp_pct)

            if pnl_pct >= tp_pct:
                logger.info(
                    "🎯 TAKE-PROFIT! Price R$%.2f is +%.2f%% (threshold: +%.2f%%)",
                    price, pnl_pct * 100, tp_pct * 100,
                )
                forced = Signal(
                    action="SELL", confidence=1.0,
                    reason=f"AUTO_TAKE_PROFIT ({pnl_pct*100:.2f}%)",
                    price=price, features={},
                )
                self.state.last_trade_time = 0
                return self._execute_trade(forced, price, force=True)

        return False

    # ====================== MAIN LOOP ======================

    def _run_loop(self) -> None:
        """Loop principal do agente — respeita horário B3."""
        logger.info("🚀 Starting B3 trading loop...")

        cycle = 0
        while not self._stop_event.is_set():
            try:
                # Verificar horário de mercado
                if not is_market_open():
                    mins = minutes_to_market_open()
                    if mins > 60:
                        logger.info("⏳ Mercado fechado — próxima abertura em %d min", mins)
                    self._stop_event.wait(timeout=min(mins * 60, 300))
                    continue

                cycle += 1
                start_time = time.time()

                # Coletar estado
                market_state = self._get_market_state()
                if market_state is None:
                    self._stop_event.wait(timeout=POLL_INTERVAL)
                    continue

                # Atualizar valor da posição
                if self.state.position > 0:
                    self.state.position_value = self.state.position * market_state.price

                # Auto-exit checks
                if self.state.position > 0:
                    if self._check_trailing_stop(market_state.price):
                        self._stop_event.wait(timeout=POLL_INTERVAL)
                        continue
                    if self._check_auto_exit(market_state.price):
                        self._stop_event.wait(timeout=POLL_INTERVAL)
                        continue

                # Market RAG: alimentar snapshots
                try:
                    self.market_rag.feed_snapshot(
                        price=market_state.price,
                        indicators=self.model.indicators,
                        spread_analysis={
                            "spread": market_state.spread,
                            "bid": market_state.bid,
                            "ask": market_state.ask,
                        },
                        flow_analysis={
                            "flow_bias": market_state.trade_flow,
                        },
                    )
                    self._rag_apply_cycle += 1

                    # Atualizar contexto de trading a cada ~2.5min
                    if self._rag_apply_cycle % 30 == 0:
                        brl_bal = get_balance() if not self.state.dry_run else float(self.config.get("dry_run_balance", 10_000))
                        risk_caps = self._get_runtime_risk_caps()
                        self.market_rag.set_trading_context(
                            avg_entry_price=self.state.entry_price,
                            position_count=self.state.position_count,
                            brl_balance=brl_bal,
                            max_position_pct=risk_caps["max_position_pct"],
                            max_positions=risk_caps["max_positions"],
                            profile=self.state.profile,
                        )
                except Exception as e:
                    logger.debug("RAG feed error: %s", e)

                # Gerar sinal
                ms = self.model.get_market_state(
                    price=market_state.price,
                    bid=market_state.bid,
                    ask=market_state.ask,
                    trade_flow=market_state.trade_flow,
                )
                signal = self.model.generate_signal(ms)

                # Registrar decisão
                decision_id = self.db.record_decision(
                    symbol=self.symbol,
                    action=signal.action,
                    confidence=signal.confidence,
                    price=signal.price,
                    reason=signal.reason,
                    features=signal.features,
                )

                # Callbacks
                for cb in self._on_signal_callbacks:
                    try:
                        cb(signal)
                    except Exception as e:
                        logger.warning("⚠️ Signal callback error: %s", e)

                # Executar trade
                if signal.action != "HOLD" and self._check_can_trade(signal):
                    executed = self._execute_trade(signal, market_state.price)
                    if executed and decision_id:
                        try:
                            self.db.mark_decision_executed(decision_id, self._last_trade_id)
                        except Exception as e:
                            logger.warning("⚠️ Decision mark error: %s", e)

                # Log periódico (~5 min)
                if cycle % 60 == 0:
                    pos_info = (
                        f"Pos: {int(self.state.position)} {self.symbol} "
                        f"({self.state.position_count}x, avg R${self.state.entry_price:.2f})"
                        if self.state.position > 0 else "No position"
                    )
                    rag_stats = self.market_rag.get_stats()
                    logger.info(
                        "📊 Cycle %d | R$%.2f | %s | PnL: R$%.2f | RAG: %s (%.0f%%)",
                        cycle, market_state.price, pos_info,
                        self.state.total_pnl,
                        rag_stats["current_regime"],
                        rag_stats["regime_confidence"] * 100,
                    )
                    self.model.save()

                # Sleep
                elapsed = time.time() - start_time
                sleep_time = max(POLL_INTERVAL - elapsed, 0.1)
                self._stop_event.wait(timeout=sleep_time)

            except Exception as e:
                logger.error("❌ Loop error: %s", e)
                self._stop_event.wait(timeout=POLL_INTERVAL)

        logger.info("🛑 B3 trading loop stopped")

    # ====================== START / STOP ======================

    def start(self) -> None:
        """Inicia o agente."""
        if self.state.running:
            logger.warning("⚠️ Agent already running")
            return

        self.state.running = True
        self._stop_event.clear()

        # Iniciar Market RAG
        try:
            self.market_rag.start()
            logger.info("🧠 Market RAG started")
        except Exception as e:
            logger.warning("⚠️ Market RAG start failed: %s", e)

        # Forçar primeiro contexto
        try:
            brl_bal = get_balance() if not self.state.dry_run else float(self.config.get("dry_run_balance", 10_000))
            risk_caps = self._get_runtime_risk_caps()
            self.market_rag.set_trading_context(
                avg_entry_price=self.state.entry_price,
                position_count=self.state.position_count,
                brl_balance=brl_bal,
                max_position_pct=risk_caps["max_position_pct"],
                max_positions=risk_caps["max_positions"],
                profile=self.state.profile,
            )
            price = get_price_fast(self.symbol, timeout=3)
            if price:
                spread_data = analyze_spread(self.symbol)
                flow_data = analyze_trade_flow(self.symbol)
                self.market_rag.feed_snapshot(
                    price=price,
                    indicators=self.model.indicators,
                    spread_analysis=spread_data,
                    flow_analysis=flow_data,
                )
                rag_adj = self.market_rag.force_recalibrate()
                logger.info(
                    "📊 Initial RAG: regime=%s, sizing=%.1f%%×%d, BRL=R$%.2f",
                    rag_adj.suggested_regime,
                    rag_adj.ai_position_size_pct * 100,
                    rag_adj.ai_max_entries, brl_bal,
                )
        except Exception as e:
            logger.warning("⚠️ Initial RAG context failed: %s", e)

        # Thread principal
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        logger.info("✅ Clear Agent started")

    def stop(self) -> None:
        """Para o agente."""
        if not self.state.running:
            return

        logger.info("🛑 Stopping Clear Agent...")
        self._stop_event.set()
        self.state.running = False

        try:
            self.market_rag.stop()
        except Exception as e:
            logger.debug("Market RAG stop: %s", e)

        self.model.save()
        logger.info("✅ Clear Agent stopped")

    def get_status(self) -> Dict:
        """Retorna status atual."""
        return {
            **self.state.to_dict(),
            "market_rag": self.market_rag.get_stats(),
            "uptime_hours": (time.time() - self.state.start_time) / 3600,
        }

    def on_signal(self, callback) -> None:
        """Registra callback para novos sinais."""
        self._on_signal_callbacks.append(callback)

    def on_trade(self, callback) -> None:
        """Registra callback para trades executados."""
        self._on_trade_callbacks.append(callback)


# ====================== DAEMON MODE ======================
class AgentDaemon:
    """Daemon para executar agente em background."""

    def __init__(self, agent: ClearTradingAgent) -> None:
        self.agent = agent
        self._setup_signals()

    def _setup_signals(self) -> None:
        """Configura handlers de sinais."""
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame) -> None:
        """Handler para sinais de sistema."""
        logger.info("📡 Received signal %d, stopping...", signum)
        self.agent.stop()
        sys.exit(0)

    def run(self) -> None:
        """Executa daemon."""
        logger.info("🤖 Starting daemon mode...")
        self.agent.start()

        try:
            while self.agent.state.running:
                time.sleep(60)
        except KeyboardInterrupt:
            pass
        finally:
            self.agent.stop()


# ====================== CLI ======================
def main() -> None:
    """Entrypoint CLI."""
    parser = argparse.ArgumentParser(description="Clear Trading Agent — B3")
    parser.add_argument("--symbol", default=None, help="Trading symbol (e.g. PETR4, WINFUT)")
    parser.add_argument("--config", default=None, help="Config file name")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Dry run mode")
    parser.add_argument("--live", action="store_true", help="Live trading mode (real money!)")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")

    args = parser.parse_args()

    if args.config:
        os.environ["CLEAR_CONFIG_FILE"] = args.config

    config_name = args.config or os.environ.get("CLEAR_CONFIG_FILE", "config.json")
    config_path = Path(__file__).parent / config_name
    _loaded_cfg: Dict = {}
    if config_path.exists():
        try:
            with open(config_path) as _f:
                _loaded_cfg = json.load(_f)
        except Exception as e:
            logger.warning("⚠️ Config load em main(): %s", e)

    if args.symbol is None:
        args.symbol = _loaded_cfg.get("symbol", "PETR4")

    dry_run = _resolve_process_dry_run(args.live, _loaded_cfg)

    print("=" * 60)
    print("🤖 Clear Trading Agent — B3")
    print("=" * 60)
    print(f"Symbol: {args.symbol}")
    print(f"Profile: {_loaded_cfg.get('profile', 'default')}")
    print(f"Mode: {'🔴 LIVE TRADING' if not dry_run else '🟢 DRY RUN'}")
    print("=" * 60)

    if not dry_run:
        print("\n⚠️  WARNING: LIVE TRADING MODE!")
        print("Real money will be used. Press Ctrl+C within 10s to cancel.")
        time.sleep(10)

    agent = ClearTradingAgent(symbol=args.symbol, dry_run=dry_run, config_name=config_name)

    # Graceful shutdown via SIGTERM (systemd)
    def _handle_sigterm(signum: int, frame: Any) -> None:
        logger.info("🛑 SIGTERM recebido, encerrando agente...")
        agent.stop()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _handle_sigterm)

    def on_signal(sig: Signal) -> None:
        if sig.action != "HOLD":
            logger.info(
                "📍 %s signal @ R$%.2f (%.1f%%) - %s",
                sig.action, sig.price, sig.confidence * 100, sig.reason,
            )

    agent.on_signal(on_signal)

    if args.daemon:
        daemon = AgentDaemon(agent)
        daemon.run()
    else:
        agent.start()
        try:
            while True:
                time.sleep(10)
                status = agent.get_status()
                print(
                    f"\r💹 Running | Trades: {status['total_trades']} | "
                    f"PnL: R${status['total_pnl']:.2f} | "
                    f"Win Rate: {status['win_rate']:.1%}",
                    end="",
                )
        except KeyboardInterrupt:
            print("\n")
            agent.stop()


if __name__ == "__main__":
    main()
