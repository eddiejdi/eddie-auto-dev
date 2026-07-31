"""Testes dos cues de produção da agenda diária."""
from __future__ import annotations

import struct
import sys
import wave
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import daily_agenda_cues as cues  # noqa: E402


def _write_tone_wav(path: Path, *, seconds: float = 0.5, rate: int = 22050, freq: float = 440.0) -> None:
    import math

    n = int(rate * seconds)
    samples = [
        int(0.2 * 32767 * math.sin(2 * math.pi * freq * (i / rate))) for i in range(n)
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(struct.pack("<" + "h" * n, *samples))


def test_parse_freeform_and_structured_cues() -> None:
    raw = (
        "***Som de Fundo de Locução***\n"
        "Bom dia. Abrimos a agenda do senador.\n"
        "Pausa de 30 Seg\n"
        "{{VINHETA:open}}\n"
        "Não há compromissos formais."
    )
    spoken, events = cues.parse_and_strip_cues(raw)
    kinds = [e.kind for e in events]
    assert "bed" in kinds
    assert "pause" in kinds
    assert "vinheta" in kinds
    assert "som de fundo" not in spoken.lower()
    assert "pausa de 30" not in spoken.lower()
    assert "Bom dia" in spoken
    assert "compromissos formais" in spoken
    pause = next(e for e in events if e.kind == "pause")
    assert pause.seconds == 30.0


def test_ensure_assets_and_render_timeline(tmp_path: Path) -> None:
    settings = cues.default_cue_settings(
        {
            "enabled": True,
            "vinheta_open": True,
            "vinheta_close": True,
            "bed_under_speech": True,
            "pause_between_segments_seconds": 0.4,
            "bed_idle_seconds": 0.3,
        }
    )
    day = tmp_path / "day"
    speech = day / "seg.wav"
    _write_tone_wav(speech, seconds=0.6)

    result = cues.apply_cues_to_production(
        speech_units=[
            (
                "abertura",
                "***Som de Fundo de Locução*** Bom dia a todos. Pausa de 2 Seg. Encerramos.",
                speech,
            )
        ],
        day_dir=day,
        settings=settings,
        output_wav=day / "locution.wav",
    )
    assert result["enabled"] is True
    assert Path(result["wav_path"]).is_file()
    assert Path(result["manifest"]).is_file()
    assert Path(result["script"]).is_file()
    assert (day / "cues" / "bed_locucao.wav").is_file()
    assert (day / "cues" / "vinheta_open.wav").is_file()
    assert result["duration_seconds"] > 0.6

    script = Path(result["script"]).read_text(encoding="utf-8")
    assert "SOM DE FUNDO" in script or "PAUSA" in script
    spoken = Path(result["spoken"]).read_text(encoding="utf-8")
    assert "Bom dia" in spoken
    assert "Pausa de" not in spoken
