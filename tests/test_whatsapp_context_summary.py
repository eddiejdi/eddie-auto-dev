"""Testes focados no resumo incremental do WhatsApp bot."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parent.parent / "scripts" / "misc" / "whatsapp_bot.py"


def _load_module():
    """Importa whatsapp_bot com stubs mínimos para dependências opcionais."""
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


def test_chat_session_compacta_em_resumo_incremental() -> None:
    """Sessão deve manter backlog até resumir e depois preservar só contexto útil."""
    wb = _load_module()
    session = wb.ChatSession(chat_id="chat-1")

    for idx in range(16):
        role = "user" if idx % 2 == 0 else "assistant"
        session.add_message(role, f"mensagem {idx}")

    assert session.needs_summary_refresh() is True
    assert len(session.pending_summary_messages) == 4
    assert len(session.messages) == wb.WHATSAPP_CONTEXT_RECENT_MESSAGES

    prompt = session.build_summary_prompt()
    assert prompt is not None
    assert "mensagem 0" in prompt
    assert "mensagem 3" in prompt

    session.apply_summary("Resumo consolidado")

    history = session.get_history()
    assert history[0]["role"] == "system"
    assert "Resumo consolidado" in history[0]["content"]
    assert session.pending_summary_messages == []
    assert len(history) == 1 + len(session.messages)


def test_chat_session_clear_remove_resumo_e_backlog() -> None:
    """Limpar sessão deve resetar resumo e mensagens compactadas."""
    wb = _load_module()
    session = wb.ChatSession(
        chat_id="chat-2",
        rolling_summary="Resumo antigo",
        pending_summary_messages=[{"role": "user", "content": "pendente"}],
        messages=[{"role": "assistant", "content": "recente"}],
    )

    session.clear()

    assert session.messages == []
    assert session.rolling_summary == ""
    assert session.pending_summary_messages == []


def test_refresh_session_summary_aplica_resumo_do_modelo() -> None:
    """Bot deve consolidar backlog quando o modelo retorna resumo válido."""
    wb = _load_module()

    class _FakeOllama:
        async def generate_validated(self, *args, **kwargs):
            return "Resumo consolidado do contexto"

    bot = object.__new__(wb.WhatsAppBot)
    bot.ollama = _FakeOllama()

    session = wb.ChatSession(chat_id="chat-3")
    for idx in range(16):
        role = "user" if idx % 2 == 0 else "assistant"
        session.add_message(role, f"mensagem {idx}")

    asyncio.run(bot.refresh_session_summary(session, "shared-assistant"))

    assert session.rolling_summary == "Resumo consolidado do contexto"
    assert session.pending_summary_messages == []
