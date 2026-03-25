#!/usr/bin/env python3
"""Create or update the Authentik proxy provider for workstation.rpa4all.com."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


BASE_URL = os.environ.get("AUTHENTIK_URL", "https://auth.rpa4all.com").rstrip("/")
API_BASE = f"{BASE_URL}/api/v3"
TOKEN = os.environ.get("AUTHENTIK_TOKEN")
USER_AGENT = os.environ.get("AUTHENTIK_USER_AGENT", "Mozilla/5.0")

APP_SLUG = os.environ.get("AUTHENTIK_WORKSTATION_APP_SLUG", "workstation-xfce")
APP_NAME = os.environ.get("AUTHENTIK_WORKSTATION_APP_NAME", "Workstation XFCE")
PROVIDER_NAME = os.environ.get(
    "AUTHENTIK_WORKSTATION_PROVIDER_NAME",
    "Workstation XFCE Proxy",
)
EXTERNAL_HOST = os.environ.get(
    "AUTHENTIK_WORKSTATION_EXTERNAL_HOST",
    "https://workstation.rpa4all.com",
)
EMBEDDED_OUTPOST_ID = os.environ.get(
    "AUTHENTIK_EMBEDDED_OUTPOST_ID",
    "fcadb664-2161-4e69-a430-aac1ec2e3b39",
)

DEFAULT_AUTHENTICATION_FLOW = os.environ.get(
    "AUTHENTIK_AUTHENTICATION_FLOW_ID",
    "d25248ef-33cb-42a6-906c-d2fdb71db134",
)
DEFAULT_AUTHORIZATION_FLOW = os.environ.get(
    "AUTHENTIK_AUTHORIZATION_FLOW_ID",
    "55b6af51-fa8f-4cc1-97c2-448908bb9674",
)
DEFAULT_INVALIDATION_FLOW = os.environ.get(
    "AUTHENTIK_INVALIDATION_FLOW_ID",
    "71dfe71e-4997-4fd1-8ac6-0db01b49e92b",
)


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


def find_provider() -> dict | None:
    providers = api_request("GET", "/providers/proxy/?ordering=name")
    return next(
        (
            item
            for item in providers.get("results", [])
            if item.get("external_host") == EXTERNAL_HOST or item.get("name") == PROVIDER_NAME
        ),
        None,
    )


def ensure_provider() -> dict:
    payload = {
        "name": PROVIDER_NAME,
        "authentication_flow": DEFAULT_AUTHENTICATION_FLOW,
        "authorization_flow": DEFAULT_AUTHORIZATION_FLOW,
        "invalidation_flow": DEFAULT_INVALIDATION_FLOW,
        "external_host": EXTERNAL_HOST,
        "mode": "forward_single",
    }
    provider = find_provider()
    if provider is None:
        provider = api_request("POST", "/providers/proxy/", payload)
        print(f"created provider {provider['pk']}")
        return provider

    provider = api_request("PATCH", f"/providers/proxy/{provider['pk']}/", payload)
    print(f"updated provider {provider['pk']}")
    return provider


def ensure_application(provider_pk: str) -> None:
    apps = api_request("GET", f"/core/applications/?search={APP_SLUG}")
    existing = next((item for item in apps.get("results", []) if item.get("slug") == APP_SLUG), None)
    payload = {
        "name": APP_NAME,
        "slug": APP_SLUG,
        "provider": provider_pk,
        "meta_launch_url": EXTERNAL_HOST,
        "policy_engine_mode": "any",
    }
    if existing is None:
        app = api_request("POST", "/core/applications/", payload)
        print(f"created app {app['slug']}")
    else:
        app = api_request("PATCH", f"/core/applications/{APP_SLUG}/", payload)
        print(f"updated app {app['slug']}")


def ensure_outpost_link(provider_pk: str) -> None:
    outpost = api_request("GET", f"/outposts/instances/{EMBEDDED_OUTPOST_ID}/")
    provider_ids = list(outpost.get("providers", []))
    if provider_pk in provider_ids:
        print("embedded outpost already linked")
        return
    provider_ids.append(provider_pk)
    outpost = api_request(
        "PATCH",
        f"/outposts/instances/{EMBEDDED_OUTPOST_ID}/",
        {"providers": provider_ids},
    )
    print(f"embedded outpost providers -> {outpost['providers']}")


def main() -> None:
    if not TOKEN:
        raise SystemExit("AUTHENTIK_TOKEN is required")
    provider = ensure_provider()
    ensure_application(provider["pk"])
    ensure_outpost_link(provider["pk"])


if __name__ == "__main__":
    main()
