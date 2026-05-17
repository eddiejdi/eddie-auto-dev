#!/usr/bin/env python3
"""Selfheal do Coordenador de GPUs Ollama.

Detecta e corrige automaticamente o problema de modelo pinado (keep_alive=-1)
no GPU0, que causa loop de 503 no coordinator :11437, degradando o trading agent
para modo shadow (sem DCA automático).

Diagnóstico:
    - qwen3:0.6b com expires=2318 (pinado permanentemente) no GPU0
    - GPU0 fica ocupado processando, fallback para GPU1 falha (modelo muito grande)
    - Coordinator retorna 503 para todos os agentes → ollama=shadow → sem DCA

Ação:
    1. Detecta se coordinator :11437 está retornando 503 para uma probe request
    2. Identifica modelos pinados (keep_alive=-1) no GPU0
    3. Descarrega via keep_alive=0 diretamente no GPU0
    4. Pré-carrega qwen3:0.6b no GPU1 onde é o seu lugar correto
    5. Envia notificação Telegram com diagnóstico e ação tomada

Usage:
    python3 ollama_gpu_selfheal.py [--dry-run] [--force]
    systemctl start ollama-gpu-selfheal.service
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ollama-selfheal")

# ── Configuração via variáveis de ambiente ──────────────────────────────────
COORDINATOR_URL = os.environ.get("OLLAMA_COORD_URL", "http://127.0.0.1:11437")
GPU0_URL        = os.environ.get("OLLAMA_GPU0_URL",  "http://127.0.0.1:11434")
GPU1_URL        = os.environ.get("OLLAMA_GPU1_URL",  "http://127.0.0.1:11435")
TELEGRAM_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT   = os.environ.get("TELEGRAM_CHAT_ID", "")

# Modelo que deve ficar no GPU1 (leve, <2GB) — não no GPU0
LIGHT_MODELS = {"qwen3:0.6b", "qwen3-fast:gpu1", "qwen2.5:1.5b-instruct-q2_k"}
# Modelo padrão a pré-carregar no GPU1 após limpeza
GPU1_WARMUP_MODEL = os.environ.get("GPU1_WARMUP_MODEL", "qwen3:0.6b")

PROBE_TIMEOUT = 15  # segundos para a probe request ao coordinator
UNLOAD_TIMEOUT = 30
WARMUP_TIMEOUT = 60


# ── Helpers de HTTP ─────────────────────────────────────────────────────────

def _http_post(url: str, payload: dict, timeout: int = 15) -> tuple[int, dict]:
    """POST JSON e retorna (status_code, response_dict)."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, {"raw": body.decode(errors="replace")}
    except urllib.error.HTTPError as exc:
        return exc.code, {"error": str(exc)}
    except Exception as exc:
        return 0, {"error": str(exc)}


def _http_get(url: str, timeout: int = 5) -> tuple[int, dict]:
    """GET JSON e retorna (status_code, response_dict)."""
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, {}
    except urllib.error.HTTPError as exc:
        return exc.code, {}
    except Exception as exc:
        return 0, {}


# ── Lógica de diagnóstico ───────────────────────────────────────────────────

def probe_coordinator() -> bool:
    """Retorna True se o coordinator responde com sucesso."""
    # Usa /api/version como healthcheck leve (sem gerar tokens)
    status, _ = _http_get(f"{COORDINATOR_URL}/api/version", timeout=5)
    return status == 200


def get_loaded_models(gpu_url: str) -> list[dict]:
    """Retorna lista de modelos carregados na GPU."""
    status, data = _http_get(f"{gpu_url}/api/ps", timeout=5)
    if status != 200:
        return []
    return data.get("models", [])


def is_pinned(model: dict) -> bool:
    """Retorna True se o modelo está pinado (expires muito no futuro, ~2318)."""
    expires_at = model.get("expires_at", "")
    if not expires_at:
        return False
    try:
        dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        return dt.year > 2100
    except (ValueError, AttributeError):
        return False


def diagnose(gpu_url: str, gpu_name: str) -> list[dict]:
    """Retorna lista de modelos problemáticos (pinados onde não deveriam estar)."""
    problems = []
    for model in get_loaded_models(gpu_url):
        name = model.get("name", "")
        pinned = is_pinned(model)
        # Modelo leve pinado no GPU0: errado — deve estar no GPU1
        if gpu_name == "GPU0" and name in LIGHT_MODELS and pinned:
            problems.append({
                "gpu": gpu_name,
                "gpu_url": gpu_url,
                "model": name,
                "vram_gb": model.get("size_vram", 0) / 1024**3,
                "expires_at": model.get("expires_at", ""),
                "reason": f"modelo leve '{name}' pinado (keep_alive=-1) no GPU0 — bloqueia VRAM",
            })
    return problems


# ── Ações de correção ───────────────────────────────────────────────────────

def unload_model(gpu_url: str, model_name: str, dry_run: bool = False) -> bool:
    """Descarrega modelo via keep_alive=0."""
    logger.info(f"{'[DRY-RUN] ' if dry_run else ''}Descarregando {model_name} de {gpu_url}...")
    if dry_run:
        return True
    status, resp = _http_post(
        f"{gpu_url}/api/generate",
        {"model": model_name, "prompt": "", "keep_alive": 0},
        timeout=UNLOAD_TIMEOUT,
    )
    if status == 200:
        logger.info(f"✅ {model_name} descarregado de {gpu_url}")
        return True
    logger.warning(f"⚠️ Falha ao descarregar {model_name}: HTTP {status} — {resp}")
    return False


def warmup_gpu1(model_name: str, dry_run: bool = False) -> bool:
    """Pré-carrega modelo no GPU1 (keep_alive=600s = 10 min)."""
    logger.info(f"{'[DRY-RUN] ' if dry_run else ''}Pré-carregando {model_name} no GPU1...")
    if dry_run:
        return True
    status, resp = _http_post(
        f"{GPU1_URL}/api/generate",
        {"model": model_name, "prompt": "", "keep_alive": 600},
        timeout=WARMUP_TIMEOUT,
    )
    if status == 200:
        logger.info(f"✅ {model_name} pré-carregado no GPU1")
        return True
    logger.warning(f"⚠️ Falha ao pré-carregar {model_name} no GPU1: HTTP {status} — {resp}")
    return False


# ── Notificação Telegram ────────────────────────────────────────────────────

def send_telegram(message: str) -> None:
    """Envia mensagem via Telegram Bot API."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        logger.warning("TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não configurados — notificação ignorada")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    status, resp = _http_post(url, {
        "chat_id": TELEGRAM_CHAT,
        "text": message,
        "parse_mode": "HTML",
    }, timeout=10)
    if status == 200:
        logger.info("📨 Notificação Telegram enviada")
    else:
        logger.warning(f"⚠️ Falha no Telegram: HTTP {status} — {resp}")


def format_telegram_message(problems: list[dict], actions: list[str], errors: list[str], dry_run: bool) -> str:
    """Formata a mensagem de notificação Telegram."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    prefix = "🔵 <b>[DRY-RUN]</b> " if dry_run else "🔧 "

    lines = [f"{prefix}<b>Ollama GPU Selfheal</b>  <code>{now}</code>", ""]

    if problems:
        lines.append("🔴 <b>Problemas detectados:</b>")
        for p in problems:
            lines.append(f"  • <code>{p['model']}</code> — {p['reason']}")
            lines.append(f"    GPU: {p['gpu']} | VRAM: {p['vram_gb']:.2f}GB | expires: <code>{p['expires_at'][:10]}</code>")
        lines.append("")

    if actions:
        lines.append("✅ <b>Ações executadas:</b>")
        for a in actions:
            lines.append(f"  • {a}")
        lines.append("")

    if errors:
        lines.append("⚠️ <b>Erros:</b>")
        for e in errors:
            lines.append(f"  • {e}")
        lines.append("")

    if not problems and not errors:
        lines.append("✅ Tudo normal — nenhuma correção necessária")

    lines.append("🤖 <i>Sistema: ollama-gpu-selfheal</i>")
    return "\n".join(lines)


# ── Ponto de entrada ─────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Selfheal do coordenador de GPUs Ollama")
    parser.add_argument("--dry-run", action="store_true", help="Apenas diagnostica, não executa correções")
    parser.add_argument("--force", action="store_true", help="Executa correção mesmo que coordinator pareça OK")
    args = parser.parse_args()

    logger.info(f"=== Ollama GPU Selfheal iniciado {'[DRY-RUN]' if args.dry_run else ''} ===")

    # 1. Verifica se o coordinator está com problema
    coord_ok = probe_coordinator()
    if coord_ok and not args.force:
        logger.info("✅ Coordinator respondendo normalmente — nenhuma ação necessária")
        return 0

    if not coord_ok:
        logger.warning(f"⚠️ Coordinator {COORDINATOR_URL} não responde ou com erro")
    elif args.force:
        logger.info("🔍 --force: executando diagnóstico mesmo com coordinator OK")

    # 2. Diagnostica GPU0
    problems = diagnose(GPU0_URL, "GPU0")

    if not problems and not coord_ok:
        # Coordinator down mas sem modelo pinado — pode ser restart do serviço
        logger.warning("Coordinator down mas sem modelo pinado no GPU0 — verificar manualmente")
        send_telegram(format_telegram_message(
            problems=[],
            actions=[],
            errors=[f"Coordinator {COORDINATOR_URL} inacessível — sem causa identificada automaticamente"],
            dry_run=args.dry_run,
        ))
        return 1

    if not problems:
        logger.info("✅ Nenhum modelo problemático encontrado — nada a fazer")
        return 0

    # 3. Executa correções
    actions: list[str] = []
    errors: list[str] = []

    for p in problems:
        logger.info(f"🔧 Corrigindo: {p['reason']}")
        ok = unload_model(p["gpu_url"], p["model"], dry_run=args.dry_run)
        if ok:
            actions.append(f"Descarregado <code>{p['model']}</code> do {p['gpu']} (era pinado até {p['expires_at'][:10]})")
        else:
            errors.append(f"Falha ao descarregar {p['model']} do {p['gpu']}")

    # 4. Pré-carrega no GPU1 (onde deveria estar)
    if actions and GPU1_WARMUP_MODEL:
        gpu1_models = {m.get("name", "") for m in get_loaded_models(GPU1_URL)}
        if GPU1_WARMUP_MODEL not in gpu1_models:
            ok = warmup_gpu1(GPU1_WARMUP_MODEL, dry_run=args.dry_run)
            if ok:
                actions.append(f"Pré-carregado <code>{GPU1_WARMUP_MODEL}</code> no GPU1 (onde pertence)")
            else:
                errors.append(f"Falha ao pré-carregar {GPU1_WARMUP_MODEL} no GPU1")
        else:
            logger.info(f"{GPU1_WARMUP_MODEL} já carregado no GPU1 — sem ação necessária")

    # 5. Notifica via Telegram
    if problems or errors:
        msg = format_telegram_message(problems, actions, errors, args.dry_run)
        send_telegram(msg)

    if errors:
        return 1

    logger.info("=== Selfheal concluído com sucesso ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
