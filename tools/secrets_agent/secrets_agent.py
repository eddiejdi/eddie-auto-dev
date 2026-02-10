#!/usr/bin/env python3
"""Secrets Agent

 - lista títulos de itens do Bitwarden (quando disponível)
 - armazena/retorna segredos locais em SQLite (POST /secrets)
 - retorna segredo sob requisição autenticada (X-API-KEY)
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
from pydantic import BaseModel
from typing import Optional
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


class SecretPayload(BaseModel):
    name: str
    value: str
    field: str = "password"
    notes: Optional[str] = None


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
    c.execute("""
    CREATE TABLE IF NOT EXISTS secrets_store (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        field TEXT NOT NULL DEFAULT 'password',
        value TEXT NOT NULL,
        notes TEXT,
        created_at INTEGER,
        updated_at INTEGER,
        UNIQUE(name, field)
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
    """List all secrets: local store + Bitwarden (if available)."""
    # Local secrets
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, field FROM secrets_store ORDER BY name")
    local = [{"id": f"local:{r[0]}:{r[1]}", "title": r[0], "field": r[1], "source": "local"} for r in c.fetchall()]
    conn.close()
    # Bitwarden secrets
    bw_items = bw_list_items()
    bw_summary = [{"id": it.get("id"), "title": it.get("name"), "source": "bitwarden"} for it in bw_items]
    combined = local + bw_summary
    SECRETS_COUNT.set(len(combined))
    return {"count": len(combined), "items": combined}


@app.post("/secrets")
def store_secret(request: Request, payload: SecretPayload):
    """Store or update a secret in the local SQLite store."""
    ip = request.client.host
    key = request.headers.get("x-api-key", "")
    if key != API_KEY:
        ACCESS_FAILURE.inc()
        audit_log(ip, "store", payload.name, "denied")
        raise HTTPException(status_code=401, detail="unauthorized")

    now = int(time.time())
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO secrets_store (name, field, value, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(name, field) DO UPDATE SET value=excluded.value, notes=excluded.notes, updated_at=excluded.updated_at
    """, (payload.name, payload.field, payload.value, payload.notes, now, now))
    conn.commit()
    conn.close()
    ACCESS_SUCCESS.inc()
    audit_log(ip, "store", payload.name, "ok")
    return {"status": "stored", "name": payload.name, "field": payload.field}


@app.get("/secrets/local/{name}")
def get_local_secret(request: Request, name: str, field: str = "password"):
    """Retrieve a locally stored secret by name and optional field."""
    ip = request.client.host
    key = request.headers.get("x-api-key", "")
    if key != API_KEY:
        ACCESS_FAILURE.inc()
        audit_log(ip, "fetch_local", name, "denied")
        FAILED_IP.setdefault(ip, []).append(time.time())
        if check_rate(ip) > FAIL_THRESHOLD:
            LEAK_ALERTS.inc()
        raise HTTPException(status_code=401, detail="unauthorized")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value, notes FROM secrets_store WHERE name=? AND field=?", (name, field))
    row = c.fetchone()
    conn.close()
    if not row:
        ACCESS_FAILURE.inc()
        audit_log(ip, "fetch_local", name, "not_found")
        raise HTTPException(status_code=404, detail=f"secret '{name}' field '{field}' not found")
    ACCESS_SUCCESS.inc()
    audit_log(ip, "fetch_local", name, "ok")
    return {"name": name, "field": field, "value": row[0], "notes": row[1]}


@app.delete("/secrets/local/{name}")
def delete_local_secret(request: Request, name: str, field: str = "password"):
    """Delete a locally stored secret."""
    ip = request.client.host
    key = request.headers.get("x-api-key", "")
    if key != API_KEY:
        ACCESS_FAILURE.inc()
        audit_log(ip, "delete_local", name, "denied")
        raise HTTPException(status_code=401, detail="unauthorized")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM secrets_store WHERE name=? AND field=?", (name, field))
    deleted = c.rowcount
    conn.commit()
    conn.close()
    if deleted == 0:
        raise HTTPException(status_code=404, detail="not found")
    audit_log(ip, "delete_local", name, "ok")
    return {"status": "deleted", "name": name, "field": field}


@app.get("/secrets/{item_id}")
def get_secret(request: Request, item_id: str):
    """Fetch a secret by Bitwarden item_id or local name (local:<name>:<field>)."""
    ip = request.client.host
    key = request.headers.get("x-api-key", "")
    if key != API_KEY:
        ACCESS_FAILURE.inc()
        audit_log(ip, "fetch", item_id, "denied")
        FAILED_IP.setdefault(ip, []).append(time.time())
        if check_rate(ip) > FAIL_THRESHOLD:
            LEAK_ALERTS.inc()
        raise HTTPException(status_code=401, detail="unauthorized")

    # Check local store first if item_id starts with 'local:'
    if item_id.startswith("local:"):
        parts = item_id.split(":", 2)
        name = parts[1] if len(parts) > 1 else item_id
        field = parts[2] if len(parts) > 2 else "password"
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT value FROM secrets_store WHERE name=? AND field=?", (name, field))
        row = c.fetchone()
        conn.close()
        if row:
            ACCESS_SUCCESS.inc()
            audit_log(ip, "fetch", item_id, "ok")
            return {"id": item_id, "value": row[0]}

    # Fallback to Bitwarden
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
