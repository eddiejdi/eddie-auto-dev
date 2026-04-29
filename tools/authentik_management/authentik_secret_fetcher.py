"""Helpers para buscar secrets diretamente no Authentik via API.

Fornece uma função utilitária que tenta múltiplos endpoints comuns do Authentik
para recuperar um campo de secret (por exemplo, `api_key`, `api_secret`, `password`).

Uso (CLI):
  AUTHENTIK_URL=https://auth.example.com AUTHENTIK_TOKEN=ak-... \
    python tools/authentik_management/authentik_secret_fetcher.py authentik/mysecret password
"""
from __future__ import annotations

import os
from typing import Optional
from urllib.parse import quote

import requests


def get_secret_from_authentik(name: str, field: str = "password", auth_url: Optional[str] = None, token: Optional[str] = None) -> Optional[str]:
    """Tenta resolver um secret no Authentik.

    A função tenta, em ordem:
    1. GET /api/v3/secrets/local/{name}?field={field}
    2. GET /api/v3/secrets/{name}
    3. GET /api/v3/core/applications/?format=json&search={name} (retorna `client_secret`)
    4. GET /api/v3/providers/oauth2/?search={name} (retorna `client_secret`)

    Retorna o valor do campo quando encontrado ou ``None`` em falha.
    """
    base = auth_url or os.environ.get("AUTHENTIK_URL", "https://auth.rpa4all.com")
    api_token = token or os.environ.get("AUTHENTIK_TOKEN", "")

    headers = {"Accept": "application/json"}
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"

    encoded = quote(name, safe="")

    try:
        # 1) /secrets/local/{name}
        url_local = f"{base.rstrip('/')}/api/v3/secrets/local/{encoded}"
        resp = requests.get(url_local, headers=headers, params={"field": field}, timeout=5, verify=False)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and data.get("value"):
                return data.get("value")

        # 2) /secrets/{name}
        url_secrets = f"{base.rstrip('/')}/api/v3/secrets/{encoded}"
        resp = requests.get(url_secrets, headers=headers, timeout=5, verify=False)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and data.get("value"):
                return data.get("value")

        # 3) applications search -> client_secret
        url_apps = f"{base.rstrip('/')}/api/v3/core/applications/"
        resp = requests.get(url_apps, headers=headers, params={"format": "json", "search": name}, timeout=5, verify=False)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results") if isinstance(data, dict) else None
            if results and isinstance(results, list) and len(results) > 0:
                first = results[0]
                if first.get("client_secret"):
                    return first.get("client_secret")

        # 4) oauth2 providers
        url_prov = f"{base.rstrip('/')}/api/v3/providers/oauth2/"
        resp = requests.get(url_prov, headers=headers, params={"search": name}, timeout=5, verify=False)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results") if isinstance(data, dict) else None
            if results and isinstance(results, list) and len(results) > 0:
                first = results[0]
                if first.get("client_secret"):
                    return first.get("client_secret")

    except Exception:
        # Não propaga erros de rede aqui — chamador decide ação.
        return None

    return None


def _main() -> None:
    import sys
    import json

    if len(sys.argv) < 2:
        print("Uso: authentik_secret_fetcher.py <name> [field]")
        raise SystemExit(1)

    name = sys.argv[1]
    field = sys.argv[2] if len(sys.argv) > 2 else "password"

    val = get_secret_from_authentik(name, field)
    print(json.dumps({"name": name, "field": field, "value": val}))


if __name__ == "__main__":
    _main()
