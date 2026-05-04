#!/usr/bin/env python3
"""
Ollama offloader — delega tarefas simples ao Ollama local para economizar tokens Claude/Copilot.

Uso:
    python tools/ollama_offloader.py --task explain --prompt "def foo(): ..."
    python tools/ollama_offloader.py --task summarize --file path/to/file.py
    echo "código" | python tools/ollama_offloader.py --task document
    python tools/ollama_offloader.py --task commit --prompt "diff aqui"
    python tools/ollama_offloader.py --classify --prompt "refaça a função X"

Tasks suportadas:
    explain    — Explicar código/conceito             → GPU1 (rápido)
    summarize  — Resumir arquivo/função               → GPU1
    commit     — Gerar mensagem de commit             → GPU1
    translate  — Traduzir comentários para PT-BR      → GPU1
    document   — Gerar docstring Google-style         → GPU0 (coder)
    review     — Code review básico                   → GPU0
    rename     — Sugerir nomes melhores               → GPU0
    format     — Melhorar legibilidade/organização    → GPU0

Classificação de complexidade:
    python tools/ollama_offloader.py --classify --prompt "implementar cache distribuído"
    → {"complexity": "COMPLEX", "offload": false, "reason": "..."}
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    print("ERRO: httpx não instalado. Execute: pip install httpx", file=sys.stderr)
    sys.exit(1)

OLLAMA_GPU0 = os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434")
OLLAMA_GPU1 = os.getenv("OLLAMA_HOST_GPU1", "http://192.168.15.2:11435")
# GPU0: modelo coder principal (qwen3:1.7b disponível como fallback de qwen2.5-coder:7b)
MODEL_GPU0 = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")
# GPU1: qwen3:1.7b funciona bem para trivials; fallback para qwen3-fast:gpu1 se necessário
MODEL_GPU1 = os.getenv("OLLAMA_SMALL_MODEL", "qwen3:1.7b")

# GPU1 (pequeno/rápido) — tarefas de leitura/resumo
_GPU1_TASKS = {"explain", "summarize", "commit", "translate"}
# GPU0 (coder) — tarefas de geração de código
_GPU0_TASKS = {"document", "review", "rename", "format"}

_SYSTEM_PROMPTS: dict[str, str] = {
    "explain": (
        "Você é um assistente de código. Explique de forma concisa o que o código faz. "
        "Sem repetir o código. Responda em português."
    ),
    "summarize": (
        "Você é um assistente técnico. Resuma o conteúdo em bullets curtos focando nos pontos-chave. "
        "Responda em português."
    ),
    "document": (
        "Você é um assistente Python. Gere docstring no estilo Google para a função/classe fornecida. "
        "Retorne apenas a docstring entre aspas triplas, sem o código."
    ),
    "review": (
        "Você é um code reviewer experiente. Liste problemas, melhorias e boas práticas para o código. "
        "Seja direto. Responda em português."
    ),
    "rename": (
        "Você é especialista em nomenclatura. Sugira nomes melhores para variáveis e funções no código. "
        "Responda em lista: 'antigo → sugerido — motivo'."
    ),
    "commit": (
        "Você é especialista em git. Gere mensagem de commit convencional (feat/fix/refactor/docs/chore) "
        "para o diff/mudança fornecido. Retorne apenas a mensagem, sem explicação."
    ),
    "translate": (
        "Você é tradutor técnico. Traduza comentários e docstrings para PT-BR, mantendo o código intacto. "
        "Retorne o código com os comentários traduzidos."
    ),
    "format": (
        "Você é especialista em estilo Python. Sugira melhorias de formatação e organização para o código. "
        "Responda em português."
    ),
}

# Palavras-chave que indicam tarefa COMPLEXA (manter em Claude/Copilot)
_COMPLEX_KEYWORDS = (
    "architect", "arquitetura", "design system", "design de sistema",
    "implement", "implementar", "criar", "create", "build", "construir",
    "refactor", "refatorar", "migrate", "migrar",
    "security", "segurança", "audit", "auditoria",
    "multi-file", "multi arquivo", "varios arquivos",
    "database schema", "schema do banco",
    "deploy", "ci/cd", "pipeline",
    "debug", "depurar", "traceback", "stacktrace",
    "fix bug", "corrigir bug", "resolver erro",
    "integrate", "integrar", "api design",
    "test suite", "suite de testes", "cobertura",
)

# Palavras-chave que indicam tarefa TRIVIAL (seguro offloading)
_TRIVIAL_KEYWORDS = (
    "explain", "explique", "o que faz", "what does",
    "summarize", "resuma", "resume",
    "document", "docstring", "documente",
    "translate", "traduza", "traduzir",
    "commit message", "mensagem de commit",
    "rename", "renomear", "nome melhor",
    "format", "formate", "organize",
    "review this", "revise este",
    "o que significa", "what is", "what means",
)


def _is_endpoint_up(url: str, timeout: float = 2.0) -> bool:
    try:
        with httpx.Client(timeout=timeout) as c:
            c.get(f"{url}/api/tags")
        return True
    except Exception:
        return False


def _select_backend(task: str) -> tuple[str, str]:
    """Seleciona host e modelo ideais para a task, com fallback GPU1→GPU0."""
    if task in _GPU1_TASKS:
        if _is_endpoint_up(OLLAMA_GPU1):
            return OLLAMA_GPU1, MODEL_GPU1
        # GPU1 offline, cai para GPU0
    return OLLAMA_GPU0, MODEL_GPU0


def _call_ollama(content: str, task: str, timeout: int = 120) -> str:
    host, model = _select_backend(task)
    system = _SYSTEM_PROMPTS.get(task, "Você é um assistente técnico útil.")
    # /no_think desabilita chain-of-thought do qwen3 → respostas ~3x mais rápidas
    user_content = f"/no_think\n{content}"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        "stream": False,
        "options": {"temperature": 0.3},
    }
    with httpx.Client(base_url=host, timeout=timeout) as client:
        resp = client.post("/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
    text = data.get("message", {}).get("content", "").strip()
    # Remove blocos <think>...</think> residuais (safety)
    import re
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return text


def classify_complexity(prompt: str) -> dict:
    """
    Classifica a complexidade de uma tarefa para decidir se deve ser offloadada.

    Returns:
        {
          "complexity": "TRIVIAL" | "MODERATE" | "COMPLEX",
          "offload": True/False,
          "suggested_task": "explain" | "review" | None,
          "reason": "..."
        }
    """
    lower = prompt.lower()

    for kw in _COMPLEX_KEYWORDS:
        if kw in lower:
            return {
                "complexity": "COMPLEX",
                "offload": False,
                "suggested_task": None,
                "reason": f"keyword '{kw}' indica tarefa complexa — use Claude/Copilot",
            }

    for kw in _TRIVIAL_KEYWORDS:
        if kw in lower:
            # Detectar task específica
            task = "explain"
            if any(x in lower for x in ("summarize", "resuma", "resume")):
                task = "summarize"
            elif any(x in lower for x in ("document", "docstring", "documente")):
                task = "document"
            elif any(x in lower for x in ("translate", "traduza")):
                task = "translate"
            elif any(x in lower for x in ("commit", "mensagem de commit")):
                task = "commit"
            elif any(x in lower for x in ("rename", "renomear", "nome")):
                task = "rename"
            elif any(x in lower for x in ("review", "revise")):
                task = "review"
            elif any(x in lower for x in ("format", "formate")):
                task = "format"
            return {
                "complexity": "TRIVIAL",
                "offload": True,
                "suggested_task": task,
                "reason": f"keyword '{kw}' indica tarefa simples — offload para Ollama",
            }

    # Prompt curto (< 200 chars) tende a ser trivial
    if len(prompt) < 200:
        return {
            "complexity": "MODERATE",
            "offload": True,
            "suggested_task": "explain",
            "reason": "prompt curto/moderado — offload para Ollama (GPU0)",
        }

    return {
        "complexity": "MODERATE",
        "offload": False,
        "suggested_task": None,
        "reason": "complexidade indeterminada — use Claude/Copilot para segurança",
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Delegar tarefas simples ao Ollama local para economizar tokens"
    )
    parser.add_argument(
        "--task",
        choices=list(_SYSTEM_PROMPTS.keys()),
        default="explain",
        help="Tipo de tarefa a delegar",
    )
    parser.add_argument("--prompt", "-p", help="Texto/código para processar")
    parser.add_argument("--file", "-f", help="Arquivo a processar (alternativa a --prompt)")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout em segundos")
    parser.add_argument(
        "--classify",
        action="store_true",
        help="Apenas classificar complexidade sem chamar o modelo (saída JSON)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar roteamento sem chamar o modelo",
    )
    args = parser.parse_args()

    # Resolver conteúdo
    if args.file:
        content = Path(args.file).read_text(encoding="utf-8")
    elif args.prompt:
        content = args.prompt
    elif not sys.stdin.isatty():
        content = sys.stdin.read().strip()
    else:
        parser.error("Forneça --prompt, --file ou pipe via stdin")
        return

    if args.classify:
        result = classify_complexity(content)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.dry_run:
        host, model = _select_backend(args.task)
        print(f"[dry-run] task={args.task} → host={host} model={model} content_len={len(content)}")
        return

    try:
        result = _call_ollama(content, args.task, timeout=args.timeout)
        print(result)
    except Exception as exc:
        print(f"ERRO ao chamar Ollama: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
