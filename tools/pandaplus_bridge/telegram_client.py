"""Cliente Telegram minimalista (sendMessage + answerCallbackQuery).

Não usa python-telegram-bot para evitar conflito de getUpdates com o bot
principal. Apenas envia mensagens e edita; o consumo de callback_query é
delegado a um endpoint HTTP local que o bot principal alimenta via patch
opcional (ver README).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class TelegramSender:
    """Cliente HTTP assíncrono para envio de mensagens Telegram.

    Args:
        token: Token do bot.
        timeout: Timeout HTTP em segundos.
    """

    def __init__(self, token: str, timeout: float = 10.0) -> None:
        if not token:
            raise ValueError("token Telegram vazio")
        self._token = token
        self._base = f"https://api.telegram.org/bot{token}"
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "TelegramSender":
        self._client = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _post(self, method: str, payload: dict) -> dict:
        """Faz POST ao endpoint Telegram e retorna o `result`.

        Args:
            method: Nome do método Telegram (ex: ``sendMessage``).
            payload: Corpo JSON da chamada.

        Returns:
            Conteúdo de ``result`` no JSON de resposta.

        Raises:
            RuntimeError: Se Telegram retornar ``ok=false``.
        """
        if self._client is None:
            raise RuntimeError("TelegramSender não inicializado (use async with)")
        url = f"{self._base}/{method}"
        resp = await self._client.post(url, json=payload)
        try:
            data = resp.json()
        except ValueError as exc:
            raise RuntimeError(
                f"Telegram resposta não-JSON ({resp.status_code})"
            ) from exc
        if not data.get("ok"):
            raise RuntimeError(
                f"Telegram {method} falhou: "
                f"{data.get('error_code')} {data.get('description')}"
            )
        return data.get("result", {})

    async def send_unlock_request(
        self,
        chat_id: int,
        request_token: str,
        unlock_request_seconds: int,
        alarm: str | None = None,
        observe_only: bool = True,
    ) -> dict:
        """Envia notificação de pedido de abertura com botões inline.

        Args:
            chat_id: Chat destino.
            request_token: Token único do pedido (usado em callback_data).
            unlock_request_seconds: Segundos restantes do pedido.
            alarm: Código de alarme opcional (wrong_finger, etc.).
            observe_only: Se True, botões viram apenas "Visualizar log".

        Returns:
            Mensagem enviada (com ``message_id``).
        """
        lines = ["🔔 *Pedido de abertura da porta*"]
        lines.append(f"⏳ Válido por *{unlock_request_seconds}s*")
        if alarm:
            lines.append(f"⚠️ Alarme: `{alarm}`")
        if observe_only:
            lines.append("\n_Modo observação ativo — aprovação desabilitada._")

        if observe_only:
            keyboard = {
                "inline_keyboard": [[
                    {
                        "text": "📋 Ver detalhes",
                        "callback_data": f"pdpls:info:{request_token}",
                    },
                ]]
            }
        else:
            keyboard = {
                "inline_keyboard": [[
                    {
                        "text": "✅ Aprovar",
                        "callback_data": f"pdpls:approve:{request_token}",
                    },
                    {
                        "text": "❌ Negar",
                        "callback_data": f"pdpls:deny:{request_token}",
                    },
                ]]
            }

        return await self._post(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": "\n".join(lines),
                "parse_mode": "Markdown",
                "reply_markup": keyboard,
            },
        )

    async def send_event(self, chat_id: int, text: str) -> dict:
        """Envia mensagem simples (eventos informativos).

        Args:
            chat_id: Chat destino.
            text: Texto Markdown.

        Returns:
            Mensagem enviada.
        """
        return await self._post(
            "sendMessage",
            {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
        )

    async def edit_message(
        self, chat_id: int, message_id: int, text: str
    ) -> dict:
        """Edita mensagem existente (usado após decisão).

        Args:
            chat_id: Chat destino.
            message_id: ID da mensagem a editar.
            text: Novo texto Markdown.

        Returns:
            Mensagem editada.
        """
        return await self._post(
            "editMessageText",
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": "Markdown",
            },
        )
