"""
Bridge que conecta o Telegram ao Agent Communication Bus.
Escuta mensagens publicadas com target="telegram" e executa ações (sendMessage, sendPhoto, sendDocument).
"""

import json
import threading
import time
import asyncio
import logging
from typing import Any

from specialized_agents.agent_communication_bus import get_communication_bus
from specialized_agents.telegram_client import TelegramClient
from specialized_agents.telegram_manager import get_telegram_manager

logger = logging.getLogger("telegram_bridge")
logging.basicConfig(level=logging.INFO)


def _handle_message(message: Any):
    # message is AgentMessage
    try:
        if message.target != "telegram":
            return

        # content is expected to be JSON
        payload = {}
        try:
            payload = json.loads(message.content)
        except Exception:
            payload = {"action": "sendMessage", "text": message.content}

        action = payload.get("action", "sendMessage")
        chat_id = payload.get("chat_id")

        # Run the actual send in an asyncio loop in a new task
        def run_async():
            try:
                asyncio.run(_process_action(action, payload, chat_id))
            except Exception as e:
                logger.exception("Error while processing telegram action: %s", e)

        t = threading.Thread(target=run_async, daemon=True)
        t.start()
    except Exception as e:
        logger.exception("Unhandled error in _handle_message: %s", e)


async def _process_action(action: str, payload: dict, chat_id: str = None):
    # allow selecting a bot by key (per-agent bots)
    bot_key = payload.get("bot_key") or payload.get("agent")
    client = None
    try:
        if bot_key:
            mgr = get_telegram_manager()
            client = mgr.get_client(bot_key)

        if client is None:
            client = TelegramClient.from_env()

        # Ensure bridge uses a direct client (bypass TELEGRAM_USE_BUS)
        if not getattr(client, "force_direct", False):
            try:
                client = TelegramClient(client.config, force_direct=True)
            except Exception:
                # fallback: try from_env with force
                client = TelegramClient.from_env(force_direct=True)

        if not client or not client.is_configured():
            logger.warning("Telegram client not configured; skipping action")
            return
    except Exception as e:
        logger.exception("Failed to initialize Telegram client: %s", e)
        return

    if action == "sendMessage":
        text = payload.get("text") or payload.get("message") or ""
        try:
            # Determine final chat target; do not fall back to default config here.
            target_chat = chat_id or payload.get("chat_id")
            if not target_chat:
                logger.warning(
                    "sendMessage skipped: missing chat_id in payload; payload=%s",
                    payload,
                )
                return

            # pass message_thread_id when available so replies appear in the correct forum topic
            thread_id = payload.get("message_thread_id")
            await client.send_message(
                text, chat_id=target_chat, message_thread_id=thread_id
            )
        except Exception as e:
            logger.exception("sendMessage failed: %s", e)
    elif action == "sendPhoto":
        path = payload.get("photo_path")
        caption = payload.get("caption")
        if path:
            try:
                target_chat = chat_id or payload.get("chat_id")
                if not target_chat:
                    logger.warning(
                        "sendPhoto skipped: missing chat_id in payload; payload=%s",
                        payload,
                    )
                    return
                await client.send_photo(path, caption=caption, chat_id=target_chat)
            except Exception as e:
                logger.exception("sendPhoto failed: %s", e)
    elif action == "sendDocument":
        path = payload.get("document_path")
        caption = payload.get("caption")
        if path:
            try:
                target_chat = chat_id or payload.get("chat_id")
                if not target_chat:
                    logger.warning(
                        "sendDocument skipped: missing chat_id in payload; payload=%s",
                        payload,
                    )
                    return
                await client.send_document(path, caption=caption, chat_id=target_chat)
            except Exception as e:
                logger.exception("sendDocument failed: %s", e)
    else:
        # default: send text representation
        try:
            target_chat = chat_id or payload.get("chat_id")
            if not target_chat:
                logger.warning(
                    "default sendMessage skipped: missing chat_id in payload; payload=%s",
                    payload,
                )
                return
            await client.send_message(json.dumps(payload), chat_id=target_chat)
        except Exception as e:
            logger.exception("default sendMessage failed: %s", e)


def start_bridge():
    """Start the bridge by subscribing to the central communication bus.
    This returns immediately after subscription; processing happens in background threads.
    """
    bus = get_communication_bus()
    bus.subscribe(_handle_message)
    print("Telegram bridge subscribed to bus (in-process)")


# Explicit exports
__all__ = ["start_bridge", "main"]


def main():
    start_bridge()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Telegram bridge shutting down")


if __name__ == "__main__":
    main()
