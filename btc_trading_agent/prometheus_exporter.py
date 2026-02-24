#!/usr/bin/env python3
"""
Prometheus Exporter para AutoCoinBot v2
Expõe métricas do agente de trading para o Prometheus/Grafana
Inclui métricas de Risk Management v2 (stop-loss, trailing-stop, daily-limits)
"""

import os
import sys
import json
import time
import sqlite3
import subprocess
import urllib.request
from pathlib import Path
from datetime import datetime
from typing import Dict
from http.server import HTTPServer, BaseHTTPRequestHandler

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

# Paths
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "trading_agent.db"
CONFIG_PATH = BASE_DIR / "config.json"


def load_config() -> Dict:
    """Carrega config.json"""
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


class MetricsCollector:
    """Coleta métricas do banco de dados SQLite"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _is_agent_process_running(self) -> bool:
        """Detecta se o processo trading_agent.py está rodando via pgrep"""
        try:
            result = subprocess.run(
                ["pgrep", "-f", "trading_agent.py"],
                capture_output=True, text=True, timeout=5
            )
            return bool(result.stdout.strip())
        except Exception:
            return False

    def _fetch_live_price(self) -> float:
        """Busca preço BTC-USDT ao vivo via KuCoin API"""
        try:
            req = urllib.request.Request(
                "https://api.kucoin.com/api/v1/market/orderbook/level1?symbol=BTC-USDT",
                headers={"User-Agent": "AutoCoinBot-Exporter/2.1"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                return float(data["data"]["price"])
        except Exception:
            return 0

    def get_metrics(self) -> Dict:
        """Coleta todas as métricas"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        metrics = {}
        now = datetime.now().timestamp()

        # ── Preço atual (DB com fallback para API live) ──
        cursor.execute("""
            SELECT price, timestamp FROM market_states
            ORDER BY timestamp DESC LIMIT 1
        """)
        result = cursor.fetchone()
        db_price = result[0] if result else 0
        db_price_age = (now - result[1]) if result and result[1] else float('inf')

        # Se preço do DB tem mais de 5 minutos, buscar ao vivo
        if db_price_age > 300:
            live_price = self._fetch_live_price()
            metrics['btc_price'] = live_price if live_price > 0 else db_price
        else:
            metrics['btc_price'] = db_price

        # ── Total de trades ──
        cursor.execute("SELECT COUNT(*) FROM trades")
        metrics['total_trades'] = cursor.fetchone()[0]

        # ── Trades com PnL ──
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning,
                SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as losing,
                SUM(pnl) as total_pnl,
                AVG(pnl) as avg_pnl,
                MAX(pnl) as best_trade,
                MIN(pnl) as worst_trade
            FROM trades WHERE pnl IS NOT NULL
        """)
        result = cursor.fetchone()
        if result and result[0]:
            metrics['total_trades_with_pnl'] = result[0]
            metrics['winning_trades'] = result[1] or 0
            metrics['losing_trades'] = result[2] or 0
            metrics['win_rate'] = (result[1] or 0) / result[0] if result[0] > 0 else 0
            metrics['total_pnl'] = result[3] if result[3] else 0
            metrics['avg_pnl'] = result[4] if result[4] else 0
            metrics['best_trade_pnl'] = result[5] if result[5] else 0
            metrics['worst_trade_pnl'] = result[6] if result[6] else 0
        else:
            metrics['total_trades_with_pnl'] = 0
            metrics['winning_trades'] = 0
            metrics['losing_trades'] = 0
            metrics['win_rate'] = 0
            metrics['total_pnl'] = 0
            metrics['avg_pnl'] = 0
            metrics['best_trade_pnl'] = 0
            metrics['worst_trade_pnl'] = 0

        # ── Decisões por tipo ──
        cursor.execute("""
            SELECT action, COUNT(*) FROM decisions
            GROUP BY action
        """)
        for row in cursor.fetchall():
            action = row[0].lower()
            metrics[f'decisions_{action}'] = row[1]

        # ── Trades por lado ──
        cursor.execute("""
            SELECT side, COUNT(*) FROM trades
            GROUP BY side
        """)
        for row in cursor.fetchall():
            side = row[0].lower()
            metrics[f'trades_{side}'] = row[1]

        # ── Indicadores técnicos (últimos valores) ──
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

        # ── Última atividade ──
        cursor.execute("SELECT MAX(timestamp) FROM market_states")
        result = cursor.fetchone()
        metrics['last_activity'] = result[0] if result and result[0] else 0

        # ── Último trade ──
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

        # ── Status do agente (process check + DB fallback) ──
        process_running = self._is_agent_process_running()
        db_recent = (now - metrics.get('last_activity', 0)) < 300  # 5 min
        metrics['agent_running'] = 1 if (process_running or db_recent) else 0

        # ── PnL acumulado (últimas 24h) ──
        cursor.execute("""
            SELECT timestamp, pnl
            FROM trades
            WHERE pnl IS NOT NULL AND timestamp > ?
            ORDER BY timestamp ASC
        """, (now - 86400,))

        cumulative_pnl = 0
        for row in cursor.fetchall():
            cumulative_pnl += row[1]
        metrics['cumulative_pnl_24h'] = cumulative_pnl

        # ── PnL acumulado total ──
        cursor.execute("SELECT COALESCE(SUM(pnl), 0) FROM trades WHERE pnl IS NOT NULL")
        metrics['cumulative_pnl'] = cursor.fetchone()[0]

        # ── Trades nas últimas 24h ──
        cursor.execute("SELECT COUNT(*) FROM trades WHERE timestamp > ?", (now - 86400,))
        metrics['trades_24h'] = cursor.fetchone()[0]

        # ── Trades na última hora ──
        cursor.execute("SELECT COUNT(*) FROM trades WHERE timestamp > ?", (now - 3600,))
        metrics['trades_1h'] = cursor.fetchone()[0]

        # ── Decisões na última hora ──
        cursor.execute("""
            SELECT action, COUNT(*) FROM decisions
            WHERE timestamp > ? GROUP BY action
        """, (now - 3600,))
        for row in cursor.fetchall():
            action = row[0].lower()
            metrics[f'decisions_1h_{action}'] = row[1]

        # ── Posição aberta (buy sem sell correspondente) ──
        cursor.execute("""
            SELECT
                SUM(CASE WHEN side = 'buy' THEN size ELSE -size END) as net_position,
                (SELECT price FROM trades ORDER BY timestamp DESC LIMIT 1) as last_price
            FROM trades
        """)
        result = cursor.fetchone()
        if result and result[0]:
            metrics['open_position_btc'] = max(0, result[0])
            metrics['open_position_usdt'] = max(0, result[0]) * (result[1] or 0)
        else:
            metrics['open_position_btc'] = 0
            metrics['open_position_usdt'] = 0

        # ── Exit reason stats (stop_loss, take_profit, trailing_stop, signal) ──
        try:
            cursor.execute("""
                SELECT exit_reason, COUNT(*) FROM trades
                WHERE exit_reason IS NOT NULL GROUP BY exit_reason
            """)
            for row in cursor.fetchall():
                reason = row[0].lower().replace(' ', '_')
                metrics[f'exit_{reason}'] = row[1]
        except sqlite3.OperationalError:
            pass  # coluna não existe ainda

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
        elif self.path == '/config':
            self.send_config()
        else:
            self.send_response(404)
            self.end_headers()

    def send_config(self):
        """Retorna config.json como JSON"""
        try:
            cfg = load_config()
            body = json.dumps(cfg, indent=2).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Error: {e}".encode('utf-8'))

    def send_metrics(self):
        """Envia métricas em formato Prometheus"""
        try:
            metrics = self.collector.get_metrics()
            cfg = load_config()

            output = []

            # ═══════════════ PREÇO ═══════════════
            output.append("# HELP btc_price Bitcoin price in USDT")
            output.append("# TYPE btc_price gauge")
            output.append(f'btc_price{{symbol="BTC-USDT"}} {metrics.get("btc_price", 0)}')
            output.append("")

            # ═══════════════ TRADING STATS ═══════════════
            output.append("# HELP btc_trading_total_trades Total number of trades executed")
            output.append("# TYPE btc_trading_total_trades counter")
            output.append(f'btc_trading_total_trades {metrics.get("total_trades", 0)}')
            output.append("")

            output.append("# HELP btc_trading_winning_trades Number of winning trades")
            output.append("# TYPE btc_trading_winning_trades counter")
            output.append(f'btc_trading_winning_trades {metrics.get("winning_trades", 0)}')
            output.append("")

            output.append("# HELP btc_trading_losing_trades Number of losing trades")
            output.append("# TYPE btc_trading_losing_trades counter")
            output.append(f'btc_trading_losing_trades {metrics.get("losing_trades", 0)}')
            output.append("")

            output.append("# HELP btc_trading_win_rate Win rate (0-1)")
            output.append("# TYPE btc_trading_win_rate gauge")
            output.append(f'btc_trading_win_rate {metrics.get("win_rate", 0):.4f}')
            output.append("")

            output.append("# HELP btc_trading_total_pnl Total profit and loss in USDT")
            output.append("# TYPE btc_trading_total_pnl gauge")
            output.append(f'btc_trading_total_pnl {metrics.get("total_pnl", 0):.4f}')
            output.append("")

            output.append("# HELP btc_trading_avg_pnl Average PnL per trade in USDT")
            output.append("# TYPE btc_trading_avg_pnl gauge")
            output.append(f'btc_trading_avg_pnl {metrics.get("avg_pnl", 0):.4f}')
            output.append("")

            output.append("# HELP btc_trading_best_trade_pnl Best single trade PnL in USDT")
            output.append("# TYPE btc_trading_best_trade_pnl gauge")
            output.append(f'btc_trading_best_trade_pnl {metrics.get("best_trade_pnl", 0):.4f}')
            output.append("")

            output.append("# HELP btc_trading_worst_trade_pnl Worst single trade PnL in USDT")
            output.append("# TYPE btc_trading_worst_trade_pnl gauge")
            output.append(f'btc_trading_worst_trade_pnl {metrics.get("worst_trade_pnl", 0):.4f}')
            output.append("")

            output.append("# HELP btc_trading_cumulative_pnl Cumulative PnL all time")
            output.append("# TYPE btc_trading_cumulative_pnl gauge")
            output.append(f'btc_trading_cumulative_pnl {metrics.get("cumulative_pnl", 0):.4f}')
            output.append("")

            output.append("# HELP btc_trading_cumulative_pnl_24h Cumulative PnL last 24h")
            output.append("# TYPE btc_trading_cumulative_pnl_24h gauge")
            output.append(f'btc_trading_cumulative_pnl_24h {metrics.get("cumulative_pnl_24h", 0):.4f}')
            output.append("")

            output.append("# HELP btc_trading_trades_24h Trades in last 24h")
            output.append("# TYPE btc_trading_trades_24h gauge")
            output.append(f'btc_trading_trades_24h {metrics.get("trades_24h", 0)}')
            output.append("")

            output.append("# HELP btc_trading_trades_1h Trades in last hour")
            output.append("# TYPE btc_trading_trades_1h gauge")
            output.append(f'btc_trading_trades_1h {metrics.get("trades_1h", 0)}')
            output.append("")

            # ═══════════════ DECISIONS ═══════════════
            output.append("# HELP btc_trading_decisions_total Total decisions by action")
            output.append("# TYPE btc_trading_decisions_total counter")
            for action in ['buy', 'sell', 'hold']:
                count = metrics.get(f'decisions_{action}', 0)
                output.append(f'btc_trading_decisions_total{{action="{action.upper()}"}} {count}')
            output.append("")

            output.append("# HELP btc_trading_decisions_1h Decisions in last hour by action")
            output.append("# TYPE btc_trading_decisions_1h gauge")
            for action in ['buy', 'sell', 'hold']:
                count = metrics.get(f'decisions_1h_{action}', 0)
                output.append(f'btc_trading_decisions_1h{{action="{action.upper()}"}} {count}')
            output.append("")

            # ═══════════════ TRADES BY SIDE ═══════════════
            output.append("# HELP btc_trading_trades_total Trades by side")
            output.append("# TYPE btc_trading_trades_total counter")
            for side in ['buy', 'sell']:
                count = metrics.get(f'trades_{side}', 0)
                output.append(f'btc_trading_trades_total{{side="{side}"}} {count}')
            output.append("")

            # ═══════════════ POSITION ═══════════════
            output.append("# HELP btc_trading_open_position_btc Open BTC position size")
            output.append("# TYPE btc_trading_open_position_btc gauge")
            output.append(f'btc_trading_open_position_btc {metrics.get("open_position_btc", 0):.8f}')
            output.append("")

            output.append("# HELP btc_trading_open_position_usdt Open position value in USDT")
            output.append("# TYPE btc_trading_open_position_usdt gauge")
            output.append(f'btc_trading_open_position_usdt {metrics.get("open_position_usdt", 0):.2f}')
            output.append("")

            # ═══════════════ TECHNICAL INDICATORS ═══════════════
            output.append("# HELP btc_trading_rsi Relative Strength Index (0-100)")
            output.append("# TYPE btc_trading_rsi gauge")
            output.append(f'btc_trading_rsi {metrics.get("rsi", 50):.2f}')
            output.append("")

            output.append("# HELP btc_trading_momentum Price momentum indicator")
            output.append("# TYPE btc_trading_momentum gauge")
            output.append(f'btc_trading_momentum {metrics.get("momentum", 0):.6f}')
            output.append("")

            output.append("# HELP btc_trading_volatility Market volatility (0-1)")
            output.append("# TYPE btc_trading_volatility gauge")
            output.append(f'btc_trading_volatility {metrics.get("volatility", 0):.6f}')
            output.append("")

            output.append("# HELP btc_trading_trend Market trend (-1 to +1)")
            output.append("# TYPE btc_trading_trend gauge")
            output.append(f'btc_trading_trend {metrics.get("trend", 0):.6f}')
            output.append("")

            output.append("# HELP btc_trading_orderbook_imbalance Order book imbalance (-1 to +1)")
            output.append("# TYPE btc_trading_orderbook_imbalance gauge")
            output.append(f'btc_trading_orderbook_imbalance {metrics.get("orderbook_imbalance", 0):.6f}')
            output.append("")

            # ═══════════════ RISK MANAGEMENT v2 ═══════════════
            output.append("# HELP btc_trading_exit_stop_loss Trades closed by stop loss")
            output.append("# TYPE btc_trading_exit_stop_loss counter")
            output.append(f'btc_trading_exit_stop_loss {metrics.get("exit_stop_loss", 0)}')
            output.append("")

            output.append("# HELP btc_trading_exit_take_profit Trades closed by take profit")
            output.append("# TYPE btc_trading_exit_take_profit counter")
            output.append(f'btc_trading_exit_take_profit {metrics.get("exit_take_profit", 0)}')
            output.append("")

            output.append("# HELP btc_trading_exit_trailing_stop Trades closed by trailing stop")
            output.append("# TYPE btc_trading_exit_trailing_stop counter")
            output.append(f'btc_trading_exit_trailing_stop {metrics.get("exit_trailing_stop", 0)}')
            output.append("")

            output.append("# HELP btc_trading_exit_signal Trades closed by model signal")
            output.append("# TYPE btc_trading_exit_signal counter")
            output.append(f'btc_trading_exit_signal {metrics.get("exit_signal", 0)}')
            output.append("")

            # ═══════════════ CONFIG (from config.json) ═══════════════
            dry_run = 1 if cfg.get("dry_run", True) else 0
            output.append("# HELP btc_trading_live_mode Live trading mode (0=dry_run, 1=live)")
            output.append("# TYPE btc_trading_live_mode gauge")
            output.append(f'btc_trading_live_mode {1 - dry_run}')
            output.append("")

            output.append("# HELP btc_trading_stop_loss_pct Configured stop loss percentage")
            output.append("# TYPE btc_trading_stop_loss_pct gauge")
            output.append(f'btc_trading_stop_loss_pct {cfg.get("stop_loss_pct", 0.02):.4f}')
            output.append("")

            output.append("# HELP btc_trading_take_profit_pct Configured take profit percentage")
            output.append("# TYPE btc_trading_take_profit_pct gauge")
            output.append(f'btc_trading_take_profit_pct {cfg.get("take_profit_pct", 0.03):.4f}')
            output.append("")

            trailing = cfg.get("trailing_stop", {})
            trail_enabled = 1 if trailing.get("enabled", False) else 0
            output.append("# HELP btc_trading_trailing_stop_enabled Trailing stop enabled (0/1)")
            output.append("# TYPE btc_trading_trailing_stop_enabled gauge")
            output.append(f'btc_trading_trailing_stop_enabled {trail_enabled}')
            output.append("")

            output.append("# HELP btc_trading_trailing_stop_activation_pct Trailing stop activation pct")
            output.append("# TYPE btc_trading_trailing_stop_activation_pct gauge")
            output.append(f'btc_trading_trailing_stop_activation_pct {trailing.get("activation_pct", 0.015):.4f}')
            output.append("")

            output.append("# HELP btc_trading_trailing_stop_trail_pct Trailing stop trail pct")
            output.append("# TYPE btc_trading_trailing_stop_trail_pct gauge")
            output.append(f'btc_trading_trailing_stop_trail_pct {trailing.get("trail_pct", 0.008):.4f}')
            output.append("")

            output.append("# HELP btc_trading_max_daily_trades Max daily trades allowed")
            output.append("# TYPE btc_trading_max_daily_trades gauge")
            output.append(f'btc_trading_max_daily_trades {cfg.get("max_daily_trades", 15)}')
            output.append("")

            output.append("# HELP btc_trading_max_daily_loss Max daily loss allowed in USDT")
            output.append("# TYPE btc_trading_max_daily_loss gauge")
            output.append(f'btc_trading_max_daily_loss {cfg.get("max_daily_loss", 150)}')
            output.append("")

            output.append("# HELP btc_trading_min_confidence Minimum confidence threshold")
            output.append("# TYPE btc_trading_min_confidence gauge")
            output.append(f'btc_trading_min_confidence {cfg.get("min_confidence", 0.60):.4f}')
            output.append("")

            # ═══════════════ AGENT STATUS ═══════════════
            output.append("# HELP btc_trading_agent_running Agent running status (1=running, 0=stopped)")
            output.append("# TYPE btc_trading_agent_running gauge")
            output.append(f'btc_trading_agent_running {metrics.get("agent_running", 0)}')
            output.append("")

            output.append("# HELP btc_trading_last_activity_timestamp Timestamp of last activity")
            output.append("# TYPE btc_trading_last_activity_timestamp gauge")
            output.append(f'btc_trading_last_activity_timestamp {metrics.get("last_activity", 0):.0f}')
            output.append("")

            # ═══════════════ LAST TRADE ═══════════════
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

            # ═══════════════ EXPORTER META ═══════════════
            output.append("# HELP btc_exporter_scrape_timestamp Exporter scrape timestamp")
            output.append("# TYPE btc_exporter_scrape_timestamp gauge")
            output.append(f'btc_exporter_scrape_timestamp {time.time():.0f}')
            output.append("")

            response = "\n".join(output)

            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(response.encode('utf-8'))

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Error: {e}".encode('utf-8'))

    def send_health(self):
        """Health check endpoint"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        health = {
            "status": "ok",
            "db_exists": DB_PATH.exists(),
            "timestamp": time.time()
        }
        self.wfile.write(json.dumps(health).encode('utf-8'))

    def log_message(self, format, *args):
        """Override to reduce logging noise — only log errors"""
        if args and '500' in str(args[0]):
            super().log_message(format, *args)


def main():
    """Main function"""
    port = 9092

    print("=" * 60)
    print("📊 AutoCoinBot Prometheus Exporter v2")
    print("=" * 60)
    print(f"\n🔗 Metrics: http://0.0.0.0:{port}/metrics")
    print(f"💚 Health:  http://0.0.0.0:{port}/health")
    print(f"⚙️  Config:  http://0.0.0.0:{port}/config")
    print(f"📁 Database: {DB_PATH}")
    print(f"📁 Config:   {CONFIG_PATH}")
    print("\n✅ Server started. Press Ctrl+C to stop.\n")

    server = HTTPServer(('0.0.0.0', port), PrometheusHandler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
