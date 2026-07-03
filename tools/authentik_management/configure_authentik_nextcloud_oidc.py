#!/usr/bin/env python3
"""Provisiona o provider OIDC do Nextcloud no Authentik."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

AUTHENTIK_URL = os.environ.get("AUTHENTIK_URL", "https://auth.rpa4all.com").rstrip("/")
AUTHENTIK_TOKEN = os.environ.get("AUTHENTIK_TOKEN", "ak-homelab-authentik-api-2026")
NEXTCLOUD_URL = os.environ.get("NEXTCLOUD_URL", "https://nextcloud.rpa4all.com").rstrip("/")
CLIENT_ID = os.environ.get("AUTHENTIK_NEXTCLOUD_CLIENT_ID", "authentik-nextcloud")
CLIENT_SECRET = os.environ.get("AUTHENTIK_NEXTCLOUD_CLIENT_SECRET", "nextcloud-sso-secret-2026")
PROVIDER_NAME = os.environ.get("AUTHENTIK_NEXTCLOUD_PROVIDER_NAME", "Nextcloud Provider")
APP_NAME = os.environ.get("AUTHENTIK_NEXTCLOUD_APP_NAME", "Nextcloud")
APP_SLUG = os.environ.get("AUTHENTIK_NEXTCLOUD_APP_SLUG", "nextcloud")


def _request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{AUTHENTIK_URL}/api/v3{path}"
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "Authorization": f"Bearer {AUTHENTIK_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            text = response.read().decode("utf-8")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} em {path}: {detail[:400]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Falha ao conectar no Authentik: {exc}") from exc


def build_redirect_uris(nextcloud_url: str) -> str:
    base_url = nextcloud_url.rstrip("/")
    # Mantemos o callback legacy do user_oidc apenas por compatibilidade de migração.
    return "\n".join(
        [
            f"{base_url}/apps/oidc_login/oidc",
            f"{base_url}/apps/user_oidc/code",
        ]
    )


def _authorization_flow_pk() -> str:
    result = _request("GET", "/flows/instances/?designation=authorization")
    items = result.get("results", [])
    if not items:
        raise RuntimeError("Nenhum authorization flow encontrado no Authentik.")
    return str(items[0]["pk"])


def _scope_mapping_pks() -> list[str]:
    try:
        result = _request("GET", "/propertymappings/provider/scope/?page_size=200")
    except RuntimeError:
        result = _request("GET", "/propertymappings/scope/?page_size=200")
    return [str(item["pk"]) for item in result.get("results", [])]


def build_provider_payload(*, flow_pk: str, mappings: list[str], nextcloud_url: str) -> dict[str, Any]:
    return {
        "name": PROVIDER_NAME,
        "authorization_flow": flow_pk,
        "client_type": "confidential",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uris": build_redirect_uris(nextcloud_url),
        "property_mappings": mappings,
        "sub_mode": "hashed_user_id",
        "include_claims_in_id_token": True,
        "issuer_mode": "per_provider",
    }


def build_app_payload(*, provider_pk: str, nextcloud_url: str) -> dict[str, Any]:
    return {
        "name": APP_NAME,
        "slug": APP_SLUG,
        "provider": provider_pk,
        "meta_launch_url": nextcloud_url.rstrip("/"),
        "policy_engine_mode": "any",
    }


def _existing_provider_pk() -> str | None:
    result = _request("GET", f"/providers/oauth2/?search={CLIENT_ID}")
    for item in result.get("results", []):
        if item.get("client_id") == CLIENT_ID:
            return str(item["pk"])
    return None


def _existing_application_pk() -> str | None:
    result = _request("GET", f"/core/applications/?slug={APP_SLUG}")
    items = result.get("results", [])
    return str(items[0]["pk"]) if items else None


def upsert_provider(*, nextcloud_url: str) -> str:
    flow_pk = _authorization_flow_pk()
    mappings = _scope_mapping_pks()
    payload = build_provider_payload(flow_pk=flow_pk, mappings=mappings, nextcloud_url=nextcloud_url)
    provider_pk = _existing_provider_pk()
    if provider_pk:
        _request("PATCH", f"/providers/oauth2/{provider_pk}/", payload)
        return provider_pk
    created = _request("POST", "/providers/oauth2/", payload)
    return str(created["pk"])


def upsert_application(*, provider_pk: str, nextcloud_url: str) -> str:
    payload = build_app_payload(provider_pk=provider_pk, nextcloud_url=nextcloud_url)
    app_pk = _existing_application_pk()
    if app_pk:
        _request("PATCH", f"/core/applications/{app_pk}/", payload)
        return app_pk
    created = _request("POST", "/core/applications/", payload)
    return str(created["pk"])


def main() -> int:
    provider_pk = upsert_provider(nextcloud_url=NEXTCLOUD_URL)
    app_pk = upsert_application(provider_pk=provider_pk, nextcloud_url=NEXTCLOUD_URL)
    print(
        json.dumps(
            {
                "status": "ok",
                "provider_pk": provider_pk,
                "application_pk": app_pk,
                "client_id": CLIENT_ID,
                "nextcloud_url": NEXTCLOUD_URL,
                "redirect_uris": build_redirect_uris(NEXTCLOUD_URL).splitlines(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
