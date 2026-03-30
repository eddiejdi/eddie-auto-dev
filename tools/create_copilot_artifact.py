#!/usr/bin/env python3
"""Cria novos artefatos de customização do Copilot com validação e scaffolding automático.

Script interativo que guia criação de:
- Skills (.github/skills/<name>/SKILL.md)
- Agents (.github/agents/<name>.agent.md)
- Prompts (.github/prompts/<name>.prompt.md)
- Instructions (.github/instructions/<name>.instructions.md)

Todos os artefatos criados são validados com lint-frontmatter.py antes de serem salvos.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ArtifactType = Literal["skill", "agent", "prompt", "instruction"]


@dataclass(slots=True)
class ArtifactConfig:
    """Configuração de um artefato a ser criado."""

    artifact_type: ArtifactType
    name: str
    description: str
    applies_to: str | None = None  # para instruction
    content: str = ""


def _repo_root() -> Path:
    """Retorna o diretório raiz do repositório."""
    return Path(__file__).resolve().parents[2]


def _sanitize_name(name: str) -> str:
    """Sanitiza nome para usar em paths e frontmatter.

    Args:
        name: Nome bruto fornecido pelo usuário.

    Returns:
        Nome sanitizado: lowercase, hífens em vez de espaços.
    """
    return name.lower().replace(" ", "-").replace("_", "-")


def _read_input(prompt: str, default: str | None = None) -> str:
    """Lê input do usuário com prompt customizado.

    Args:
        prompt: Texto para exibir.
        default: Valor padrão se usuário deixar em branco.

    Returns:
        String fornecida (ou default).
    """
    full_prompt = prompt
    if default:
        full_prompt += f" [{default}]"
    full_prompt += ": "

    while True:
        response = input(full_prompt).strip()
        if response:
            return response
        if default:
            return default
        print("  ⚠️  Input obrigatório. Tente novamente.")


def _read_multiline(prompt: str) -> str:
    """Lê múltiplas linhas de input.

    Args:
        prompt: Texto inicial.

    Returns:
        Texto multilinhas (termina com linha vazia).
    """
    print(f"{prompt} (termine com linha vazia):")
    lines = []
    while True:
        line = input()
        if not line:
            break
        lines.append(line)
    return "\n".join(lines)


def _choose_artifact_type() -> ArtifactType:
    """Guia usuário a escolher tipo de artefato.

    Returns:
        Tipo selecionado.
    """
    options = {
        "1": "skill",
        "2": "agent",
        "3": "prompt",
        "4": "instruction",
    }

    print("\n🎯 Qual tipo de artefato deseja criar?")
    print("  1. Skill (workflow multi-step, recorrente)")
    print("  2. Agent (persona especializada)")
    print("  3. Prompt (tarefa única, workflow específico)")
    print("  4. Instruction (regras globais por path)")

    choice = input("\nEscolha (1-4): ").strip()
    if choice in options:
        return options[choice]

    print(f"❌ Opção '{choice}' inválida. Usando padrão: skill")
    return "skill"


def _collect_skill_info() -> ArtifactConfig:
    """Coleta informações para novo Skill.

    Returns:
        Configuração do skill.
    """
    print("\n📚 Criando novo Skill\n")

    name = _sanitize_name(_read_input("Nome do skill (ex: api-design, testing-advanced)"))
    description = _read_input(
        "Descrição (trigger phrase, ex: 'Use when: designing REST APIs')"
    )

    print("\n📝 Estrutura do Skill:")
    print("  - Objetivo: O que a skill ensina/permite")
    print("  - Escopo: Quando usar / quando NÃO usar")
    print("  - Workflow: Passos principais")
    print("  - Validação: Como verificar sucesso")

    objective = _read_input("Objetivo do skill")
    scope_use = _read_input("Quando usar (1-2 linhas)")
    scope_not = _read_input("Quando NÃO usar (1-2 linhas)")
    workflow = _read_multiline("Workflow dos passos")

    content = f"""# {name.replace('-', ' ').title()}

## Objetivo
{objective}

## Escopo

**Quando usar:**
{scope_use}

**Quando NÃO usar:**
{scope_not}

## Workflow

{workflow}

## Validação
Sucesso quando: [descreva aqui]

## Erros Comuns
- [erro 1]
- [erro 2]
"""

    return ArtifactConfig(
        artifact_type="skill",
        name=name,
        description=description,
        content=content,
    )


def _collect_agent_info() -> ArtifactConfig:
    """Coleta informações para novo Agent.

    Returns:
        Configuração do agent.
    """
    print("\n🤖 Criando novo Agent\n")

    name = _sanitize_name(_read_input("Nome do agent (ex: api-architect, security-auditor)"))
    description = _read_input(
        "Descrição (trigger phrases, ex: 'Use when: designing REST APIs, reviewing contracts')"
    )

    print("\nFerramenta disponíveis: read, edit, execute, search, semantic_search, web")
    tools_str = _read_input("Ferramentas (comma-separated, ex: read, edit, search)")
    tools = [t.strip() for t in tools_str.split(",") if t.strip()]

    role = _read_multiline("Definição de papel (persona, responsabilidades)")

    content = f"""# {name.replace('-', ' ').title()} Agent

## Persona
{role}

## Responsabilidades
[Descreva responsabilidades principais]

## Workflow
[Descreva processo típico de execução]

## Limitações
[Descreva escopo limitado do agent]
"""

    return ArtifactConfig(
        artifact_type="agent",
        name=name,
        description=description,
        content=content,
    )


def _collect_prompt_info() -> ArtifactConfig:
    """Coleta informações para novo Prompt.

    Returns:
        Configuração do prompt.
    """
    print("\n💬 Criando novo Prompt (task-specific workflow)\n")

    name = _sanitize_name(_read_input("Nome do prompt (ex: code-review-pr, design-api)"))
    description = _read_input(
        "Descrição com trigger phrases (ex: 'Use when: reviewing code for security issues')"
    )

    objective = _read_input("Objetivo único deste prompt")
    example = _read_input("Exemplo de invocação (ex: '@code-review-pr python.py')")
    output_format = _read_input("Formato esperado de output")

    content = f"""# {name.replace('-', ' ').title()} Prompt

## Objetivo
{objective}

## Processo
[Descreva passos do workflow]

## Entrada
Exemplo: {example}

## Saída Esperada
{output_format}

## Validação
Sucesso quando: [critério]
"""

    return ArtifactConfig(
        artifact_type="prompt",
        name=name,
        description=description,
        content=content,
    )


def _collect_instruction_info() -> ArtifactConfig:
    """Coleta informações para nova Instruction.

    Returns:
        Configuração da instrução.
    """
    print("\n📋 Criando nova Instruction (regras por path)\n")

    name = _sanitize_name(_read_input("Nome da instrução (ex: python-coding, trading-db)"))
    applies_to = _read_input(
        "Glob pattern (ex: 'src/api/**.py', '**/trading/**.py')"
    )
    description = _read_input("Descrição (ex: 'Python coding standards for API')")

    rules = _read_multiline("Regras principais (uma por linha)")

    content = f"""# {name.replace('-', ' ').title()} Standards

## Escopo
Arquivos matching: `{applies_to}`

## Regras

{rules}

## Exemplos
[Adicione exemplos de código correto]

## Contra-exemplos
[Adicione exemplos do que EVITAR]
"""

    return ArtifactConfig(
        artifact_type="instruction",
        name=name,
        description=description,
        applies_to=applies_to,
        content=content,
    )


def _generate_frontmatter(config: ArtifactConfig) -> str:
    """Gera frontmatter YAML para o artefato.

    Args:
        config: Configuração do artefato.

    Returns:
        Bloco YAML com ---...---
    """
    lines = ["---", f'description: "{config.description}"']

    if config.applies_to:
        lines.append(f'applyTo: "{config.applies_to}"')

    if config.artifact_type in ("agent",):
        # agents podem ter um campo 'tools'
        lines.append('tools: [read, edit, search]')

    lines.append("---")
    return "\n".join(lines)


def _get_artifact_path(config: ArtifactConfig) -> Path:
    """Determina o caminho destino baseado no tipo.

    Args:
        config: Configuração do artefato.

    Returns:
        Caminho absoluto onde salvar.
    """
    repo_root = _repo_root()

    if config.artifact_type == "skill":
        return repo_root / ".github" / "skills" / config.name / "SKILL.md"
    elif config.artifact_type == "agent":
        return repo_root / ".github" / "agents" / f"{config.name}.agent.md"
    elif config.artifact_type == "prompt":
        return repo_root / ".github" / "prompts" / f"{config.name}.prompt.md"
    elif config.artifact_type == "instruction":
        return repo_root / ".github" / "instructions" / f"{config.name}.instructions.md"

    raise ValueError(f"Unknown artifact type: {config.artifact_type}")


def _validate_artifact(file_path: Path) -> bool:
    """Valida artefato usando lint-frontmatter.py.

    Args:
        file_path: Caminho do arquivo criado.

    Returns:
        True se válido, False caso contrário.
    """
    repo_root = _repo_root()
    linter_path = repo_root / ".github" / "hooks" / "lint-frontmatter.py"

    if not linter_path.exists():
        print("⚠️  Linter não encontrado. Pulando validação.")
        return True

    result = subprocess.run(
        [sys.executable, str(linter_path)],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"❌ Validação falhou:\n{result.stdout}")
        return False

    print("✅ Validação passou")
    return True


def _save_artifact(config: ArtifactConfig) -> Path:
    """Salva artefato em disco.

    Args:
        config: Configuração do artefato.

    Returns:
        Caminho onde foi salvo.

    Raises:
        FileExistsError: Se arquivo já existe.
    """
    dest_path = _get_artifact_path(config)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    if dest_path.exists():
        raise FileExistsError(f"Artefato já existe: {dest_path}")

    frontmatter = _generate_frontmatter(config)
    full_content = frontmatter + "\n\n" + config.content

    dest_path.write_text(full_content, encoding="utf-8")

    return dest_path


def main() -> int:
    """Executa fluxo de criação de artefato interativo.

    Returns:
        Código de saída (0 sucesso, 1 erro).
    """
    print("=" * 60)
    print("🚀 Copilot Artifact Creator")
    print("=" * 60)

    try:
        # Escolha tipo
        artifact_type = _choose_artifact_type()

        # Coleta informações
        if artifact_type == "skill":
            config = _collect_skill_info()
        elif artifact_type == "agent":
            config = _collect_agent_info()
        elif artifact_type == "prompt":
            config = _collect_prompt_info()
        elif artifact_type == "instruction":
            config = _collect_instruction_info()

        # Confirma criação
        dest = _get_artifact_path(config)
        print(f"\n📂 Destino: {dest.relative_to(_repo_root())}")
        confirm = input("Criar artefato? (s/n): ").strip().lower()

        if confirm != "s":
            print("❌ Cancelado.")
            return 1

        # Salva
        saved_path = _save_artifact(config)
        print(f"✅ Artefato criado: {saved_path.relative_to(_repo_root())}")

        # Valida
        print("\n🔍 Validando frontmatter...")
        if not _validate_artifact(saved_path):
            print("❌ Validação falhou. Arquivo removido.")
            saved_path.unlink()
            return 1

        print(f"\n🎉 Sucesso! Seu {config.artifact_type} está pronto:")
        print(f"   {saved_path.relative_to(_repo_root())}")
        print("\nPróximos passos:")
        print("  1. Edite o arquivo para adicionar conteúdo detalhado")
        print("  2. Execute 'git add' e 'git commit'")
        print("  3. Push para PR e aguarde validação em CI")

        return 0

    except KeyboardInterrupt:
        print("\n\n❌ Cancelado pelo usuário.")
        return 1
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
