#!/usr/bin/env python3
"""Create or update the Authentik proxy provider for mail.rpa4all.com."""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error


BASE_URL = os.environ.get("AUTHENTIK_URL", "https://auth.rpa4all.com").rstrip("/")
API_BASE = f"{BASE_URL}/api/v3"
TOKEN = os.environ.get("AUTHENTIK_TOKEN")
USER_AGENT = os.environ.get("AUTHENTIK_USER_AGENT", "Mozilla/5.0")

APP_SLUG = "mailu-email"
PROVIDER_NAME = "Mail Roundcube Proxy"
EXTERNAL_HOST = "https://mail.rpa4all.com"
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
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        details = exc.read().decode()
        raise RuntimeError(f"{method} {path} failed with {exc.code}: {details}") from exc


def main() -> None:
    if not TOKEN:
        raise SystemExit("AUTHENTIK_TOKEN is required")

    providers = api_request("GET", "/providers/proxy/?ordering=name")
    provider = next(
        (
            item
            for item in providers.get("results", [])
            if item.get("external_host") == EXTERNAL_HOST or item.get("name") == PROVIDER_NAME
        ),
        None,
    )

    if provider is None:
        provider = api_request(
            "POST",
            "/providers/proxy/",
            {
                "name": PROVIDER_NAME,
                "authentication_flow": DEFAULT_AUTHENTICATION_FLOW,
                "authorization_flow": DEFAULT_AUTHORIZATION_FLOW,
                "invalidation_flow": DEFAULT_INVALIDATION_FLOW,
                "external_host": EXTERNAL_HOST,
                "mode": "forward_single",
            },
        )
        print(f"created provider {provider['pk']}")
    else:
        print(f"using provider {provider['pk']}")

    app = api_request(
        "PATCH",
        f"/core/applications/{APP_SLUG}/",
        {
            "provider": provider["pk"],
            "meta_launch_url": EXTERNAL_HOST,
        },
    )
    print(f"application provider -> {app['provider']}")

    outpost = api_request("GET", f"/outposts/instances/{EMBEDDED_OUTPOST_ID}/")
    provider_ids = list(outpost.get("providers", []))
    if provider["pk"] not in provider_ids:
        provider_ids.append(provider["pk"])
        outpost = api_request(
            "PATCH",
            f"/outposts/instances/{EMBEDDED_OUTPOST_ID}/",
            {"providers": provider_ids},
        )
        print(f"embedded outpost providers -> {outpost['providers']}")
    else:
        print("embedded outpost already linked")


if __name__ == "__main__":
    main()
