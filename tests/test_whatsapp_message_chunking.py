"""Testes da quebra de mensagens grandes em várias mensagens no WhatsApp bot."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent.parent / "scripts" / "misc" / "whatsapp_bot.py"


def _load_module():
    module_name = "whatsapp_bot_message_chunking_tests"
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


def test_short_text_returns_single_chunk_unchanged():
    mod = _load_module()
    chunks = mod.WAHAClient._split_message_chunks("mensagem curta", max_len=100)
    assert chunks == ["mensagem curta"]


def test_empty_text_returns_no_chunks():
    mod = _load_module()
    assert mod.WAHAClient._split_message_chunks("", max_len=100) == []
    assert mod.WAHAClient._split_message_chunks("   ", max_len=100) == []


def test_splits_on_paragraph_boundary():
    mod = _load_module()
    text = ("a" * 40) + "\n\n" + ("b" * 40) + "\n\n" + ("c" * 40)
    chunks = mod.WAHAClient._split_message_chunks(text, max_len=50)
    assert len(chunks) == 3
    assert chunks[0] == "a" * 40
    assert chunks[1] == "b" * 40
    assert chunks[2] == "c" * 40
    # Nenhuma parte estoura o limite configurado.
    assert all(len(c) <= 50 for c in chunks)


def test_splits_on_word_boundary_without_newlines():
    mod = _load_module()
    text = " ".join(["palavra"] * 20)  # 7 chars + espaço = 8 * 20 - 1 = 159 chars
    chunks = mod.WAHAClient._split_message_chunks(text, max_len=50)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= 50
        # Nunca corta uma palavra ao meio.
        assert not c.startswith(" ") and not c.endswith(" ")
    # Reconstituindo (com espaço entre partes) recupera o texto original.
    assert " ".join(chunks) == text


def test_hard_cut_when_no_whitespace_available():
    mod = _load_module()
    text = "x" * 130
    chunks = mod.WAHAClient._split_message_chunks(text, max_len=50)
    assert len(chunks) == 3
    assert "".join(chunks) == text
    assert all(len(c) <= 50 for c in chunks)


def test_send_text_single_chunk_calls_send_once():
    mod = _load_module()
    waha = mod.WAHAClient.__new__(mod.WAHAClient)
    calls = []

    async def fake_send_chunk(chat_id, text):
        calls.append((chat_id, text))
        return {"status_code": 200}

    waha._send_text_chunk = fake_send_chunk

    result = asyncio.run(waha.send_text("5511999999999@c.us", "mensagem curta"))

    assert len(calls) == 1
    assert calls[0] == ("5511999999999@c.us", "mensagem curta")
    assert result == {"status_code": 200}


def test_send_text_splits_and_numbers_multiple_chunks(monkeypatch):
    mod = _load_module()
    monkeypatch.setattr(mod, "WHATSAPP_MAX_MESSAGE_CHARS", 50)

    waha = mod.WAHAClient.__new__(mod.WAHAClient)
    calls = []

    async def fake_send_chunk(chat_id, text):
        calls.append(text)
        return {"status_code": 200}

    waha._send_text_chunk = fake_send_chunk

    text = " ".join(["palavra"] * 20)
    result = asyncio.run(waha.send_text("5511999999999@c.us", text))

    assert len(calls) > 1
    total = len(calls)
    for i, sent in enumerate(calls, start=1):
        assert sent.startswith(f"({i}/{total}) ")
    assert result == {"status_code": 200}


def test_send_text_aborts_remaining_chunks_on_failure(monkeypatch):
    mod = _load_module()
    monkeypatch.setattr(mod, "WHATSAPP_MAX_MESSAGE_CHARS", 50)

    waha = mod.WAHAClient.__new__(mod.WAHAClient)
    calls = []

    async def fake_send_chunk(chat_id, text):
        calls.append(text)
        if len(calls) == 1:
            return {"error": "boom"}
        return {"status_code": 200}

    waha._send_text_chunk = fake_send_chunk

    text = " ".join(["palavra"] * 20)
    result = asyncio.run(waha.send_text("5511999999999@c.us", text))

    # Parou no primeiro erro — não tentou enviar as partes seguintes.
    assert len(calls) == 1
    assert result == {"error": "boom"}
