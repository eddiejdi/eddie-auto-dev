"""Helpers para envio de notificacoes ao Telegram via Secrets Agent."""

from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from tools.secrets_loader import get_telegram_chat_id, get_telegram_token


def send_telegram_message(
    message: str,
    *,
    chat_id: str | None = None,
    parse_mode: str | None = None,
    disable_web_page_preview: bool = True,
    timeout: int = 10,
) -> dict[str, Any]:
    """Envia uma mensagem para o Telegram usando secrets centralizados."""

    token = get_telegram_token()
    target_chat_id = chat_id or get_telegram_chat_id()

    if not target_chat_id:
        raise RuntimeError("Telegram chat_id not configured in Secrets Agent")

    payload: dict[str, Any] = {
        "chat_id": target_chat_id,
        "text": message,
        "disable_web_page_preview": disable_web_page_preview,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        api_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram API HTTP {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Telegram API unreachable: {exc.reason}") from exc

    data = json.loads(raw)
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API rejected message: {data}")

    return {
        "success": True,
        "chat_id": str(target_chat_id),
        "message_id": data.get("result", {}).get("message_id"),
    }
