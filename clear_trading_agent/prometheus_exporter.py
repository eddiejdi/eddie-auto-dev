#!/usr/bin/env python3
"""
Prometheus Exporter para Clear Trading Agent (B3/MT5).

Expõe métricas do agente de trading para o Prometheus/Grafana.
Fonte: PostgreSQL (schema clear, porta 5433).
Porta padrão: 9100.
"""
from __future__ import annotations

import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Optional

try:
    import psycopg2
    import psycopg2.pool
except ImportError:
    print("❌ psycopg2 não encontrado. Instale: pip install psycopg2-binary")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / os.environ.get("CLEAR_CONFIG_FILE", "config.json")

import logging

logger = logging.getLogger(__name__)

try:
    from clear_trading_agent.secrets_helper import get_database_url
    DATABASE_URL = get_database_url()
except Exception as e:
    logger.warning("Falha ao importar secrets_helper: %s", e)
    DATABASE_URL = os.environ.get("DATABASE_URL", "")
    if not DATABASE_URL:
        print("❌ DATABASE_URL não configurado.")
        sys.exit(1)

METRICS_PORT = int(os.environ.get("CLEAR_METRICS_PORT", "9102"))


def load_config() -> Dict:
    """Carrega config.json."""
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


class MetricsCollector:
    """Coleta métricas do PostgreSQL (schema clear)."""

    def __init__(self, dsn: str, symbol: str = "PETR4", profile: str = "default") -> None:
        self.dsn = dsn
        self.symbol = symbol
        self.profile = profile
        self._pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None

    def _get_conn(self) -> "psycopg2.extensions.connection":
        """Obtém conexão PostgreSQL do pool com autocommit e search_path clear."""
        if self._pool is None:
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1, maxconn=3, dsn=self.dsn
            )
        conn = self._pool.getconn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SET search_path TO clear, public")
        cur.close()
        return conn

    def _put_conn(self, conn: "psycopg2.extensions.connection") -> None:
        """Devolve conexão ao pool."""
        if self._pool is not None:
            try:
                self._pool.putconn(conn)
            except Exception:
                pass

    def collect_trade_metrics(self) -> Dict:
        """Coleta métricas de trades."""
        metrics: Dict = {}
        try:
            conn = self._get_conn()
            cur = conn.cursor()

            # Total de trades
            cur.execute(
                "SELECT COUNT(*) FROM trades WHERE symbol=%s",
                (self.symbol,),
            )
            metrics["total_trades"] = cur.fetchone()[0]

            # Trades nas últimas 24h
            cur.execute(
                "SELECT COUNT(*) FROM trades WHERE symbol=%s AND created_at > NOW() - INTERVAL '24 hours'",
                (self.symbol,),
            )
            metrics["trades_24h"] = cur.fetchone()[0]

            # PnL total
            cur.execute(
                "SELECT COALESCE(SUM(pnl), 0) FROM trades WHERE symbol=%s AND pnl IS NOT NULL",
                (self.symbol,),
            )
            metrics["total_pnl"] = float(cur.fetchone()[0])

            # PnL 24h
            cur.execute(
                "SELECT COALESCE(SUM(pnl), 0) FROM trades "
                "WHERE symbol=%s AND pnl IS NOT NULL AND created_at > NOW() - INTERVAL '24 hours'",
                (self.symbol,),
            )
            metrics["pnl_24h"] = float(cur.fetchone()[0])

            # Win rate
            cur.execute(
                "SELECT COUNT(*) FILTER (WHERE pnl > 0), COUNT(*) FROM trades "
                "WHERE symbol=%s AND side='sell' AND pnl IS NOT NULL",
                (self.symbol,),
            )
            row = cur.fetchone()
            wins, total = row[0], row[1]
            metrics["win_rate"] = wins / max(total, 1)
            metrics["winning_trades"] = wins
            metrics["losing_trades"] = total - wins

            # Último preço
            cur.execute(
                "SELECT price FROM trades WHERE symbol=%s ORDER BY created_at DESC LIMIT 1",
                (self.symbol,),
            )
            row = cur.fetchone()
            metrics["last_price"] = float(row[0]) if row else 0

            # Buys vs Sells
            cur.execute(
                "SELECT side, COUNT(*) FROM trades WHERE symbol=%s GROUP BY side",
                (self.symbol,),
            )
            for side, count in cur.fetchall():
                metrics[f"trades_{side}"] = count

            cur.close()
            self._put_conn(conn)

        except Exception as e:
            metrics["error"] = str(e)

        return metrics

    def collect_rag_metrics(self) -> Dict:
        """Coleta métricas do Market RAG."""
        metrics: Dict = {}
        try:
            adj_file = BASE_DIR / "data" / "market_rag" / "regime_adjustments.json"
            if adj_file.exists():
                with open(adj_file) as f:
                    data = json.load(f)
                current = data.get("current", {})
                metrics["regime"] = current.get("suggested_regime", "UNKNOWN")
                metrics["regime_confidence"] = current.get("regime_confidence", 0)
                metrics["buy_threshold"] = current.get("buy_threshold", 0.3)
                metrics["sell_threshold"] = current.get("sell_threshold", -0.3)
                metrics["ai_min_confidence"] = current.get("ai_min_confidence", 0.6)
                metrics["ai_min_trade_interval"] = current.get("ai_min_trade_interval", 180)
                metrics["ai_take_profit_pct"] = current.get("ai_take_profit_pct", 0.025)
                metrics["ai_aggressiveness"] = current.get("ai_aggressiveness", 0.5)
        except Exception as e:
            logger.debug("RAG metrics load: %s", e)
        return metrics

    def collect_tax_metrics(self) -> Dict:
        """Coleta métricas fiscais do TaxTracker."""
        metrics: Dict = {}
        try:
            tax_file = BASE_DIR / "data" / f"tax_state_{self.symbol}.json"
            if not tax_file.exists():
                tax_file = BASE_DIR / "data" / "tax_state.json"
            if tax_file.exists():
                with open(tax_file) as f:
                    data = json.load(f)
                losses = data.get("accumulated_losses", {})
                metrics["loss_equity_swing"] = float(losses.get("equity_swing", 0))
                metrics["loss_equity_daytrade"] = float(losses.get("equity_daytrade", 0))
                metrics["loss_futures_swing"] = float(losses.get("futures_swing", 0))
                metrics["loss_futures_daytrade"] = float(losses.get("futures_daytrade", 0))

                # Mês atual
                from datetime import datetime, timezone, timedelta
                brt = timezone(timedelta(hours=-3))
                ym = datetime.now(brt).strftime("%Y-%m")
                monthly = data.get("monthly", {}).get(ym, {})
                metrics["equity_swing_sales_total"] = float(monthly.get("equity_swing_sales_total", 0))
                metrics["equity_swing_remaining"] = float(monthly.get("equity_swing_remaining", 20000))
                metrics["equity_swing_pnl"] = float(monthly.get("equity_swing_pnl", 0))
                metrics["equity_daytrade_pnl"] = float(monthly.get("equity_daytrade_pnl", 0))
                metrics["futures_swing_pnl"] = float(monthly.get("futures_swing_pnl", 0))
                metrics["futures_daytrade_pnl"] = float(monthly.get("futures_daytrade_pnl", 0))
                metrics["irrf_total"] = float(monthly.get("irrf_total", 0))
                metrics["total_tax_due"] = float(monthly.get("total_tax_due", 0))
                metrics["equity_swing_exempt"] = 1 if monthly.get("equity_swing_exempt", True) else 0
                metrics["events_count"] = int(monthly.get("events_count", 0))
        except Exception as e:
            logger.debug("Tax metrics load: %s", e)
        return metrics


def format_metrics(collector: MetricsCollector) -> str:
    """Formata métricas no formato Prometheus text exposition."""
    lines: list[str] = []
    symbol = collector.symbol
    profile = collector.profile
    labels = f'symbol="{symbol}",profile="{profile}",market="B3"'

    # Trade metrics
    tm = collector.collect_trade_metrics()
    lines.append(f'# HELP clear_trades_total Total de trades executados')
    lines.append(f'# TYPE clear_trades_total counter')
    lines.append(f'clear_trades_total{{{labels}}} {tm.get("total_trades", 0)}')

    lines.append(f'# HELP clear_trades_24h Trades nas últimas 24 horas')
    lines.append(f'# TYPE clear_trades_24h gauge')
    lines.append(f'clear_trades_24h{{{labels}}} {tm.get("trades_24h", 0)}')

    lines.append(f'# HELP clear_pnl_total PnL total em BRL')
    lines.append(f'# TYPE clear_pnl_total gauge')
    lines.append(f'clear_pnl_total{{{labels}}} {tm.get("total_pnl", 0):.2f}')

    lines.append(f'# HELP clear_pnl_24h PnL nas últimas 24 horas em BRL')
    lines.append(f'# TYPE clear_pnl_24h gauge')
    lines.append(f'clear_pnl_24h{{{labels}}} {tm.get("pnl_24h", 0):.2f}')

    lines.append(f'# HELP clear_win_rate Win rate (0.0–1.0)')
    lines.append(f'# TYPE clear_win_rate gauge')
    lines.append(f'clear_win_rate{{{labels}}} {tm.get("win_rate", 0):.4f}')

    lines.append(f'# HELP clear_last_price Último preço em BRL')
    lines.append(f'# TYPE clear_last_price gauge')
    lines.append(f'clear_last_price{{{labels}}} {tm.get("last_price", 0):.2f}')

    # RAG metrics
    rag = collector.collect_rag_metrics()
    regime_map = {"BULLISH": 1, "BEARISH": -1, "RANGING": 0, "UNKNOWN": 0}
    lines.append(f'# HELP clear_rag_regime Regime de mercado (1=bull, 0=ranging, -1=bear)')
    lines.append(f'# TYPE clear_rag_regime gauge')
    lines.append(f'clear_rag_regime{{{labels}}} {regime_map.get(rag.get("regime", "UNKNOWN"), 0)}')

    lines.append(f'# HELP clear_rag_confidence Confiança do regime')
    lines.append(f'# TYPE clear_rag_confidence gauge')
    lines.append(f'clear_rag_confidence{{{labels}}} {rag.get("regime_confidence", 0):.4f}')

    lines.append(f'# HELP clear_ai_take_profit_pct Take-profit dinâmico (%)')
    lines.append(f'# TYPE clear_ai_take_profit_pct gauge')
    lines.append(f'clear_ai_take_profit_pct{{{labels}}} {rag.get("ai_take_profit_pct", 0.025):.5f}')

    # Tax Guardrails metrics
    tax = collector.collect_tax_metrics()
    lines.append(f'# HELP clear_tax_equity_swing_sales_brl Total de vendas de ações swing no mês (BRL)')
    lines.append(f'# TYPE clear_tax_equity_swing_sales_brl gauge')
    lines.append(f'clear_tax_equity_swing_sales_brl{{{labels}}} {tax.get("equity_swing_sales_total", 0):.2f}')

    lines.append(f'# HELP clear_tax_equity_swing_remaining_brl Headroom restante para isenção R$20k (BRL)')
    lines.append(f'# TYPE clear_tax_equity_swing_remaining_brl gauge')
    lines.append(f'clear_tax_equity_swing_remaining_brl{{{labels}}} {tax.get("equity_swing_remaining", 20000):.2f}')

    lines.append(f'# HELP clear_tax_equity_swing_exempt Dentro da isenção R$20k (1=sim, 0=não)')
    lines.append(f'# TYPE clear_tax_equity_swing_exempt gauge')
    lines.append(f'clear_tax_equity_swing_exempt{{{labels}}} {tax.get("equity_swing_exempt", 1)}')

    lines.append(f'# HELP clear_tax_pnl_equity_swing_brl PnL ações swing no mês (BRL)')
    lines.append(f'# TYPE clear_tax_pnl_equity_swing_brl gauge')
    lines.append(f'clear_tax_pnl_equity_swing_brl{{{labels}}} {tax.get("equity_swing_pnl", 0):.2f}')

    lines.append(f'# HELP clear_tax_pnl_equity_daytrade_brl PnL ações day trade no mês (BRL)')
    lines.append(f'# TYPE clear_tax_pnl_equity_daytrade_brl gauge')
    lines.append(f'clear_tax_pnl_equity_daytrade_brl{{{labels}}} {tax.get("equity_daytrade_pnl", 0):.2f}')

    lines.append(f'# HELP clear_tax_pnl_futures_swing_brl PnL futuros swing no mês (BRL)')
    lines.append(f'# TYPE clear_tax_pnl_futures_swing_brl gauge')
    lines.append(f'clear_tax_pnl_futures_swing_brl{{{labels}}} {tax.get("futures_swing_pnl", 0):.2f}')

    lines.append(f'# HELP clear_tax_pnl_futures_daytrade_brl PnL futuros day trade no mês (BRL)')
    lines.append(f'# TYPE clear_tax_pnl_futures_daytrade_brl gauge')
    lines.append(f'clear_tax_pnl_futures_daytrade_brl{{{labels}}} {tax.get("futures_daytrade_pnl", 0):.2f}')

    lines.append(f'# HELP clear_tax_irrf_brl IRRF retido no mês (BRL)')
    lines.append(f'# TYPE clear_tax_irrf_brl gauge')
    lines.append(f'clear_tax_irrf_brl{{{labels}}} {tax.get("irrf_total", 0):.4f}')

    lines.append(f'# HELP clear_tax_due_brl IR total estimado a pagar no mês (BRL)')
    lines.append(f'# TYPE clear_tax_due_brl gauge')
    lines.append(f'clear_tax_due_brl{{{labels}}} {tax.get("total_tax_due", 0):.2f}')

    lines.append(f'# HELP clear_tax_loss_accumulated_brl Prejuízo acumulado por categoria (BRL)')
    lines.append(f'# TYPE clear_tax_loss_accumulated_brl gauge')
    lines.append(f'clear_tax_loss_accumulated_brl{{{labels},category="equity_swing"}} {tax.get("loss_equity_swing", 0):.2f}')
    lines.append(f'clear_tax_loss_accumulated_brl{{{labels},category="equity_daytrade"}} {tax.get("loss_equity_daytrade", 0):.2f}')
    lines.append(f'clear_tax_loss_accumulated_brl{{{labels},category="futures_swing"}} {tax.get("loss_futures_swing", 0):.2f}')
    lines.append(f'clear_tax_loss_accumulated_brl{{{labels},category="futures_daytrade"}} {tax.get("loss_futures_daytrade", 0):.2f}')

    lines.append(f'# HELP clear_tax_events_count Eventos fiscais registrados no mês')
    lines.append(f'# TYPE clear_tax_events_count gauge')
    lines.append(f'clear_tax_events_count{{{labels}}} {tax.get("events_count", 0)}')

    lines.append("")
    return "\n".join(lines)


class MetricsHandler(BaseHTTPRequestHandler):
    """Handler HTTP para endpoint /metrics."""

    collector: MetricsCollector

    def do_GET(self) -> None:
        """Responde requisições GET."""
        if self.path == "/metrics":
            body = format_metrics(self.collector)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode())
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args) -> None:
        """Suprime logs de requisição padrão."""
        pass


def main() -> None:
    """Entrypoint do Prometheus exporter."""
    config = load_config()
    symbol = config.get("symbol", "PETR4")
    profile = config.get("profile", "default")

    collector = MetricsCollector(DATABASE_URL, symbol=symbol, profile=profile)
    MetricsHandler.collector = collector

    server = ThreadingHTTPServer(("0.0.0.0", METRICS_PORT), MetricsHandler)
    print(f"📊 Clear Prometheus Exporter: http://0.0.0.0:{METRICS_PORT}/metrics")
    print(f"   Symbol: {symbol} | Profile: {profile}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Exporter stopped")
        server.shutdown()


if __name__ == "__main__":
    main()
