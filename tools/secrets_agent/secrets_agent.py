#!/usr/bin/env python3
"""Secrets Agent — gateway unificado para secrets com auto-unlock Bitwarden.

Funcionalidades:
 - Auto-login e auto-unlock do Bitwarden (sem solicitar senha)
 - Cache persistente de sessão BW (sobrevive a restarts)
 - Lista títulos de itens do Bitwarden (quando disponível)
 - Armazena/retorna segredos locais em SQLite (POST /secrets)
 - Retorna segredo sob requisição autenticada (X-API-KEY)
 - Mantém auditoria em SQLite e exporta métricas Prometheus
 - Detecta tentativas de acesso suspeitas (exaustão/erros repetidos)

Autenticação BW (ordem de prioridade):
 1. BW_SESSION env var (sessão já desbloqueada)
 2. Cache em disco ({APP_DIR}/bw_session.cache)
 3. Auto-unlock via BW_MASTER_PASSWORD env var ou BW_PASSWORD_FILE
 4. Auto-login via BW_CLIENTID + BW_CLIENTSECRET (API key)
 5. Auto-login via BW_EMAIL + BW_MASTER_PASSWORD
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import subprocess
import time
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    generate_latest,
    start_http_server,
)
from pydantic import BaseModel

logger = logging.getLogger("secrets_agent")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
)

# ─── Configuração ─────────────────────────────────────────────
APP_DIR = Path(os.environ.get("SECRETS_AGENT_DATA", "/var/lib/eddie/secrets_agent"))
APP_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = APP_DIR / "audit.db"

API_KEY = os.environ.get("SECRETS_AGENT_API_KEY", "please-set-a-strong-key")

BW_SESSION_CACHE = APP_DIR / "bw_session.cache"
BW_PASSWORD_FILE = Path(
    os.environ.get("BW_PASSWORD_FILE", str(APP_DIR / ".bw_master_password"))
)
BW_CMD_TIMEOUT = int(os.environ.get("BW_CMD_TIMEOUT", "30"))

# ─── Métricas Prometheus ──────────────────────────────────────
ACCESS_SUCCESS = Counter("secrets_agent_access_success_total", "Successful secret fetches")
ACCESS_FAILURE = Counter("secrets_agent_access_failure_total", "Failed secret fetch attempts")
LEAK_ALERTS = Counter("secrets_agent_leak_alerts_total", "Leak detection alerts")
SECRETS_COUNT = Gauge("secrets_agent_secrets_count", "Number of secrets discovered")
BW_UNLOCK_SUCCESS = Counter("secrets_agent_bw_unlock_success_total", "BW auto-unlock successes")
BW_UNLOCK_FAILURE = Counter("secrets_agent_bw_unlock_failure_total", "BW auto-unlock failures")
BW_STATUS_GAUGE = Gauge("secrets_agent_bw_status", "BW status: 0=unknown, 1=unauthenticated, 2=locked, 3=unlocked")

FAILED_IP: dict[str, list[float]] = {}
FAIL_WINDOW = 60
FAIL_THRESHOLD = int(os.environ.get("SECRETS_AGENT_FAIL_THRESHOLD", "5"))


# ═══════════════════════════════════════════════════════════════
#  BitwardenSessionManager — auto-login, auto-unlock, cache
# ═══════════════════════════════════════════════════════════════

class BitwardenSessionManager:
    """Gerencia sessão BW com auto-login, auto-unlock e cache persistente.

    Nunca solicita senha interativamente. Usa env vars ou arquivo de senha.
    """

    _STATUS_MAP = {"unauthenticated": 1, "locked": 2, "unlocked": 3}

    def __init__(self) -> None:
        self._session: Optional[str] = None
        self._last_status: str = "unknown"
        self._last_check: float = 0.0
        self._status_ttl: float = float(os.environ.get("BW_STATUS_TTL", "60"))
        self._load_cached_session()

    # ── Carregamento e persistência ──────────────────────────

    def _load_cached_session(self) -> None:
        """Carrega sessão de env var ou cache em disco."""
        # 1) env var
        session = os.environ.get("BW_SESSION", "")
        if session and session not in ("notset", ""):
            self._session = session
            logger.info("Sessão BW carregada de env var BW_SESSION")
            return
        # 2) cache file
        if BW_SESSION_CACHE.exists():
            try:
                cached = BW_SESSION_CACHE.read_text().strip()
                if cached and cached != "notset":
                    self._session = cached
                    os.environ["BW_SESSION"] = cached
                    logger.info("Sessão BW carregada do cache em disco")
                    return
            except OSError as exc:
                logger.warning(f"Falha ao ler cache BW: {exc}")

    def _save_session(self, session: str) -> None:
        """Persiste sessão no env, em memória e em disco."""
        self._session = session
        os.environ["BW_SESSION"] = session
        try:
            BW_SESSION_CACHE.write_text(session)
            BW_SESSION_CACHE.chmod(0o600)
            logger.info("Sessão BW salva no cache em disco")
        except OSError as exc:
            logger.warning(f"Falha ao salvar cache BW: {exc}")

    def _invalidate_session(self) -> None:
        """Invalida sessão atual (força re-unlock no próximo uso)."""
        self._session = None
        self._last_status = "unknown"
        self._last_check = 0.0
        os.environ.pop("BW_SESSION", None)
        try:
            BW_SESSION_CACHE.unlink(missing_ok=True)
        except OSError:
            pass

    # ── Obtenção de credenciais ──────────────────────────────

    def _get_master_password(self) -> Optional[str]:
        """Obtém master password de env var ou arquivo seguro."""
        # 1) env var
        master = os.environ.get("BW_MASTER_PASSWORD")
        if master:
            return master
        # 2) arquivo de senha (mais seguro para systemd)
        if BW_PASSWORD_FILE.exists():
            try:
                return BW_PASSWORD_FILE.read_text().strip()
            except OSError as exc:
                logger.warning(f"Falha ao ler arquivo de senha BW: {exc}")
        return None

    # ── Status ───────────────────────────────────────────────

    def _build_env(self) -> dict[str, str]:
        """Constrói env dict com BW_SESSION setada."""
        env = os.environ.copy()
        if self._session:
            env["BW_SESSION"] = self._session
        return env

    def get_status(self, force: bool = False) -> str:
        """Retorna status do BW: 'unauthenticated', 'locked', 'unlocked', 'unknown'.

        Cacheia resultado por _status_ttl segundos para evitar chamadas excessivas.
        """
        now = time.time()
        if not force and (now - self._last_check) < self._status_ttl:
            return self._last_status
        try:
            p = subprocess.run(
                ["bw", "status"],
                capture_output=True, text=True,
                timeout=BW_CMD_TIMEOUT, env=self._build_env(),
            )
            data = json.loads(p.stdout.strip())
            status = data.get("status", "unknown")
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as exc:
            logger.warning(f"Falha ao verificar status BW: {exc}")
            status = "unknown"

        self._last_status = status
        self._last_check = now
        BW_STATUS_GAUGE.set(self._STATUS_MAP.get(status, 0))
        return status

    # ── Login ────────────────────────────────────────────────

    def _try_api_key_login(self) -> bool:
        """Tenta login via API key (BW_CLIENTID + BW_CLIENTSECRET)."""
        client_id = os.environ.get("BW_CLIENTID")
        client_secret = os.environ.get("BW_CLIENTSECRET")
        if not client_id or not client_secret:
            return False
        try:
            env = os.environ.copy()
            env["BW_CLIENTID"] = client_id
            env["BW_CLIENTSECRET"] = client_secret
            p = subprocess.run(
                ["bw", "login", "--apikey"],
                capture_output=True, text=True,
                timeout=BW_CMD_TIMEOUT, env=env,
            )
            if p.returncode == 0:
                logger.info("Login BW via API key bem-sucedido")
                self._last_check = 0.0  # forçar re-check de status
                return True
            logger.warning(f"Login BW via API key falhou: {p.stderr.strip()}")
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            logger.warning(f"Login BW via API key erro: {exc}")
        return False

    def _try_email_login(self) -> bool:
        """Tenta login via email + master password."""
        email = os.environ.get("BW_EMAIL")
        master = self._get_master_password()
        if not email or not master:
            return False
        try:
            env = os.environ.copy()
            env["BW_MASTER_PASSWORD"] = master
            p = subprocess.run(
                ["bw", "login", email, "--passwordenv", "BW_MASTER_PASSWORD", "--raw"],
                capture_output=True, text=True,
                timeout=BW_CMD_TIMEOUT, env=env,
            )
            session = (p.stdout or "").strip()
            if p.returncode == 0 and session:
                self._save_session(session)
                logger.info("Login BW via email+password bem-sucedido")
                return True
            logger.warning(f"Login BW via email falhou: {p.stderr.strip()}")
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            logger.warning(f"Login BW via email erro: {exc}")
        return False

    def _try_login(self) -> bool:
        """Tenta login por qualquer método disponível."""
        return self._try_api_key_login() or self._try_email_login()

    # ── Unlock ───────────────────────────────────────────────

    def _try_unlock(self) -> bool:
        """Tenta unlock com master password (env var ou arquivo)."""
        master = self._get_master_password()
        if not master:
            logger.warning(
                "Auto-unlock impossível: BW_MASTER_PASSWORD e BW_PASSWORD_FILE "
                f"({BW_PASSWORD_FILE}) não encontrados"
            )
            BW_UNLOCK_FAILURE.inc()
            return False
        try:
            p = subprocess.run(
                ["bw", "unlock", "--raw"],
                input=master,
                capture_output=True, text=True,
                timeout=BW_CMD_TIMEOUT,
            )
            session = (p.stdout or "").strip()
            if p.returncode == 0 and session:
                self._save_session(session)
                self._last_status = "unlocked"
                self._last_check = time.time()
                BW_STATUS_GAUGE.set(3)
                BW_UNLOCK_SUCCESS.inc()
                logger.info("Auto-unlock BW bem-sucedido")
                return True
            logger.warning(f"Auto-unlock BW falhou (rc={p.returncode}): {p.stderr.strip()}")
        except subprocess.TimeoutExpired:
            logger.warning("Auto-unlock BW timeout")
        except FileNotFoundError:
            logger.error("Comando 'bw' não encontrado no PATH")
        BW_UNLOCK_FAILURE.inc()
        return False

    # ── Garantia de sessão ───────────────────────────────────

    def ensure_session(self) -> bool:
        """Garante sessão BW válida sem solicitar senha interativamente.

        Retorna True se sessão está pronta, False se impossível.
        """
        status = self.get_status(force=False)

        if status == "unlocked":
            return True

        if status == "locked":
            logger.info("BW locked — tentando auto-unlock...")
            return self._try_unlock()

        if status == "unauthenticated":
            logger.info("BW não autenticado — tentando auto-login...")
            if self._try_login():
                # após login, pode estar locked — tentar unlock
                new_status = self.get_status(force=True)
                if new_status == "unlocked":
                    return True
                if new_status == "locked":
                    return self._try_unlock()
            return False

        # unknown — tentar unlock direto (pode funcionar se bw está ok)
        logger.info(f"BW status '{status}' — tentando unlock direto...")
        return self._try_unlock()

    # ── Execução de comandos BW ──────────────────────────────

    def run_command(self, args: list[str], retry: bool = True) -> subprocess.CompletedProcess:
        """Executa comando bw com sessão garantida e retry em falha."""
        self.ensure_session()
        env = self._build_env()
        try:
            result = subprocess.run(
                ["bw"] + args,
                capture_output=True, text=True,
                timeout=BW_CMD_TIMEOUT, env=env,
            )
            # Se falhou por sessão expirada, tenta re-unlock
            if result.returncode != 0 and retry:
                stderr = (result.stderr or "").lower()
                if "session key" in stderr or "not logged in" in stderr or "locked" in stderr:
                    logger.info("Sessão BW expirada — re-unlock automático...")
                    self._invalidate_session()
                    if self.ensure_session():
                        env = self._build_env()
                        result = subprocess.run(
                            ["bw"] + args,
                            capture_output=True, text=True,
                            timeout=BW_CMD_TIMEOUT, env=env,
                        )
            return result
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout ao executar bw {args}")
            raise
        except FileNotFoundError:
            logger.error("Comando 'bw' não encontrado")
            raise

    def get_info(self) -> dict:
        """Retorna informações de diagnóstico da sessão BW."""
        status = self.get_status(force=True)
        has_master = self._get_master_password() is not None
        has_api_key = bool(os.environ.get("BW_CLIENTID"))
        has_email = bool(os.environ.get("BW_EMAIL"))
        has_session = bool(self._session)
        has_cache = BW_SESSION_CACHE.exists()
        return {
            "bw_status": status,
            "session_loaded": has_session,
            "session_cache_exists": has_cache,
            "master_password_available": has_master,
            "api_key_available": has_api_key,
            "email_available": has_email,
            "password_file": str(BW_PASSWORD_FILE),
            "password_file_exists": BW_PASSWORD_FILE.exists(),
            "session_cache_path": str(BW_SESSION_CACHE),
        }


# Singleton global
bw_manager = BitwardenSessionManager()


# ═══════════════════════════════════════════════════════════════
#  FastAPI App
# ═══════════════════════════════════════════════════════════════

app = FastAPI(title="Secrets Agent", version="2.0.0")


class SecretPayload(BaseModel):
    """Payload para armazenar um secret local."""
    name: str
    value: str
    field: str = "password"
    notes: Optional[str] = None


@app.on_event("startup")
def startup_bw_session() -> None:
    """Tenta garantir sessão BW em background (não bloqueia startup)."""
    init_db()
    logger.info("Secrets Agent v2.0 iniciando — auto-unlock BW em background...")

    def _bg_unlock() -> None:
        try:
            ok = bw_manager.ensure_session()
            info = bw_manager.get_info()
            if ok:
                logger.info(f"BW pronto: status={info['bw_status']}")
            else:
                logger.warning(
                    f"BW indisponível: status={info['bw_status']}, "
                    f"master_pw={info['master_password_available']}, "
                    f"api_key={info['api_key_available']}. "
                    "Secrets locais continuam funcionando."
                )
        except Exception as exc:
            logger.error(f"Erro ao auto-unlock BW: {exc}")

    thread = threading.Thread(target=_bg_unlock, daemon=True, name="bw-auto-unlock")
    thread.start()


def init_db() -> None:
    """Inicializa banco SQLite de auditoria e secrets locais."""
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


def audit_log(ip: str, action: str, secret_id: str, result: str) -> None:
    """Registra ação na tabela de auditoria."""
    ts = int(time.time())
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT INTO audit (ts, ip, action, secret_id, result) VALUES (?, ?, ?, ?, ?)",
            (ts, ip, action, secret_id, result),
        )
        conn.commit()
        conn.close()
    except sqlite3.Error as exc:
        logger.error(f"Falha ao gravar auditoria: {exc}")


def bw_list_items() -> list[dict]:
    """Lista itens do Bitwarden com auto-unlock transparente."""
    try:
        p = bw_manager.run_command(["list", "items", "--raw"])
        if p.returncode != 0:
            logger.warning(f"bw list items falhou: {p.stderr.strip()}")
            return []
        items = json.loads(p.stdout)
        SECRETS_COUNT.set(len(items))
        return items
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as exc:
        logger.warning(f"bw list items erro: {exc}")
        return []


def bw_get_item(item_id: str) -> Optional[dict]:
    """Busca item completo do Bitwarden por ID ou nome."""
    try:
        p = bw_manager.run_command(["get", "item", item_id])
        if p.returncode != 0:
            logger.warning(f"bw get item '{item_id}' falhou: {p.stderr.strip()}")
            return None
        return json.loads(p.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as exc:
        logger.warning(f"bw get item '{item_id}' erro: {exc}")
        return None


def bw_get_item_password(item_id: str) -> Optional[str]:
    """Extrai password de um item BW (login.password, fields ou notes)."""
    obj = bw_get_item(item_id)
    if not obj:
        return None
    # login.password
    if obj.get("login") and obj["login"].get("password"):
        return obj["login"]["password"]
    # custom fields
    for f in obj.get("fields") or []:
        if f.get("type") in ("password",) or f.get("name", "").lower() in (
            "password", "api_token", "token",
        ):
            return f.get("value")
    # fallback to notes
    return obj.get("notes")


def check_rate(ip: str) -> int:
    """Verifica taxa de falhas por IP."""
    now = time.time()
    times = FAILED_IP.get(ip, [])
    times = [t for t in times if now - t <= FAIL_WINDOW]
    FAILED_IP[ip] = times
    return len(times)


@app.get("/metrics")
def metrics():
    """Métricas Prometheus."""
    return JSONResponse(content=generate_latest().decode(), media_type=CONTENT_TYPE_LATEST)


@app.get("/bw/status")
def bw_status_endpoint():
    """Diagnóstico da sessão Bitwarden (não requer API key)."""
    return bw_manager.get_info()


@app.post("/bw/unlock")
def bw_unlock_endpoint(request: Request):
    """Força re-unlock do Bitwarden (requer API key)."""
    key = request.headers.get("x-api-key", "")
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="unauthorized")
    bw_manager._invalidate_session()
    ok = bw_manager.ensure_session()
    return {
        "success": ok,
        "info": bw_manager.get_info(),
    }


@app.get("/secrets")
def list_secrets():
    """Lista todos os secrets: store local + Bitwarden (com auto-unlock)."""
    # Local secrets
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, field FROM secrets_store ORDER BY name")
    local = [
        {"id": f"local:{r[0]}:{r[1]}", "title": r[0], "field": r[1], "source": "local"}
        for r in c.fetchall()
    ]
    conn.close()
    # Bitwarden secrets (auto-unlock transparente)
    bw_items = bw_list_items()
    bw_summary = [
        {"id": it.get("id"), "title": it.get("name"), "source": "bitwarden"}
        for it in bw_items
    ]
    combined = local + bw_summary
    SECRETS_COUNT.set(len(combined))
    return {
        "count": len(combined),
        "items": combined,
        "bw_status": bw_manager.get_status(),
    }


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


@app.get("/secrets/local/{name:path}")
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


@app.get("/health")
def health():
    """Health check com status BW integrado."""
    bw_info = bw_manager.get_info()
    return {
        "status": "ok",
        "bw_status": bw_info["bw_status"],
        "bw_session_loaded": bw_info["session_loaded"],
    }


if __name__ == "__main__":
    prometheus_port = int(os.environ.get("SECRETS_AGENT_PROM_PORT", "8001"))
    start_http_server(prometheus_port)
    import uvicorn

    port = int(os.environ.get("SECRETS_AGENT_PORT", "8088"))
    logger.info(f"Secrets Agent v2.0 — porta {port}, métricas em {prometheus_port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
