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

# ====================== CONSTANTES ======================
# Default symbol — can be overridden by config file or CLI
_config_file = os.environ.get("COIN_CONFIG_FILE", "config.json")
_config_path = Path(__file__).parent / _config_file
try:
    with open(_config_path) as _cf:
        _config = json.load(_cf)
    DEFAULT_SYMBOL = _config.get("symbol", "BTC-USDT")
except Exception:
    DEFAULT_SYMBOL = "BTC-USDT"
POLL_INTERVAL = 5  # segundos entre análises
MIN_TRADE_INTERVAL = 600  # segundos mínimo entre trades
MIN_CONFIDENCE = 0.70  # confiança mínima para executar trade
MIN_TRADE_AMOUNT = 10  # USDT mínimo por trade
MAX_POSITION_PCT = 0.3  # máximo 30% do saldo em posição
TRADING_FEE_PCT = 0.001  # 0.1% por trade

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
            "dry_run": self.dry_run
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
            
            # Indicadores do modelo
            self.model.indicators.update(price)
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
                volume_ratio=flow_analysis.get("total_volume", 1),
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
        
        return True
    
    def _calculate_trade_size(self, signal: Signal, price: float) -> float:
        """Calcula tamanho do trade"""
        if signal.action == "BUY":
            usdt_balance = get_balance("USDT") if not self.state.dry_run else 1000
            max_amount = usdt_balance * MAX_POSITION_PCT
            
            # Escalar pelo confidence
            amount = max_amount * signal.confidence
            amount = max(amount, MIN_TRADE_AMOUNT)
            
            return min(amount, usdt_balance * 0.95)  # Deixar margem
        
            # --- FEE CHECK INSERTED: estimar taxas antes de enviar ordem de venda
            size = self.state.position
            if size <= 0:
                return False

            gross_sell = price * size
            sell_fee = gross_sell * TRADING_FEE_PCT
            buy_fee_approx = self.state.entry_price * size * TRADING_FEE_PCT
            total_fees = sell_fee + buy_fee_approx

            pnl = (price - self.state.entry_price) * size
            # Abort if profit does not cover estimated fees
            if pnl <= total_fees:
                logger.warning(f"⚠️ SELL aborted — profit ${pnl:.2f} does not cover estimated fees ${total_fees:.2f}")
                return False


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
                    if pnl > 0:
                        self.state.winning_trades += 1
                    
                    self.state.position = 0
                    self.state.entry_price = 0
                
                # Atualizar estado
                self.state.total_trades += 1
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
    parser.add_argument("--symbol", default=None, help="Trading pair (overrides config)")
    parser.add_argument("--config", default=None, help="Config file name (e.g. config_ETH_USDT.json)")
    parser.add_argument("--api-port", type=int, default=None, help="Engine API port")
    parser.add_argument("--metrics-port", type=int, default=None, help="Prometheus metrics port")
    parser.add_argument("--dry-run", action="store_true", default=True,
                       help="Dry run mode (no real trades)")
    parser.add_argument("--live", action="store_true",
                       help="Live trading mode (real money!)")
    parser.add_argument("--daemon", action="store_true",
                       help="Run as daemon")
    
    args = parser.parse_args()
    
    # Set config file env var for multi-coin
    if args.config:
        os.environ["COIN_CONFIG_FILE"] = args.config
    
    # Load config to get symbol
    config_name = args.config or os.environ.get("COIN_CONFIG_FILE", "config.json")
    config_path = Path(__file__).parent / config_name
    _loaded_cfg = {}
    if config_path.exists():
        try:
            with open(config_path) as _f:
                _loaded_cfg = json.load(_f)
        except Exception:
            pass
    
    # Symbol: CLI overrides config, config overrides default
    if args.symbol is None:
        args.symbol = _loaded_cfg.get("symbol", "BTC-USDT")
    
    # API port env
    if args.api_port:
        os.environ["BTC_ENGINE_API_PORT"] = str(args.api_port)
    
    # Metrics port env
    if args.metrics_port:
        os.environ["METRICS_PORT"] = str(args.metrics_port)
    
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
