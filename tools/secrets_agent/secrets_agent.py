#!/usr/bin/env python3
"""Secrets Agent

 - lista títulos de itens do Bitwarden
 - retorna senha sob requisição autenticada (X-API-KEY)
 - mantém auditoria em sqlite e exporta métricas Prometheus
 - detecta tentativas de acesso suspeitas (exaustão/erros repetidos)
"""
import os
import json
import sqlite3
import subprocess
import time
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client import start_http_server

APP_DIR = Path(os.environ.get("SECRETS_AGENT_DATA", "/var/lib/eddie/secrets_agent"))
APP_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = APP_DIR / "audit.db"

API_KEY = os.environ.get("SECRETS_AGENT_API_KEY", "please-set-a-strong-key")

# Prometheus metrics
ACCESS_SUCCESS = Counter("secrets_agent_access_success_total", "Successful secret fetches")
ACCESS_FAILURE = Counter("secrets_agent_access_failure_total", "Failed secret fetch attempts")
LEAK_ALERTS = Counter("secrets_agent_leak_alerts_total", "Leak detection alerts")
SECRETS_COUNT = Gauge("secrets_agent_secrets_count", "Number of secrets discovered")

FAILED_IP = {}
FAIL_WINDOW = 60
FAIL_THRESHOLD = int(os.environ.get("SECRETS_AGENT_FAIL_THRESHOLD", "5"))

app = FastAPI(title="Secrets Agent")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts INTEGER,
        ip TEXT,
        action TEXT,
        secret_id TEXT,
        result TEXT
    )""")
    conn.commit()
    conn.close()


def audit_log(ip, action, secret_id, result):
    ts = int(time.time())
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO audit (ts, ip, action, secret_id, result) VALUES (?, ?, ?, ?, ?)",
              (ts, ip, action, secret_id, result))
    conn.commit()
    conn.close()


def bw_list_items():
    # Requires `bw` CLI and an unlocked session (BW_SESSION env)
    try:
        p = subprocess.run(["bw", "list", "items", "--raw"], capture_output=True, text=True, check=True)
        items = json.loads(p.stdout)
        # update metric
        SECRETS_COUNT.set(len(items))
        return items
    except Exception:
        return []


def bw_get_item_password(item_id):
    # Uses bw get item and extracts password from fields or login.password
    try:
        p = subprocess.run(["bw", "get", "item", item_id], capture_output=True, text=True, check=True)
        obj = json.loads(p.stdout)
        # common locations
        if obj.get("login") and obj["login"].get("password"):
            return obj["login"]["password"]
        # search fields
        for f in obj.get("fields", []):
            if f.get("type") in ("password",) or f.get("name", "").lower() in ("password", "api_token", "token"):
                return f.get("value")
        # fallback to notes
        return obj.get("notes")
    except Exception:
        return None


def check_rate(ip):
    now = time.time()
    times = FAILED_IP.get(ip, [])
    times = [t for t in times if now - t <= FAIL_WINDOW]
    FAILED_IP[ip] = times
    return len(times)


@app.get("/metrics")
def metrics():
    return JSONResponse(content=generate_latest().decode(), media_type=CONTENT_TYPE_LATEST)


@app.get("/secrets")
def list_secrets():
    items = bw_list_items()
    summary = [{"id": it.get("id"), "title": it.get("name")} for it in items]
    return {"count": len(summary), "items": summary}


@app.get("/secrets/{item_id}")
def get_secret(request: Request, item_id: str):
    ip = request.client.host
    key = request.headers.get("x-api-key", "")
    if key != API_KEY:
        ACCESS_FAILURE.inc()
        audit_log(ip, "fetch", item_id, "denied")
        # rate check
        FAILED_IP.setdefault(ip, []).append(time.time())
        if check_rate(ip) > FAIL_THRESHOLD:
            LEAK_ALERTS.inc()
        raise HTTPException(status_code=401, detail="unauthorized")

    pwd = bw_get_item_password(item_id)
    if pwd is None:
        ACCESS_FAILURE.inc()
        audit_log(ip, "fetch", item_id, "not_found")
        raise HTTPException(status_code=404, detail="secret not found")

    ACCESS_SUCCESS.inc()
    audit_log(ip, "fetch", item_id, "ok")
    return {"id": item_id, "value": pwd}


@app.get("/audit/recent")
def recent_audit(limit: int = 50):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT ts, ip, action, secret_id, result FROM audit ORDER BY ts DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return {"rows": rows}


if __name__ == "__main__":
    init_db()
    # prometheus client HTTP on port 8001 by default
    prometheus_port = int(os.environ.get("SECRETS_AGENT_PROM_PORT", "8001"))
    start_http_server(prometheus_port)
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("SECRETS_AGENT_PORT", "8088")))
