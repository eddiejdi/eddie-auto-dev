#!/usr/bin/env python3
"""Publica a locução da agenda diária no canal YouTube."""
from __future__ import annotations

import json
import logging
import pickle
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from daily_agenda_config import load_config, resolve_repo_path

logger = logging.getLogger(__name__)

YOUTUBE_SCOPES = (
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
)
READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
MANAGE_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"


@dataclass(frozen=True)
class YouTubePublishResult:
    video_id: str
    video_url: str
    title: str
    privacy_status: str


def _load_credentials(credentials_file: Path, token_file: Path):
    try:
        from google.auth.transport.requests import Request
    except ImportError as exc:
        raise RuntimeError(
            "Dependências Google ausentes. Instale: "
            "google-auth-oauthlib google-api-python-client"
        ) from exc

    creds = None
    if token_file.exists():
        with token_file.open("rb") as handle:
            creds = pickle.load(handle)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_file.parent.mkdir(parents=True, exist_ok=True)
        with token_file.open("wb") as handle:
            pickle.dump(creds, handle)
        return creds

    if not credentials_file.exists():
        raise RuntimeError(
            f"Credenciais OAuth não encontradas: {credentials_file}. "
            "Baixe credentials.json do Google Cloud Console "
            "(YouTube Data API v3 habilitada)."
        )

    raise RuntimeError(
        f"Token OAuth ausente em {token_file}. "
        "Autentique com: python3 tools/setup_agenda_youtube_oauth.py"
    )


def _has_readonly_scope(creds) -> bool:
    scopes = getattr(creds, "scopes", None) or ()
    return READONLY_SCOPE in scopes


def _build_youtube_client(creds):
    from googleapiclient.discovery import build

    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def get_authenticated_channel_info(*, config: dict[str, Any] | None = None) -> dict[str, str]:
    """Canal que receberá uploads com o token OAuth atual (channels.list mine=true)."""
    cfg = config or load_config()
    yt = cfg["youtube"]
    credentials_file = resolve_repo_path(yt["credentials_file"])
    token_file = resolve_repo_path(yt["token_file"])
    creds = _load_credentials(credentials_file, token_file)
    if not _has_readonly_scope(creds):
        raise RuntimeError(
            "Token OAuth sem escopo youtube.readonly. "
            "Reautentique com: python3 tools/setup_agenda_youtube_oauth.py --url-only"
        )

    youtube = _build_youtube_client(creds)
    response = youtube.channels().list(part="snippet", mine=True).execute()
    items = response.get("items", [])
    if not items:
        raise RuntimeError(
            "Nenhum canal YouTube encontrado para a conta autenticada. "
            "Autorize com a conta Google do canal @AgendaDiáriaImportante."
        )
    snippet = items[0]["snippet"]
    resolved_id = items[0]["id"]
    return {
        "id": resolved_id,
        "title": snippet.get("title", ""),
        "url": f"https://www.youtube.com/channel/{resolved_id}",
    }


def get_channel_info(*, config: dict[str, Any] | None = None) -> dict[str, str]:
    """Compat: retorna o canal autenticado (destino real do upload)."""
    return get_authenticated_channel_info(config=config)


def verify_upload_channel(*, config: dict[str, Any] | None = None) -> dict[str, str]:
    cfg = config or load_config()
    yt = cfg["youtube"]
    expected_id = (yt.get("channel_id") or "").strip()
    if not expected_id:
        return get_authenticated_channel_info(config=cfg)

    authenticated = get_authenticated_channel_info(config=cfg)
    if authenticated["id"] != expected_id:
        handle = yt.get("channel_handle", "@AgendaDiáriaImportante")
        raise RuntimeError(
            "Conta OAuth autenticada não corresponde ao canal configurado. "
            f"Upload iria para '{authenticated['title']}' ({authenticated['url']}), "
            f"mas o esperado é {handle} "
            f"(https://www.youtube.com/channel/{expected_id}). "
            "Reautentique com a conta Google do canal correto: "
            "python3 tools/setup_agenda_youtube_oauth.py --url-only"
        )
    return authenticated


def _verify_uploaded_video_channel(
    youtube,
    *,
    video_id: str,
    expected_channel_id: str,
) -> None:
    response = youtube.videos().list(part="snippet", id=video_id).execute()
    items = response.get("items", [])
    if not items:
        return
    actual_channel_id = items[0]["snippet"].get("channelId", "")
    if actual_channel_id and actual_channel_id != expected_channel_id:
        raise RuntimeError(
            "Vídeo publicado no canal errado. "
            f"Esperado: https://www.youtube.com/channel/{expected_channel_id}. "
            f"Publicado em: https://www.youtube.com/channel/{actual_channel_id}. "
            f"Remova manualmente https://www.youtube.com/watch?v={video_id} "
            "e reautentique com a conta @AgendaDiáriaImportante."
        )


def youtube_auth_status(config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or load_config()
    yt = cfg["youtube"]
    credentials_file = resolve_repo_path(yt["credentials_file"])
    token_file = resolve_repo_path(yt["token_file"])
    configured_id = (yt.get("channel_id") or "").strip()
    status = {
        "enabled": bool(yt.get("enabled")),
        "channel_id": configured_id,
        "configured_channel_id": configured_id,
        "configured_channel_handle": yt.get("channel_handle", ""),
        "configured_channel_url": yt.get("channel_url", ""),
        "credentials_present": credentials_file.exists(),
        "token_present": token_file.exists(),
        "authenticated": False,
        "authenticated_channel_id": "",
        "channel_title": "",
        "channel_url": "",
        "channel_mismatch": False,
        "upload_only_scope": False,
        "error": "",
    }
    if not status["credentials_present"] or not status["token_present"]:
        return status
    try:
        creds = _load_credentials(credentials_file, token_file)
        status["upload_only_scope"] = not _has_readonly_scope(creds)
        if status["upload_only_scope"]:
            status["error"] = (
                "Token com escopo só de upload; não é possível validar o canal. "
                "Reautentique sem --upload-only-scope."
            )
            return status
        info = get_authenticated_channel_info(config=cfg)
        status["authenticated"] = True
        status["authenticated_channel_id"] = info.get("id", "")
        status["channel_title"] = info.get("title", "")
        status["channel_url"] = info.get("url", "")
        if configured_id and status["authenticated_channel_id"] != configured_id:
            status["channel_mismatch"] = True
            status["error"] = (
                f"Canal autenticado ({info.get('title')}) difere do configurado "
                f"({yt.get('channel_handle', configured_id)})."
            )
    except Exception as exc:
        status["error"] = str(exc)
    return status


def build_video_title(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return f"Agenda Diária — Flávio Bolsonaro — {dt.strftime('%d/%m/%Y')}"


def build_video_description(date_str: str, locution_text: str, source_text: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    preview = locution_text.strip()
    if len(preview) > 1200:
        preview = preview[:1197] + "..."
    return (
        f"Boletim automatizado da agenda pública do senador Flávio Bolsonaro "
        f"para {dt.strftime('%d/%m/%Y')}.\n\n"
        f"{preview}\n\n"
        "Fontes: Congresso Nacional, comissões do Senado e cobertura da imprensa.\n"
        "Gerado automaticamente no homelab RPA4All.\n\n"
        f"---\nTexto-fonte resumido:\n{source_text.strip()[:800]}"
    )


def render_audio_video(
    *,
    wav_path: Path,
    output_mp4: Path,
    cover_image: Path | None = None,
) -> Path:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg não encontrado no PATH.")

    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    cover = cover_image if cover_image and cover_image.exists() else None
    if cover is None:
        cover = output_mp4.parent / "_generated_cover.jpg"
        _write_fallback_cover(cover)

    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(cover),
        "-i",
        str(wav_path),
        "-c:v",
        "libx264",
        "-tune",
        "stillimage",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-pix_fmt",
        "yuv420p",
        "-shortest",
        str(output_mp4),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou: {proc.stderr[-1200:]}")
    return output_mp4


def _write_fallback_cover(path: Path) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        # Sem Pillow: cria um JPEG mínimo via ffmpeg color source.
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=#0f1420:s=1280x720",
                "-frames:v",
                "1",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return

    img = Image.new("RGB", (1280, 720), color=(15, 20, 32))
    draw = ImageDraw.Draw(img)
    draw.rectangle((60, 60, 1220, 660), outline=(79, 140, 255), width=4)
    draw.text((100, 280), "Agenda Diária", fill=(231, 236, 245))
    draw.text((100, 340), "Flávio Bolsonaro — Senado Federal", fill=(147, 161, 189))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="JPEG", quality=90)


def publish_edition(
    date_str: str,
    *,
    artifacts_dir: Path,
    config: dict[str, Any] | None = None,
    privacy_status: str | None = None,
) -> YouTubePublishResult:
    cfg = config or load_config()
    yt = cfg["youtube"]
    if not yt.get("enabled", True):
        raise RuntimeError("Publicação YouTube desabilitada na configuração.")

    day_dir = artifacts_dir / date_str
    wav_path = day_dir / "locution.wav"
    locution_path = day_dir / "locution.txt"
    source_path = day_dir / "source.txt"
    if not wav_path.exists():
        raise RuntimeError(f"Áudio ausente para {date_str}: {wav_path}")
    if not locution_path.exists():
        raise RuntimeError(f"Locução ausente para {date_str}: {locution_path}")

    mp4_path = day_dir / "locution.mp4"
    cover_image = resolve_repo_path(yt.get("cover_image", ""))
    render_audio_video(wav_path=wav_path, output_mp4=mp4_path, cover_image=cover_image)

    credentials_file = resolve_repo_path(yt["credentials_file"])
    token_file = resolve_repo_path(yt["token_file"])
    creds = _load_credentials(credentials_file, token_file)
    from googleapiclient.http import MediaFileUpload

    expected_channel_id = (yt.get("channel_id") or "").strip()
    if expected_channel_id:
        verify_upload_channel(config=cfg)

    youtube = _build_youtube_client(creds)
    title = build_video_title(date_str)
    description = build_video_description(
        date_str,
        locution_path.read_text(encoding="utf-8"),
        source_path.read_text(encoding="utf-8") if source_path.exists() else "",
    )
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": list(yt.get("default_tags", [])),
            "categoryId": str(yt.get("category_id", "25")),
        },
        "status": {
            "privacyStatus": privacy_status or yt.get("privacy_status", "public"),
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(str(mp4_path), mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response: dict[str, Any] = {}
    while response == {}:
        _status, response = request.next_chunk()
    video_id = response["id"]
    if expected_channel_id:
        _verify_uploaded_video_channel(
            youtube,
            video_id=video_id,
            expected_channel_id=expected_channel_id,
        )
    result = YouTubePublishResult(
        video_id=video_id,
        video_url=f"https://www.youtube.com/watch?v={video_id}",
        title=title,
        privacy_status=body["status"]["privacyStatus"],
    )
    meta = {
        "youtube_video_id": result.video_id,
        "youtube_url": result.video_url,
        "youtube_title": result.title,
        "privacy_status": result.privacy_status,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    (day_dir / "publish_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    logger.info("YouTube publicado: %s", result.video_url)
    return result


def _has_manage_scope(creds) -> bool:
    scopes = getattr(creds, "scopes", None) or ()
    return MANAGE_SCOPE in scopes


def delete_youtube_video(
    video_id: str,
    *,
    config: dict[str, Any] | None = None,
) -> str:
    cfg = config or load_config()
    yt = cfg["youtube"]
    credentials_file = resolve_repo_path(yt["credentials_file"])
    token_file = resolve_repo_path(yt["token_file"])
    creds = _load_credentials(credentials_file, token_file)
    if not _has_manage_scope(creds):
        raise RuntimeError(
            "Token OAuth sem escopo para apagar vídeos (youtube.force-ssl). "
            "Reautentique com: python3 tools/setup_agenda_youtube_oauth.py --url-only"
        )
    youtube = _build_youtube_client(creds)
    youtube.videos().delete(id=video_id).execute()
    url = f"https://www.youtube.com/watch?v={video_id}"
    logger.info("YouTube apagado: %s", url)
    return url