"""Carregamento de settings.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_SETTINGS_PATH = PACKAGE_ROOT / "settings.yaml"


def load_settings(path: Path | str | None = None) -> dict[str, Any]:
    settings_path = Path(path) if path else DEFAULT_SETTINGS_PATH
    if not settings_path.is_file():
        raise FileNotFoundError(f"settings.yaml não encontrado: {settings_path}")
    with settings_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return _with_defaults(data)


def _with_defaults(data: dict[str, Any]) -> dict[str, Any]:
    scheduler = data.setdefault("scheduler", {})
    scheduler.setdefault("posts_per_day", 3)
    scheduler.setdefault("post_times", ["08:30", "14:00", "20:00"])
    scheduler.setdefault("poll_interval_seconds", 60)
    scheduler.setdefault("max_retries", 3)
    scheduler.setdefault("timezone", "America/Sao_Paulo")

    data.setdefault("topics_priority", ["cripto", "curiosidades", "viral_trends"])
    data.setdefault("daily_limit", 3)

    paths = data.setdefault("paths", {})
    paths.setdefault("data_dir", str(PACKAGE_ROOT / "data"))
    paths.setdefault("output_dir", str(PACKAGE_ROOT / "output"))
    paths.setdefault("prompts_dir", str(PACKAGE_ROOT / "data" / "prompts"))
    paths.setdefault("db_path", str(PACKAGE_ROOT / "data" / "queue.db"))
    paths.setdefault("logs_dir", str(PACKAGE_ROOT / "data" / "logs"))

    video = data.setdefault("video", {})
    video.setdefault("width", 1080)
    video.setdefault("height", 1920)
    video.setdefault("max_duration_seconds", 60)
    video.setdefault("tts_backend", "mock")

    publisher = data.setdefault("publisher", {})
    publisher.setdefault("mode", "mock")
    publisher.setdefault("platform", "kwai")

    return data