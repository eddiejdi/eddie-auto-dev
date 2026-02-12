#!/usr/bin/env python3
"""
Prometheus Exporter para AutoCoinBot
Expõe métricas do agente de trading para o Prometheus/Grafana
"""

import sys
import time
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

# Database path
DB_PATH = Path(__file__).parent / "data" / "trading_agent.db"


class MetricsCollector:
    """Coleta métricas do banco de dados"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def get_metrics(self) -> Dict:
        """Coleta todas as métricas"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        metrics = {}
        now = datetime.now().timestamp()
        
        # Preço atual
        cursor.execute("""
            SELECT price FROM market_states 
            ORDER BY timestamp DESC LIMIT 1
        """)
        result = cursor.fetchone()
        metrics['btc_price'] = result[0] if result else 0
        
        # Total de trades
        cursor.execute("SELECT COUNT(*) FROM trades")
        metrics['total_trades'] = cursor.fetchone()[0]
        
        # Trades com PnL
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning,
                SUM(pnl) as total_pnl,
                AVG(pnl) as avg_pnl
            FROM trades WHERE pnl IS NOT NULL
        """)
        result = cursor.fetchone()
        if result and result[0]:
            metrics['total_trades_with_pnl'] = result[0]
            metrics['winning_trades'] = result[1]
            metrics['win_rate'] = result[1] / result[0] if result[0] > 0 else 0
            metrics['total_pnl'] = result[2] if result[2] else 0
            metrics['avg_pnl'] = result[3] if result[3] else 0
        else:
            metrics['total_trades_with_pnl'] = 0
            metrics['winning_trades'] = 0
            metrics['win_rate'] = 0
            metrics['total_pnl'] = 0
            metrics['avg_pnl'] = 0
        
        # Decisões por tipo
        cursor.execute("""
            SELECT action, COUNT(*) FROM decisions 
            GROUP BY action
        """)
        for row in cursor.fetchall():
            action = row[0].lower()
            metrics[f'decisions_{action}'] = row[1]
        
        # Trades por lado
        cursor.execute("""
            SELECT side, COUNT(*) FROM trades 
            GROUP BY side
        """)
        for row in cursor.fetchall():
            side = row[0].lower()
            metrics[f'trades_{side}'] = row[1]
        
        # Indicadores técnicos (últimos valores)
        cursor.execute("""
            SELECT rsi, momentum, volatility, trend, orderbook_imbalance
            FROM market_states 
            ORDER BY timestamp DESC LIMIT 1
        """)
        result = cursor.fetchone()
        if result:
            metrics['rsi'] = result[0] if result[0] else 50
            metrics['momentum'] = result[1] if result[1] else 0
            metrics['volatility'] = result[2] if result[2] else 0
            metrics['trend'] = result[3] if result[3] else 0
            metrics['orderbook_imbalance'] = result[4] if result[4] else 0
        
        # Última atividade
        cursor.execute("""
            SELECT MAX(timestamp) FROM market_states
        """)
        result = cursor.fetchone()
        metrics['last_activity'] = result[0] if result and result[0] else 0
        
        # Último trade
        cursor.execute("""
            SELECT timestamp, side, price, size, pnl 
            FROM trades 
            ORDER BY timestamp DESC LIMIT 1
        """)
        result = cursor.fetchone()
        if result:
            metrics['last_trade_timestamp'] = result[0]
            metrics['last_trade_side'] = 1 if result[1] == 'buy' else 0
            metrics['last_trade_price'] = result[2]
            metrics['last_trade_size'] = result[3]
            metrics['last_trade_pnl'] = result[4] if result[4] else 0
        
        # Status do agente (ativo se última atividade < 1 minuto)
        metrics['agent_running'] = 1 if (now - metrics.get('last_activity', 0)) < 60 else 0
        
        # PnL acumulado ao longo do tempo (últimas 24h)
        cursor.execute("""
            SELECT timestamp, pnl 
            FROM trades 
            WHERE pnl IS NOT NULL 
            AND timestamp > ?
            ORDER BY timestamp ASC
        """, (now - 86400,))
        
        cumulative_pnl = 0
        pnl_series = []
        for row in cursor.fetchall():
            cumulative_pnl += row[1]
            pnl_series.append((row[0], cumulative_pnl))
        
        metrics['cumulative_pnl'] = cumulative_pnl
        
        conn.close()
        return metrics


class PrometheusHandler(BaseHTTPRequestHandler):
    """Handler HTTP para expor métricas no formato Prometheus"""
    
    collector = MetricsCollector(str(DB_PATH))
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/metrics':
            self.send_metrics()
        elif self.path == '/health':
            self.send_health()
        else:
            self.send_response(404)
            self.end_headers()
    
    def send_metrics(self):
        """Envia métricas em formato Prometheus"""
        try:
            metrics = self.collector.get_metrics()
            
            output = []
            
            # Header
            output.append("# HELP btc_price Bitcoin price in USDT")
            output.append("# TYPE btc_price gauge")
            output.append(f'btc_price{{symbol="BTC-USDT"}} {metrics.get("btc_price", 0)}')
            output.append("")
            
            # Trading metrics
            output.append("# HELP btc_trading_total_trades Total number of trades executed")
            output.append("# TYPE btc_trading_total_trades counter")
            output.append(f'btc_trading_total_trades {metrics.get("total_trades", 0)}')
            output.append("")
            
            output.append("# HELP btc_trading_winning_trades Number of winning trades")
            output.append("# TYPE btc_trading_winning_trades counter")
            output.append(f'btc_trading_winning_trades {metrics.get("winning_trades", 0)}')
            output.append("")
            
            output.append("# HELP btc_trading_win_rate Win rate (0-1)")
            output.append("# TYPE btc_trading_win_rate gauge")
            output.append(f'btc_trading_win_rate {metrics.get("win_rate", 0):.4f}')
            output.append("")
            
            output.append("# HELP btc_trading_total_pnl Total profit and loss in USDT")
            output.append("# TYPE btc_trading_total_pnl gauge")
            output.append(f'btc_trading_total_pnl {metrics.get("total_pnl", 0):.2f}')
            output.append("")
            
            output.append("# HELP btc_trading_avg_pnl Average profit and loss per trade")
            output.append("# TYPE btc_trading_avg_pnl gauge")
            output.append(f'btc_trading_avg_pnl {metrics.get("avg_pnl", 0):.2f}')
            output.append("")
            
            output.append("# HELP btc_trading_cumulative_pnl Cumulative PnL over time")
            output.append("# TYPE btc_trading_cumulative_pnl gauge")
            output.append(f'btc_trading_cumulative_pnl {metrics.get("cumulative_pnl", 0):.2f}')
            output.append("")
            
            # Decisions
            output.append("# HELP btc_trading_decisions_total Total decisions by action")
            output.append("# TYPE btc_trading_decisions_total counter")
            for action in ['buy', 'sell', 'hold']:
                count = metrics.get(f'decisions_{action}', 0)
                output.append(f'btc_trading_decisions_total{{action="{action.upper()}"}} {count}')
            output.append("")
            
            # Trades by side
            output.append("# HELP btc_trading_trades_total Trades by side")
            output.append("# TYPE btc_trading_trades_total counter")
            for side in ['buy', 'sell']:
                count = metrics.get(f'trades_{side}', 0)
                output.append(f'btc_trading_trades_total{{side="{side}"}} {count}')
            output.append("")
            
            # Technical indicators
            output.append("# HELP btc_trading_rsi Relative Strength Index (0-100)")
            output.append("# TYPE btc_trading_rsi gauge")
            output.append(f'btc_trading_rsi {metrics.get("rsi", 50):.2f}')
            output.append("")
            
            output.append("# HELP btc_trading_momentum Price momentum indicator")
            output.append("# TYPE btc_trading_momentum gauge")
            output.append(f'btc_trading_momentum {metrics.get("momentum", 0):.4f}')
            output.append("")
            
            output.append("# HELP btc_trading_volatility Market volatility (0-1)")
            output.append("# TYPE btc_trading_volatility gauge")
            output.append(f'btc_trading_volatility {metrics.get("volatility", 0):.4f}')
            output.append("")
            
            output.append("# HELP btc_trading_trend Market trend (-1 to +1)")
            output.append("# TYPE btc_trading_trend gauge")
            output.append(f'btc_trading_trend {metrics.get("trend", 0):.4f}')
            output.append("")
            
            output.append("# HELP btc_trading_orderbook_imbalance Order book imbalance (-1 to +1)")
            output.append("# TYPE btc_trading_orderbook_imbalance gauge")
            output.append(f'btc_trading_orderbook_imbalance {metrics.get("orderbook_imbalance", 0):.4f}')
            output.append("")
            
            # Agent status
            output.append("# HELP btc_trading_agent_running Agent running status (1=running, 0=stopped)")
            output.append("# TYPE btc_trading_agent_running gauge")
            output.append(f'btc_trading_agent_running {metrics.get("agent_running", 0)}')
            output.append("")
            
            output.append("# HELP btc_trading_last_activity_timestamp Timestamp of last activity")
            output.append("# TYPE btc_trading_last_activity_timestamp gauge")
            output.append(f'btc_trading_last_activity_timestamp {metrics.get("last_activity", 0):.0f}')
            output.append("")
            
            # Last trade info
            if metrics.get('last_trade_timestamp'):
                output.append("# HELP btc_trading_last_trade_info Last trade information")
                output.append("# TYPE btc_trading_last_trade_info gauge")
                side = 'buy' if metrics.get('last_trade_side', 0) == 1 else 'sell'
                output.append(
                    f'btc_trading_last_trade_info{{side="{side}",'
                    f'price="{metrics.get("last_trade_price", 0):.2f}",'
                    f'size="{metrics.get("last_trade_size", 0):.6f}",'
                    f'pnl="{metrics.get("last_trade_pnl", 0):.2f}"}} '
                    f'{metrics.get("last_trade_timestamp", 0):.0f}'
                )
                output.append("")
            
            # Model info (mock - would need to read from model file)
            output.append("# HELP btc_trading_model_episodes Total training episodes")
            output.append("# TYPE btc_trading_model_episodes counter")
            output.append(f'btc_trading_model_episodes 66588')
            output.append("")
            
            output.append("# HELP btc_trading_live_mode Live trading mode (0=dry_run, 1=live)")
            output.append("# TYPE btc_trading_live_mode gauge")
            output.append(f'btc_trading_live_mode 0')  # Would need to read from config
            output.append("")
            
            response = "\n".join(output)
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(response.encode('utf-8'))
            
        except Exception as e:
            print(f"Error generating metrics: {e}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Error: {e}".encode('utf-8'))
    
    def send_health(self):
        """Health check endpoint"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK")
    
    def log_message(self, format, *args):
        """Override to reduce logging noise"""
        pass


def main():
    """Main function"""
    port = 9092  # Changed from 9090 to avoid conflict
    
    print("="*60)
    print("📊 AutoCoinBot Prometheus Exporter")
    print("="*60)
    print(f"\n🔗 Metrics: http://localhost:{port}/metrics")
    print(f"💚 Health:  http://localhost:{port}/health")
    print(f"📁 Database: {DB_PATH}")
    print("\n✅ Server started. Press Ctrl+C to stop.\n")
    
    server = HTTPServer(('0.0.0.0', port), PrometheusHandler)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
