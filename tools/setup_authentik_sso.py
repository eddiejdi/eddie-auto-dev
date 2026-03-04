#!/usr/bin/env python3
"""Script para configurar Authentik SSO com providers OAuth2 para Nextcloud, Grafana e OpenWebUI."""
from __future__ import annotations

import json
import sys
import urllib.request
import urllib.error

BASE = "http://localhost:9000"
TOKEN = "ak-homelab-authentik-api-2026"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}


def api(method: str, path: str, data: dict | None = None) -> dict:
    """Faz requisição à API do Authentik."""
    url = f"{BASE}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"  ERRO {e.code}: {err[:200]}")
        return {"error": e.code, "detail": err}


def get_auth_flow() -> str:
    """Busca o flow de autorização padrão."""
    r = api("GET", "/api/v3/flows/instances/?designation=authorization")
    return r["results"][0]["pk"]


def get_scope_mappings() -> list[str]:
    """Busca todos os scope mappings OIDC."""
    r = api("GET", "/api/v3/propertymappings/scope/?page_size=50")
    return [m["pk"] for m in r["results"]]


def create_provider(name: str, client_id: str, client_secret: str,
                    redirect_uris: str, flow_pk: str, mappings: list[str]) -> int | None:
    """Cria um OAuth2/OIDC provider."""
    print(f"\n[Provider] Criando: {name}")
    data = {
        "name": name,
        "authorization_flow": flow_pk,
        "client_type": "confidential",
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uris": redirect_uris,
        "property_mappings": mappings,
        "sub_mode": "hashed_user_id",
        "include_claims_in_id_token": True,
        "issuer_mode": "per_provider",
    }
    r = api("POST", "/api/v3/providers/oauth2/", data)
    if "pk" in r:
        print(f"  OK — Provider ID: {r['pk']}")
        return r["pk"]
    if "name" in r.get("detail", "") or "already" in str(r):
        print(f"  Já existe, buscando...")
        existing = api("GET", f"/api/v3/providers/oauth2/?search={name}")
        if existing.get("results"):
            pk = existing["results"][0]["pk"]
            print(f"  Encontrado ID: {pk}")
            return pk
    return None


def create_application(name: str, slug: str, provider_pk: int, launch_url: str) -> bool:
    """Cria uma application no Authentik."""
    print(f"\n[Application] Criando: {name}")
    data = {
        "name": name,
        "slug": slug,
        "provider": provider_pk,
        "meta_launch_url": launch_url,
        "policy_engine_mode": "any",
    }
    r = api("POST", "/api/v3/core/applications/", data)
    if "pk" in r:
        print(f"  OK — App: {r['slug']}")
        return True
    if "already" in str(r) or "slug" in str(r.get("detail", "")):
        print(f"  Já existe, atualizando...")
        api("PATCH", f"/api/v3/core/applications/{slug}/", data)
        return True
    return False


def main() -> None:
    """Configura providers e applications no Authentik."""
    print("=== Setup Authentik SSO ===\n")

    # 1. Buscar flow e mappings
    print("[1] Buscando authorization flow...")
    flow_pk = get_auth_flow()
    print(f"  Flow: {flow_pk}")

    print("[2] Buscando scope mappings...")
    mappings = get_scope_mappings()
    print(f"  Mappings: {len(mappings)} encontrados")

    # 2. Criar providers OAuth2
    services = [
        {
            "name": "Nextcloud Provider",
            "client_id": "authentik-nextcloud",
            "client_secret": "nextcloud-sso-secret-2026",
            "redirect_uris": "https://nextcloud.rpa4all.com/apps/oidc_login/oidc\nhttps://nextcloud.rpa4all.com/apps/user_oidc/code",
            "app_name": "Nextcloud",
            "app_slug": "nextcloud",
            "launch_url": "https://nextcloud.rpa4all.com",
        },
        {
            "name": "Grafana Provider",
            "client_id": "authentik-grafana",
            "client_secret": "grafana-sso-secret-2026",
            "redirect_uris": "https://grafana.rpa4all.com/login/generic_oauth",
            "app_name": "Grafana",
            "app_slug": "grafana",
            "launch_url": "https://grafana.rpa4all.com",
        },
        {
            "name": "OpenWebUI Provider",
            "client_id": "authentik-openwebui",
            "client_secret": "openwebui-sso-secret-2026",
            "redirect_uris": "https://openwebui.rpa4all.com/oauth/oidc/callback",
            "app_name": "OpenWebUI",
            "app_slug": "openwebui",
            "launch_url": "https://openwebui.rpa4all.com",
        },
    ]

    results = {}
    for svc in services:
        provider_pk = create_provider(
            svc["name"], svc["client_id"], svc["client_secret"],
            svc["redirect_uris"], flow_pk, mappings,
        )
        if provider_pk:
            ok = create_application(svc["app_name"], svc["app_slug"], provider_pk, svc["launch_url"])
            results[svc["app_slug"]] = {"provider_pk": provider_pk, "ok": ok}
        else:
            results[svc["app_slug"]] = {"provider_pk": None, "ok": False}

    # 3. Resumo
    print("\n=== RESUMO ===")
    for slug, info in results.items():
        status = "OK" if info["ok"] else "FALHA"
        print(f"  {slug}: {status} (provider_pk={info['provider_pk']})")

    # 4. OIDC config URLs
    print(f"\n=== URLs OIDC ===")
    print(f"  Issuer:    https://auth.rpa4all.com/application/o/<slug>/")
    print(f"  Authorize: https://auth.rpa4all.com/application/o/authorize/")
    print(f"  Token:     https://auth.rpa4all.com/application/o/token/")
    print(f"  UserInfo:  https://auth.rpa4all.com/application/o/userinfo/")
    print(f"  JWKS:      https://auth.rpa4all.com/application/o/<slug>/jwks/")


if __name__ == "__main__":
    main()
