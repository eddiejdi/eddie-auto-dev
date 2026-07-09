#!/usr/bin/env python3
"""Orquestrador da agenda diaria: coleta -> LLM -> TTS -> Telegram."""
from __future__ import annotations

import argparse
import importlib.util
import logging
import sys
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
from daily_agenda_config import load_config
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
            lines.append(f"• {entry.time_label} — {label}")
    else:
        lines.append("_Sem compromissos formais confirmados nas fontes oficiais._")

    if collected.news:
        lines.append(f"\n*Imprensa:* {len(collected.news)} menção(ões) recente(s)")
        for item in collected.news[:2]:
            lines.append(f"• {item.title} ({item.outlet})")

    if collected.sources_used:
        lines.append(f"\n_Fontes: {', '.join(collected.sources_used)}_")

    if llm_endpoint or tts_backend:
        lines.append(
            f"\n_Midia: qualidade `{quality}` | LLM `{llm_endpoint or 'n/a'}` | TTS `{tts_backend or 'n/a'}`_"
        )

    body_preview = final_text.strip()
    if len(body_preview) > 900:
        body_preview = body_preview[:897] + "..."
    lines.append(f"\n{body_preview}")
    return header + "\n".join(lines)


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


def run_broadcast(
    *,
    date_str: str,
    mode: str,
    artifacts_dir: Path,
    timeout: int,
    retries: int,
    trust_env: bool,
    include_news: bool,
    media_plan,
    max_rounds: int,
    retry_wait_seconds: int,
    no_expand: bool,
    no_rewrite: bool,
    no_normalize: bool,
    skip_telegram: bool,
    skip_audio: bool,
    telegram_chat_id: str | None,
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
    )
    source_text = agenda_mod.build_source_text(
        collected,
        date_label=agenda_mod.format_date_label(date_str),
    )

    paths = artifact_paths(date_str, artifacts_dir)
    paths["day_dir"].mkdir(parents=True, exist_ok=True)
    agenda_mod.write_text(paths["source"], source_text)

    final_text, llm_endpoint = prepare_locution_text(
        source_text,
        tts_mod=tts_mod,
        llm_endpoints=media_plan.llm_endpoints,
        max_rounds=max_rounds,
        retry_wait_seconds=retry_wait_seconds,
        no_expand=no_expand,
        no_rewrite=no_rewrite,
        no_normalize=no_normalize,
    )
    tts_mod.save_text(paths["locution_text"], final_text)

    wav_path: Path | None = None
    tts_backend = ""
    if not skip_audio:
        try:
            tts_backend = synthesize_audio(
                final_text,
                tts_mod=tts_mod,
                wav_output=paths["wav"],
                tts_settings=media_plan.tts,
            ) or ""
            wav_path = paths["wav"]
        except Exception:
            logger.warning("Falha ao sintetizar audio; seguindo apenas com texto.", exc_info=True)

    if not skip_telegram:
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
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--retries", type=int, default=1)
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
    parser.add_argument("--telegram-chat-id", default=None)
    parser.add_argument(
        "--upload-youtube",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Publica no canal YouTube após gerar o áudio.",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    date_str = resolve_date(args.date)
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

    result = run_broadcast(
        date_str=date_str,
        mode=args.mode,
        artifacts_dir=args.artifacts_dir,
        timeout=args.timeout,
        retries=args.retries,
        trust_env=args.trust_env,
        include_news=not args.no_news,
        media_plan=media_plan,
        max_rounds=args.llm_max_rounds,
        retry_wait_seconds=args.llm_retry_wait_seconds,
        no_expand=args.no_llm_expand,
        no_rewrite=args.no_llm_rewrite,
        no_normalize=args.no_normalize,
        skip_telegram=args.dry_run,
        skip_audio=args.skip_audio or backend_override == "none",
        telegram_chat_id=telegram_chat_id,
    )

    upload_youtube = (
        args.upload_youtube
        if args.upload_youtube is not None
        else panel_cfg["defaults"].get("upload_youtube", False)
    )
    youtube_url = ""
    if upload_youtube and not args.dry_run and result.wav_path:
        try:
            from youtube_agenda_publisher import publish_edition

            yt_result = publish_edition(date_str, artifacts_dir=args.artifacts_dir, config=panel_cfg)
            youtube_url = yt_result.video_url
        except Exception:
            logger.warning("Falha ao publicar no YouTube.", exc_info=True)

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
    else:
        print("\nAgenda diaria enviada no Telegram.")
    if youtube_url:
        print(f"YouTube: {youtube_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())