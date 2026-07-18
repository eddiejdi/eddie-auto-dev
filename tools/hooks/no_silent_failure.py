#!/usr/bin/env python3
"""no_silent_failure.py — Bloqueia padrões de erro silencioso / fallback sem incidente.

Política global (hooks + pre-commit + agents):
  Nunca permitir erros engolidos, fallbacks silenciosos ou "fail-open" sem
  comunicação de incidente.

Uso:
  python3 tools/hooks/no_silent_failure.py --staged
  python3 tools/hooks/no_silent_failure.py path/to/file.py

Escape intencional (linha):
  # silent-ok   ou   # incident-ok

Escape de sessão:
  ALLOW_SILENT_FAILURE=1

Códigos de saída:
  0 = limpo
  2 = violações (bloquear commit)
  1 = erro interno do detector (também comunica incidente; pre-commit bloqueia)
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]

# Escape explícito na mesma linha
_ESCAPE = re.compile(r"(#|//)\s*(silent-ok|incident-ok)\b", re.I)

# Python: except + pass na mesma linha
_RE_EXCEPT_PASS_SAME = re.compile(
    r"except\s*(\w+(\s+as\s+\w+)?)?\s*:\s*pass\b"
)
# Python: except Exception: ... return None/False/[]/{} sem log — heurística em bloco
_RE_EXCEPT_LINE = re.compile(r"^\s*except(\s+\w+(\s+as\s+\w+)?)?\s*:\s*(#.*)?$")
_RE_PASS = re.compile(r"^\s*pass\s*(#.*)?$")
_RE_CONTINUE = re.compile(r"^\s*continue\s*(#.*)?$")
_RE_RETURN_EMPTY = re.compile(
    r"^\s*return\s+(None|False|True|0|\[\]|\{\}|\"\"|\'\')\s*(#.*)?$"
)
_RE_LOG = re.compile(
    r"\b(logger\.|logging\.|print\(|emit_incident|incident_notify|log\(|warn|warning|error|exception|critical)\b",
    re.I,
)

# Shell / bash staged
_RE_SHELL_SWALLOW = re.compile(
    r"(>\s*/dev/null\s+2>&1\s*\|\|\s*true|2>/dev/null\s*\|\|\s*true|\|\|\s*true\b)"
)
_RE_SHELL_CRITICAL = re.compile(
    r"\b(wiki_sync|systemctl|docker\s+restart|psql|curl\s+-|git\s+push|deploy)\b",
    re.I,
)

# Comentários que marcam fail-open sem incidente
_RE_FAIL_OPEN_COMMENT = re.compile(
    r"(fail-open|fail open|non-blocking|não-bloqueante|nao-bloqueante|"
    r"silent(?:ly)?\s+ignore|engole|engolir|swallow|ignorad[oa]\s*silenc)",
    re.I,
)

SKIP_PATH_PARTS = (
    "/.venv/",
    "/node_modules/",
    "/__pycache__/",
    "/.archive/",
    "/vendor/",
)


@dataclass
class Finding:
    path: str
    line: int
    kind: str
    text: str

    def format(self) -> str:
        return f"  {self.path}:{self.line} [{self.kind}] {self.text.strip()[:160]}"


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        stderr=subprocess.DEVNULL,
    )


def staged_paths() -> list[str]:
    raw = _git("diff", "--cached", "--name-only", "--diff-filter=AM")
    return [p for p in raw.splitlines() if p]


def read_staged(path: str) -> str | None:
    try:
        return _git("show", f":{path}")
    except subprocess.CalledProcessError:
        fp = REPO_ROOT / path
        if fp.is_file():
            return fp.read_text(encoding="utf-8", errors="replace")
        return None


def _should_skip(path: str) -> bool:
    norm = "/" + path.replace("\\", "/")
    if any(s in norm for s in SKIP_PATH_PARTS):
        return True
    # O próprio detector e incident_notify podem conter exemplos
    base = Path(path).name
    if base in {"no_silent_failure.py", "incident_notify.py"}:
        return True
    return False


def _is_test(path: str) -> bool:
    p = path.replace("\\", "/")
    return (
        "/tests/" in f"/{p}"
        or p.startswith("tests/")
        or "/test_" in f"/{p}"
        or p.endswith("_test.py")
    )


def scan_python(path: str, content: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        lineno = i + 1
        if _ESCAPE.search(line):
            i += 1
            continue

        if _RE_EXCEPT_PASS_SAME.search(line):
            findings.append(
                Finding(path, lineno, "except-pass", line)
            )
            i += 1
            continue

        m = _RE_EXCEPT_LINE.match(line)
        if m:
            # Olha as próximas linhas do bloco (indent > except)
            except_indent = len(line) - len(line.lstrip(" \t"))
            j = i + 1
            block: list[tuple[int, str]] = []
            while j < len(lines):
                nxt = lines[j]
                if not nxt.strip():
                    j += 1
                    continue
                ind = len(nxt) - len(nxt.lstrip(" \t"))
                if ind <= except_indent:
                    break
                block.append((j + 1, nxt))
                # Limita bloco curto de swallow
                if len(block) >= 8:
                    break
                j += 1

            if not block:
                i += 1
                continue

            # Escape em qualquer linha do bloco (ex.: pass  # silent-ok)
            if any(_ESCAPE.search(t) for _, t in block):
                i = j
                continue

            block_text = "\n".join(t for _, t in block)
            has_log = bool(_RE_LOG.search(block_text))
            only_swallow = all(
                _RE_PASS.match(t)
                or _RE_CONTINUE.match(t)
                or _RE_RETURN_EMPTY.match(t)
                or t.strip().startswith("#")
                for _, t in block
            )
            if only_swallow and not has_log:
                kind = "except-swallow"
                # classifica
                if any(_RE_PASS.match(t) for _, t in block):
                    kind = "except-pass"
                elif any(_RE_CONTINUE.match(t) for _, t in block):
                    kind = "except-continue-silent"
                elif any(_RE_RETURN_EMPTY.match(t) for _, t in block):
                    kind = "except-return-empty-silent"
                findings.append(
                    Finding(
                        path,
                        lineno,
                        kind,
                        line + " → " + block[0][1].strip(),
                    )
                )
            i = j
            continue

        # Só comentários de linha completa (não regex/código) que documentam
        # fail-open sem menção a incidente.
        stripped = line.lstrip()
        if stripped.startswith("#") and _RE_FAIL_OPEN_COMMENT.search(stripped):
            if "incident" not in stripped.lower() and "incidente" not in stripped.lower():
                findings.append(
                    Finding(path, lineno, "fail-open-comment", line)
                )

        i += 1
    return findings


def scan_shell(path: str, content: str) -> list[Finding]:
    findings: list[Finding] = []
    for lineno, line in enumerate(content.splitlines(), 1):
        if _ESCAPE.search(line):
            continue
        if _RE_SHELL_SWALLOW.search(line) and _RE_SHELL_CRITICAL.search(line):
            findings.append(
                Finding(path, lineno, "shell-swallow-critical", line)
            )
        if re.search(r"\|\|\s*true\b", line) and re.search(
            r"(wiki_sync|incident|deploy|systemctl\s+restart)", line, re.I
        ):
            findings.append(
                Finding(path, lineno, "shell-true-swallow", line)
            )
    return findings


def scan_text(path: str, content: str) -> list[Finding]:
    if path.endswith((".py", ".pyi")):
        return scan_python(path, content)
    if path.endswith((".sh", ".bash")) or path.endswith("/pre-commit") or path.endswith("/post-commit"):
        return scan_shell(path, content)
    # githooks sem extensão
    base = Path(path).name
    if base in {"pre-commit", "post-commit", "pre-push"}:
        return scan_shell(path, content)
    return []


def find_violations(
    paths: Iterable[str],
    reader=read_staged,
) -> list[Finding]:
    out: list[Finding] = []
    for path in paths:
        if _should_skip(path):
            continue
        content = reader(path)
        if content is None:
            continue
        found = scan_text(path, content)
        # Em testes: só bloqueia except-pass explícito (mais ruidoso)
        if _is_test(path):
            found = [f for f in found if f.kind in {"except-pass", "shell-swallow-critical"}]
        out.extend(found)
    return out


def _cli_staged() -> int:
    if os.environ.get("ALLOW_SILENT_FAILURE", "").strip() in {"1", "true", "yes"}:
        print("  (ALLOW_SILENT_FAILURE set — checagem de erro silencioso pulada)")
        return 0
    paths = staged_paths()
    if not paths:
        return 0
    findings = find_violations(paths)
    if not findings:
        return 0

    print("❌ BLOQUEADO: erro silencioso / fallback sem comunicação de incidente")
    print()
    print("  Política global: nunca engolir Exception/pass, continue/return vazio")
    print("  em except, ou || true em operações críticas, sem log/incidente.")
    print()
    for f in findings:
        print(f.format())
    print()
    print("  Corrija: logue (logger/print), chame tools/hooks/incident_notify.py,")
    print("  ou marque a linha com `# silent-ok` / `# incident-ok` se for intencional.")
    print("  Escape de sessão: ALLOW_SILENT_FAILURE=1 (não recomendado).")
    return 2


def main(argv: list[str]) -> int:
    if "--staged" in argv or not argv:
        return _cli_staged()

    findings: list[Finding] = []
    for path in argv:
        if path.startswith("-"):
            continue
        p = Path(path)
        if not p.is_file():
            continue
        content = p.read_text(encoding="utf-8", errors="replace")
        findings.extend(scan_text(str(path), content))
    if findings:
        for f in findings:
            print(f.format())
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except Exception as exc:
        # Detector com bug: comunica incidente e FALHA (não fail-open silencioso)
        try:
            from tools.hooks.incident_notify import emit_incident

            emit_incident(
                "no_silent_failure",
                f"detector quebrou: {exc}",
                severity="error",
                details=repr(exc),
            )
        except Exception as nested:
            print(
                f"[no_silent_failure] INCIDENTE: detector falhou ({exc}); "
                f"notify também falhou ({nested})",
                file=sys.stderr,
            )
        raise SystemExit(1)
