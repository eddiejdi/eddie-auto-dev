from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
MODULE_PATH = TOOLS_DIR / "run_daily_agenda_broadcast.py"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TOOLS_DIR))

_SPEC = importlib.util.spec_from_file_location("run_daily_agenda_broadcast", MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
broadcast = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = broadcast
_SPEC.loader.exec_module(broadcast)


def test_resolve_date_aceita_hoje() -> None:
    assert broadcast.resolve_date("hoje") == datetime.now().strftime("%Y-%m-%d")
    assert broadcast.resolve_date("2026-07-09") == "2026-07-09"


def test_build_telegram_summary_inclui_compromissos_e_fontes(monkeypatch) -> None:
    agenda_mod = MagicMock()
    entry = MagicMock()
    entry.time_label = "10h"
    entry.committee_sigla = "CDH"
    entry.entry_type = "committee"
    news = MagicMock()
    news.title = "Flavio em agenda nos EUA"
    news.outlet = "O Globo"
    collected = MagicMock()
    collected.entries = (entry,)
    collected.news = (news,)
    collected.sources_used = ("congresso_nacional", "google_noticias")

    summary = broadcast.build_telegram_summary(
        date_str="2026-07-09",
        collected=collected,
        source_text="Texto fonte",
        final_text="Texto final para locucao.",
        agenda_mod=agenda_mod,
        llm_endpoint="gpu0:mistral:7b",
        tts_backend="piper-gpu",
        quality="balanced",
    )

    assert "Agenda Diária" in summary
    assert "09/07/2026" in summary
    assert "10h" in summary
    assert "CDH" in summary
    assert "O Globo" in summary
    # underscores de free-text são escapados para o Markdown do Telegram
    assert "congresso\\_nacional" in summary or "congresso_nacional" in summary
    assert "gpu0:mistral:7b" in summary
    assert "piper-gpu" in summary
    assert "Texto final para locucao." in summary


def test_escape_telegram_md_protege_caracteres() -> None:
    raw = "titulo_com_underscore e *negrito* e `code`"
    escaped = broadcast._escape_telegram_md(raw)
    assert "\\_" in escaped
    assert "\\*" in escaped
    assert "\\`" in escaped


def test_run_broadcast_dry_run_gera_artefatos(tmp_path, monkeypatch) -> None:
    agenda_mod = MagicMock()
    collected = MagicMock()
    collected.entries = ()
    collected.news = ()
    collected.sources_used = ("snapshot",)
    collected.sources_failed = ()
    agenda_mod.load_entries.return_value = collected
    agenda_mod.build_source_text.return_value = "Texto fonte consolidado."
    agenda_mod.format_date_label.return_value = "esta quinta-feira, 9 de julho de 2026"
    agenda_mod.write_text.side_effect = lambda path, text: path.write_text(text, encoding="utf-8")

    tts_mod = MagicMock()
    tts_mod.normalize_for_speech.side_effect = lambda text: text
    tts_mod.heuristic_rewrite_for_broadcast.side_effect = lambda text: text
    tts_mod.save_text.side_effect = lambda path, text: path.write_text(text + "\n", encoding="utf-8")

    monkeypatch.setattr(
        broadcast,
        "_load_module",
        lambda path, name: agenda_mod if "agenda" in path.name else tts_mod,
    )
    import agenda_media_router as media_router

    media_plan = media_router.resolve_media_plan(
        quality="fast",
        llm_auto_route=False,
        ollama_host="http://localhost:11434",
        ollama_model="gemma3:1b",
        backend_override="none",
    )

    monkeypatch.setattr(
        broadcast,
        "prepare_locution_text",
        lambda *args, **kwargs: ("Texto final.", "gpu1:gemma3:1b"),
    )
    monkeypatch.setattr(broadcast, "send_telegram_message", lambda *args, **kwargs: {"success": True})
    monkeypatch.setattr(broadcast, "send_telegram_audio", lambda *args, **kwargs: {"success": True})

    result = broadcast.run_broadcast(
        date_str="2026-06-17",
        mode="snapshot",
        artifacts_dir=tmp_path,
        timeout=5,
        retries=0,
        trust_env=False,
        include_news=False,
        deep_search=False,
        media_plan=media_plan,
        max_rounds=1,
        retry_wait_seconds=0,
        no_expand=True,
        no_rewrite=True,
        no_normalize=True,
        skip_telegram=True,
        skip_audio=True,
        telegram_chat_id=None,
    )

    assert result.source_text == "Texto fonte consolidado."
    assert result.final_text == "Texto final."
    assert result.source_path.exists()
    assert result.locution_text_path.exists()
    assert result.wav_path is None


def test_send_telegram_audio_mock_http(monkeypatch) -> None:
    from specialized_agents import telegram_notify

    monkeypatch.setattr(telegram_notify, "get_telegram_token", lambda: "token-test")
    monkeypatch.setattr(telegram_notify, "get_telegram_chat_id", lambda: "12345")

    class FakeResponse:
        def read(self) -> bytes:
            return b'{"ok": true, "result": {"message_id": 99}}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(telegram_notify.request, "urlopen", lambda *args, **kwargs: FakeResponse())

    audio_path = Path(__file__).with_name("_tmp_test_audio.wav")
    audio_path.write_bytes(b"RIFFxxxx")
    try:
        result = telegram_notify.send_telegram_audio(str(audio_path))
    finally:
        audio_path.unlink(missing_ok=True)

    assert result["success"] is True
    assert result["message_id"] == 99