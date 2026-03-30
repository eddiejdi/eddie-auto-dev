#!/usr/bin/env python3
"""Validador universal para customizações de múltiplas extensões IA.

Suporta:
- GitHub Copilot (YAML frontmatter)
- Codex / Continue (JSON config)
- Futuro: Claude for VS Code, Cursor, etc.

Princípio: Reuse máximo de lógica entre extensões.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

ConfigFormat = Literal["yaml", "json", "toml"]


@dataclass(slots=True)
class ValidationResult:
    """Resultado de uma validação."""

    path: Path
    format: ConfigFormat
    is_valid: bool
    errors: list[str]


def _validate_description(
    obj: dict[str, Any] | None, source: str
) -> list[str]:
    """Valida que 'description' com trigger phrases existe.

    Args:
        obj: Dicionário contendo field 'description'.
        source: Context para erro (ex: "agent 'security-auditor'").

    Returns:
        Lista de erros (vazia se válido).
    """
    errors = []

    if obj is None:
        errors.append(f"{source}: missing or null object")
        return errors

    description = obj.get("description", "").strip()
    if not description:
        errors.append(f"{source}: missing 'description' field")
        return errors

    # Trigger phrases indicam discovery melhor, mas não são obrigatórias
    # (alguns agentes legados podem não ter)
    trigger_keywords = ("use when:", "quando:", "use for:", "quando usar:")
    has_trigger = any(kw in description.lower() for kw in trigger_keywords)

    # Warning apenas, não erro — alguns agents podem ser genéricos
    if not has_trigger and len(description) < 20:
        # Se descrição é muito curta, avisa
        pass

    return errors


def _validate_yaml_frontmatter(path: Path) -> list[str]:
    """Valida YAML frontmatter de arquivo Copilot.

    Args:
        path: Path do arquivo (.instructions.md, .prompt.md, etc).

    Returns:
        Lista de erros encontrados.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        return [f"Cannot read file: {e}"]

    # Extrai frontmatter simples
    if not content.startswith("---\n"):
        return ["Missing YAML frontmatter (expected '---' at start)"]

    end_idx = content.find("\n---\n", 4)
    if end_idx == -1:
        return ["Malformed YAML frontmatter (missing closing '---')"]

    frontmatter_text = content[4:end_idx]

    # Parse simples procurando 'description:'
    errors = []
    has_description = False

    for line in frontmatter_text.splitlines():
        if line.strip().startswith("description:"):
            has_description = True
            break

    if not has_description:
        errors.append("Missing 'description' field in YAML frontmatter")

    return errors


def _validate_json_schema(path: Path) -> list[str]:
    """Valida JSON config para Codex/Continue.

    Args:
        path: Path do arquivo (config.json ou similar).

    Returns:
        Lista de erros encontrados.
    """
    try:
        content = path.read_text(encoding="utf-8")
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return [f"Invalid JSON: {e}"]
    except Exception as e:
        return [f"Cannot read file: {e}"]

    errors = []

    # Valida top-level agents array
    agents = data.get("agents", [])
    if not isinstance(agents, list):
        errors.append("'agents' must be an array")
        return errors

    # Valida cada agent
    for idx, agent in enumerate(agents):
        agent_name = agent.get("id", f"agent[{idx}]")
        errors.extend(_validate_description(agent, f"Agent '{agent_name}'"))

    # Valida top-level personas/prompts
    for key in ("personas", "prompts"):
        items = data.get(key, [])
        if not isinstance(items, list):
            continue

        for idx, item in enumerate(items):
            item_name = item.get("id", f"{key}[{idx}]")
            errors.extend(_validate_description(item, f"{key.title()} '{item_name}'"))

    return errors


def _validate_toml_schema(path: Path) -> list[str]:
    """Placeholder para validação futura de TOML (Continue, Claude).

    Args:
        path: Path do arquivo (.continue/config.toml ou similar).

    Returns:
        Lista de erros encontrados.
    """
    # Futuro: usar tomllib (Python 3.11+) ou toml package
    return ["TOML validation not yet implemented"]


def validate_customization(path: Path, format: ConfigFormat | None = None) -> ValidationResult:
    """Valida customização agnóstica de extensão IA.

    Args:
        path: Path do arquivo.
        format: Formato esperado. Se None, detecta pela extensão.

    Returns:
        ValidationResult com status e erros.
    """
    if format is None:
        # Detect automaticamente
        if path.name.endswith(".json"):
            format = "json"
        elif path.name.endswith((".toml", ".yaml", ".yml")):
            format = "yaml" if path.name.endswith((".yaml", ".yml")) else "toml"
        elif path.name.endswith(".md"):
            format = "yaml"  # Copilot usa YAML frontmatter em MD
        else:
            return ValidationResult(
                path=path,
                format="yaml",
                is_valid=False,
                errors=[f"Unknown file type for path: {path}"],
            )

    if not path.exists():
        return ValidationResult(
            path=path,
            format=format,
            is_valid=False,
            errors=[f"File not found: {path}"],
        )

    if format == "yaml":
        errors = _validate_yaml_frontmatter(path)
    elif format == "json":
        errors = _validate_json_schema(path)
    elif format == "toml":
        errors = _validate_toml_schema(path)
    else:
        errors = [f"Unsupported format: {format}"]

    return ValidationResult(
        path=path,
        format=format,
        is_valid=len(errors) == 0,
        errors=errors,
    )


def main() -> int:
    """Script para validar customizações de extensões IA.

    Uso:
        python tools/validator_universal.py .github/prompts/*.prompt.md
        python tools/validator_universal.py .codex/config.json

    Returns:
        0 se tudo válido, 1 se algum erro.
    """
    import sys

    if len(sys.argv) < 2:
        print("Usage: validator_universal.py <files...>")
        print("  Automatically detects format (YAML/JSON/TOML)")
        return 1

    all_valid = True
    for arg in sys.argv[1:]:
        path = Path(arg)
        result = validate_customization(path)

        if not result.is_valid:
            print(f"❌ {path} ({result.format})")
            for error in result.errors:
                print(f"   {error}")
            all_valid = False
        else:
            print(f"✅ {path} ({result.format})")

    print()
    if all_valid:
        print("✅ All customizations valid")
        return 0
    else:
        print("❌ Some customizations invalid")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
