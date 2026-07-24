#!/usr/bin/env python3
"""Valida novos endpoints HTTP contra o catálogo de APIs.

Fonte de verdade: .apis-catalog/catalog.json (tools/catalog_apis.py).

Modos:
  1. PreToolUse hook (stdin JSON)
  2. CLI / pre-commit / CI:
       python3 tools/hooks/api_registry_validate.py --staged
       python3 tools/hooks/api_registry_validate.py <file> ...
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
CATALOG_FILE = REPO_ROOT / ".apis-catalog" / "catalog.json"
FUZZY_CUTOFF = 0.90

# Docs/testes/tooling contêm exemplos de rotas — não são endpoints de produção.
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

DECORATOR_RE = re.compile(
    r"""@(?:(?P<app>[A-Za-z_][A-Za-z0-9_]*)\.)?
        (?P<method>get|post|put|patch|delete|head|options)
        \(\s*['"](?P<path>[^'"]+)['"]
    """,
    re.IGNORECASE | re.VERBOSE,
)

FLASK_ROUTE_RE = re.compile(
    r"""@(?P<app>[A-Za-z_][A-Za-z0-9_]*)\.route\(\s*['"](?P<path>[^'"]+)['"]
        (?:[^)]*methods\s*=\s*\[(?P<methods>[^\]]+)\])?
    """,
    re.IGNORECASE | re.VERBOSE,
)

OPENAPI_PATH_RE = re.compile(
    r"""^\s{0,4}(/(?:[A-Za-z0-9_{}\-./:]+)):\s*$""",
    re.MULTILINE,
)
OPENAPI_METHOD_RE = re.compile(
    r"""^\s{2,6}(get|post|put|patch|delete|head|options):\s*$""",
    re.MULTILINE | re.IGNORECASE,
)


def _normalize_path(path: str) -> str:
    path = path.strip()
    if not path.startswith("/"):
        path = "/" + path
    path = re.sub(r"\{([^}:]+)(?::[^}]+)?\}", r"{\1}", path)
    path = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)", r"{\1}", path)
    path = re.sub(r"<([A-Za-z_][A-Za-z0-9_]*)>", r"{\1}", path)
    path = re.sub(r"//+", "/", path)
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return path


def _op_key(method: str, path: str) -> str:
    return f"{method.upper()} {_normalize_path(path)}"


def _should_skip_path(file_path: str) -> bool:
    if not file_path:
        return False
    norm = file_path.replace("\\", "/").lstrip("./")
    return any(norm.startswith(p) or norm == p.rstrip("/") for p in SKIP_PATH_PREFIXES)


def load_catalog_keys() -> dict[str, str]:
    """{operationKey: category} — only full METHOD /path keys (no bare path)."""
    if not CATALOG_FILE.exists():
        return {}
    try:
        data = json.loads(CATALOG_FILE.read_text())
    except Exception:
        return {}
    keys: dict[str, str] = {}
    for category, entries in data.get("categories", {}).items():
        if not isinstance(entries, dict):
            continue
        for op_key in entries:
            keys[op_key] = category
    return keys


def extract_candidates(blob: str, file_path: str = "") -> set[str]:
    found: set[str] = set()
    for m in DECORATOR_RE.finditer(blob):
        found.add(_op_key(m.group("method"), m.group("path")))
    for m in FLASK_ROUTE_RE.finditer(blob):
        methods_raw = m.group("methods") or "GET"
        methods = re.findall(r"[A-Za-z]+", methods_raw) or ["GET"]
        for method in methods:
            found.add(_op_key(method, m.group("path")))

    # OpenAPI yaml-ish: pair nearby path + method lines
    if file_path.endswith((".yaml", ".yml", ".json")) or "openapi" in file_path.lower():
        lines = blob.splitlines()
        current_path = None
        for line in lines:
            pm = re.match(r"""^\s{0,4}(/(?:[^:]+)):\s*$""", line)
            if pm:
                current_path = pm.group(1)
                continue
            mm = re.match(r"""^\s{2,8}(get|post|put|patch|delete|head|options):\s*$""", line, re.I)
            if mm and current_path:
                found.add(_op_key(mm.group(1), current_path))
    return found


def classify(op_key: str, catalog_keys: dict[str, str]) -> tuple[str, str]:
    if op_key in catalog_keys:
        return "ok", ""

    # exact path with different method is OK (not duplicate)
    parts = op_key.split(" ", 1)
    method, path = (parts[0], parts[1]) if len(parts) == 2 else ("", op_key)

    # Fuzzy only against same-method full keys; ignore trivial short paths (/, /x).
    same_method = [k for k in catalog_keys if k.startswith(method + " ")]
    path_segments = [s for s in path.split("/") if s]
    if len(path_segments) >= 1 and path not in {"/", ""}:
        close = difflib.get_close_matches(op_key, same_method, n=1, cutoff=FUZZY_CUTOFF)
        if close:
            existing = close[0]
            # Avoid false positives like GET /x ≈ GET / or GET /a ≈ GET /ab
            existing_path = existing.split(" ", 1)[1] if " " in existing else existing
            existing_segs = [s for s in existing_path.split("/") if s]
            if existing_segs and (
                path_segments[0] == existing_segs[0]
                or abs(len(path) - len(existing_path)) <= 2
            ):
                # Require high similarity on the path portion alone for short paths
                path_ratio = difflib.SequenceMatcher(None, path, existing_path).ratio()
                if path_ratio >= FUZZY_CUTOFF and path != existing_path:
                    return "duplicate", (
                        f"Endpoint '{op_key}' é muito parecido com '{existing}' "
                        f"(categoria '{catalog_keys[existing]}'). Confirme se não é o mesmo "
                        "contrato antes de criar outro — evita fragmentar a taxonomia de APIs."
                    )

    if path and not path.startswith("/"):
        return "lint", f"Path de API deve começar com '/': '{op_key}'."

    return "new", (
        f"Endpoint '{op_key}' não está no catálogo (.apis-catalog/catalog.json). "
        "Documente em docs/taxonomy/APIS.md e rode "
        "`python3 tools/catalog_apis.py` (ou `tools/catalog_taxonomy.py --domain apis`)."
    )


def evaluate(blob: str, file_path: str = "") -> list[tuple[str, str, str]]:
    catalog_keys = load_catalog_keys()
    results = []
    for op_key in sorted(extract_candidates(blob, file_path)):
        status, message = classify(op_key, catalog_keys)
        if status != "ok":
            results.append((op_key, status, message))
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


def _looks_like_api_blob(blob: str) -> bool:
    upper_hints = ("@APP.", "@ROUTER.", "APIROUTER", "OPENAPI")
    b = blob.upper()
    if any(h in b for h in upper_hints):
        return True
    if DECORATOR_RE.search(blob) or FLASK_ROUTE_RE.search(blob):
        return True
    return False


def run_as_hook() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return 0
    blob, file_path = _get_blob_and_path(payload)
    if not blob or not _looks_like_api_blob(blob):
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
        print(_deny("Possível duplicata de taxonomia de APIs detectada", context))
        return 0
    if others:
        print(_warn("📋 Registro de APIs: " + "\n\n".join(m for _, m in others)))
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
        try:
            blob = reader(f)
        except Exception:
            continue
        if not blob:
            continue
        if not _looks_like_api_blob(blob) and not f.endswith((".yaml", ".yml")):
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
        print("✅ api_registry_validate: nenhum endpoint novo ou duplicado detectado.")
    if duplicate_found:
        print(
            "\nCommit bloqueado: resolva as duplicatas de APIs acima "
            "(reutilize o endpoint existente) e tente novamente.",
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
