#!/usr/bin/env python3
"""Registra o painel de acesso ao Nextcloud como Application no Authentik."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

AUTHENTIK_URL = os.environ.get("AUTHENTIK_URL", "https://auth.rpa4all.com").rstrip("/")
AUTHENTIK_TOKEN = os.environ.get("AUTHENTIK_TOKEN", "ak-homelab-authentik-api-2026")
PANEL_URL = os.environ.get(
    "NEXTCLOUD_ACCESS_PANEL_URL",
    "https://homelab.rpa4all.com/nextcloud-access/panel",
)
APP_NAME = os.environ.get("NEXTCLOUD_ACCESS_PANEL_NAME", "Painel Nextcloud RPA4All")
APP_SLUG = os.environ.get("NEXTCLOUD_ACCESS_PANEL_SLUG", "nextcloud-access-panel")


def request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Executa chamadas na API do Authentik."""
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


def existing_application() -> dict[str, Any] | None:
    """Busca a aplicação pelo slug."""
    result = request("GET", f"/core/applications/?slug={APP_SLUG}")
    items = result.get("results", [])
    return items[0] if items else None


def app_payload() -> dict[str, Any]:
    """Payload base da aplicação."""
    return {
        "name": APP_NAME,
        "slug": APP_SLUG,
        "meta_launch_url": PANEL_URL,
        "meta_description": "Painel administrativo para criação de acesso ao Nextcloud via Authentik OIDC.",
        "policy_engine_mode": "any",
    }


def upsert_application() -> tuple[str, str]:
    """Cria ou atualiza a application do painel."""
    current = existing_application()
    payload = app_payload()

    if current:
        app_pk = str(current["pk"])
        request("PATCH", f"/core/applications/{app_pk}/", payload)
        return app_pk, "updated"

    created = request("POST", "/core/applications/", payload)
    return str(created["pk"]), "created"


def main() -> int:
    """CLI principal."""
    try:
        app_pk, action = upsert_application()
    except Exception as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "status": "ok",
                "action": action,
                "application_pk": app_pk,
                "application_slug": APP_SLUG,
                "launch_url": PANEL_URL,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
