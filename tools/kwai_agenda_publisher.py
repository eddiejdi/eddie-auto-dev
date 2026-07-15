#!/usr/bin/env python3
"""Publica a edição da agenda diária no Kwai (reaproveita o mp4 do YouTube)."""
from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from daily_agenda_config import load_config, resolve_repo_path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KwaiPublishResult:
    post_id: str
    post_url: str
    title: str


def build_caption(date_str: str) -> tuple[str, str]:
    from youtube_agenda_publisher import build_video_title

    dt = datetime.strptime(date_str, "%Y-%m-%d")
    title = build_video_title(date_str)
    script = (
        f"Boletim automatizado da agenda pública do senador Flávio Bolsonaro "
        f"para {dt.strftime('%d/%m/%Y')}. "
        "Fontes: Congresso Nacional, comissões do Senado e cobertura da imprensa."
    )
    return title, script


def _ensure_mp4(date_str: str, day_dir: Path, cfg: dict[str, Any]) -> Path:
    from youtube_agenda_publisher import render_audio_video

    mp4_path = day_dir / "locution.mp4"
    if mp4_path.exists():
        return mp4_path
    wav_path = day_dir / "locution.wav"
    if not wav_path.exists():
        raise RuntimeError(f"Áudio ausente para {date_str}: {wav_path}")
    cover_image = resolve_repo_path(cfg["youtube"].get("cover_image", ""))
    return render_audio_video(
        wav_path=wav_path,
        output_mp4=mp4_path,
        cover_image=cover_image,
    )


def publish_edition(
    date_str: str,
    *,
    artifacts_dir: Path,
    config: dict[str, Any] | None = None,
) -> KwaiPublishResult:
    cfg = config or load_config()
    kwai_cfg = cfg.get("kwai", {})
    if not kwai_cfg.get("enabled", True):
        raise RuntimeError("Publicação Kwai desabilitada na configuração.")

    day_dir = artifacts_dir / date_str
    mp4_path = _ensure_mp4(date_str, day_dir, cfg)

    from content_automation.models import GeneratedContent, VideoArtifact
    from content_automation.publisher import KwaiPublisher

    title, script = build_caption(date_str)
    content = GeneratedContent(
        topic="agenda-diaria",
        title=title,
        script=script,
        cta="",
    )
    video = VideoArtifact(
        mp4_path=str(mp4_path),
        wav_path=str(day_dir / "locution.wav"),
        srt_path="",
        cover_path="",
        duration_seconds=0.0,
    )

    upload_url = (kwai_cfg.get("upload_url") or "").strip() or None
    result = KwaiPublisher(upload_url=upload_url).publish(content, video, platform="kwai")

    meta_path = day_dir / "publish_meta.json"
    meta: dict[str, Any] = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update(
        {
            "kwai_post_id": result.external_id,
            "kwai_url": result.url,
            "kwai_title": title,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    logger.info("Kwai publicado: %s", result.url)
    return KwaiPublishResult(
        post_id=result.external_id,
        post_url=result.url,
        title=title,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if len(sys.argv) < 2:
        print("Uso: python3 tools/kwai_agenda_publisher.py YYYY-MM-DD [artifacts_dir]")
        sys.exit(1)
    date_arg = sys.argv[1]
    artifacts = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else REPO_ROOT / "artifacts" / "daily_agenda"
    )
    published = publish_edition(date_arg, artifacts_dir=artifacts)
    print(f"Kwai: {published.post_url}")
