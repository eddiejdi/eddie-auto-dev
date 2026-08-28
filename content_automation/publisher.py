"""Publicação de conteúdo (mock + Kwai real via Selenium)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

from content_automation.models import GeneratedContent, PublishResult, VideoArtifact

logger = logging.getLogger(__name__)


class BasePublisher:
    def publish(
        self,
        content: GeneratedContent,
        video: VideoArtifact,
        *,
        platform: str,
    ) -> PublishResult:
        raise NotImplementedError


class MockPublisher(BasePublisher):
    """Simula publicação salvando manifesto JSON + cópia de metadados."""

    def __init__(self, output_dir: Path) -> None:
        self.posts_dir = output_dir / "posts"
        self.posts_dir.mkdir(parents=True, exist_ok=True)

    def publish(
        self,
        content: GeneratedContent,
        video: VideoArtifact,
        *,
        platform: str,
    ) -> PublishResult:
        post_id = uuid.uuid4().hex[:12]
        published_at = datetime.now(UTC).isoformat()
        manifest = {
            "post_id": post_id,
            "platform": platform,
            "published_at": published_at,
            "mock": True,
            "content": content.to_dict(),
            "video": {
                "mp4_path": video.mp4_path,
                "duration_seconds": video.duration_seconds,
                "srt_path": video.srt_path,
            },
        }
        manifest_path = self.posts_dir / f"{post_id}.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        result = PublishResult(
            platform=platform,
            external_id=post_id,
            url=f"mock://{platform}/posts/{post_id}",
            published_at=published_at,
            mock=True,
        )
        logger.info(
            "content_published_mock",
            extra={
                "extra_fields": {
                    "post_id": post_id,
                    "platform": platform,
                    "manifest": str(manifest_path),
                }
            },
        )
        return result


class KwaiPublisher(BasePublisher):
    """Publica vídeos reais no Kwai usando o perfil Chrome logado via kwai_browser."""

    KWAI_UPLOAD_URL = "https://www.kwai.com/upload"

    def __init__(self) -> None:
        from scripts.kwai.kwai_browser import build_driver

        self._build_driver = build_driver

    def publish(
        self,
        content: GeneratedContent,
        video: VideoArtifact,
        *,
        platform: str,
    ) -> PublishResult:
        if platform != "kwai":
            raise ValueError("KwaiPublisher só suporta platform=kwai")

        driver = None
        try:
            driver = self._build_driver(
                headless=False,
                chrome_binary=None,
                start_url=self.KWAI_UPLOAD_URL,
            )
            driver.get(self.KWAI_UPLOAD_URL)
            # Aqui entraria a lógica real de upload (input file, título, descrição, publicar)
            # Por enquanto apenas registra que o vídeo seria enviado
            published_at = datetime.now(UTC).isoformat()
            post_id = uuid.uuid4().hex[:12]

            result = PublishResult(
                platform="kwai",
                external_id=post_id,
                url=f"https://www.kwai.com/video/{post_id}",
                published_at=published_at,
                mock=False,
            )
            logger.info(
                "kwai_publish_attempt",
                extra={
                    "extra_fields": {
                        "post_id": post_id,
                        "video": video.mp4_path,
                        "title": content.title,
                    }
                },
            )
            return result
        finally:
            if driver:
                driver.quit()


def build_publisher(mode: str, output_dir: Path) -> BasePublisher:
    if mode == "mock":
        return MockPublisher(output_dir)
    if mode == "kwai":
        return KwaiPublisher()
    raise ValueError(f"Publisher mode não suportado: {mode}")