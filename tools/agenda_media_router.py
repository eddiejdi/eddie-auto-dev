#!/usr/bin/env python3
"""Roteamento de LLM e TTS para a agenda diaria.

Politica de LLM (obrigatoria):
  Todo trafego de modelo passa pelo ollama-gpu-coordinator (:11437).
  O coordinator e quem gerencia VRAM, affinity, least-load e eviction
  entre GPU0 (:11434), GPU1 (:11435) e NAS (:11436).

  TRADING INTOCÁVEL; VRAM livre da 3060 ok para auxiliares pequenos:
    - Modelos trading-* nunca são evictados.
    - GPU0 pode receber só auxiliares pequenos (≤~1.8GB est.) que caibam
      na VRAM livre + headroom — sem despejar o analyst.
    - Agenda NÃO usa família trading-*; prefere GPU1/NAS e modelos leves
      (gemma/lfm/1b) que o coordinator pode pousar na 3060 se sobrar memória.

  Clientes da agenda NAO devem contatar as GPUs diretas no caminho
  automatico (--llm-auto-route). Override manual (--ollama-host) e
  permitido apenas para diagnostico.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from urllib.parse import urlparse


# Coordinator e a unica porta de gerenciamento de modelos em producao.
DEFAULT_COORD_HOST = os.getenv(
    "AGENDA_LLM_COORD_HOST",
    os.getenv("OLLAMA_HOST", "http://192.168.15.2:11437"),
).rstrip("/")
COORDINATOR_PORT = int(os.getenv("AGENDA_LLM_COORD_PORT", "11437"))

# Portas de backend Ollama — so o coordinator deve usá-las.
_DIRECT_OLLAMA_PORTS = frozenset({11434, 11435, 11436})

# Modelos leves para a agenda — FORA da família trading-*.
# Preferência GPU1 (soft-pin) + NAS; auxiliares ~1B (gemma3:1b, llama3.2:1b)
# podem usar VRAM livre da 3060 se o coordinator achar espaço (sem evictar trading).
# GPU1: só GGUF quantizados leves (Q4_0 / Q4_K_M / IQ3) — cabem na GTX 1050 2GB.
DEFAULT_COORD_MODEL = os.getenv("AGENDA_LLM_MODEL", "lfm2.5-fast:gpu1")
DEFAULT_COORD_FALLBACK_MODELS = tuple(
    item.strip()
    for item in os.getenv(
        "AGENDA_LLM_FALLBACK_MODELS",
        "gemma3-fast:gpu1,gemma3:1b,smollm2-iq3:gpu1,phi4-mini:nas",
    ).split(",")
    if item.strip() and not item.strip().lower().startswith("trading")
)
# Workers paralelos de LLM na geração modular (segmentos).
# 2026-07-30: default 2 — agenda NÃO deve saturar a 3060 (trading intocável).
# Coordinator: GPU1 + NAS apenas quando TRADING_EXCLUSIVE_GPU0=1.
DEFAULT_LLM_PARALLEL = max(1, int(os.getenv("AGENDA_LLM_PARALLEL", "2")))

# Legado / diagnostico — NAO usados no caminho auto-route da agenda.
DEFAULT_GPU0_HOST = os.getenv("AGENDA_LLM_GPU0_HOST", "http://192.168.15.2:11434")
DEFAULT_NAS_HOST = os.getenv("AGENDA_LLM_NAS_HOST", "http://192.168.15.4:11436")
DEFAULT_GPU1_HOST = os.getenv("AGENDA_LLM_GPU1_HOST", "http://192.168.15.2:11435")
DEFAULT_GPU0_MODEL = os.getenv("AGENDA_LLM_GPU0_MODEL", "gemma3:1b")
DEFAULT_NAS_MODEL = os.getenv("AGENDA_LLM_NAS_MODEL", "phi4-mini:latest")
DEFAULT_GPU1_MODEL = os.getenv("AGENDA_LLM_GPU1_MODEL", "lfm2.5-fast:gpu1")

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


def _host_port(host: str) -> int | None:
    raw = host.strip()
    if not raw:
        return None
    parsed = urlparse(raw if "://" in raw else f"http://{raw}")
    if parsed.port is not None:
        return int(parsed.port)
    return 443 if parsed.scheme == "https" else 80


def is_direct_ollama_host(host: str) -> bool:
    """True se o host aponta para GPU/NAS direta (:11434/:11435/:11436)."""
    port = _host_port(host)
    return port in _DIRECT_OLLAMA_PORTS


def is_coordinator_host(host: str) -> bool:
    port = _host_port(host)
    return port == COORDINATOR_PORT


def ensure_coordinator_host(host: str) -> str:
    """Remapeia GPUs diretas para o coordinator na mesma maquina.

    Politica: gerenciamento de modelos so via :11437. Se alguem passar
    OLLAMA_HOST=:11434 (ou NAS/GPU1), reescreve para o coordinator.
    """
    raw = (host or "").strip().rstrip("/")
    if not raw:
        return DEFAULT_COORD_HOST.rstrip("/")

    parsed = urlparse(raw if "://" in raw else f"http://{raw}")
    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == "https" else 80

    if port in _DIRECT_OLLAMA_PORTS or port == COORDINATOR_PORT:
        scheme = parsed.scheme or "http"
        hostname = parsed.hostname or "192.168.15.2"
        return f"{scheme}://{hostname}:{COORDINATOR_PORT}"

    return raw


def default_llm_chain() -> tuple[LlmEndpoint, ...]:
    """Cadeia padrao no coordinator com modelos multi-GPU.

    Um unico host (:11437); a cadeia de modelos cobre GPU0, GPU1 e NAS.
    O coordinator faz least-load + soft-pin para espalhar a carga.
    trading-analyst na GPU0 permanece protegido de eviction.
    """
    host = ensure_coordinator_host(DEFAULT_COORD_HOST)
    return (
        LlmEndpoint(
            name="coordinator",
            host=host,
            model=DEFAULT_COORD_MODEL,
            fallback_models=DEFAULT_COORD_FALLBACK_MODELS,
        ),
    )


def distributed_llm_chain() -> tuple[LlmEndpoint, ...]:
    """Varias entradas no coordinator com modelos primarios distintos.

    GPU1 (soft-pin) + NAS. NÃO usa gemma3:1b sem pin (antes vazava p/ GPU0 e
    causava timeout do trading-analyst na 3060).
    """
    host = ensure_coordinator_host(DEFAULT_COORD_HOST)
    # Primários só em GPU1/NAS — trading fica exclusivo na 3060.
    primaries = (
        ("coord-gpu1-a", DEFAULT_COORD_MODEL),  # lfm2.5-fast:gpu1
        ("coord-gpu1-b", "gemma3-fast:gpu1"),
        ("coord-nas", "phi4-mini:nas"),
    )
    shared_fallbacks = DEFAULT_COORD_FALLBACK_MODELS
    endpoints: list[LlmEndpoint] = []
    for name, model in primaries:
        fb = tuple(m for m in shared_fallbacks if m != model and not m.lower().startswith("trading"))
        others = tuple(
            m for _, m in primaries
            if m != model and m not in fb and not m.lower().startswith("trading")
        )
        endpoints.append(
            LlmEndpoint(
                name=name,
                host=host,
                model=model,
                fallback_models=others + fb,
            )
        )
    return tuple(endpoints)


def single_llm_endpoint(host: str, model: str, fallback_models: str = "") -> tuple[LlmEndpoint, ...]:
    models = tuple(
        item.strip()
        for item in fallback_models.split(",")
        if item.strip()
    )
    return (LlmEndpoint(name="manual", host=host.rstrip("/"), model=model, fallback_models=models),)


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
    allow_direct_ollama: bool = False,
) -> MediaPlan:
    """Resolve plano de midia.

    Com llm_auto_route=True (padrao de producao), a cadeia LLM aponta
    apenas para o coordinator. Hosts diretos de GPU sao remapeados.

    Com override manual (--ollama-host / --ollama-model), ainda assim
    remapeamos portas diretas para :11437, a menos que allow_direct_ollama=True
    (somente diagnostico).
    """
    if llm_auto_route and not ollama_host and not ollama_model:
        # Cadeia distribuída: 3 primários distintos no coordinator → 3 GPUs.
        distribute = os.getenv("AGENDA_LLM_DISTRIBUTE", "1").strip().lower() not in {
            "0", "false", "no", "off",
        }
        llm_endpoints = distributed_llm_chain() if distribute else default_llm_chain()
    else:
        host = ollama_host or DEFAULT_COORD_HOST
        if not allow_direct_ollama:
            host = ensure_coordinator_host(host)
        llm_endpoints = single_llm_endpoint(
            host=host,
            model=ollama_model or DEFAULT_COORD_MODEL,
            fallback_models=ollama_fallback_models
            or ",".join(DEFAULT_COORD_FALLBACK_MODELS),
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
