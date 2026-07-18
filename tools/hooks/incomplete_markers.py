#!/usr/bin/env python3
"""Detector de tarefas incompletas deixadas por ferramentas de IA (Copilot, Claude Code, Codex).

Motor compartilhado por duas camadas de guardrail:
  - Stop hook (block_incomplete_stop.py): barra o encerramento da sessão do Claude Code
    enquanto o working tree tiver marcadores de trabalho incompleto.
  - git pre-commit (.githooks/pre-commit): rejeita o commit com stubs nas linhas adicionadas.

Princípios de design (calibrado para ALTO SINAL — baixo falso-positivo):
  - Baseline por git diff: só considera as LINHAS ADICIONADAS. Marcadores pré-existentes
    no repositório nunca disparam — apenas o que a sessão/commit introduziu.
  - Alto sinal apenas: NotImplementedError, "implement this", elipses "... existing code ...",
    stubs óbvios. TODO/FIXME genérico NÃO bloqueia (é backlog legítimo).
  - Análise AST para Python: distingue stub real de método abstrato/Protocol legítimo.
  - Allowlist: arquivos .pyi, testes de hook e o próprio detector são ignorados.
  - Escape inline: uma linha com `# stub-ok` ou `# noqa: incomplete` é ignorada.
  - Erro interno do detector: emite INCIDENTE (stderr + incident_notify) e exit 1.

Uso como CLI (modo pre-commit):
    python3 tools/hooks/incomplete_markers.py --staged
    → exit 1 e lista de achados se houver incompletude nas linhas staged; exit 0 caso contrário.
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, Iterable

# ---------------------------------------------------------------------------
# Supressão inline — permite stub intencional sem acionar o guardrail
# ---------------------------------------------------------------------------
SUPPRESS_INLINE = re.compile(r"#\s*(?:stub-ok|noqa:\s*incomplete)\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Extensões consideradas "código" (config incluída — elipse de agente quebra YAML/JSON).
# Docs (.md/.rst/.txt) são deliberadamente EXCLUÍDAS: "..." é legítimo em exemplos.
# ---------------------------------------------------------------------------
CODE_EXTENSIONS: tuple[str, ...] = (
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".kt", ".kts",
    ".rb", ".php", ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".sh", ".bash",
    ".swift", ".scala", ".lua", ".sql", ".vue", ".svelte",
    ".yml", ".yaml", ".json", ".toml", ".ini", ".cfg", ".conf", ".env",
)

# ---------------------------------------------------------------------------
# Allowlist de arquivos — nunca escaneados (contêm os padrões como dados/teste).
# ---------------------------------------------------------------------------
ALLOWLIST_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\.pyi$"),                                  # stubs de tipo: `...` é legítimo
    re.compile(r"(^|/)tools/hooks/incomplete_markers\.py$"),
    re.compile(r"(^|/)tools/hooks/block_incomplete_stop\.py$"),
    re.compile(r"(^|/)tests?/"),                            # suíte de testes referencia os padrões
    re.compile(r"test_.*\.py$"),
    re.compile(r"_test\.(py|js|ts|go)$"),
    re.compile(r"(^|/)\.githooks/"),                        # o próprio hook shell
)

# ---------------------------------------------------------------------------
# Padrões de ALTO SINAL por linha (todas as linguagens). Cada um é praticamente
# sempre um stub deixado por IA — não um artefato legítimo.
# ---------------------------------------------------------------------------
HIGH_SIGNAL_LINE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # O "destruidor de arquivo": elipse elíptica típica de edição preguiçosa de IA.
    (re.compile(r"(?:#|//|/\*|<!--|--|;)\s*\.{2,}\s*"
                r"(?:existing|rest\b|resto\b|restante|remaining|unchanged|permanece|"
                r"mant[eé]m|same\b|previous|snip|omitted|etc\b|c[oó]digo)",
                re.IGNORECASE),
     "elipse de código omitido ('... existing code ...') — cole o conteúdo real, não um resumo"),
    (re.compile(r"\.{3,}\s*(?:existing|rest of|resto do|remaining|restante)\s+"
                r"(?:code|c[oó]digo|lines|linhas|logic|l[oó]gica)",
                re.IGNORECASE),
     "elipse de código omitido — o trecho real precisa estar presente"),
    # Pedido explícito de implementação futura.
    (re.compile(r"\b(?:TODO|FIXME|HACK|XXX)\b[:\s_-]*\bimplement", re.IGNORECASE),
     "TODO/FIXME de implementação pendente"),
    (re.compile(r"\bimplement\s+(?:this|me|here|later|it)\b", re.IGNORECASE),
     "'implement this/here/later' — implementação adiada"),
    (re.compile(r"\b(?:not\s+(?:yet\s+)?implemented|to\s+be\s+implemented|unimplemented)\b",
                re.IGNORECASE),
     "'not implemented / to be implemented' — funcionalidade ausente"),
    # Placeholders de código.
    (re.compile(r"\byour[\s_]+code[\s_]+here\b", re.IGNORECASE),
     "placeholder 'your code here'"),
    (re.compile(r"\bcode\s+goes\s+here\b", re.IGNORECASE),
     "placeholder 'code goes here'"),
    (re.compile(r"\b(?:add|insert|put|write)\s+(?:your\s+)?"
                r"(?:code|implementation|impl|logic|l[oó]gica)\s+here\b", re.IGNORECASE),
     "placeholder 'add implementation here'"),
    (re.compile(r"\bfill\s+in\s+(?:the\s+)?(?:implementation|logic|details|code|blanks)\b",
                re.IGNORECASE),
     "placeholder 'fill in the implementation'"),
    (re.compile(r"(?:#|//)\s*placeholder\b", re.IGNORECASE),
     "comentário 'placeholder'"),
    (re.compile(r"\bplaceholder\s+(?:implementation|logic|for\s+now|until)\b", re.IGNORECASE),
     "placeholder de implementação"),
    # pass/return com comentário de stub.
    (re.compile(r"\bpass\s*#\s*(?:TODO|FIXME|stub|implement|placeholder|for\s+now)",
                re.IGNORECASE),
     "'pass' usado como stub"),
    # JS/TS.
    (re.compile(r"throw\s+new\s+Error\(\s*['\"`]\s*"
                r"(?:not\s+implemented|unimplemented|TODO|implement)", re.IGNORECASE),
     "throw new Error('not implemented')"),
    # Rust.
    (re.compile(r"\b(?:unimplemented|todo)!\s*\("),
     "macro Rust unimplemented!()/todo!()"),
    # Go.
    (re.compile(r"panic\(\s*[\"`]\s*(?:TODO|not\s+implemented|implement)", re.IGNORECASE),
     "panic(\"TODO / not implemented\")"),
)


@dataclass(frozen=True)
class Finding:
    """Um marcador de incompletude localizado."""
    path: str
    line: int
    reason: str
    snippet: str

    def format(self) -> str:
        snip = self.snippet.strip()
        if len(snip) > 100:
            snip = snip[:97] + "..."
        return f"  {self.path}:{self.line} — {self.reason}\n      → {snip}"


def is_allowlisted(path: str) -> bool:
    norm = path.replace("\\", "/")
    return any(p.search(norm) for p in ALLOWLIST_PATTERNS)


def is_code_file(path: str) -> bool:
    norm = path.replace("\\", "/").lower()
    return norm.endswith(CODE_EXTENSIONS)


def scan_line(line: str) -> str | None:
    """Retorna a razão do primeiro padrão de alto sinal encontrado na linha, ou None."""
    if SUPPRESS_INLINE.search(line):
        return None
    for pattern, reason in HIGH_SIGNAL_LINE_PATTERNS:
        if pattern.search(line):
            return reason
    return None


# ---------------------------------------------------------------------------
# Análise AST de Python — distingue stub real de abstração legítima.
# ---------------------------------------------------------------------------
_ABSTRACT_DECORATORS = {
    "abstractmethod", "abstractproperty",
    "abstractclassmethod", "abstractstaticmethod", "overload",
}
_ABSTRACT_BASES = {"Protocol", "ABC"}


def _decorator_name(node: ast.expr) -> str:
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _is_abstract_fn(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(_decorator_name(d) in _ABSTRACT_DECORATORS for d in fn.decorator_list)


def _is_abstract_class(cls: ast.ClassDef) -> bool:
    for base in cls.bases:
        if _decorator_name(base) in _ABSTRACT_BASES:
            return True
    for kw in cls.keywords:
        if kw.arg == "metaclass" and _decorator_name(kw.value) == "ABCMeta":
            return True
    return False


def _stub_finding(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[int, str] | None:
    """Se o corpo da função for apenas um stub, retorna (lineno_do_stub, razão)."""
    body = list(fn.body)
    # Ignora docstring inicial.
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(getattr(body[0], "value", None), ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]
    if len(body) != 1:
        return None
    stmt = body[0]
    # Corpo == `...` (Ellipsis) → stub não implementado (pass puro é ignorado: ruidoso).
    if (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)
            and stmt.value.value is Ellipsis):
        return stmt.lineno, "função com corpo `...` (stub não implementado)"
    # Corpo == raise NotImplementedError.
    if isinstance(stmt, ast.Raise) and stmt.exc is not None:
        if _decorator_name(stmt.exc) in {"NotImplementedError", "NotImplemented"}:
            return stmt.lineno, "função levanta NotImplementedError (não implementada)"
    return None


def scan_python_source(source: str, path: str) -> list[tuple[int, str]]:
    """Escaneia fonte Python via AST. Retorna [(lineno, razão)].

    Um SyntaxError significa arquivo que não compila → sinal forte de código incompleto.
    Stubs em métodos abstratos / classes Protocol/ABC são ignorados (legítimos).
    """
    if path.replace("\\", "/").lower().endswith(".pyi"):
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [(exc.lineno or 1, f"arquivo Python não compila (SyntaxError: {exc.msg})")]

    findings: list[tuple[int, str]] = []

    def visit(node: ast.AST, class_is_abstract: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, _is_abstract_class(child))
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not class_is_abstract and not _is_abstract_fn(child):
                    stub = _stub_finding(child)
                    if stub:
                        findings.append(stub)
                visit(child, False)  # defs aninhadas não são métodos da classe abstrata
            else:
                visit(child, class_is_abstract)

    visit(tree, False)
    return findings


# ---------------------------------------------------------------------------
# Parser de git diff unificado — extrai as linhas ADICIONADAS por arquivo.
# ---------------------------------------------------------------------------
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def parse_added_lines(diff_text: str) -> dict[str, dict[int, str]]:
    """Retorna {path: {lineno_novo: conteúdo}} para todas as linhas adicionadas ('+')."""
    added: dict[str, dict[int, str]] = {}
    current: str | None = None
    new_lineno = 0
    for raw in diff_text.splitlines():
        if raw.startswith("+++ "):
            target = raw[4:].strip()
            if target == "/dev/null":
                current = None
            else:
                current = target[2:] if target.startswith(("a/", "b/")) else target
                added.setdefault(current, {})
            continue
        if raw.startswith("--- "):
            continue
        m = _HUNK_RE.match(raw)
        if m:
            new_lineno = int(m.group(1))
            continue
        if current is None:
            continue
        if raw.startswith("+"):
            added[current][new_lineno] = raw[1:]
            new_lineno += 1
        elif raw.startswith("-"):
            pass  # linha removida não avança o contador do arquivo novo
        elif raw.startswith("\\"):
            pass  # "\ No newline at end of file"
        else:  # contexto
            new_lineno += 1
    return added


def find_incomplete(
    diff_text: str,
    file_reader: Callable[[str], str | None],
) -> list[Finding]:
    """Núcleo: cruza marcadores com as linhas adicionadas no diff.

    file_reader(path) devolve o conteúdo completo do arquivo (versão staged ou working
    tree, conforme o chamador) para a análise AST de Python — ou None se indisponível.
    """
    added = parse_added_lines(diff_text)
    findings: list[Finding] = []

    for path, lines in added.items():
        if is_allowlisted(path) or not is_code_file(path):
            continue

        # 1. Regex de alto sinal sobre cada linha adicionada.
        for lineno, content in lines.items():
            reason = scan_line(content)
            if reason:
                findings.append(Finding(path, lineno, reason, content))

        # 2. AST para Python: só reporta stubs cuja linha foi adicionada nesta mudança.
        if path.lower().endswith(".py"):
            source = file_reader(path)
            if source is None:
                continue
            for lineno, reason in scan_python_source(source, path):
                # SyntaxError (lineno pode não estar no diff) sempre reporta se o arquivo
                # foi tocado; stubs só se a linha do stub foi adicionada.
                if "SyntaxError" in reason or lineno in lines:
                    # Respeita supressão inline na própria linha do stub, se legível.
                    stub_line = lines.get(lineno, "")
                    if stub_line and SUPPRESS_INLINE.search(stub_line):
                        continue
                    findings.append(Finding(path, lineno, reason, stub_line or "<stub>"))

    findings.sort(key=lambda f: (f.path, f.line))
    return findings


# ---------------------------------------------------------------------------
# Helpers de git para os chamadores.
# ---------------------------------------------------------------------------
def _git(args: list[str]) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], text=True, stderr=subprocess.DEVNULL
        )
    except Exception as exc:
        print(f"[incomplete_markers] git {' '.join(args)} falhou: {exc}", file=sys.stderr)
        return ""


def staged_diff() -> str:
    return _git(["diff", "--cached", "--unified=0"])


def working_tree_diff() -> str:
    """Tudo que ainda não está commitado (staged + unstaged) em relação a HEAD."""
    return _git(["diff", "HEAD", "--unified=0"])


def read_staged_file(path: str) -> str | None:
    out = _git(["show", f":{path}"])
    return out or None


def read_worktree_file(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError as exc:
        print(f"[incomplete_markers] leitura {path} falhou: {exc}", file=sys.stderr)
        return None


def _cli_staged() -> int:
    """Modo pre-commit: escaneia o diff staged.

    Códigos de saída: 0 = limpo, 2 = incompletude detectada (bloquear commit),
    1 = erro interno do detector (incidente obrigatório; pre-commit notifica).
    """
    findings = find_incomplete(staged_diff(), read_staged_file)
    if not findings:
        return 0
    print("❌ BLOQUEADO: tarefa incompleta detectada nas linhas staged:")
    print()
    for f in findings:
        print(f.format())
    print()
    print("  Complete a implementação antes de commitar. Se o stub for intencional:")
    print("    • adicione `# stub-ok` na linha, ou")
    print("    • defina ALLOW_INCOMPLETE=1, ou")
    print("    • use git commit --no-verify (não recomendado).")
    return 2


def main(argv: Iterable[str]) -> int:
    args = list(argv)
    if "--staged" in args:
        return _cli_staged()
    # Sem flag: também opera no modo staged (padrão do pre-commit).
    return _cli_staged()


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except Exception as exc:
        # Bug do detector: NÃO silencioso — comunica incidente.
        # Exit 1 (não 0): pre-commit trata como incidente (warn + notify).
        print(
            f"[incomplete_markers] INCIDENTE: detector falhou ({exc})",
            file=sys.stderr,
        )
        try:
            from tools.hooks.incident_notify import emit_incident

            emit_incident(
                "incomplete_markers",
                f"detector falhou: {exc}",
                severity="warn",
                details=repr(exc),
            )
        except Exception as nested:
            print(
                f"[incomplete_markers] notify também falhou: {nested}",
                file=sys.stderr,
            )
        raise SystemExit(1)
