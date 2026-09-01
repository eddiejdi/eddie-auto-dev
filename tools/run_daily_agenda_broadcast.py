#!/usr/bin/env python3
"""Orquestrador da agenda diaria: coleta -> LLM -> TTS -> Telegram."""
from __future__ import annotations

import argparse
import importlib.util
import logging
import os
import sys
import wave
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from agenda_media_router import resolve_media_plan, tts_fallback_chain
from daily_agenda_approval import send_preview_request, wait_for_decision
from daily_agenda_config import load_audio_settings, load_config
from daily_agenda_job_status import PanelJobReporter
from daily_agenda_segments import (
    generate_modular_locution,
    should_use_modular,
)
from specialized_agents.telegram_notify import send_telegram_audio, send_telegram_message
from tools.secrets_loader import get_agenda_telegram_chat_id

logger = logging.getLogger(__name__)

DEFAULT_ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "daily_agenda"
AGENDA_MODULE_PATH = TOOLS_DIR / "build_flavio_bolsonaro_agenda_source.py"
TTS_MODULE_PATH = TOOLS_DIR / "test_cpu_tts_from_generated_text.py"


@dataclass(frozen=True)
class BroadcastArtifacts:
    date_str: str
    source_text: str
    final_text: str
    source_path: Path
    locution_text_path: Path
    wav_path: Path | None
    sources_used: tuple[str, ...]
    sources_failed: tuple[str, ...]
    llm_endpoint: str = ""
    tts_backend: str = ""
    quality: str = "balanced"


def _load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Nao foi possivel carregar modulo {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def resolve_date(date_arg: str | None) -> str:
    if date_arg in (None, "", "today", "hoje"):
        return datetime.now().strftime("%Y-%m-%d")
    datetime.strptime(date_arg, "%Y-%m-%d")
    return date_arg


def artifact_paths(date_str: str, artifacts_dir: Path) -> dict[str, Path]:
    day_dir = artifacts_dir / date_str
    return {
        "day_dir": day_dir,
        "source": day_dir / "source.txt",
        "locution_text": day_dir / "locution.txt",
        "wav": day_dir / "locution.wav",
    }


def _escape_telegram_md(text: str) -> str:
    """Escapa caracteres que quebram parse_mode Markdown legado do Telegram."""
    if not text:
        return ""
    # Ordem importa: barra primeiro.
    return (
        text.replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("*", "\\*")
        .replace("_", "\\_")
        .replace("[", "\\[")
    )


def build_telegram_summary(
    *,
    date_str: str,
    collected,
    source_text: str,
    final_text: str,
    agenda_mod,
    llm_endpoint: str,
    tts_backend: str,
    quality: str,
) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    header = (
        f"📻 *Agenda Diária — Flávio Bolsonaro*\n"
        f"📅 {dt.strftime('%d/%m/%Y')}\n"
    )

    lines: list[str] = []
    if collected.entries:
        lines.append(f"*Compromissos:* {len(collected.entries)}")
        for entry in collected.entries[:5]:
            label = entry.committee_sigla
            if entry.entry_type == "plenary":
                label = "Plenário"
            lines.append(
                f"• {_escape_telegram_md(entry.time_label)} — {_escape_telegram_md(label)}"
            )
    else:
        lines.append("_Sem compromissos formais confirmados nas fontes oficiais._")

    if collected.news:
        lines.append(f"\n*Imprensa:* {len(collected.news)} matéria(s) distinta(s)")
        from build_flavio_bolsonaro_agenda_source import format_news_outlets

        for item in collected.news[:5]:
            title = _escape_telegram_md(item.title)
            outlets = _escape_telegram_md(format_news_outlets(item))
            lines.append(f"• {title} (publicado por {outlets})")

    if collected.sources_used:
        fontes = _escape_telegram_md(", ".join(collected.sources_used))
        lines.append(f"\nFontes: {fontes}")

    if llm_endpoint or tts_backend:
        q = _escape_telegram_md(quality)
        llm = _escape_telegram_md(llm_endpoint or "n/a")
        tts = _escape_telegram_md(tts_backend or "n/a")
        lines.append(f"\nMidia: qualidade `{q}` | LLM `{llm}` | TTS `{tts}`")

    body_preview = _escape_telegram_md(final_text.strip())
    if len(body_preview) > 900:
        body_preview = body_preview[:897] + "..."
    lines.append(f"\n{body_preview}")
    return header + "\n".join(lines)


def wav_duration_seconds(path: Path) -> float:
    """Duração em segundos de um WAV PCM."""
    with wave.open(str(path), "rb") as handle:
        frames = handle.getnframes()
        rate = handle.getframerate() or 1
        return float(frames) / float(rate)


def _lengthen_source_for_duration(source_text: str, *, min_duration_seconds: int, attempt: int) -> str:
    """Anexa instrução explícita de duração mínima ao texto-base (retry)."""
    hint = (
        f"\n\n[INSTRUCAO DE DURACAO — tentativa {attempt}] "
        f"O audio final precisa ter no minimo {min_duration_seconds} segundos. "
        "Expanda e reescreva com mais detalhes factuais ja presentes no texto-base, "
        "sem inventar fatos, ate atingir densidade suficiente para essa duracao."
    )
    return source_text.rstrip() + hint


def prepare_locution_text(
    source_text: str,
    *,
    tts_mod,
    llm_endpoints,
    max_rounds: int,
    retry_wait_seconds: int,
    no_expand: bool,
    no_rewrite: bool,
    no_normalize: bool,
) -> tuple[str, str]:
    llm_endpoint = ""
    expanded_text = source_text
    if not no_expand:
        try:
            expanded_text, llm_endpoint = tts_mod.expand_details_with_llm_chain(
                source_text,
                endpoints=llm_endpoints,
                max_rounds=max_rounds,
                retry_wait_seconds=retry_wait_seconds,
            )
        except Exception:
            logger.warning("Expansao via cadeia LLM indisponivel; usando texto-fonte.", exc_info=True)
            expanded_text = source_text

    normalized_text = (
        expanded_text if no_normalize else tts_mod.normalize_for_speech(expanded_text)
    )
    final_text = tts_mod.heuristic_rewrite_for_broadcast(normalized_text)

    if not no_rewrite:
        try:
            candidate_text, rewrite_endpoint = tts_mod.rewrite_for_broadcast_with_llm_chain(
                final_text,
                endpoints=llm_endpoints,
                max_rounds=max_rounds,
                retry_wait_seconds=retry_wait_seconds,
            )
            if tts_mod.is_valid_broadcast_text(candidate_text):
                final_text = candidate_text
                llm_endpoint = rewrite_endpoint or llm_endpoint
        except Exception:
            logger.warning("Reescrita via cadeia LLM indisponivel; mantendo texto heuristico.", exc_info=True)

    return final_text, llm_endpoint


def synthesize_audio(
    final_text: str,
    *,
    tts_mod,
    wav_output: Path,
    tts_settings,
) -> str | None:
    backends = tts_fallback_chain(tts_settings)
    return tts_mod.synthesize_with_fallbacks(
        final_text,
        wav_output,
        backends=backends,
        piper_voice=tts_settings.piper_voice,
        google_voice=tts_settings.google_voice,
        piper_use_cuda=tts_settings.piper_use_cuda,
        piper_cuda_device=tts_settings.piper_cuda_device,
        kokoro_voice=tts_settings.kokoro_voice,
        kokoro_device=tts_settings.kokoro_device,
    )


def prepare_locution_and_audio(
    source_text: str,
    *,
    tts_mod,
    llm_endpoints,
    max_rounds: int,
    retry_wait_seconds: int,
    no_expand: bool,
    no_rewrite: bool,
    no_normalize: bool,
    skip_audio: bool,
    wav_output: Path,
    tts_settings,
    min_duration_seconds: int = 0,
    max_length_retries: int = 0,
    day_dir: Path | None = None,
    audio_settings: dict | None = None,
) -> tuple[str, str, Path | None, str, float]:
    """Gera locução + áudio.

    Se a duração alvo for longa (modular), planeja N segmentos, gera LLM+TTS
    por parte e concatena o WAV final. Caso contrário, mantém o fluxo single-shot
    com retries de alongamento.
    """
    audio_cfg = dict(audio_settings or {})
    use_modular = should_use_modular(
        min_duration_seconds,
        modular=audio_cfg.get("modular"),
        modular_threshold_seconds=int(audio_cfg.get("modular_threshold_seconds") or 300),
    )

    if use_modular and min_duration_seconds > 0:
        work_dir = day_dir or wav_output.parent
        logger.info(
            "Usando pipeline modular (alvo=%ss, segmento~%ss).",
            min_duration_seconds,
            audio_cfg.get("segment_target_seconds", 180),
        )
        from daily_agenda_segments import (
            classify_source_mode,
            DEFAULT_SEM_PAUTA_MAX_DURATION,
            DEFAULT_SEM_PAUTA_MAX_SEGMENTS,
        )

        source_mode = classify_source_mode(source_text)
        sem_cap = int(
            audio_cfg.get("sem_pauta_max_duration_seconds") or DEFAULT_SEM_PAUTA_MAX_DURATION
        )
        sem_max_seg = int(
            audio_cfg.get("sem_pauta_max_segments") or DEFAULT_SEM_PAUTA_MAX_SEGMENTS
        )
        allow_extras = bool(audio_cfg.get("sem_pauta_allow_extras", False))
        if source_mode == "sem_pauta" and not allow_extras:
            # Dia vazio: não forçar 2ª leva para encher 1h.
            max_length_retries = 0

        modular = generate_modular_locution(
            source_text,
            day_dir=work_dir,
            wav_output=wav_output,
            tts_mod=tts_mod,
            llm_endpoints=llm_endpoints,
            tts_settings=tts_settings,
            synthesize_fn=synthesize_audio,
            min_duration_seconds=min_duration_seconds,
            segment_target_seconds=int(audio_cfg.get("segment_target_seconds") or 180),
            segment_gap_seconds=float(audio_cfg.get("segment_gap_seconds") or 0.6),
            words_per_minute=int(audio_cfg.get("words_per_minute") or 140),
            max_rounds=max_rounds,
            retry_wait_seconds=retry_wait_seconds,
            no_expand=no_expand,
            no_normalize=no_normalize,
            skip_audio=skip_audio,
            max_segments=int(audio_cfg.get("max_segments") or 40),
            editor_enabled=bool(audio_cfg.get("editor_enabled", True)),
            editor_batch_size=int(audio_cfg.get("editor_batch_size") or 3),
            llm_parallel=int(audio_cfg.get("llm_parallel") or 3),
            sem_pauta_max_duration_seconds=sem_cap,
            sem_pauta_max_segments=sem_max_seg,
        )
        # Se o modular ficou muito abaixo do alvo e ainda há retries, alonga
        # com uma passagem extra de segmentos (re-planeja com alvo residual).
        duration = modular.duration_seconds
        attempts_left = max(0, max_length_retries)
        while (
            not skip_audio
            and attempts_left > 0
            and duration + 1.0 < float(min_duration_seconds)
            and modular.wav_path
        ):
            deficit = int(min_duration_seconds - duration)
            logger.info(
                "Modular abaixo do alvo (%.1fs < %ss). Gerando segmentos extras (~%ss)…",
                duration,
                min_duration_seconds,
                deficit,
            )
            extra = generate_modular_locution(
                _lengthen_source_for_duration(
                    source_text,
                    min_duration_seconds=min_duration_seconds,
                    attempt=max_length_retries - attempts_left + 2,
                ),
                day_dir=work_dir / f"segments_extra_{max_length_retries - attempts_left + 1}",
                wav_output=work_dir / f"_extra_{max_length_retries - attempts_left + 1}.wav",
                tts_mod=tts_mod,
                llm_endpoints=llm_endpoints,
                tts_settings=tts_settings,
                synthesize_fn=synthesize_audio,
                min_duration_seconds=max(deficit, int(audio_cfg.get("segment_target_seconds") or 180)),
                segment_target_seconds=int(audio_cfg.get("segment_target_seconds") or 180),
                segment_gap_seconds=float(audio_cfg.get("segment_gap_seconds") or 0.6),
                words_per_minute=int(audio_cfg.get("words_per_minute") or 140),
                max_rounds=max_rounds,
                retry_wait_seconds=retry_wait_seconds,
                no_expand=no_expand,
                no_normalize=no_normalize,
                skip_audio=False,
                max_segments=int(audio_cfg.get("max_segments") or 40),
                editor_enabled=bool(audio_cfg.get("editor_enabled", True)),
                editor_batch_size=int(audio_cfg.get("editor_batch_size") or 3),
                llm_parallel=int(audio_cfg.get("llm_parallel") or 3),
                sem_pauta_max_duration_seconds=sem_cap,
                sem_pauta_max_segments=sem_max_seg,
            )
            if extra.wav_path and extra.wav_path.exists():
                from daily_agenda_segments import concat_wav_files

                parts = [modular.wav_path, extra.wav_path]
                duration = concat_wav_files(
                    parts,
                    wav_output,
                    gap_seconds=float(audio_cfg.get("segment_gap_seconds") or 0.6),
                )
                modular.final_text = (modular.final_text + "\n\n" + extra.final_text).strip()
                modular.wav_path = wav_output
                modular.duration_seconds = duration
                modular.llm_endpoint = extra.llm_endpoint or modular.llm_endpoint
                modular.tts_backend = extra.tts_backend or modular.tts_backend
            attempts_left -= 1

        if not skip_audio and duration + 1.0 < float(min_duration_seconds):
            logger.warning(
                "Audio modular ficou em %.1fs abaixo do minimo %ss apos extras; seguindo assim.",
                duration,
                min_duration_seconds,
            )
        return (
            modular.final_text,
            modular.llm_endpoint,
            modular.wav_path if modular.wav_path and modular.wav_path.exists() else None,
            modular.tts_backend,
            modular.duration_seconds,
        )

    # --- Fluxo single-shot (boletins curtos) ---
    working_source = source_text
    final_text = source_text
    llm_endpoint = ""
    wav_path: Path | None = None
    tts_backend = ""
    duration = 0.0
    attempts = 1 + max(0, max_length_retries)

    for attempt in range(1, attempts + 1):
        final_text, llm_endpoint = prepare_locution_text(
            working_source,
            tts_mod=tts_mod,
            llm_endpoints=llm_endpoints,
            max_rounds=max_rounds,
            retry_wait_seconds=retry_wait_seconds,
            no_expand=no_expand,
            no_rewrite=no_rewrite,
            no_normalize=no_normalize,
        )
        if skip_audio:
            return final_text, llm_endpoint, None, "", 0.0

        try:
            tts_backend = synthesize_audio(
                final_text,
                tts_mod=tts_mod,
                wav_output=wav_output,
                tts_settings=tts_settings,
            ) or ""
            wav_path = wav_output if wav_output.exists() else None
        except Exception:
            logger.warning(
                "Falha ao sintetizar audio (tentativa %s/%s).",
                attempt,
                attempts,
                exc_info=True,
            )
            wav_path = None
            break

        if not wav_path:
            break

        try:
            duration = wav_duration_seconds(wav_path)
        except Exception:
            logger.warning("Nao foi possivel medir duracao de %s", wav_path, exc_info=True)
            duration = 0.0
            break

        logger.info(
            "Audio tentativa %s/%s: %.1fs (minimo=%ss)",
            attempt,
            attempts,
            duration,
            min_duration_seconds,
        )
        if min_duration_seconds <= 0 or duration + 0.05 >= float(min_duration_seconds):
            break

        if attempt >= attempts:
            logger.warning(
                "Audio ficou em %.1fs abaixo do minimo %ss apos %s tentativas; seguindo assim.",
                duration,
                min_duration_seconds,
                attempts,
            )
            break

        logger.info(
            "Audio curto (%.1fs < %ss). Regenerando locucao (tentativa %s)…",
            duration,
            min_duration_seconds,
            attempt + 1,
        )
        working_source = _lengthen_source_for_duration(
            source_text,
            min_duration_seconds=min_duration_seconds,
            attempt=attempt + 1,
        )

    return final_text, llm_endpoint, wav_path, tts_backend, duration


def run_broadcast(
    *,
    date_str: str,
    mode: str,
    artifacts_dir: Path,
    timeout: int,
    retries: int,
    trust_env: bool,
    include_news: bool,
    deep_search: bool,
    media_plan,
    max_rounds: int,
    retry_wait_seconds: int,
    no_expand: bool,
    no_rewrite: bool,
    no_normalize: bool,
    skip_telegram: bool,
    skip_audio: bool,
    telegram_chat_id: str | None,
    telegram_mode: str = "full",
    approval_attempt: int = 1,
    min_duration_seconds: int | None = None,
    max_length_retries: int | None = None,
    segment_target_seconds: int | None = None,
    force_modular: bool | None = None,
) -> BroadcastArtifacts:
    agenda_mod = _load_module(AGENDA_MODULE_PATH, "agenda_source_runtime")
    tts_mod = _load_module(TTS_MODULE_PATH, "tts_runtime")

    collected = agenda_mod.load_entries(
        date_str,
        mode=mode,
        timeout=timeout,
        trust_env=trust_env,
        retries=retries,
        include_news=include_news,
        deep_search=deep_search,
    )
    source_text = agenda_mod.build_source_text(
        collected,
        date_label=agenda_mod.format_date_label(date_str),
    )

    paths = artifact_paths(date_str, artifacts_dir)
    paths["day_dir"].mkdir(parents=True, exist_ok=True)
    agenda_mod.write_text(paths["source"], source_text)

    audio_cfg = dict(load_audio_settings())
    min_duration = (
        int(min_duration_seconds)
        if min_duration_seconds is not None
        else int(audio_cfg.get("min_duration_seconds", 0) or 0)
    )
    length_retries = (
        int(max_length_retries)
        if max_length_retries is not None
        else int(audio_cfg.get("max_length_retries", 0) or 0)
    )
    if segment_target_seconds is not None:
        audio_cfg["segment_target_seconds"] = int(segment_target_seconds)
    if force_modular is False:
        audio_cfg["modular"] = False
    elif force_modular is True:
        audio_cfg["modular"] = True

    final_text, llm_endpoint, wav_path, tts_backend, audio_duration = prepare_locution_and_audio(
        source_text,
        tts_mod=tts_mod,
        llm_endpoints=media_plan.llm_endpoints,
        max_rounds=max_rounds,
        retry_wait_seconds=retry_wait_seconds,
        no_expand=no_expand,
        no_rewrite=no_rewrite,
        no_normalize=no_normalize,
        skip_audio=skip_audio,
        wav_output=paths["wav"],
        tts_settings=media_plan.tts,
        min_duration_seconds=min_duration,
        max_length_retries=length_retries,
        day_dir=paths["day_dir"],
        audio_settings=audio_cfg,
    )
    tts_mod.save_text(paths["locution_text"], final_text)
    if audio_duration > 0:
        logger.info("Duracao final do audio: %.1fs (minimo configurado=%ss)", audio_duration, min_duration)

    if not skip_telegram and telegram_chat_id:
        summary = build_telegram_summary(
            date_str=date_str,
            collected=collected,
            source_text=source_text,
            final_text=final_text,
            agenda_mod=agenda_mod,
            llm_endpoint=llm_endpoint,
            tts_backend=tts_backend,
            quality=media_plan.quality,
        )
        if telegram_mode == "preview":
            if wav_path and wav_path.exists():
                send_preview_request(
                    date_str=date_str,
                    summary_text=summary,
                    wav_path=wav_path,
                    chat_id=telegram_chat_id,
                    attempt=approval_attempt,
                    deep_search=deep_search,
                    entries_count=len(collected.entries),
                    news_count=len(collected.news),
                    quality=media_plan.quality,
                )
        else:
            send_telegram_message(summary, chat_id=telegram_chat_id, parse_mode="Markdown")
            if wav_path and wav_path.exists():
                caption = f"Agenda diária — {datetime.strptime(date_str, '%Y-%m-%d').strftime('%d/%m/%Y')}"
                send_telegram_audio(
                    str(wav_path),
                    chat_id=telegram_chat_id,
                    caption=caption,
                )

    return BroadcastArtifacts(
        date_str=date_str,
        source_text=source_text,
        final_text=final_text,
        source_path=paths["source"],
        locution_text_path=paths["locution_text"],
        wav_path=wav_path if wav_path and wav_path.exists() else None,
        sources_used=collected.sources_used,
        sources_failed=collected.sources_failed,
        llm_endpoint=llm_endpoint,
        tts_backend=tts_backend,
        quality=media_plan.quality,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Orquestra agenda diaria com audio no Telegram.")
    parser.add_argument("--date", default="today", help="Data YYYY-MM-DD, ou 'today'/'hoje'.")
    parser.add_argument("--mode", choices=("auto", "live", "snapshot"), default="auto")
    parser.add_argument("--artifacts-dir", type=Path, default=DEFAULT_ARTIFACTS_DIR)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--retries", type=int, default=4)
    parser.add_argument("--trust-env", action="store_true")
    parser.add_argument("--no-news", action="store_true")
    parser.add_argument(
        "--quality",
        choices=("fast", "balanced", "best"),
        default="balanced",
        help="Perfil de qualidade: fast (CPU), balanced (Piper GPU0), best (Kokoro/Gemini).",
    )
    parser.add_argument(
        "--backend",
        choices=("auto", "piper-cpu", "piper-gpu", "piper-local", "kokoro-gpu0", "gemini-tts", "none"),
        default="auto",
        help="Override do backend TTS (auto usa --quality).",
    )
    parser.add_argument("--piper-voice", default=None)
    parser.add_argument("--google-voice", default="Kore")
    parser.add_argument(
        "--llm-auto-route",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Roteia LLM GPU0 -> NAS -> GPU1 automaticamente.",
    )
    parser.add_argument("--ollama-host", default=None, help="Override manual do host LLM.")
    parser.add_argument("--ollama-model", default=None, help="Override manual do modelo LLM.")
    parser.add_argument("--ollama-fallback-models", default="")
    parser.add_argument("--llm-max-rounds", type=int, default=2)
    parser.add_argument("--llm-retry-wait-seconds", type=int, default=6)
    parser.add_argument("--no-llm-expand", action="store_true")
    parser.add_argument("--no-llm-rewrite", action="store_true")
    parser.add_argument("--no-normalize", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Gera artefatos sem enviar Telegram.")
    parser.add_argument("--skip-audio", action="store_true")
    parser.add_argument(
        "--min-audio-seconds",
        type=int,
        default=None,
        help="Duração alvo do áudio em segundos (default painel: 3600 = 1h). "
        "Acima do threshold modular, gera N segmentos e concatena.",
    )
    parser.add_argument(
        "--segment-seconds",
        type=int,
        default=None,
        help="Duração alvo por segmento no modo modular (default: 180s).",
    )
    parser.add_argument(
        "--no-modular",
        action="store_true",
        help="Força pipeline single-shot (sem segmentação/concatenação).",
    )
    parser.add_argument("--telegram-chat-id", default=None)
    parser.add_argument(
        "--upload-youtube",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Publica no canal YouTube após gerar o áudio.",
    )
    parser.add_argument(
        "--require-approval",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Envia prévia no Telegram e aguarda aprovação antes de publicar.",
    )
    parser.add_argument(
        "--approval-timeout-minutes",
        type=int,
        default=None,
        help="Tempo máximo aguardando aprovação no Telegram.",
    )
    parser.add_argument(
        "--max-regenerations",
        type=int,
        default=None,
        help="Máximo de regenerações com busca profunda.",
    )
    parser.add_argument(
        "--deep-search",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Coleta profunda (padrão: ligada). Use --no-deep-search para modo rápido.",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def _publish_youtube(date_str: str, artifacts_dir: Path, panel_cfg: dict) -> str:
    from youtube_agenda_publisher import publish_edition

    yt_result = publish_edition(date_str, artifacts_dir=artifacts_dir, config=panel_cfg)
    return yt_result.video_url


def _run_with_optional_approval(
    *,
    args: argparse.Namespace,
    panel_cfg: dict,
    date_str: str,
    media_plan,
    telegram_chat_id: str | None,
) -> tuple[BroadcastArtifacts, str, str]:
    approval_cfg = panel_cfg.get("approval", {})
    require_approval = (
        args.require_approval
        if args.require_approval is not None
        else panel_cfg["defaults"].get("require_approval", False)
    )
    upload_youtube = (
        args.upload_youtube
        if args.upload_youtube is not None
        else panel_cfg["defaults"].get("upload_youtube", False)
    )
    timeout_minutes = (
        args.approval_timeout_minutes
        if args.approval_timeout_minutes is not None
        else int(approval_cfg.get("timeout_minutes", 180))
    )
    max_regenerations = (
        args.max_regenerations
        if args.max_regenerations is not None
        else int(approval_cfg.get("max_regenerations", 2))
    )

    search_cfg = panel_cfg.get("search", {})
    attempt = 1
    deep_search = (
        args.deep_search
        if args.deep_search is not None
        else bool(search_cfg.get("deep_search", True))
    )
    if args.timeout == 45 and search_cfg.get("timeout"):
        args.timeout = int(search_cfg["timeout"])
    if args.retries == 4 and search_cfg.get("retries"):
        args.retries = int(search_cfg["retries"])
    youtube_url = ""
    approval_note = ""

    while True:
        result = run_broadcast(
            date_str=date_str,
            mode=args.mode,
            artifacts_dir=args.artifacts_dir,
            timeout=args.timeout,
            retries=args.retries,
            trust_env=args.trust_env,
            include_news=not args.no_news,
            deep_search=deep_search,
            media_plan=media_plan,
            max_rounds=args.llm_max_rounds,
            retry_wait_seconds=args.llm_retry_wait_seconds,
            no_expand=args.no_llm_expand,
            no_rewrite=args.no_llm_rewrite,
            no_normalize=args.no_normalize,
            skip_telegram=args.dry_run,
            skip_audio=args.skip_audio
            or (getattr(media_plan.tts, "backend", "") == "none"),
            telegram_chat_id=telegram_chat_id,
            telegram_mode="preview" if require_approval and not args.dry_run else "full",
            approval_attempt=attempt,
            min_duration_seconds=getattr(args, "min_audio_seconds", None),
            segment_target_seconds=getattr(args, "segment_seconds", None),
            force_modular=False if getattr(args, "no_modular", False) else None,
        )

        if args.dry_run or not require_approval:
            if upload_youtube and not args.dry_run and result.wav_path:
                try:
                    youtube_url = _publish_youtube(date_str, args.artifacts_dir, panel_cfg)
                except Exception:
                    logger.warning("Falha ao publicar no YouTube.", exc_info=True)
            return result, youtube_url, approval_note

        if not telegram_chat_id:
            raise RuntimeError("require_approval exige telegram_chat_id configurado.")

        logger.info(
            "Aguardando aprovação no Telegram (tentativa %s, timeout %s min)...",
            attempt,
            timeout_minutes,
        )
        decision = wait_for_decision(
            date_str=date_str,
            timeout_minutes=timeout_minutes,
            # Polling do Telegram é feito de forma centralizada pelo
            # eddie-telegram-bot, unico long-poll do token. Ele roteia os botões
            # dag:* via approval_gateway._on_callback -> daily_agenda_approval.
            # Aguardar apenas o arquivo de estado evita 409/conflico de pollers.
            poll_telegram=False,
        )
        if decision == "approved":
            approval_note = "Aprovado no Telegram."
            if upload_youtube and result.wav_path:
                try:
                    youtube_url = _publish_youtube(date_str, args.artifacts_dir, panel_cfg)
                    send_telegram_message(
                        f"✅ Agenda publicada no YouTube\n{youtube_url}",
                        chat_id=telegram_chat_id,
                    )
                except Exception:
                    logger.warning("Falha ao publicar no YouTube após aprovação.", exc_info=True)
            else:
                send_telegram_message(
                    "✅ Agenda aprovada. Publicação YouTube desabilitada.",
                    chat_id=telegram_chat_id,
                )
            return result, youtube_url, approval_note

        if decision == "regenerate" and attempt <= max_regenerations:
            attempt += 1
            deep_search = True
            args.timeout = min(90, max(args.timeout, 45) + 15)
            args.retries = max(args.retries, 5)
            approval_note = f"Regeneração {attempt - 1}/{max_regenerations} solicitada."
            logger.info(
                "Regenerando com busca profunda (tentativa %s, timeout=%ss, retries=%s)...",
                attempt,
                args.timeout,
                args.retries,
            )
            continue

        approval_note = f"Encerrado sem publicar ({decision})."
        if telegram_chat_id:
            send_telegram_message(
                f"⏹️ Agenda {date_str} não publicada ({decision}).",
                chat_id=telegram_chat_id,
            )
        return result, "", approval_note


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    date_str = resolve_date(args.date)
    artifacts_dir = Path(args.artifacts_dir) if args.artifacts_dir else DEFAULT_ARTIFACTS_DIR
    # Homelab panel (:8093). Workstation/outros hosts empurram log via HTTP.
    panel_url = os.environ.get("DAILY_AGENDA_PANEL_URL", "http://192.168.15.2:8093").strip()
    reporter = PanelJobReporter(
        artifacts_dir=artifacts_dir,
        source="broadcast",
        panel_url=panel_url,
        log_level=logging.INFO,
    )
    reporter.attach_logging(level=logging.INFO)
    reporter.start(
        date=date_str,
        phase="broadcast",
        command=" ".join(sys.argv),
        note=(
            f"Iniciando agenda diária date={date_str} quality={getattr(args, 'quality', '')} "
            f"(painel={panel_url or 'local-only'})"
        ),
        reset_log=True,
    )

    try:
        backend_override = None if args.backend == "auto" else args.backend
        if args.skip_audio or args.backend == "none":
            backend_override = "none"

        media_plan = resolve_media_plan(
            quality=args.quality,
            llm_auto_route=args.llm_auto_route,
            ollama_host=args.ollama_host,
            ollama_model=args.ollama_model,
            ollama_fallback_models=args.ollama_fallback_models,
            backend_override=backend_override,
            piper_voice_override=args.piper_voice,
            google_voice=args.google_voice,
        )

        panel_cfg = load_config()
        telegram_chat_id = args.telegram_chat_id
        if not telegram_chat_id:
            telegram_chat_id = (panel_cfg.get("telegram", {}).get("chat_id") or "").strip() or None
        if not telegram_chat_id:
            telegram_chat_id = get_agenda_telegram_chat_id() or None

        result, youtube_url, approval_note = _run_with_optional_approval(
            args=args,
            panel_cfg=panel_cfg,
            date_str=date_str,
            media_plan=media_plan,
            telegram_chat_id=telegram_chat_id,
        )

        print(result.source_text)
        print("\n--- Locucao ---\n")
        print(result.final_text)
        print(f"\nFonte salva em: {result.source_path}")
        print(f"Locucao salva em: {result.locution_text_path}")
        if result.wav_path:
            print(f"Audio salvo em: {result.wav_path}")
        if result.llm_endpoint:
            print(f"LLM utilizado: {result.llm_endpoint}")
        if result.tts_backend:
            print(f"TTS utilizado: {result.tts_backend}")
        if result.sources_used:
            print(f"Fontes utilizadas: {', '.join(result.sources_used)}")
        if result.sources_failed:
            print(f"Fontes sem resultado: {', '.join(result.sources_failed)}")
        if args.dry_run:
            print("\nDry-run: Telegram nao foi acionado.")
        elif approval_note:
            print(f"\n{approval_note}")
        else:
            print("\nAgenda diaria enviada no Telegram.")
        if youtube_url:
            print(f"YouTube: {youtube_url}")

        reporter.finish(
            status="done",
            returncode=0,
            note=f"Agenda {date_str} finalizada. {approval_note}".strip(),
            extra={"youtube": youtube_url or None},
        )
        return 0
    except Exception as exc:
        logger.exception("Falha no pipeline da agenda diária")
        reporter.finish(status="failed", returncode=1, error=str(exc), note=f"ERRO: {exc}")
        raise
    finally:
        reporter.detach_logging()


if __name__ == "__main__":
    raise SystemExit(main())