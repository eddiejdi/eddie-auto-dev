#!/usr/bin/env python3
"""Roteamento de LLM e TTS para a agenda diaria."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


DEFAULT_GPU0_HOST = os.getenv("AGENDA_LLM_GPU0_HOST", "http://192.168.15.2:11434")
DEFAULT_NAS_HOST = os.getenv("AGENDA_LLM_NAS_HOST", "http://192.168.15.4:11436")
DEFAULT_GPU1_HOST = os.getenv("AGENDA_LLM_GPU1_HOST", "http://192.168.15.2:11435")

DEFAULT_GPU0_MODEL = os.getenv("AGENDA_LLM_GPU0_MODEL", "mistral:7b")
DEFAULT_NAS_MODEL = os.getenv("AGENDA_LLM_NAS_MODEL", "mistral:7b")
DEFAULT_GPU1_MODEL = os.getenv("AGENDA_LLM_GPU1_MODEL", "gemma3:1b")

PIPER_VOICES = {
    "fast": "pt_BR-cadu-medium",
    "balanced": "pt_BR-faber-medium",
    "best": "pt_BR-faber-medium",
}
KOKORO_DEFAULT_VOICE = os.getenv("KOKORO_VOICE", "pm_santa")
KOKORO_VENV_PYTHON = os.getenv(
    "KOKORO_VENV_PYTHON",
    ".venv-tts-kokoro/bin/python",
)
PIPER_VENV_PYTHON = os.getenv(
    "PIPER_VENV_PYTHON",
    ".venv-tts-piper/bin/python",
)


@dataclass(frozen=True)
class LlmEndpoint:
    name: str
    host: str
    model: str
    fallback_models: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TtsSettings:
    backend: str
    piper_voice: str
    piper_use_cuda: bool
    piper_cuda_device: str
    google_voice: str
    kokoro_voice: str
    kokoro_device: str


@dataclass(frozen=True)
class MediaPlan:
    quality: str
    llm_endpoints: tuple[LlmEndpoint, ...]
    tts: TtsSettings


def default_llm_chain() -> tuple[LlmEndpoint, ...]:
    return (
        LlmEndpoint(
            name="gpu0",
            host=DEFAULT_GPU0_HOST,
            model=DEFAULT_GPU0_MODEL,
            fallback_models=("phi4-mini:latest", "llama3.2:3b"),
        ),
        LlmEndpoint(
            name="nas",
            host=DEFAULT_NAS_HOST,
            model=DEFAULT_NAS_MODEL,
            fallback_models=(),
        ),
        LlmEndpoint(
            name="gpu1",
            host=DEFAULT_GPU1_HOST,
            model=DEFAULT_GPU1_MODEL,
            fallback_models=("llama3.2:1b",),
        ),
    )


def single_llm_endpoint(host: str, model: str, fallback_models: str = "") -> tuple[LlmEndpoint, ...]:
    models = tuple(
        item.strip()
        for item in fallback_models.split(",")
        if item.strip()
    )
    return (LlmEndpoint(name="manual", host=host, model=model, fallback_models=models),)


def resolve_tts_settings(
    *,
    quality: str,
    backend_override: str | None = None,
    piper_voice_override: str | None = None,
    google_voice: str = "Kore",
) -> TtsSettings:
    normalized = quality.strip().lower()
    if normalized not in {"fast", "balanced", "best"}:
        raise ValueError(f"Qualidade TTS invalida: {quality}")

    piper_voice = piper_voice_override or PIPER_VOICES[normalized]

    if backend_override and backend_override not in {"none", "auto"}:
        backend = backend_override
        piper_use_cuda = backend == "piper-gpu"
        return TtsSettings(
            backend=backend,
            piper_voice=piper_voice,
            piper_use_cuda=piper_use_cuda,
            piper_cuda_device="0",
            google_voice=google_voice,
            kokoro_voice=KOKORO_DEFAULT_VOICE,
            kokoro_device="cuda:0",
        )

    if normalized == "fast":
        backend = "piper-cpu"
        piper_use_cuda = False
    elif normalized == "balanced":
        backend = "piper-gpu"
        piper_use_cuda = True
    else:
        backend = "kokoro-gpu0"
        piper_use_cuda = True

    return TtsSettings(
        backend=backend,
        piper_voice=piper_voice,
        piper_use_cuda=piper_use_cuda,
        piper_cuda_device="0",
        google_voice=google_voice,
        kokoro_voice=KOKORO_DEFAULT_VOICE,
        kokoro_device="cuda:0",
    )


def resolve_media_plan(
    *,
    quality: str = "balanced",
    llm_auto_route: bool = True,
    ollama_host: str | None = None,
    ollama_model: str | None = None,
    ollama_fallback_models: str = "",
    backend_override: str | None = None,
    piper_voice_override: str | None = None,
    google_voice: str = "Kore",
) -> MediaPlan:
    if llm_auto_route and not ollama_host and not ollama_model:
        llm_endpoints = default_llm_chain()
    else:
        llm_endpoints = single_llm_endpoint(
            host=ollama_host or DEFAULT_GPU1_HOST,
            model=ollama_model or DEFAULT_GPU1_MODEL,
            fallback_models=ollama_fallback_models,
        )

    tts = resolve_tts_settings(
        quality=quality,
        backend_override=backend_override,
        piper_voice_override=piper_voice_override,
        google_voice=google_voice,
    )
    return MediaPlan(
        quality=quality,
        llm_endpoints=llm_endpoints,
        tts=tts,
    )


def tts_fallback_chain(settings: TtsSettings) -> tuple[str, ...]:
    if settings.backend == "kokoro-gpu0":
        return ("kokoro-gpu0", "gemini-tts", "piper-gpu", "piper-cpu")
    if settings.backend == "piper-gpu":
        return ("piper-gpu", "piper-cpu")
    if settings.backend == "gemini-tts":
        return ("gemini-tts", "piper-gpu", "piper-cpu")
    return ("piper-cpu",)