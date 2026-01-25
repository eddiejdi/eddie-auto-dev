"""
Automatic responder for Telegram inbound updates.
Listens on the Agent Communication Bus for messages from `telegram` and
reacts to simple confirmations (e.g. text contains 'sim').

This module publishes requests back to the bus with target="telegram"
so `telegram_bridge` will send messages.
"""
import json
import logging
import html
import os
import requests
from typing import Any

from specialized_agents.agent_communication_bus import get_communication_bus, MessageType
from specialized_agents.telegram_client import TelegramClient

logger = logging.getLogger("telegram_auto_responder")


def _handle_bus_message(message: Any):
    try:
        if message.source != "telegram":
            return

        # message.content is JSON string of the Telegram update
        try:
            update = json.loads(message.content)
        except Exception:
            logger.debug("Could not parse telegram update content")
            return

        # Support multiple update types: message, edited_message, channel_post,
        # edited_channel_post, callback_query (use the nested message), etc.
        msg = None
        update_type = None

        if update.get("message"):
            update_type = "message"
            msg = update.get("message")
        elif update.get("edited_message"):
            update_type = "edited_message"
            msg = update.get("edited_message")
        elif update.get("channel_post"):
            update_type = "channel_post"
            msg = update.get("channel_post")
        elif update.get("edited_channel_post"):
            update_type = "edited_channel_post"
            msg = update.get("edited_channel_post")
        elif update.get("callback_query"):
            update_type = "callback_query"
            cq = update.get("callback_query")
            # callback_query may include data and reference the original message
            msg = cq.get("message") or {}
            # prefer callback data as text when present
            if cq.get("data"):
                # normalize into msg-like structure
                msg = msg.copy() if isinstance(msg, dict) else {}
                msg["text"] = cq.get("data")
                # treat callback sender as from
                msg["from"] = cq.get("from", msg.get("from"))

        if not msg:
            return

        # Prefer explicit text, otherwise use forum/topic name or caption
        text = (msg.get("text") or
                (msg.get("forum_topic_created") or {}).get("name") or
                msg.get("caption") or "").strip()
        from_user = msg.get("from", {})
        user_id = str(from_user.get("id") or from_user.get("user_id") or "")

        # determine incoming chat id (prefer the chat from the update)
        incoming_chat = None
        if msg.get("chat") and msg.get("chat").get("id") is not None:
            incoming_chat = msg.get("chat", {}).get("id")
        else:
            # some updates may include chat_id at top-level or in other fields
            incoming_chat = update.get("chat_id") or msg.get("chat_id")

        incoming_chat = str(incoming_chat) if incoming_chat is not None else None

        # If configured, keep the director chat available as a fallback but
        # prefer replying to the same chat where the message originated.
        client = TelegramClient.from_env()
        director_chat = None
        try:
            director_chat = str(client.config.chat_id) if client and client.config and client.config.chat_id else None
        except Exception:
            director_chat = None

        # Avoid replying to messages sent by bots (including ourselves)
        if from_user.get("is_bot"):
            return

        # Reply to any non-empty user message (was previously only matching 'sim')
        if text:
            # publish a contextual confirmation reply to the originating chat (fallback to director_chat)
            # include sender name when available and escape text to be safe for HTML parse_mode
            sender_name = (from_user.get("first_name") or from_user.get("username") or "").strip()
            if sender_name:
                sender_name = html.escape(sender_name) + ": "
            safe_text = html.escape(text)
            # Try to generate a fluid reply using local Ollama (if available)
            reply_text = None
            ollama_host = os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434")
            ollama_model = os.getenv("OLLAMA_MODEL", "eddie-assistant")
            try:
                prompt = (
                    "Responda de forma natural e conversacional em português. Seja breve e humano.\n"
                    f"Usuário: {text}\nAssistente:"
                )
                r = requests.post(
                    f"{ollama_host}/api/generate",
                    json={"model": ollama_model, "prompt": prompt, "stream": False, "options": {"num_predict": 1}},
                    timeout=8,
                )
                if r.status_code == 200:
                    jr = r.json()
                    # attempt to extract generated text from common keys
                    candidates = []
                    if isinstance(jr, dict):
                        for k in ("output", "generated", "response", "result", "text", "data"):
                            v = jr.get(k)
                            if isinstance(v, str):
                                candidates.append(v)
                            elif isinstance(v, list):
                                for it in v:
                                    if isinstance(it, str):
                                        candidates.append(it)
                                    elif isinstance(it, dict):
                                        for sub in ("text", "content", "output"):
                                            if it.get(sub):
                                                candidates.append(it.get(sub))
                    # fallback: walk nested structure
                    if not candidates:
                        def walk(o):
                            if isinstance(o, str):
                                return o
                            if isinstance(o, dict):
                                for vv in o.values():
                                    res = walk(vv)
                                    if res:
                                        return res
                            if isinstance(o, list):
                                for vv in o:
                                    res = walk(vv)
                                    if res:
                                        return res
                            return None
                        maybe = walk(jr)
                        if isinstance(maybe, str):
                            candidates.append(maybe)

                    if candidates:
                        reply_text = candidates[0]
                else:
                    logger.warning("Ollama /api/generate returned %s: %s", r.status_code, r.text[:200])
            except Exception as e:
                logger.warning("Ollama generate failed (%s) — attempting OpenWebUI fallback", e)
                # Try OpenWebUI (fallback) using API key from repo cofre
                try:
                    from tools.secrets_loader import get_openwebui_api_key
                    openwebui_key = get_openwebui_api_key()
                except Exception:
                    openwebui_key = None

                if openwebui_key:
                    try:
                        openwebui_host = os.getenv("OPENWEBUI_HOST", "http://192.168.15.2:3000")
                        headers = {"Authorization": f"Bearer {openwebui_key}", "Content-Type": "application/json"}
                        ow_payload = {
                            "model": os.getenv("OPENWEBUI_MODEL", "eddie-assistant:latest"),
                            "messages": [{"role": "user", "content": prompt},],
                            "stream": False
                        }
                        r2 = requests.post(f"{openwebui_host}/api/chat/completions", json=ow_payload, headers=headers, timeout=10)
                        if r2.status_code == 200:
                            jr2 = r2.json()
                            # attempt to extract text from choices
                            if isinstance(jr2, dict) and jr2.get("choices"):
                                choice = jr2.get("choices")[0]
                                text = choice.get("message", {}).get("content") if isinstance(choice, dict) else None
                                if text:
                                    reply_text = text
                        else:
                            logger.warning("OpenWebUI /api/chat/completions returned %s: %s", r2.status_code, r2.text[:200])
                    except Exception as e2:
                        logger.warning("OpenWebUI fallback failed (%s)", e2)

            if not reply_text:
                reply_text = f"Recebido: {text}"

            safe_reply = html.escape(reply_text)
            payload = {
                "action": "sendMessage",
                "chat_id": incoming_chat or director_chat,
                "text": f"{sender_name}{safe_reply}",
                "parse_mode": "HTML"
            }
            # if the incoming message belongs to a forum/topic, include thread id
            thread_id = msg.get("message_thread_id")
            if thread_id:
                payload["message_thread_id"] = thread_id
            try:
                get_communication_bus().publish(
                    MessageType.REQUEST,
                    source="auto_responder",
                    target="telegram",
                    content=json.dumps(payload),
                    metadata={"auto": True}
                )
                logger.info("Auto-responder sent confirmation to chat %s", payload.get("chat_id"))
            except Exception:
                logger.exception("Failed to publish auto-responder message")
    except Exception:
        logger.exception("Error handling bus message")


def start_auto_responder():
    bus = get_communication_bus()
    bus.subscribe(_handle_bus_message)
    logger.info("Telegram auto-responder subscribed to bus")

    # Replay recent telegram messages that arrived before the responder started
    try:
        recent = bus.get_messages(limit=200, source="telegram")
        if recent:
            logger.info("Replaying %d recent telegram messages to auto-responder", len(recent))
            for m in recent:
                try:
                    _handle_bus_message(m)
                except Exception:
                    logger.exception("Error replaying bus message to auto-responder")
    except Exception:
        logger.exception("Failed to replay recent telegram messages")


__all__ = ["start_auto_responder"]
