"""Testes do tool-calling do WhatsApp bot (OllamaClient.chat_with_tools e
WhatsAppBot._process_with_tools) — segue o padrão de importlib+stub de
tests/test_whatsapp_context_summary.py."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, patch

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
    fake_aiohttp.web = types.SimpleNamespace()

    sys.modules.setdefault("psycopg2", fake_psycopg2)
    sys.modules.setdefault("psycopg2.extras", fake_extras)
    sys.modules.setdefault("psycopg2.pool", fake_pool)
    sys.modules.setdefault("aiohttp", fake_aiohttp)

    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


# ── OllamaClient.chat_with_tools ─────────────────────────────────────────


def test_chat_with_tools_sends_tools_and_parses_tool_calls():
    wb = _load_module()
    client = object.__new__(wb.OllamaClient)
    client.host = "http://fake-ollama"

    captured = {}

    async def fake_post(url, json):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse(200, {
            "message": {
                "content": "",
                "tool_calls": [
                    {"function": {"name": "trading_summary", "arguments": {"symbol": "BTC-USDT"}}}
                ],
            }
        })

    client.client = types.SimpleNamespace(post=fake_post)
    schema = [{"type": "function", "function": {"name": "trading_summary", "parameters": {}}}]

    content, tool_calls = asyncio.run(
        client.chat_with_tools([{"role": "user", "content": "resume o trading"}], model="shared-homelab", tools=schema)
    )

    assert captured["json"]["tools"] == schema
    assert content == ""
    assert tool_calls == [{"function": {"name": "trading_summary", "arguments": {"symbol": "BTC-USDT"}}}]


def test_chat_with_tools_no_tool_calls_returns_empty_list():
    wb = _load_module()
    client = object.__new__(wb.OllamaClient)
    client.host = "http://fake-ollama"

    async def fake_post(url, json):
        return _FakeResponse(200, {"message": {"content": "Bom dia!"}})

    client.client = types.SimpleNamespace(post=fake_post)

    content, tool_calls = asyncio.run(
        client.chat_with_tools([{"role": "user", "content": "oi"}], model="shared-homelab")
    )
    assert content == "Bom dia!"
    assert tool_calls == []


def test_chat_with_tools_http_error():
    wb = _load_module()
    client = object.__new__(wb.OllamaClient)
    client.host = "http://fake-ollama"

    async def fake_post(url, json):
        return _FakeResponse(500, {})

    client.client = types.SimpleNamespace(post=fake_post)

    content, tool_calls = asyncio.run(client.chat_with_tools([], model="shared-homelab"))
    assert "Erro" in content
    assert tool_calls == []


# ── WhatsAppBot._process_with_tools ──────────────────────────────────────


def _make_bot(wb):
    bot = object.__new__(wb.WhatsAppBot)
    bot._notifier = None
    return bot


def test_process_with_tools_executes_safe_tool_then_returns_final_content():
    wb = _load_module()
    bot = _make_bot(wb)

    calls = []

    async def fake_chat_with_tools(messages, model, system, tools):
        calls.append(list(messages))
        if len(calls) == 1:
            return "", [{"function": {"name": "trading_summary", "arguments": {"symbol": "BTC-USDT"}}}]
        return "O trading está indo bem.", []

    bot.ollama = types.SimpleNamespace(chat_with_tools=fake_chat_with_tools)

    with patch.object(wb.mcp_tool_bridge, "build_ollama_tool_schemas", return_value=[]), \
         patch.object(wb.mcp_tool_bridge, "is_gated", return_value=False), \
         patch.object(wb.mcp_tool_bridge, "execute_safe", return_value={"ok": True, "symbol": "BTC-USDT"}) as fake_exec, \
         patch.object(wb.mcp_tool_bridge, "declare_gate") as fake_declare:

        response = asyncio.run(
            bot._process_with_tools(
                [{"role": "user", "content": "resume o trading"}],
                "shared-homelab", "system prompt", "5511981193899@c.us",
            )
        )

    fake_exec.assert_called_once_with("trading_summary", {"symbol": "BTC-USDT"})
    fake_declare.assert_not_called()
    assert response == "O trading está indo bem."
    # segunda chamada ao modelo deve incluir a mensagem role=tool com o resultado
    tool_messages = [m for m in calls[1] if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    assert "BTC-USDT" in tool_messages[0]["content"]


def test_process_with_tools_no_tool_call_returns_content_immediately():
    wb = _load_module()
    bot = _make_bot(wb)

    async def fake_chat_with_tools(messages, model, system, tools):
        return "Bom dia! Como posso ajudar?", []

    bot.ollama = types.SimpleNamespace(chat_with_tools=fake_chat_with_tools)

    with patch.object(wb.mcp_tool_bridge, "build_ollama_tool_schemas", return_value=[]):
        response = asyncio.run(
            bot._process_with_tools([{"role": "user", "content": "bom dia"}], "shared-homelab", "sys", "chat-1")
        )

    assert response == "Bom dia! Como posso ajudar?"


def test_process_with_tools_gated_tool_declares_intent_and_spawns_task_without_executing():
    """O teste mais importante deste arquivo: ferramenta arriscada nunca é
    executada de dentro do loop — só é declarada e delegada a uma task de
    fundo; o turno atual só devolve o ack de aprovação pendente."""
    wb = _load_module()
    bot = _make_bot(wb)

    async def fake_chat_with_tools(messages, model, system, tools):
        return "", [{"function": {"name": "secrets_get", "arguments": {"name": "eddie/foo"}}}]

    bot.ollama = types.SimpleNamespace(chat_with_tools=fake_chat_with_tools)

    created_tasks = []

    def fake_create_task(coro):
        created_tasks.append(coro)
        coro.close()  # evita "coroutine was never awaited"; não queremos rodar de verdade
        return object()

    with patch.object(wb.mcp_tool_bridge, "build_ollama_tool_schemas", return_value=[]), \
         patch.object(wb.mcp_tool_bridge, "is_gated", return_value=True), \
         patch.object(wb.mcp_tool_bridge, "execute_safe") as fake_exec_safe, \
         patch.object(wb.mcp_tool_bridge, "declare_gate", return_value="intent-abc") as fake_declare, \
         patch.object(wb.asyncio, "create_task", side_effect=fake_create_task):

        response = asyncio.run(
            bot._process_with_tools(
                [{"role": "user", "content": "me mostra o segredo eddie/foo"}],
                "shared-homelab", "sys", "5511981193899@c.us",
            )
        )

    fake_exec_safe.assert_not_called()
    fake_declare.assert_called_once()
    assert fake_declare.call_args[0][0] == "secrets_get"
    assert len(created_tasks) == 1
    assert "requer sua aprovação" in response
    assert "secrets_get" in response


def test_process_with_tools_stops_after_max_rounds():
    wb = _load_module()
    bot = _make_bot(wb)

    async def always_calls_tool(messages, model, system, tools):
        return "", [{"function": {"name": "trading_summary", "arguments": {}}}]

    bot.ollama = types.SimpleNamespace(chat_with_tools=always_calls_tool)

    with patch.object(wb.mcp_tool_bridge, "build_ollama_tool_schemas", return_value=[]), \
         patch.object(wb.mcp_tool_bridge, "is_gated", return_value=False), \
         patch.object(wb.mcp_tool_bridge, "execute_safe", return_value={"ok": True}), \
         patch.object(wb, "MAX_TOOL_ROUNDS", 2):

        response = asyncio.run(
            bot._process_with_tools([{"role": "user", "content": "oi"}], "shared-homelab", "sys", "chat-1")
        )

    assert "não consegui concluir" in response.lower()


# ── Kill-switch do tool-calling ──────────────────────────────────────────


def test_tool_calling_disabled_by_default():
    """Default DESLIGADO: o llama3.1:8b base escolhe ferramenta errada (medido
    em produção — pediu `bus_publish` para um pedido de Google Calendar), o que
    é pior que a resposta conversacional anterior. Só religar (WHATSAPP_TOOL_CALLING=1)
    depois do candidato treinado passar no shadow-eval."""
    wb = _load_module()
    assert wb.TOOL_CALLING_ENABLED is False
