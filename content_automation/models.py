"""Modelos de domínio do pipeline de conteúdo."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ContentStatus(str, Enum):
    PENDING = "pending"
    GENERATED = "generated"
    POSTED = "posted"
    FAILED = "failed"


@dataclass
class TrendItem:
    topic: str
    title: str
    score: float
    source: str = "mock"
    tags: list[str] = field(default_factory=list)


@dataclass
class GeneratedContent:
    topic: str
    title: str
    script: str
    cta: str
    trend_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VideoArtifact:
    mp4_path: str
    wav_path: str
    srt_path: str
    cover_path: str
    duration_seconds: float


@dataclass
class PublishResult:
    platform: str
    external_id: str
    url: str
    published_at: str
    mock: bool = True


@dataclass
class QueueItem:
    id: int
    status: ContentStatus
    topic: str
    scheduled_for: str
    title: str = ""
    script: str = ""
    cta: str = ""
    trend_score: float = 0.0
    video_path: str = ""
    publish_url: str = ""
    retries: int = 0
    error: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


@dataclass
class PipelineRunStats:
    started_at: datetime
    finished_at: datetime | None = None
    generated: int = 0
    published: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        if self.finished_at is None:
            return 0.0
        return (self.finished_at - self.started_at).total_seconds()