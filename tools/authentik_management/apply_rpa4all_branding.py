#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from typing import Any

import requests


AUTHENTIK_URL = os.getenv("AUTHENTIK_URL", "https://auth.rpa4all.com").rstrip("/")
AUTHENTIK_TOKEN = os.getenv("AUTHENTIK_TOKEN", "ak-homelab-authentik-api-2026").strip()
VERIFY_TLS = os.getenv("AUTHENTIK_VERIFY_TLS", "0").lower() in {"1", "true", "yes", "on"}

BRAND_TITLE = os.getenv("RPA4ALL_AUTH_TITLE", "RPA4ALL Identity").strip() or "RPA4ALL Identity"
BRAND_LOGO = os.getenv("RPA4ALL_AUTH_LOGO", "https://www.rpa4all.com/assets/rpa4all-auth-logo.svg").strip()
BRAND_FAVICON = os.getenv("RPA4ALL_AUTH_FAVICON", "https://www.rpa4all.com/assets/rpa4all-auth-favicon.svg").strip()
FLOW_TITLE = os.getenv("RPA4ALL_AUTH_FLOW_TITLE", "Central de Acesso RPA4ALL").strip() or "Central de Acesso RPA4ALL"
FLOW_LAYOUT = os.getenv("RPA4ALL_AUTH_FLOW_LAYOUT", "content_right").strip() or "content_right"
FLOW_BACKGROUND = os.getenv(
    "RPA4ALL_AUTH_FLOW_BACKGROUND",
    "https://www.rpa4all.com/assets/storage-images/storage-operations.jpg",
).strip()


def authentik_request(method: str, endpoint: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.request(
        method,
        f"{AUTHENTIK_URL}/api/v3{endpoint}",
        headers={
            "Authorization": f"Bearer {AUTHENTIK_TOKEN}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
        verify=VERIFY_TLS,
    )
    response.raise_for_status()
    return response.json() if response.text else {}


def get_default_brand() -> dict[str, Any]:
    payload = authentik_request("GET", "/core/brands/")
    for brand in payload.get("results", []):
        if brand.get("default"):
            return brand
    raise RuntimeError("Nenhum brand default encontrado no Authentik.")


def main() -> int:
    if not AUTHENTIK_TOKEN:
        print("AUTHENTIK_TOKEN nao configurado.", file=sys.stderr)
        return 1

    brand = get_default_brand()
    brand_uuid = brand["brand_uuid"]
    flow_slug = "default-authentication-flow"

    brand_result = authentik_request(
        "PATCH",
        f"/core/brands/{brand_uuid}/",
        {
            "branding_title": BRAND_TITLE,
            "branding_logo": BRAND_LOGO,
            "branding_favicon": BRAND_FAVICON,
        },
    )

    flow_payload = {
        "title": FLOW_TITLE,
        "layout": FLOW_LAYOUT,
        "background": FLOW_BACKGROUND,
    }

    flow_result: dict[str, Any] | dict[str, str]
    try:
        flow_result = authentik_request("PATCH", f"/flows/instances/{flow_slug}/", flow_payload)
    except requests.HTTPError as exc:
        flow_result = {
            "status": "flow_patch_failed",
            "detail": exc.response.text[:1000] if exc.response is not None else str(exc),
        }

    print(
        json.dumps(
            {
                "brand": {
                    "brand_uuid": brand_uuid,
                    "branding_title": brand_result.get("branding_title"),
                    "branding_logo": brand_result.get("branding_logo"),
                    "branding_favicon": brand_result.get("branding_favicon"),
                },
                "flow": flow_result,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
