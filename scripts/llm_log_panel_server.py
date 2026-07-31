#!/usr/bin/env python3
"""Painel de auditoria de prompts LLM — backend HTTP.

Serve UI em JS para:
  - ver TODOS os prompts que passaram pelo ollama-gpu-coordinator (:11437)
  - histórico em PostgreSQL (ollama_payload_log), se DATABASE_URL estiver setada
  - prompts de trading em btc.llm_calls (quando o DB de trading estiver disponível)
  - config do log de fine-tuning (btc.llm_log_config)

Endpoints:
  GET  /  | /index.html | /llm-prompts/…  → painel HTML
  GET  /llm_log_panel.js                  → frontend
  GET  /api/health
  GET  /api/coordinator-requests          → proxy resiliente do ring /api/requests
       (sempre HTTP 200; se o coordinator cair, devolve {"requests":[],"degraded":true})
  GET  /api/config                        → {config, stats} (trading)
  POST /api/config                        → atualiza config trading
  GET  /api/prompts                       → lista unificada de prompts
       ?source=all|coordinator|pg|trading
       &limit=50 &offset=0 &model= &q= &status=
  GET  /api/prompts/export                → JSON download (mesmos filtros)

Autenticação: PANEL_API_KEY (header X-API-KEY ou ?key=).
Em produção, o Authentik proxy em auth.rpa4all.com/llm-prompts/ é a porta de entrada.

Uso:
  python3 scripts/llm_log_panel_server.py
  LLM_LOG_PANEL_PORT=8092 COORDINATOR_URL=http://192.168.15.2:11437 \\
    python3 scripts/llm_log_panel_server.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("llm-log-panel")

HOST = os.environ.get("LLM_LOG_PANEL_HOST", "0.0.0.0")
PORT = int(os.environ.get("LLM_LOG_PANEL_PORT", "8092"))
API_KEY = os.environ.get("PANEL_API_KEY", "").strip()
COORDINATOR_URL = os.environ.get(
    "COORDINATOR_URL",
    os.environ.get("OLLAMA_HOST", "http://192.168.15.2:11437"),
).rstrip("/")
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
STATIC_DIR = Path(__file__).resolve().parent / "llm_log_panel"

# Trading DB é opcional — painel continua útil só com coordinator.
# Import e conexão são 100% lazy para o servidor subir sem esperar Secrets Agent.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "btc_trading_agent"))
_DB = None
_DB_IMPORT_ERROR: str | None = None
_DB_TRIED = False
TrainingDatabase = None  # type: ignore


def _load_training_db_class():
    """Importa TrainingDatabase sob demanda (evita atraso no boot)."""
    global TrainingDatabase, _DB_IMPORT_ERROR
    if TrainingDatabase is not None or _DB_IMPORT_ERROR:
        return TrainingDatabase
    try:
        from training_db import TrainingDatabase as _TDB  # type: ignore

        TrainingDatabase = _TDB  # type: ignore
        return TrainingDatabase
    except Exception as exc:  # pragma: no cover
        _DB_IMPORT_ERROR = str(exc)
        log.warning("import training_db falhou: %s", exc)
        return None


def _db():
    """Instância lazy do TrainingDatabase (pode falhar sem DSN de trading)."""
    global _DB, _DB_TRIED, _DB_IMPORT_ERROR
    if _DB is not None:
        return _DB
    if _DB_TRIED:
        return None
    _DB_TRIED = True
    cls = _load_training_db_class()
    if cls is None:
        return None
    try:
        _DB = cls()
        return _DB
    except Exception as exc:
        _DB_IMPORT_ERROR = str(exc)
        log.warning("TrainingDatabase indisponível: %s", exc)
        return None


def _authorized(handler: BaseHTTPRequestHandler) -> bool:
    if not API_KEY:
        return True
    if handler.headers.get("X-API-KEY", "") == API_KEY:
        return True
    # permite ?key= na query (útil no primeiro load do JS via meta)
    qs = parse_qs(urlparse(handler.path).query)
    return (qs.get("key") or [""])[0] == API_KEY


def _fetch_coordinator_raw(limit: int = 100) -> tuple[list[dict[str, Any]], bool]:
    """Busca o ring do coordinator. Retorna (rows, degraded).

    degraded=True quando o coordinator não respondeu — o caller deve
    preferir HTTP 200 + lista vazia a 5xx/timeout (painel Grafana Infinity
    transforma falha de upstream em status 400 a cada refresh).
    """
    url = f"{COORDINATOR_URL}/api/requests?limit={max(1, min(limit, 500))}"
    req = urllib.request.Request(url, headers={"User-Agent": "llm-log-panel/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        log.warning("coordinator /api/requests falhou: %s", exc)
        return [], True
    rows = data.get("requests") or []
    if not isinstance(rows, list):
        return [], True
    return [r for r in rows if isinstance(r, dict)], False


def _fetch_coordinator_requests(limit: int = 100) -> list[dict[str, Any]]:
    rows, _degraded = _fetch_coordinator_raw(limit=limit)
    out: list[dict[str, Any]] = []
    for i, r in enumerate(rows):
        out.append(
            {
                "id": f"coord-{r.get('ts', i)}-{r.get('model', '')}-{i}",
                "source": "coordinator",
                "ts": r.get("ts"),
                "model": r.get("model") or "",
                "endpoint": r.get("endpoint") or "",
                "path": r.get("path") or "",
                "status": r.get("status"),
                "elapsed_s": r.get("elapsed_s"),
                "streaming": bool(r.get("streaming")),
                "prompt": r.get("prompt") or "",
                "response": r.get("response") or "",
                "error": r.get("error") or "",
                "prompt_chars": len(r.get("prompt") or ""),
                "response_chars": len(r.get("response") or ""),
            }
        )
    return out


def _fetch_pg_payload_log(limit: int = 100, offset: int = 0, model: str = "", q: str = "") -> list[dict[str, Any]]:
    if not DATABASE_URL:
        return []
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        return []
    clauses = ["1=1"]
    params: list[Any] = []
    if model:
        clauses.append("model ILIKE %s")
        params.append(f"%{model}%")
    if q:
        clauses.append("(prompt ILIKE %s OR response ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])
    sql = (
        "SELECT id, ts, model, endpoint, path, status, elapsed_s, streaming, prompt, response "
        f"FROM ollama_payload_log WHERE {' AND '.join(clauses)} "
        "ORDER BY ts DESC NULLS LAST LIMIT %s OFFSET %s"
    )
    params.extend([limit, offset])
    try:
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        finally:
            conn.close()
    except Exception as exc:
        log.warning("ollama_payload_log query falhou: %s", exc)
        return []
    out = []
    for r in rows:
        out.append(
            {
                "id": f"pg-{r.get('id')}",
                "source": "pg",
                "ts": r.get("ts").isoformat() if hasattr(r.get("ts"), "isoformat") else r.get("ts"),
                "model": r.get("model") or "",
                "endpoint": r.get("endpoint") or "",
                "path": r.get("path") or "",
                "status": r.get("status"),
                "elapsed_s": r.get("elapsed_s"),
                "streaming": bool(r.get("streaming")),
                "prompt": r.get("prompt") or "",
                "response": r.get("response") or "",
                "error": "",
                "prompt_chars": len(r.get("prompt") or ""),
                "response_chars": len(r.get("response") or ""),
            }
        )
    return out


def _fetch_trading_calls(limit: int = 100, model: str = "", q: str = "") -> list[dict[str, Any]]:
    db = _db()
    if db is None:
        return []
    try:
        # get_llm_calls ordena ASC; pedimos mais e invertemos
        rows = db.get_llm_calls(limit=min(max(limit, 1) * 2, 2000))
    except Exception as exc:
        log.warning("btc.llm_calls query falhou: %s", exc)
        return []
    rows = list(reversed(rows))[:limit]
    out = []
    for r in rows:
        prompt = r.get("prompt") or ""
        response = r.get("response_text") or ""
        if model and model.lower() not in (r.get("model") or "").lower():
            continue
        if q and q.lower() not in (prompt + response).lower():
            continue
        ts = r.get("timestamp")
        if isinstance(ts, (int, float)):
            from datetime import datetime, timezone

            ts_iso = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        else:
            ts_iso = str(ts) if ts is not None else ""
        out.append(
            {
                "id": f"trade-{r.get('id')}",
                "source": "trading",
                "ts": ts_iso,
                "model": r.get("model") or "",
                "endpoint": r.get("host") or "",
                "path": f"btc.llm_calls/{r.get('call_type') or ''}",
                "status": 200,
                "elapsed_s": (float(r["latency_ms"]) / 1000.0) if r.get("latency_ms") is not None else None,
                "streaming": False,
                "prompt": prompt,
                "response": response,
                "error": "",
                "prompt_chars": len(prompt),
                "response_chars": len(response),
                "meta": {
                    "call_type": r.get("call_type"),
                    "symbol": r.get("symbol"),
                    "profile": r.get("profile"),
                    "trigger": r.get("trigger"),
                },
            }
        )
    return out[:limit]


def _filter_rows(
    rows: list[dict[str, Any]],
    *,
    model: str = "",
    q: str = "",
    status: str = "",
) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        if model and model.lower() not in (r.get("model") or "").lower():
            continue
        if status:
            try:
                if int(r.get("status") or 0) != int(status):
                    continue
            except ValueError:
                continue
        if q:
            blob = f"{r.get('prompt','')} {r.get('response','')} {r.get('model','')} {r.get('endpoint','')}"
            if q.lower() not in blob.lower():
                continue
        out.append(r)
    return out


def _trading_payload() -> dict[str, Any]:
    db = _db()
    if db is None:
        return {
            "config": None,
            "stats": None,
            "available": False,
            "error": _DB_IMPORT_ERROR or "TrainingDatabase indisponível",
        }
    try:
        return {
            "config": db.get_llm_log_config(),
            "stats": db.get_llm_call_stats(),
            "available": True,
        }
    except Exception as exc:
        return {"config": None, "stats": None, "available": False, "error": str(exc)}


class Handler(BaseHTTPRequestHandler):
    server_version = "LLMLogPanel/2.0"

    def _send(self, code: int, body: bytes, content_type: str, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        # path-based proxy sob auth.rpa4all.com/llm-prompts/
        self.send_header("Access-Control-Allow-Origin", "*")
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, obj: dict | list) -> None:
        self._send(
            code,
            json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def _normalize_path(self) -> str:
        path = urlparse(self.path).path
        # suporta montagem sob /llm-prompts/ no Authentik proxy
        for prefix in ("/llm-prompts", "/llm_prompts", "/llm-log"):
            if path == prefix:
                return "/"
            if path.startswith(prefix + "/"):
                return path[len(prefix) :] or "/"
        return path

    def _serve_static(self, name: str, content_type: str) -> None:
        path = STATIC_DIR / name
        if not path.exists():
            self._send_json(404, {"error": f"{name} não encontrado"})
            return
        self._send(200, path.read_bytes(), content_type)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send(204, b"", "text/plain", {
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, X-API-KEY, X-Updated-By",
        })

    def do_GET(self) -> None:  # noqa: N802
        route = self._normalize_path()
        qs = parse_qs(urlparse(self.path).query)

        if route in ("/", "/index.html"):
            self._serve_static("index.html", "text/html; charset=utf-8")
            return
        if route in ("/llm_log_panel.js", "/panel.js"):
            self._serve_static("llm_log_panel.js", "application/javascript; charset=utf-8")
            return
        if route == "/api/health":
            self._send_json(
                200,
                {
                    "ok": True,
                    "coordinator_url": COORDINATOR_URL,
                    "pg_enabled": bool(DATABASE_URL),
                    "trading_db": _db() is not None,
                },
            )
            return

        # Proxy resiliente do ring do coordinator — usado pelo painel Grafana
        # "Payload Log" (Infinity datasource). Sempre 200 para não poluir o
        # dashboard com 400 a cada refresh quando o coordinator reinicia.
        if route in ("/api/coordinator-requests", "/api/requests"):
            try:
                limit = int((qs.get("limit") or ["50"])[0])
            except (TypeError, ValueError):
                limit = 50
            limit = max(1, min(limit, 200))
            rows, degraded = _fetch_coordinator_raw(limit=limit)
            self._send_json(
                200,
                {
                    "requests": rows,
                    "total": len(rows),
                    "degraded": degraded,
                    "source": COORDINATOR_URL,
                },
            )
            return

        if route in ("/api/config", "/api/prompts", "/api/prompts/export"):
            if not _authorized(self):
                self._send_json(401, {"error": "unauthorized"})
                return

        if route == "/api/config":
            try:
                self._send_json(200, _trading_payload())
            except Exception as e:
                log.error("GET /api/config falhou: %s", e)
                self._send_json(500, {"error": str(e)})
            return

        if route in ("/api/prompts", "/api/prompts/export"):
            try:
                source = (qs.get("source") or ["all"])[0].strip().lower()
                limit = int((qs.get("limit") or ["80"])[0])
                offset = int((qs.get("offset") or ["0"])[0])
                model = (qs.get("model") or [""])[0].strip()
                q = (qs.get("q") or [""])[0].strip()
                status = (qs.get("status") or [""])[0].strip()
                limit = max(1, min(limit, 500))
                offset = max(0, offset)

                rows: list[dict[str, Any]] = []
                sources_used: list[str] = []
                if source in ("all", "coordinator"):
                    rows.extend(_fetch_coordinator_requests(limit=min(limit + offset, 500)))
                    sources_used.append("coordinator")
                if source in ("all", "pg"):
                    rows.extend(_fetch_pg_payload_log(limit=limit + offset, offset=0, model=model, q=q))
                    sources_used.append("pg")
                if source in ("all", "trading"):
                    rows.extend(_fetch_trading_calls(limit=limit + offset, model=model, q=q))
                    sources_used.append("trading")

                rows = _filter_rows(rows, model=model, q=q, status=status)

                # ordena por ts desc (string ISO funciona)
                def _ts_key(item: dict[str, Any]) -> str:
                    return str(item.get("ts") or "")

                rows.sort(key=_ts_key, reverse=True)
                # dedupe grosseiro por (ts, model, prompt[:120])
                seen: set[str] = set()
                deduped: list[dict[str, Any]] = []
                for r in rows:
                    key = f"{r.get('ts')}|{r.get('model')}|{(r.get('prompt') or '')[:120]}"
                    if key in seen:
                        continue
                    seen.add(key)
                    deduped.append(r)
                total = len(deduped)
                page = deduped[offset : offset + limit]

                payload = {
                    "total": total,
                    "offset": offset,
                    "limit": limit,
                    "sources": sources_used,
                    "coordinator_url": COORDINATOR_URL,
                    "items": page,
                }
                if route.endswith("/export"):
                    body = json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")
                    self._send(
                        200,
                        body,
                        "application/json; charset=utf-8",
                        {"Content-Disposition": "attachment; filename=llm-prompts-export.json"},
                    )
                else:
                    self._send_json(200, payload)
            except Exception as e:
                log.error("GET /api/prompts falhou: %s", e)
                self._send_json(500, {"error": str(e)})
            return

        self._send_json(404, {"error": "rota desconhecida", "path": route})

    def do_POST(self) -> None:  # noqa: N802
        route = self._normalize_path()
        if route != "/api/config":
            self._send_json(404, {"error": "rota desconhecida"})
            return
        if not _authorized(self):
            self._send_json(401, {"error": "unauthorized"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            fields = json.loads(raw.decode("utf-8") or "{}")
        except Exception as e:
            self._send_json(400, {"error": f"JSON inválido: {e}"})
            return
        db = _db()
        if db is None:
            self._send_json(503, {"error": "TrainingDatabase indisponível"})
            return
        try:
            updated_by = self.headers.get("X-Updated-By") or self.client_address[0]
            db.set_llm_log_config(updated_by=updated_by, **fields)
            log.info("config atualizada por %s: %s", updated_by, fields)
            self._send_json(200, _trading_payload())
        except Exception as e:
            log.error("POST /api/config falhou: %s", e)
            self._send_json(500, {"error": str(e)})

    def log_message(self, fmt: str, *args) -> None:
        log.debug("%s - %s", self.address_string(), fmt % args)


def main() -> int:
    log.info(
        "Painel auditoria LLM em http://%s:%d (auth=%s coord=%s)",
        HOST,
        PORT,
        "on" if API_KEY else "off",
        COORDINATOR_URL,
    )
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info("encerrando")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
