#!/usr/bin/env python3
"""Integra o TrueNAS SCALE NAS com o Authentik via LDAP Outpost."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# ── Endpoints ──────────────────────────────────────────────────────────────
AUTHENTIK_URL = os.environ.get("AUTHENTIK_URL", "http://192.168.15.2:9000").rstrip("/")
NAS_URL = os.environ.get("NAS_URL", "http://192.168.15.4").rstrip("/")
SECRETS_AGENT_URL = os.environ.get("SECRETS_AGENT_URL", "http://192.168.15.2:8088")

# ── LDAP Provider e Outpost ────────────────────────────────────────────────
LDAP_PROVIDER_NAME = os.environ.get("AUTHENTIK_NAS_LDAP_PROVIDER_NAME", "RPA4ALL LDAP Provider v2")
LDAP_BASE_DN = os.environ.get("AUTHENTIK_LDAP_BASE_DN", "DC=ldap,DC=goauthentik,DC=io")
LDAP_OUTPOST_NAME = os.environ.get("AUTHENTIK_LDAP_OUTPOST_NAME", "RPA4ALL LDAP Outpost v2")
LDAP_OUTPOST_CONTAINER = os.environ.get("AUTHENTIK_LDAP_OUTPOST_CONTAINER", "authentik-ldap-outpost")
LDAP_SERVER_HOST = os.environ.get("AUTHENTIK_LDAP_HOST", "192.168.15.2")
LDAP_SERVER_PORT = int(os.environ.get("AUTHENTIK_LDAP_PORT", "389"))
LDAP_BIND_USER = os.environ.get("AUTHENTIK_NAS_LDAP_BIND_USER", "ldapservice")
LDAP_BIND_TOKEN_ID = os.environ.get("AUTHENTIK_NAS_LDAP_BIND_TOKEN_ID", "ldapservice-app-pass-20260324")
AUTHENTIK_WORKER_CONTAINER = os.environ.get("AUTHENTIK_WORKER_CONTAINER", "authentik-worker")


# ── Secrets Agent ──────────────────────────────────────────────────────────

def _get_secret(name: str, field: str = "password") -> str:
    """Lê um segredo do Secrets Agent local."""
    api_key = os.environ.get("SECRETS_AGENT_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "SECRETS_AGENT_API_KEY não configurada. "
            "Exporte via: export SECRETS_AGENT_API_KEY=$(cat ~/.config/homelab/secrets.env | grep SECRETS_AGENT_API_KEY | cut -d= -f2)"
        )
    url = f"{SECRETS_AGENT_URL}/secrets/{name}?field={field}"
    req = urllib.request.Request(url, headers={"x-api-key": api_key})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
            return data["value"]
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Secrets agent HTTP {exc.code} para '{name}': {exc.read().decode()[:200]}") from exc
    except (KeyError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Resposta inesperada do secrets agent para '{name}': {exc}") from exc


def _set_secret(name: str, value: str, field: str = "password") -> None:
    """Grava ou atualiza um segredo no Secrets Agent local."""
    api_key = os.environ.get("SECRETS_AGENT_API_KEY", "")
    if not api_key:
        return
    url = f"{SECRETS_AGENT_URL}/secrets"
    body = json.dumps({"name": name, "value": value, "field": field}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except urllib.error.HTTPError:
        pass  # falha silenciosa — não interrompe o fluxo principal


def _authentik_token() -> str:
    """Retorna o token da API do Authentik."""
    if tok := os.environ.get("AUTHENTIK_TOKEN"):
        return tok
    return _get_secret("authentik/api_token")


def _nas_api_key() -> str:
    """Retorna a API key do TrueNAS."""
    if key := os.environ.get("NAS_API_KEY"):
        return key
    return _get_secret("nas-optiplex", field="api_key")


# ── Authentik API ──────────────────────────────────────────────────────────

def _ak_request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{AUTHENTIK_URL}/api/v3{path}"
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {
        "Authorization": f"Bearer {_authentik_token()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            text = r.read().decode()
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"Authentik HTTP {exc.code} em {path}: {detail[:400]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Não conseguiu conectar no Authentik ({AUTHENTIK_URL}): {exc}") from exc


# ── TrueNAS API ────────────────────────────────────────────────────────────

def _nas_request(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    url = f"{NAS_URL}/api/v2.0{path}"
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {
        "Authorization": f"Bearer {_nas_api_key()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            text = r.read().decode()
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"TrueNAS HTTP {exc.code} em {path}: {detail[:400]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Não conseguiu conectar no NAS ({NAS_URL}): {exc}") from exc


# ── LDAP Provider ──────────────────────────────────────────────────────────

def get_ldap_provider_pk() -> str:
    """Retorna o pk do LDAP provider existente pelo nome."""
    qs = urllib.parse.urlencode({"search": LDAP_PROVIDER_NAME})
    result = _ak_request("GET", f"/providers/ldap/?{qs}")
    for item in result.get("results", []):
        if item.get("name") == LDAP_PROVIDER_NAME:
            return str(item["pk"])
    raise RuntimeError(
        f"LDAP Provider '{LDAP_PROVIDER_NAME}' não encontrado no Authentik. "
        "Verifique AUTHENTIK_NAS_LDAP_PROVIDER_NAME."
    )


# ── LDAP Outpost ───────────────────────────────────────────────────────────

def get_ldap_outpost() -> dict[str, Any]:
    """Retorna o objeto do LDAP outpost existente pelo nome."""
    qs = urllib.parse.urlencode({"search": LDAP_OUTPOST_NAME})
    result = _ak_request("GET", f"/outposts/instances/?{qs}")
    for item in result.get("results", []):
        if item.get("name") == LDAP_OUTPOST_NAME:
            return item
    raise RuntimeError(
        f"LDAP Outpost '{LDAP_OUTPOST_NAME}' não encontrado. "
        "Verifique AUTHENTIK_LDAP_OUTPOST_NAME."
    )


def ensure_outpost_has_provider(outpost: dict[str, Any], provider_pk: str) -> bool:
    """Associa o provider ao outpost se ainda não estiver. Retorna True se atualizou."""
    providers = outpost.get("providers", [])
    if int(provider_pk) in providers:
        return False
    _ak_request(
        "PATCH",
        f"/outposts/instances/{outpost['pk']}/",
        {"providers": list(providers) + [int(provider_pk)]},
    )
    return True


def start_ldap_outpost_container(*, dry_run: bool = True) -> str:
    """Inicia o container Docker do LDAP outpost se estiver parado."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Status}}", LDAP_OUTPOST_CONTAINER],
            capture_output=True,
            text=True,
            timeout=10,
        )
        status = result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "docker indisponível neste host"

    if status == "running":
        return "running"
    if dry_run:
        return f"parado ({status}) — use --apply para iniciar"
    subprocess.run(["docker", "start", LDAP_OUTPOST_CONTAINER], check=True, timeout=30)
    return "iniciado"


# ── Token de bind para NAS ─────────────────────────────────────────────────

def _get_token_key_via_django(identifier: str) -> str:
    """Obtém a key de um token do Authentik via Django shell (requer Docker local)."""
    cmd = (
        f"from authentik.core.models import Token; "
        f"print(Token.objects.get(identifier='{identifier}').key)"
    )
    result = subprocess.run(
        ["docker", "exec", AUTHENTIK_WORKER_CONTAINER, "ak", "shell", "-c", cmd],
        capture_output=True,
        text=True,
        timeout=30,
    )
    key = result.stdout.strip()
    if result.returncode != 0 or not key:
        raise RuntimeError(f"Django shell falhou para token '{identifier}': {result.stderr[:200]}")
    return key


def _ldapservice_user_pk() -> int:
    qs = urllib.parse.urlencode({"search": LDAP_BIND_USER})
    result = _ak_request("GET", f"/core/users/?{qs}")
    for item in result.get("results", []):
        if item.get("username") == LDAP_BIND_USER:
            return int(item["pk"])
    raise RuntimeError(f"Usuário '{LDAP_BIND_USER}' não encontrado no Authentik.")


def ensure_nas_ldap_bind_token(*, dry_run: bool = True) -> str:
    """
    Garante que existe um token de bind dedicado para o NAS.
    Retorna a key (senha LDAP) usada no TrueNAS.

    Ordem de precedência:
      1. Env var AUTHENTIK_NAS_LDAP_BIND_PASSWORD
      2. Secret agent: eddie/nas-ldap-bind-password
      3. Authentik API view_key do token existente
      4. Criar novo token (somente com --apply)
    """
    # 1. Env var explícita
    if bind_pw := os.environ.get("AUTHENTIK_NAS_LDAP_BIND_PASSWORD"):
        return bind_pw

    # 2. Secrets agent (confia apenas se Django shell confirmar — evita cache stale)
    try:
        cached = _get_secret("eddie/nas-ldap-bind-password")
        # Verifica se o valor bate com a key real do token no Authentik
        try:
            actual = _get_token_key_via_django(LDAP_BIND_TOKEN_ID)
            if actual == cached:
                return cached
            # Cache desatualizado — corrigir
            _set_secret("eddie/nas-ldap-bind-password", actual)
            return actual
        except RuntimeError:
            # Docker indisponível neste host — confiar no cache
            return cached
    except RuntimeError:
        pass

    # 3. Token já existente no Authentik — tentar view_key via API
    qs = urllib.parse.urlencode({"identifier": LDAP_BIND_TOKEN_ID})
    result = _ak_request("GET", f"/core/tokens/?{qs}")
    token_exists = any(
        item.get("identifier") == LDAP_BIND_TOKEN_ID for item in result.get("results", [])
    )
    if token_exists:
        try:
            key_resp = _ak_request("POST", f"/core/tokens/{LDAP_BIND_TOKEN_ID}/view_key/")
            if (key := key_resp.get("key", "")) and key not in ("", "***", "N/A"):
                return key
        except RuntimeError:
            pass

        # 3b. view_key sem permissão — tentar via Django shell (disponível no homelab)
        try:
            key = _get_token_key_via_django(LDAP_BIND_TOKEN_ID)
            _set_secret("eddie/nas-ldap-bind-password", key)
            return key
        except RuntimeError:
            pass

        raise RuntimeError(
            f"Token '{LDAP_BIND_TOKEN_ID}' existe mas não foi possível obter a key. "
            "Defina AUTHENTIK_NAS_LDAP_BIND_PASSWORD ou armazene no secrets agent como "
            "'eddie/nas-ldap-bind-password'."
        )

    # 4. Criar novo token
    if dry_run:
        return f"<será gerado ao executar --apply>"

    import secrets as _secrets
    new_key = _secrets.token_urlsafe(32)
    user_pk = _ldapservice_user_pk()
    _ak_request("POST", "/core/tokens/", {
        "identifier": LDAP_BIND_TOKEN_ID,
        "intent": "app_password",
        "user": user_pk,
        "expiring": False,
        "key": new_key,
    })
    # Persistir no secrets agent para recuperação futura
    _set_secret("eddie/nas-ldap-bind-password", new_key)
    return new_key


# ── TrueNAS LDAP ───────────────────────────────────────────────────────────

def _wait_nas_job(job_id: int, timeout: int = 60) -> None:
    """Aguarda um job assíncrono do TrueNAS completar."""
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = _nas_request("GET", f"/core/get_jobs?id={job_id}")
        if isinstance(job, list) and job:
            state = job[0].get("state", "")
            if state == "SUCCESS":
                return
            if state in ("FAILED", "ABORTED"):
                error = job[0].get("error", "desconhecido")
                raise RuntimeError(f"TrueNAS job {job_id} falhou: {error}")
        time.sleep(2)
    raise RuntimeError(f"Timeout aguardando job TrueNAS {job_id}")


def build_nas_ldap_payload(bind_password: str) -> dict[str, Any]:
    return {
        "hostname": [LDAP_SERVER_HOST],
        "basedn": LDAP_BASE_DN,
        "binddn": f"CN={LDAP_BIND_USER},OU=users,{LDAP_BASE_DN}",
        "bindpw": bind_password,
        "anonbind": False,
        "ssl": "OFF",
        "validate_certificates": False,
        "disable_freenas_cache": False,
        "timeout": 30,
        "dns_timeout": 5,
        "schema": "RFC2307",
        "enable": True,
        "search_bases": {},
        "attribute_maps": {},
    }


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Integra TrueNAS SCALE com Authentik via LDAP Outpost."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica as configurações no TrueNAS e inicia o LDAP outpost (default: dry-run)",
    )
    parser.add_argument(
        "--skip-nas",
        action="store_true",
        help="Apenas verifica o Authentik, não toca no TrueNAS",
    )
    args = parser.parse_args()
    dry_run = not args.apply

    report: dict[str, Any] = {}

    print("=== [1] Verificando LDAP Provider no Authentik ===")
    provider_pk = get_ldap_provider_pk()
    print(f"  Provider: {LDAP_PROVIDER_NAME} (pk={provider_pk})")
    report["authentik_ldap_provider_pk"] = provider_pk

    print("\n=== [2] Verificando LDAP Outpost no Authentik ===")
    outpost = get_ldap_outpost()
    outpost_pk = str(outpost["pk"])
    print(f"  Outpost: {LDAP_OUTPOST_NAME} (pk={outpost_pk})")
    updated = ensure_outpost_has_provider(outpost, provider_pk)
    print(f"  Provider associado: {'adicionado agora' if updated else 'já existia'}")
    report["authentik_ldap_outpost_pk"] = outpost_pk

    print("\n=== [3] Verificando container LDAP Outpost ===")
    container_status = start_ldap_outpost_container(dry_run=dry_run)
    print(f"  Container '{LDAP_OUTPOST_CONTAINER}': {container_status}")
    report["ldap_outpost_container_status"] = container_status

    print("\n=== [4] Resolvendo token de bind LDAP ===")
    bind_password = ensure_nas_ldap_bind_token(dry_run=dry_run)
    bind_dn = f"CN={LDAP_BIND_USER},OU=users,{LDAP_BASE_DN}"
    print(f"  Bind DN: {bind_dn}")
    print(f"  Token ID: {LDAP_BIND_TOKEN_ID}")
    report["ldap_bind_dn"] = bind_dn
    report["ldap_bind_token_id"] = LDAP_BIND_TOKEN_ID

    if not args.skip_nas:
        print(f"\n=== [5] {'Aplicando' if args.apply else 'Simulando'} LDAP no TrueNAS ===")
        ldap_payload = build_nas_ldap_payload(bind_password)

        if dry_run:
            display = {**ldap_payload, "bindpw": "***"}
            print(json.dumps(display, indent=4, ensure_ascii=False))
            report["nas_ldap_config_dry_run"] = display
        else:
            result = _nas_request("PUT", "/ldap", ldap_payload)
            # TrueNAS SCALE 24.10 pode retornar um job ID (int) para ops assíncronas
            if isinstance(result, int):
                _wait_nas_job(result)
                result = _nas_request("GET", "/ldap")
            print(f"  enable={result.get('enable')}, hostname={result.get('hostname')}")
            report["nas_ldap_enabled"] = result.get("enable")
            report["nas_ldap_hostname"] = result.get("hostname")

    report.update({
        "status": "ok" if args.apply else "dry-run",
        "ldap_server": f"{LDAP_SERVER_HOST}:{LDAP_SERVER_PORT}",
        "base_dn": LDAP_BASE_DN,
        "nas_url": NAS_URL,
    })

    print("\n=== Resultado ===")
    print(json.dumps(report, indent=2, ensure_ascii=False))

    if dry_run:
        print("\n[!] Modo dry-run. Execute com --apply para aplicar as mudanças.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
