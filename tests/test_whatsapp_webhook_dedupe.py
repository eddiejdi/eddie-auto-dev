"""Testes do dedupe de eventos de webhook duplicados (WAHA manda "message" +
"message.any" — às vezes redelivery do mesmo evento — pra uma única mensagem
real; sem dedupe isso gera respostas duplicadas)."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock

MODULE_PATH = Path(__file__).resolve().parent.parent / "scripts" / "misc" / "whatsapp_bot.py"


def _load_module():
    module_name = "whatsapp_bot_for_tests"
    cached = sys.modules.get(module_name)
    if cached is not None:
        return cached

    fake_psycopg2 = types.ModuleType("psycopg2")
    fake_extras = types.ModuleType("psycopg2.extras")
    fake_pool = types.ModuleType("psycopg2.pool")
    fake_aiohttp = types.ModuleType("aiohttp")

    class _FakePool:
        def __init__(self, *args, **kwargs):
            pass

    fake_extras.RealDictCursor = object
    fake_pool.SimpleConnectionPool = _FakePool
    fake_aiohttp.web = types.SimpleNamespace(Application=object)

    sys.modules.setdefault("psycopg2", fake_psycopg2)
    sys.modules.setdefault("psycopg2.extras", fake_extras)
    sys.modules.setdefault("psycopg2.pool", fake_pool)
    sys.modules.setdefault("aiohttp", fake_aiohttp)

    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _make_server(wb):
    server = object.__new__(wb.WebhookServer)
    server._recent_message_ids = {}
    server._recent_message_ids_ttl = 300.0
    return server


def test_is_duplicate_message_flags_second_occurrence():
    wb = _load_module()
    server = _make_server(wb)

    assert server._is_duplicate_message("msg-1") is False
    assert server._is_duplicate_message("msg-1") is True
    assert server._is_duplicate_message("msg-2") is False


def test_prunes_old_entries_once_over_cap():
    wb = _load_module()
    server = _make_server(wb)

    for i in range(501):
        server._recent_message_ids[f"old-{i}"] = 0.0  # bem no passado

    assert server._is_duplicate_message("new-msg") is False
    # entradas expiradas (ts=0.0, bem além do TTL) devem ter sido podadas
    assert "old-0" not in server._recent_message_ids
    assert "new-msg" in server._recent_message_ids


def test_process_message_event_skips_duplicate_delivery():
    """Simula WAHA mandando o mesmo message.id duas vezes (message + message.any)
    — só a primeira deve chamar bot.process_message / waha.send_text."""
    wb = _load_module()
    server = _make_server(wb)
    server.bot = types.SimpleNamespace(process_message=AsyncMock(return_value="Bom dia!"))
    server.waha = types.SimpleNamespace(
        mark_as_read=AsyncMock(return_value=None),
        send_text=AsyncMock(return_value={"id": "sent-1"}),
    )

    payload = {
        "id": "true_143430516752629@lid_ABC123_out",
        "timestamp": 1785336241,
        "from": "5511981193899@c.us",
        "fromMe": True,
        "body": "Bom dia",
    }
    event_message_any = {"event": "message.any", "payload": dict(payload)}
    event_message = {"event": "message", "payload": dict(payload)}

    async def run():
        await server.process_message_event(event_message_any)
        await server.process_message_event(event_message)  # mesmo payload.id — deve ser ignorado

    asyncio.run(run())

    server.bot.process_message.assert_awaited_once()
    server.waha.send_text.assert_awaited_once()
