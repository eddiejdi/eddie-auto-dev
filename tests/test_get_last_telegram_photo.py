"""Testes unitários para `tools.get_last_telegram_photo`.

Os testes usam injeção de dependência para simular respostas do MCP sem acessar
o Telegram ou Ollama.
"""
from pathlib import Path
import sys
from pathlib import Path as _P

# Garantir que o diretório do projeto esteja no sys.path durante execução dos testes
sys.path.insert(0, str(_P(__file__).resolve().parents[1]))

from tools.get_last_telegram_photo import fetch_latest_photo_path


def test_fetch_latest_photo_returns_local_path_when_present() -> None:
    """Se a mensagem já contém `local_path`, deve retornar esse caminho."""

    def fake_mcp_call(tool: str, params: dict):
        if tool == "tg_latest":
            return {
                "messages": [
                    {"type": "text", "text": "oi"},
                    {"type": "photo", "file_id": "F1", "local_path": "/tmp/tg_media/F1.jpg"},
                ]
            }
        return {}

    p = fetch_latest_photo_path(n=5, analyze_media=True, mcp_call=fake_mcp_call)
    assert p == Path("/tmp/tg_media/F1.jpg")


def test_fetch_latest_photo_fallbacks_to_tg_analyze_when_no_local_path() -> None:
    """Se `local_path` não existir, deve chamar `tg_analyze` e retornar `local_path` do resultado."""

    calls = {}

    def fake_mcp_call(tool: str, params: dict):
        calls.setdefault(tool, 0)
        calls[tool] += 1
        if tool == "tg_latest":
            return {"messages": [{"type": "photo", "file_id": "F2"}]}
        if tool == "tg_analyze":
            return {"file_id": "F2", "local_path": "/tmp/tg_media/F2.jpg", "analysis": "ok"}
        return {}

    p = fetch_latest_photo_path(n=3, analyze_media=False, mcp_call=fake_mcp_call)
    assert p == Path("/tmp/tg_media/F2.jpg")
    assert calls.get("tg_latest", 0) >= 1
    assert calls.get("tg_analyze", 0) >= 1


def test_fetch_latest_photo_returns_none_when_no_photo() -> None:
    """Retorna None se não houver mensagens do tipo foto."""

    def fake_mcp_call(tool: str, params: dict):
        return {"messages": [{"type": "text", "text": "sem foto"}]}

    p = fetch_latest_photo_path(mcp_call=fake_mcp_call)
    assert p is None
