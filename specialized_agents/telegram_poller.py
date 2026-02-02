"""
Simple Telegram poller: periodically calls `getUpdates` on the bot,
publishes inbound messages to the Agent Communication Bus so the system
can react to messages sent to the bot.

This is intentionally lightweight and safe for local execution inside
the API process. It keeps track of `update_id` to avoid reprocessing.
"""

import asyncio
import json
import os
import threading
import time
import logging
from typing import Optional

from specialized_agents.agent_communication_bus import (
    get_communication_bus,
    MessageType,
)
from specialized_agents.telegram_client import TelegramClient

logger = logging.getLogger(__name__)


def _log_to_file(line: str, path: str = "/tmp/telegram_poller.log"):
    try:
        with open(path, "a") as f:
            f.write(line + "\n")
    except Exception:
        # best-effort logging; do not crash poller
        pass


_stop_flag = False
_thread: Optional[threading.Thread] = None


def _persist_offset(path: str, offset: int):
    try:
        with open(path, "w") as f:
            f.write(str(offset))
    except Exception:
        pass


def _load_offset(path: str) -> Optional[int]:
    try:
        if os.path.exists(path):
            with open(path) as f:
                return int(f.read().strip())
    except Exception:
        pass
    return None


async def _poll_once(client: TelegramClient, last_offset: Optional[int]):
    try:
        logger.debug("Polling telegram getUpdates with offset=%s", last_offset)
        _log_to_file(f"polling offset={last_offset}")
        res = await client.get_updates(
            offset=last_offset + 1 if last_offset else None, limit=50
        )
        # TelegramClient._request returns a wrapper like {"success": True, "data": [...]}
        if isinstance(res, dict) and res.get("success"):
            updates = res.get("data", []) or res.get("result", [])
        else:
            # fallback to raw telegram structure
            updates = res.get("result", []) if isinstance(res, dict) else []
        logger.debug("Received %d updates", len(updates) if updates is not None else 0)
        _log_to_file(f"received_updates={len(updates) if updates is not None else 0}")
        if not updates:
            return last_offset

        bus = get_communication_bus()
        max_offset = last_offset or 0
        for u in updates:
            uid = u.get("update_id")
            if uid is None:
                continue
            if uid > max_offset:
                max_offset = uid

            # publish the update as a request coming from telegram
            content = json.dumps(u)
            bus.publish(
                MessageType.REQUEST,
                source="telegram",
                target="coordinator",
                content=content,
                metadata={"via_telegram": True},
            )
            _log_to_file(f"processed_update_id={uid}")
            logger.info("Published telegram update_id=%s to bus", uid)

        return max_offset
    except Exception:
        logger.exception("Error while polling telegram updates")
        _log_to_file("poll_error")
        return last_offset


def _poll_loop(
    poll_interval: float = 2.0, offset_file: str = "/tmp/telegram_poller.offset"
):
    global _stop_flag
    client = TelegramClient.from_env()
    if not client.is_configured():
        return
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    last_offset = _load_offset(offset_file)
    logger.info(
        "Starting telegram poller loop (offset_file=%s, start_offset=%s)",
        offset_file,
        last_offset,
    )
    _log_to_file(f"poller_start offset={last_offset}")
    while not _stop_flag:
        try:
            last_offset = loop.run_until_complete(_poll_once(client, last_offset))
            if last_offset:
                _persist_offset(offset_file, last_offset)
                _log_to_file(f"persisted_offset={last_offset}")
        except Exception:
            logger.exception("Unexpected error in poll loop")
            _log_to_file("loop_exception")
        time.sleep(poll_interval)


def start_poller(poll_interval: float = 2.0):
    """Start the telegram poller in a background thread."""
    global _thread, _stop_flag
    if _thread and _thread.is_alive():
        return
    _stop_flag = False
    _thread = threading.Thread(target=_poll_loop, args=(poll_interval,), daemon=True)
    _thread.start()


def stop_poller():
    global _stop_flag, _thread
    _stop_flag = True
    if _thread:
        _thread.join(timeout=1)


__all__ = ["start_poller", "stop_poller"]
