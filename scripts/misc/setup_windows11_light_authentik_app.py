#!/usr/bin/env python3
"""Create or update the Authentik application for Windows 11 Light workstation."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


BASE_URL = os.environ.get("AUTHENTIK_URL", "https://auth.rpa4all.com").rstrip("/")
API_BASE = f"{BASE_URL}/api/v3"
TOKEN = os.environ.get("AUTHENTIK_TOKEN")
USER_AGENT = os.environ.get("AUTHENTIK_USER_AGENT", "Mozilla/5.0")

APP_SLUG = os.environ.get("AUTHENTIK_WINDOWS11_APP_SLUG", "windows11-light")
APP_NAME = os.environ.get("AUTHENTIK_WINDOWS11_APP_NAME", "Windows 11 Light")
LAUNCH_URL = os.environ.get(
    "AUTHENTIK_WINDOWS11_LAUNCH_URL",
    "https://homelab.rpa4all.com/windows11",
)
PROVIDER_EXTERNAL_HOST = os.environ.get(
    "AUTHENTIK_WINDOWS11_PROVIDER_EXTERNAL_HOST",
    "https://homelab.rpa4all.com",
)
PROVIDER_FALLBACK_NAME = os.environ.get(
    "AUTHENTIK_WINDOWS11_PROVIDER_FALLBACK_NAME",
    "Homelab API Proxy",
)
ATTACH_PROVIDER = os.environ.get(
    "AUTHENTIK_WINDOWS11_ATTACH_PROVIDER",
    "false",
).strip().lower() in {"1", "true", "yes", "y"}


def api_request(method: str, path: str, payload: dict | None = None) -> dict:
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        f"{API_BASE}{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        details = exc.read().decode()
        raise RuntimeError(f"{method} {path} failed with {exc.code}: {details}") from exc


def find_homelab_provider_pk() -> str:
    providers = api_request("GET", "/providers/proxy/?ordering=name")
    target = next(
        (
            item
            for item in providers.get("results", [])
            if item.get("external_host") == PROVIDER_EXTERNAL_HOST
            or item.get("name") == PROVIDER_FALLBACK_NAME
        ),
        None,
    )
    if target is None:
        raise RuntimeError(
            f"No proxy provider found for external_host={PROVIDER_EXTERNAL_HOST!r}"
        )
    return str(target["pk"])


def ensure_application(provider_pk: str | None) -> None:
    apps = api_request("GET", f"/core/applications/?search={APP_SLUG}")
    existing = next((item for item in apps.get("results", []) if item.get("slug") == APP_SLUG), None)
    payload = {
        "name": APP_NAME,
        "slug": APP_SLUG,
        "meta_launch_url": LAUNCH_URL,
        "open_in_new_tab": True,
        "policy_engine_mode": "any",
    }
    if provider_pk:
        payload["provider"] = provider_pk
    elif existing is not None and existing.get("provider") is not None:
        # Explicitly detach from provider when requested.
        payload["provider"] = None

    if existing is None:
        app = api_request("POST", "/core/applications/", payload)
        print(f"created app {app['slug']}")
    else:
        app = api_request("PATCH", f"/core/applications/{APP_SLUG}/", payload)
        print(f"updated app {app['slug']}")


def main() -> None:
    if not TOKEN:
        raise SystemExit("AUTHENTIK_TOKEN is required")
    provider_pk = find_homelab_provider_pk() if ATTACH_PROVIDER else None
    ensure_application(provider_pk)


if __name__ == "__main__":
    main()
