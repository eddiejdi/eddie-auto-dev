#!/usr/bin/env python3
"""Cria ou atualiza o atalho do console admin do Authentik na Library."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import requests


AUTHENTIK_URL = os.getenv("AUTHENTIK_URL", "https://auth.rpa4all.com").rstrip("/")
AUTHENTIK_TOKEN = os.getenv("AUTHENTIK_TOKEN", "ak-homelab-authentik-api-2026").strip()

APP_NAME = os.getenv("AUTHENTIK_ADMIN_APP_NAME", "Authentik Admin").strip() or "Authentik Admin"
APP_SLUG = os.getenv("AUTHENTIK_ADMIN_APP_SLUG", "authentik-admin").strip() or "authentik-admin"
APP_LAUNCH_URL = os.getenv(
    "AUTHENTIK_ADMIN_APP_URL",
    f"{AUTHENTIK_URL}/if/admin/",
).strip()
APP_ICON_URL = os.getenv(
    "AUTHENTIK_ADMIN_APP_ICON_URL",
    f"{AUTHENTIK_URL}/static/dist/assets/icons/icon.png",
).strip()
APP_DESCRIPTION = os.getenv(
    "AUTHENTIK_ADMIN_APP_DESCRIPTION",
    "Atalho para o console administrativo do Authentik.",
).strip()
APP_PUBLISHER = os.getenv("AUTHENTIK_ADMIN_APP_PUBLISHER", "RPA4ALL").strip()
VERIFY_TLS = os.getenv("AUTHENTIK_VERIFY_TLS", "0").lower() in {"1", "true", "yes", "on"}


def authentik_request(
    method: str,
    endpoint: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = requests.request(
        method,
        f"{AUTHENTIK_URL}/api/v3{endpoint}",
        json=payload,
        headers={
            "Authorization": f"Bearer {AUTHENTIK_TOKEN}",
            "Content-Type": "application/json",
        },
        timeout=20,
        verify=VERIFY_TLS,
    )
    response.raise_for_status()
    return response.json() if response.text else {}


def find_application() -> dict[str, Any] | None:
    result = authentik_request("GET", f"/core/applications/?search={APP_SLUG}")
    for app in result.get("results", []):
        if app.get("slug") == APP_SLUG:
            return app
    return None


def desired_payload() -> dict[str, Any]:
    return {
        "name": APP_NAME,
        "slug": APP_SLUG,
        "provider": None,
        "meta_launch_url": APP_LAUNCH_URL,
        "meta_description": APP_DESCRIPTION,
        "meta_publisher": APP_PUBLISHER,
        "open_in_new_tab": False,
        "policy_engine_mode": "any",
        "group": "",
        "backchannel_providers": [],
    }


def main() -> int:
    if not AUTHENTIK_TOKEN:
        print("AUTHENTIK_TOKEN nao configurado.", file=sys.stderr)
        return 1

    payload = desired_payload()
    existing = find_application()
    if existing:
        app = authentik_request("PATCH", f"/core/applications/{APP_SLUG}/", payload)
        result = {"status": "updated", "application": app}
    else:
        app = authentik_request("POST", "/core/applications/", payload)
        result = {"status": "created", "application": app}

    if APP_ICON_URL:
        authentik_request("POST", f"/core/applications/{APP_SLUG}/set_icon_url/", {"url": APP_ICON_URL})
        result["application"] = find_application() or app
        result["icon_url"] = APP_ICON_URL

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
