"""PreToolUse hook — injeta o conteúdo atual do MEMORY.md como additionalContext.

Ao rodar antes de QUALQUER ferramenta (matcher .*), garante que todo tool call
receba o estado mais recente da memória do projeto, incluindo:
- Regras de feedback aprendidas (deploy, tape, guardrails, etc.)
- Referências de infraestrutura (serviços, hosts, portas)
- Estado de projetos em andamento

O conteúdo é lido em tempo real do arquivo MEMORY.md, então reflete
mudanças feitas durante a sessão sem precisar reiniciar.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

MEMORY_PATHS = [
    Path.home() / ".claude" / "projects" / "-workspace-eddie-auto-dev" / "memory" / "MEMORY.md",
    Path("/workspace/eddie-auto-dev/.claude/memory/MEMORY.md"),
]

MAX_CHARS = 6000


def _load_input() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    return json.loads(raw) if raw else {}


def _read_memory() -> str:
    for path in MEMORY_PATHS:
        if path.exists():
            try:
                content = path.read_text(encoding="utf-8")
                if len(content) > MAX_CHARS:
                    content = content[:MAX_CHARS] + "\n... (truncado)"
                return content
            except Exception:
                pass
    return ""


def main() -> int:
    _load_input()  # consome stdin (obrigatório mesmo que não use o payload)

    memory = _read_memory()
    if not memory:
        print(json.dumps({"continue": True}))
        return 0

    print(json.dumps({
        "continue": True,
        "additionalContext": f"# Memória do projeto (MEMORY.md)\n\n{memory}",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
