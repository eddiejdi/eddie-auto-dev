"""Testes do pipeline de automação de conteúdo."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from content_automation.config import load_settings
from content_automation.generator import generate_content
from content_automation.models import ContentStatus
from content_automation.publisher import KwaiPublisher, MockPublisher
from content_automation.scheduler import ContentScheduler
from content_automation.storage import ContentQueue
from content_automation.trends import collect_trends, pick_best_trend
from content_automation.video_pipeline import render_video


@pytest.fixture
def settings(tmp_path: Path) -> dict:
    root = tmp_path / "content_automation"
    prompts = root / "data" / "prompts"
    prompts.mkdir(parents=True)
    for topic in ("cripto", "curiosidades", "viral_trends"):
        src = Path("content_automation/data/prompts") / f"{topic}.yaml"
        (prompts / f"{topic}.yaml").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    cfg = load_settings("content_automation/settings.yaml")
    cfg["paths"]["data_dir"] = str(root / "data")
    cfg["paths"]["output_dir"] = str(root / "output")
    cfg["paths"]["prompts_dir"] = str(prompts)
    cfg["paths"]["db_path"] = str(root / "data" / "queue.db")
    cfg["paths"]["logs_dir"] = str(root / "data" / "logs")
    cfg["scheduler"]["post_times"] = ["00:01", "00:02", "00:03"]
    return cfg


def test_collect_trends_sorted(settings: dict) -> None:
    trends = collect_trends(settings["topics_priority"], seed=42)
    assert len(trends) >= 3
    assert trends[0].score >= trends[-1].score


def test_generator_produces_script(settings: dict) -> None:
    trend = pick_best_trend(settings["topics_priority"])
    assert trend is not None
    content = generate_content(trend, prompts_dir=Path(settings["paths"]["prompts_dir"]))
    assert content.title
    assert content.script
    assert content.cta
    assert content.topic == trend.topic


def test_queue_lifecycle(settings: dict) -> None:
    queue = ContentQueue(Path(settings["paths"]["db_path"]))
    item = queue.enqueue(topic="cripto", scheduled_for="2026-07-15T08:30:00-03:00", trend_score=0.9)
    assert item.status == ContentStatus.PENDING
    updated = queue.update_item(item.id, status=ContentStatus.GENERATED, title="Teste")
    assert updated.status == ContentStatus.GENERATED
    assert updated.title == "Teste"


def test_mock_publisher_writes_manifest(settings: dict) -> None:
    trend = pick_best_trend(settings["topics_priority"])
    content = generate_content(trend, prompts_dir=Path(settings["paths"]["prompts_dir"]))
    from content_automation.models import VideoArtifact

    video = VideoArtifact(
        mp4_path="/tmp/fake.mp4",
        wav_path="/tmp/fake.wav",
        srt_path="/tmp/fake.srt",
        cover_path="/tmp/fake.jpg",
        duration_seconds=30.0,
    )
    publisher = MockPublisher(Path(settings["paths"]["output_dir"]))
    result = publisher.publish(content, video, platform="kwai")
    manifest = Path(settings["paths"]["output_dir"]) / "posts" / f"{result.external_id}.json"
    assert manifest.is_file()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["mock"] is True


def test_kwai_publisher_instantiation():
    pub = KwaiPublisher()
    assert pub is not None

    # Deve rejeitar platform diferente de kwai
    from content_automation.models import GeneratedContent, VideoArtifact

    fake_content = GeneratedContent(
        title="t", script="s", cta="c", topic="cripto", trend_score=1.0
    )
    fake_video = VideoArtifact(
        mp4_path="/tmp/x.mp4",
        wav_path=None,
        srt_path=None,
        cover_path=None,
        duration_seconds=15.0,
    )
    with pytest.raises(ValueError):
        pub.publish(fake_content, fake_video, platform="youtube")


def test_end_to_end_pipeline(settings: dict, monkeypatch) -> None:
    monkeypatch.setattr(
        "content_automation.video_pipeline.shutil.which",
        lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None,
    )

    def fake_run(cmd, capture_output=True, text=True, check=False):
        class Result:
            returncode = 0
            stderr = ""

        out_mp4 = None
        for index, part in enumerate(cmd):
            if part.endswith(".mp4"):
                out_mp4 = Path(part)
                break
        if out_mp4 is not None:
            out_mp4.parent.mkdir(parents=True, exist_ok=True)
            out_mp4.write_bytes(b"fake-mp4")
        return Result()

    monkeypatch.setattr("content_automation.video_pipeline.subprocess.run", fake_run)

    scheduler = ContentScheduler(settings)
    scheduler.plan_daily_slots()
    stats = scheduler.run_cycle(force=True)
    assert stats.published >= 1
    posted = scheduler.queue.list_by_status(ContentStatus.POSTED)
    assert posted
    assert posted[0].video_path