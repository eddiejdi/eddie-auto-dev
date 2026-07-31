#!/usr/bin/env python3
"""Registra o painel de auditoria de prompts LLM no Authentik (auth.rpa4all.com).

Cria/atualiza:
  - Application (atalho no portal)
  - Proxy Provider (forward auth / reverse proxy) apontando para o painel interno
  - Associa o provider ao outpost embutido (se existir)

Env:
  AUTHENTIK_URL          default https://auth.rpa4all.com
  AUTHENTIK_TOKEN        Bearer token admin (obrigatório)
  LLM_PROMPT_PANEL_URL   default https://auth.rpa4all.com/llm-prompts/
  LLM_PROMPT_INTERNAL    default http://192.168.15.2:8092
  LLM_PROMPT_APP_SLUG    default llm-prompt-audit
  LLM_PROMPT_APP_NAME    default Auditoria Prompts LLM

Uso:
  export AUTHENTIK_TOKEN=...
  python3 tools/authentik_management/register_llm_prompt_audit_panel.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

AUTHENTIK_URL = os.environ.get("AUTHENTIK_URL", "https://auth.rpa4all.com").rstrip("/")
AUTHENTIK_TOKEN = os.environ.get("AUTHENTIK_TOKEN", "").strip()
PANEL_EXTERNAL = os.environ.get(
    "LLM_PROMPT_PANEL_URL",
    "https://auth.rpa4all.com/llm-prompts/",
).rstrip("/") + "/"
PANEL_INTERNAL = os.environ.get("LLM_PROMPT_INTERNAL", "http://192.168.15.2:8092").rstrip("/")
APP_SLUG = os.environ.get("LLM_PROMPT_APP_SLUG", "llm-prompt-audit")
APP_NAME = os.environ.get("LLM_PROMPT_APP_NAME", "Auditoria Prompts LLM")
PROVIDER_NAME = os.environ.get("LLM_PROMPT_PROVIDER_NAME", "llm-prompt-audit-proxy")


def request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{AUTHENTIK_URL}/api/v3{path}"
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "Authorization": f"Bearer {AUTHENTIK_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            text = response.read().decode("utf-8")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} em {path}: {detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Falha ao conectar no Authentik: {exc}") from exc


def find_one(path: str, key: str, value: str) -> dict[str, Any] | None:
    qs = urllib.parse.urlencode({key: value})
    result = request("GET", f"{path}?{qs}")
    items = result.get("results", [])
    return items[0] if items else None


def ensure_proxy_provider() -> tuple[str, str]:
    """Cria ou atualiza Proxy Provider path-based sob /llm-prompts/."""
    current = find_one("/providers/proxy/", "name", PROVIDER_NAME)
    # external_host = portal path; internal = painel na LAN
    # mode: forward_single (path) via external_host + path
    payload: dict[str, Any] = {
        "name": PROVIDER_NAME,
        "authorization_flow": None,  # preenchido abaixo se necessário
        "external_host": PANEL_EXTERNAL.rstrip("/"),
        "internal_host": PANEL_INTERNAL,
        "internal_host_ssl_validation": False,
        "mode": "proxy",
        "cookie_domain": "rpa4all.com",
        "skip_path_regex": "^/api/health$",
    }

    # authorization_flow obrigatório — pega o default authentication/authorization se existir
    flows = request("GET", "/flows/instances/?designation=authorization")
    flow_items = flows.get("results") or []
    if flow_items:
        payload["authorization_flow"] = flow_items[0].get("pk")
    else:
        # fallback: tenta default-provider-authorization-implicit-consent
        f2 = find_one("/flows/instances/", "slug", "default-provider-authorization-implicit-consent")
        if f2:
            payload["authorization_flow"] = f2.get("pk")

    if not payload.get("authorization_flow"):
        raise RuntimeError("Nenhum authorization_flow encontrado no Authentik")

    if current:
        pk = str(current["pk"])
        # não envia None desnecessário
        request("PATCH", f"/providers/proxy/{pk}/", {k: v for k, v in payload.items() if v is not None})
        return pk, "updated"

    created = request("POST", "/providers/proxy/", payload)
    return str(created["pk"]), "created"


def ensure_application(provider_pk: str) -> tuple[str, str]:
    current = find_one("/core/applications/", "slug", APP_SLUG)
    payload = {
        "name": APP_NAME,
        "slug": APP_SLUG,
        "provider": int(provider_pk) if str(provider_pk).isdigit() else provider_pk,
        "meta_launch_url": PANEL_EXTERNAL,
        "meta_description": (
            "Auditoria de todos os prompts LLM via ollama-gpu-coordinator "
            "(ajuste, export e fine-tuning)."
        ),
        "policy_engine_mode": "any",
        "open_in_new_tab": True,
    }
    if current:
        pk = str(current["pk"])
        request("PATCH", f"/core/applications/{pk}/", payload)
        return pk, "updated"
    created = request("POST", "/core/applications/", payload)
    return str(created["pk"]), "created"


def attach_to_embedded_outpost(provider_pk: str) -> str:
    """Tenta associar o provider ao outpost embutido do Authentik."""
    outposts = request("GET", "/outposts/instances/?page_size=50")
    items = outposts.get("results") or []
    if not items:
        return "no-outpost"
    # prefere embedded
    target = None
    for o in items:
        name = (o.get("name") or "").lower()
        if "embedded" in name or "authentik Embedded" in (o.get("name") or ""):
            target = o
            break
    if target is None:
        target = items[0]
    providers = list(target.get("providers") or [])
    pk_int = int(provider_pk) if str(provider_pk).isdigit() else provider_pk
    if pk_int in providers:
        return f"already-on:{target.get('name')}"
    providers.append(pk_int)
    request("PATCH", f"/outposts/instances/{target['pk']}/", {"providers": providers})
    return f"attached:{target.get('name')}"


def main() -> int:
    if not AUTHENTIK_TOKEN:
        print(
            "Erro: defina AUTHENTIK_TOKEN (Bearer admin do Authentik).",
            file=sys.stderr,
        )
        return 1
    try:
        provider_pk, p_action = ensure_proxy_provider()
        app_pk, a_action = ensure_application(provider_pk)
        outpost = attach_to_embedded_outpost(provider_pk)
    except Exception as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "status": "ok",
                "application": {"pk": app_pk, "slug": APP_SLUG, "action": a_action},
                "provider": {"pk": provider_pk, "name": PROVIDER_NAME, "action": p_action},
                "outpost": outpost,
                "launch_url": PANEL_EXTERNAL,
                "internal_host": PANEL_INTERNAL,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
