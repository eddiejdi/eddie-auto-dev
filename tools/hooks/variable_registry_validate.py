#!/usr/bin/env python3
"""Valida novas variáveis de ambiente/configuração contra o catálogo central
antes de permitir que um agente (Claude Code, Cursor, Grok, Codex) as crie.

Fonte de verdade: .variables-catalog/catalog.json (gerado por tools/catalog_variables.py).

Dois modos de uso:
  1. PreToolUse hook (Claude Code / Cursor / Grok via hooks.json):
       stdin = payload JSON do hook, stdout = decisão JSON.
  2. CLI / pre-commit / CI:
       python3 tools/hooks/variable_registry_validate.py --staged
       python3 tools/hooks/variable_registry_validate.py <file> [<file> ...]

Regras:
  - Nome já existe no catálogo (exato)               → OK, silencioso.
  - Nome é "quase" um existente (case/separador/typo) → DENY, sugere o nome
    canônico já cadastrado (evita duplicata de taxonomia, ex: API_TOKEN vs
    APITOKEN vs Api_Token).
  - Nome não segue UPPER_SNAKE_CASE                   → WARN com correção sugerida.
  - Nome genuinamente novo, sem duplicata             → WARN lembrando de
    catalogar (rodar tools/catalog_variables.py + documentar em
    docs/variables-taxonomy/).
"""
from __future__ import annotations

import difflib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_FILE = REPO_ROOT / ".variables-catalog" / "catalog.json"

# Extração de nomes de variável em código-fonte (qualquer arquivo).
CODE_VAR_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"os\.(?:getenv|environ\.get)\(\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]"),
    re.compile(r"os\.environ\[\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*\]"),
    re.compile(r"process\.env\.([A-Za-z_][A-Za-z0-9_]*)"),
    re.compile(r"process\.env\[\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*\]"),
    re.compile(r"^\s*Environment\s*=\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)=", re.MULTILINE),
    re.compile(r"^\s*export\s+([A-Z_][A-Z0-9_]*)=", re.MULTILINE),
)

# Extração restrita a arquivos .env* (linha inteira é KEY=VALUE).
ENV_FILE_VAR_PATTERN = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", re.MULTILINE)

ENV_FILE_NAME_RE = re.compile(r"(^|/)[^/]*\.env(\.[^/]*)?$")

FUZZY_CUTOFF = 0.86


def _normalize(name: str) -> str:
    return re.sub(r"[_\-.]", "", name).upper()


def load_catalog_names() -> dict[str, str]:
    """Retorna {NOME_CANÔNICO: categoria} a partir do catálogo."""
    if not CATALOG_FILE.exists():
        return {}
    try:
        data = json.loads(CATALOG_FILE.read_text())
    except Exception:
        return {}
    names: dict[str, str] = {}
    for category, entries in data.get("categories", {}).items():
        if not isinstance(entries, dict):
            continue
        for name in entries:
            names[name] = category
    return names


def extract_candidates(blob: str, file_path: str = "") -> set[str]:
    found: set[str] = set()
    for pattern in CODE_VAR_PATTERNS:
        for m in pattern.finditer(blob):
            found.add(m.group(1))
    if ENV_FILE_NAME_RE.search(file_path or ""):
        for m in ENV_FILE_VAR_PATTERN.finditer(blob):
            found.add(m.group(1))
    return found


def classify(name: str, catalog_names: dict[str, str]) -> tuple[str, str]:
    """Retorna (status, mensagem). status ∈ {ok, duplicate, lint, new}."""
    if name in catalog_names:
        return "ok", ""

    normalized = _normalize(name)
    for existing in catalog_names:
        if _normalize(existing) == normalized:
            return "duplicate", (
                f"'{name}' é uma variação de '{existing}' (já cadastrada, categoria "
                f"'{catalog_names[existing]}'). Reutilize o nome existente em vez de "
                "criar uma variante — evita fragmentar a taxonomia."
            )

    close = difflib.get_close_matches(name, catalog_names.keys(), n=1, cutoff=FUZZY_CUTOFF)
    if close:
        existing = close[0]
        return "duplicate", (
            f"'{name}' é muito parecida com '{existing}' (já cadastrada, categoria "
            f"'{catalog_names[existing]}'). Confirme se não é a mesma variável antes "
            "de criar uma nova — possível typo."
        )

    if not re.match(r"^[A-Z][A-Z0-9_]*$", name):
        suggestion = re.sub(r"[^A-Za-z0-9]+", "_", name).upper().strip("_")
        return "lint", (
            f"'{name}' não segue a convenção UPPER_SNAKE_CASE usada no catálogo. "
            f"Sugestão: '{suggestion}'."
        )

    return "new", (
        f"'{name}' não está no catálogo (.variables-catalog/catalog.json). Antes de "
        "seguir: documente o propósito em docs/variables-taxonomy/ e rode "
        "`python3 tools/catalog_variables.py` para reindexar."
    )


def evaluate(blob: str, file_path: str = "") -> list[tuple[str, str, str]]:
    """Retorna lista de (nome, status, mensagem) para candidatos não-'ok'."""
    catalog_names = load_catalog_names()
    results = []
    for name in sorted(extract_candidates(blob, file_path)):
        status, message = classify(name, catalog_names)
        if status != "ok":
            results.append((name, status, message))
    return results


# ---------------------------------------------------------------------------
# Modo 1: PreToolUse hook (Claude Code / Cursor / Grok)
# ---------------------------------------------------------------------------

def _get_blob_and_path(payload: dict[str, Any]) -> tuple[str, str]:
    tool_input = payload.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return str(tool_input), ""
    parts = []
    for key in ("command", "cmd", "new_string", "content"):
        v = tool_input.get(key, "")
        if isinstance(v, str) and v:
            parts.append(v)
    file_path = tool_input.get("file_path", "") or ""
    return "\n".join(parts), file_path


def _deny(reason: str, context: str) -> str:
    return json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
            "additionalContext": context,
        }
    })


def _warn(context: str) -> str:
    return json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": context,
        }
    })


def run_as_hook() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return 0

    blob, file_path = _get_blob_and_path(payload)
    if not blob:
        return 0

    results = evaluate(blob, file_path)
    if not results:
        return 0

    duplicates = [(n, m) for n, s, m in results if s == "duplicate"]
    others = [(n, m) for n, s, m in results if s != "duplicate"]

    if duplicates:
        context = "\n\n".join(m for _, m in duplicates)
        if others:
            context += "\n\n" + "\n\n".join(m for _, m in others)
        print(_deny(
            "Possível duplicata de taxonomia de variáveis detectada",
            context,
        ))
        return 0

    if others:
        context = "\n\n".join(m for _, m in others)
        print(_warn(f"📋 Registro de variáveis: {context}"))
        return 0

    return 0


# ---------------------------------------------------------------------------
# Modo 2: CLI / pre-commit / CI
# ---------------------------------------------------------------------------

def _staged_files() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    return [f for f in out.stdout.splitlines() if f.strip()]


def _staged_added_lines(file_path: str) -> str:
    out = subprocess.run(
        ["git", "diff", "--cached", "-U0", "--", file_path],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    added = [
        line[1:] for line in out.stdout.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    return "\n".join(added)


def run_as_cli(argv: list[str]) -> int:
    if "--staged" in argv:
        files = _staged_files()
        reader = _staged_added_lines
    else:
        files = [a for a in argv if not a.startswith("--")]
        reader = lambda f: Path(f).read_text(errors="ignore")  # noqa: E731

    skip_ext = (".lock", ".png", ".jpg", ".jpeg", ".pdf", ".json.bak")
    duplicate_found = False
    any_findings = False

    for f in files:
        if f.endswith(skip_ext) or f == str(CATALOG_FILE.relative_to(REPO_ROOT)):
            continue
        try:
            blob = reader(f)
        except Exception:
            continue
        if not blob:
            continue
        results = evaluate(blob, f)
        if not results:
            continue
        any_findings = True
        for name, status, message in results:
            icon = {"duplicate": "❌", "lint": "⚠️ ", "new": "📋"}.get(status, "•")
            print(f"{icon} [{f}] {message}")
            if status == "duplicate":
                duplicate_found = True

    if not any_findings:
        print("✅ variable_registry_validate: nenhuma variável nova ou duplicada detectada.")
    if duplicate_found:
        print(
            "\nCommit bloqueado: resolva as duplicatas de taxonomia acima "
            "(reutilize o nome existente) e tente novamente.",
            file=sys.stderr,
        )
        return 1
    return 0


def main() -> int:
    if len(sys.argv) > 1:
        return run_as_cli(sys.argv[1:])
    return run_as_hook()


if __name__ == "__main__":
    raise SystemExit(main())
