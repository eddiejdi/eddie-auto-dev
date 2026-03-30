from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ValidationIssue:
    """Representa um problema encontrado na validacao de frontmatter."""

    path: Path
    message: str


def _extract_frontmatter(text: str) -> str | None:
    """Extrai o bloco YAML inicial delimitado por `---`.

    Args:
        text: Conteudo completo do arquivo.

    Returns:
        O conteudo YAML sem delimitadores, ou None se ausente/invalido.
    """
    if not text.startswith("---\n"):
        return None

    end_marker = text.find("\n---\n", 4)
    if end_marker == -1:
        return None

    return text[4:end_marker]


def _strip_quotes(value: str) -> str:
    """Remove aspas simples ou duplas de um valor textual.

    Args:
        value: Valor bruto em string.

    Returns:
        Valor sem aspas de borda.
    """
    if len(value) >= 2 and ((value[0] == "'" and value[-1] == "'") or (value[0] == '"' and value[-1] == '"')):
        return value[1:-1]
    return value


def _parse_frontmatter(frontmatter: str) -> tuple[dict[str, Any] | None, str | None]:
    """Faz parse simples de frontmatter YAML-like em formato chave: valor.

    Args:
        frontmatter: Conteudo sem delimitadores.

    Returns:
        Tupla (dados, erro). Quando erro existir, dados sera None.
    """
    data: dict[str, Any] = {}
    for raw_line in frontmatter.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if ":" not in line:
            return None, f"invalid yaml-like syntax: {raw_line}"

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            return None, f"invalid key in frontmatter: {raw_line}"

        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if inner:
                items = [_strip_quotes(item.strip()) for item in inner.split(",") if item.strip()]
            else:
                items = []
            data[key] = items
        else:
            data[key] = _strip_quotes(value)

    return data, None


def _should_have_description(path: Path) -> bool:
    """Indica se o tipo de artefato exige o campo `description`.

    Args:
        path: Caminho do arquivo analisado.

    Returns:
        True quando o arquivo deve declarar `description`.
    """
    name = path.name
    return name.endswith(".instructions.md") or name.endswith(".prompt.md") or name.endswith(".agent.md") or name == "SKILL.md"


def _is_overly_broad_apply_to(value: str) -> bool:
    """Verifica se um applyTo e amplo demais para uso seguro.

    Args:
        value: Valor bruto do campo applyTo.

    Returns:
        True quando o padrao e excessivamente amplo.
    """
    normalized = value.strip()
    return normalized in {"**", "**/*", "*"}


def validate_file(path: Path) -> list[ValidationIssue]:
    """Valida o frontmatter de um arquivo de customizacao.

    Args:
        path: Caminho do arquivo alvo.

    Returns:
        Lista de problemas encontrados.
    """
    issues: list[ValidationIssue] = []
    text = path.read_text(encoding="utf-8")

    if "\t" in text.split("\n", 20)[0:20]:
        issues.append(ValidationIssue(path=path, message="frontmatter must not use tab indentation"))

    frontmatter = _extract_frontmatter(text)
    if frontmatter is None:
        issues.append(ValidationIssue(path=path, message="missing or malformed frontmatter block"))
        return issues

    parsed, parse_error = _parse_frontmatter(frontmatter)
    if parse_error:
        issues.append(ValidationIssue(path=path, message=parse_error))
        return issues

    if not isinstance(parsed, dict):
        issues.append(ValidationIssue(path=path, message="frontmatter must be a YAML mapping"))
        return issues

    if _should_have_description(path) and not parsed.get("description"):
        issues.append(ValidationIssue(path=path, message="missing required field: description"))

    apply_to = parsed.get("applyTo")
    if isinstance(apply_to, str) and _is_overly_broad_apply_to(apply_to):
        issues.append(ValidationIssue(path=path, message="applyTo is too broad; prefer domain-specific globs"))

    return issues


def _iter_target_files(repo_root: Path) -> list[Path]:
    """Lista arquivos de customizacao que devem ser validados.

    Args:
        repo_root: Caminho raiz do repositorio.

    Returns:
        Lista ordenada de caminhos alvo.
    """
    patterns = [
        ".github/instructions/*.md",
        ".github/prompts/*.prompt.md",
        ".github/agents/*.agent.md",
        ".github/skills/*/SKILL.md",
    ]

    files: list[Path] = []
    for pattern in patterns:
        files.extend(repo_root.glob(pattern))

    return sorted(set(files))


def main() -> int:
    """Executa validacao de frontmatter para artefatos de customizacao.

    Returns:
        Codigo de saida do processo (0 sem erros, 1 com erros).
    """
    repo_root = Path(__file__).resolve().parents[2]
    files = _iter_target_files(repo_root)

    issues: list[ValidationIssue] = []
    for file_path in files:
        issues.extend(validate_file(file_path))

    if issues:
        for issue in issues:
            print(f"{issue.path.relative_to(repo_root)}: {issue.message}")
        return 1

    print(f"frontmatter lint passed for {len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
