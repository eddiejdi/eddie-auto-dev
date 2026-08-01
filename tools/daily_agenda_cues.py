#!/usr/bin/env python3
"""Cues de produção da agenda diária → artefatos de áudio e mix final.

Converte indicações de roteiro (pausa, som de fundo, vinheta) em WAV reais e
monta uma timeline de produção. O texto falado fica limpo para o TTS; os cues
viram assets em ``cues/`` + ``cues/manifest.json``.

Formatos reconhecidos no texto:
  - estruturado: ``{{PAUSE:30}}`` ``{{BED:locucao}}`` ``{{VINHETA:open}}``
  - livre (legado): ``***Som de Fundo de Locução***``, ``Pausa de 30 Seg``,
    ``[TRILHA]``, ``(pausa)``, ``LOCUTOR:`` (só o rótulo some; fala permanece)
"""
from __future__ import annotations

import json
import logging
import math
import re
import struct
import wave
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal

logger = logging.getLogger(__name__)

CueKind = Literal["pause", "bed", "vinheta", "stinger", "speech"]

DEFAULT_RATE = 22050
DEFAULT_CHANNELS = 1
DEFAULT_SAMPWIDTH = 2

# Marcadores estruturados preferidos no pipeline.
_STRUCTURED_CUE_RE = re.compile(
    r"\{\{\s*(PAUSE|BED|VINHETA|STINGER|SFX)\s*(?::\s*([^}]+))?\s*\}\}",
    re.IGNORECASE,
)

# Livre → (kind, arg)
_FREEFORM_PATTERNS: tuple[tuple[re.Pattern[str], str, str | None], ...] = (
    (
        re.compile(
            r"\*{2,3}\s*som\s+de\s+fundo(?:\s+de\s+locu[cç][aã]o)?\s*\*{2,3}",
            re.I,
        ),
        "bed",
        "locucao",
    ),
    (
        re.compile(
            r"\[\s*som(?:\s+de\s+fundo)?(?:\s+de\s+locu[cç][aã]o)?[^\]]{0,40}\]",
            re.I,
        ),
        "bed",
        "locucao",
    ),
    (
        re.compile(
            r"\(\s*som(?:\s+de\s+fundo)?(?:\s+de\s+locu[cç][aã]o)?[^)]{0,40}\)",
            re.I,
        ),
        "bed",
        "locucao",
    ),
    (
        re.compile(
            r"\*{2,3}\s*pausa(?:\s+de)?\s*(\d+)\s*(?:seg(?:undos?)?|s)?\s*\*{2,3}",
            re.I,
        ),
        "pause",
        None,  # seconds from group 1
    ),
    (
        re.compile(
            r"(?m)^\s*(?:[-–—*•]\s*)?pausa(?:\s+de)?\s*(\d+)\s*(?:seg(?:undos?)?|s)?\s*[.!]?\s*$",
            re.I,
        ),
        "pause",
        None,
    ),
    (
        re.compile(
            r"\bpausa(?:\s+de)?\s*(\d+)\s*(?:seg(?:undos?)?|s)\b",
            re.I,
        ),
        "pause",
        None,
    ),
    (
        re.compile(
            r"\*{2,3}\s*(?:vinheta|abertura)\s*\*{2,3}",
            re.I,
        ),
        "vinheta",
        "open",
    ),
    (
        re.compile(
            r"\[\s*(?:vinheta|trilha\s*abertura)[^\]]{0,40}\]",
            re.I,
        ),
        "vinheta",
        "open",
    ),
    (
        re.compile(
            r"\b(?:trilha|m[uú]sica|sfx|bgm)\s*:\s*[^\n.!?]{0,40}",
            re.I,
        ),
        "bed",
        "locucao",
    ),
)

_LABEL_ONLY_RE = re.compile(r"\b(?:locutor|off|narrador)\s*:\s*", re.I)


@dataclass(frozen=True)
class CueEvent:
    kind: CueKind
    arg: str = ""
    seconds: float = 0.0
    source: str = ""  # trecho original no texto
    speech_text: str = ""  # só para kind=speech


@dataclass
class CueSettings:
    enabled: bool = True
    vinheta_open: bool = True
    vinheta_close: bool = True
    bed_under_speech: bool = True
    bed_gain: float = 0.09
    voice_gain: float = 1.0
    pause_between_segments_seconds: float = 1.2
    default_pause_seconds: float = 2.0
    vinheta_open_seconds: float = 2.4
    vinheta_close_seconds: float = 1.8
    bed_idle_seconds: float = 1.5  # bed sozinho quando cue BED sem fala
    rate: int = DEFAULT_RATE


def default_cue_settings(raw: dict[str, Any] | None = None) -> CueSettings:
    raw = raw or {}
    return CueSettings(
        enabled=bool(raw.get("enabled", raw.get("cues_enabled", True))),
        vinheta_open=bool(raw.get("vinheta_open", True)),
        vinheta_close=bool(raw.get("vinheta_close", True)),
        bed_under_speech=bool(raw.get("bed_under_speech", True)),
        bed_gain=float(raw.get("bed_gain", 0.09)),
        voice_gain=float(raw.get("voice_gain", 1.0)),
        pause_between_segments_seconds=float(
            raw.get("pause_between_segments_seconds", 1.2)
        ),
        default_pause_seconds=float(raw.get("default_pause_seconds", 2.0)),
        vinheta_open_seconds=float(raw.get("vinheta_open_seconds", 2.4)),
        vinheta_close_seconds=float(raw.get("vinheta_close_seconds", 1.8)),
        bed_idle_seconds=float(raw.get("bed_idle_seconds", 1.5)),
        rate=int(raw.get("rate", DEFAULT_RATE)),
    )


def load_cue_settings_from_audio_cfg(audio: dict[str, Any] | None) -> CueSettings:
    audio = audio or {}
    cues_raw = dict(audio.get("cues") or {})
    if "cues_enabled" in audio and "enabled" not in cues_raw:
        cues_raw["enabled"] = audio["cues_enabled"]
    return default_cue_settings(cues_raw)


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------


def _pause_seconds(raw: str | None, default: float) -> float:
    if raw is None or str(raw).strip() == "":
        return float(default)
    m = re.search(r"(\d+(?:[.,]\d+)?)", str(raw))
    if not m:
        return float(default)
    return max(0.2, float(m.group(1).replace(",", ".")))


def parse_and_strip_cues(
    text: str,
    *,
    default_pause_seconds: float = 2.0,
) -> tuple[str, list[CueEvent]]:
    """Extrai cues do texto e devolve (fala_limpa, eventos na ordem)."""
    if not text:
        return "", []

    events: list[CueEvent] = []
    work = text

    # 1) Estruturados {{PAUSE:30}} etc. — substitui por placeholder ordenado.
    placeholders: list[CueEvent] = []

    def _struct_sub(match: re.Match[str]) -> str:
        kind = match.group(1).upper()
        arg = (match.group(2) or "").strip()
        src = match.group(0)
        if kind == "PAUSE":
            sec = _pause_seconds(arg, default_pause_seconds)
            placeholders.append(
                CueEvent(kind="pause", arg=arg or str(int(sec)), seconds=sec, source=src)
            )
        elif kind == "BED":
            placeholders.append(
                CueEvent(kind="bed", arg=arg or "locucao", seconds=0.0, source=src)
            )
        elif kind in {"VINHETA", "STINGER"}:
            placeholders.append(
                CueEvent(
                    kind="vinheta" if kind == "VINHETA" else "stinger",
                    arg=arg or ("open" if kind == "VINHETA" else "hit"),
                    seconds=0.0,
                    source=src,
                )
            )
        else:  # SFX
            placeholders.append(
                CueEvent(kind="stinger", arg=arg or "hit", seconds=0.0, source=src)
            )
        return f"\0CUE{len(placeholders) - 1}\0"

    work = _STRUCTURED_CUE_RE.sub(_struct_sub, work)

    # 2) Livre → placeholder
    for pat, kind, fixed_arg in _FREEFORM_PATTERNS:
        def _free_sub(match: re.Match[str], _kind=kind, _fixed=fixed_arg) -> str:
            src = match.group(0)
            if _kind == "pause":
                sec = _pause_seconds(
                    match.group(1) if match.lastindex else None,
                    default_pause_seconds,
                )
                placeholders.append(
                    CueEvent(
                        kind="pause",
                        arg=str(int(sec)) if sec == int(sec) else f"{sec:.1f}",
                        seconds=sec,
                        source=src,
                    )
                )
            else:
                placeholders.append(
                    CueEvent(
                        kind=_kind,  # type: ignore[arg-type]
                        arg=_fixed or "",
                        seconds=0.0,
                        source=src,
                    )
                )
            return f"\0CUE{len(placeholders) - 1}\0"

        work = pat.sub(_free_sub, work)

    work = _LABEL_ONLY_RE.sub("", work)

    # 3) Percorre fala + placeholders na ordem
    parts = re.split(r"(\0CUE\d+\0)", work)
    speech_chunks: list[str] = []
    for part in parts:
        if not part:
            continue
        m = re.fullmatch(r"\0CUE(\d+)\0", part)
        if m:
            events.append(placeholders[int(m.group(1))])
            continue
        chunk = re.sub(r"\s+", " ", part).strip(" \n\t-–—•")
        if chunk:
            speech_chunks.append(chunk)
            # fala intercala com cues; a fala em si não é CueEvent aqui —
            # o caller une speech_chunks para TTS.

    spoken = re.sub(r"\s+", " ", " ".join(speech_chunks)).strip()
    spoken = re.sub(r"\s+([,.;:!?])", r"\1", spoken)
    return spoken, events


def annotate_script(speech_blocks: list[tuple[str, str, list[CueEvent]]]) -> str:
    """Gera script de produção legível (cues + fala)."""
    lines: list[str] = []
    for role, spoken, cues in speech_blocks:
        lines.append(f"## {role}")
        for cue in cues:
            if cue.kind == "pause":
                lines.append(f"[PAUSA {cue.seconds:g}s]")
            elif cue.kind == "bed":
                lines.append(f"[SOM DE FUNDO: {cue.arg or 'locucao'}]")
            elif cue.kind == "vinheta":
                lines.append(f"[VINHETA: {cue.arg or 'open'}]")
            elif cue.kind == "stinger":
                lines.append(f"[SFX: {cue.arg or 'hit'}]")
        if spoken:
            lines.append(spoken)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


# ---------------------------------------------------------------------------
# PCM helpers
# ---------------------------------------------------------------------------


def _nframes(seconds: float, rate: int) -> int:
    return max(0, int(round(float(seconds) * float(rate))))


def write_pcm_wav(
    path: Path,
    pcm: bytes,
    *,
    rate: int = DEFAULT_RATE,
    channels: int = DEFAULT_CHANNELS,
    sampwidth: int = DEFAULT_SAMPWIDTH,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(sampwidth)
        handle.setframerate(rate)
        handle.writeframes(pcm)
    return path


def silence_pcm(seconds: float, *, rate: int = DEFAULT_RATE) -> bytes:
    n = _nframes(seconds, rate)
    return b"\x00\x00" * n


def _tone_pcm(
    seconds: float,
    *,
    freq: float,
    rate: int = DEFAULT_RATE,
    amplitude: float = 0.25,
    fade_in: float = 0.02,
    fade_out: float = 0.08,
) -> bytes:
    n = _nframes(seconds, rate)
    if n <= 0:
        return b""
    fade_in_n = min(n, _nframes(fade_in, rate))
    fade_out_n = min(n, _nframes(fade_out, rate))
    samples: list[int] = []
    for i in range(n):
        t = i / rate
        env = 1.0
        if fade_in_n and i < fade_in_n:
            env *= i / fade_in_n
        if fade_out_n and i >= n - fade_out_n:
            env *= (n - i) / fade_out_n
        val = math.sin(2.0 * math.pi * freq * t) * amplitude * env
        samples.append(int(max(-1.0, min(1.0, val)) * 32767))
    return struct.pack("<" + "h" * n, *samples)


def _soft_noise_bed_pcm(
    seconds: float,
    *,
    rate: int = DEFAULT_RATE,
    amplitude: float = 0.06,
    seed: int = 42,
) -> bytes:
    """Bed suave (ruído filtrado barato) para 'som de fundo de locução'."""
    n = _nframes(seconds, rate)
    if n <= 0:
        return b""
    # LCG simples — determinístico, sem random global.
    state = seed & 0xFFFFFFFF
    samples: list[int] = []
    prev = 0.0
    fade_n = min(n, _nframes(0.15, rate))
    for i in range(n):
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        white = (state / 0xFFFFFFFF) * 2.0 - 1.0
        # low-pass 1-pole ~ soft bed
        prev = 0.94 * prev + 0.06 * white
        env = 1.0
        if fade_n and i < fade_n:
            env *= i / fade_n
        if fade_n and i >= n - fade_n:
            env *= (n - i) / fade_n
        # leve modulação para não ser estático
        lfo = 0.85 + 0.15 * math.sin(2.0 * math.pi * 0.15 * (i / rate))
        val = prev * amplitude * env * lfo
        samples.append(int(max(-1.0, min(1.0, val)) * 32767))
    return struct.pack("<" + "h" * n, *samples)


def _vinheta_pcm(seconds: float, *, rate: int = DEFAULT_RATE, open_style: bool = True) -> bytes:
    """Vinheta curta com 3 tons (abertura) ou 2 tons descendentes (fechamento)."""
    if seconds <= 0:
        return b""
    freqs = (392.0, 523.25, 659.25) if open_style else (523.25, 392.0)
    piece = seconds / len(freqs)
    chunks = [
        _tone_pcm(piece, freq=f, rate=rate, amplitude=0.22, fade_in=0.01, fade_out=0.06)
        for f in freqs
    ]
    return b"".join(chunks)


def _stinger_pcm(*, rate: int = DEFAULT_RATE) -> bytes:
    return _tone_pcm(0.35, freq=880.0, rate=rate, amplitude=0.18, fade_in=0.005, fade_out=0.12)


def mix_pcm(
    voice: bytes,
    bed: bytes,
    *,
    voice_gain: float = 1.0,
    bed_gain: float = 0.09,
) -> bytes:
    """Mix mono 16-bit; faz loop do bed até cobrir a voz."""
    if not voice:
        return bed
    if not bed:
        return voice

    def _samples(pcm: bytes) -> list[int]:
        n = len(pcm) // 2
        return list(struct.unpack("<" + "h" * n, pcm[: n * 2]))

    v = _samples(voice)
    b = _samples(bed)
    if not b:
        return voice
    out: list[int] = []
    blen = len(b)
    for i, vs in enumerate(v):
        bs = b[i % blen]
        mixed = int(vs * voice_gain + bs * bed_gain)
        if mixed > 32767:
            mixed = 32767
        elif mixed < -32768:
            mixed = -32768
        out.append(mixed)
    return struct.pack("<" + "h" * len(out), *out)


def loop_pcm_to_duration(pcm: bytes, seconds: float, *, rate: int) -> bytes:
    need = _nframes(seconds, rate) * 2
    if need <= 0:
        return b""
    if not pcm:
        return silence_pcm(seconds, rate=rate)
    if len(pcm) >= need:
        return pcm[:need]
    reps = (need // len(pcm)) + 1
    return (pcm * reps)[:need]


# ---------------------------------------------------------------------------
# Asset generation
# ---------------------------------------------------------------------------


def ensure_cue_assets(
    cues_dir: Path,
    *,
    settings: CueSettings,
) -> dict[str, Path]:
    """Gera (ou reutiliza) assets base de produção."""
    cues_dir.mkdir(parents=True, exist_ok=True)
    rate = settings.rate
    assets: dict[str, Path] = {}

    pause_path = cues_dir / "pause_default.wav"
    if not pause_path.exists():
        write_pcm_wav(
            pause_path,
            silence_pcm(settings.default_pause_seconds, rate=rate),
            rate=rate,
        )
    assets["pause_default"] = pause_path

    bed_path = cues_dir / "bed_locucao.wav"
    if not bed_path.exists():
        # Bed longo o bastante para loop sob segmentos (~3 min).
        write_pcm_wav(
            bed_path,
            _soft_noise_bed_pcm(180.0, rate=rate, amplitude=0.07),
            rate=rate,
        )
    assets["bed_locucao"] = bed_path

    v_open = cues_dir / "vinheta_open.wav"
    if not v_open.exists():
        write_pcm_wav(
            v_open,
            _vinheta_pcm(settings.vinheta_open_seconds, rate=rate, open_style=True),
            rate=rate,
        )
    assets["vinheta_open"] = v_open

    v_close = cues_dir / "vinheta_close.wav"
    if not v_close.exists():
        write_pcm_wav(
            v_close,
            _vinheta_pcm(settings.vinheta_close_seconds, rate=rate, open_style=False),
            rate=rate,
        )
    assets["vinheta_close"] = v_close

    stinger = cues_dir / "stinger_hit.wav"
    if not stinger.exists():
        write_pcm_wav(stinger, _stinger_pcm(rate=rate), rate=rate)
    assets["stinger_hit"] = stinger

    return assets


def pause_wav(
    cues_dir: Path,
    seconds: float,
    *,
    rate: int = DEFAULT_RATE,
) -> Path:
    sec = max(0.2, float(seconds))
    name = f"pause_{sec:g}s.wav".replace(".", "p")
    path = cues_dir / name
    if not path.exists():
        write_pcm_wav(path, silence_pcm(sec, rate=rate), rate=rate)
    return path


# ---------------------------------------------------------------------------
# Timeline render
# ---------------------------------------------------------------------------


@dataclass
class TimelineItem:
    kind: CueKind
    path: Path | None = None
    pcm: bytes | None = None
    label: str = ""
    seconds: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)


def _read_wav(path: Path) -> tuple[bytes, int]:
    with wave.open(str(path), "rb") as handle:
        rate = handle.getframerate()
        channels = handle.getnchannels()
        sampwidth = handle.getsampwidth()
        frames = handle.readframes(handle.getnframes())
    if sampwidth != 2:
        raise RuntimeError(f"WAV precisa ser 16-bit: {path}")
    if channels > 1:
        n = len(frames) // (2 * channels)
        mono = []
        for i in range(n):
            off = i * channels * 2
            mono.append(struct.unpack_from("<h", frames, off)[0])
        frames = struct.pack("<" + "h" * n, *mono)
    return frames, rate


def _resample_if_needed(pcm: bytes, src_rate: int, dst_rate: int) -> bytes:
    if src_rate == dst_rate or not pcm:
        return pcm
    # Import local para evitar ciclo com segments se preferir — reimplementação mínima.
    import array

    samples = array.array("h")
    samples.frombytes(pcm)
    src_len = len(samples)
    dst_len = max(1, int(round(src_len * float(dst_rate) / float(src_rate))))
    out = array.array("h", [0] * dst_len)
    if src_len == 1:
        return array.array("h", [samples[0]] * dst_len).tobytes()
    for i in range(dst_len):
        pos = i * (src_len - 1) / (dst_len - 1)
        i0 = int(pos)
        i1 = min(i0 + 1, src_len - 1)
        frac = pos - i0
        out[i] = int(samples[i0] * (1.0 - frac) + samples[i1] * frac)
    return out.tobytes()


def build_production_timeline(
    *,
    speech_wavs: list[tuple[str, Path, list[CueEvent]]],
    cues_dir: Path,
    settings: CueSettings,
) -> list[TimelineItem]:
    """Monta timeline: vinheta → (cues + fala com bed) × N → vinheta final."""
    assets = ensure_cue_assets(cues_dir, settings=settings)
    rate = settings.rate
    timeline: list[TimelineItem] = []

    if settings.vinheta_open:
        timeline.append(
            TimelineItem(
                kind="vinheta",
                path=assets["vinheta_open"],
                label="vinheta_open",
                seconds=settings.vinheta_open_seconds,
            )
        )

    bed_pcm_cache: bytes | None = None
    bed_rate = rate

    def bed_pcm() -> bytes:
        nonlocal bed_pcm_cache, bed_rate
        if bed_pcm_cache is None:
            bed_pcm_cache, bed_rate = _read_wav(assets["bed_locucao"])
            bed_pcm_cache = _resample_if_needed(bed_pcm_cache, bed_rate, rate)
            bed_rate = rate
        return bed_pcm_cache

    for idx, (role, wav_path, cues) in enumerate(speech_wavs):
        want_bed = settings.bed_under_speech
        for cue in cues:
            if cue.kind == "pause":
                p = pause_wav(cues_dir, cue.seconds or settings.default_pause_seconds, rate=rate)
                timeline.append(
                    TimelineItem(
                        kind="pause",
                        path=p,
                        label=f"pause_{cue.seconds:g}s",
                        seconds=float(cue.seconds or settings.default_pause_seconds),
                        meta={"source": cue.source, "role": role},
                    )
                )
            elif cue.kind == "bed":
                want_bed = True
                # Bed solo curto antes da fala (atmosfera).
                solo = loop_pcm_to_duration(
                    bed_pcm(), settings.bed_idle_seconds, rate=rate
                )
                solo_path = cues_dir / f"bed_idle_{idx + 1:02d}.wav"
                write_pcm_wav(solo_path, solo, rate=rate)
                timeline.append(
                    TimelineItem(
                        kind="bed",
                        path=solo_path,
                        label="bed_idle",
                        seconds=settings.bed_idle_seconds,
                        meta={"source": cue.source, "role": role},
                    )
                )
            elif cue.kind == "vinheta":
                which = "vinheta_open" if "close" not in (cue.arg or "").lower() else "vinheta_close"
                timeline.append(
                    TimelineItem(
                        kind="vinheta",
                        path=assets[which],
                        label=which,
                        seconds=settings.vinheta_open_seconds
                        if which == "vinheta_open"
                        else settings.vinheta_close_seconds,
                        meta={"source": cue.source, "role": role},
                    )
                )
            elif cue.kind == "stinger":
                timeline.append(
                    TimelineItem(
                        kind="stinger",
                        path=assets["stinger_hit"],
                        label="stinger_hit",
                        seconds=0.35,
                        meta={"source": cue.source, "role": role},
                    )
                )

        if not wav_path.exists():
            continue
        voice_pcm, voice_rate = _read_wav(wav_path)
        voice_pcm = _resample_if_needed(voice_pcm, voice_rate, rate)
        voice_secs = len(voice_pcm) / 2 / rate
        if want_bed:
            mixed = mix_pcm(
                voice_pcm,
                loop_pcm_to_duration(bed_pcm(), voice_secs + 0.05, rate=rate),
                voice_gain=settings.voice_gain,
                bed_gain=settings.bed_gain,
            )
            mixed_path = cues_dir / f"speech_bed_{idx + 1:02d}_{role}.wav"
            write_pcm_wav(mixed_path, mixed, rate=rate)
            timeline.append(
                TimelineItem(
                    kind="speech",
                    path=mixed_path,
                    label=f"speech+bed:{role}",
                    seconds=voice_secs,
                    meta={"role": role, "source_wav": str(wav_path.name)},
                )
            )
        else:
            timeline.append(
                TimelineItem(
                    kind="speech",
                    path=wav_path,
                    label=f"speech:{role}",
                    seconds=voice_secs,
                    meta={"role": role, "source_wav": str(wav_path.name)},
                )
            )

        # Pausa padrão entre segmentos (exceto último).
        if idx < len(speech_wavs) - 1 and settings.pause_between_segments_seconds > 0:
            p = pause_wav(
                cues_dir, settings.pause_between_segments_seconds, rate=rate
            )
            timeline.append(
                TimelineItem(
                    kind="pause",
                    path=p,
                    label="pause_between_segments",
                    seconds=settings.pause_between_segments_seconds,
                    meta={"role": role},
                )
            )

    if settings.vinheta_close:
        timeline.append(
            TimelineItem(
                kind="vinheta",
                path=assets["vinheta_close"],
                label="vinheta_close",
                seconds=settings.vinheta_close_seconds,
            )
        )

    return timeline


def render_timeline(
    timeline: list[TimelineItem],
    output_path: Path,
    *,
    rate: int = DEFAULT_RATE,
) -> float:
    """Concatena itens da timeline em um único WAV. Retorna duração em segundos."""
    if not timeline:
        raise ValueError("Timeline vazia.")
    pcm_out = bytearray()
    for item in timeline:
        if item.pcm is not None:
            pcm_out.extend(item.pcm)
            continue
        if item.path is None or not item.path.exists():
            logger.warning("Item de timeline sem áudio: %s", item.label)
            continue
        frames, src_rate = _read_wav(item.path)
        pcm_out.extend(_resample_if_needed(frames, src_rate, rate))

    write_pcm_wav(output_path, bytes(pcm_out), rate=rate)
    return len(pcm_out) / 2 / float(rate)


def write_cue_manifest(
    path: Path,
    *,
    timeline: list[TimelineItem],
    settings: CueSettings,
    speech_blocks: list[dict[str, Any]],
) -> None:
    payload = {
        "settings": asdict(settings),
        "speech_blocks": speech_blocks,
        "timeline": [
            {
                "kind": t.kind,
                "label": t.label,
                "seconds": t.seconds,
                "path": str(t.path) if t.path else "",
                "meta": t.meta,
            }
            for t in timeline
        ],
        "total_seconds": sum(t.seconds for t in timeline),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def apply_cues_to_production(
    *,
    speech_units: list[tuple[str, str, Path]],
    # (role, spoken_text_original, wav_path)
    day_dir: Path,
    settings: CueSettings | None = None,
    output_wav: Path | None = None,
) -> dict[str, Any]:
    """Pipeline completo de cues para uma edição já com WAVs de fala.

    Returns dict com paths e duração.
    """
    settings = settings or default_cue_settings()
    if not settings.enabled:
        return {"enabled": False}

    cues_dir = day_dir / "cues"
    ensure_cue_assets(cues_dir, settings=settings)

    speech_wavs: list[tuple[str, Path, list[CueEvent]]] = []
    speech_blocks_meta: list[dict[str, Any]] = []
    script_parts: list[tuple[str, str, list[CueEvent]]] = []
    spoken_clean_parts: list[str] = []

    for role, original_text, wav_path in speech_units:
        spoken, cues = parse_and_strip_cues(
            original_text,
            default_pause_seconds=settings.default_pause_seconds,
        )
        # Se o WAV já foi gerado do texto limpo, usamos os cues extraídos do original.
        speech_wavs.append((role, wav_path, cues))
        script_parts.append((role, spoken or original_text, cues))
        if spoken:
            spoken_clean_parts.append(spoken)
        speech_blocks_meta.append(
            {
                "role": role,
                "spoken": spoken,
                "cues": [asdict(c) for c in cues],
                "wav": str(wav_path.name) if wav_path else "",
            }
        )

    timeline = build_production_timeline(
        speech_wavs=speech_wavs,
        cues_dir=cues_dir,
        settings=settings,
    )
    out = output_wav or (day_dir / "locution.wav")
    duration = render_timeline(timeline, out, rate=settings.rate)

    script_path = day_dir / "locution.script.txt"
    script_path.write_text(annotate_script(script_parts), encoding="utf-8")
    spoken_path = day_dir / "locution.spoken.txt"
    spoken_path.write_text("\n\n".join(spoken_clean_parts).strip() + "\n", encoding="utf-8")
    manifest_path = cues_dir / "manifest.json"
    write_cue_manifest(
        manifest_path,
        timeline=timeline,
        settings=settings,
        speech_blocks=speech_blocks_meta,
    )

    logger.info(
        "Cues de produção: %s itens → %.1fs (%s)",
        len(timeline),
        duration,
        out,
    )
    return {
        "enabled": True,
        "duration_seconds": duration,
        "wav_path": str(out),
        "cues_dir": str(cues_dir),
        "manifest": str(manifest_path),
        "script": str(script_path),
        "spoken": str(spoken_path),
        "timeline_items": len(timeline),
    }
