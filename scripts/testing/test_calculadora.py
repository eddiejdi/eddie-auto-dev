#!/usr/bin/env python3
"""Teste direto de criacao de calculadora usando agentes especializados."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Optional


def resolve_project_root() -> Path:
    """Resolve a raiz do projeto de forma portavel."""
    env_root = os.getenv("MYCLAUDE_ROOT")
    if env_root:
        candidate = Path(env_root).expanduser().resolve()
        if candidate.exists():
            return candidate

    # scripts/testing/test_calculadora.py -> raiz
    return Path(__file__).resolve().parent.parent.parent


def prepare_runtime_paths(project_root: Optional[Path] = None) -> Path:
    """Prepara cwd e sys.path para importar modulos locais."""
    root = project_root or resolve_project_root()
    os.chdir(root)
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root


def _extract_task_fields(result: dict[str, Any]) -> tuple[str, str, str, str, int, int]:
    """Extrai campos esperados da resposta do agente para exibicao."""
    task = result.get("task", {})
    return (
        str(result.get("success", "")),
        str(result.get("agent", "")),
        str(task.get("status", "")),
        str(task.get("project_path", "")),
        len(str(task.get("code", ""))),
        len(str(task.get("tests", ""))),
    )


async def main() -> None:
    """Executa o fluxo de criacao de projeto de calculadora."""
    project_root = prepare_runtime_paths()

    from specialized_agents import get_agent_manager

    print("=" * 60)
    print("  TESTE: CRIACAO DE CALCULADORA COM LLM OTIMIZADO")
    print("=" * 60)
    print(f"  ROOT: {project_root}")
    print()

    print("[1/5] Inicializando Agent Manager...")
    manager = get_agent_manager()
    await manager.initialize()

    print("[2/5] Enviando requisicao para o agente Python...")
    print("      Aguarde enquanto o LLM gera o codigo...")
    print()

    description = """Calculadora CLI com:
- Soma, subtracao, multiplicacao, divisao
- Potenciacao e raiz quadrada
- Memoria para armazenar valores
- Historico de operacoes"""

    result = await manager.create_project(
        language="python",
        description=description,
        project_name="calculadora_final",
    )

    print("[3/5] Processamento concluido!")
    print()

    success, agent, status, project_path, code_len, tests_len = _extract_task_fields(result)

    print("[4/5] RESULTADO:")
    print("-" * 60)
    print(f"  Success: {success}")
    print(f"  Agent: {agent}")
    print(f"  Status: {status}")
    print(f"  Code Length: {code_len} chars")
    print(f"  Tests Length: {tests_len} chars")
    print(f"  Project Path: {project_path}")
    print()

    print("[5/5] CODIGO GERADO:")
    print("-" * 60)
    code = str(result.get("task", {}).get("code", ""))
    if code:
        print(code[:2000] + "..." if len(code) > 2000 else code)
    else:
        print("(codigo vazio)")
    print("-" * 60)

    if code:
        output_path = Path("/tmp/calculadora_gerada.py")
        output_path.write_text(code, encoding="utf-8")
        print(f"\n[OK] Codigo salvo em {output_path}")

    print("\n" + "=" * 60)
    print("  FIM DO TESTE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
