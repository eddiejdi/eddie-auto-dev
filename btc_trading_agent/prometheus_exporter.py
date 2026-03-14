#!/usr/bin/env python3
"""
Prometheus Exporter para AutoCoinBot v3 (PostgreSQL)
Expõe métricas do agente de trading para o Prometheus/Grafana
Inclui métricas de Risk Management v2 (stop-loss, trailing-stop, daily-limits)

Migrado de SQLite → PostgreSQL em 2026-03-03.
Fonte primária: PostgreSQL (schema btc, porta 5433)
"""

import os
import sys
import json
import time
import subprocess
import urllib.request
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

try:
    import psycopg2
except ImportError:
    print("❌ psycopg2 não encontrado. Instale: pip install psycopg2-binary")
    sys.exit(1)

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

# Paths
BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / os.environ.get("COIN_CONFIG_FILE", "config.json")

# PostgreSQL DSN via Secrets Agent (NUNCA hardcoded)
try:
    from secrets_helper import get_database_url
    DATABASE_URL = get_database_url()
except Exception:
    DATABASE_URL = os.environ.get("DATABASE_URL", "")
    if not DATABASE_URL:
        print("❌ DATABASE_URL não configurado. Use Secrets Agent ou env var.")
        sys.exit(1)


def load_config() -> Dict:
    """Carrega config.json"""
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


class MetricsCollector:
    """Coleta métricas do PostgreSQL (schema btc)"""

    def __init__(self, dsn: str, symbol: str = "BTC-USDT", profile: str = "default"):
        self.dsn = dsn
        self.symbol = symbol
        self.profile = profile

    def _get_conn(self):
        """Cria conexão PostgreSQL com autocommit e search_path btc"""
        conn = psycopg2.connect(self.dsn)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SET search_path TO btc, public")
        cur.close()
        return conn

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
        """Busca preço ao vivo via KuCoin API"""
        try:
            symbol = self.symbol
            req = urllib.request.Request(
                f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={symbol}",
                headers={"User-Agent": "AutoCoinBot-Exporter/2.1"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                return float(data["data"]["price"])
        except Exception:
            return 0


    def _fetch_exchange_balances(self) -> Dict[str, float]:
        """Busca saldos reais da exchange KuCoin via kucoin_api module.

        Returns:
            Dict com 'usdt', 'btc' e 'success'. Se falhar, success=False.
        """
        try:
            from kucoin_api import get_balance
            usdt = get_balance("USDT")
            btc = get_balance("BTC")
            return {"usdt": usdt, "btc": btc, "success": True}
        except Exception as e:
            print(f"⚠️ Falha ao buscar saldos da exchange: {e}")
            return {"usdt": 0.0, "btc": 0.0, "success": False}

    def _save_exchange_snapshot(self, usdt: float, btc: float,
                                btc_price: float, equity: float) -> None:
        """Grava snapshot de saldo da exchange na tabela btc.exchange_snapshots.

        Limita a 1 snapshot por minuto para não sobrecarregar o banco.
        """
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            # Só insere se o último snapshot tem mais de 60 segundos
            cur.execute("""
                INSERT INTO btc.exchange_snapshots
                    (timestamp, usdt_balance, btc_balance, btc_price, equity_usdt)
                SELECT EXTRACT(EPOCH FROM NOW()), %s, %s, %s, %s
                WHERE NOT EXISTS (
                    SELECT 1 FROM btc.exchange_snapshots
                    WHERE timestamp > EXTRACT(EPOCH FROM NOW()) - 60
                )
            """, (usdt, btc, btc_price, equity))
            # Cleanup: manter só últimas 24h de snapshots
            cur.execute("""
                DELETE FROM btc.exchange_snapshots
                WHERE timestamp < EXTRACT(EPOCH FROM NOW()) - 86400
            """)
            cur.close()
            conn.close()
        except Exception as e:
            print(f"⚠️ Falha ao salvar snapshot: {e}")


    def get_metrics(self) -> Dict:
        """Coleta todas as métricas do PostgreSQL, separadas por modo (dry/live)"""
        conn = self._get_conn()
        cursor = conn.cursor()

        metrics = {}
        now = datetime.now().timestamp()

        # ── Preço atual (DB com fallback para API live) ──
        cursor.execute("""
            SELECT price, timestamp FROM market_states
            WHERE symbol = %s
            ORDER BY timestamp DESC LIMIT 1
        """, (self.symbol,))
        result = cursor.fetchone()
        db_price = result[0] if result else 0
        db_price_age = (now - result[1]) if result and result[1] else float('inf')

        # Se preço do DB tem mais de 5 minutos, buscar ao vivo
        if db_price_age > 300:
            live_price = self._fetch_live_price()
            metrics['btc_price'] = live_price if live_price > 0 else db_price
        else:
            metrics['btc_price'] = db_price

        # ── Coleta stats por modo (dry_run=true/false — PostgreSQL boolean) ──
        for mode_val, mode_name in [(True, 'dry'), (False, 'live')]:
            prefix = f'{mode_name}_'

            # Total de trades
            cursor.execute("SELECT COUNT(*) FROM trades WHERE dry_run=%s AND symbol=%s AND profile=%s", (mode_val, self.symbol, self.profile))
            metrics[f'{prefix}total_trades'] = cursor.fetchone()[0]

            # Trades com PnL (COM filtro symbol)
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning,
                    SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as losing,
                    SUM(pnl) as total_pnl,
                    AVG(pnl) as avg_pnl,
                    MAX(pnl) as best_trade,
                    MIN(pnl) as worst_trade
                FROM trades WHERE pnl IS NOT NULL AND dry_run=%s AND symbol=%s AND profile=%s
            """, (mode_val, self.symbol, self.profile))
            result = cursor.fetchone()

            # Total de SELLs (inclui NULL pnl) para win_rate preciso
            cursor.execute(
                "SELECT COUNT(*) FROM trades WHERE side='sell' AND dry_run=%s AND symbol=%s AND profile=%s",
                (mode_val, self.symbol, self.profile)
            )
            total_sells = cursor.fetchone()[0]

            if result and result[0]:
                metrics[f'{prefix}winning_trades'] = result[1] or 0
                metrics[f'{prefix}losing_trades'] = result[2] or 0
                # Win rate usa total_sells como denominador (inclui sells com pnl NULL)
                metrics[f'{prefix}win_rate'] = (result[1] or 0) / total_sells if total_sells > 0 else 0
                metrics[f'{prefix}total_pnl'] = result[3] if result[3] else 0
                metrics[f'{prefix}avg_pnl'] = result[4] if result[4] else 0
                metrics[f'{prefix}best_trade_pnl'] = result[5] if result[5] else 0
                metrics[f'{prefix}worst_trade_pnl'] = result[6] if result[6] else 0
            else:
                for k in ['winning_trades', 'losing_trades', 'win_rate', 'total_pnl',
                           'avg_pnl', 'best_trade_pnl', 'worst_trade_pnl']:
                    metrics[f'{prefix}{k}'] = 0

            # PnL acumulado total (COM filtro symbol)
            cursor.execute("SELECT COALESCE(SUM(pnl), 0) FROM trades WHERE pnl IS NOT NULL AND dry_run=%s AND symbol=%s AND profile=%s", (mode_val, self.symbol, self.profile))
            metrics[f'{prefix}cumulative_pnl'] = cursor.fetchone()[0]

            # PnL últimas 24h (COM filtro symbol)
            cursor.execute("""
                SELECT COALESCE(SUM(pnl), 0) FROM trades
                WHERE pnl IS NOT NULL AND timestamp > %s AND dry_run=%s AND symbol=%s AND profile=%s
            """, (now - 86400, mode_val, self.symbol, self.profile))
            metrics[f'{prefix}cumulative_pnl_24h'] = cursor.fetchone()[0]

            # Trades 24h / 1h
            cursor.execute("SELECT COUNT(*) FROM trades WHERE timestamp > %s AND dry_run=%s AND symbol=%s AND profile=%s", (now - 86400, mode_val, self.symbol, self.profile))
            metrics[f'{prefix}trades_24h'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM trades WHERE timestamp > %s AND dry_run=%s AND symbol=%s AND profile=%s", (now - 3600, mode_val, self.symbol, self.profile))
            metrics[f'{prefix}trades_1h'] = cursor.fetchone()[0]

            # Trades por lado (COM filtro symbol)
            cursor.execute("SELECT side, COUNT(*) FROM trades WHERE dry_run=%s AND symbol=%s AND profile=%s GROUP BY side", (mode_val, self.symbol, self.profile))
            for row in cursor.fetchall():
                metrics[f'{prefix}trades_{row[0].lower()}'] = row[1]

            # Posição aberta — multi-posição: soma todos os BUYs desde o último SELL
            cursor.execute("""
                SELECT side, size, price, timestamp FROM trades
                WHERE dry_run=%s AND symbol=%s AND profile=%s
                ORDER BY timestamp DESC LIMIT 50
            """, (mode_val, self.symbol, self.profile))
            recent_trades = cursor.fetchall()
            open_buys = []
            for t in recent_trades:
                if t[0] == 'sell':
                    break
                if t[0] == 'buy':
                    open_buys.append(t)
            if open_buys:
                total_btc = sum(b[1] or 0 for b in open_buys)
                total_cost = sum((b[1] or 0) * (b[2] or 0) for b in open_buys)
                avg_entry = total_cost / total_btc if total_btc > 0 else 0
                metrics[f'{prefix}open_position_btc'] = total_btc
                metrics[f'{prefix}open_position_usdt'] = total_btc * avg_entry
                metrics[f'{prefix}open_position_count'] = len(open_buys)
                metrics[f'{prefix}avg_entry_price'] = avg_entry
            else:
                metrics[f'{prefix}open_position_btc'] = 0
                metrics[f'{prefix}open_position_usdt'] = 0
                metrics[f'{prefix}open_position_count'] = 0
                metrics[f'{prefix}avg_entry_price'] = 0

            # Exit reasons — extraído de metadata JSONB (coluna exit_reason não existe no PG)
            try:
                cursor.execute("""
                    SELECT metadata->>'exit_reason' as reason, COUNT(*) FROM trades
                    WHERE metadata->>'exit_reason' IS NOT NULL
                      AND dry_run=%s AND symbol=%s AND profile=%s
                    GROUP BY metadata->>'exit_reason'
                """, (mode_val, self.symbol, self.profile))
                for row in cursor.fetchall():
                    reason = row[0].lower().replace(' ', '_')
                    metrics[f'{prefix}exit_{reason}'] = row[1]
            except Exception:
                pass

            # Último trade do modo (COM filtro symbol)
            cursor.execute("""
                SELECT timestamp, side, price, size, pnl
                FROM trades WHERE dry_run=%s AND symbol=%s AND profile=%s ORDER BY timestamp DESC LIMIT 1
            """, (mode_val, self.symbol, self.profile))
            result = cursor.fetchone()
            if result:
                metrics[f'{prefix}last_trade_timestamp'] = result[0]
                metrics[f'{prefix}last_trade_side'] = 1 if result[1] == 'buy' else 0
                metrics[f'{prefix}last_trade_price'] = result[2]
                metrics[f'{prefix}last_trade_size'] = result[3]
                metrics[f'{prefix}last_trade_pnl'] = result[4] if result[4] else 0

        # ── Decisões por tipo (global — COM filtro symbol) ──
        cursor.execute("SELECT action, COUNT(*) FROM decisions WHERE symbol=%s AND profile=%s GROUP BY action", (self.symbol, self.profile))
        for row in cursor.fetchall():
            metrics[f'decisions_{row[0].lower()}'] = row[1]

        # Decisões última hora (COM filtro symbol)
        cursor.execute("""
            SELECT action, COUNT(*) FROM decisions
            WHERE timestamp > %s AND symbol=%s AND profile=%s GROUP BY action
        """, (now - 3600, self.symbol, self.profile))
        for row in cursor.fetchall():
            metrics[f'decisions_1h_{row[0].lower()}'] = row[1]

        # Último score final gerado pelo modelo (features é JSONB no PostgreSQL)
        try:
            cursor.execute("SELECT features FROM decisions WHERE symbol=%s AND profile=%s ORDER BY timestamp DESC LIMIT 1", (self.symbol, self.profile))
            row = cursor.fetchone()
            if row and row[0]:
                f = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                metrics['final_score'] = float(f.get('final_score', 0))
            else:
                metrics['final_score'] = 0.0
        except Exception:
            metrics['final_score'] = 0.0

        # ── Indicadores técnicos (últimos valores — COM filtro symbol) ──
        cursor.execute("""
            SELECT rsi, momentum, volatility, trend, orderbook_imbalance, trade_flow,
                   bid, ask, spread, volume
            FROM market_states WHERE symbol=%s ORDER BY timestamp DESC LIMIT 1
        """, (self.symbol,))
        result = cursor.fetchone()
        if result:
            metrics['rsi'] = result[0] if result[0] else 50
            metrics['momentum'] = result[1] if result[1] else 0
            metrics['volatility'] = result[2] if result[2] else 0
            metrics['trend'] = result[3] if result[3] else 0
            metrics['orderbook_imbalance'] = result[4] if result[4] else 0
            metrics['trade_flow'] = result[5] if result[5] else 0
            metrics['bid_volume'] = result[6] if result[6] else 0
            metrics['ask_volume'] = result[7] if result[7] else 0
            metrics['spread'] = result[8] if result[8] else 0
            metrics['volume'] = result[9] if result[9] else 0

        # ── Última atividade ──
        cursor.execute("SELECT MAX(timestamp) FROM market_states WHERE symbol=%s", (self.symbol,))
        result = cursor.fetchone()
        metrics['last_activity'] = result[0] if result and result[0] else 0

        # ── Status do agente (process check + DB fallback) ──
        process_running = self._is_agent_process_running()
        db_recent = (now - metrics.get('last_activity', 0)) < 300
        metrics['agent_running'] = 1 if (process_running or db_recent) else 0

        # ── Equity / Patrimônio (saldos reais da exchange) ──
        # Usa KuCoin API para obter saldos reais da conta trading.
        # Fallback para cálculo via DB caso API indisponível.
        try:
            initial_capital = load_config().get('initial_capital', 100.0)
            btc_price = metrics.get('btc_price', 0)
            metrics['initial_capital'] = initial_capital

            # Tentar saldos reais da exchange
            exchange = self._fetch_exchange_balances()
            if exchange['success'] and btc_price > 0:
                usdt_bal = exchange['usdt']
                btc_bal = exchange['btc']
                equity = usdt_bal + btc_bal * btc_price
                unrealized = btc_bal * (btc_price - metrics.get(
                    'live_avg_entry_price',
                    metrics.get('dry_avg_entry_price', btc_price)
                )) if btc_bal > 0 else 0.0

                metrics['equity_usdt'] = equity
                metrics['equity_btc'] = equity / btc_price
                metrics['unrealized_pnl'] = unrealized
                metrics['exchange_usdt_balance'] = usdt_bal
                metrics['exchange_btc_balance'] = btc_bal

                # Salvar snapshot no PostgreSQL
                self._save_exchange_snapshot(usdt_bal, btc_bal, btc_price, equity)
            else:
                # Fallback: equity = USDT_livre + posição * preço
                # USDT_livre = initial_capital + sell_funds - buy_funds (sem depósitos)
                conn2 = self._get_conn()
                cur2 = conn2.cursor()
                cur2.execute("""
                    SELECT
                        COALESCE(SUM(CASE WHEN side='sell'
                            THEN COALESCE(NULLIF(funds,0), size*price) ELSE 0 END), 0),
                        COALESCE(SUM(CASE WHEN side='buy'
                            AND COALESCE(metadata->>'source','') != 'external_deposit'
                            THEN funds ELSE 0 END), 0)
                    FROM btc.trades WHERE symbol=%s AND profile=%s
                """, (self.symbol, self.profile))
                sell_funds, buy_funds = cur2.fetchone()
                cur2.close()
                conn2.close()

                usdt_free = initial_capital + float(sell_funds) - float(buy_funds)
                is_live = load_config().get('live_mode', False)
                active_prefix = 'live_' if is_live else 'dry_'
                btc_pos = metrics.get(f'{active_prefix}open_position_btc', 0)
                equity = usdt_free + btc_pos * btc_price

                metrics['equity_usdt'] = equity
                metrics['equity_btc'] = equity / btc_price if btc_price > 0 else 0
                metrics['unrealized_pnl'] = btc_pos * btc_price
                metrics['exchange_usdt_balance'] = usdt_free
                metrics['exchange_btc_balance'] = btc_pos
        except Exception as e:
            print(f"⚠️ Erro ao calcular equity: {e}")
            metrics['initial_capital'] = 100.0
            metrics['equity_usdt'] = 100.0
            metrics['equity_btc'] = 0
            metrics['unrealized_pnl'] = 0

        cursor.close()
        conn.close()
        return metrics


class PrometheusHandler(BaseHTTPRequestHandler):
    """Handler HTTP para expor métricas no formato Prometheus"""

    _collector = None

    @classmethod
    def get_collector(cls):
        if cls._collector is None:
            symbol = os.environ.get("COIN_SYMBOL", "BTC-USDT")
            cfg = load_config()
            profile = cfg.get("profile", "default")
            cls._collector = MetricsCollector(DATABASE_URL, symbol, profile)
        return cls._collector

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
            metrics = self.get_collector().get_metrics()
            cfg = load_config()

            # Determinar modo ativo: live_mode=true → prefixo 'live_', senão 'dry_'
            is_live = cfg.get('live_mode', False)
            active = 'live_' if is_live else 'dry_'
            active_label = 'live' if is_live else 'dry'

            output = []

            # ═══════════════ PREÇO ═══════════════
            _sym = os.environ.get("COIN_SYMBOL", "BTC-USDT")
            _coin = _sym.split("-")[0]
            # Label coin= para compatibilidade com dashboard Grafana ($coin variable)
            _profile = cfg.get('profile', 'default')
            _cl = f'coin="{_sym}",profile="{_profile}"'  # coin+profile labels
            output.append(f"# HELP crypto_price {_coin} price in USDT")
            output.append("# TYPE crypto_price gauge")
            output.append(f'crypto_price{{symbol="{_sym}",{_cl}}} {metrics.get("btc_price", 0)}')
            # Keep btc_price alias for backward compat
            output.append(f'btc_price{{symbol="{_sym}",{_cl}}} {metrics.get("btc_price", 0)}')
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
                ('btc_trading_open_position_count', 'open_position_count', 'Number of open BUY entries (multi-position)', 'gauge', '{v}'),
                ('btc_trading_avg_entry_price', 'avg_entry_price', 'Weighted avg entry price of open position', 'gauge', '{v:.2f}'),
            ]

            for prom_name, key, help_text, ptype, fmt in stat_metrics:
                v = metrics.get(f'{active}{key}', 0)
                output.append(f"# HELP {prom_name} {help_text}")
                output.append(f"# TYPE {prom_name} {ptype}")
                output.append(f'{prom_name}{{{_cl}}} {fmt.format(v=v)}')
                output.append("")

            # ═══════════════ STATS POR MODO (com label) ═══════════════
            output.append("# HELP btc_trading_mode_total_trades Total trades by mode")
            output.append("# TYPE btc_trading_mode_total_trades counter")
            for mode in ['dry', 'live']:
                v = metrics.get(f'{mode}_total_trades', 0)
                output.append(f'btc_trading_mode_total_trades{{mode="{mode}",{_cl}}} {v}')
            output.append("")

            output.append("# HELP btc_trading_mode_pnl Total PnL by mode")
            output.append("# TYPE btc_trading_mode_pnl gauge")
            for mode in ['dry', 'live']:
                v = metrics.get(f'{mode}_total_pnl', 0)
                output.append(f'btc_trading_mode_pnl{{mode="{mode}",{_cl}}} {v:.4f}')
            output.append("")

            output.append("# HELP btc_trading_mode_win_rate Win rate by mode")
            output.append("# TYPE btc_trading_mode_win_rate gauge")
            for mode in ['dry', 'live']:
                v = metrics.get(f'{mode}_win_rate', 0)
                output.append(f'btc_trading_mode_win_rate{{mode="{mode}",{_cl}}} {v:.4f}')
            output.append("")

            output.append("# HELP btc_trading_mode_winning Winning trades by mode")
            output.append("# TYPE btc_trading_mode_winning counter")
            for mode in ['dry', 'live']:
                v = metrics.get(f'{mode}_winning_trades', 0)
                output.append(f'btc_trading_mode_winning{{mode="{mode}",{_cl}}} {v}')
            output.append("")

            output.append("# HELP btc_trading_mode_losing Losing trades by mode")
            output.append("# TYPE btc_trading_mode_losing counter")
            for mode in ['dry', 'live']:
                v = metrics.get(f'{mode}_losing_trades', 0)
                output.append(f'btc_trading_mode_losing{{mode="{mode}",{_cl}}} {v}')
            output.append("")

            # ═══════════════ TRADES BY SIDE (modo ativo) ═══════════════
            output.append("# HELP btc_trading_trades_total Trades by side (active mode)")
            output.append("# TYPE btc_trading_trades_total counter")
            for side in ['buy', 'sell']:
                count = metrics.get(f'{active}trades_{side}', 0)
                output.append(f'btc_trading_trades_total{{side="{side}",{_cl}}} {count}')
            output.append("")

            # ═══════════════ DECISIONS (global) ═══════════════
            output.append("# HELP btc_trading_decisions_total Total decisions by action")
            output.append("# TYPE btc_trading_decisions_total counter")
            for action in ['buy', 'sell', 'hold']:
                count = metrics.get(f'decisions_{action}', 0)
                output.append(f'btc_trading_decisions_total{{action="{action.upper()}",{_cl}}} {count}')
            output.append("")

            output.append("# HELP btc_trading_decisions_1h Decisions in last hour by action")
            output.append("# TYPE btc_trading_decisions_1h gauge")
            for action in ['buy', 'sell', 'hold']:
                count = metrics.get(f'decisions_1h_{action}', 0)
                output.append(f'btc_trading_decisions_1h{{action="{action.upper()}",{_cl}}} {count}')
            output.append("")

            # ═══════════════ TECHNICAL INDICATORS ═══════════════
            indicators = [
                ('btc_trading_rsi', 'rsi', 'RSI (0-100)', 50, '{v:.2f}'),
                ('btc_trading_momentum', 'momentum', 'Price momentum', 0, '{v:.6f}'),
                ('btc_trading_volatility', 'volatility', 'Volatility (0-1)', 0, '{v:.6f}'),
                ('btc_trading_trend', 'trend', 'Trend (-1 to +1)', 0, '{v:.6f}'),
                ('btc_trading_orderbook_imbalance', 'orderbook_imbalance', 'Orderbook imbalance', 0, '{v:.6f}'),
                ('btc_trading_trade_flow', 'trade_flow', 'Trade flow bias (-1 to +1)', 0, '{v:.6f}'),
                ('btc_trading_bid_volume', 'bid_volume', 'Orderbook bid volume', 0, '{v:.6f}'),
                ('btc_trading_ask_volume', 'ask_volume', 'Orderbook ask volume', 0, '{v:.6f}'),
                ('btc_trading_spread', 'spread', 'Bid-ask spread', 0, '{v:.6f}'),
            ]
            for prom_name, key, help_text, default, fmt in indicators:
                v = metrics.get(key, default)
                output.append(f"# HELP {prom_name} {help_text}")
                output.append(f"# TYPE {prom_name} gauge")
                output.append(f'{prom_name}{{{_cl}}} {fmt.format(v=v)}')
                output.append("")

            # ═══════════════ MODEL FINAL SCORE (última decisão) ═══════════════
            output.append("# HELP btc_trading_final_score Latest model final_score (-1..1)")
            output.append("# TYPE btc_trading_final_score gauge")
            output.append(f'btc_trading_final_score{{symbol="{_sym}",{_cl}}} {metrics.get("final_score", 0):.6f}')
            output.append("")

            # ═══════════════ EXIT REASONS (modo ativo) ═══════════════
            for reason in ['stop_loss', 'take_profit', 'trailing_stop', 'signal']:
                prom_name = f'btc_trading_exit_{reason}'
                v = metrics.get(f'{active}exit_{reason}', 0)
                output.append(f"# HELP {prom_name} Trades closed by {reason} (active mode)")
                output.append(f"# TYPE {prom_name} counter")
                output.append(f'{prom_name}{{{_cl}}} {v}')
                output.append("")

            # ═══════════════ CONFIG ═══════════════
            live_val = 1 if cfg.get('live_mode', False) else 0
            output.append("# HELP btc_trading_live_mode Live trading mode (0=dry_run, 1=live)")
            output.append("# TYPE btc_trading_live_mode gauge")
            output.append(f'btc_trading_live_mode{{{_cl}}} {live_val}')
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
                output.append(f'{prom_name}{{{_cl}}} {fmt.format(v=v)}')
                output.append("")

            trailing = cfg.get("trailing_stop", {})
            trail_enabled = 1 if trailing.get("enabled", False) else 0
            output.append("# HELP btc_trading_trailing_stop_enabled Trailing stop enabled")
            output.append("# TYPE btc_trading_trailing_stop_enabled gauge")
            output.append(f'btc_trading_trailing_stop_enabled{{{_cl}}} {trail_enabled}')
            output.append("")
            output.append("# HELP btc_trading_trailing_stop_activation_pct Trailing stop activation")
            output.append("# TYPE btc_trading_trailing_stop_activation_pct gauge")
            output.append(f'btc_trading_trailing_stop_activation_pct{{{_cl}}} {trailing.get("activation_pct", 0.015):.4f}')
            output.append("")
            output.append("# HELP btc_trading_trailing_stop_trail_pct Trailing stop trail")
            output.append("# TYPE btc_trading_trailing_stop_trail_pct gauge")
            output.append(f'btc_trading_trailing_stop_trail_pct{{{_cl}}} {trailing.get("trail_pct", 0.008):.4f}')
            output.append("")

            # ═══════════════ MODEL THRESHOLDS (se disponível) ═══════════════
            try:
                from fast_model import FastTradingModel
                try:
                    model = FastTradingModel(_sym)
                    output.append("# HELP btc_trading_model_buy_threshold Model buy decision threshold")
                    output.append("# TYPE btc_trading_model_buy_threshold gauge")
                    output.append(f'btc_trading_model_buy_threshold{{{_cl}}} {model.buy_threshold}')
                    output.append("")

                    output.append("# HELP btc_trading_model_sell_threshold Model sell decision threshold")
                    output.append("# TYPE btc_trading_model_sell_threshold gauge")
                    output.append(f'btc_trading_model_sell_threshold{{{_cl}}} {model.sell_threshold}')
                    output.append("")

                    output.append("# HELP btc_trading_model_min_confidence Model minimum confidence threshold")
                    output.append("# TYPE btc_trading_model_min_confidence gauge")
                    output.append(f'btc_trading_model_min_confidence{{{_cl}}} {model.min_confidence}')
                    output.append("")
                except Exception:
                    # If model construction fails, export defaults of 0 to keep metrics stable
                    output.append("# HELP btc_trading_model_buy_threshold Model buy decision threshold (unavailable)")
                    output.append("# TYPE btc_trading_model_buy_threshold gauge")
                    output.append(f'btc_trading_model_buy_threshold{{{_cl}}} 0')
                    output.append("")
                    output.append("# HELP btc_trading_model_sell_threshold Model sell decision threshold (unavailable)")
                    output.append("# TYPE btc_trading_model_sell_threshold gauge")
                    output.append(f'btc_trading_model_sell_threshold{{{_cl}}} 0')
                    output.append("")
                    output.append("# HELP btc_trading_model_min_confidence Model minimum confidence threshold (unavailable)")
                    output.append("# TYPE btc_trading_model_min_confidence gauge")
                    output.append(f'btc_trading_model_min_confidence{{{_cl}}} 0')
                    output.append("")
            except Exception:
                # fast_model not available in this environment
                output.append("# HELP btc_trading_model_buy_threshold Model buy decision threshold (missing module)")
                output.append("# TYPE btc_trading_model_buy_threshold gauge")
                output.append(f'btc_trading_model_buy_threshold{{{_cl}}} 0')
                output.append("")
                output.append("# HELP btc_trading_model_sell_threshold Model sell decision threshold (missing module)")
                output.append("# TYPE btc_trading_model_sell_threshold gauge")
                output.append(f'btc_trading_model_sell_threshold{{{_cl}}} 0')
                output.append("")
                output.append("# HELP btc_trading_model_min_confidence Model minimum confidence threshold (missing module)")
                output.append("# TYPE btc_trading_model_min_confidence gauge")
                output.append(f'btc_trading_model_min_confidence{{{_cl}}} 0')
                output.append("")

            # ═══════════════ MARKET RAG (AI Output) ═══════════════
            try:
                rag_dir = BASE_DIR / "data" / "market_rag"
                profile_file = rag_dir / f"regime_adjustments_{self.profile}.json"
                rag_file = profile_file if profile_file.exists() else rag_dir / "regime_adjustments.json"
                if rag_file.exists():
                    with open(rag_file) as _rf:
                        rag_data = json.load(_rf)
                    cur = rag_data.get("current", {})

                    # Regime numérico: BULL=1, RANGING=0, BEAR=-1
                    regime_str = cur.get("suggested_regime", "RANGING")
                    regime_map = {"BULL": 1, "BULLISH": 1, "RANGING": 0, "BEAR": -1, "BEARISH": -1}
                    regime_num = regime_map.get(regime_str.upper(), 0)

                    rag_metrics = [
                        ("btc_rag_regime", "RAG regime (1=bull, 0=ranging, -1=bear)", regime_num, "{v}"),
                        ("btc_rag_regime_confidence", "RAG regime confidence (0-1)", cur.get("regime_confidence", 0), "{v:.4f}"),
                        ("btc_rag_bull_pct", "RAG bull pattern percentage", cur.get("bull_pct", 0), "{v:.4f}"),
                        ("btc_rag_bear_pct", "RAG bear pattern percentage", cur.get("bear_pct", 0), "{v:.4f}"),
                        ("btc_rag_flat_pct", "RAG flat/ranging pattern percentage", cur.get("flat_pct", 0), "{v:.4f}"),
                        ("btc_rag_buy_threshold", "RAG-adjusted buy threshold", cur.get("buy_threshold", 0.30), "{v:.4f}"),
                        ("btc_rag_sell_threshold", "RAG-adjusted sell threshold", cur.get("sell_threshold", -0.30), "{v:.4f}"),
                        ("btc_rag_similar_count", "Number of similar patterns found", cur.get("similar_count", 0), "{v}"),
                        ("btc_rag_avg_return_5m", "Avg 5min return of similar patterns", cur.get("avg_return_5m", 0), "{v:.6f}"),
                        ("btc_rag_avg_return_15m", "Avg 15min return of similar patterns", cur.get("avg_return_15m", 0), "{v:.6f}"),
                        ("btc_rag_weight_technical", "RAG-adjusted technical weight", cur.get("weight_technical", 0.35), "{v:.4f}"),
                        ("btc_rag_weight_orderbook", "RAG-adjusted orderbook weight", cur.get("weight_orderbook", 0.30), "{v:.4f}"),
                        ("btc_rag_weight_flow", "RAG-adjusted flow weight", cur.get("weight_flow", 0.25), "{v:.4f}"),
                        ("btc_rag_weight_qlearning", "RAG-adjusted Q-learning weight", cur.get("weight_qlearning", 0.10), "{v:.4f}"),
                        # AI Trade Gating metrics
                        ("btc_rag_ai_min_confidence", "AI-controlled min confidence", cur.get("ai_min_confidence", 0.60), "{v:.4f}"),
                        ("btc_rag_ai_min_trade_interval", "AI-controlled min trade interval (s)", cur.get("ai_min_trade_interval", 180), "{v}"),
                        ("btc_rag_ai_rebuy_lock", "AI rebuy lock enabled (1=on, 0=off)", 1 if cur.get("ai_rebuy_lock_enabled", True) else 0, "{v}"),
                        ("btc_rag_ai_aggressiveness", "AI aggressiveness (0-1)", cur.get("ai_aggressiveness", 0.5), "{v:.4f}"),
                        ("btc_rag_ai_buy_target", "AI buy target price", cur.get("ai_buy_target_price", 0), "{v:.2f}"),
                        ("btc_rag_ai_position_size_pct", "AI position size pct per entry", cur.get("ai_position_size_pct", 0.04), "{v:.4f}"),
                        ("btc_rag_ai_max_entries", "AI max entries", cur.get("ai_max_entries", 20), "{v}"),
                        ("btc_rag_baseline_max_position_pct", "Baseline hard cap max position pct", cur.get("baseline_max_position_pct", 0.50), "{v:.4f}"),
                        ("btc_rag_baseline_max_positions", "Baseline hard cap max positions", cur.get("baseline_max_positions", 3), "{v}"),
                        ("btc_rag_applied_min_confidence", "Applied min confidence after Ollama clamps", cur.get("applied_min_confidence", cur.get("ai_min_confidence", 0.60)), "{v:.4f}"),
                        ("btc_rag_applied_min_trade_interval", "Applied min trade interval after Ollama clamps", cur.get("applied_min_trade_interval", cur.get("ai_min_trade_interval", 180)), "{v}"),
                        ("btc_rag_applied_max_position_pct", "Applied hard cap max position pct", cur.get("applied_max_position_pct", cur.get("baseline_max_position_pct", 0.50)), "{v:.4f}"),
                        ("btc_rag_applied_max_positions", "Applied hard cap max positions", cur.get("applied_max_positions", cur.get("baseline_max_positions", 3)), "{v}"),
                        ("btc_rag_ollama_last_update", "Last Ollama trade-controls update timestamp", cur.get("ollama_last_update", 0), "{v:.3f}"),
                        ("btc_rag_ollama_suggested_min_confidence", "Suggested min confidence from Ollama", cur.get("ollama_suggested_min_confidence", 0), "{v:.4f}"),
                        ("btc_rag_ollama_suggested_min_trade_interval", "Suggested min trade interval from Ollama", cur.get("ollama_suggested_min_trade_interval", 0), "{v}"),
                        ("btc_rag_ollama_suggested_max_position_pct", "Suggested max position pct from Ollama", cur.get("ollama_suggested_max_position_pct", 0), "{v:.4f}"),
                        ("btc_rag_ollama_suggested_max_positions", "Suggested max positions from Ollama", cur.get("ollama_suggested_max_positions", 0), "{v}"),
                    ]
                    for prom_name, help_text, v, fmt in rag_metrics:
                        output.append(f"# HELP {prom_name} {help_text}")
                        output.append(f"# TYPE {prom_name} gauge")
                        output.append(f'{prom_name}{{{_cl}}} {fmt.format(v=v)}')
                        output.append("")

                    # Regime label (para value mapping no Grafana)
                    output.append("# HELP btc_rag_regime_info RAG regime info label")
                    output.append("# TYPE btc_rag_regime_info gauge")
                    output.append(f'btc_rag_regime_info{{regime="{regime_str}",{_cl}}} 1')
                    output.append("")
                    ollama_mode = str(cur.get("ollama_mode", "shadow") or "shadow")
                    output.append("# HELP btc_rag_ollama_mode_info Ollama trade-controls mode label")
                    output.append("# TYPE btc_rag_ollama_mode_info gauge")
                    output.append(f'btc_rag_ollama_mode_info{{mode="{ollama_mode}",{_cl}}} 1')
                    output.append("")
                else:
                    # RAG file not yet created — export neutral defaults
                    for name in ["btc_rag_regime", "btc_rag_regime_confidence", "btc_rag_bull_pct",
                                 "btc_rag_bear_pct", "btc_rag_flat_pct"]:
                        output.append(f"# TYPE {name} gauge")
                        output.append(f'{name}{{{_cl}}} 0')
                        output.append("")
            except Exception:
                pass  # RAG metrics non-critical

            # ═══════════════ AGENT STATUS ═══════════════
            output.append("# HELP btc_trading_agent_running Agent running (1=yes, 0=no)")
            output.append("# TYPE btc_trading_agent_running gauge")
            output.append(f'btc_trading_agent_running{{{_cl}}} {metrics.get("agent_running", 0)}')
            output.append("")

            output.append("# HELP btc_trading_last_activity_timestamp Last activity timestamp")
            output.append("# TYPE btc_trading_last_activity_timestamp gauge")
            output.append(f'btc_trading_last_activity_timestamp{{{_cl}}} {metrics.get("last_activity", 0):.0f}')
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
                    f'pnl="{metrics.get(f"{active}last_trade_pnl", 0):.2f}",{_cl}}} '
                    f'{lt_ts:.0f}'
                )
                output.append("")

            # ═══════════════ ACTIVE MODE LABEL ═══════════════
            output.append("# HELP btc_trading_active_mode Current active mode (label)")
            output.append("# TYPE btc_trading_active_mode gauge")
            output.append(f'btc_trading_active_mode{{mode="{active_label}",{_cl}}} 1')
            output.append("")

            # ═══════════════ EQUITY / PATRIMÔNIO ═══════════════
            output.append("# HELP btc_trading_equity_usdt Total portfolio equity in USDT")
            output.append("# TYPE btc_trading_equity_usdt gauge")
            output.append(f'btc_trading_equity_usdt{{{_cl}}} {metrics.get("equity_usdt", 0):.4f}')
            output.append("")

            output.append("# HELP btc_trading_equity_btc Total portfolio equity in BTC")
            output.append("# TYPE btc_trading_equity_btc gauge")
            output.append(f'btc_trading_equity_btc{{{_cl}}} {metrics.get("equity_btc", 0):.8f}')
            output.append("")

            output.append("# HELP btc_trading_initial_capital Initial capital in USDT")
            output.append("# TYPE btc_trading_initial_capital gauge")
            output.append(f'btc_trading_initial_capital{{{_cl}}} {metrics.get("initial_capital", 100):.2f}')
            output.append("")

            output.append("# HELP btc_trading_unrealized_pnl Unrealized PnL from open positions")
            output.append("# TYPE btc_trading_unrealized_pnl gauge")
            output.append(f'btc_trading_unrealized_pnl{{{_cl}}} {metrics.get("unrealized_pnl", 0):.4f}')
            output.append("")

            output.append("# HELP btc_trading_exchange_usdt_balance USDT balance on exchange")
            output.append("# TYPE btc_trading_exchange_usdt_balance gauge")
            output.append(f'btc_trading_exchange_usdt_balance{{{_cl}}} {metrics.get("exchange_usdt_balance", 0):.4f}')
            output.append("")

            output.append("# HELP btc_trading_exchange_btc_balance BTC balance on exchange")
            output.append("# TYPE btc_trading_exchange_btc_balance gauge")
            output.append(f'btc_trading_exchange_btc_balance{{{_cl}}} {metrics.get("exchange_btc_balance", 0):.8f}')
            output.append("")

            # ═══════════════ EXPORTER META ═══════════════
            output.append("# HELP btc_exporter_scrape_timestamp Exporter scrape timestamp")
            output.append("# TYPE btc_exporter_scrape_timestamp gauge")
            output.append(f'btc_exporter_scrape_timestamp{{{_cl}}} {time.time():.0f}')
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
        db_ok = False
        try:
            conn = psycopg2.connect(DATABASE_URL)
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute("SELECT 1")
            db_ok = True
            cur.close()
            conn.close()
        except Exception:
            pass
        health = {
            "status": "ok" if db_ok else "degraded",
            "db_type": "postgresql",
            "db_connected": db_ok,
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
    port = int(os.environ.get("METRICS_PORT", "9092"))
    
    # Load symbol from config
    config_name = os.environ.get("COIN_CONFIG_FILE", "config.json")
    config_path = BASE_DIR / config_name
    _symbol = "BTC-USDT"
    try:
        with open(config_path) as _f:
            _cfg = json.load(_f)
            _symbol = _cfg.get("symbol", "BTC-USDT")
    except Exception:
        pass
    os.environ.setdefault("COIN_SYMBOL", _symbol)

    print("=" * 60)
    print("📊 AutoCoinBot Prometheus Exporter v3 (PostgreSQL)")
    print("=" * 60)
    print(f"\n🔗 Metrics: http://0.0.0.0:{port}/metrics")
    print(f"💚 Health:  http://0.0.0.0:{port}/health")
    print(f"⚙️  Config:  http://0.0.0.0:{port}/config")
    print(f"🔄 Toggle:  POST http://0.0.0.0:{port}/toggle-mode")
    print(f"📍 Mode:    http://0.0.0.0:{port}/mode")
    print(f"🐘 Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")
    print(f"📁 Config:   {config_path}")
    print(f"🪙 Symbol:   {_symbol}")
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
