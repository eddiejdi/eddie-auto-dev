from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import youtube_agenda_publisher as yt  # noqa: E402


def test_build_video_title_and_description() -> None:
    title = yt.build_video_title("2026-07-09")
    assert "09/07/2026" in title
    assert "Flávio Bolsonaro" in title
    desc = yt.build_video_description("2026-07-09", "Locucao longa", "Fonte curta")
    assert "09/07/2026" in desc
    assert "Locucao longa" in desc


def test_render_audio_video_uses_ffmpeg(tmp_path, monkeypatch) -> None:
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"wav")
    out = tmp_path / "out.mp4"
    monkeypatch.setattr(yt.shutil, "which", lambda _: "/usr/bin/ffmpeg")
    proc = MagicMock(returncode=0, stderr="")
    monkeypatch.setattr(yt.subprocess, "run", lambda *a, **k: proc)
    monkeypatch.setattr(yt, "_write_fallback_cover", lambda path: path.write_bytes(b"jpg"))
    result = yt.render_audio_video(wav_path=wav, output_mp4=out, cover_image=None)
    assert result == out


def test_publish_edition_writes_meta(tmp_path, monkeypatch) -> None:
    day = tmp_path / "2026-07-09"
    day.mkdir()
    (day / "locution.wav").write_bytes(b"wav")
    (day / "locution.txt").write_text("Texto", encoding="utf-8")
    (day / "source.txt").write_text("Fonte", encoding="utf-8")

    monkeypatch.setattr(yt, "render_audio_video", lambda **kwargs: kwargs["output_mp4"])

    class FakeVideos:
        def insert(self, **kwargs):
            class Req:
                def next_chunk(self_inner):
                    return None, {"id": "abc123"}

            return Req()

    fake_youtube = MagicMock()
    fake_youtube.videos.return_value = FakeVideos()
    fake_build = MagicMock(return_value=fake_youtube)
    fake_media = MagicMock(return_value="media")

    cfg = yt.load_config()
    cfg["youtube"]["channel_id"] = ""

    with patch.object(yt, "_load_credentials", return_value=object()):
        with patch.dict(
            sys.modules,
            {
                "googleapiclient.discovery": MagicMock(build=fake_build),
                "googleapiclient.http": MagicMock(MediaFileUpload=fake_media),
            },
        ):
            result = yt.publish_edition("2026-07-09", artifacts_dir=tmp_path, config=cfg)
    assert result.video_id == "abc123"
    meta = json.loads((day / "publish_meta.json").read_text(encoding="utf-8"))
    assert meta["youtube_video_id"] == "abc123"


def test_verify_upload_channel_rejects_mismatch(monkeypatch) -> None:
    monkeypatch.setattr(
        yt,
        "get_authenticated_channel_info",
        lambda **kwargs: {
            "id": "UCpersonal",
            "title": "Canal Pessoal",
            "url": "https://www.youtube.com/channel/UCpersonal",
        },
    )
    cfg = yt.load_config()
    with pytest.raises(RuntimeError, match="Conta OAuth autenticada não corresponde"):
        yt.verify_upload_channel(config=cfg)


def test_youtube_auth_status_flags_upload_only_scope(tmp_path, monkeypatch) -> None:
    class FakeCreds:
        scopes = ("https://www.googleapis.com/auth/youtube.upload",)
        valid = True
        expired = False

    cfg = yt.load_config()
    cfg["youtube"]["credentials_file"] = str(tmp_path / "credentials.json")
    cfg["youtube"]["token_file"] = str(tmp_path / "token.pickle")
    (tmp_path / "credentials.json").write_text("{}", encoding="utf-8")
    (tmp_path / "token.pickle").write_bytes(b"token")

    monkeypatch.setattr(yt, "_load_credentials", lambda *args, **kwargs: FakeCreds())
    status = yt.youtube_auth_status(cfg)
    assert status["upload_only_scope"] is True
    assert status["authenticated"] is False
    assert "escopo só de upload" in status["error"]