"""Pipeline de vídeo: TTS + imagem + legendas -> MP4."""

from __future__ import annotations

import logging
import math
import re
import shutil
import subprocess
import textwrap
import wave
from pathlib import Path

from content_automation.models import GeneratedContent, VideoArtifact

logger = logging.getLogger(__name__)


def _estimate_duration(script: str, *, max_seconds: int) -> float:
    words = len(re.findall(r"\w+", script))
    # ~2.5 palavras/segundo em narração PT-BR
    estimated = max(words / 2.5, 8.0)
    return min(estimated, float(max_seconds))


def _write_srt(path: Path, script: str, duration: float) -> None:
    chunks = textwrap.wrap(script, width=42) or [script]
    slot = duration / max(len(chunks), 1)
    lines: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        start = (index - 1) * slot
        end = min(index * slot, duration)
        lines.extend(
            [
                str(index),
                f"{_srt_ts(start)} --> {_srt_ts(end)}",
                chunk,
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def _srt_ts(seconds: float) -> str:
    millis = int(seconds * 1000)
    hours, rem = divmod(millis, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _synthesize_tts_mock(wav_path: Path, script: str, duration: float) -> None:
    """Gera WAV silencioso com duração estimada (mock TTS)."""
    sample_rate = 22050
    n_frames = int(sample_rate * duration)
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(wav_path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * n_frames)


def _synthesize_tts_espeak(wav_path: Path, script: str) -> bool:
    if shutil.which("espeak") is None:
        return False
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["espeak", "-v", "pt", "-w", str(wav_path), script],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0 and wav_path.is_file()


def synthesize_speech(
    wav_path: Path,
    script: str,
    *,
    backend: str = "mock",
    duration_hint: float,
) -> str:
    if backend == "espeak" and _synthesize_tts_espeak(wav_path, script):
        return "espeak"
    _synthesize_tts_mock(wav_path, script, duration_hint)
    return "mock"


def _write_cover(path: Path, title: str, *, width: int, height: int) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont

        img = Image.new("RGB", (width, height), color=(12, 18, 32))
        draw = ImageDraw.Draw(img)
        draw.rectangle((40, 40, width - 40, height - 40), outline=(56, 189, 248), width=4)
        wrapped = "\n".join(textwrap.wrap(title, width=22))
        draw.multiline_text((80, height // 3), wrapped, fill=(248, 250, 252), spacing=8)
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path, format="JPEG", quality=90)
        return
    except ImportError:
        pass

    if shutil.which("ffmpeg") is None:
        raise RuntimeError("Pillow ou ffmpeg necessário para gerar capa.")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=#0c1220:s={width}x{height}",
            "-frames:v",
            "1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def _render_video_mock_stub(
    content: GeneratedContent,
    *,
    output_dir: Path,
    duration: float,
) -> VideoArtifact:
    """Fallback sem ffmpeg — gera artefatos mínimos para demo/CI."""
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", content.title.lower())[:48].strip("_")
    work_dir = output_dir / "videos" / slug
    work_dir.mkdir(parents=True, exist_ok=True)
    wav_path = work_dir / "narration.wav"
    srt_path = work_dir / "captions.srt"
    cover_path = work_dir / "cover.jpg"
    mp4_path = work_dir / "final.mp4"
    _synthesize_tts_mock(wav_path, content.script, duration)
    _write_srt(srt_path, content.script, duration)
    cover_path.write_bytes(b"mock-cover")
    mp4_path.write_bytes(b"mock-mp4-stub")
    return VideoArtifact(
        mp4_path=str(mp4_path),
        wav_path=str(wav_path),
        srt_path=str(srt_path),
        cover_path=str(cover_path),
        duration_seconds=duration,
    )


def render_video(
    content: GeneratedContent,
    *,
    output_dir: Path,
    width: int = 1080,
    height: int = 1920,
    max_duration_seconds: int = 60,
    tts_backend: str = "mock",
) -> VideoArtifact:
    duration = _estimate_duration(content.script, max_seconds=max_duration_seconds)
    if shutil.which("ffmpeg") is None:
        logger.warning("ffmpeg ausente — usando renderização mock stub")
        return _render_video_mock_stub(content, output_dir=output_dir, duration=duration)

    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", content.title.lower())[:48].strip("_")
    work_dir = output_dir / "videos" / slug
    work_dir.mkdir(parents=True, exist_ok=True)

    wav_path = work_dir / "narration.wav"
    srt_path = work_dir / "captions.srt"
    cover_path = work_dir / "cover.jpg"
    mp4_path = work_dir / "final.mp4"

    used_tts = synthesize_speech(
        wav_path,
        f"{content.script}\n\n{content.cta}",
        backend=tts_backend,
        duration_hint=duration,
    )
    _write_srt(srt_path, content.script, duration)
    _write_cover(cover_path, content.title, width=width, height=height)

    # Vídeo vertical estático + áudio + legendas queimadas (simplificado)
    safe_title = content.title.replace("'", "\\'")[:80]
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
        f"drawtext=text='{safe_title}':x=(w-text_w)/2:y=h*0.08:"
        f"fontsize=42:fontcolor=white:box=1:boxcolor=black@0.45"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(cover_path),
        "-i",
        str(wav_path),
        "-vf",
        vf,
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
        "-t",
        str(math.ceil(duration)),
        str(mp4_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou: {proc.stderr[-1500:]}")

    artifact = VideoArtifact(
        mp4_path=str(mp4_path),
        wav_path=str(wav_path),
        srt_path=str(srt_path),
        cover_path=str(cover_path),
        duration_seconds=duration,
    )
    logger.info(
        "video_rendered",
        extra={
            "extra_fields": {
                "mp4": artifact.mp4_path,
                "duration": artifact.duration_seconds,
                "tts": used_tts,
            }
        },
    )
    return artifact