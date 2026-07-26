#!/usr/bin/env python3
"""Valida novas tabelas SQL/DDL contra o catálogo de tabelas.

Fonte de verdade: .tables-catalog/catalog.json (tools/catalog_tables.py).

Modos:
  1. PreToolUse hook (stdin JSON)
  2. CLI / pre-commit / CI:
       python3 tools/hooks/table_registry_validate.py --staged
       python3 tools/hooks/table_registry_validate.py <file> ...
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
CATALOG_FILE = REPO_ROOT / ".tables-catalog" / "catalog.json"
FUZZY_CUTOFF = 0.88

# Docs, tests e o próprio tooling usam CREATE TABLE em exemplos — não são DDL real.
SKIP_PATH_PREFIXES = (
    "docs/",
    "tests/",
    "tools/hooks/",
    "tools/catalog_",
    "tools/taxonomy_meta.py",
    ".tables-catalog/",
    ".apis-catalog/",
    ".taxonomy-catalog/",
    ".variables-catalog/",
)

# Tokens que a regex pode capturar por engano (ex.: IF de IF NOT EXISTS incompleto).
SQL_RESERVED_TABLE_NAMES = frozenset(
    {
        "if",
        "not",
        "exists",
        "for",
        "select",
        "from",
        "where",
        "table",
        "create",
        "alter",
        "drop",
        "index",
        "view",
        "into",
        "values",
        "and",
        "or",
        "as",
        "on",
        "set",
        "with",
        "null",
        "primary",
        "key",
        "constraint",
        "foreign",
        "references",
        "unique",
        "check",
        "default",
        "true",
        "false",
        "temp",
        "temporary",
        "public",
        "schema",
    }
)

CREATE_TABLE_RE = re.compile(
    r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
        (?:(?P<schema>\{?[A-Za-z_][A-Za-z0-9_]*\}?)\.)?
        (?P<table>\{?[A-Za-z_][A-Za-z0-9_]*\}?|"[A-Za-z_][A-Za-z0-9_]*")
    """,
    re.IGNORECASE | re.VERBOSE,
)

SCHEMA_CONST_RE = re.compile(
    r"""(?:^|\n)\s*SCHEMA\s*=\s*['"]([A-Za-z_][A-Za-z0-9_]*)['"]"""
)


def _should_skip_path(file_path: str) -> bool:
    if not file_path:
        return False
    norm = file_path.replace("\\", "/").lstrip("./")
    return any(norm.startswith(p) or norm == p.rstrip("/") for p in SKIP_PATH_PREFIXES)


def _normalize_fqn(schema: str | None, table: str) -> str:
    sch = (schema or "public").lower().strip().strip('"')
    tbl = table.lower().strip().strip('"')
    return f"{sch}.{tbl}"


def _resolve_token(token: str | None, schema_const: str | None) -> str | None:
    if not token:
        return None
    token = token.strip().strip('"')
    if token.startswith("{") or token in ("SCHEMA",):
        return schema_const
    return token


def load_catalog_names() -> dict[str, str]:
    """{fqn: category}"""
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
        for fqn in entries:
            names[fqn.lower()] = category
            # also bare table name for convenience
            bare = fqn.split(".")[-1]
            names.setdefault(bare, category)
    return names


def extract_candidates(blob: str) -> set[str]:
    schema_const = None
    m = SCHEMA_CONST_RE.search(blob)
    if m:
        schema_const = m.group(1)
    found: set[str] = set()
    for m in CREATE_TABLE_RE.finditer(blob):
        raw_schema = m.group("schema")
        raw_table = m.group("table")
        schema = _resolve_token(raw_schema, schema_const)
        table = _resolve_token(raw_table, schema_const)
        if not table or "{" in table or "}" in table:
            continue
        if table.lower() in SQL_RESERVED_TABLE_NAMES:
            continue
        if schema and schema.lower() in SQL_RESERVED_TABLE_NAMES - {"public"}:
            # schema token capturado por engano (ex.: IF.)
            continue
        found.add(_normalize_fqn(schema, table))
        found.add(table.lower())
    return found


def classify(name: str, catalog_names: dict[str, str]) -> tuple[str, str]:
    key = name.lower()
    if key in catalog_names:
        return "ok", ""

    # bare name vs fqn collisions handled via catalog keys
    close = difflib.get_close_matches(key, catalog_names.keys(), n=1, cutoff=FUZZY_CUTOFF)
    if close:
        existing = close[0]
        return "duplicate", (
            f"Tabela '{name}' é muito parecida com '{existing}' (já no catálogo, "
            f"categoria '{catalog_names[existing]}'). Reutilize a tabela existente "
            "ou renomeie de forma semanticamente distinta — evita fragmentar a taxonomia."
        )

    # snake_case preference for tables
    if not re.match(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)?$", key):
        suggestion = re.sub(r"[^A-Za-z0-9.]+", "_", key).lower().strip("_")
        return "lint", (
            f"Tabela '{name}' não segue snake_case (schema.table). Sugestão: '{suggestion}'."
        )

    return "new", (
        f"Tabela '{name}' não está no catálogo (.tables-catalog/catalog.json). "
        "Documente o propósito em docs/taxonomy/TABLES.md e rode "
        "`python3 tools/catalog_tables.py` (ou `tools/catalog_taxonomy.py --domain tables`)."
    )


def evaluate(blob: str, file_path: str = "") -> list[tuple[str, str, str]]:
    catalog_names = load_catalog_names()
    results = []
    for name in sorted(extract_candidates(blob)):
        status, message = classify(name, catalog_names)
        if status != "ok":
            results.append((name, status, message))
    return results


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
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
                "additionalContext": context,
            }
        }
    )


def _warn(context: str) -> str:
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": context,
            }
        }
    )


def run_as_hook() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return 0
    blob, file_path = _get_blob_and_path(payload)
    if not blob or "CREATE TABLE" not in blob.upper():
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
        print(_deny("Possível duplicata de taxonomia de tabelas detectada", context))
        return 0
    if others:
        print(_warn("📋 Registro de tabelas: " + "\n\n".join(m for _, m in others)))
    return 0


def _staged_files() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return [f for f in out.stdout.splitlines() if f.strip()]


def _staged_added_lines(file_path: str) -> str:
    out = subprocess.run(
        ["git", "diff", "--cached", "-U0", "--", file_path],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    added = [
        line[1:]
        for line in out.stdout.splitlines()
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

    skip_ext = (".lock", ".png", ".jpg", ".jpeg", ".pdf")
    duplicate_found = False
    any_findings = False

    for f in files:
        if f.endswith(skip_ext) or f.endswith("catalog.json"):
            continue
        if _should_skip_path(f):
            continue
        # only SQL/Python-ish production paths
        if not re.search(r"\.(sql|py)$", f, re.I):
            continue
        try:
            blob = reader(f)
        except Exception:
            continue
        if not blob or "CREATE TABLE" not in blob.upper():
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
        print("✅ table_registry_validate: nenhuma tabela nova ou duplicada detectada.")
    if duplicate_found:
        print(
            "\nCommit bloqueado: resolva as duplicatas de tabelas acima "
            "(reutilize a tabela existente) e tente novamente.",
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
