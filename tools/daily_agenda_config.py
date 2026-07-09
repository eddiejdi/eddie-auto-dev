#!/usr/bin/env python3
"""Configuração persistente do painel e publicação da agenda diária."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "artifacts" / "daily_agenda" / "panel_config.json"
DEFAULT_ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "daily_agenda"
DEFAULT_JOB_PATH = DEFAULT_ARTIFACTS_DIR / "panel_job.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "defaults": {
        "mode": "auto",
        "quality": "balanced",
        "include_news": True,
        "send_telegram": True,
        "upload_youtube": True,
    },
    "youtube": {
        "enabled": True,
        "channel_id": os.getenv(
            "AGENDA_YOUTUBE_CHANNEL_ID",
            "UCEyYr2YE1HLDTKT4cnMefmw",
        ),
        "channel_handle": "@AgendaDiáriaImportante",
        "channel_url": "https://www.youtube.com/channel/UCEyYr2YE1HLDTKT4cnMefmw",
        "privacy_status": "public",
        "category_id": "25",
        "default_tags": [
            "agenda diária",
            "Agenda Diária Importante",
            "Flávio Bolsonaro",
            "Senado Federal",
            "política",
        ],
        "cover_image": "artifacts/daily_agenda/youtube/cover.jpg",
        "credentials_file": "artifacts/daily_agenda/youtube/credentials.json",
        "token_file": "artifacts/daily_agenda/youtube/token.pickle",
    },
    "telegram": {
        "enabled": True,
        "chat_id": os.getenv("AGENDA_TELEGRAM_CHAT_ID", ""),
    },
}


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        return json.loads(json.dumps(DEFAULT_CONFIG))
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    return _deep_merge(DEFAULT_CONFIG, data)


def save_config(config: dict[str, Any], path: Path | None = None) -> Path:
    cfg_path = path or DEFAULT_CONFIG_PATH
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    merged = _deep_merge(DEFAULT_CONFIG, config)
    cfg_path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return cfg_path


def resolve_repo_path(value: str | Path, *, repo_root: Path = REPO_ROOT) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def list_editions(artifacts_dir: Path | None = None) -> list[dict[str, Any]]:
    root = artifacts_dir or DEFAULT_ARTIFACTS_DIR
    if not root.exists():
        return []
    editions: list[dict[str, Any]] = []
    for day_dir in sorted(root.iterdir(), reverse=True):
        if not day_dir.is_dir():
            continue
        date_str = day_dir.name
        try:
            from datetime import datetime

            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
        meta_path = day_dir / "publish_meta.json"
        meta = {}
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        editions.append(
            {
                "date": date_str,
                "has_source": (day_dir / "source.txt").exists(),
                "has_locution": (day_dir / "locution.txt").exists(),
                "has_wav": (day_dir / "locution.wav").exists(),
                "has_mp4": (day_dir / "locution.mp4").exists(),
                "youtube_video_id": meta.get("youtube_video_id", ""),
                "youtube_url": meta.get("youtube_url", ""),
                "updated_at": meta.get("updated_at", ""),
            }
        )
    return editions