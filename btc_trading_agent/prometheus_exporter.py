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
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

# Paths
BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"

# Resolve DB path using the same env var used by training_db if present; otherwise
# fall back to the local data path. Importing training_db allows a single source
# of truth when running in the same environment.
try:
    from btc_trading_agent import training_db as _training_db
    DB_PATH = Path(os.getenv("BTC_DB_PATH") or os.getenv("TRAINING_DB_PATH") or str(_training_db.DB_PATH))
except Exception:
    DB_PATH = BASE_DIR / "data" / "trading_agent.db"


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
        """Coleta todas as métricas, separadas por modo (dry/live)"""
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

        # ── Coleta stats por modo (dry_run=1 e dry_run=0) ──
        for mode_val, mode_name in [(1, 'dry'), (0, 'live')]:
            prefix = f'{mode_name}_'

            # Total de trades
            cursor.execute("SELECT COUNT(*) FROM trades WHERE dry_run=?", (mode_val,))
            metrics[f'{prefix}total_trades'] = cursor.fetchone()[0]

            # Trades com PnL
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning,
                    SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as losing,
                    SUM(pnl) as total_pnl,
                    AVG(pnl) as avg_pnl,
                    MAX(pnl) as best_trade,
                    MIN(pnl) as worst_trade
                FROM trades WHERE pnl IS NOT NULL AND dry_run=?
            """, (mode_val,))
            result = cursor.fetchone()
            if result and result[0]:
                metrics[f'{prefix}winning_trades'] = result[1] or 0
                metrics[f'{prefix}losing_trades'] = result[2] or 0
                metrics[f'{prefix}win_rate'] = (result[1] or 0) / result[0] if result[0] > 0 else 0
                metrics[f'{prefix}total_pnl'] = result[3] if result[3] else 0
                metrics[f'{prefix}avg_pnl'] = result[4] if result[4] else 0
                metrics[f'{prefix}best_trade_pnl'] = result[5] if result[5] else 0
                metrics[f'{prefix}worst_trade_pnl'] = result[6] if result[6] else 0
            else:
                for k in ['winning_trades', 'losing_trades', 'win_rate', 'total_pnl',
                           'avg_pnl', 'best_trade_pnl', 'worst_trade_pnl']:
                    metrics[f'{prefix}{k}'] = 0

            # PnL acumulado total
            cursor.execute("SELECT COALESCE(SUM(pnl), 0) FROM trades WHERE pnl IS NOT NULL AND dry_run=?", (mode_val,))
            metrics[f'{prefix}cumulative_pnl'] = cursor.fetchone()[0]

            # PnL últimas 24h
            cursor.execute("""
                SELECT COALESCE(SUM(pnl), 0) FROM trades
                WHERE pnl IS NOT NULL AND timestamp > ? AND dry_run=?
            """, (now - 86400, mode_val))
            metrics[f'{prefix}cumulative_pnl_24h'] = cursor.fetchone()[0]

            # Trades 24h / 1h
            cursor.execute("SELECT COUNT(*) FROM trades WHERE timestamp > ? AND dry_run=?", (now - 86400, mode_val))
            metrics[f'{prefix}trades_24h'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM trades WHERE timestamp > ? AND dry_run=?", (now - 3600, mode_val))
            metrics[f'{prefix}trades_1h'] = cursor.fetchone()[0]

            # Trades por lado
            cursor.execute("SELECT side, COUNT(*) FROM trades WHERE dry_run=? GROUP BY side", (mode_val,))
            for row in cursor.fetchall():
                metrics[f'{prefix}trades_{row[0].lower()}'] = row[1]

            # Posição aberta
            cursor.execute("""
                SELECT SUM(CASE WHEN side='buy' THEN size ELSE -size END) as net,
                       (SELECT price FROM trades WHERE dry_run=? ORDER BY timestamp DESC LIMIT 1) as lp
                FROM trades WHERE dry_run=?
            """, (mode_val, mode_val))
            result = cursor.fetchone()
            if result and result[0]:
                metrics[f'{prefix}open_position_btc'] = max(0, result[0])
                metrics[f'{prefix}open_position_usdt'] = max(0, result[0]) * (result[1] or 0)
            else:
                metrics[f'{prefix}open_position_btc'] = 0
                metrics[f'{prefix}open_position_usdt'] = 0

            # Exit reasons
            try:
                cursor.execute("""
                    SELECT exit_reason, COUNT(*) FROM trades
                    WHERE exit_reason IS NOT NULL AND dry_run=? GROUP BY exit_reason
                """, (mode_val,))
                for row in cursor.fetchall():
                    reason = row[0].lower().replace(' ', '_')
                    metrics[f'{prefix}exit_{reason}'] = row[1]
            except sqlite3.OperationalError:
                pass

            # Último trade do modo
            cursor.execute("""
                SELECT timestamp, side, price, size, pnl
                FROM trades WHERE dry_run=? ORDER BY timestamp DESC LIMIT 1
            """, (mode_val,))
            result = cursor.fetchone()
            if result:
                metrics[f'{prefix}last_trade_timestamp'] = result[0]
                metrics[f'{prefix}last_trade_side'] = 1 if result[1] == 'buy' else 0
                metrics[f'{prefix}last_trade_price'] = result[2]
                metrics[f'{prefix}last_trade_size'] = result[3]
                metrics[f'{prefix}last_trade_pnl'] = result[4] if result[4] else 0

        # ── Decisões por tipo (global — não tem dry_run na tabela decisions) ──
        cursor.execute("SELECT action, COUNT(*) FROM decisions GROUP BY action")
        for row in cursor.fetchall():
            metrics[f'decisions_{row[0].lower()}'] = row[1]

        cursor.execute("""
            SELECT action, COUNT(*) FROM decisions
            WHERE timestamp > ? GROUP BY action
        """, (now - 3600,))
        for row in cursor.fetchall():
            metrics[f'decisions_1h_{row[0].lower()}'] = row[1]

        # ── Indicadores técnicos (últimos valores) ──
        cursor.execute("""
            SELECT rsi, momentum, volatility, trend, orderbook_imbalance
            FROM market_states ORDER BY timestamp DESC LIMIT 1
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

        # ── Status do agente (process check + DB fallback) ──
        process_running = self._is_agent_process_running()
        db_recent = (now - metrics.get('last_activity', 0)) < 300
        metrics['agent_running'] = 1 if (process_running or db_recent) else 0

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
        elif self.path == '/mode':
            self.send_mode()
        elif self.path == '/toggle-mode':
            self.handle_toggle_mode()
        elif self.path == '/set-live':
            self._set_mode_direct(True)
        elif self.path == '/set-dry':
            self._set_mode_direct(False)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        """Handle POST requests"""
        if self.path == '/toggle-mode':
            self.handle_toggle_mode()
        elif self.path == '/set-mode':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length else b'{}'
            self.handle_set_mode(body)
        else:
            self.send_response(404)
            self.end_headers()

    def _cors_headers(self):
        """Add CORS headers for Grafana access"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def send_mode(self):
        """Retorna modo atual — HTML para browser, JSON para API"""
        try:
            cfg = load_config()
            live = cfg.get('live_mode', False)

            accept = self.headers.get('Accept', '')
            if 'text/html' in accept:
                mode_emoji = '💰' if live else '🧪'
                mode_text = 'REAL (LIVE)' if live else 'DRY RUN (Simulação)'
                bg_color = '#e74c3c' if live else '#3498db'
                html = f"""<!DOCTYPE html>
    <html><head><meta charset="utf-8"><title>AutoCoinBot Mode</title>
    <style>
body {{ font-family: -apple-system, sans-serif; background: #1a1a2e; color: #eee;
       display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }}
.card {{ background: #16213e; border-radius: 16px; padding: 40px; text-align: center;
         box-shadow: 0 8px 32px rgba(0,0,0,0.4); max-width: 420px; }}
.badge {{ display: inline-block; padding: 12px 28px; border-radius: 12px; font-size: 24px;
          font-weight: bold; color: white; background: {bg_color}; margin: 16px 0; }}
.btn {{ display: inline-block; padding: 14px 32px; border-radius: 10px; font-size: 16px;
        font-weight: bold; color: white; text-decoration: none; margin: 8px;
        transition: transform 0.2s; }}
.btn:hover {{ transform: scale(1.05); }}
.btn-toggle {{ background: linear-gradient(135deg, #f39c12, #e67e22); }}
.btn-live {{ background: linear-gradient(135deg, #e74c3c, #c0392b); }}
.btn-dry {{ background: linear-gradient(135deg, #3498db, #2980b9); }}
</style></head>
<body><div class="card">
<h2>🤖 AutoCoinBot — Modo Atual</h2>
<div class="badge">{mode_emoji} {mode_text}</div>
<div style="margin-top:20px">
  <a class="btn btn-toggle" href="/toggle-mode">🔄 Alternar</a>
</div>
<div style="margin-top:8px">
  <a class="btn btn-live" href="/set-live">💰 REAL</a>
  <a class="btn btn-dry" href="/set-dry">🧪 DRY</a>
</div>
</div></body></html>"""
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self._cors_headers()
                self.end_headers()
                self.wfile.write(html.encode('utf-8'))
            else:
                body = json.dumps({
                    'live_mode': live,
                    'mode': 'LIVE' if live else 'DRY_RUN',
                    'label': '💰 REAL' if live else '🧪 DRY RUN'
                }).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self._cors_headers()
                self.end_headers()
                self.wfile.write(body)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f'{{"error": "{e}"}}'.encode('utf-8'))

    def handle_toggle_mode(self):
        """Alterna entre LIVE e DRY RUN no config.json — retorna HTML amigável"""
        try:
            cfg = load_config()
            old_mode = cfg.get('live_mode', False)
            cfg['live_mode'] = not old_mode
            cfg['dry_run'] = old_mode  # dry_run = inverso de live_mode
            with open(CONFIG_PATH, 'w') as f:
                json.dump(cfg, f, indent=2)
            new_mode = cfg['live_mode']
            print(f"🔄 Mode toggled: {'LIVE' if old_mode else 'DRY_RUN'} → {'LIVE' if new_mode else 'DRY_RUN'}")

            # Check Accept header — return HTML for browsers, JSON for API
            accept = self.headers.get('Accept', '')
            if 'text/html' in accept:
                self._send_mode_html(new_mode, old_mode)
            else:
                body = json.dumps({
                    'success': True,
                    'previous': 'LIVE' if old_mode else 'DRY_RUN',
                    'current': 'LIVE' if new_mode else 'DRY_RUN',
                    'label': '💰 REAL' if new_mode else '🧪 DRY RUN',
                    'live_mode': new_mode
                }).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self._cors_headers()
                self.end_headers()
                self.wfile.write(body)
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(f'{{"error": "{e}"}}'.encode('utf-8'))

    def _set_mode_direct(self, live: bool):
        """Define modo diretamente via GET /set-live ou /set-dry"""
        try:
            cfg = load_config()
            old_mode = cfg.get('live_mode', False)
            cfg['live_mode'] = live
            cfg['dry_run'] = not live  # dry_run = inverso de live_mode
            with open(CONFIG_PATH, 'w') as f:
                json.dump(cfg, f, indent=2)
            print(f"✅ Mode set: {'LIVE' if old_mode else 'DRY_RUN'} → {'LIVE' if live else 'DRY_RUN'}")
            # Honor Accept header: return HTML for browsers, JSON for API/clients
            accept = self.headers.get('Accept', '')
            if 'text/html' in accept:
                self._send_mode_html(live, old_mode)
            else:
                body = json.dumps({
                    'success': True,
                    'previous': 'LIVE' if old_mode else 'DRY_RUN',
                    'current': 'LIVE' if live else 'DRY_RUN',
                    'live_mode': live,
                    'label': '💰 REAL' if live else '🧪 DRY RUN'
                }).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self._cors_headers()
                self.end_headers()
                self.wfile.write(body)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f'{{"error": "{e}"}}'.encode('utf-8'))

    def _send_mode_html(self, current_live: bool, previous_live: bool):
        """Retorna página HTML bonita com status e botões"""
        mode_emoji = '💰' if current_live else '🧪'
        mode_text = 'REAL (LIVE)' if current_live else 'DRY RUN (Simulação)'
        bg_color = '#e74c3c' if current_live else '#3498db'
        prev_text = 'LIVE' if previous_live else 'DRY RUN'
        curr_text = 'LIVE' if current_live else 'DRY RUN'

        html = f"""<!DOCTYPE html>
    <html><head><meta charset="utf-8"><title>AutoCoinBot Mode</title>
    <style>
body {{ font-family: -apple-system, sans-serif; background: #1a1a2e; color: #eee;
       display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }}
.card {{ background: #16213e; border-radius: 16px; padding: 40px; text-align: center;
         box-shadow: 0 8px 32px rgba(0,0,0,0.4); max-width: 420px; }}
.badge {{ display: inline-block; padding: 12px 28px; border-radius: 12px; font-size: 24px;
          font-weight: bold; color: white; background: {bg_color}; margin: 16px 0; }}
.change {{ color: #888; font-size: 14px; margin: 8px 0; }}
.btn {{ display: inline-block; padding: 14px 32px; border-radius: 10px; font-size: 16px;
        font-weight: bold; color: white; text-decoration: none; margin: 8px;
        transition: transform 0.2s, box-shadow 0.2s; }}
.btn:hover {{ transform: scale(1.05); box-shadow: 0 4px 12px rgba(0,0,0,0.3); }}
.btn-live {{ background: linear-gradient(135deg, #e74c3c, #c0392b); }}
.btn-dry {{ background: linear-gradient(135deg, #3498db, #2980b9); }}
.btn-toggle {{ background: linear-gradient(135deg, #f39c12, #e67e22); }}
.note {{ color: #666; font-size: 12px; margin-top: 16px; }}
</style></head>
<body><div class="card">
<h2>🤖 AutoCoinBot</h2>
<div class="badge">{mode_emoji} {mode_text}</div>
<div class="change">Alterado: {prev_text} → {curr_text}</div>
<div style="margin-top:20px">
  <a class="btn btn-toggle" href="/toggle-mode">🔄 Alternar</a>
</div>
<div style="margin-top:8px">
  <a class="btn btn-live" href="/set-live">💰 REAL</a>
  <a class="btn btn-dry" href="/set-dry">🧪 DRY</a>
</div>
<div class="note">Redirecionando em 3s... <a href="/mode" style="color:#3498db">ver status</a></div>
</div></body></html>"""

        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self._cors_headers()
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def handle_set_mode(self, body: bytes):
        """Define modo explicitamente: {"live_mode": true/false}"""
        try:
            data = json.loads(body) if body else {}
            if 'live_mode' not in data:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"error": "missing live_mode field"}')
                return
            cfg = load_config()
            old_mode = cfg.get('live_mode', False)
            cfg['live_mode'] = bool(data['live_mode'])
            with open(CONFIG_PATH, 'w') as f:
                json.dump(cfg, f, indent=2)
            new_mode = cfg['live_mode']
            body = json.dumps({
                'success': True,
                'previous': 'LIVE' if old_mode else 'DRY_RUN',
                'current': 'LIVE' if new_mode else 'DRY_RUN',
                'live_mode': new_mode
            }).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._cors_headers()
            self.end_headers()
            self.wfile.write(body)
            print(f"✅ Mode set: {'LIVE' if old_mode else 'DRY_RUN'} → {'LIVE' if new_mode else 'DRY_RUN'}")
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(f'{{"error": "{e}"}}'.encode('utf-8'))

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
        """Envia métricas em formato Prometheus — filtradas pelo modo ativo"""
        try:
            metrics = self.collector.get_metrics()
            cfg = load_config()

            # Determinar modo ativo: live_mode=true → prefixo 'live_', senão 'dry_'
            is_live = cfg.get('live_mode', False)
            active = 'live_' if is_live else 'dry_'
            active_label = 'live' if is_live else 'dry'

            output = []

            # ═══════════════ PREÇO ═══════════════
            output.append("# HELP btc_price Bitcoin price in USDT")
            output.append("# TYPE btc_price gauge")
            output.append(f'btc_price{{symbol="BTC-USDT"}} {metrics.get("btc_price", 0)}')
            output.append("")

            # ═══════════════ TRADING STATS (modo ativo) ═══════════════
            # Métricas principais refletem o modo selecionado
            stat_metrics = [
                ('btc_trading_total_trades', 'total_trades', 'Total trades (active mode)', 'counter', '{v}'),
                ('btc_trading_winning_trades', 'winning_trades', 'Winning trades (active mode)', 'counter', '{v}'),
                ('btc_trading_losing_trades', 'losing_trades', 'Losing trades (active mode)', 'counter', '{v}'),
                ('btc_trading_win_rate', 'win_rate', 'Win rate 0-1 (active mode)', 'gauge', '{v:.4f}'),
                ('btc_trading_total_pnl', 'total_pnl', 'Total PnL USDT (active mode)', 'gauge', '{v:.4f}'),
                ('btc_trading_avg_pnl', 'avg_pnl', 'Avg PnL per trade (active mode)', 'gauge', '{v:.4f}'),
                ('btc_trading_best_trade_pnl', 'best_trade_pnl', 'Best trade PnL (active mode)', 'gauge', '{v:.4f}'),
                ('btc_trading_worst_trade_pnl', 'worst_trade_pnl', 'Worst trade PnL (active mode)', 'gauge', '{v:.4f}'),
                ('btc_trading_cumulative_pnl', 'cumulative_pnl', 'Cumulative PnL all time (active mode)', 'gauge', '{v:.4f}'),
                ('btc_trading_cumulative_pnl_24h', 'cumulative_pnl_24h', 'Cumulative PnL 24h (active mode)', 'gauge', '{v:.4f}'),
                ('btc_trading_trades_24h', 'trades_24h', 'Trades in 24h (active mode)', 'gauge', '{v}'),
                ('btc_trading_trades_1h', 'trades_1h', 'Trades in 1h (active mode)', 'gauge', '{v}'),
                ('btc_trading_open_position_btc', 'open_position_btc', 'Open BTC position (active mode)', 'gauge', '{v:.8f}'),
                ('btc_trading_open_position_usdt', 'open_position_usdt', 'Open USDT position (active mode)', 'gauge', '{v:.2f}'),
            ]

            for prom_name, key, help_text, ptype, fmt in stat_metrics:
                v = metrics.get(f'{active}{key}', 0)
                output.append(f"# HELP {prom_name} {help_text}")
                output.append(f"# TYPE {prom_name} {ptype}")
                output.append(f'{prom_name} {fmt.format(v=v)}')
                output.append("")

            # ═══════════════ STATS POR MODO (com label) ═══════════════
            output.append("# HELP btc_trading_mode_total_trades Total trades by mode")
            output.append("# TYPE btc_trading_mode_total_trades counter")
            for mode in ['dry', 'live']:
                v = metrics.get(f'{mode}_total_trades', 0)
                output.append(f'btc_trading_mode_total_trades{{mode="{mode}"}} {v}')
            output.append("")

            output.append("# HELP btc_trading_mode_pnl Total PnL by mode")
            output.append("# TYPE btc_trading_mode_pnl gauge")
            for mode in ['dry', 'live']:
                v = metrics.get(f'{mode}_total_pnl', 0)
                output.append(f'btc_trading_mode_pnl{{mode="{mode}"}} {v:.4f}')
            output.append("")

            output.append("# HELP btc_trading_mode_win_rate Win rate by mode")
            output.append("# TYPE btc_trading_mode_win_rate gauge")
            for mode in ['dry', 'live']:
                v = metrics.get(f'{mode}_win_rate', 0)
                output.append(f'btc_trading_mode_win_rate{{mode="{mode}"}} {v:.4f}')
            output.append("")

            output.append("# HELP btc_trading_mode_winning Winning trades by mode")
            output.append("# TYPE btc_trading_mode_winning counter")
            for mode in ['dry', 'live']:
                v = metrics.get(f'{mode}_winning_trades', 0)
                output.append(f'btc_trading_mode_winning{{mode="{mode}"}} {v}')
            output.append("")

            output.append("# HELP btc_trading_mode_losing Losing trades by mode")
            output.append("# TYPE btc_trading_mode_losing counter")
            for mode in ['dry', 'live']:
                v = metrics.get(f'{mode}_losing_trades', 0)
                output.append(f'btc_trading_mode_losing{{mode="{mode}"}} {v}')
            output.append("")

            # ═══════════════ TRADES BY SIDE (modo ativo) ═══════════════
            output.append("# HELP btc_trading_trades_total Trades by side (active mode)")
            output.append("# TYPE btc_trading_trades_total counter")
            for side in ['buy', 'sell']:
                count = metrics.get(f'{active}trades_{side}', 0)
                output.append(f'btc_trading_trades_total{{side="{side}"}} {count}')
            output.append("")

            # ═══════════════ DECISIONS (global) ═══════════════
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

            # ═══════════════ TECHNICAL INDICATORS ═══════════════
            indicators = [
                ('btc_trading_rsi', 'rsi', 'RSI (0-100)', 50, '{v:.2f}'),
                ('btc_trading_momentum', 'momentum', 'Price momentum', 0, '{v:.6f}'),
                ('btc_trading_volatility', 'volatility', 'Volatility (0-1)', 0, '{v:.6f}'),
                ('btc_trading_trend', 'trend', 'Trend (-1 to +1)', 0, '{v:.6f}'),
                ('btc_trading_orderbook_imbalance', 'orderbook_imbalance', 'Orderbook imbalance', 0, '{v:.6f}'),
            ]
            for prom_name, key, help_text, default, fmt in indicators:
                v = metrics.get(key, default)
                output.append(f"# HELP {prom_name} {help_text}")
                output.append(f"# TYPE {prom_name} gauge")
                output.append(f'{prom_name} {fmt.format(v=v)}')
                output.append("")

            # ═══════════════ EXIT REASONS (modo ativo) ═══════════════
            for reason in ['stop_loss', 'take_profit', 'trailing_stop', 'signal']:
                prom_name = f'btc_trading_exit_{reason}'
                v = metrics.get(f'{active}exit_{reason}', 0)
                output.append(f"# HELP {prom_name} Trades closed by {reason} (active mode)")
                output.append(f"# TYPE {prom_name} counter")
                output.append(f'{prom_name} {v}')
                output.append("")

            # ═══════════════ CONFIG ═══════════════
            live_val = 1 if cfg.get('live_mode', False) else 0
            output.append("# HELP btc_trading_live_mode Live trading mode (0=dry_run, 1=live)")
            output.append("# TYPE btc_trading_live_mode gauge")
            output.append(f'btc_trading_live_mode {live_val}')
            output.append("")

            config_metrics = [
                ('btc_trading_stop_loss_pct', 'stop_loss_pct', 0.02, '{v:.4f}'),
                ('btc_trading_take_profit_pct', 'take_profit_pct', 0.03, '{v:.4f}'),
                ('btc_trading_max_daily_trades', 'max_daily_trades', 15, '{v}'),
                ('btc_trading_max_daily_loss', 'max_daily_loss', 150, '{v}'),
                ('btc_trading_min_confidence', 'min_confidence', 0.60, '{v:.4f}'),
            ]
            for prom_name, key, default, fmt in config_metrics:
                v = cfg.get(key, default)
                output.append(f"# HELP {prom_name} Configured {key}")
                output.append(f"# TYPE {prom_name} gauge")
                output.append(f'{prom_name} {fmt.format(v=v)}')
                output.append("")

            trailing = cfg.get("trailing_stop", {})
            trail_enabled = 1 if trailing.get("enabled", False) else 0
            output.append("# HELP btc_trading_trailing_stop_enabled Trailing stop enabled")
            output.append("# TYPE btc_trading_trailing_stop_enabled gauge")
            output.append(f'btc_trading_trailing_stop_enabled {trail_enabled}')
            output.append("")
            output.append("# HELP btc_trading_trailing_stop_activation_pct Trailing stop activation")
            output.append("# TYPE btc_trading_trailing_stop_activation_pct gauge")
            output.append(f'btc_trading_trailing_stop_activation_pct {trailing.get("activation_pct", 0.015):.4f}')
            output.append("")
            output.append("# HELP btc_trading_trailing_stop_trail_pct Trailing stop trail")
            output.append("# TYPE btc_trading_trailing_stop_trail_pct gauge")
            output.append(f'btc_trading_trailing_stop_trail_pct {trailing.get("trail_pct", 0.008):.4f}')
            output.append("")

            # ═══════════════ AGENT STATUS ═══════════════
            output.append("# HELP btc_trading_agent_running Agent running (1=yes, 0=no)")
            output.append("# TYPE btc_trading_agent_running gauge")
            output.append(f'btc_trading_agent_running {metrics.get("agent_running", 0)}')
            output.append("")

            output.append("# HELP btc_trading_last_activity_timestamp Last activity timestamp")
            output.append("# TYPE btc_trading_last_activity_timestamp gauge")
            output.append(f'btc_trading_last_activity_timestamp {metrics.get("last_activity", 0):.0f}')
            output.append("")

            # ═══════════════ LAST TRADE (modo ativo) ═══════════════
            lt_ts = metrics.get(f'{active}last_trade_timestamp')
            if lt_ts:
                output.append("# HELP btc_trading_last_trade_info Last trade info (active mode)")
                output.append("# TYPE btc_trading_last_trade_info gauge")
                side = 'buy' if metrics.get(f'{active}last_trade_side', 0) == 1 else 'sell'
                output.append(
                    f'btc_trading_last_trade_info{{side="{side}",mode="{active_label}",'
                    f'price="{metrics.get(f"{active}last_trade_price", 0):.2f}",'
                    f'size="{metrics.get(f"{active}last_trade_size", 0):.6f}",'
                    f'pnl="{metrics.get(f"{active}last_trade_pnl", 0):.2f}"}} '
                    f'{lt_ts:.0f}'
                )
                output.append("")

            # ═══════════════ ACTIVE MODE LABEL ═══════════════
            output.append("# HELP btc_trading_active_mode Current active mode (label)")
            output.append("# TYPE btc_trading_active_mode gauge")
            output.append(f'btc_trading_active_mode{{mode="{active_label}"}} 1')
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
        """Log every request with client IP, path, and status"""
        # Always log all requests for debugging
        sys.stderr.write("[EXPORTER] %s - - [%s] %s\n" % (
            self.client_address[0],
            self.log_date_time_string(),
            format%args))
        sys.stderr.flush()


def main():
    """Main function"""
    port = 9092

    print("=" * 60)
    print("📊 AutoCoinBot Prometheus Exporter v2")
    print("=" * 60)
    print(f"\n🔗 Metrics: http://0.0.0.0:{port}/metrics")
    print(f"💚 Health:  http://0.0.0.0:{port}/health")
    print(f"⚙️  Config:  http://0.0.0.0:{port}/config")
    print(f"🔄 Toggle:  POST http://0.0.0.0:{port}/toggle-mode")
    print(f"📍 Mode:    http://0.0.0.0:{port}/mode")
    print(f"📁 Database: {DB_PATH}")
    print(f"📁 Config:   {CONFIG_PATH}")
    print("\n✅ Server started. Press Ctrl+C to stop.\n")

    # Use a threaded server so a long /metrics scrape doesn't block control endpoints
    server = ThreadingHTTPServer(('0.0.0.0', port), PrometheusHandler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
