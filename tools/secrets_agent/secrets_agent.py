#!/usr/bin/env python3
"""Secrets Agent — gateway unificado para secrets com auto-unlock Bitwarden.

Funcionalidades:
 - Auto-login e auto-unlock do Bitwarden (sem solicitar senha)
 - Cache persistente de sessão BW (sobrevive a restarts)
 - Lista títulos de itens do Bitwarden
 - Armazena/retorna segredos diretamente no Bitwarden (sem SQLite)
 - Retorna segredo sob requisição autenticada (X-API-KEY)
 - Mantém auditoria em memória e exporta métricas Prometheus
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
import subprocess
import time
import threading
from collections import deque
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
APP_DIR = Path(os.environ.get("SECRETS_AGENT_DATA", "/var/lib/shared/secrets_agent"))
APP_DIR.mkdir(parents=True, exist_ok=True)

API_KEY = os.environ.get("SECRETS_AGENT_API_KEY", "please-set-a-strong-key")

BW_SESSION_CACHE = APP_DIR / "bw_session.cache"
BW_PASSWORD_FILE = Path(
    os.environ.get("BW_PASSWORD_FILE", str(APP_DIR / ".bw_master_password"))
)
BW_CMD_TIMEOUT = int(os.environ.get("BW_CMD_TIMEOUT", "60"))
BW_STATUS_TIMEOUT = int(os.environ.get("BW_STATUS_TIMEOUT", "10"))

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
AUDIT_MAX = int(os.environ.get("SECRETS_AGENT_AUDIT_MAX", "5000"))
AUDIT_EVENTS = deque(maxlen=AUDIT_MAX)


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
        self._auth_failure_ttl: float = float(
            os.environ.get("BW_AUTH_FAILURE_TTL", "300")
        )
        self._last_auth_failure: float = 0.0
        self._last_auth_failure_reason: str = ""
        self._auth_lock = threading.Lock()
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
        self._clear_auth_failure()
        os.environ.pop("BW_SESSION", None)
        try:
            BW_SESSION_CACHE.unlink(missing_ok=True)
        except OSError:
            pass

    def _clear_auth_failure(self) -> None:
        """Limpa estado de backoff após autenticação bem-sucedida."""
        self._last_auth_failure = 0.0
        self._last_auth_failure_reason = ""

    def _mark_auth_failure(self, reason: str) -> None:
        """Ativa backoff temporário após falha de login/unlock."""
        self._last_auth_failure = time.time()
        self._last_auth_failure_reason = reason

    def _auth_backoff_active(self) -> bool:
        """Retorna True se ainda estiver em cooldown após falha recente."""
        if self._last_auth_failure <= 0:
            return False
        age = time.time() - self._last_auth_failure
        if age >= self._auth_failure_ttl:
            self._clear_auth_failure()
            return False
        remaining = int(self._auth_failure_ttl - age)
        logger.info(
            "BW em cooldown por falha recente (%ss restantes): %s",
            remaining,
            self._last_auth_failure_reason or "auth failure",
        )
        return True

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

    def _session_probe_ok(self) -> bool:
        """Valida sessão BW por comando real (evita falso 'locked' do bw status)."""
        if not self._session:
            return False
        try:
            p = subprocess.run(
                ["bw", "list", "items", "--search", "__secrets_agent_probe__", "--raw"],
                capture_output=True,
                text=True,
                timeout=BW_STATUS_TIMEOUT,
                env=self._build_env(),
            )
            if p.returncode == 0:
                return True
            stderr = (p.stderr or "").lower()
            if "session key" in stderr or "not logged in" in stderr:
                self._invalidate_session()
            return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_status(self, force: bool = False) -> str:
        """Retorna status do BW: 'unauthenticated', 'locked', 'unlocked', 'unknown'.

        Cacheia resultado por _status_ttl segundos para evitar chamadas excessivas.
        """
        now = time.time()
        if not force and (now - self._last_check) < self._status_ttl:
            return self._last_status
        if self._session_probe_ok():
            self._last_status = "unlocked"
            self._last_check = now
            BW_STATUS_GAUGE.set(3)
            return "unlocked"
        try:
            p = subprocess.run(
                ["bw", "status"],
                capture_output=True, text=True,
                timeout=BW_STATUS_TIMEOUT, env=self._build_env(),
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
                self._clear_auth_failure()
                logger.info("Login BW via API key bem-sucedido")
                self._last_check = 0.0  # forçar re-check de status
                return True
            reason = p.stderr.strip() or "api key login failed"
            self._mark_auth_failure(reason)
            logger.warning(f"Login BW via API key falhou: {reason}")
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            self._mark_auth_failure(str(exc))
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
                self._clear_auth_failure()
                logger.info("Login BW via email+password bem-sucedido")
                return True
            reason = p.stderr.strip() or "email login failed"
            self._mark_auth_failure(reason)
            logger.warning(f"Login BW via email falhou: {reason}")
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            self._mark_auth_failure(str(exc))
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
            self._mark_auth_failure("master password unavailable")
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
                self._clear_auth_failure()
                BW_STATUS_GAUGE.set(3)
                BW_UNLOCK_SUCCESS.inc()
                logger.info("Auto-unlock BW bem-sucedido")
                return True
            reason = p.stderr.strip() or f"unlock failed rc={p.returncode}"
            self._mark_auth_failure(reason)
            logger.warning(f"Auto-unlock BW falhou (rc={p.returncode}): {reason}")
        except subprocess.TimeoutExpired:
            self._mark_auth_failure("unlock timeout")
            logger.warning("Auto-unlock BW timeout")
        except FileNotFoundError:
            self._mark_auth_failure("bw command not found")
            logger.error("Comando 'bw' não encontrado no PATH")
        BW_UNLOCK_FAILURE.inc()
        return False

    # ── Garantia de sessão ───────────────────────────────────

    def ensure_session(self) -> bool:
        """Garante sessão BW válida sem solicitar senha interativamente.

        Retorna True se sessão está pronta, False se impossível.
        """
        with self._auth_lock:
            status = self.get_status(force=False)

            if status == "unlocked":
                self._clear_auth_failure()
                return True

            if self._auth_backoff_active():
                return False

            if status == "locked":
                logger.info("BW locked — tentando auto-unlock...")
                return self._try_unlock()

            if status == "unauthenticated":
                logger.info("BW não autenticado — tentando auto-login...")
                if self._try_login():
                    # após login, pode estar locked — tentar unlock
                    new_status = self.get_status(force=True)
                    if new_status == "unlocked":
                        self._clear_auth_failure()
                        return True
                    if new_status == "locked":
                        return self._try_unlock()
                return False

            # unknown — tentar unlock direto (pode funcionar se bw está ok)
            logger.info(f"BW status '{status}' — tentando unlock direto...")
            return self._try_unlock()

    # ── Execução de comandos BW ──────────────────────────────

    def run_command(
        self,
        args: list[str],
        retry: bool = True,
        input_data: Optional[str] = None,
    ) -> subprocess.CompletedProcess:
        """Executa comando bw com sessão garantida e retry em falha."""
        if not self.ensure_session():
            return subprocess.CompletedProcess(
                ["bw"] + args,
                1,
                "",
                "Bitwarden unavailable; session could not be established",
            )
        env = self._build_env()
        try:
            result = subprocess.run(
                ["bw"] + args,
                input=input_data,
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
                            input=input_data,
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

    def get_info(self, non_blocking: bool = False) -> dict:
        """Retorna informações de diagnóstico da sessão BW."""
        if non_blocking:
            status = self._last_status
            session_ready = bool(self._session) and status == "unlocked"
        else:
            session_ready = self.ensure_session()
            status = self.get_status(force=True)
            if session_ready and status != "unlocked":
                status = "unlocked"
        has_master = self._get_master_password() is not None
        has_api_key = bool(os.environ.get("BW_CLIENTID"))
        has_email = bool(os.environ.get("BW_EMAIL"))
        has_session = bool(self._session)
        has_cache = BW_SESSION_CACHE.exists()
        return {
            "bw_status": status,
            "session_ready": session_ready,
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
#  LocalVault — fallback criptografado quando BW indisponível
# ═══════════════════════════════════════════════════════════════

import hashlib
import hmac
import base64
import secrets as _secrets_mod

LOCAL_VAULT_DIR = APP_DIR / "local_vault"
LOCAL_VAULT_DIR.mkdir(parents=True, exist_ok=True)
LOCAL_VAULT_PASSFILE = APP_DIR / "simple_vault_passphrase"

LOCAL_SECRETS_COUNT = Gauge(
    "secrets_agent_local_secrets_count", "Number of secrets in local vault"
)


class LocalVault:
    """Vault local criptografado com HMAC-SHA256 para fallback sem BW.

    Armazena secrets como arquivos JSON assinados em local_vault/.
    Usa passphrase do arquivo simple_vault_passphrase como chave.
    """

    def __init__(self, vault_dir: Path, passfile: Path) -> None:
        self._dir = vault_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._passfile = passfile
        self._key: Optional[bytes] = None

    def _get_key(self) -> bytes:
        """Obtém a chave de criptografia da passphrase."""
        if self._key:
            return self._key
        if not self._passfile.exists():
            passphrase = _secrets_mod.token_hex(32)
            self._passfile.write_text(passphrase)
            self._passfile.chmod(0o600)
            logger.info(f"Nova passphrase gerada em {self._passfile}")
        raw = self._passfile.read_text().strip()
        self._key = hashlib.sha256(raw.encode()).digest()
        return self._key

    def _safe_filename(self, name: str, field: str) -> str:
        """Gera nome de arquivo seguro para o secret."""
        tag = hashlib.sha256(f"{name}:{field}".encode()).hexdigest()[:16]
        return f"{tag}.json"

    def _sign(self, data: bytes) -> str:
        """HMAC-SHA256 do conteúdo."""
        return hmac.new(self._get_key(), data, hashlib.sha256).hexdigest()

    def _xor_crypt(self, data: bytes) -> bytes:
        """Criptografia XOR simétrica com chave derivada (para valores curtos)."""
        key = self._get_key()
        stream = hashlib.sha256(key + b"stream").digest()
        out = bytearray(len(data))
        for i in range(len(data)):
            ki = i % len(stream)
            if ki == 0 and i > 0:
                stream = hashlib.sha256(key + stream).digest()
            out[i] = data[i] ^ stream[ki]
        return bytes(out)

    def store(
        self, name: str, value: str, field: str = "password", notes: Optional[str] = None
    ) -> bool:
        """Armazena secret no vault local."""
        try:
            payload = json.dumps({
                "name": name,
                "field": field,
                "value": base64.b64encode(self._xor_crypt(value.encode())).decode(),
                "notes": notes,
                "ts": int(time.time()),
            }, separators=(",", ":"))
            sig = self._sign(payload.encode())
            envelope = json.dumps({"data": payload, "sig": sig}, separators=(",", ":"))
            fpath = self._dir / self._safe_filename(name, field)
            fpath.write_text(envelope)
            fpath.chmod(0o600)
            logger.info(f"Local vault: stored '{name}' field='{field}'")
            self._update_metric()
            return True
        except Exception as exc:
            logger.error(f"Local vault store error: {exc}")
            return False

    def get(self, name: str, field: str = "password") -> Optional[str]:
        """Recupera secret do vault local."""
        fpath = self._dir / self._safe_filename(name, field)
        if not fpath.exists():
            return None
        try:
            envelope = json.loads(fpath.read_text())
            data_str = envelope["data"]
            sig = envelope["sig"]
            if not hmac.compare_digest(self._sign(data_str.encode()), sig):
                logger.error(f"Local vault: HMAC mismatch for '{name}'")
                return None
            payload = json.loads(data_str)
            encrypted = base64.b64decode(payload["value"])
            return self._xor_crypt(encrypted).decode()
        except Exception as exc:
            logger.error(f"Local vault get error: {exc}")
            return None

    def delete(self, name: str, field: str = "password") -> bool:
        """Remove secret do vault local."""
        fpath = self._dir / self._safe_filename(name, field)
        if fpath.exists():
            fpath.unlink()
            logger.info(f"Local vault: deleted '{name}' field='{field}'")
            self._update_metric()
            return True
        return False

    def list_all(self) -> list[dict]:
        """Lista todos os secrets no vault local."""
        items = []
        for fpath in self._dir.glob("*.json"):
            try:
                envelope = json.loads(fpath.read_text())
                data_str = envelope["data"]
                sig = envelope["sig"]
                if not hmac.compare_digest(self._sign(data_str.encode()), sig):
                    continue
                payload = json.loads(data_str)
                items.append({
                    "name": payload["name"],
                    "field": payload["field"],
                    "ts": payload.get("ts"),
                    "source": "local_vault",
                })
            except Exception:
                continue
        return items

    def _update_metric(self) -> None:
        """Atualiza métrica Prometheus."""
        count = len(list(self._dir.glob("*.json")))
        LOCAL_SECRETS_COUNT.set(count)


local_vault = LocalVault(LOCAL_VAULT_DIR, LOCAL_VAULT_PASSFILE)


# ═══════════════════════════════════════════════════════════════
#  FastAPI App
# ═══════════════════════════════════════════════════════════════

app = FastAPI(title="Secrets Agent", version="2.1.0")


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
                    "Operações de secrets dependem do BW."
                )
        except Exception as exc:
            logger.error(f"Erro ao auto-unlock BW: {exc}")

    thread = threading.Thread(target=_bg_unlock, daemon=True, name="bw-auto-unlock")
    thread.start()


def init_db() -> None:
    """Compatibilidade retroativa: SQLite removido, nada a inicializar."""
    return None


def audit_log(ip: str, action: str, secret_id: str, result: str) -> None:
    """Registra ação de auditoria em memória."""
    ts = int(time.time())
    AUDIT_EVENTS.append((ts, ip, action, secret_id, result))


def _bw_item_name(secret_name: str, field: str) -> str:
    """Nome canônico do item BW para evitar colisão entre fields."""
    if field == "password":
        return secret_name
    return f"{secret_name}#{field}"


def _bw_notes(secret_name: str, field: str, notes: Optional[str]) -> str:
    """Notas com marcador de origem do Secrets Agent."""
    header = "\n".join(
        [
            "[secrets-agent]",
            f"secret={secret_name}",
            f"field={field}",
        ]
    )
    if notes:
        return f"{header}\n\n{notes}"
    return header


def bw_non_blocking_available() -> bool:
    """Indica se vale tentar BW sem fazer probes bloqueantes."""
    return bw_manager.get_info(non_blocking=True).get("bw_status") == "unlocked"


def bw_find_item_exact(name: str) -> Optional[dict]:
    """Busca item BW por nome exato."""
    if not bw_non_blocking_available():
        return None
    try:
        p = bw_manager.run_command(["list", "items", "--search", name, "--raw"])
        if p.returncode != 0:
            logger.warning(f"bw list --search '{name}' falhou: {p.stderr.strip()}")
            return None
        items = json.loads(p.stdout or "[]")
        exact = [it for it in items if it.get("name") == name]
        if not exact:
            return None
        if len(exact) > 1:
            logger.warning(
                f"Encontrados {len(exact)} itens BW com nome duplicado '{name}'. "
                f"Usando id={exact[0].get('id')}"
            )
        return exact[0]
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as exc:
        logger.warning(f"bw find item '{name}' erro: {exc}")
    # Fallback: alguns nomes (com caracteres especiais/path) podem não aparecer no --search.
    obj = bw_get_item(name)
    if obj and obj.get("name") == name:
        return {"id": obj.get("id"), "name": obj.get("name")}
    return None


def bw_upsert_secret(payload: "SecretPayload") -> tuple[bool, str, Optional[str]]:
    """Cria/atualiza item no BW para refletir o secret local."""
    item_name = _bw_item_name(payload.name, payload.field)
    try:
        existing = bw_find_item_exact(item_name)

        if existing and existing.get("id"):
            item_obj = bw_get_item(existing["id"])
            if not item_obj:
                return False, item_name, "failed_to_load_existing_item"
        else:
            p_tpl = bw_manager.run_command(["get", "template", "item"])
            if p_tpl.returncode != 0:
                reason = (p_tpl.stderr or "template fetch failed").strip()
                return False, item_name, f"template_error:{reason}"
            try:
                item_obj = json.loads(p_tpl.stdout)
            except json.JSONDecodeError:
                return False, item_name, "template_decode_error"

        item_obj["type"] = 1  # login item
        item_obj["name"] = item_name
        item_obj["notes"] = _bw_notes(payload.name, payload.field, payload.notes)
        login = item_obj.get("login") or {}
        login["username"] = payload.field
        login["password"] = payload.value
        login["uris"] = login.get("uris") or []
        item_obj["login"] = login

        encoded_input = json.dumps(item_obj, separators=(",", ":"), ensure_ascii=True)
        p_enc = bw_manager.run_command(["encode"], input_data=encoded_input)
        if p_enc.returncode != 0:
            reason = (p_enc.stderr or "encode failed").strip()
            return False, item_name, f"encode_error:{reason}"
        encoded = (p_enc.stdout or "").strip()
        if not encoded:
            return False, item_name, "encode_empty_output"

        if existing and existing.get("id"):
            p_save = bw_manager.run_command(["edit", "item", existing["id"], encoded])
        else:
            p_save = bw_manager.run_command(["create", "item", encoded])
        if p_save.returncode != 0:
            reason = (p_save.stderr or "save failed").strip()
            # Fallback para valores/formatos rejeitados pelo login item:
            # usa secure note com valor bruto em notes.
            if "model state is invalid" in reason.lower():
                fallback_obj = json.loads(json.dumps(item_obj))
                fallback_obj["type"] = 2  # secure note
                fallback_obj["secureNote"] = {"type": 0}
                fallback_obj["login"] = None
                fallback_obj["notes"] = payload.value

                fallback_in = json.dumps(fallback_obj, separators=(",", ":"), ensure_ascii=True)
                p_enc2 = bw_manager.run_command(["encode"], input_data=fallback_in)
                if p_enc2.returncode != 0 or not (p_enc2.stdout or "").strip():
                    reason2 = (p_enc2.stderr or "encode fallback failed").strip()
                    return False, item_name, f"fallback_encode_error:{reason2}"
                encoded2 = (p_enc2.stdout or "").strip()

                if existing and existing.get("id"):
                    p_save2 = bw_manager.run_command(["edit", "item", existing["id"], encoded2])
                else:
                    p_save2 = bw_manager.run_command(["create", "item", encoded2])
                if p_save2.returncode == 0:
                    return True, item_name, None
                reason2 = (p_save2.stderr or "fallback save failed").strip()
                return False, item_name, f"fallback_save_error:{reason2}"

            return False, item_name, f"save_error:{reason}"

        return True, item_name, None
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return False, item_name, f"command_error:{exc}"


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


def bw_get_secret_value(name: str, field: str = "password") -> Optional[str]:
    """Busca secret por nome lógico + field usando convenção canônica no BW."""
    item_name = _bw_item_name(name, field)
    exact = bw_find_item_exact(item_name)
    if not exact:
        return None
    item_id = exact.get("id") or item_name
    return bw_get_item_password(item_id)


def bw_get_secret_fields(name: str) -> dict[str, str]:
    """Retorna todos os fields de um secret nomeado via itens `<name>#<field>`."""
    if not bw_non_blocking_available():
        return {}
    try:
        p = bw_manager.run_command(["list", "items", "--search", name, "--raw"])
        if p.returncode != 0:
            return {}
        items = json.loads(p.stdout or "[]")
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        return {}

    fields: dict[str, str] = {}
    prefix = f"{name}#"
    for it in items:
        title = it.get("name") or ""
        if title == name:
            field_name = "password"
        elif title.startswith(prefix):
            field_name = title[len(prefix):]
            if not field_name:
                continue
        else:
            continue
        item_id = it.get("id") or title
        value = bw_get_item_password(item_id)
        if value is not None:
            fields[field_name] = value
    return fields


def bw_delete_secret(name: str, field: str = "password") -> tuple[bool, Optional[str]]:
    """Remove secret do BW por nome lógico/field."""
    item_name = _bw_item_name(name, field)
    exact = bw_find_item_exact(item_name)
    if not exact or not exact.get("id"):
        return False, "not_found"
    p = bw_manager.run_command(["delete", "item", exact["id"]])
    if p.returncode != 0:
        reason = (p.stderr or "delete failed").strip()
        return False, reason
    return True, None


def parse_local_ref(item_id: str, default_field: str = "password") -> tuple[str, str]:
    """Converte `local:<name>:<field>` para (name, field)."""
    parts = item_id.split(":", 2)
    name = parts[1] if len(parts) > 1 else item_id
    field = parts[2] if len(parts) > 2 else default_field
    return name, field


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
    """Lista secrets disponíveis — BW + local vault."""
    bw_info = bw_manager.get_info(non_blocking=True)
    bw_items = bw_list_items() if bw_info["bw_status"] == "unlocked" else []
    bw_summary = [
        {"id": it.get("id"), "title": it.get("name"), "source": "bitwarden"}
        for it in bw_items
    ]
    local_items = local_vault.list_all()
    all_items = bw_summary + local_items
    SECRETS_COUNT.set(len(all_items))
    return {
        "count": len(all_items),
        "items": all_items,
        "bw_status": bw_info["bw_status"],
    }


@app.post("/secrets")
def store_secret(request: Request, payload: SecretPayload):
    """Store/update secret — tenta BW, fallback para local vault."""
    ip = request.client.host
    key = request.headers.get("x-api-key", "")
    if key != API_KEY:
        ACCESS_FAILURE.inc()
        audit_log(ip, "store", payload.name, "denied")
        raise HTTPException(status_code=401, detail="unauthorized")

    bw_ok = False
    bw_err = None
    bw_item_name = _bw_item_name(payload.name, payload.field)

    # Tenta BW sempre; se não estiver disponível, o erro será reportado.
    bw_ok, bw_item_name, bw_err = bw_upsert_secret(payload)

    # Sempre salva no local vault (mirror/fallback).
    local_ok = local_vault.store(payload.name, payload.value, payload.field, payload.notes)

    if not bw_ok:
        ACCESS_FAILURE.inc()
        audit_log(ip, "store", payload.name, f"bw_failed:{bw_err}")
        raise HTTPException(status_code=503, detail=f"bitwarden unavailable: {bw_err}")

    if not local_ok:
        logger.warning(f"Local vault mirror failed for {payload.name}#{payload.field}")

    ACCESS_SUCCESS.inc()
    audit_log(ip, "store", payload.name, "ok")
    return {
        "status": "stored",
        "name": payload.name,
        "field": payload.field,
        "bw_sync": {
            "enabled": True,
            "ok": bw_ok,
            "item_name": bw_item_name if bw_ok else None,
            "error": bw_err,
        },
        "local_vault": local_ok,
    }


@app.get("/secrets/local/{name:path}")
def get_local_secret(request: Request, name: str, field: str = "password"):
    """Recupera secret exclusivamente do vault local para evitar travas do BW."""
    ip = request.client.host
    key = request.headers.get("x-api-key", "")
    if key != API_KEY:
        ACCESS_FAILURE.inc()
        audit_log(ip, "fetch_local", name, "denied")
        FAILED_IP.setdefault(ip, []).append(time.time())
        if check_rate(ip) > FAIL_THRESHOLD:
            LEAK_ALERTS.inc()
        raise HTTPException(status_code=401, detail="unauthorized")

    value = local_vault.get(name, field)
    if value is None:
        ACCESS_FAILURE.inc()
        audit_log(ip, "fetch_local", name, "not_found")
        raise HTTPException(status_code=404, detail=f"secret '{name}' field '{field}' not found")
    ACCESS_SUCCESS.inc()
    audit_log(ip, "fetch_local", name, "ok")
    return {"name": name, "field": field, "value": value, "notes": None, "source": "local_vault"}


@app.delete("/secrets/local/{name}")
def delete_local_secret(request: Request, name: str, field: str = "password"):
    """Compat route: remove secret correspondente no BW."""
    ip = request.client.host
    key = request.headers.get("x-api-key", "")
    if key != API_KEY:
        ACCESS_FAILURE.inc()
        audit_log(ip, "delete_local", name, "denied")
        raise HTTPException(status_code=401, detail="unauthorized")

    ok, err = bw_delete_secret(name, field)
    if not ok:
        if err == "not_found":
            raise HTTPException(status_code=404, detail="not found")
        raise HTTPException(status_code=503, detail=f"bitwarden unavailable: {err}")
    audit_log(ip, "delete_local", name, "ok")
    return {"status": "deleted", "name": name, "field": field, "source": "bitwarden"}
    

@app.get("/secrets/{item_id:path}")
def get_secret(request: Request, item_id: str, field: str = "password"):
    """Fetch a secret by Bitwarden item_id/name, local:<name>:<field>, ou local vault fallback."""
    ip = request.client.host
    key = request.headers.get("x-api-key", "")
    if key != API_KEY:
        ACCESS_FAILURE.inc()
        audit_log(ip, "fetch", item_id, "denied")
        FAILED_IP.setdefault(ip, []).append(time.time())
        if check_rate(ip) > FAIL_THRESHOLD:
            LEAK_ALERTS.inc()
        raise HTTPException(status_code=401, detail="unauthorized")

    if item_id.startswith("local:"):
        name, local_field = parse_local_ref(item_id, field)
        value = bw_get_secret_value(name, local_field)
        if value is None:
            value = local_vault.get(name, local_field)
        if value is None:
            ACCESS_FAILURE.inc()
            audit_log(ip, "fetch", item_id, "not_found")
            raise HTTPException(status_code=404, detail="secret not found")
        ACCESS_SUCCESS.inc()
        audit_log(ip, "fetch", item_id, "ok")
        return {"id": item_id, "value": value}

    # Tenta BW
    value = bw_get_secret_value(item_id, field)
    if value is not None:
        ACCESS_SUCCESS.inc()
        audit_log(ip, "fetch", item_id, "ok")
        return {"id": item_id, "value": value}

    fields = bw_get_secret_fields(item_id)
    if fields:
        ACCESS_SUCCESS.inc()
        audit_log(ip, "fetch", item_id, "ok")
        return {"id": item_id, "fields": fields}

    # fallback: trata item_id como id real no BW
    pwd = bw_get_item_password(item_id)
    if pwd is not None:
        ACCESS_SUCCESS.inc()
        audit_log(ip, "fetch", item_id, "ok")
        return {"id": item_id, "value": pwd}

    # Fallback final: local vault
    local_val = local_vault.get(item_id, field)
    if local_val is not None:
        ACCESS_SUCCESS.inc()
        audit_log(ip, "fetch", item_id, "ok")
        return {"id": item_id, "value": local_val, "source": "local_vault"}

    ACCESS_FAILURE.inc()
    audit_log(ip, "fetch", item_id, "not_found")
    raise HTTPException(status_code=404, detail="secret not found")


@app.get("/audit/recent")
def recent_audit(limit: int = 50):
    safe_limit = max(0, min(limit, AUDIT_MAX))
    if safe_limit == 0:
        return {"rows": []}
    rows = list(AUDIT_EVENTS)[-safe_limit:]
    rows.reverse()
    return {"rows": rows}


@app.get("/health")
def health():
    """Health check com status BW integrado."""
    bw_info = bw_manager.get_info(non_blocking=True)
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
