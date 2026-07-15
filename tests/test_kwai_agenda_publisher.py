from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kwai_agenda_publisher as kwai  # noqa: E402


def test_build_caption_e_factual() -> None:
    title, script = kwai.build_caption("2026-07-14")
    assert "14/07/2026" in title
    assert "Flávio Bolsonaro" in title
    assert "agenda pública" in script
    assert "Fontes:" in script


def test_publish_edition_reusa_mp4_e_grava_meta(tmp_path, monkeypatch) -> None:
    day = tmp_path / "2026-07-14"
    day.mkdir()
    (day / "locution.wav").write_bytes(b"wav")
    (day / "locution.mp4").write_bytes(b"mp4")
    (day / "publish_meta.json").write_text(
        json.dumps({"youtube_video_id": "abc123"}), encoding="utf-8"
    )

    class FakePublisher:
        def __init__(self, upload_url=None):
            self.upload_url = upload_url

        def publish(self, content, video, *, platform):
            assert platform == "kwai"
            assert video.mp4_path.endswith("locution.mp4")

            class Result:
                external_id = "kwai42"
                url = "https://www.kwai.com/video/kwai42"

            return Result()

    from content_automation import publisher as pub_mod

    monkeypatch.setattr(pub_mod, "KwaiPublisher", FakePublisher)

    result = kwai.publish_edition("2026-07-14", artifacts_dir=tmp_path)
    assert result.post_id == "kwai42"
    assert result.post_url == "https://www.kwai.com/video/kwai42"

    meta = json.loads((day / "publish_meta.json").read_text(encoding="utf-8"))
    assert meta["kwai_post_id"] == "kwai42"
    assert meta["kwai_url"] == "https://www.kwai.com/video/kwai42"
    assert meta["youtube_video_id"] == "abc123"


def test_publish_edition_renderiza_mp4_quando_ausente(tmp_path, monkeypatch) -> None:
    day = tmp_path / "2026-07-14"
    day.mkdir()
    (day / "locution.wav").write_bytes(b"wav")

    import youtube_agenda_publisher as yt

    def fake_render(*, wav_path, output_mp4, cover_image=None):
        output_mp4.write_bytes(b"mp4")
        return output_mp4

    monkeypatch.setattr(yt, "render_audio_video", fake_render)

    class FakePublisher:
        def __init__(self, upload_url=None):
            self.upload_url = upload_url

        def publish(self, content, video, *, platform):
            class Result:
                external_id = "novo1"
                url = "https://www.kwai.com/video/novo1"

            return Result()

    from content_automation import publisher as pub_mod

    monkeypatch.setattr(pub_mod, "KwaiPublisher", FakePublisher)

    result = kwai.publish_edition("2026-07-14", artifacts_dir=tmp_path)
    assert result.post_id == "novo1"
    assert (day / "locution.mp4").exists()
