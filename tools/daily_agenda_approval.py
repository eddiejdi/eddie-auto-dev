#!/usr/bin/env python3
"""Aprovação humana da agenda diária via Telegram (áudio prévio)."""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from urllib import error, parse, request

from daily_agenda_config import DEFAULT_ARTIFACTS_DIR
from secrets_loader import get_telegram_token

logger = logging.getLogger(__name__)

ApprovalDecision = Literal["approved", "regenerate", "rejected", "timeout", "waiting"]

APPROVAL_FILE = DEFAULT_ARTIFACTS_DIR / "approval_pending.json"
CALLBACK_APPROVE = "dag:A:"
CALLBACK_REGENERATE = "dag:R:"
CALLBACK_REJECT = "dag:X:"
POLL_INTERVAL_SECS = 5
# Bot API limita upload ~50 MiB; margem para multipart + caption.
TELEGRAM_AUDIO_MAX_BYTES = 48 * 1024 * 1024


@dataclass(frozen=True)
class ApprovalState:
    date_str: str
    status: ApprovalDecision
    attempt: int
    deep_search: bool
    message_id: int | None
    audio_message_id: int | None
    created_at: str
    decided_at: str = ""
    decided_by: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "date_str": self.date_str,
            "status": self.status,
            "attempt": self.attempt,
            "deep_search": self.deep_search,
            "message_id": self.message_id,
            "audio_message_id": self.audio_message_id,
            "created_at": self.created_at,
            "decided_at": self.decided_at,
            "decided_by": self.decided_by,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApprovalState:
        return cls(
            date_str=str(data.get("date_str", "")),
            status=data.get("status", "waiting"),  # type: ignore[arg-type]
            attempt=int(data.get("attempt", 1)),
            deep_search=bool(data.get("deep_search", False)),
            message_id=data.get("message_id"),
            audio_message_id=data.get("audio_message_id"),
            created_at=str(data.get("created_at", "")),
            decided_at=str(data.get("decided_at", "")),
            decided_by=str(data.get("decided_by", "")),
        )


def approval_keyboard(date_str: str) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Aprovar e publicar",
                    "callback_data": f"{CALLBACK_APPROVE}{date_str}",
                },
                {
                    "text": "🔍 Gerar de novo",
                    "callback_data": f"{CALLBACK_REGENERATE}{date_str}",
                },
            ],
            [
                {
                    "text": "⏹️ Não publicar / descartar",
                    "callback_data": f"{CALLBACK_REJECT}{date_str}",
                },
            ],
        ]
    }


def load_state(path: Path | None = None) -> ApprovalState | None:
    state_path = path or APPROVAL_FILE
    if not state_path.exists():
        return None
    return ApprovalState.from_dict(json.loads(state_path.read_text(encoding="utf-8")))


def save_state(state: ApprovalState, path: Path | None = None) -> None:
    state_path = path or APPROVAL_FILE
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(state.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _telegram_api(method: str, payload: dict[str, Any], *, timeout: int = 30) -> dict[str, Any]:
    token = get_telegram_token()
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram API HTTP {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Telegram API unreachable: {exc.reason}") from exc

    data = json.loads(raw)
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API rejected {method}: {data}")
    return data.get("result", {})


def build_preview_caption(
    *,
    date_str: str,
    attempt: int,
    deep_search: bool,
    entries_count: int,
    news_count: int,
    quality: str,
) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    mode = "busca profunda" if deep_search else "coleta padrão"
    attempt_label = f" (tentativa {attempt})" if attempt > 1 else ""
    return (
        f"🎧 Prévia — Agenda Diária — {dt.strftime('%d/%m/%Y')}{attempt_label}\n"
        f"Compromissos: {entries_count} | Imprensa: {news_count}\n"
        f"Qualidade: {quality} | Modo: {mode}\n\n"
        "Ouça o áudio e escolha:\n"
        "✅ Aprovar e publicar no YouTube\n"
        "🔍 Gerar de novo com busca mais profunda\n"
        "⏹️ Não publicar / descartar"
    )


def prepare_telegram_audio(wav_path: Path, *, max_bytes: int = TELEGRAM_AUDIO_MAX_BYTES) -> Path:
    """Garante arquivo de áudio abaixo do limite do Bot API (WAV longo → MP3)."""
    wav_path = Path(wav_path)
    if not wav_path.is_file():
        raise FileNotFoundError(f"Áudio não encontrado: {wav_path}")
    size = wav_path.stat().st_size
    if size <= max_bytes:
        return wav_path

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError(
            f"Áudio {size} bytes excede limite Telegram ({max_bytes}) e ffmpeg não está no PATH."
        )

    # ~56 min de mono: 48 kbps ≈ 20 MB; 32 kbps ≈ 13 MB.
    out_path = wav_path.with_suffix(".telegram.mp3")
    for bitrate in ("64k", "48k", "32k", "24k"):
        cmd = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(wav_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "22050",
            "-c:a",
            "libmp3lame",
            "-b:a",
            bitrate,
            str(out_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            logger.warning("ffmpeg bitrate=%s falhou: %s", bitrate, (proc.stderr or "")[-400:])
            continue
        out_size = out_path.stat().st_size
        logger.info(
            "Áudio comprimido para Telegram: %s → %s (%.1f MB @ %s)",
            wav_path.name,
            out_path.name,
            out_size / (1024 * 1024),
            bitrate,
        )
        if out_size <= max_bytes:
            return out_path

    if out_path.is_file() and out_path.stat().st_size <= max_bytes:
        return out_path
    raise RuntimeError(
        f"Não foi possível comprimir {wav_path} abaixo de {max_bytes} bytes para o Telegram."
    )


def send_preview_request(
    *,
    date_str: str,
    summary_text: str,
    wav_path: Path,
    chat_id: str,
    attempt: int,
    deep_search: bool,
    entries_count: int,
    news_count: int,
    quality: str,
) -> ApprovalState:
    caption = build_preview_caption(
        date_str=date_str,
        attempt=attempt,
        deep_search=deep_search,
        entries_count=entries_count,
        news_count=news_count,
        quality=quality,
    )
    keyboard = approval_keyboard(date_str)

    # Texto da locução/notícias costuma quebrar Markdown legado; tenta Markdown e
    # cai para texto puro se a API recusar parse de entities.
    try:
        summary_result = _telegram_api(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": summary_text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
                "reply_markup": keyboard,
            },
        )
    except RuntimeError as exc:
        if "can't parse entities" not in str(exc).lower() and "parse entities" not in str(exc).lower():
            raise
        logger.warning("Markdown rejeitado pelo Telegram; reenviando prévia em texto puro.")
        summary_result = _telegram_api(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": summary_text,
                "disable_web_page_preview": True,
                "reply_markup": keyboard,
            },
        )

    audio_path = prepare_telegram_audio(Path(wav_path))
    with audio_path.open("rb") as handle:
        audio_bytes = handle.read()

    filename = audio_path.name
    content_type = "audio/mpeg" if audio_path.suffix.lower() == ".mp3" else "application/octet-stream"

    boundary = "----eddieAgendaApprovalBoundary"
    body_parts: list[bytes] = []

    def add_field(name: str, value: str) -> None:
        body_parts.append(f"--{boundary}\r\n".encode())
        body_parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body_parts.append(value.encode("utf-8"))
        body_parts.append(b"\r\n")

    add_field("chat_id", str(chat_id))
    add_field("caption", caption)
    add_field("reply_markup", json.dumps(keyboard, ensure_ascii=False))

    body_parts.append(f"--{boundary}\r\n".encode())
    body_parts.append(
        f'Content-Disposition: form-data; name="audio"; filename="{filename}"\r\n'.encode()
    )
    body_parts.append(f"Content-Type: {content_type}\r\n\r\n".encode())
    body_parts.append(audio_bytes)
    body_parts.append(b"\r\n")
    body_parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(body_parts)

    token = get_telegram_token()
    req = request.Request(
        f"https://api.telegram.org/bot{token}/sendAudio",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=300) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram sendAudio HTTP {exc.code}: {details}") from exc

    audio_data = json.loads(raw)
    if not audio_data.get("ok"):
        raise RuntimeError(f"Telegram sendAudio rejected: {audio_data}")

    state = ApprovalState(
        date_str=date_str,
        status="waiting",
        attempt=attempt,
        deep_search=deep_search,
        message_id=summary_result.get("message_id"),
        audio_message_id=audio_data.get("result", {}).get("message_id"),
        created_at=datetime.now().isoformat(timespec="seconds"),
    )
    save_state(state)
    return state


def _parse_callback_data(data: str) -> tuple[ApprovalDecision, str] | None:
    if data.startswith(CALLBACK_APPROVE):
        return "approved", data[len(CALLBACK_APPROVE) :]
    if data.startswith(CALLBACK_REGENERATE):
        return "regenerate", data[len(CALLBACK_REGENERATE) :]
    if data.startswith(CALLBACK_REJECT):
        return "rejected", data[len(CALLBACK_REJECT) :]
    return None


def handle_telegram_callback(callback: dict[str, Any]) -> bool:
    """Processa callback dag:* e atualiza approval_pending.json."""
    data = callback.get("data", "")
    parsed = _parse_callback_data(data)
    if parsed is None:
        return False

    decision, date_str = parsed
    state = load_state()
    if state is None or state.date_str != date_str or state.status != "waiting":
        _telegram_api(
            "answerCallbackQuery",
            {
                "callback_query_id": callback.get("id", ""),
                "text": "Solicitação expirada ou já respondida.",
                "show_alert": True,
            },
        )
        return True

    user = callback.get("from", {}) or {}
    decided_by = user.get("username") or user.get("first_name") or "usuario"
    updated = ApprovalState(
        date_str=state.date_str,
        status=decision,
        attempt=state.attempt,
        deep_search=state.deep_search,
        message_id=state.message_id,
        audio_message_id=state.audio_message_id,
        created_at=state.created_at,
        decided_at=datetime.now().isoformat(timespec="seconds"),
        decided_by=str(decided_by),
    )
    save_state(updated)

    if decision == "approved":
        note = "Aprovado — publicando..."
        status_line = "✅ Aprovado"
    elif decision == "regenerate":
        note = "Regenerando com busca profunda..."
        status_line = "🔍 Nova geração solicitada"
    else:
        note = "Descartado — não publica."
        status_line = "⏹️ Não publicada (descartada)"
    _telegram_api(
        "answerCallbackQuery",
        {"callback_query_id": callback.get("id", ""), "text": note},
    )

    msg = callback.get("message") or {}
    msg_id = msg.get("message_id")
    chat_id = (msg.get("chat") or {}).get("id")
    if msg_id and chat_id:
        _telegram_api(
            "editMessageReplyMarkup",
            {
                "chat_id": chat_id,
                "message_id": msg_id,
                "reply_markup": {"inline_keyboard": []},
            },
        )
        _telegram_api(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": f"{status_line} — agenda {date_str} por @{decided_by}",
                "disable_web_page_preview": True,
            },
        )
    return True


def _poll_telegram_updates(offset: int, *, timeout: int = 25) -> tuple[int, list[dict[str, Any]]]:
    token = get_telegram_token()
    query = parse.urlencode({
        "offset": offset,
        "timeout": timeout,
        "allowed_updates": json.dumps(["callback_query"]),
    })
    req = request.Request(
        f"https://api.telegram.org/bot{token}/getUpdates?{query}",
        method="GET",
    )
    try:
        with request.urlopen(req, timeout=timeout + 5) as response:
            raw = response.read().decode("utf-8")
    except (error.URLError, TimeoutError):
        return offset, []

    payload = json.loads(raw)
    if not payload.get("ok"):
        return offset, []

    updates = payload.get("result", [])
    next_offset = offset
    for item in updates:
        next_offset = max(next_offset, int(item.get("update_id", 0)) + 1)
    return next_offset, updates


def wait_for_decision(
    *,
    date_str: str,
    timeout_minutes: int,
    poll_telegram: bool = True,
) -> ApprovalDecision:
    state = load_state()
    if state and state.date_str == date_str and state.status != "waiting":
        return state.status

    deadline = time.time() + max(1, timeout_minutes) * 60
    offset = 0

    while time.time() < deadline:
        state = load_state()
        if state and state.date_str == date_str and state.status != "waiting":
            return state.status

        if poll_telegram:
            offset, updates = _poll_telegram_updates(offset)
            for item in updates:
                callback = item.get("callback_query")
                if callback:
                    handle_telegram_callback(callback)
            state = load_state()
            if state and state.date_str == date_str and state.status != "waiting":
                return state.status

        time.sleep(POLL_INTERVAL_SECS)

    expired = load_state()
    if expired and expired.date_str == date_str:
        save_state(
            ApprovalState(
                date_str=expired.date_str,
                status="timeout",
                attempt=expired.attempt,
                deep_search=expired.deep_search,
                message_id=expired.message_id,
                audio_message_id=expired.audio_message_id,
                created_at=expired.created_at,
                decided_at=datetime.now().isoformat(timespec="seconds"),
                decided_by="timeout",
            )
        )
    return "timeout"