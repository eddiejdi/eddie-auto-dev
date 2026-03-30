#!/usr/bin/env python3
"""Sincroniza customizações do Copilot para config do Codex/Continue.

Extrai agents e prompts de `.github/agents/` e `.github/prompts/`
e gera `.codex/config.json` automaticamente.

Benefício: Uma única fonte de verdade para múltiplas extensões.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class CustomizationItem:
    """Uma customização (agent, prompt, skill)."""

    id: str
    description: str
    sourceFile: str
    tools: list[str] | None = None
    type: str = "agent"  # agent, prompt, skill


def _extract_yaml_field(text: str, field: str) -> str | None:
    """Extrai campo YAML simples de texto.

    Args:
        text: Conteúdo com frontmatter YAML.
        field: Nome do field (ex: 'description').

    Returns:
        Valor (sem aspas), ou None se não encontrado.
    """
    # Pattern: description: "valor" ou description: valor
    pattern = rf'^{field}:\s*[\"\']?(.+?)[\"\']?$'
    for line in text.splitlines():
        match = re.match(pattern, line.strip(), re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _extract_yaml_list_field(text: str, field: str) -> list[str] | None:
    """Extrai lista YAML de um field.

    Args:
        text: Conteúdo com frontmatter.
        field: Nome do field (ex: 'tools').

    Returns:
        List de strings, ou None.
    """
    # Pattern: tools: [item1, item2] ou tools:\n  - item1
    pattern = rf'^{field}:\s*\[(.+?)\]'
    for line in text.splitlines():
        match = re.match(pattern, line.strip(), re.IGNORECASE)
        if match:
            items_str = match.group(1)
            return [item.strip().strip('\'"') for item in items_str.split(",")]
    return None


def _extract_frontmatter(content: str) -> str | None:
    """Extrai bloco frontmatter YAML de arquivo.

    Args:
        content: Conteúdo completo do arquivo.

    Returns:
        Texto YAML (sem delimitadores), ou None.
    """
    if not content.startswith("---\n"):
        return None
    end_idx = content.find("\n---\n", 4)
    if end_idx == -1:
        return None
    return content[4:end_idx]


def _process_agent_file(path: Path) -> CustomizationItem | None:
    """Processa arquivo .agent.md e extrai customização.

    Args:
        path: Caminho do arquivo.

    Returns:
        CustomizationItem preenchido, ou None se inválido.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return None

    frontmatter = _extract_frontmatter(content)
    if not frontmatter:
        return None

    description = _extract_yaml_field(frontmatter, "description")
    if not description:
        return None

    tools = _extract_yaml_list_field(frontmatter, "tools") or ["read", "search"]

    agent_id = path.stem  # Remove .agent.md suffix
    try:
        relative_path = str(path.relative_to(Path.cwd()))
    except ValueError:
        relative_path = str(path)
    return CustomizationItem(
        id=agent_id,
        description=description,
        sourceFile=relative_path,
        tools=tools,
        type="agent",
    )


def _process_prompt_file(path: Path) -> CustomizationItem | None:
    """Processa arquivo .prompt.md e extrai customização.

    Args:
        path: Caminho do arquivo.

    Returns:
        CustomizationItem preenchido, ou None se inválido.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return None

    frontmatter = _extract_frontmatter(content)
    if not frontmatter:
        return None

    description = _extract_yaml_field(frontmatter, "description")
    if not description:
        return None

    prompt_id = path.stem  # Remove .prompt.md suffix
    try:
        relative_path = str(path.relative_to(Path.cwd()))
    except ValueError:
        relative_path = str(path)
    return CustomizationItem(
        id=prompt_id,
        description=description,
        sourceFile=relative_path,
        type="prompt",
    )


def sync_codex_from_copilot(copilot_dir: Path | str = ".github") -> dict[str, Any]:
    """Sincroniza config do Codex a partir de customizações Copilot.

    Args:
        copilot_dir: Diretório base do Copilot (padrão: .github).

    Returns:
        Dicionário config.json para Codex.
    """
    copilot_dir = Path(copilot_dir)

    agents: list[dict[str, Any]] = []
    prompts: list[dict[str, Any]] = []

    # Processa agents
    agents_dir = copilot_dir / "agents"
    if agents_dir.exists():
        for agent_file in agents_dir.glob("*.agent.md"):
            item = _process_agent_file(agent_file)
            if item:
                agents.append(asdict(item))

    # Processa prompts
    prompts_dir = copilot_dir / "prompts"
    if prompts_dir.exists():
        for prompt_file in prompts_dir.glob("*.prompt.md"):
            item = _process_prompt_file(prompt_file)
            if item:
                prompts.append(asdict(item))

    config = {
        "version": "1.0",
        "metadata": {
            "synced_from": "GitHub Copilot customizations",
            "source_repo": ".github/agents/ and .github/prompts/",
            "note": "Auto-generated. Edit .github/ files, not this JSON.",
        },
        "agents": agents,
        "prompts": prompts,
    }

    return config


def main() -> int:
    """Executa sync e salva em .codex/config.json.

    Returns:
        0 se sucesso, 1 se erro.
    """
    try:
        config = sync_codex_from_copilot(".github")

        # Cria diretório .codex se não existir
        codex_dir = Path(".codex")
        codex_dir.mkdir(exist_ok=True)

        config_path = codex_dir / "config.json"
        config_path.write_text(
            json.dumps(config, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        agent_count = len(config.get("agents", []))
        prompt_count = len(config.get("prompts", []))

        print(f"✅ Synced to {config_path}")
        print(f"   Agents: {agent_count}")
        print(f"   Prompts: {prompt_count}")

        return 0

    except Exception as e:
        print(f"❌ Sync failed: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
