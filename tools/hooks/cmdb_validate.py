"""PreToolUse hook — valida que componentes de infra referenciados existem no CMDB NetBox.

Bloqueia comandos e edições que mencionam IPs 192.168.15.x ou hostnames de infra
não cadastrados no NetBox (http://192.168.15.2:18091/cmdb/netbox/).

Token: variável de ambiente NETBOX_API_TOKEN. Sem token → warn, não bloqueia.
Cache: /tmp/cmdb_ip_cache.json (TTL 5 min) para não sobrecarregar o NetBox.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

NETBOX_URL = "http://192.168.15.2:18091/cmdb/netbox/api"
CACHE_FILE = Path("/tmp/cmdb_validate_cache.json")
CACHE_TTL = 300  # 5 minutos
SECRETS_AGENT_URL = "http://192.168.15.2:8088"
_TOKEN_CACHE: dict[str, Any] = {}

# IPs próprios do homelab — nunca precisam de check (são o servidor que serve o NetBox)
SKIP_IPS: frozenset[str] = frozenset({
    "192.168.15.1",   # ZTE GPON gateway
    "192.168.15.2",   # homelab eth-onboard
    "192.168.15.3",   # homelab eth-wan
})

# Hostnames canônicos de infra → mapeamento para verificação no NetBox
# Apenas hostnames explícitos em contexto de infra são checados
INFRA_HOSTNAME_RE = re.compile(
    r"\b(homelab|nas|storj-host0|pihole|pi\.hole|chromecast|tank3-pro|edenilson|"
    r"openwebui|nextcloud|authentik|wikijs|prometheus|grafana)\b",
    re.IGNORECASE,
)

# Padrão de IPs da rede local do homelab
LAN_IP_RE = re.compile(r"\b192\.168\.15\.(\d{1,3})\b")

# Contextos onde hostnames são relevantes para checar (evita falsos positivos em comentários)
INFRA_CONTEXT_RE = re.compile(
    r"\b(ssh|scp|ping|curl|wget|nmap|nc|ansible|systemctl|docker|kubectl|"
    r"deploy|connect|host|target|server|address|endpoint|gateway|remote)\b",
    re.IGNORECASE,
)


def _load_local_secrets() -> dict[str, str]:
    """Lê ~/.config/homelab/secrets.env (fora do git) para chaves de serviço locais."""
    env_file = Path.home() / ".config" / "homelab" / "secrets.env"
    if not env_file.exists():
        return {}
    result: dict[str, str] = {}
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            result[k.strip()] = v.strip()
    return result


def _fetch_token_from_secrets_agent() -> str | None:
    """Busca token NetBox do secrets agent (Authentik). Cache em memória por 5 min."""
    api_key = (
        os.environ.get("SECRETS_AGENT_API_KEY")
        or _load_local_secrets().get("SECRETS_AGENT_API_KEY")
    )
    if not api_key:
        return None
    now = time.time()
    if _TOKEN_CACHE.get("token") and now - _TOKEN_CACHE.get("ts", 0) < CACHE_TTL:
        return _TOKEN_CACHE["token"]
    try:
        req = urllib.request.Request(
            f"{SECRETS_AGENT_URL}/secrets/eddie/netbox_api_token?field=token",
            headers={"Accept": "application/json", "x-api-key": api_key},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            token = data.get("value")
            if token:
                _TOKEN_CACHE["token"] = token
                _TOKEN_CACHE["ts"] = now
                return token
    except Exception:
        pass
    return None


def _provision_new_token() -> str | None:
    """Se o token atual retorna 403, busca credenciais do superuser no secrets agent,
    provisiona novo token no NetBox e armazena de volta no secrets agent."""
    api_key = (
        os.environ.get("SECRETS_AGENT_API_KEY")
        or _load_local_secrets().get("SECRETS_AGENT_API_KEY")
    )
    if not api_key:
        return None

    # 1. Buscar username e password do superuser no secrets agent (campos separados)
    try:
        hdrs = {"Accept": "application/json", "x-api-key": api_key}
        req_u = urllib.request.Request(
            f"{SECRETS_AGENT_URL}/secrets/eddie/netbox_superuser?field=username",
            headers=hdrs,
        )
        with urllib.request.urlopen(req_u, timeout=3) as r:
            username = json.loads(r.read()).get("value")
        req_p = urllib.request.Request(
            f"{SECRETS_AGENT_URL}/secrets/eddie/netbox_superuser?field=password",
            headers=hdrs,
        )
        with urllib.request.urlopen(req_p, timeout=3) as r:
            password = json.loads(r.read()).get("value")
        if not username or not password:
            return None
    except Exception:
        return None

    # 2. Provisionar novo token no NetBox
    try:
        body = json.dumps({"username": username, "password": password}).encode()
        req = urllib.request.Request(
            f"{NETBOX_URL}/users/tokens/provision/",
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        new_token = data.get("token") or data.get("key")  # "token" é o campo de 40 chars
        if not new_token:
            return None
    except Exception:
        return None

    # 3. Armazenar novo token no secrets agent
    try:
        body = json.dumps({
            "name": "eddie/netbox_api_token",
            "value": new_token,
            "field": "token",
            "notes": f"auto-provisioned by cmdb_validate.py at {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
        }).encode()
        req = urllib.request.Request(
            f"{SECRETS_AGENT_URL}/secrets",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "x-api-key": api_key,
            },
            method="POST",
        )
        urllib.request.urlopen(req, timeout=3).close()
    except Exception:
        pass  # falha ao armazenar não impede o uso do token agora

    # 4. Atualizar cache em memória
    _TOKEN_CACHE["token"] = new_token
    _TOKEN_CACHE["ts"] = time.time()
    return new_token


def _get_token() -> str | None:
    # 1. secrets agent (Authentik) — fonte canônica, sempre consultado primeiro
    t = _fetch_token_from_secrets_agent()
    if t:
        return t
    # 2. env var fallback (override manual ou debug local)
    return os.environ.get("NETBOX_API_TOKEN") or os.environ.get("NETBOX_TOKEN")


def _load_cache() -> dict[str, Any]:
    try:
        if CACHE_FILE.exists():
            data = json.loads(CACHE_FILE.read_text())
            if time.time() - data.get("_ts", 0) < CACHE_TTL:
                return data
    except Exception:
        pass
    return {}


def _save_cache(cache: dict[str, Any]) -> None:
    try:
        cache["_ts"] = time.time()
        CACHE_FILE.write_text(json.dumps(cache))
    except Exception:
        pass


def _netbox_get(path: str, token: str) -> dict[str, Any]:
    url = f"{NETBOX_URL}{path}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Token {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise PermissionError("NetBox: token inválido ou sem permissão")
        return {"count": -1}  # erro de HTTP inesperado → fail-open
    except Exception:
        return {"count": -1}  # NetBox indisponível → fail-open


def _ip_exists(ip: str, token: str) -> bool | None:
    """True=existe, False=não existe, None=erro (fail-open)."""
    data = _netbox_get(f"/ipam/ip-addresses/?address={ip}&limit=1", token)
    count = data.get("count", -1)
    if count == -1:
        return None  # falha na consulta → não bloqueia
    return count > 0


def _device_or_vm_exists(name: str, token: str) -> bool | None:
    """Verifica em devices e VMs. True=existe, False=não existe, None=erro."""
    for endpoint in ("/dcim/devices/", "/virtualization/virtual-machines/"):
        data = _netbox_get(f"{endpoint}?name={name}&limit=1", token)
        count = data.get("count", -1)
        if count == -1:
            return None
        if count > 0:
            return True
    return False


def _get_blob(payload: dict[str, Any]) -> str:
    """Extrai texto relevante do payload da tool call para análise."""
    tool_input = payload.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return str(tool_input)
    parts: list[str] = []
    for key in ("command", "cmd", "file_path", "new_string", "content", "old_string"):
        v = tool_input.get(key, "")
        if isinstance(v, str) and v:
            parts.append(v)
    return "\n".join(parts)


def _extract_ips(blob: str) -> set[str]:
    found = set()
    for m in LAN_IP_RE.finditer(blob):
        ip = m.group(0)
        if ip not in SKIP_IPS:
            found.add(ip)
    return found


def _extract_hostnames(blob: str) -> set[str]:
    """Extrai hostnames apenas quando há contexto de operação de infra."""
    if not INFRA_CONTEXT_RE.search(blob):
        return set()
    return {m.group(1).lower() for m in INFRA_HOSTNAME_RE.finditer(blob)}


def _deny(reason: str, context: str) -> str:
    return json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
            "additionalContext": context,
        }
    })


def _warn(context: str) -> str:
    return json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": context,
        }
    })


def main() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        return 0

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return 0

    blob = _get_blob(payload)
    if not blob:
        return 0

    ips = _extract_ips(blob)
    hostnames = _extract_hostnames(blob)

    if not ips and not hostnames:
        return 0

    token = _get_token()
    if not token:
        # Sem token: avisa mas não bloqueia
        targets = sorted(ips) + sorted(hostnames)
        print(_warn(
            f"⚠️ CMDB: componentes de infra detectados {targets} mas NETBOX_API_TOKEN não configurado — "
            "validação ignorada. Configure: settings.json → env.NETBOX_API_TOKEN ou "
            "export NETBOX_API_TOKEN=<token> (obtido em http://192.168.15.2:18091/cmdb/netbox/users/tokens/)."
        ))
        return 0

    cache = _load_cache()
    not_found_ips: list[str] = []
    not_found_hosts: list[str] = []

    def _run_checks(tok: str) -> None:
        # --- Validar IPs ---
        for ip in sorted(ips):
            cache_key = f"ip:{ip}"
            if cache_key in cache:
                exists = cache[cache_key]
            else:
                result = _ip_exists(ip, tok)
                exists = result if result is not None else True  # fail-open em erro
                cache[cache_key] = exists
            if not exists:
                not_found_ips.append(ip)

        # --- Validar Hostnames ---
        for host in sorted(hostnames):
            cache_key = f"host:{host}"
            if cache_key in cache:
                exists = cache[cache_key]
            else:
                result = _device_or_vm_exists(host, tok)
                exists = result if result is not None else True  # fail-open em erro
                cache[cache_key] = exists
            if not exists:
                not_found_hosts.append(host)

    try:
        _run_checks(token)
    except PermissionError:
        # Token inválido (403) — tentar provisionar novo token automaticamente
        new_token = _provision_new_token()
        if new_token:
            not_found_ips.clear()
            not_found_hosts.clear()
            try:
                _run_checks(new_token)
            except PermissionError as e:
                print(_warn(f"⚠️ CMDB: {e} — validação ignorada."))
                return 0
        else:
            print(_warn("⚠️ CMDB: token inválido e não foi possível provisionar novo token — validação ignorada."))
            return 0
    finally:
        _save_cache(cache)

    issues: list[str] = []
    if not_found_ips:
        issues.append(
            "IPs não cadastrados no CMDB:\n"
            + "\n".join(f"  - {ip}  →  http://192.168.15.2:18091/cmdb/netbox/ipam/ip-addresses/add/" for ip in not_found_ips)
        )
    if not_found_hosts:
        issues.append(
            "Hostnames não encontrados no CMDB (devices/VMs):\n"
            + "\n".join(f"  - {h}  →  http://192.168.15.2:18091/cmdb/netbox/dcim/devices/add/" for h in not_found_hosts)
        )

    if issues:
        print(_deny(
            f"Componente(s) de infra não cadastrado(s) no CMDB NetBox",
            "Os seguintes componentes foram referenciados mas não existem no NetBox CMDB:\n\n"
            + "\n\n".join(issues)
            + "\n\nCadastre o componente no CMDB antes de prosseguir, ou corrija o IP/hostname."
        ))
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
