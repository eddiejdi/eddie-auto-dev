#!/usr/bin/env python3
"""Script de warmup para manter modelos Ollama carregados nas GPUs.

Envia requisições leves (keep_alive=-1) para garantir que os modelos
permaneçam na VRAM. Projetado para rodar via systemd timer a cada 5 min.

Uso:
    python3 scripts/ollama_warmup.py           # warmup padrão (modelo configurado em cada GPU)
    python3 scripts/ollama_warmup.py --verbose  # com logs detalhados
    python3 scripts/ollama_warmup.py --status   # apenas verificar estado
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional

# ── Configuração ─────────────────────────────────────────────────
def _csv_env(name: str, default: str) -> list[str]:
    """Lê lista CSV de env var removendo vazios."""
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


GPU0_HOST = os.getenv("OLLAMA_HOST_GPU0", os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434"))
GPU1_HOST = os.getenv("OLLAMA_HOST_GPU1", "http://192.168.15.2:11435")

# Modelos padrão para manter warm em cada GPU
GPU0_MODELS = _csv_env("OLLAMA_WARM_MODELS_GPU0", os.getenv("OLLAMA_WARM_MODEL_GPU0", "trading-analyst:latest"))
GPU1_MODELS = _csv_env("OLLAMA_WARM_MODELS_GPU1", os.getenv("OLLAMA_WARM_MODEL_GPU1", "qwen3:0.6b"))

WARMUP_PROMPT = "ping"
TIMEOUT_SECONDS = 120  # cold load pode levar >30s (phi4-mini ~2.5GB)
KEEP_ALIVE = -1  # permanente — nunca descarregar (inteiro para API Ollama)

logger = logging.getLogger("ollama-warmup")


# ── Data classes ─────────────────────────────────────────────────
@dataclass
class GpuStatus:
    """Status de uma instância Ollama."""

    host: str
    name: str
    online: bool = False
    version: str = ""
    loaded_models: list[str] = field(default_factory=list)
    error: str = ""


@dataclass
class WarmupResult:
    """Resultado de um warmup de modelo."""

    host: str
    model: str
    success: bool = False
    already_loaded: bool = False
    load_time_ms: float = 0.0
    error: str = ""


# ── Funções auxiliares ────────────────────────────────────────────
def _http_request(
    url: str,
    data: Optional[dict] = None,
    timeout: int = TIMEOUT_SECONDS,
) -> dict:
    """Faz requisição HTTP para a API Ollama."""
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data else None,
        headers={"Content-Type": "application/json"},
        method="POST" if data else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _model_aliases(model: str) -> set[str]:
    """Normaliza nome do modelo para matching com ou sem :latest."""
    model_norm = model.lower().strip()
    aliases = {model_norm}
    if model_norm.endswith(":latest"):
        aliases.add(model_norm.rsplit(":", 1)[0])
    else:
        aliases.add(f"{model_norm}:latest")
    return aliases


def _list_installed_models(host: str) -> set[str]:
    """Retorna nomes dos modelos instalados em uma instância Ollama."""
    tags_data = _http_request(f"{host}/api/tags", timeout=5)
    return {
        str(model_data["name"]).lower().strip()
        for model_data in tags_data.get("models", [])
        if model_data.get("name")
    }


def check_gpu_status(host: str, name: str) -> GpuStatus:
    """Verifica status de uma instância Ollama."""
    status = GpuStatus(host=host, name=name)
    try:
        version_data = _http_request(f"{host}/api/version", timeout=5)
        status.online = True
        status.version = version_data.get("version", "unknown")

        ps_data = _http_request(f"{host}/api/ps", timeout=5)
        status.loaded_models = [
            m["name"] for m in ps_data.get("models", [])
        ]
    except urllib.error.URLError as exc:
        status.error = f"Conexão recusada: {exc.reason}"
    except Exception as exc:
        status.error = str(exc)
    return status


def warmup_model(host: str, model: str) -> WarmupResult:
    """Envia requisição de warmup para carregar modelo na VRAM."""
    result = WarmupResult(host=host, model=model)
    model_aliases = _model_aliases(model)

    # Verificar se modelo já está carregado
    try:
        ps_data = _http_request(f"{host}/api/ps", timeout=5)
        loaded = {
            str(model_data["name"]).lower().strip()
            for model_data in ps_data.get("models", [])
            if model_data.get("name")
        }
        if loaded & model_aliases:
            result.success = True
            result.already_loaded = True
            logger.info(f"  ✓ {model} já carregado em {host}")
            return result
    except Exception:
        pass

    # Falha cedo quando o modelo não existe, evitando cold load inútil.
    try:
        installed = _list_installed_models(host)
        if installed and not (installed & model_aliases):
            result.error = f"modelo '{model}' não está instalado em {host}"
            logger.error(f"  ✗ {model} em {host}: {result.error}")
            return result
    except Exception as exc:
        logger.warning(f"  ⚠ Não foi possível validar {model} via /api/tags em {host}: {exc}")

    # Enviar requisição leve com keep_alive=-1
    start = time.monotonic()
    try:
        payload = {
            "model": model,
            "prompt": WARMUP_PROMPT,
            "stream": False,
            "keep_alive": KEEP_ALIVE,
            "options": {
                "num_predict": 1,
                "temperature": 0.0,
            },
        }
        _http_request(
            f"{host}/api/generate",
            data=payload,
            timeout=TIMEOUT_SECONDS,
        )
        elapsed_ms = (time.monotonic() - start) * 1000
        result.success = True
        result.load_time_ms = elapsed_ms
        logger.info(f"  ✓ {model} carregado em {host} ({elapsed_ms:.0f}ms)")
    except urllib.error.HTTPError as exc:
        result.error = f"HTTP {exc.code}: {exc.read().decode()[:200]}"
        logger.error(f"  ✗ {model} em {host}: {result.error}")
    except Exception as exc:
        result.error = str(exc)
        logger.error(f"  ✗ {model} em {host}: {result.error}")

    return result


def run_warmup(verbose: bool = False) -> tuple[list[WarmupResult], bool]:
    """Executa warmup em ambas as GPUs.

    Retorna:
        Tupla (lista de resultados, sucesso geral).
    """
    results: list[WarmupResult] = []
    all_ok = True

    gpu_configs = [
        (GPU0_HOST, "GPU0 (RTX 2060)", GPU0_MODELS),
        (GPU1_HOST, "GPU1 (GTX 1050)", GPU1_MODELS),
    ]

    for host, name, models in gpu_configs:
        logger.info(f"Verificando {name} ({host})...")
        status = check_gpu_status(host, name)

        if not status.online:
            logger.warning(f"  ⚠ {name} OFFLINE: {status.error}")
            for model in models:
                results.append(WarmupResult(
                    host=host, model=model, error=status.error,
                ))
            all_ok = False
            continue

        if verbose:
            logger.info(f"  Ollama v{status.version}")
            if status.loaded_models:
                logger.info(f"  Modelos carregados: {', '.join(status.loaded_models)}")
            else:
                logger.info("  Nenhum modelo carregado")

        for model in models:
            result = warmup_model(host, model)
            results.append(result)
            if not result.success:
                all_ok = False

    return results, all_ok


def show_status() -> None:
    """Exibe status de ambas as GPUs."""
    for host, name in [(GPU0_HOST, "GPU0 (RTX 2060)"), (GPU1_HOST, "GPU1 (GTX 1050)")]:
        status = check_gpu_status(host, name)
        if status.online:
            models_str = ", ".join(status.loaded_models) if status.loaded_models else "nenhum"
            logger.info(f"{name}: ONLINE v{status.version} | Modelos: {models_str}")
        else:
            logger.info(f"{name}: OFFLINE ({status.error})")


# ── Main ──────────────────────────────────────────────────────────
def main() -> int:
    """Ponto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Mantém modelos Ollama carregados nas GPUs (warmup)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Logs detalhados",
    )
    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="Apenas verificar estado das GPUs",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s [warmup] %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.status:
        show_status()
        return 0

    logger.info("Iniciando warmup das GPUs...")
    results, all_ok = run_warmup(verbose=args.verbose)

    # Resumo
    loaded = sum(1 for r in results if r.success and not r.already_loaded)
    cached = sum(1 for r in results if r.already_loaded)
    failed = sum(1 for r in results if not r.success)

    logger.info(
        f"Warmup completo: {loaded} carregado(s), "
        f"{cached} já em cache, {failed} falha(s)"
    )

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
