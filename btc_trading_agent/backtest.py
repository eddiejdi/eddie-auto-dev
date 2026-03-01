#!/usr/bin/env python3
"""
Backtesting Engine - Testa estratégias em dados históricos
"""

import sys
import json
import psycopg2
import psycopg2.extras
import argparse
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field

# Import local modules
sys.path.insert(0, str(Path(__file__).parent))
from fast_model import FastTradingModel, MarketState, Signal


@dataclass
class BacktestTrade:
    """Trade no backtest"""
    timestamp: float
    side: str  # 'buy' or 'sell'
    price: float
    size: float
    entry_price: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    reason: str = ""


@dataclass
class BacktestStats:
    """Estatísticas do backtest"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    avg_pnl: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    total_volume: float = 0.0
    avg_trade_size: float = 0.0
    trades: List[BacktestTrade] = field(default_factory=list)
    
    def calculate(self):
        """Calcula estatísticas"""
        if not self.trades:
            return
        
        self.total_trades = len(self.trades)
        self.winning_trades = sum(1 for t in self.trades if t.pnl > 0)
        self.losing_trades = sum(1 for t in self.trades if t.pnl < 0)
        self.win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0
        
        pnls = [t.pnl for t in self.trades]
        self.total_pnl = sum(pnls)
        self.avg_pnl = np.mean(pnls) if pnls else 0
        self.max_profit = max(pnls) if pnls else 0
        self.max_loss = min(pnls) if pnls else 0
        
        # Drawdown
        cumulative = np.cumsum(pnls)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = running_max - cumulative
        self.max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0
        
        # Sharpe Ratio (assumindo 0% risk-free rate)
        if len(pnls) > 1:
            std = np.std(pnls)
            self.sharpe_ratio = (self.avg_pnl / std) * np.sqrt(len(pnls)) if std > 0 else 0
        
        self.total_volume = sum(t.size * t.price for t in self.trades)
        self.avg_trade_size = self.total_volume / self.total_trades if self.total_trades > 0 else 0
    
    def print_report(self):
        """Imprime relatório"""
        print("\n" + "="*60)
        print("📊 RELATÓRIO DE BACKTEST")
        print("="*60)
        print(f"\n📈 PERFORMANCE:")
        print(f"  • Total de Trades: {self.total_trades}")
        print(f"  • Trades Vencedores: {self.winning_trades}")
        print(f"  • Trades Perdedores: {self.losing_trades}")
        print(f"  • Win Rate: {self.win_rate:.1%}")
        print(f"\n💰 FINANCEIRO:")
        print(f"  • PnL Total: ${self.total_pnl:.2f}")
        print(f"  • PnL Médio: ${self.avg_pnl:.2f}")
        print(f"  • Melhor Trade: ${self.max_profit:.2f}")
        print(f"  • Pior Trade: ${self.max_loss:.2f}")
        print(f"  • Max Drawdown: ${self.max_drawdown:.2f}")
        print(f"\n📊 MÉTRICAS:")
        print(f"  • Sharpe Ratio: {self.sharpe_ratio:.2f}")
        print(f"  • Volume Total: ${self.total_volume:,.2f}")
        print(f"  • Tamanho Médio: ${self.avg_trade_size:.2f}")
        print("\n" + "="*60)


class BacktestEngine:
    """Engine de backtesting"""
    
    def __init__(self, db_path: str, initial_balance: float = 10000.0):
        self.db_path = db_path
        self.initial_balance = initial_balance
        self.balance_usdt = initial_balance
        self.balance_btc = 0.0
        self.position_entry = 0.0
        self.model = FastTradingModel()
        self.stats = BacktestStats()
        
        # Configuração
        self.trading_fee = 0.001  # 0.1%
        self.min_trade_amount = 50.0
        self.max_position_pct = 0.5
        
    def load_historical_data(self, hours: int = 24) -> List[Dict]:
        """Carrega dados históricos do banco (PostgreSQL)"""
        conn = psycopg2.connect(self.db_path)
        cursor = conn.cursor()
        
        # Carregar market_states
        cutoff = datetime.now().timestamp() - (hours * 3600)
        cursor.execute("""
            SELECT timestamp, price, orderbook_imbalance, trade_flow,
                   rsi, momentum, volatility, trend
            FROM btc.market_states
            WHERE timestamp > %s AND symbol = 'BTC-USDT'
            ORDER BY timestamp ASC
        """, (cutoff,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        data = []
        for row in rows:
            data.append({
                'timestamp': row[0],
                'price': row[1],
                'orderbook_imbalance': row[2],
                'trade_flow': row[3],
                'rsi': row[4],
                'momentum': row[5],
                'volatility': row[6],
                'trend': row[7]
            })
        
        return data
    
    def run(self, hours: int = 24, rsi_oversold: int = 40, rsi_overbought: int = 60) -> BacktestStats:
        """Executa backtest"""
        print(f"\n🔄 Carregando dados dos últimos {hours} horas...")
        data = self.load_historical_data(hours)
        
        if len(data) < 10:
            print("❌ Dados insuficientes para backtest")
            return self.stats
        
        print(f"✅ {len(data)} pontos de dados carregados")
        print(f"📊 Período: {datetime.fromtimestamp(data[0]['timestamp']).strftime('%Y-%m-%d %H:%M')} "
              f"até {datetime.fromtimestamp(data[-1]['timestamp']).strftime('%Y-%m-%d %H:%M')}")
        print(f"⚙️  RSI Levels: Oversold={rsi_oversold}, Overbought={rsi_overbought}")
        print(f"\n🎯 Executando backtest...")
        
        # Reset
        self.balance_usdt = self.initial_balance
        self.balance_btc = 0.0
        self.position_entry = 0.0
        self.stats = BacktestStats()
        
        # Simular trading
        for i, point in enumerate(data):
            # Criar MarketState
            state = MarketState(
                price=point['price'],
                orderbook_imbalance=point['orderbook_imbalance'],
                trade_flow=point['trade_flow'],
                rsi=point['rsi'],
                momentum=point['momentum'],
                volatility=point['volatility'],
                trend=point['trend']
            )
            
            # Atualizar indicadores do modelo
            self.model.indicators.update(state.price)
            
            # Gerar sinal (aplicar estratégia customizada)
            signal = self._generate_signal(state, rsi_oversold, rsi_overbought)
            
            # Executar trade se aplicável
            if signal.action == "BUY" and self.balance_btc == 0:
                self._execute_buy(state, signal)
            elif signal.action == "SELL" and self.balance_btc > 0:
                self._execute_sell(state, signal)
        
        # Fechar posição aberta ao final
        if self.balance_btc > 0:
            final_state = MarketState(price=data[-1]['price'])
            self._execute_sell(final_state, Signal(
                action="SELL",
                confidence=1.0,
                price=data[-1]['price'],
                reason="Fechar ao final do backtest"
            ))
        
        # Calcular estatísticas
        self.stats.calculate()
        
        return self.stats
    
    def _generate_signal(self, state: MarketState, rsi_oversold: int, rsi_overbought: int) -> Signal:
        """Gera sinal baseado em estratégia"""
        reasons = []
        score = 0.0
        
        # RSI
        if state.rsi < rsi_oversold:
            score += 0.4
            reasons.append("RSI oversold")
        elif state.rsi > rsi_overbought:
            score -= 0.4
            reasons.append("RSI overbought")
        
        # Orderbook imbalance
        if state.orderbook_imbalance > 0.2:
            score += 0.2
            reasons.append("bid pressure")
        elif state.orderbook_imbalance < -0.2:
            score -= 0.2
            reasons.append("ask pressure")
        
        # Trade flow
        if state.trade_flow > 0.3:
            score += 0.2
            reasons.append("buying pressure")
        elif state.trade_flow < -0.3:
            score -= 0.2
            reasons.append("selling pressure")
        
        # Trend
        if state.trend > 0.1:
            score += 0.1
            reasons.append("uptrend")
        elif state.trend < -0.1:
            score -= 0.1
            reasons.append("downtrend")
        
        # Momentum
        if state.momentum > 0.5:
            score += 0.1
            reasons.append("positive momentum")
        elif state.momentum < -0.5:
            score -= 0.1
            reasons.append("negative momentum")
        
        # Decisão
        action = "HOLD"
        if score > 0.3:
            action = "BUY"
        elif score < -0.3:
            action = "SELL"
        
        confidence = abs(score)
        
        return Signal(
            action=action,
            confidence=min(confidence, 1.0),
            price=state.price,
            reason=", ".join(reasons) if reasons else "neutral"
        )
    
    def _execute_buy(self, state: MarketState, signal: Signal):
        """Executa compra no backtest"""
        amount_usdt = self.balance_usdt * self.max_position_pct
        if amount_usdt < self.min_trade_amount:
            return
        
        fee = amount_usdt * self.trading_fee
        btc_bought = (amount_usdt - fee) / state.price
        
        self.balance_usdt -= amount_usdt
        self.balance_btc = btc_bought
        self.position_entry = state.price
        
        # Registrar (PnL ainda é 0)
        trade = BacktestTrade(
            timestamp=state.timestamp,
            side="buy",
            price=state.price,
            size=btc_bought,
            entry_price=state.price,
            reason=signal.reason
        )
        self.stats.trades.append(trade)
    
    def _execute_sell(self, state: MarketState, signal: Signal):
        """Executa venda no backtest"""
        if self.balance_btc <= 0:
            return
        
        usdt_received = self.balance_btc * state.price
        fee = usdt_received * self.trading_fee
        usdt_received -= fee
        
        # Calcular PnL
        cost = (self.balance_usdt / (1 - self.max_position_pct)) * self.max_position_pct
        pnl = usdt_received - cost
        pnl_pct = (state.price / self.position_entry - 1) * 100 if self.position_entry > 0 else 0
        
        self.balance_usdt = self.initial_balance + pnl  # Reset para próximo trade
        
        # Registrar
        trade = BacktestTrade(
            timestamp=state.timestamp,
            side="sell",
            price=state.price,
            size=self.balance_btc,
            entry_price=self.position_entry,
            pnl=pnl,
            pnl_pct=pnl_pct,
            reason=signal.reason
        )
        self.stats.trades.append(trade)
        
        self.balance_btc = 0.0
        self.position_entry = 0.0


def main():
    parser = argparse.ArgumentParser(description="Backtest Trading Strategy")
    parser.add_argument("--db", default=os.getenv("DATABASE_URL", "postgresql://postgres:eddie_memory_2026@172.17.0.2:5432/postgres"),
                       help="PostgreSQL DSN")
    parser.add_argument("--hours", type=int, default=24,
                       help="Hours of historical data")
    parser.add_argument("--initial", type=float, default=10000.0,
                       help="Initial balance USDT")
    parser.add_argument("--rsi-oversold", type=int, default=40,
                       help="RSI oversold level")
    parser.add_argument("--rsi-overbought", type=int, default=60,
                       help="RSI overbought level")
    parser.add_argument("--compare", action="store_true",
                       help="Compare old vs new RSI levels")
    
    args = parser.parse_args()
    
    print("="*60)
    print("🧪 BACKTESTING ENGINE")
    print("="*60)
    
    if args.compare:
        print("\n📊 Comparando configurações de RSI...\n")
        
        # Old config (35/65)
        print("🔵 CONFIGURAÇÃO ANTIGA (RSI 35/65):")
        engine1 = BacktestEngine(args.db, args.initial)
        stats1 = engine1.run(args.hours, rsi_oversold=35, rsi_overbought=65)
        stats1.print_report()
        
        # New config (40/60)
        print("\n🟢 CONFIGURAÇÃO NOVA (RSI 40/60):")
        engine2 = BacktestEngine(args.db, args.initial)
        stats2 = engine2.run(args.hours, rsi_oversold=40, rsi_overbought=60)
        stats2.print_report()
        
        # Comparação
        print("\n" + "="*60)
        print("📊 COMPARAÇÃO")
        print("="*60)
        print(f"\n{'Métrica':<25} {'Antiga':<15} {'Nova':<15} {'Diferença'}")
        print("-"*60)
        
        metrics = [
            ("Trades Totais", stats1.total_trades, stats2.total_trades),
            ("Win Rate", f"{stats1.win_rate:.1%}", f"{stats2.win_rate:.1%}"),
            ("PnL Total", f"${stats1.total_pnl:.2f}", f"${stats2.total_pnl:.2f}"),
            ("PnL Médio", f"${stats1.avg_pnl:.2f}", f"${stats2.avg_pnl:.2f}"),
            ("Max Drawdown", f"${stats1.max_drawdown:.2f}", f"${stats2.max_drawdown:.2f}"),
            ("Sharpe Ratio", f"{stats1.sharpe_ratio:.2f}", f"{stats2.sharpe_ratio:.2f}"),
        ]
        
        for metric, old, new in metrics:
            if isinstance(old, (int, float)) and isinstance(new, (int, float)):
                diff = new - old
                diff_str = f"{'+' if diff > 0 else ''}{diff:.2f}"
            else:
                diff_str = "-"
            print(f"{metric:<25} {str(old):<15} {str(new):<15} {diff_str}")
        
        print("\n" + "="*60)
        
        # Recomendação
        if stats2.total_pnl > stats1.total_pnl:
            print("✅ RECOMENDAÇÃO: Usar nova configuração (RSI 40/60)")
        elif stats2.total_pnl < stats1.total_pnl:
            print("⚠️  RECOMENDAÇÃO: Manter configuração antiga (RSI 35/65)")
        else:
            print("ℹ️  RECOMENDAÇÃO: Ambas configurações são equivalentes")
        
    else:
        # Single backtest
        engine = BacktestEngine(args.db, args.initial)
        stats = engine.run(args.hours, args.rsi_oversold, args.rsi_overbought)
        stats.print_report()
    
    print()


if __name__ == "__main__":
    main()
