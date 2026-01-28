#!/usr/bin/env python3
"""Agent bridge: consume LLM requests from the Agent Communication Bus and
call OpenWebUI (fallback to Ollama when configured). Publishes LLM responses
back to the bus.
"""
import asyncio
import logging
import time
from typing import Any

from specialized_agents.agent_communication_bus import (
    get_communication_bus,
    MessageType,
    log_llm_call,
    log_llm_response,
)

from openwebui_integration import get_integration_client

logger = logging.getLogger("agent_openwebui_bridge")


def _schedule_coroutine(coro):
    loop = asyncio.get_event_loop()
    if loop.is_running():
        return asyncio.ensure_future(coro)
    else:
        return asyncio.run(coro)


def _handle_message(message: Any):
    try:
        # Only react to requests intended for LLM or openwebui
        if message.target and ("openwebui" in message.target.lower() or message.message_type == MessageType.LLM_CALL):
            prompt = message.content or message.metadata.get("prompt") or ""
            if not prompt:
                return

            # schedule async processing
            _schedule_coroutine(_process_prompt(message.id, message.source, prompt))

    except Exception:
        logger.exception("Error in bus message handler")


async def _process_prompt(msg_id: str, source: str, prompt: str):
    client = get_integration_client()

    # Log LLM call
    log_llm_call("agent_openwebui_bridge", "openwebui", prompt=prompt, model=None)

    # Try WebUI first with retries
    max_retries = 3
    backoff = 1.0
    for attempt in range(1, max_retries + 1):
        try:
            resp = await client.chat_webui(prompt)
            if resp.success:
                log_llm_response("agent_openwebui_bridge", resp.content, model=resp.model, prompt_length=len(prompt))
                return
            else:
                logger.warning("OpenWebUI returned error: %s", resp.error)
                # If API key missing, no need to retry
                if "API Key" in (resp.error or ""):
                    break
        except Exception as e:
            logger.warning("OpenWebUI call failed (attempt %d): %s", attempt, e)

        await asyncio.sleep(backoff)
        backoff *= 2

    # Fallback: try Ollama
    try:
        resp2 = await client.chat_ollama(prompt)
        if resp2.success:
            log_llm_response("agent_openwebui_bridge", resp2.content, model=resp2.model, prompt_length=len(prompt))
            return
        else:
            logger.warning("Ollama fallback error: %s", resp2.error)
            log_llm_response("agent_openwebui_bridge", f"Erro: {resp2.error}", model=resp2.model)
    except Exception as e:
        logger.exception("Ollama fallback failed: %s", e)


def start_openwebui_bridge():
    bus = get_communication_bus()
    bus.subscribe(_handle_message)
    logger.info("OpenWebUI bridge subscribed to bus")

    # Optionally replay recent LLM_CALL messages
    try:
        recent = bus.get_messages(limit=200, message_types=[MessageType.LLM_CALL])
        for m in recent:
            try:
                _handle_message(m)
            except Exception:
                logger.exception("Error replaying message")
    except Exception:
        logger.exception("Failed to replay recent messages")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    start_openwebui_bridge()
    # Keep the process alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
