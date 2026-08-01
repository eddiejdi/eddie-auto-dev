#!/usr/bin/env python3
"""Registra o painel WhatsApp Persona NSFW no Authentik (auth.rpa4all.com).

Cria/atualiza Application + Proxy Provider apontando para o painel interno.

Env:
  AUTHENTIK_URL                default https://auth.rpa4all.com
  AUTHENTIK_TOKEN              Bearer admin (obrigatório)
  WA_PERSONA_PANEL_URL         default https://auth.rpa4all.com/whatsapp-persona/
  WA_PERSONA_PANEL_INTERNAL    default http://192.168.15.2:8094
  WA_PERSONA_APP_SLUG          default whatsapp-persona
  WA_PERSONA_APP_NAME          default WhatsApp Persona NSFW

Uso:
  export AUTHENTIK_TOKEN=...
  python3 tools/authentik_management/register_whatsapp_persona_panel.py
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
    "WA_PERSONA_PANEL_URL",
    "https://auth.rpa4all.com/whatsapp-persona/",
).rstrip("/") + "/"
PANEL_INTERNAL = os.environ.get(
    "WA_PERSONA_PANEL_INTERNAL",
    "http://192.168.15.2:8094",
).rstrip("/")
APP_SLUG = os.environ.get("WA_PERSONA_APP_SLUG", "whatsapp-persona")
APP_NAME = os.environ.get("WA_PERSONA_APP_NAME", "WhatsApp Persona NSFW")
PROVIDER_NAME = os.environ.get("WA_PERSONA_PROVIDER_NAME", "whatsapp-persona-proxy")


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
    """Cria provider dedicado (nunca reutiliza pk de outro app)."""
    current = find_one("/providers/proxy/", "name", PROVIDER_NAME)
    # Copia flows de um provider existente (Authentik 2024 exige invalidation_flow)
    template = request("GET", "/providers/proxy/?page_size=5")
    t0 = (template.get("results") or [None])[0] or {}
    auth_flow = t0.get("authorization_flow")
    inv_flow = t0.get("invalidation_flow")
    if not auth_flow:
        flows = request("GET", "/flows/instances/?designation=authorization")
        flow_items = flows.get("results") or []
        if flow_items:
            auth_flow = flow_items[0].get("pk")
    if not auth_flow:
        raise RuntimeError("Nenhum authorization_flow encontrado no Authentik")

    payload: dict[str, Any] = {
        "name": PROVIDER_NAME,
        "authorization_flow": auth_flow,
        "invalidation_flow": inv_flow,
        "external_host": PANEL_EXTERNAL.rstrip("/"),
        "internal_host": PANEL_INTERNAL,
        "internal_host_ssl_validation": False,
        "mode": "proxy",
        "cookie_domain": "rpa4all.com",
        "skip_path_regex": "^/api/health$",
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    if current:
        pk = str(current["pk"])
        request("PATCH", f"/providers/proxy/{pk}/", payload)
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
            "Ajuste de system prompt, temperatura e rebuild da persona NSFW "
            "do bot WhatsApp (eddie-persona-free)."
        ),
        "open_in_new_tab": True,
    }
    if current:
        pk = str(current["pk"])
        request("PATCH", f"/core/applications/{pk}/", payload)
        return pk, "updated"
    created = request("POST", "/core/applications/", payload)
    return str(created.get("pk") or created.get("slug")), "created"


def attach_outpost(provider_pk: str) -> str:
    """Associa o provider ao outpost embutido se existir."""
    outposts = request("GET", "/outposts/instances/")
    items = outposts.get("results") or []
    if not items:
        return "no-outpost"
    # prefere embedded / default
    outpost = items[0]
    for item in items:
        name = (item.get("name") or "").lower()
        if "embedded" in name or "default" in name or "proxy" in name:
            outpost = item
            break
    pk = outpost["pk"]
    providers = list(outpost.get("providers") or [])
    try:
        prov_int = int(provider_pk)
    except ValueError:
        prov_int = provider_pk
    if prov_int not in providers:
        providers.append(prov_int)
        request("PATCH", f"/outposts/instances/{pk}/", {"providers": providers})
        return f"attached:{outpost.get('name')}"
    return f"already:{outpost.get('name')}"


def main() -> int:
    if not AUTHENTIK_TOKEN:
        print("AUTHENTIK_TOKEN obrigatório", file=sys.stderr)
        return 2
    print(f"Authentik: {AUTHENTIK_URL}")
    print(f"External:  {PANEL_EXTERNAL}")
    print(f"Internal:  {PANEL_INTERNAL}")
    provider_pk, pstat = ensure_proxy_provider()
    print(f"Provider:  {provider_pk} ({pstat})")
    app_pk, astat = ensure_application(provider_pk)
    print(f"App:       {app_pk} ({astat})")
    ostat = attach_outpost(provider_pk)
    print(f"Outpost:   {ostat}")
    print(f"OK → {PANEL_EXTERNAL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
