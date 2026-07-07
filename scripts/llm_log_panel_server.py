#!/usr/bin/env python3
"""Painel de controle do log de LLM (Fase 1 do fine-tuning) — backend HTTP.

Serve um painel em JS para LIGAR/DESLIGAR o log de chamadas ao Ollama
(btc.llm_calls) e parametrizar suas variáveis (toggle por call_type, sample_rate,
truncagem de prompt, retenção). Os agentes de trading leem a config com cache curto
(30s) e a respeitam — sem nunca deixar o log interferir na decisão de trading.

Endpoints:
  GET  /                     → painel (HTML)
  GET  /llm_log_panel.js     → JS do painel
  GET  /api/config           → {config, stats}
  POST /api/config           → aplica config parcial (JSON no corpo) → {config, stats}

Autenticação: se PANEL_API_KEY estiver no ambiente, exige header X-API-KEY nos POST
(e nos GET /api). Sem a env, roda aberto na LAN (padrão dos painéis internos).

Só toca a tabela btc.llm_log_config (via TrainingDatabase) e LÊ btc.llm_calls para
stats. Não altera trading, não troca modelo, não faz deploy.

Uso:
  python3 scripts/llm_log_panel_server.py            # 0.0.0.0:8092
  LLM_LOG_PANEL_PORT=9000 python3 scripts/llm_log_panel_server.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))
from training_db import TrainingDatabase  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("llm-log-panel")

HOST = os.environ.get("LLM_LOG_PANEL_HOST", "0.0.0.0")
PORT = int(os.environ.get("LLM_LOG_PANEL_PORT", "8092"))
API_KEY = os.environ.get("PANEL_API_KEY", "").strip()
STATIC_DIR = Path(__file__).resolve().parent / "llm_log_panel"

# Uma única instância de DB compartilhada pelas threads (pool interno é thread-safe).
_DB: TrainingDatabase | None = None


def _db() -> TrainingDatabase:
    global _DB
    if _DB is None:
        _DB = TrainingDatabase()
    return _DB


def _payload() -> dict:
    db = _db()
    return {"config": db.get_llm_log_config(), "stats": db.get_llm_call_stats()}


class Handler(BaseHTTPRequestHandler):
    server_version = "LLMLogPanel/1.0"

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, obj: dict) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _authorized(self) -> bool:
        if not API_KEY:
            return True
        return self.headers.get("X-API-KEY", "") == API_KEY

    def _serve_static(self, name: str, content_type: str) -> None:
        path = STATIC_DIR / name
        if not path.exists():
            self._send_json(404, {"error": f"{name} não encontrado"})
            return
        self._send(200, path.read_bytes(), content_type)

    def do_GET(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        if route in ("/", "/index.html"):
            self._serve_static("index.html", "text/html; charset=utf-8")
        elif route == "/llm_log_panel.js":
            self._serve_static("llm_log_panel.js", "application/javascript; charset=utf-8")
        elif route == "/api/config":
            if not self._authorized():
                self._send_json(401, {"error": "unauthorized"})
                return
            try:
                self._send_json(200, _payload())
            except Exception as e:
                log.error("GET /api/config falhou: %s", e)
                self._send_json(500, {"error": str(e)})
        elif route == "/api/health":
            self._send_json(200, {"ok": True})
        else:
            self._send_json(404, {"error": "rota desconhecida"})

    def do_POST(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        if route != "/api/config":
            self._send_json(404, {"error": "rota desconhecida"})
            return
        if not self._authorized():
            self._send_json(401, {"error": "unauthorized"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            fields = json.loads(raw.decode("utf-8") or "{}")
        except Exception as e:
            self._send_json(400, {"error": f"JSON inválido: {e}"})
            return
        try:
            updated_by = self.headers.get("X-Updated-By") or self.client_address[0]
            _db().set_llm_log_config(updated_by=updated_by, **fields)
            log.info("config atualizada por %s: %s", updated_by, fields)
            self._send_json(200, _payload())
        except Exception as e:
            log.error("POST /api/config falhou: %s", e)
            self._send_json(500, {"error": str(e)})

    def log_message(self, fmt: str, *args) -> None:  # silencia log padrão ruidoso
        log.debug("%s - %s", self.address_string(), fmt % args)


def main() -> int:
    log.info("Painel de log de LLM em http://%s:%d (auth=%s)",
             HOST, PORT, "on" if API_KEY else "off")
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info("encerrando")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
