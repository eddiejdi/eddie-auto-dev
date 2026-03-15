"""Helpers para montar credenciais Gmail a partir do Secrets Agent."""

from __future__ import annotations

import ast
import base64
import json
import logging
from typing import Any, Sequence

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials

from tools.secrets_agent_client import get_secrets_agent_client

logger = logging.getLogger(__name__)

DEFAULT_GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def _decode_token_mapping(raw_token: Any) -> dict[str, Any]:
    if isinstance(raw_token, dict):
        return raw_token

    queue: list[str] = []
    if isinstance(raw_token, bytes):
        queue.append(raw_token.decode("utf-8", errors="replace").strip())
    elif isinstance(raw_token, str):
        queue.append(raw_token.strip())
    else:
        raise RuntimeError("Token Gmail em formato inválido.")

    seen: set[str] = set()
    while queue:
        current = queue.pop(0).strip()
        if not current or current in seen:
            continue
        seen.add(current)

        try:
            parsed = json.loads(current)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, str):
            queue.append(parsed)

        try:
            decoded = base64.b64decode(current, validate=True).decode("utf-8")
        except Exception:
            decoded = None
        if decoded:
            queue.append(decoded)

        try:
            literal = ast.literal_eval(current)
        except Exception:
            literal = None
        if isinstance(literal, dict):
            return literal
        if isinstance(literal, str):
            queue.append(literal)

    raise RuntimeError("Token Gmail inválido ou em formato não suportado.")


def load_gmail_credentials(secret_names: Sequence[str], scopes: Sequence[str] | None = None) -> Credentials:
    client = get_secrets_agent_client()
    raw_token = None
    resolved_secret = None
    try:
        for secret_name in secret_names:
            raw_token = client.get_local_secret(secret_name, field="token_json")
            if raw_token:
                resolved_secret = f"{secret_name}:local"
                break
            raw_token = client.get_secret(secret_name, field="token_json")
            if raw_token:
                resolved_secret = f"{secret_name}:fallback"
                break
    finally:
        client.close()

    if not raw_token:
        raise RuntimeError("Token Gmail não encontrado no Secrets Agent.")

    token_data = _decode_token_mapping(raw_token)
    logger.info("Token Gmail carregado do Secrets Agent via %s", resolved_secret)

    creds = Credentials(
        token=token_data.get("access_token") or token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=list(token_data.get("scopes") or scopes or DEFAULT_GMAIL_SCOPES),
    )

    if not creds.valid and creds.refresh_token:
        creds.refresh(GoogleAuthRequest())

    return creds
