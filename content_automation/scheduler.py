"""Agenda diária e orquestração da fila."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from content_automation.config import load_settings
from content_automation.generator import generate_content
from content_automation.models import ContentStatus, PipelineRunStats, QueueItem
from content_automation.publisher import build_publisher
from content_automation.storage import ContentQueue
from content_automation.trends import pick_best_trend
from content_automation.video_pipeline import render_video

logger = logging.getLogger(__name__)


class ContentScheduler:
    def __init__(self, settings: dict | None = None) -> None:
        self.settings = settings or load_settings()
        paths = self.settings["paths"]
        self.queue = ContentQueue(Path(paths["db_path"]))
        self.prompts_dir = Path(paths["prompts_dir"])
        self.output_dir = Path(paths["output_dir"])
        self.publisher = build_publisher(
            self.settings["publisher"]["mode"],
            self.output_dir,
        )
        self.tz = ZoneInfo(self.settings["scheduler"]["timezone"])

    def _today_prefix(self) -> str:
        return datetime.now(self.tz).strftime("%Y-%m-%d")

    def _slot_datetimes_today(self) -> list[datetime]:
        today = datetime.now(self.tz).date()
        slots: list[datetime] = []
        for hhmm in self.settings["scheduler"]["post_times"]:
            hour, minute = map(int, hhmm.split(":"))
            slots.append(datetime(today.year, today.month, today.day, hour, minute, tzinfo=self.tz))
        return slots

    def plan_daily_slots(self) -> list[QueueItem]:
        """Cria itens pending para slots do dia que ainda não existem na fila."""
        created: list[QueueItem] = []
        day_prefix = self._today_prefix()
        if self.queue.count_today(day_prefix) >= int(self.settings["daily_limit"]):
            return created

        used_topics: set[str] = set()
        for slot_dt in self._slot_datetimes_today():
            slot_key = slot_dt.isoformat()
            if self.queue.has_slot(slot_key):
                continue
            if self.queue.count_today(day_prefix) >= int(self.settings["daily_limit"]):
                break

            trend = pick_best_trend(self.settings["topics_priority"], exclude_topics=used_topics)
            if trend is None:
                logger.warning("Nenhuma trend disponível para agendar slot %s", slot_key)
                continue

            used_topics.add(trend.topic)
            item = self.queue.enqueue(
                topic=trend.topic,
                scheduled_for=slot_key,
                trend_score=trend.score,
            )
            created.append(item)
            logger.info(
                "slot_planned",
                extra={
                    "extra_fields": {
                        "queue_id": item.id,
                        "topic": trend.topic,
                        "scheduled_for": slot_key,
                    }
                },
            )
        return created

    def due_items(self, *, grace_minutes: int = 0) -> list[QueueItem]:
        now = datetime.now(self.tz)
        pending = self.queue.list_by_status(ContentStatus.PENDING)
        due: list[QueueItem] = []
        for item in pending:
            slot_dt = datetime.fromisoformat(item.scheduled_for)
            if slot_dt <= now + timedelta(minutes=grace_minutes):
                due.append(item)
        return due

    def process_item(self, item: QueueItem) -> QueueItem:
        trend = pick_best_trend([item.topic])
        if trend is None:
            raise RuntimeError(f"Sem trend para tópico {item.topic}")

        content = generate_content(
            trend,
            prompts_dir=self.prompts_dir,
            max_script_seconds=int(self.settings["video"]["max_duration_seconds"]),
        )
        video = render_video(
            content,
            output_dir=self.output_dir,
            width=int(self.settings["video"]["width"]),
            height=int(self.settings["video"]["height"]),
            max_duration_seconds=int(self.settings["video"]["max_duration_seconds"]),
            tts_backend=str(self.settings["video"]["tts_backend"]),
        )
        publish = self.publisher.publish(
            content,
            video,
            platform=str(self.settings["publisher"]["platform"]),
        )

        return self.queue.update_item(
            item.id,
            status=ContentStatus.POSTED,
            title=content.title,
            script=content.script,
            cta=content.cta,
            trend_score=content.trend_score,
            video_path=video.mp4_path,
            publish_url=publish.url,
            error="",
        )

    def process_due(self, *, force: bool = False) -> PipelineRunStats:
        stats = PipelineRunStats(started_at=datetime.now(UTC))
        max_retries = int(self.settings["scheduler"]["max_retries"])
        items = self.queue.list_by_status(ContentStatus.PENDING) if force else self.due_items()

        for item in items:
            try:
                self.process_item(item)
                stats.published += 1
                stats.generated += 1
            except Exception as exc:
                retries = item.retries + 1
                status = ContentStatus.FAILED if retries >= max_retries else ContentStatus.PENDING
                self.queue.update_item(
                    item.id,
                    status=status,
                    retries=retries,
                    error=str(exc),
                )
                stats.failed += 1
                stats.errors.append(f"item={item.id}: {exc}")
                logger.exception("pipeline_item_failed", extra={"extra_fields": {"queue_id": item.id}})

        stats.finished_at = datetime.now(UTC)
        return stats

    def run_cycle(self, *, force: bool = False) -> PipelineRunStats:
        self.plan_daily_slots()
        return self.process_due(force=force)