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

import yaml


@dataclass(slots=True)
class CustomizationItem:
    """Uma customização (agent, prompt, skill)."""

    id: str
    description: str
    sourceFile: str
    tools: list[str] | None = None
    type: str = "agent"  # agent, prompt, skill


def _normalize_plugin_name(value: str) -> str:
    """Normaliza nome para o padrão de plugins do Codex."""
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized or "workspace-bridge"


def _strip_known_suffix(path: Path, suffix: str) -> str:
    """Remove um sufixo conhecido do nome do arquivo."""
    name = path.name
    if name.endswith(suffix):
        return name[: -len(suffix)]
    return path.stem


def _relative_path(path: Path) -> str:
    """Retorna caminho relativo ao diretório atual quando possível."""
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


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

    agent_id = _strip_known_suffix(path, ".agent.md")
    relative_path = _relative_path(path)
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

    prompt_id = _strip_known_suffix(path, ".prompt.md")
    relative_path = _relative_path(path)
    return CustomizationItem(
        id=prompt_id,
        description=description,
        sourceFile=relative_path,
        type="prompt",
    )


def _normalize_hook_command(entry: dict[str, Any]) -> str | None:
    """Converte comando de hook do Copilot para um comando portátil do Codex."""
    candidates = [entry.get("command"), entry.get("linux")]
    for candidate in candidates:
        if not isinstance(candidate, str) or not candidate.strip():
            continue
        script_match = re.search(r"(tools/[^\s]+\.py)", candidate)
        if script_match:
            return f"python3 ./{script_match.group(1)}"
        return candidate.strip()
    return None


def sync_codex_hooks_from_copilot(copilot_dir: Path | str = ".github") -> dict[str, Any]:
    """Converte hooks do Copilot para o formato `hooks.json` do Codex."""
    copilot_dir = Path(copilot_dir)
    hooks_dir = copilot_dir / "hooks"

    events: dict[str, list[dict[str, Any]]] = {}
    if not hooks_dir.exists():
        return {"hooks": events}

    for hook_file in sorted(hooks_dir.glob("*.json")):
        try:
            data = json.loads(hook_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        for event_name, entries in data.get("hooks", {}).items():
            if not isinstance(entries, list):
                continue

            event_hooks = events.setdefault(event_name, [])
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                command = _normalize_hook_command(entry)
                if not command:
                    continue
                event_hooks.append(
                    {
                        "matcher": ".*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": command,
                            }
                        ],
                    }
                )

    return {"hooks": events}


def sync_codex_mcp_from_continue(
    continue_dir: Path | str = ".continue",
    existing_mcp_path: Path | str = ".mcp.json",
) -> dict[str, Any]:
    """Monta `.mcp.json` do Codex a partir do existente e dos YAMLs do Continue."""
    continue_dir = Path(continue_dir)
    existing_mcp_path = Path(existing_mcp_path)

    merged: dict[str, Any] = {"mcpServers": {}}

    if existing_mcp_path.exists():
        try:
            data = json.loads(existing_mcp_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("mcpServers"), dict):
                merged["mcpServers"].update(data["mcpServers"])
        except Exception:
            pass

    mcp_dir = continue_dir / "mcpServers"
    if not mcp_dir.exists():
        return merged

    for yaml_file in sorted(mcp_dir.glob("*.y*ml")):
        try:
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
        except Exception:
            continue

        for server in data.get("mcpServers", []):
            if not isinstance(server, dict):
                continue
            name = server.get("name")
            if not isinstance(name, str) or not name or name in merged["mcpServers"]:
                continue

            normalized = {
                "command": server.get("command"),
                "args": server.get("args", []),
            }
            env = server.get("env")
            if isinstance(env, dict) and env:
                normalized["env"] = env
            merged["mcpServers"][name] = normalized

    return merged


def build_codex_plugin_manifest() -> dict[str, Any]:
    """Gera o manifesto mínimo do plugin local para Codex carregar hooks e MCPs."""
    plugin_name = _normalize_plugin_name(Path.cwd().name)
    display_name = Path.cwd().name
    return {
        "name": plugin_name,
        "version": "1.0.0",
        "description": "Bridge local entre customizações do Copilot e o Codex neste workspace.",
        "author": {
            "name": display_name,
        },
        "hooks": "./hooks.json",
        "mcpServers": "./.mcp.json",
        "interface": {
            "displayName": display_name,
            "shortDescription": "Importa hooks e MCPs locais para o Codex.",
            "longDescription": (
                "Plugin local do workspace que expõe ao Codex os hooks derivados do Copilot "
                "e os MCP servers definidos para este repositório."
            ),
            "developerName": display_name,
            "category": "Coding",
            "capabilities": ["Interactive", "Write"],
            "defaultPrompt": [
                "Use os hooks locais e o MCP homelab deste workspace durante a sessão."
            ],
            "screenshots": [],
        },
    }


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
            "hooks_path": "hooks.json",
            "mcp_path": ".mcp.json",
            "plugin_manifest": ".codex-plugin/plugin.json",
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
        hooks_config = sync_codex_hooks_from_copilot(".github")
        mcp_config = sync_codex_mcp_from_continue(".continue", ".mcp.json")
        plugin_manifest = build_codex_plugin_manifest()

        # Cria diretório .codex se não existir
        codex_dir = Path(".codex")
        codex_dir.mkdir(exist_ok=True)

        config_path = codex_dir / "config.json"
        config_path.write_text(
            json.dumps(config, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        hooks_path = Path("hooks.json")
        hooks_path.write_text(
            json.dumps(hooks_config, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        mcp_path = Path(".mcp.json")
        mcp_path.write_text(
            json.dumps(mcp_config, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        plugin_dir = Path(".codex-plugin")
        plugin_dir.mkdir(exist_ok=True)
        plugin_manifest_path = plugin_dir / "plugin.json"
        plugin_manifest_path.write_text(
            json.dumps(plugin_manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        agent_count = len(config.get("agents", []))
        prompt_count = len(config.get("prompts", []))
        hook_count = sum(len(entries) for entries in hooks_config.get("hooks", {}).values())
        mcp_count = len(mcp_config.get("mcpServers", {}))

        print(f"✅ Synced to {config_path}")
        print(f"   Agents: {agent_count}")
        print(f"   Prompts: {prompt_count}")
        print(f"   Hooks: {hook_count} -> {hooks_path}")
        print(f"   MCP servers: {mcp_count} -> {mcp_path}")
        print(f"   Plugin manifest: {plugin_manifest_path}")

        return 0

    except Exception as e:
        print(f"❌ Sync failed: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
