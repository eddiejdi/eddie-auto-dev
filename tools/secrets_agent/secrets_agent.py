#!/usr/bin/env python3
"""Secrets Agent — gateway unificado para secrets com backend Authentik.

Funcionalidades:
 - Armazena/retorna secrets no Authentik via OAuth2 provider API
 - Cache local criptografado (LocalVault) como fallback automático
 - Retorna segredo sob requisição autenticada (X-API-KEY)
 - Mantém auditoria em memória e exporta métricas Prometheus
 - Detecta tentativas de acesso suspeitas (exaustão/erros repetidos)

Backend Authentik (prioridade para leitura/escrita):
 1. Authentik OAuth2 provider API — AUTHENTIK_URL + AUTHENTIK_TOKEN
 2. LocalVault criptografado em disco — fallback quando Authentik indisponível

Convenção de client_id no Authentik:
  secret/{name}             → client_id: secret-{name-com-hifens}
  secret/{name}#{field}     → client_id: secret-{name-com-hifens}-{field-com-hifens}
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets as _secrets_mod
import threading
import time
from collections import deque
from pathlib import Path
from typing import Optional

import requests
import urllib3
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

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("secrets_agent")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
)

# ─── Configuração ─────────────────────────────────────────────
APP_DIR = Path(os.environ.get("SECRETS_AGENT_DATA", "/var/lib/shared/secrets_agent"))
APP_DIR.mkdir(parents=True, exist_ok=True)

API_KEY = os.environ.get("SECRETS_AGENT_API_KEY", "please-set-a-strong-key")

# ─── Métricas Prometheus ──────────────────────────────────────
ACCESS_SUCCESS = Counter("secrets_agent_access_success_total", "Successful secret fetches")
ACCESS_FAILURE = Counter("secrets_agent_access_failure_total", "Failed secret fetch attempts")
LEAK_ALERTS = Counter("secrets_agent_leak_alerts_total", "Leak detection alerts")
SECRETS_COUNT = Gauge("secrets_agent_secrets_count", "Number of secrets discovered")
AK_STATUS_GAUGE = Gauge("secrets_agent_authentik_status", "Authentik: 0=unavailable, 1=available")
AK_STORE_SUCCESS = Counter("secrets_agent_ak_store_success_total", "Authentik store successes")
AK_STORE_FAILURE = Counter("secrets_agent_ak_store_failure_total", "Authentik store failures")

FAILED_IP: dict[str, list[float]] = {}
FAIL_WINDOW = 60
FAIL_THRESHOLD = int(os.environ.get("SECRETS_AGENT_FAIL_THRESHOLD", "5"))
AUDIT_MAX = int(os.environ.get("SECRETS_AGENT_AUDIT_MAX", "5000"))
AUDIT_EVENTS = deque(maxlen=AUDIT_MAX)


# ═══════════════════════════════════════════════════════════════
#  AuthentikSecretManager — leitura/escrita via Authentik API
# ═══════════════════════════════════════════════════════════════

class AuthentikSecretManager:
    """Gerencia secrets via Authentik OAuth2 provider API.

    Cada secret é armazenado como um OAuth2 provider com:
      client_id     = "secret-{name}-{field}" (hifenizado)
      client_secret = <valor>
    """

    def __init__(self) -> None:
        self._base = os.environ.get("AUTHENTIK_URL", "https://auth.rpa4all.com").rstrip("/")
        self._token = os.environ.get("AUTHENTIK_TOKEN", "")
        self._available: bool = False
        self._last_check: float = 0.0
        self._status_ttl: float = float(os.environ.get("AUTHENTIK_STATUS_TTL", "60"))
        self._auth_flow_pk: Optional[str] = None
        self._invalidation_flow_pk: Optional[str] = None
        self._lock = threading.Lock()
        self._http = requests.Session()
        self._http.verify = False

    @property
    def _headers(self) -> dict:
        h: dict = {"Accept": "application/json", "Content-Type": "application/json"}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    def _client_id(self, name: str, field: str = "password") -> str:
        """Converte nome lógico para client_id canônico no Authentik."""
        safe_name = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        if field == "password":
            return f"secret-{safe_name}"
        safe_field = re.sub(r"[^a-z0-9]+", "-", field.lower()).strip("-")
        return f"secret-{safe_name}-{safe_field}"

    # ── Disponibilidade ──────────────────────────────────────

    def _probe(self) -> bool:
        """Testa conectividade com a API do Authentik."""
        if not self._base or not self._token:
            return False
        try:
            r = self._http.get(
                f"{self._base}/api/v3/core/tokens/",
                headers=self._headers,
                params={"page_size": 1},
                timeout=5,
            )
            return r.status_code < 500
        except Exception:
            return False

    def is_available(self, force: bool = False) -> bool:
        """Retorna True se Authentik está acessível (cache por status_ttl segundos)."""
        now = time.time()
        if not force and (now - self._last_check) < self._status_ttl:
            return self._available
        with self._lock:
            self._available = self._probe()
            self._last_check = now
            AK_STATUS_GAUGE.set(1 if self._available else 0)
        return self._available

    def _get_flow_pk(self, designation: str, attr: str) -> Optional[str]:
        """Obtém PK de um flow por designation (cacheado em atributo)."""
        cached = getattr(self, attr, None)
        if cached:
            return cached
        try:
            r = self._http.get(
                f"{self._base}/api/v3/flows/instances/",
                headers=self._headers,
                params={"designation": designation, "page_size": 1},
                timeout=10,
            )
            if r.status_code == 200:
                results = r.json().get("results", [])
                if results:
                    setattr(self, attr, results[0]["pk"])
                    return results[0]["pk"]
        except Exception as exc:
            logger.warning("Authentik: falha ao buscar flow %s: %s", designation, exc)
        return None

    def _get_auth_flow_pk(self) -> Optional[str]:
        return self._get_flow_pk("authorization", "_auth_flow_pk")

    def _get_invalidation_flow_pk(self) -> Optional[str]:
        return self._get_flow_pk("invalidation", "_invalidation_flow_pk")

    # ── Leitura ──────────────────────────────────────────────

    def get_secret(self, name: str, field: str = "password") -> Optional[str]:
        """Busca secret no Authentik por client_id exato."""
        client_id = self._client_id(name, field)
        try:
            r = self._http.get(
                f"{self._base}/api/v3/providers/oauth2/",
                headers=self._headers,
                params={"search": client_id, "page_size": 20},
                timeout=10,
            )
            if r.status_code != 200:
                return None
            for item in r.json().get("results", []):
                if item.get("client_id") == client_id:
                    return item.get("client_secret") or None
        except Exception as exc:
            logger.warning("Authentik get_secret(%s, %s) erro: %s", name, field, exc)
        return None

    def get_secret_fields(self, name: str) -> dict[str, str]:
        """Retorna todos os fields de um secret (busca por prefixo de client_id)."""
        prefix = self._client_id(name, "password")
        try:
            r = self._http.get(
                f"{self._base}/api/v3/providers/oauth2/",
                headers=self._headers,
                params={"search": prefix, "page_size": 50},
                timeout=10,
            )
            if r.status_code != 200:
                return {}
            fields: dict[str, str] = {}
            for item in r.json().get("results", []):
                cid = item.get("client_id", "")
                secret = item.get("client_secret")
                if not secret:
                    continue
                if cid == prefix:
                    fields["password"] = secret
                elif cid.startswith(prefix + "-"):
                    field_name = cid[len(prefix) + 1:]
                    if field_name:
                        fields[field_name] = secret
            return fields
        except Exception as exc:
            logger.warning("Authentik get_secret_fields(%s) erro: %s", name, exc)
            return {}

    # ── Escrita ──────────────────────────────────────────────

    def upsert_secret(self, payload: "SecretPayload") -> tuple[bool, str, Optional[str]]:
        """Cria ou atualiza secret no Authentik via OAuth2 provider."""
        client_id = self._client_id(payload.name, payload.field)
        try:
            r = self._http.get(
                f"{self._base}/api/v3/providers/oauth2/",
                headers=self._headers,
                params={"search": client_id, "page_size": 10},
                timeout=10,
            )
            existing_pk = None
            if r.status_code == 200:
                for item in r.json().get("results", []):
                    if item.get("client_id") == client_id:
                        existing_pk = item["pk"]
                        break

            if existing_pk:
                r2 = self._http.patch(
                    f"{self._base}/api/v3/providers/oauth2/{existing_pk}/",
                    headers=self._headers,
                    json={"client_secret": payload.value},
                    timeout=10,
                )
                if r2.status_code == 200:
                    AK_STORE_SUCCESS.inc()
                    return True, client_id, None
                AK_STORE_FAILURE.inc()
                return False, client_id, f"patch_error:{r2.status_code}"

            flow_pk = self._get_auth_flow_pk()
            if not flow_pk:
                AK_STORE_FAILURE.inc()
                return False, client_id, "authorization_flow_not_found"

            data: dict = {
                "name": f"secret-holder:{payload.name}#{payload.field}",
                "authorization_flow": flow_pk,
                "client_type": "confidential",
                "client_id": client_id,
                "client_secret": payload.value,
                "redirect_uris": [
                    {"matching_mode": "strict", "url": "https://placeholder.local/secret-holder"}
                ],
                "sub_mode": "hashed_user_id",
                "issuer_mode": "per_provider",
                "include_claims_in_id_token": False,
            }
            inv_flow = self._get_invalidation_flow_pk()
            if inv_flow:
                data["invalidation_flow"] = inv_flow
            r3 = self._http.post(
                f"{self._base}/api/v3/providers/oauth2/",
                headers=self._headers,
                json=data,
                timeout=15,
            )
            if r3.status_code == 201:
                AK_STORE_SUCCESS.inc()
                return True, client_id, None
            AK_STORE_FAILURE.inc()
            return False, client_id, f"create_error:{r3.status_code}:{r3.text[:150]}"
        except Exception as exc:
            AK_STORE_FAILURE.inc()
            return False, client_id, f"exception:{exc}"

    # ── Remoção ──────────────────────────────────────────────

    def delete_secret(self, name: str, field: str = "password") -> tuple[bool, Optional[str]]:
        """Remove secret do Authentik."""
        client_id = self._client_id(name, field)
        try:
            r = self._http.get(
                f"{self._base}/api/v3/providers/oauth2/",
                headers=self._headers,
                params={"search": client_id, "page_size": 10},
                timeout=10,
            )
            if r.status_code != 200:
                return False, "not_found"
            for item in r.json().get("results", []):
                if item.get("client_id") == client_id:
                    pk = item["pk"]
                    del_r = self._http.delete(
                        f"{self._base}/api/v3/providers/oauth2/{pk}/",
                        headers=self._headers,
                        timeout=10,
                    )
                    if del_r.status_code == 204:
                        return True, None
                    return False, f"delete_error:{del_r.status_code}"
            return False, "not_found"
        except Exception as exc:
            return False, f"exception:{exc}"

    # ── Listagem ─────────────────────────────────────────────

    def list_items(self) -> list[dict]:
        """Lista todos os secrets armazenados no Authentik (client_id com prefixo 'secret-')."""
        try:
            r = self._http.get(
                f"{self._base}/api/v3/providers/oauth2/",
                headers=self._headers,
                params={"page_size": 500},
                timeout=15,
            )
            if r.status_code != 200:
                return []
            items = []
            for item in r.json().get("results", []):
                cid = item.get("client_id", "")
                if cid.startswith("secret-"):
                    items.append({
                        "id": cid,
                        "title": item.get("name", cid),
                        "source": "authentik",
                    })
            SECRETS_COUNT.set(len(items))
            return items
        except Exception as exc:
            logger.warning("Authentik list_items erro: %s", exc)
            return []

    def get_info(self, non_blocking: bool = False) -> dict:
        """Informações de diagnóstico do backend Authentik."""
        available = self._available if non_blocking else self.is_available()
        return {
            "authentik_status": "available" if available else "unavailable",
            "authentik_url": self._base,
            "token_configured": bool(self._token),
        }


# Singleton global
ak_manager = AuthentikSecretManager()


# ═══════════════════════════════════════════════════════════════
#  LocalVault — fallback criptografado quando Authentik indisponível
# ═══════════════════════════════════════════════════════════════

LOCAL_VAULT_DIR = APP_DIR / "local_vault"
LOCAL_VAULT_DIR.mkdir(parents=True, exist_ok=True)
LOCAL_VAULT_PASSFILE = APP_DIR / "simple_vault_passphrase"

LOCAL_SECRETS_COUNT = Gauge(
    "secrets_agent_local_secrets_count", "Number of secrets in local vault"
)


class LocalVault:
    """Vault local criptografado com HMAC-SHA256 para fallback sem Authentik.

    Armazena secrets como arquivos JSON assinados em local_vault/.
    Usa passphrase do arquivo simple_vault_passphrase como chave.
    """

    def __init__(self, vault_dir: Path, passfile: Path) -> None:
        self._dir = vault_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._passfile = passfile
        self._key: Optional[bytes] = None

    def _get_key(self) -> bytes:
        if self._key:
            return self._key
        if not self._passfile.exists():
            passphrase = _secrets_mod.token_hex(32)
            self._passfile.write_text(passphrase)
            self._passfile.chmod(0o600)
            logger.info("Nova passphrase gerada em %s", self._passfile)
        raw = self._passfile.read_text().strip()
        self._key = hashlib.sha256(raw.encode()).digest()
        return self._key

    def _safe_filename(self, name: str, field: str) -> str:
        tag = hashlib.sha256(f"{name}:{field}".encode()).hexdigest()[:16]
        return f"{tag}.json"

    def _sign(self, data: bytes) -> str:
        return hmac.new(self._get_key(), data, hashlib.sha256).hexdigest()

    def _xor_crypt(self, data: bytes) -> bytes:
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
            logger.info("Local vault: stored '%s' field='%s'", name, field)
            self._update_metric()
            return True
        except Exception as exc:
            logger.error("Local vault store error: %s", exc)
            return False

    def get(self, name: str, field: str = "password") -> Optional[str]:
        fpath = self._dir / self._safe_filename(name, field)
        if not fpath.exists():
            return None
        try:
            envelope = json.loads(fpath.read_text())
            data_str = envelope["data"]
            sig = envelope["sig"]
            if not hmac.compare_digest(self._sign(data_str.encode()), sig):
                logger.error("Local vault: HMAC mismatch for '%s'", name)
                return None
            payload = json.loads(data_str)
            encrypted = base64.b64decode(payload["value"])
            return self._xor_crypt(encrypted).decode()
        except Exception as exc:
            logger.error("Local vault get error: %s", exc)
            return None

    def delete(self, name: str, field: str = "password") -> bool:
        fpath = self._dir / self._safe_filename(name, field)
        if fpath.exists():
            fpath.unlink()
            logger.info("Local vault: deleted '%s' field='%s'", name, field)
            self._update_metric()
            return True
        return False

    def list_all(self) -> list[dict]:
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
        count = len(list(self._dir.glob("*.json")))
        LOCAL_SECRETS_COUNT.set(count)


local_vault = LocalVault(LOCAL_VAULT_DIR, LOCAL_VAULT_PASSFILE)


# ═══════════════════════════════════════════════════════════════
#  FastAPI App
# ═══════════════════════════════════════════════════════════════

app = FastAPI(title="Secrets Agent", version="3.0.0")


class SecretPayload(BaseModel):
    name: str
    value: str
    field: str = "password"
    notes: Optional[str] = None


@app.on_event("startup")
def startup_event() -> None:
    """Testa conexão com Authentik em background (não bloqueia startup)."""
    init_db()
    logger.info("Secrets Agent v3.0 iniciando — backend: Authentik...")

    def _bg_probe() -> None:
        try:
            ok = ak_manager.is_available(force=True)
            info = ak_manager.get_info()
            if ok:
                logger.info("Authentik disponível: %s", info["authentik_url"])
            else:
                logger.warning(
                    "Authentik indisponível: url=%s, token=%s. "
                    "Operações de read/write usarão LocalVault como fallback.",
                    info["authentik_url"],
                    "configurado" if info["token_configured"] else "NÃO configurado",
                )
        except Exception as exc:
            logger.error("Erro ao verificar Authentik: %s", exc)

    thread = threading.Thread(target=_bg_probe, daemon=True, name="authentik-probe")
    thread.start()


def init_db() -> None:
    """Compatibilidade retroativa."""
    return None


def audit_log(ip: str, action: str, secret_id: str, result: str) -> None:
    ts = int(time.time())
    AUDIT_EVENTS.append((ts, ip, action, secret_id, result))


def check_rate(ip: str) -> int:
    now = time.time()
    times = FAILED_IP.get(ip, [])
    times = [t for t in times if now - t <= FAIL_WINDOW]
    FAILED_IP[ip] = times
    return len(times)


def parse_local_ref(item_id: str, default_field: str = "password") -> tuple[str, str]:
    """Converte `local:<name>:<field>` para (name, field)."""
    parts = item_id.split(":", 2)
    name = parts[1] if len(parts) > 1 else item_id
    field = parts[2] if len(parts) > 2 else default_field
    return name, field


# ─── Endpoints ────────────────────────────────────────────────

@app.get("/metrics")
def metrics():
    return JSONResponse(content=generate_latest().decode(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
def health():
    info = ak_manager.get_info(non_blocking=True)
    return {
        "status": "ok",
        "backend_status": info["authentik_status"],
        "backend": "authentik",
    }


@app.get("/bw/status")
def bw_status_endpoint():
    """Diagnóstico do backend (mantido para compatibilidade com consumidores legados)."""
    return ak_manager.get_info()


@app.post("/bw/unlock")
def bw_unlock_endpoint(request: Request):
    """Testa conexão com o backend Authentik (mantido para compatibilidade)."""
    key = request.headers.get("x-api-key", "")
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="unauthorized")
    ok = ak_manager.is_available(force=True)
    return {
        "success": ok,
        "info": ak_manager.get_info(),
    }


@app.get("/authentik/status")
def authentik_status_endpoint():
    """Diagnóstico da conexão com o Authentik."""
    return ak_manager.get_info()


@app.get("/secrets")
def list_secrets():
    """Lista secrets disponíveis — Authentik + local vault."""
    ak_info = ak_manager.get_info(non_blocking=True)
    ak_items = ak_manager.list_items() if ak_info["authentik_status"] == "available" else []
    local_items = local_vault.list_all()
    all_items = ak_items + local_items
    SECRETS_COUNT.set(len(all_items))
    return {
        "count": len(all_items),
        "items": all_items,
        "backend_status": ak_info["authentik_status"],
    }


@app.post("/secrets")
def store_secret(request: Request, payload: SecretPayload):
    """Armazena secret — tenta Authentik, sempre espelha no LocalVault."""
    ip = request.client.host
    key = request.headers.get("x-api-key", "")
    if key != API_KEY:
        ACCESS_FAILURE.inc()
        audit_log(ip, "store", payload.name, "denied")
        raise HTTPException(status_code=401, detail="unauthorized")

    ak_ok, ak_item_id, ak_err = ak_manager.upsert_secret(payload)
    local_ok = local_vault.store(payload.name, payload.value, payload.field, payload.notes)

    if not ak_ok and not local_ok:
        ACCESS_FAILURE.inc()
        audit_log(ip, "store", payload.name, f"all_backends_failed:{ak_err}")
        raise HTTPException(status_code=503, detail=f"all backends failed: {ak_err}")

    if not ak_ok:
        logger.warning("Authentik store falhou para %s#%s: %s (LocalVault OK)", payload.name, payload.field, ak_err)

    ACCESS_SUCCESS.inc()
    audit_log(ip, "store", payload.name, "ok")
    return {
        "status": "stored",
        "name": payload.name,
        "field": payload.field,
        "backend_sync": {
            "source": "authentik",
            "ok": ak_ok,
            "item_id": ak_item_id if ak_ok else None,
            "error": ak_err,
        },
        "local_vault": local_ok,
    }


@app.get("/secrets/local/{name:path}")
def get_local_secret(request: Request, name: str, field: str = "password"):
    """Recupera secret do LocalVault (acesso local, sem rede)."""
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
    """Remove secret do Authentik e do LocalVault."""
    ip = request.client.host
    key = request.headers.get("x-api-key", "")
    if key != API_KEY:
        ACCESS_FAILURE.inc()
        audit_log(ip, "delete_local", name, "denied")
        raise HTTPException(status_code=401, detail="unauthorized")

    ak_ok, ak_err = ak_manager.delete_secret(name, field)
    local_ok = local_vault.delete(name, field)

    if not ak_ok and not local_ok:
        if ak_err == "not_found":
            raise HTTPException(status_code=404, detail="not found")
        raise HTTPException(status_code=503, detail=f"delete failed: {ak_err}")

    audit_log(ip, "delete_local", name, "ok")
    return {"status": "deleted", "name": name, "field": field}


@app.get("/secrets/{item_id:path}")
def get_secret(request: Request, item_id: str, field: str = "password"):
    """Busca secret por nome — Authentik primeiro, fallback LocalVault."""
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
        value = ak_manager.get_secret(name, local_field)
        if value is None:
            value = local_vault.get(name, local_field)
        if value is None:
            ACCESS_FAILURE.inc()
            audit_log(ip, "fetch", item_id, "not_found")
            raise HTTPException(status_code=404, detail="secret not found")
        ACCESS_SUCCESS.inc()
        audit_log(ip, "fetch", item_id, "ok")
        return {"id": item_id, "value": value}

    # 1. Tenta Authentik — field exato
    value = ak_manager.get_secret(item_id, field)
    if value is not None:
        ACCESS_SUCCESS.inc()
        audit_log(ip, "fetch", item_id, "ok")
        return {"id": item_id, "value": value, "source": "authentik"}

    # 2. Tenta Authentik — todos os fields (secrets com múltiplos campos)
    fields = ak_manager.get_secret_fields(item_id)
    if fields:
        ACCESS_SUCCESS.inc()
        audit_log(ip, "fetch", item_id, "ok")
        return {"id": item_id, "fields": fields, "source": "authentik"}

    # 3. Fallback: LocalVault
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


if __name__ == "__main__":
    prometheus_port = int(os.environ.get("SECRETS_AGENT_PROM_PORT", "8001"))
    start_http_server(prometheus_port)
    import uvicorn

    port = int(os.environ.get("SECRETS_AGENT_PORT", "8088"))
    logger.info("Secrets Agent v3.0 — porta %d, métricas em %d", port, prometheus_port)
    uvicorn.run(app, host="0.0.0.0", port=port)
