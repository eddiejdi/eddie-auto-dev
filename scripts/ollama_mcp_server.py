#!/usr/bin/env python3
"""
Ollama MCP Server — exposes local GPU cluster (3 GPUs) as Claude Code tools.

Saves Claude API tokens by routing eligible tasks to local LLMs:
  GPU0  RTX 3060 12GB  192.168.15.2:11544  (proxy → 11434)  trading-analyst / heavy
  GPU1  GTX 1050  2GB  192.168.15.2:11545  (proxy → 11435)  gemma3-fast:gpu1 / fast
  NAS   RTX 2060  8GB  192.168.15.4:11546  (proxy → 11436)  phi4-mini:latest / mid-tier

Tools exposed to Claude Code:
  ollama_ask           — general question/task, auto-selects GPU
  ollama_analyze_code  — code review / explain / suggest fixes
  ollama_summarize     — summarize text / diff / log
  ollama_suggest_commit — generate commit message from git diff
  ollama_health        — check which GPUs are reachable
"""

import json
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [ollama-mcp] %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
log = logging.getLogger("ollama-mcp")

# ---------------------------------------------------------------------------
# Endpoint config — env-overridable so tests can point elsewhere
# ---------------------------------------------------------------------------
ENDPOINTS = [
    {
        "name": "gpu0-rtx3060",
        "host": os.environ.get("LLM_GPU0_HOST", "http://192.168.15.2:11544"),
        "model": os.environ.get("LLM_GPU0_MODEL", "trading-analyst"),
        "vram_gb": 12,
        "speed": "slow",   # big model, slower per token
    },
    {
        "name": "gpu1-gtx1050",
        "host": os.environ.get("LLM_GPU1_HOST", "http://192.168.15.2:11545"),
        "model": os.environ.get("LLM_GPU1_MODEL", "gemma3-fast:gpu1"),
        "vram_gb": 2,
        "speed": "fast",
    },
    {
        "name": "nas-rtx2060",
        "host": os.environ.get("LLM_NAS_HOST", "http://192.168.15.4:11546"),
        "model": os.environ.get("LLM_NAS_MODEL", "phi4-mini:latest"),
        "vram_gb": 8,
        "speed": "medium",
    },
]

_health_cache: dict[str, tuple[bool, float]] = {}
HEALTH_TTL = 30.0  # seconds


def _is_healthy(endpoint: dict, timeout: float = 3.0) -> bool:
    host = endpoint["host"]
    now = time.monotonic()
    cached = _health_cache.get(host)
    if cached and (now - cached[1]) < HEALTH_TTL:
        return cached[0]
    try:
        req = urllib.request.Request(f"{host}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=timeout):
            pass
        _health_cache[host] = (True, now)
        return True
    except Exception:
        _health_cache[host] = (False, now)
        return False


def _pick_endpoint(prefer_speed: str = "any") -> dict | None:
    """Return best healthy endpoint for the requested speed tier."""
    # Speed order: fast → medium → slow
    order = {"fast": 0, "medium": 1, "slow": 2}
    candidates = [ep for ep in ENDPOINTS if _is_healthy(ep)]
    if not candidates:
        return None
    if prefer_speed == "fast":
        candidates.sort(key=lambda e: order.get(e["speed"], 9))
    elif prefer_speed == "slow":
        candidates.sort(key=lambda e: -order.get(e["speed"], 0))
    else:
        candidates.sort(key=lambda e: order.get(e["speed"], 9))
    return candidates[0]


def _ollama_generate(host: str, model: str, prompt: str, timeout: int = 120) -> str:
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 2048},
    }).encode()
    req = urllib.request.Request(
        f"{host}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
        return data.get("response", "").strip()


def _try_generate(prompt: str, prefer_speed: str = "any", timeout: int = 120) -> tuple[str, str]:
    """Returns (text, endpoint_name). Falls back through all healthy endpoints."""
    candidates = [ep for ep in ENDPOINTS if _is_healthy(ep)]
    order = {"fast": 0, "medium": 1, "slow": 2}
    if prefer_speed == "slow":
        candidates.sort(key=lambda e: -order.get(e["speed"], 0))
    else:
        candidates.sort(key=lambda e: order.get(e["speed"], 9))

    for ep in candidates:
        try:
            text = _ollama_generate(ep["host"], ep["model"], prompt, timeout=timeout)
            if text:
                return text, ep["name"]
        except Exception as exc:
            log.warning("endpoint %s failed: %s", ep["name"], exc)
    return "(sem resposta — todos os endpoints falharam)", "none"


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

def handle_ollama_ask(args: dict) -> dict:
    prompt = args.get("prompt", "")
    if not prompt:
        return _text("Erro: prompt vazio.")
    context = args.get("context", "")
    full_prompt = f"{context}\n\n{prompt}" if context else prompt
    prefer = "fast" if len(prompt.split()) < 100 else "any"
    text, ep = _try_generate(full_prompt, prefer_speed=prefer)
    return _text(f"[{ep}]\n{text}")


def handle_ollama_analyze_code(args: dict) -> dict:
    code = args.get("code", "")
    question = args.get("question", "Analise este código: identifique problemas, sugira melhorias.")
    lang = args.get("language", "")
    fence = f"```{lang}" if lang else "```"
    prompt = f"{question}\n\n{fence}\n{code}\n```"
    text, ep = _try_generate(prompt, prefer_speed="any", timeout=180)
    return _text(f"[{ep}]\n{text}")


def handle_ollama_summarize(args: dict) -> dict:
    content = args.get("content", "")
    instruction = args.get("instruction", "Resuma o conteúdo abaixo de forma concisa.")
    prompt = f"{instruction}\n\n{content}"
    text, ep = _try_generate(prompt, prefer_speed="fast")
    return _text(f"[{ep}]\n{text}")


def handle_ollama_suggest_commit(args: dict) -> dict:
    diff = args.get("diff", "")
    if not diff:
        # auto-capture from cwd
        cwd = args.get("cwd", "/workspace/eddie-auto-dev")
        try:
            diff = subprocess.check_output(
                ["git", "diff", "--cached", "--stat", "-p", "--no-color"],
                cwd=cwd, text=True, timeout=10,
            )
            if not diff.strip():
                diff = subprocess.check_output(
                    ["git", "diff", "--stat", "-p", "--no-color"],
                    cwd=cwd, text=True, timeout=10,
                )
        except Exception as exc:
            return _text(f"Erro ao capturar git diff: {exc}")

    prompt = (
        "Gere uma mensagem de commit git concisa e descritiva para as mudanças abaixo. "
        "Use o formato: tipo(escopo): descrição breve. "
        "Responda APENAS com a mensagem de commit, sem explicações.\n\n"
        f"```diff\n{diff[:6000]}\n```"
    )
    text, ep = _try_generate(prompt, prefer_speed="fast", timeout=60)
    return _text(f"[{ep}]\n{text}")


def handle_ollama_health(_args: dict) -> dict:
    lines = ["## Ollama GPU Cluster Health\n"]
    for ep in ENDPOINTS:
        ok = _is_healthy(ep, timeout=3.0)
        status = "✓ online" if ok else "✗ offline"
        lines.append(f"- **{ep['name']}** {ep['host']} ({ep['vram_gb']}GB)  model=`{ep['model']}`  {status}")
    healthy = sum(1 for ep in ENDPOINTS if _health_cache.get(ep["host"], (False,))[0])
    lines.append(f"\n{healthy}/{len(ENDPOINTS)} endpoints disponíveis.")
    return _text("\n".join(lines))


def _text(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}


# ---------------------------------------------------------------------------
# MCP protocol
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "ollama_ask",
        "description": (
            "Envie uma pergunta ou tarefa para o cluster Ollama local (GPU0/GPU1/NAS). "
            "Use para análises, perguntas sobre código, explicações ou qualquer tarefa "
            "que não exija acesso a ferramentas externas — economiza tokens Claude."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Pergunta ou instrução."},
                "context": {"type": "string", "description": "Contexto adicional (opcional)."},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "ollama_analyze_code",
        "description": (
            "Analisa ou explica um trecho de código usando LLM local. "
            "Ideal para code review, detecção de bugs, sugestões de refatoração — economiza tokens Claude."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Código fonte a analisar."},
                "question": {"type": "string", "description": "O que analisar/perguntar sobre o código."},
                "language": {"type": "string", "description": "Linguagem (python, js, yaml, etc.) para syntax highlight."},
            },
            "required": ["code"],
        },
    },
    {
        "name": "ollama_summarize",
        "description": (
            "Sumariza texto, diff, log ou qualquer conteúdo longo usando LLM local. "
            "Economiza tokens Claude ao condensar conteúdo antes de passar para Claude."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Conteúdo a sumarizar."},
                "instruction": {"type": "string", "description": "Instrução de sumarização (opcional)."},
            },
            "required": ["content"],
        },
    },
    {
        "name": "ollama_suggest_commit",
        "description": (
            "Gera mensagem de commit a partir do git diff atual ou de um diff fornecido. "
            "Usa LLM local — zero tokens Claude."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "diff": {"type": "string", "description": "Git diff (opcional — captura automaticamente se omitido)."},
                "cwd": {"type": "string", "description": "Diretório do repositório (default: /workspace/eddie-auto-dev)."},
            },
            "required": [],
        },
    },
    {
        "name": "ollama_health",
        "description": "Verifica quais GPUs do cluster Ollama estão disponíveis (RTX3060, GTX1050, RTX2060 NAS).",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
]

HANDLERS: dict[str, Any] = {
    "ollama_ask": handle_ollama_ask,
    "ollama_analyze_code": handle_ollama_analyze_code,
    "ollama_summarize": handle_ollama_summarize,
    "ollama_suggest_commit": handle_ollama_suggest_commit,
    "ollama_health": handle_ollama_health,
}


def mcp_response(id_: Any, result: Any) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": id_, "result": result})


def mcp_error(id_: Any, code: int, message: str) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}})


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as exc:
            print(mcp_error(None, -32700, f"parse error: {exc}"), flush=True)
            continue

        id_ = msg.get("id")
        method = msg.get("method", "")
        params = msg.get("params", {})

        if method == "initialize":
            print(mcp_response(id_, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "ollama-local", "version": "1.0.0"},
            }), flush=True)

        elif method == "notifications/initialized":
            pass

        elif method == "tools/list":
            print(mcp_response(id_, {"tools": TOOLS}), flush=True)

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            if tool_name not in HANDLERS:
                print(mcp_error(id_, -32601, f"unknown tool: {tool_name}"), flush=True)
                continue
            try:
                result = HANDLERS[tool_name](arguments)
                print(mcp_response(id_, result), flush=True)
            except Exception as exc:
                log.exception("tool %s failed", tool_name)
                print(mcp_error(id_, -32000, str(exc)), flush=True)

        elif method == "ping":
            print(mcp_response(id_, {}), flush=True)

        else:
            if id_ is not None:
                print(mcp_error(id_, -32601, f"method not found: {method}"), flush=True)


if __name__ == "__main__":
    main()
