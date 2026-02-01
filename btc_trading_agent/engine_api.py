#!/usr/bin/env python3
"""
Bitcoin Trading Engine - API HTTP
API para controle e configuração do engine via painel web
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import logging

# Paths
ENGINE_DIR = Path(__file__).parent
sys.path.insert(0, str(ENGINE_DIR))

from trading_engine import get_engine
from btc_query import get_market_analysis, get_recent_trades, get_performance

# ====================== CONFIG ======================
API_PORT = int(os.getenv("BTC_ENGINE_API_PORT", "8511"))
API_HOST = os.getenv("BTC_ENGINE_API_HOST", "0.0.0.0")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ====================== REQUEST HANDLER ======================
class EngineAPIHandler(BaseHTTPRequestHandler):
    """Handler para API HTTP"""

    def _send_json(self, data: dict, status: int = 200):
        """Envia resposta JSON"""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS"
        )
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def _send_error(self, message: str, status: int = 400):
        """Envia erro"""
        self._send_json({"error": message}, status)

    def _read_body(self) -> dict:
        """Lê body da requisição"""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                body = self.rfile.read(content_length)
                return json.loads(body.decode())
        except:
            pass
        return {}

    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS"
        )
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        """Handle GET requests"""
        parsed = urlparse(self.path)
        path = parsed.path
        engine = get_engine()

        # Health check
        if path == "/health":
            self._send_json({"status": "healthy", "service": "btc-trading-engine"})

        # Status
        elif path == "/api/status":
            self._send_json(
                {
                    "engine": engine.get_stats(),
                    "config": engine.get_config(),
                    "timestamp": datetime.now().isoformat(),
                }
            )

        # Stats
        elif path == "/api/stats":
            self._send_json(engine.get_stats())

        # Config
        elif path == "/api/config":
            self._send_json(engine.get_config())

        # Price
        elif path == "/api/price":
            from kucoin_api import get_price_fast

            price = get_price_fast(engine.config["symbol"])
            self._send_json(
                {
                    "symbol": engine.config["symbol"],
                    "price": price,
                    "formatted": f"${price:,.2f}" if price else None,
                }
            )

        # Balances - Saldo da conta
        elif path == "/api/balances":
            try:
                from kucoin_api import get_balances, get_balance, get_price_fast

                balances = get_balances()

                # Filtrar apenas saldos > 0
                active_balances = [b for b in balances if b["balance"] > 0]

                # Calcular valor total em USDT
                total_usdt = 0
                for b in active_balances:
                    if b["currency"] == "USDT":
                        total_usdt += b["balance"]
                    elif b["currency"] == "BTC":
                        btc_price = get_price_fast("BTC-USDT")
                        if btc_price:
                            total_usdt += b["balance"] * btc_price
                    else:
                        # Tentar obter preço de outras moedas
                        try:
                            price = get_price_fast(f"{b['currency']}-USDT")
                            if price:
                                total_usdt += b["balance"] * price
                        except:
                            pass

                self._send_json(
                    {
                        "balances": active_balances,
                        "total_usdt": round(total_usdt, 2),
                        "formatted_total": f"${total_usdt:,.2f}",
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            except Exception as e:
                self._send_error(f"Erro ao obter saldo: {str(e)}", 500)

        # Saldo específico de uma moeda
        elif path.startswith("/api/balance/"):
            try:
                from kucoin_api import get_balance

                currency = path.split("/")[-1].upper()
                balance = get_balance(currency)
                self._send_json(
                    {
                        "currency": currency,
                        "available": balance,
                        "formatted": (
                            f"{balance:.8f}" if currency == "BTC" else f"{balance:.2f}"
                        ),
                    }
                )
            except Exception as e:
                self._send_error(f"Erro ao obter saldo: {str(e)}", 500)

        # Histórico de execuções (fills)
        elif path == "/api/fills":
            try:
                from kucoin_api import get_fills

                query = parse_qs(parsed.query)
                symbol = query.get("symbol", [engine.config["symbol"]])[0]
                limit = int(query.get("limit", [20])[0])
                fills = get_fills(symbol, limit)

                # Calcular totais
                total_bought = sum(
                    float(f.get("size", 0)) for f in fills if f.get("side") == "buy"
                )
                total_sold = sum(
                    float(f.get("size", 0)) for f in fills if f.get("side") == "sell"
                )
                total_fees = sum(float(f.get("fee", 0)) for f in fills)

                self._send_json(
                    {
                        "fills": fills,
                        "summary": {
                            "total_bought": total_bought,
                            "total_sold": total_sold,
                            "total_fees": total_fees,
                            "count": len(fills),
                        },
                        "symbol": symbol,
                    }
                )
            except Exception as e:
                self._send_error(f"Erro ao obter histórico: {str(e)}", 500)

        # Analysis
        elif path == "/api/analysis":
            self._send_json({"analysis": get_market_analysis()})

        # Trades
        elif path == "/api/trades":
            query = parse_qs(parsed.query)
            limit = int(query.get("limit", [10])[0])
            self._send_json({"trades": get_recent_trades(limit)})

        # Performance
        elif path == "/api/performance":
            self._send_json({"performance": get_performance()})

        # Signals
        elif path == "/api/signals":
            self._send_json(
                {
                    "last_signal": engine.stats.last_signal,
                    "signals_generated": engine.stats.signals_generated,
                }
            )

        else:
            self._send_error("Not found", 404)

    def do_POST(self):
        """Handle POST requests"""
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_body()
        engine = get_engine()

        # Start engine
        if path == "/api/start":
            if engine.start():
                self._send_json({"success": True, "message": "Engine started"})
            else:
                self._send_error("Failed to start engine")

        # Stop engine
        elif path == "/api/stop":
            if engine.stop():
                self._send_json({"success": True, "message": "Engine stopped"})
            else:
                self._send_error("Failed to stop engine")

        # Pause engine
        elif path == "/api/pause":
            if engine.pause():
                self._send_json({"success": True, "message": "Engine paused"})
            else:
                self._send_error("Failed to pause engine")

        # Resume engine
        elif path == "/api/resume":
            if engine.resume():
                self._send_json({"success": True, "message": "Engine resumed"})
            else:
                self._send_error("Failed to resume engine")

        # Manual buy
        elif path == "/api/buy":
            amount = body.get("amount", 10)
            result = engine.manual_buy(amount)
            self._send_json(
                {
                    "success": result.success,
                    "trade": (
                        {
                            "side": result.side,
                            "size": result.size,
                            "price": result.price,
                            "funds": result.funds,
                        }
                        if result.success
                        else None
                    ),
                    "error": result.error,
                }
            )

        # Manual sell
        elif path == "/api/sell":
            result = engine.manual_sell()
            self._send_json(
                {
                    "success": result.success,
                    "trade": (
                        {
                            "side": result.side,
                            "size": result.size,
                            "price": result.price,
                            "pnl": result.pnl,
                        }
                        if result.success
                        else None
                    ),
                    "error": result.error,
                }
            )

        # Close position
        elif path == "/api/close":
            result = engine.close_position()
            self._send_json({"success": result.success, "error": result.error})

        else:
            self._send_error("Not found", 404)

    def do_PUT(self):
        """Handle PUT requests"""
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_body()
        engine = get_engine()

        # Update config
        if path == "/api/config":
            if engine.update_config(body):
                self._send_json({"success": True, "config": engine.get_config()})
            else:
                self._send_error("Failed to update config")

        else:
            self._send_error("Not found", 404)

    def log_message(self, format, *args):
        """Override para log customizado"""
        logger.info(f"{self.client_address[0]} - {args[0]}")


# ====================== SERVER ======================
def run_api_server(host: str = API_HOST, port: int = API_PORT):
    """Inicia servidor da API"""
    server = HTTPServer((host, port), EngineAPIHandler)

    print(f"""
╔═══════════════════════════════════════════════════════════╗
║  Bitcoin Trading Engine - API Server                      ║
╠═══════════════════════════════════════════════════════════╣
║  URL: http://{host}:{port}                                ║
║                                                           ║
║  Endpoints:                                               ║
║    GET  /api/status        - Status completo              ║
║    GET  /api/stats         - Estatísticas do engine       ║
║    GET  /api/config        - Configuração atual           ║
║    GET  /api/price         - Preço atual                  ║
║    GET  /api/balances      - Saldos da conta KuCoin       ║
║    GET  /api/balance/BTC   - Saldo de moeda específica    ║
║    GET  /api/fills         - Histórico de execuções       ║
║    GET  /api/analysis      - Análise de mercado           ║
║    GET  /api/trades        - Trades recentes              ║
║    GET  /api/signals       - Último sinal                 ║
║                                                           ║
║    POST /api/start         - Iniciar engine               ║
║    POST /api/stop          - Parar engine                 ║
║    POST /api/pause         - Pausar engine                ║
║    POST /api/resume        - Resumir engine               ║
║    POST /api/buy           - Compra manual                ║
║    POST /api/sell          - Venda manual                 ║
║    POST /api/close         - Fechar posição               ║
║                                                           ║
║    PUT  /api/config        - Atualizar config             ║
╚═══════════════════════════════════════════════════════════╝
""")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 API Server stopped")
        server.shutdown()


if __name__ == "__main__":
    run_api_server()
