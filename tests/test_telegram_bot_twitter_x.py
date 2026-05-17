"""Testes unitários do fluxo /x no bot do Telegram."""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from typing import Any

# Garante import do módulo raiz do projeto durante execução do pytest.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from telegram_bot import TelegramBot


class FakeTelegramAPI:
    """API fake para validar chamadas de envio sem acessar Telegram real."""

    def __init__(self) -> None:
        self.messages: list[str] = []
        self.photos: list[str] = []
        self.videos: list[str] = []
        self.documents: list[str] = []
        self.deleted_ids: list[int] = []

    async def send_message(self, chat_id: int, text: str, reply_to_message_id: int | None = None) -> dict[str, Any]:
        self.messages.append(text)
        if text.startswith("⏳"):
            return {"ok": True, "result": {"message_id": 9001}}
        return {"ok": True, "result": {"message_id": 9002}}

    async def send_chat_action(self, chat_id: int, action: str = "typing") -> dict[str, Any]:
        return {"ok": True, "result": True}

    async def edit_message_text(self, chat_id: int, message_id: int, text: str, parse_mode: str = "Markdown") -> dict[str, Any]:
        self.messages.append(text)
        return {"ok": True, "result": True}

    async def delete_message(self, chat_id: int, message_id: int) -> dict[str, Any]:
        self.deleted_ids.append(message_id)
        return {"ok": True, "result": True}

    async def send_photo_file(self, chat_id: int, file_path: str, caption: str | None = None) -> dict[str, Any]:
        self.photos.append(file_path)
        return {"ok": True, "result": {"photo": True}}

    async def send_video_file(
        self,
        chat_id: int,
        file_path: str,
        caption: str | None = None,
        reply_to_message_id: int | None = None,
    ) -> dict[str, Any]:
        self.videos.append(file_path)
        return {"ok": True, "result": {"video": True}}

    async def send_document_file(self, chat_id: int, file_path: str, caption: str | None = None) -> dict[str, Any]:
        self.documents.append(file_path)
        return {"ok": True, "result": {"document": True}}


def _build_bot_with_fake_api() -> tuple[TelegramBot, FakeTelegramAPI]:
    """Cria instância de TelegramBot sem __init__ para testes unitários isolados."""
    bot = TelegramBot.__new__(TelegramBot)
    fake_api = FakeTelegramAPI()
    bot.api = fake_api
    return bot, fake_api


def test_handle_twitter_download_envia_texto_e_todas_as_midias(tmp_path: Path) -> None:
    """Quando fxtwitter retorna texto + mídias, o bot envia ambos."""
    bot, fake_api = _build_bot_with_fake_api()

    async def fake_fx(user: str, tweet_id: str) -> tuple[str | None, list[dict[str, str]]]:
        return (
            "Post com 2 mídias",
            [
                {"url": "https://cdn.exemplo.com/m1.jpg", "kind": "photo"},
                {"url": "https://cdn.exemplo.com/m2.mp4", "kind": "video"},
            ],
        )

    async def fake_download(url: str, tmp_dir: str, filename: str) -> str | None:
        file_path = tmp_path / filename
        file_path.write_bytes(b"a" * 2048)
        return str(file_path)

    async def fake_ytdlp(url: str, tmp_dir: str, tweet_id: str) -> list[str]:
        return []

    bot._fxtwitter_get_post_data = fake_fx  # type: ignore[attr-defined]
    bot._download_file = fake_download  # type: ignore[attr-defined]
    bot._ytdlp_download = fake_ytdlp  # type: ignore[attr-defined]

    asyncio.run(bot._handle_twitter_download(123, 456, "https://x.com/user/status/123456789"))

    assert any("Texto do post" in msg for msg in fake_api.messages)
    assert len(fake_api.photos) == 1
    assert len(fake_api.videos) == 1
    assert fake_api.deleted_ids == [9001]


def test_handle_twitter_download_fallback_ytdlp_quando_fxtwitter_sem_midia(tmp_path: Path) -> None:
    """Se fxtwitter não trouxer mídia, o bot usa fallback do yt-dlp."""
    bot, fake_api = _build_bot_with_fake_api()

    photo_path = tmp_path / "fallback_1.jpg"
    video_path = tmp_path / "fallback_2.mp4"
    photo_path.write_bytes(b"p" * 4096)
    video_path.write_bytes(b"v" * 4096)

    async def fake_fx(user: str, tweet_id: str) -> tuple[str | None, list[dict[str, str]]]:
        return None, []

    async def fake_ytdlp(url: str, tmp_dir: str, tweet_id: str) -> list[str]:
        return [str(photo_path), str(video_path)]

    async def fake_download(url: str, tmp_dir: str, filename: str) -> str | None:
        return None

    bot._fxtwitter_get_post_data = fake_fx  # type: ignore[attr-defined]
    bot._ytdlp_download = fake_ytdlp  # type: ignore[attr-defined]
    bot._download_file = fake_download  # type: ignore[attr-defined]

    asyncio.run(bot._handle_twitter_download(999, 111, "https://x.com/user/status/2222"))

    assert len(fake_api.photos) == 1
    assert len(fake_api.videos) == 1
    assert not any("Texto do post" in msg for msg in fake_api.messages)


def test_extract_twitter_status_url_detecta_link_em_texto_livre() -> None:
    """A detecção deve encontrar URL válida mesmo sem comando /x."""
    bot, _ = _build_bot_with_fake_api()

    text = "Olha isso aqui: https://x.com/alguem/status/1234567890?s=20, muito bom"
    detected = bot._extract_twitter_status_url(text)

    assert detected == "https://x.com/alguem/status/1234567890?s=20"


def test_handle_message_dispara_fluxo_twitter_sem_comando_x() -> None:
    """Mensagem normal com link de post deve acionar handler do Twitter."""
    bot, _ = _build_bot_with_fake_api()
    called: dict[str, Any] = {}

    async def fake_handler(chat_id: int, msg_id: int, args: str) -> None:
        called["chat_id"] = chat_id
        called["msg_id"] = msg_id
        called["args"] = args

    bot._handle_twitter_download = fake_handler  # type: ignore[attr-defined]

    message = {
        "chat": {"id": 10},
        "from": {"id": 20, "first_name": "Teste"},
        "message_id": 30,
        "text": "https://twitter.com/user/status/987654321",
    }

    asyncio.run(bot.handle_message(message))

    assert called["chat_id"] == 10
    assert called["msg_id"] == 30
    assert called["args"] == "https://twitter.com/user/status/987654321"
