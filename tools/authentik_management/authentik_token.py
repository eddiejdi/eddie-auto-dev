#!/usr/bin/env python3
"""Resolve o token da API do Authentik sem hardcodar segredo.

Ordem de resolução:
  1. env AUTHENTIK_TOKEN
  2. /etc/systemd/system/secrets_agent.service.d/override.conf (homelab, canônico)
  3. secrets_agent local (http://localhost:8088/secrets/authentik/api_token)
  4. vazio

Uso:
  from authentik_token import resolve_token
  token = resolve_token()
"""
from __future__ import annotations

import json
import os
import re

try:
    from urllib.request import urlopen
except ImportError:  # pragma: no cover
    urlopen = None

OVERRIDE_CONF = "/etc/systemd/system/secrets_agent.service.d/override.conf"
SECRETS_AGENT_URL = "http://localhost:8088/secrets/authentik/api_token"


def _from_override_conf() -> str:
    if not os.path.exists(OVERRIDE_CONF):
        return ""
    try:
        with open(OVERRIDE_CONF) as fh:
            txt = fh.read()
        match = re.search(r'AUTHENTIK_TOKEN="?([^"\n]+)"?', txt)
        return match.group(1).strip() if match else ""
    except Exception:
        return ""


def _from_secrets_agent() -> str:
    if not urlopen:
        return ""
    try:
        with urlopen(SECRETS_AGENT_URL, timeout=5) as resp:
            payload = json.loads(resp.read().decode())
        data = payload.get("data", payload)
        value = data.get("value") if isinstance(data, dict) else None
        return str(value).strip() if value else ""
    except Exception:
        return ""


def resolve_token() -> str:
    env = os.environ.get("AUTHENTIK_TOKEN", "").strip()
    if env:
        return env
    return _from_override_conf() or _from_secrets_agent()


if __name__ == "__main__":
    resolved = resolve_token()
    print(f"token_len={len(resolved)} prefix={resolved[:6]}..." if resolved else "token=<vazio>")