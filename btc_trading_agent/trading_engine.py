#!/usr/bin/env python3
"""
Bitcoin Trading Engine - Motor de Compra e Venda
Motor autônomo que executa trades baseado nos sinais do agente
"""

import os
import sys
import time
import json
import signal
import logging
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import sqlite3

# Paths
ENGINE_DIR = Path(__file__).parent
sys.path.insert(0, str(ENGINE_DIR))

from kucoin_api import (
    get_price_fast, get_orderbook, get_balances, get_balance,
    place_market_order, analyze_orderbook, analyze_trade_flow,
    _has_keys
)
from fast_model import FastTradingModel, MarketState, Signal
from training_db import TrainingDatabase
from whatsapp_notifications import notify_buy, notify_sell, notify_error, notify_status

# ====================== LOGGING ======================
LOG_DIR = ENGINE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "engine.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ====================== CONFIGURAÇÃO ======================
CONFIG_FILE = ENGINE_DIR / "config.json"

DEFAULT_CONFIG = {
    "enabled": False,
    "dry_run": True,
    "symbol": "BTC-USDT",
    "poll_interval": 5,
    "min_trade_interval": 60,
    "min_confidence": 0.5,
    "min_trade_amount": 10,
    "max_position_pct": 0.3,
    "stop_loss_pct": 0.05,
    "take_profit_pct": 0.10,
    "max_daily_trades": 20,
    "max_daily_loss": 100,
    "trading_hours": {
        "enabled": False,
        "start": "09:00",
        "end": "22:00"
    },
    "notifications": {
        "enabled": True,
        "telegram_chat_id": "",
        "whatsapp_chat_id": "",  # Ex: "5511999999999@c.us" ou "grupo@g.us"
        "on_trade": True,
        "on_signal": False,
        "on_error": True
    },
    "risk_management": {
        "enabled": True,
        "max_drawdown_pct": 0.15,
        "position_sizing": "fixed",
        "kelly_fraction": 0.25
    }
}

def load_config() -> Dict:
    """Carrega configuração do arquivo"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                config = json.load(f)
                # Merge com defaults
                return {**DEFAULT_CONFIG, **config}
        except:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(config: Dict):
    """Salva configuração no arquivo"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

# ====================== ENUMS ======================
class EngineState(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"

class TradeType(Enum):
    MANUAL = "manual"
    AUTO = "auto"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"

# ====================== TRADE RESULT ======================
@dataclass
class TradeResult:
    success: bool
    trade_id: Optional[int] = None
    side: str = ""
    size: float = 0.0
    price: float = 0.0
    funds: float = 0.0
    pnl: float = 0.0
    error: Optional[str] = None
    trade_type: TradeType = TradeType.AUTO
    timestamp: datetime = field(default_factory=datetime.now)

# ====================== ENGINE STATS ======================
@dataclass
class EngineStats:
    state: EngineState = EngineState.STOPPED
    uptime_seconds: float = 0
    cycles: int = 0
    signals_generated: int = 0
    trades_executed: int = 0
    trades_today: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    daily_pnl: float = 0.0
    max_drawdown: float = 0.0
    current_position: float = 0.0
    entry_price: float = 0.0
    unrealized_pnl: float = 0.0
    last_trade_time: Optional[datetime] = None
    last_signal: Optional[Dict] = None
    last_error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "state": self.state.value,
            "uptime_seconds": self.uptime_seconds,
            "cycles": self.cycles,
            "signals_generated": self.signals_generated,
            "trades_executed": self.trades_executed,
            "trades_today": self.trades_today,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.winning_trades / max(self.trades_executed, 1),
            "total_pnl": self.total_pnl,
            "daily_pnl": self.daily_pnl,
            "max_drawdown": self.max_drawdown,
            "current_position": self.current_position,
            "entry_price": self.entry_price,
            "unrealized_pnl": self.unrealized_pnl,
            "last_trade_time": self.last_trade_time.isoformat() if self.last_trade_time else None,
            "last_signal": self.last_signal,
            "last_error": self.last_error
        }

# ====================== TRADING ENGINE ======================
class TradingEngine:
    """Motor principal de trading"""
    
    def __init__(self):
        self.config = load_config()
        self.stats = EngineStats()
        self.model = FastTradingModel(self.config["symbol"])
        self.db = TrainingDatabase()
        
        # Estado
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._trade_lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._start_time: Optional[datetime] = None
        
        # Callbacks
        self._callbacks: Dict[str, List[Callable]] = {
            "on_signal": [],
            "on_trade": [],
            "on_error": [],
            "on_state_change": []
        }
        
        # Daily reset
        self._last_daily_reset = datetime.now().date()
        
        logger.info("🤖 Trading Engine initialized")
    
    # ==================== CONFIGURATION ====================
    
    def get_config(self) -> Dict:
        """Retorna configuração atual"""
        return self.config.copy()
    
    def update_config(self, new_config: Dict) -> bool:
        """Atualiza configuração"""
        try:
            self.config.update(new_config)
            save_config(self.config)
            logger.info(f"⚙️ Config updated: {list(new_config.keys())}")
            return True
        except Exception as e:
            logger.error(f"❌ Config update failed: {e}")
            return False
    
    # ==================== STATE MANAGEMENT ====================
    
    def _set_state(self, state: EngineState):
        """Muda estado do engine"""
        old_state = self.stats.state
        self.stats.state = state
        logger.info(f"📊 State: {old_state.value} → {state.value}")
        self._fire_callback("on_state_change", old_state, state)
    
    def _fire_callback(self, event: str, *args):
        """Dispara callbacks"""
        for cb in self._callbacks.get(event, []):
            try:
                cb(*args)
            except Exception as e:
                logger.warning(f"⚠️ Callback error: {e}")
    
    def on(self, event: str, callback: Callable):
        """Registra callback"""
        if event in self._callbacks:
            self._callbacks[event].append(callback)
    
    # ==================== RISK MANAGEMENT ====================
    
    def _check_daily_limits(self) -> bool:
        """Verifica limites diários"""
        # Reset diário
        today = datetime.now().date()
        if today != self._last_daily_reset:
            self.stats.trades_today = 0
            self.stats.daily_pnl = 0
            self._last_daily_reset = today
        
        # Limite de trades
        if self.stats.trades_today >= self.config["max_daily_trades"]:
            logger.warning("⚠️ Daily trade limit reached")
            return False
        
        # Limite de perda
        if abs(self.stats.daily_pnl) >= self.config["max_daily_loss"] and self.stats.daily_pnl < 0:
            logger.warning("⚠️ Daily loss limit reached")
            return False
        
        return True
    
    def _check_trading_hours(self) -> bool:
        """Verifica se está no horário de trading"""
        if not self.config["trading_hours"]["enabled"]:
            return True
        
        now = datetime.now().time()
        start = datetime.strptime(self.config["trading_hours"]["start"], "%H:%M").time()
        end = datetime.strptime(self.config["trading_hours"]["end"], "%H:%M").time()
        
        return start <= now <= end
    
    def _check_stop_loss(self, current_price: float) -> bool:
        """Verifica stop loss"""
        if self.stats.current_position <= 0:
            return False
        
        if self.stats.entry_price <= 0:
            return False
        
        loss_pct = (self.stats.entry_price - current_price) / self.stats.entry_price
        return loss_pct >= self.config["stop_loss_pct"]
    
    def _check_take_profit(self, current_price: float) -> bool:
        """Verifica take profit"""
        if self.stats.current_position <= 0:
            return False
        
        if self.stats.entry_price <= 0:
            return False
        
        profit_pct = (current_price - self.stats.entry_price) / self.stats.entry_price
        return profit_pct >= self.config["take_profit_pct"]
    
    def _calculate_position_size(self, signal: Signal, price: float) -> float:
        """Calcula tamanho da posição"""
        if self.config["dry_run"]:
            balance = 1000  # Simulação
        else:
            balance = get_balance("USDT") or 0
        
        max_amount = balance * self.config["max_position_pct"]
        
        sizing = self.config["risk_management"]["position_sizing"]
        
        if sizing == "fixed":
            amount = max_amount * signal.confidence
        elif sizing == "kelly":
            # Kelly criterion simplificado
            kelly = self.config["risk_management"]["kelly_fraction"]
            win_rate = self.stats.winning_trades / max(self.stats.trades_executed, 1)
            amount = balance * kelly * win_rate * signal.confidence
        else:
            amount = max_amount * signal.confidence
        
        return max(min(amount, max_amount), self.config["min_trade_amount"])
    
    # ==================== TRADING EXECUTION ====================
    
    def _send_trade_notification(self, result: TradeResult, pnl_pct: float = 0.0):
        """Envia notificação de trade via WhatsApp"""
        try:
            notif = self.config.get("notifications", {})
            if not notif.get("enabled") or not notif.get("on_trade"):
                return
            
            chat_id = notif.get("whatsapp_chat_id", "")
            if not chat_id:
                return
            
            if result.side == "buy":
                notify_buy(
                    symbol=self.config["symbol"],
                    size=result.size,
                    price=result.price,
                    funds=result.funds,
                    trade_type=result.trade_type.value,
                    dry_run=self.config["dry_run"],
                    chat_id=chat_id
                )
            else:
                notify_sell(
                    symbol=self.config["symbol"],
                    size=result.size,
                    price=result.price,
                    pnl=result.pnl,
                    pnl_pct=pnl_pct,
                    trade_type=result.trade_type.value,
                    dry_run=self.config["dry_run"],
                    chat_id=chat_id
                )
                
        except Exception as e:
            logger.warning(f"⚠️ WhatsApp notification failed: {e}")
    
    def _send_error_notification(self, error: str):
        """Envia notificação de erro via WhatsApp"""
        try:
            notif = self.config.get("notifications", {})
            if not notif.get("enabled") or not notif.get("on_error"):
                return
            
            chat_id = notif.get("whatsapp_chat_id", "")
            if chat_id:
                notify_error(error, chat_id)
                
        except Exception as e:
            logger.warning(f"⚠️ WhatsApp error notification failed: {e}")
    
    def _execute_buy(self, price: float, amount: float, trade_type: TradeType = TradeType.AUTO) -> TradeResult:
        """Executa compra"""
        with self._trade_lock:
            try:
                if self.config["dry_run"]:
                    size = amount / price
                    logger.info(f"🔵 [DRY] BUY {size:.6f} BTC @ ${price:,.2f}")
                else:
                    result = place_market_order(self.config["symbol"], "buy", funds=amount)
                    if not result.get("success"):
                        return TradeResult(success=False, error=str(result))
                    size = amount / price * 0.999  # Fee
                
                # Atualizar estado
                self.stats.current_position = size
                self.stats.entry_price = price
                self.stats.trades_executed += 1
                self.stats.trades_today += 1
                self.stats.last_trade_time = datetime.now()
                
                # Registrar no banco
                trade_id = self.db.record_trade(
                    symbol=self.config["symbol"],
                    side="buy",
                    price=price,
                    size=size,
                    funds=amount,
                    dry_run=self.config["dry_run"]
                )
                
                result = TradeResult(
                    success=True,
                    trade_id=trade_id,
                    side="buy",
                    size=size,
                    price=price,
                    funds=amount,
                    trade_type=trade_type
                )
                
                self._fire_callback("on_trade", result)
                
                # 📱 Notificar via WhatsApp
                self._send_trade_notification(result)
                
                return result
                
            except Exception as e:
                error = str(e)
                logger.error(f"❌ Buy failed: {error}")
                self._fire_callback("on_error", error)
                self._send_error_notification(f"Falha na compra: {error}")
                return TradeResult(success=False, error=error)
    
    def _execute_sell(self, price: float, trade_type: TradeType = TradeType.AUTO) -> TradeResult:
        """Executa venda"""
        with self._trade_lock:
            try:
                size = self.stats.current_position
                if size <= 0:
                    return TradeResult(success=False, error="No position to sell")
                
                # PnL
                pnl = (price - self.stats.entry_price) * size
                pnl_pct = ((price / self.stats.entry_price) - 1) * 100 if self.stats.entry_price > 0 else 0
                
                if self.config["dry_run"]:
                    logger.info(f"🔴 [DRY] SELL {size:.6f} BTC @ ${price:,.2f} (PnL: ${pnl:.2f})")
                else:
                    result = place_market_order(self.config["symbol"], "sell", size=size)
                    if not result.get("success"):
                        return TradeResult(success=False, error=str(result))
                
                # Atualizar stats
                self.stats.total_pnl += pnl
                self.stats.daily_pnl += pnl
                if pnl > 0:
                    self.stats.winning_trades += 1
                else:
                    self.stats.losing_trades += 1
                
                # Registrar
                trade_id = self.db.record_trade(
                    symbol=self.config["symbol"],
                    side="sell",
                    price=price,
                    size=size,
                    dry_run=self.config["dry_run"]
                )
                self.db.update_trade_pnl(trade_id, pnl, pnl_pct)
                
                # Reset posição
                old_entry = self.stats.entry_price
                self.stats.current_position = 0
                self.stats.entry_price = 0
                self.stats.unrealized_pnl = 0
                self.stats.trades_executed += 1
                self.stats.trades_today += 1
                self.stats.last_trade_time = datetime.now()
                
                result = TradeResult(
                    success=True,
                    trade_id=trade_id,
                    side="sell",
                    size=size,
                    price=price,
                    pnl=pnl,
                    trade_type=trade_type
                )
                
                self._fire_callback("on_trade", result)
                
                # 📱 Notificar via WhatsApp
                self._send_trade_notification(result, pnl_pct)
                
                return result
                
            except Exception as e:
                error = str(e)
                logger.error(f"❌ Sell failed: {error}")
                self._fire_callback("on_error", error)
                self._send_error_notification(f"Falha na venda: {error}")
                return TradeResult(success=False, error=error)
    
    # ==================== MAIN LOOP ====================
    
    def _get_market_state(self, price: float) -> Optional[MarketState]:
        """Coleta estado do mercado"""
        try:
            ob = analyze_orderbook(self.config["symbol"])
            flow = analyze_trade_flow(self.config["symbol"])
            
            self.model.indicators.update(price)
            
            return MarketState(
                price=price,
                bid=ob.get("bid_volume", 0),
                ask=ob.get("ask_volume", 0),
                spread=ob.get("spread", 0),
                orderbook_imbalance=ob.get("imbalance", 0),
                trade_flow=flow.get("flow_bias", 0),
                volume_ratio=flow.get("total_volume", 1),
                rsi=self.model.indicators.rsi(),
                momentum=self.model.indicators.momentum(),
                volatility=self.model.indicators.volatility(),
                trend=self.model.indicators.trend()
            )
        except Exception as e:
            logger.warning(f"⚠️ Market state error: {e}")
            return None
    
    def _run_cycle(self):
        """Executa um ciclo de trading"""
        # Obter preço
        price = get_price_fast(self.config["symbol"], timeout=3)
        if not price:
            return
        
        # Atualizar unrealized PnL
        if self.stats.current_position > 0 and self.stats.entry_price > 0:
            self.stats.unrealized_pnl = (price - self.stats.entry_price) * self.stats.current_position
        
        # Verificar stop loss / take profit
        if self._check_stop_loss(price):
            logger.warning(f"🛑 STOP LOSS triggered @ ${price:,.2f}")
            self._execute_sell(price, TradeType.STOP_LOSS)
            return
        
        if self._check_take_profit(price):
            logger.info(f"🎯 TAKE PROFIT triggered @ ${price:,.2f}")
            self._execute_sell(price, TradeType.TAKE_PROFIT)
            return
        
        # Verificar limites
        if not self._check_daily_limits():
            return
        
        if not self._check_trading_hours():
            return
        
        # Obter estado do mercado
        state = self._get_market_state(price)
        if not state:
            return
        
        # Gerar sinal
        explore = (self.stats.cycles % 10 == 0)
        signal = self.model.predict(state, explore=explore)
        
        self.stats.signals_generated += 1
        self.stats.last_signal = {
            "action": signal.action,
            "confidence": signal.confidence,
            "reason": signal.reason,
            "price": price,
            "timestamp": datetime.now().isoformat()
        }
        
        self._fire_callback("on_signal", signal)
        
        # Registrar decisão
        self.db.record_decision(
            symbol=self.config["symbol"],
            action=signal.action,
            confidence=signal.confidence,
            price=price,
            reason=signal.reason
        )
        
        # Verificar intervalo mínimo
        if self.stats.last_trade_time:
            elapsed = (datetime.now() - self.stats.last_trade_time).total_seconds()
            if elapsed < self.config["min_trade_interval"]:
                return
        
        # Verificar confiança mínima
        if signal.confidence < self.config["min_confidence"]:
            return
        
        # Executar trade
        if signal.action == "BUY" and self.stats.current_position <= 0:
            amount = self._calculate_position_size(signal, price)
            self._execute_buy(price, amount)
        
        elif signal.action == "SELL" and self.stats.current_position > 0:
            self._execute_sell(price)
    
    def _run_loop(self):
        """Loop principal"""
        logger.info("🚀 Engine loop starting...")
        self._set_state(EngineState.RUNNING)
        
        while not self._stop_event.is_set():
            try:
                # Verificar pause
                if self._pause_event.is_set():
                    time.sleep(1)
                    continue
                
                # Executar ciclo
                self.stats.cycles += 1
                self._run_cycle()
                
                # Atualizar uptime
                if self._start_time:
                    self.stats.uptime_seconds = (datetime.now() - self._start_time).total_seconds()
                
                # Salvar modelo periodicamente
                if self.stats.cycles % 60 == 0:
                    self.model.save()
                
                # Sleep
                time.sleep(self.config["poll_interval"])
                
            except Exception as e:
                error = str(e)
                logger.error(f"❌ Loop error: {error}")
                self.stats.last_error = error
                self._fire_callback("on_error", error)
                time.sleep(self.config["poll_interval"])
        
        self._set_state(EngineState.STOPPED)
        logger.info("🛑 Engine loop stopped")
    
    # ==================== PUBLIC API ====================
    
    def start(self) -> bool:
        """Inicia o engine"""
        if self.stats.state == EngineState.RUNNING:
            logger.warning("⚠️ Engine already running")
            return False
        
        if not self.config["enabled"]:
            logger.warning("⚠️ Engine is disabled in config")
            return False
        
        # Verificar credenciais para modo live
        if not self.config["dry_run"] and not _has_keys():
            logger.error("❌ API credentials required for live trading")
            return False
        
        self._set_state(EngineState.STARTING)
        self._stop_event.clear()
        self._pause_event.clear()
        self._start_time = datetime.now()
        
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
        logger.info("✅ Engine started")
        return True
    
    def stop(self) -> bool:
        """Para o engine"""
        if self.stats.state == EngineState.STOPPED:
            return True
        
        logger.info("🛑 Stopping engine...")
        self._stop_event.set()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        
        # Salvar modelo
        self.model.save()
        
        # Snapshot de performance
        self.db.record_performance_snapshot(self.config["symbol"])
        
        logger.info("✅ Engine stopped")
        return True
    
    def pause(self) -> bool:
        """Pausa o engine"""
        if self.stats.state != EngineState.RUNNING:
            return False
        
        self._pause_event.set()
        self._set_state(EngineState.PAUSED)
        logger.info("⏸️ Engine paused")
        return True
    
    def resume(self) -> bool:
        """Resume o engine"""
        if self.stats.state != EngineState.PAUSED:
            return False
        
        self._pause_event.clear()
        self._set_state(EngineState.RUNNING)
        logger.info("▶️ Engine resumed")
        return True
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas"""
        return self.stats.to_dict()
    
    def manual_buy(self, amount: float) -> TradeResult:
        """Compra manual"""
        price = get_price_fast(self.config["symbol"])
        if not price:
            return TradeResult(success=False, error="Price unavailable")
        return self._execute_buy(price, amount, TradeType.MANUAL)
    
    def manual_sell(self) -> TradeResult:
        """Venda manual"""
        price = get_price_fast(self.config["symbol"])
        if not price:
            return TradeResult(success=False, error="Price unavailable")
        return self._execute_sell(price, TradeType.MANUAL)
    
    def close_position(self) -> TradeResult:
        """Fecha posição atual"""
        if self.stats.current_position <= 0:
            return TradeResult(success=False, error="No position to close")
        return self.manual_sell()

# ====================== SINGLETON ======================
_engine: Optional[TradingEngine] = None

def get_engine() -> TradingEngine:
    """Obtém instância do engine"""
    global _engine
    if _engine is None:
        _engine = TradingEngine()
    return _engine

# ====================== CLI ======================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="BTC Trading Engine")
    parser.add_argument("command", choices=["start", "stop", "status", "config"], help="Command")
    parser.add_argument("--enable", action="store_true", help="Enable engine")
    parser.add_argument("--disable", action="store_true", help="Disable engine")
    parser.add_argument("--live", action="store_true", help="Live trading mode")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    
    args = parser.parse_args()
    engine = get_engine()
    
    if args.command == "config":
        if args.enable:
            engine.update_config({"enabled": True})
            print("✅ Engine enabled")
        if args.disable:
            engine.update_config({"enabled": False})
            print("✅ Engine disabled")
        if args.live:
            engine.update_config({"dry_run": False})
            print("⚠️ LIVE TRADING MODE ENABLED")
        if args.dry_run:
            engine.update_config({"dry_run": True})
            print("✅ Dry run mode enabled")
        
        print("\nCurrent config:")
        print(json.dumps(engine.get_config(), indent=2))
    
    elif args.command == "start":
        if engine.start():
            print("✅ Engine started")
            # Manter rodando
            try:
                while engine.stats.state == EngineState.RUNNING:
                    time.sleep(5)
                    stats = engine.get_stats()
                    print(f"\r📊 Cycles: {stats['cycles']} | "
                          f"Trades: {stats['trades_executed']} | "
                          f"PnL: ${stats['total_pnl']:.2f}", end="")
            except KeyboardInterrupt:
                print("\n")
                engine.stop()
        else:
            print("❌ Failed to start engine")
    
    elif args.command == "stop":
        engine.stop()
        print("✅ Engine stopped")
    
    elif args.command == "status":
        stats = engine.get_stats()
        print(json.dumps(stats, indent=2))

if __name__ == "__main__":
    main()
