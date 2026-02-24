#!/usr/bin/env python3
"""
Bitcoin Trading Agent 24/7
Agente autônomo de trading que opera continuamente
"""

import os
import sys
import time
import json
import signal
import logging
import argparse
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional
from dataclasses import dataclass

# Adicionar diretório ao path
sys.path.insert(0, str(Path(__file__).parent))

from kucoin_api import (
    get_price, get_price_fast, get_orderbook, get_candles,
    get_recent_trades, get_balances, get_balance,
    place_market_order, analyze_orderbook, analyze_trade_flow,
    _has_keys
)
from fast_model import FastTradingModel, MarketState, Signal
from training_db import TrainingDatabase

# ====================== CONFIGURAÇÃO ======================
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "agent.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ====================== CARREGAR CONFIG ======================
import json as _json
_CONFIG_PATH = Path(__file__).parent / "config.json"
try:
    with open(_CONFIG_PATH) as _f:
        _config = _json.load(_f)
except Exception:
    _config = {}

# ====================== CONSTANTES ======================
DEFAULT_SYMBOL = _config.get("symbol", "BTC-USDT")
POLL_INTERVAL = _config.get("poll_interval", 5)
MIN_TRADE_INTERVAL = _config.get("min_trade_interval", 180)  # 3 min entre trades
MIN_CONFIDENCE = _config.get("min_confidence", 0.60)  # subido de 0.50 para 0.60
MIN_TRADE_AMOUNT = _config.get("min_trade_amount", 50)  # subido de 10 para 50
MAX_POSITION_PCT = _config.get("max_position_pct", 0.3)
TRADING_FEE_PCT = 0.001  # 0.1% por trade

# ====================== STOP LOSS / TAKE PROFIT ======================
STOP_LOSS_PCT = _config.get("stop_loss_pct", 0.02)  # -2% stop loss
TAKE_PROFIT_PCT = _config.get("take_profit_pct", 0.03)  # +3% take profit
TRAILING_STOP_CFG = _config.get("trailing_stop", {})
TRAILING_STOP_ENABLED = TRAILING_STOP_CFG.get("enabled", True)
TRAILING_STOP_ACTIVATION = TRAILING_STOP_CFG.get("activation_pct", 0.015)  # 1.5%
TRAILING_STOP_TRAIL = TRAILING_STOP_CFG.get("trail_pct", 0.008)  # 0.8%
MAX_DAILY_TRADES = _config.get("max_daily_trades", 15)
MAX_DAILY_LOSS = _config.get("max_daily_loss", 150)

# ====================== ESTADO DO AGENTE ======================
@dataclass
class AgentState:
    """Estado atual do agente"""
    running: bool = False
    symbol: str = DEFAULT_SYMBOL
    position: float = 0.0  # BTC em carteira
    position_value: float = 0.0  # Valor em USDT
    entry_price: float = 0.0
    last_trade_time: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    total_pnl: float = 0.0
    dry_run: bool = True
    # — Trailing stop state —
    highest_price_since_entry: float = 0.0
    trailing_stop_active: bool = False
    # — Saída parcial —
    partial_sold: bool = False
    original_position: float = 0.0
    # — Daily limits —
    daily_trades: int = 0
    daily_pnl: float = 0.0
    daily_reset_time: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "running": self.running,
            "symbol": self.symbol,
            "position_btc": self.position,
            "position_usdt": self.position_value,
            "entry_price": self.entry_price,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "win_rate": self.winning_trades / max(self.total_trades, 1),
            "total_pnl": self.total_pnl,
            "dry_run": self.dry_run,
            "highest_price_since_entry": self.highest_price_since_entry,
            "trailing_stop_active": self.trailing_stop_active,
            "partial_sold": self.partial_sold,
            "daily_trades": self.daily_trades,
            "daily_pnl": self.daily_pnl,
        }

# ====================== AGENTE PRINCIPAL ======================
class BitcoinTradingAgent:
    """Agente de trading de Bitcoin 24/7"""
    
    def __init__(self, symbol: str = DEFAULT_SYMBOL, dry_run: bool = True):
        self.symbol = symbol
        self.state = AgentState(symbol=symbol, dry_run=dry_run)
        self.model = FastTradingModel(symbol)
        self.db = TrainingDatabase()
        
        # Threading
        self._stop_event = threading.Event()
        self._trade_lock = threading.Lock()
        
        # Callbacks
        self._on_signal_callbacks = []
        self._on_trade_callbacks = []
        
        logger.info(f"🤖 Agent initialized: {symbol} (dry_run={dry_run})")
    
    def _get_market_state(self) -> Optional[MarketState]:
        """Coleta estado atual do mercado"""
        try:
            # Preço
            price = get_price_fast(self.symbol, timeout=2)
            if price is None:
                logger.warning("⚠️ Price unavailable")
                return None
            
            # Order book
            ob_analysis = analyze_orderbook(self.symbol)
            
            # Trade flow
            flow_analysis = analyze_trade_flow(self.symbol)
            
            # === Candles reais de 1min (Etapa 3) ===
            try:
                candles = get_candles(self.symbol, ktype="1min", limit=50)
                if candles and len(candles) >= 10:
                    self.model.indicators.update_from_candles(candles)
                    # Usar volume do último candle
                    last_volume = candles[-1].get('volume', 0)
                else:
                    # Fallback: tick único
                    self.model.indicators.update(price)
                    last_volume = flow_analysis.get("total_volume", 0)
            except Exception as e:
                logger.debug(f"⚠️ Candles fallback to tick: {e}")
                self.model.indicators.update(price)
                last_volume = flow_analysis.get("total_volume", 0)
            
            rsi = self.model.indicators.rsi()
            momentum = self.model.indicators.momentum()
            volatility = self.model.indicators.volatility()
            trend = self.model.indicators.trend()
            
            state = MarketState(
                price=price,
                bid=ob_analysis.get("bid_volume", 0),
                ask=ob_analysis.get("ask_volume", 0),
                spread=ob_analysis.get("spread", 0),
                orderbook_imbalance=ob_analysis.get("imbalance", 0),
                trade_flow=flow_analysis.get("flow_bias", 0),
                volume_ratio=self.model.indicators.volume_ratio() if last_volume > 0 else 1.0,
                rsi=rsi,
                momentum=momentum,
                volatility=volatility,
                trend=trend
            )
            
            # Registrar estado
            self.db.record_market_state(
                symbol=self.symbol,
                price=price,
                orderbook_imbalance=state.orderbook_imbalance,
                trade_flow=state.trade_flow,
                rsi=rsi,
                momentum=momentum,
                volatility=volatility,
                trend=trend
            )
            
            return state
            
        except Exception as e:
            logger.error(f"❌ Error getting market state: {e}")
            return None
    
    def _check_can_trade(self, signal: Signal) -> bool:
        """Verifica se pode executar trade"""
        # Intervalo mínimo
        elapsed = time.time() - self.state.last_trade_time
        if elapsed < MIN_TRADE_INTERVAL:
            logger.debug(f"⏳ Trade cooldown: {MIN_TRADE_INTERVAL - elapsed:.0f}s remaining")
            return False
        
        # Confiança mínima
        if signal.confidence < MIN_CONFIDENCE:
            logger.debug(f"📉 Low confidence: {signal.confidence:.1%}")
            return False
        
        # Verificar se já tem posição
        if signal.action == "BUY" and self.state.position > 0:
            logger.debug("📦 Already have position")
            return False
        
        if signal.action == "SELL" and self.state.position <= 0:
            logger.debug("📭 No position to sell")
            return False
        
        # Daily limits
        self._reset_daily_limits_if_needed()
        if self.state.daily_trades >= MAX_DAILY_TRADES:
            logger.info(f"📊 Daily trade limit reached: {self.state.daily_trades}/{MAX_DAILY_TRADES}")
            return False
        if self.state.daily_pnl <= -MAX_DAILY_LOSS:
            logger.info(f"🛑 Daily loss limit reached: ${self.state.daily_pnl:.2f}")
            return False
        
        return True
    
    def _reset_daily_limits_if_needed(self):
        """Reseta contadores diários à meia-noite"""
        now = time.time()
        if now - self.state.daily_reset_time > 86400:  # 24h
            self.state.daily_trades = 0
            self.state.daily_pnl = 0.0
            self.state.daily_reset_time = now
            logger.info("🔄 Daily counters reset")
    
    def _check_exit_conditions(self, price: float) -> Optional[str]:
        """
        Verifica se deve sair da posição por Stop Loss, Take Profit ou Trailing Stop.
        Retorna: 'stop_loss', 'take_profit', 'trailing_stop', 'partial_take_profit', ou None
        """
        if self.state.position <= 0 or self.state.entry_price <= 0:
            return None
        
        pnl_pct = (price - self.state.entry_price) / self.state.entry_price
        
        # === Stop Loss ===
        if pnl_pct <= -STOP_LOSS_PCT:
            logger.warning(f"🛑 STOP LOSS triggered: {pnl_pct:.2%} <= -{STOP_LOSS_PCT:.2%}")
            return "stop_loss"
        
        # === Take Profit completo ===
        if pnl_pct >= TAKE_PROFIT_PCT:
            logger.info(f"🎯 TAKE PROFIT triggered: {pnl_pct:.2%} >= {TAKE_PROFIT_PCT:.2%}")
            return "take_profit"
        
        # === Saída parcial (50% da posição ao atingir metade do TP) ===
        half_tp = TAKE_PROFIT_PCT / 2  # 1.5%
        if pnl_pct >= half_tp and not self.state.partial_sold:
            logger.info(f"📤 PARTIAL TAKE PROFIT: {pnl_pct:.2%} >= {half_tp:.2%}")
            return "partial_take_profit"
        
        # === Trailing Stop ===
        if TRAILING_STOP_ENABLED:
            return self._check_trailing_stop(price, pnl_pct)
        
        return None
    
    def _check_trailing_stop(self, price: float, pnl_pct: float) -> Optional[str]:
        """Verifica trailing stop"""
        # Atualizar preço máximo desde entrada
        if price > self.state.highest_price_since_entry:
            self.state.highest_price_since_entry = price
        
        # Ativar trailing stop quando lucro >= activation_pct
        if not self.state.trailing_stop_active:
            if pnl_pct >= TRAILING_STOP_ACTIVATION:
                self.state.trailing_stop_active = True
                logger.info(f"📈 Trailing stop ACTIVATED at {pnl_pct:.2%} "
                          f"(high: ${self.state.highest_price_since_entry:,.2f})")
            return None
        
        # Se trailing stop ativo, verificar queda desde o máximo
        if self.state.highest_price_since_entry > 0:
            drop_from_high = (self.state.highest_price_since_entry - price) / self.state.highest_price_since_entry
            if drop_from_high >= TRAILING_STOP_TRAIL:
                logger.info(f"📉 TRAILING STOP triggered: dropped {drop_from_high:.2%} from "
                          f"high ${self.state.highest_price_since_entry:,.2f}")
                return "trailing_stop"
        
        return None
    
    def _execute_forced_sell(self, price: float, reason: str, partial: bool = False) -> bool:
        """Executa venda forçada (stop loss / take profit / trailing stop)"""
        if self.state.position <= 0:
            return False
        
        with self._trade_lock:
            try:
                if partial:
                    size = self.state.position * 0.5  # Vende 50%
                else:
                    size = self.state.position
                
                # Calcular PnL
                pnl = (price - self.state.entry_price) * size
                pnl_pct = ((price / self.state.entry_price) - 1) * 100
                
                emoji = {"stop_loss": "🛑", "take_profit": "🎯", 
                         "trailing_stop": "📉", "partial_take_profit": "📤"}.get(reason, "⚡")
                
                if self.state.dry_run:
                    logger.info(f"{emoji} [DRY] FORCED SELL ({reason}) {size:.6f} BTC @ ${price:,.2f} "
                              f"(PnL: ${pnl:.2f} / {pnl_pct:.2f}%)")
                else:
                    result = place_market_order(self.symbol, "sell", size=size)
                    if not result.get("success"):
                        logger.error(f"❌ Forced sell failed: {result}")
                        return False
                    logger.info(f"{emoji} FORCED SELL ({reason}) {size:.6f} BTC @ ${price:,.2f} "
                              f"(PnL: ${pnl:.2f} / {pnl_pct:.2f}%)")
                
                # Registrar trade
                trade_id = self.db.record_trade(
                    symbol=self.symbol,
                    side="sell",
                    price=price,
                    size=size,
                    dry_run=self.state.dry_run
                )
                self.db.update_trade_pnl(trade_id, pnl, pnl_pct)
                
                # Atualizar estado
                self.state.total_pnl += pnl
                self.state.daily_pnl += pnl
                if pnl > 0:
                    self.state.winning_trades += 1
                
                if partial:
                    self.state.position -= size
                    self.state.partial_sold = True
                    logger.info(f"📊 Remaining position: {self.state.position:.6f} BTC")
                else:
                    self.state.position = 0
                    self.state.entry_price = 0
                    self.state.highest_price_since_entry = 0
                    self.state.trailing_stop_active = False
                    self.state.partial_sold = False
                    self.state.original_position = 0
                
                self.state.total_trades += 1
                self.state.daily_trades += 1
                self.state.last_trade_time = time.time()
                
                # Callbacks
                for cb in self._on_trade_callbacks:
                    try:
                        cb(Signal(action="SELL", confidence=1.0, price=price, 
                                 reason=reason, features={"forced": True}), price)
                    except Exception as e:
                        logger.warning(f"⚠️ Trade callback error: {e}")
                
                return True
                
            except Exception as e:
                logger.error(f"❌ Forced sell error: {e}")
                return False
    
    def _calculate_trade_size(self, signal: Signal, price: float) -> float:
        """Calcula tamanho do trade"""
        if signal.action == "BUY":
            usdt_balance = get_balance("USDT") if not self.state.dry_run else 1000
            max_amount = usdt_balance * MAX_POSITION_PCT
            
            # Escalar pelo confidence
            amount = max_amount * signal.confidence
            amount = max(amount, MIN_TRADE_AMOUNT)
            
            return min(amount, usdt_balance * 0.95)  # Deixar margem
        
        elif signal.action == "SELL":
            # Vender posição inteira
            return self.state.position
        
        return 0
    
    def _execute_trade(self, signal: Signal, price: float) -> bool:
        """Executa trade"""
        with self._trade_lock:
            try:
                if signal.action == "BUY":
                    amount_usdt = self._calculate_trade_size(signal, price)
                    if amount_usdt < MIN_TRADE_AMOUNT:
                        logger.warning(f"⚠️ Trade amount too small: ${amount_usdt:.2f}")
                        return False
                    
                    if self.state.dry_run:
                        # Simulação
                        size = amount_usdt / price
                        self.state.position = size
                        self.state.entry_price = price
                        logger.info(f"🔵 [DRY] BUY {size:.6f} BTC @ ${price:,.2f} (${amount_usdt:.2f})")
                    else:
                        # Trade real
                        result = place_market_order(self.symbol, "buy", funds=amount_usdt)
                        if not result.get("success"):
                            logger.error(f"❌ Order failed: {result}")
                            return False
                        
                        # Atualizar posição (aproximado)
                        size = amount_usdt / price * (1 - TRADING_FEE_PCT)
                        self.state.position = size
                        self.state.entry_price = price
                        logger.info(f"🟢 BUY {size:.6f} BTC @ ${price:,.2f}")
                    
                    # Inicializar trailing stop state
                    self.state.highest_price_since_entry = price
                    self.state.trailing_stop_active = False
                    self.state.partial_sold = False
                    self.state.original_position = size
                    
                    # Registrar
                    trade_id = self.db.record_trade(
                        symbol=self.symbol,
                        side="buy",
                        price=price,
                        size=size,
                        funds=amount_usdt,
                        dry_run=self.state.dry_run
                    )
                    
                elif signal.action == "SELL":
                    size = self.state.position
                    if size <= 0:
                        return False
                    
                    # Calcular PnL
                    pnl = (price - self.state.entry_price) * size
                    pnl_pct = ((price / self.state.entry_price) - 1) * 100
                    
                    if self.state.dry_run:
                        logger.info(f"🔴 [DRY] SELL {size:.6f} BTC @ ${price:,.2f} "
                                  f"(PnL: ${pnl:.2f} / {pnl_pct:.2f}%)")
                    else:
                        result = place_market_order(self.symbol, "sell", size=size)
                        if not result.get("success"):
                            logger.error(f"❌ Order failed: {result}")
                            return False
                        logger.info(f"🔴 SELL {size:.6f} BTC @ ${price:,.2f} "
                                  f"(PnL: ${pnl:.2f} / {pnl_pct:.2f}%)")
                    
                    # Registrar
                    trade_id = self.db.record_trade(
                        symbol=self.symbol,
                        side="sell",
                        price=price,
                        size=size,
                        dry_run=self.state.dry_run
                    )
                    self.db.update_trade_pnl(trade_id, pnl, pnl_pct)
                    
                    # Atualizar estado
                    self.state.total_pnl += pnl
                    self.state.daily_pnl += pnl
                    if pnl > 0:
                        self.state.winning_trades += 1
                    
                    self.state.position = 0
                    self.state.entry_price = 0
                    self.state.highest_price_since_entry = 0
                    self.state.trailing_stop_active = False
                    self.state.partial_sold = False
                    self.state.original_position = 0
                
                # Atualizar estado
                self.state.total_trades += 1
                self.state.daily_trades += 1
                self.state.last_trade_time = time.time()
                
                # Callbacks
                for cb in self._on_trade_callbacks:
                    try:
                        cb(signal, price)
                    except Exception as e:
                        logger.warning(f"⚠️ Trade callback error: {e}")
                
                return True
                
            except Exception as e:
                logger.error(f"❌ Trade execution error: {e}")
                return False
    
    def _run_loop(self):
        """Loop principal do agente"""
        logger.info("🚀 Starting trading loop...")
        
        cycle = 0
        while not self._stop_event.is_set():
            try:
                cycle += 1
                start_time = time.time()
                
                # Coletar estado do mercado
                market_state = self._get_market_state()
                if market_state is None:
                    time.sleep(POLL_INTERVAL)
                    continue
                
                # Atualizar valor da posição
                if self.state.position > 0:
                    self.state.position_value = self.state.position * market_state.price
                    
                    # === VERIFICAR EXIT CONDITIONS (antes do modelo) ===
                    exit_reason = self._check_exit_conditions(market_state.price)
                    if exit_reason:
                        is_partial = (exit_reason == "partial_take_profit")
                        executed = self._execute_forced_sell(market_state.price, exit_reason, partial=is_partial)
                        if executed:
                            logger.info(f"⚡ Forced exit ({exit_reason}) executed at ${market_state.price:,.2f}")
                            # Se vendeu tudo, pular para próximo ciclo
                            if not is_partial:
                                time.sleep(POLL_INTERVAL)
                                continue
                
                # Gerar sinal
                explore = (cycle % 10 == 0)  # Explorar a cada 10 ciclos
                signal = self.model.predict(market_state, explore=explore)
                
                # Registrar decisão
                decision_id = self.db.record_decision(
                    symbol=self.symbol,
                    action=signal.action,
                    confidence=signal.confidence,
                    price=signal.price,
                    reason=signal.reason,
                    features=signal.features
                )
                
                # Callbacks
                for cb in self._on_signal_callbacks:
                    try:
                        cb(signal)
                    except Exception as e:
                        logger.warning(f"⚠️ Signal callback error: {e}")
                
                # Verificar se deve executar
                if signal.action != "HOLD" and self._check_can_trade(signal):
                    executed = self._execute_trade(signal, market_state.price)
                    if executed:
                        self.db.mark_decision_executed(decision_id, self.state.total_trades)
                
                # Log periódico
                if cycle % 60 == 0:  # A cada ~5 minutos
                    pos_info = f"Position: {self.state.position:.6f} BTC" if self.state.position > 0 else "No position"
                    logger.info(f"📊 Cycle {cycle} | ${market_state.price:,.2f} | "
                              f"{pos_info} | PnL: ${self.state.total_pnl:.2f}")
                    
                    # Salvar modelo
                    self.model.save()
                
                # Sleep
                elapsed = time.time() - start_time
                sleep_time = max(POLL_INTERVAL - elapsed, 0.1)
                time.sleep(sleep_time)
                
            except Exception as e:
                logger.error(f"❌ Loop error: {e}")
                time.sleep(POLL_INTERVAL)
        
        logger.info("🛑 Trading loop stopped")
    
    def start(self):
        """Inicia o agente"""
        if self.state.running:
            logger.warning("⚠️ Agent already running")
            return
        
        self.state.running = True
        self._stop_event.clear()
        
        # Thread principal
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
        logger.info("✅ Agent started")
    
    def stop(self):
        """Para o agente"""
        if not self.state.running:
            return
        
        logger.info("🛑 Stopping agent...")
        self._stop_event.set()
        self.state.running = False
        
        # Salvar modelo
        self.model.save()
        
        # Snapshot de performance
        self.db.record_performance_snapshot(self.symbol)
        
        logger.info("✅ Agent stopped")
    
    def get_status(self) -> Dict:
        """Retorna status atual"""
        return {
            **self.state.to_dict(),
            "model_stats": self.model.get_stats(),
            "uptime_hours": (time.time() - self.state.last_trade_time) / 3600 if self.state.last_trade_time else 0
        }
    
    def on_signal(self, callback):
        """Registra callback para novos sinais"""
        self._on_signal_callbacks.append(callback)
    
    def on_trade(self, callback):
        """Registra callback para trades executados"""
        self._on_trade_callbacks.append(callback)

# ====================== DAEMON MODE ======================
class AgentDaemon:
    """Daemon para executar agente em background"""
    
    def __init__(self, agent: BitcoinTradingAgent):
        self.agent = agent
        self._setup_signals()
    
    def _setup_signals(self):
        """Configura handlers de sinais"""
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
    
    def _handle_signal(self, signum, frame):
        """Handler para sinais de sistema"""
        logger.info(f"📡 Received signal {signum}, stopping...")
        self.agent.stop()
        sys.exit(0)
    
    def run(self):
        """Executa daemon"""
        logger.info("🤖 Starting daemon mode...")
        self.agent.start()
        
        try:
            while self.agent.state.running:
                time.sleep(60)
                
                # Log status a cada minuto
                status = self.agent.get_status()
                logger.debug(f"Status: {json.dumps(status, indent=2)}")
                
        except KeyboardInterrupt:
            pass
        finally:
            self.agent.stop()

# ====================== CLI ======================
def main():
    parser = argparse.ArgumentParser(description="Bitcoin Trading Agent 24/7")
    parser.add_argument("--symbol", default="BTC-USDT", help="Trading pair")
    parser.add_argument("--dry-run", action="store_true", default=True,
                       help="Dry run mode (no real trades)")
    parser.add_argument("--live", action="store_true",
                       help="Live trading mode (real money!)")
    parser.add_argument("--daemon", action="store_true",
                       help="Run as daemon")
    
    args = parser.parse_args()
    
    # Verificar credenciais para modo live
    dry_run = not args.live
    if not dry_run and not _has_keys():
        logger.error("❌ API credentials required for live trading!")
        logger.error("Set KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE")
        sys.exit(1)
    
    print("=" * 60)
    print("🤖 Bitcoin Trading Agent 24/7")
    print("=" * 60)
    print(f"Symbol: {args.symbol}")
    print(f"Mode: {'🔴 LIVE TRADING' if not dry_run else '🟢 DRY RUN'}")
    print(f"API Keys: {'✅ Configured' if _has_keys() else '❌ Missing'}")
    print("=" * 60)
    
    if not dry_run:
        print("\n⚠️  WARNING: LIVE TRADING MODE!")
        print("Real money will be used. Press Ctrl+C within 10s to cancel.")
        time.sleep(10)
    
    # Criar agente
    agent = BitcoinTradingAgent(symbol=args.symbol, dry_run=dry_run)
    
    # Callback para sinais
    def on_signal(sig: Signal):
        if sig.action != "HOLD":
            logger.info(f"📍 {sig.action} signal @ ${sig.price:,.2f} "
                       f"({sig.confidence:.1%}) - {sig.reason}")
    
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
                print(f"\r💹 Running | Trades: {status['total_trades']} | "
                     f"PnL: ${status['total_pnl']:.2f} | "
                     f"Win Rate: {status['win_rate']:.1%}", end="")
        except KeyboardInterrupt:
            print("\n")
            agent.stop()

if __name__ == "__main__":
    main()
