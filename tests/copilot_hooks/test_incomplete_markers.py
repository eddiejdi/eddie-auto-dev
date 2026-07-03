"""Testes de regressão para o detector de tarefas incompletas (tools/hooks/incomplete_markers.py).

Guardrail calibrado para ALTO SINAL: bloqueia stubs óbvios deixados por IA
(NotImplementedError, "... existing code ...", "implement this", placeholders)
sem falso-positivo em código legítimo (abstract/Protocol, TODO de backlog, testes).

Consumido por:
  - block_incomplete_stop.py (Stop hook — barra encerramento do Claude Code)
  - .githooks/pre-commit Check 8 (rede agnóstica de ferramenta: Copilot, Codex, manual)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "hooks"))

import incomplete_markers as im  # noqa: E402


def _diff(path: str, added_lines: list[str], start: int = 1) -> str:
    """Monta um git diff unificado sintético com `added_lines` adicionadas em `path`."""
    body = "\n".join("+" + ln for ln in added_lines)
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        f"@@ -0,0 +{start},{len(added_lines)} @@\n"
        f"{body}\n"
    )


class TestScanLine(unittest.TestCase):
    """Padrões de linha de alto sinal (todas as linguagens)."""

    def test_high_signal_positivos(self) -> None:
        casos = [
            "# ... existing code ...",
            "// ... resto do código ...",
            "# TODO: implement this later",
            "raise Foo  # implement this",
            "// this is not yet implemented",
            "const x = 'your code here'",
            "throw new Error('not implemented')",
            "    unimplemented!()",
            'panic("TODO: fill later")',
            "    pass  # TODO: implement",
        ]
        for linha in casos:
            with self.subTest(linha=linha):
                self.assertIsNotNone(im.scan_line(linha), f"deveria marcar: {linha!r}")

    def test_baixo_sinal_e_codigo_normal_nao_marcam(self) -> None:
        casos = [
            "# TODO: revisar isso depois",       # backlog legítimo
            "# FIXME quando sobrar tempo",
            "def soma(a, b):",
            "    return a + b",
            "placeholder = request.form['x']",   # 'placeholder' como identificador
            '<input placeholder="Nome">',        # atributo HTML legítimo
            "logger.info('rest of the batch done')",  # 'rest' sem elipse
        ]
        for linha in casos:
            with self.subTest(linha=linha):
                self.assertIsNone(im.scan_line(linha), f"NÃO deveria marcar: {linha!r}")

    def test_supressao_inline(self) -> None:
        self.assertIsNone(im.scan_line("raise NotImplementedError  # stub-ok"))
        self.assertIsNone(im.scan_line("# ... existing code ...  # noqa: incomplete"))


class TestScanPythonAst(unittest.TestCase):
    """Análise AST: distingue stub real de abstração legítima."""

    def test_stub_concreto_marca(self) -> None:
        src = "def f():\n    raise NotImplementedError\n"
        self.assertTrue(im.scan_python_source(src, "m.py"))

    def test_corpo_ellipsis_marca(self) -> None:
        src = "def f():\n    ...\n"
        self.assertTrue(im.scan_python_source(src, "m.py"))

    def test_abstractmethod_nao_marca(self) -> None:
        src = (
            "import abc\n"
            "class B(abc.ABC):\n"
            "    @abc.abstractmethod\n"
            "    def f(self):\n"
            "        ...\n"
        )
        self.assertEqual(im.scan_python_source(src, "m.py"), [])

    def test_metodo_em_protocol_nao_marca(self) -> None:
        src = (
            "from typing import Protocol\n"
            "class P(Protocol):\n"
            "    def f(self) -> int:\n"
            "        ...\n"
        )
        self.assertEqual(im.scan_python_source(src, "m.py"), [])

    def test_pass_puro_nao_marca(self) -> None:
        # `pass` sozinho é ruidoso demais (handlers vazios legítimos) → não marca via AST.
        src = "def f():\n    pass\n"
        self.assertEqual(im.scan_python_source(src, "m.py"), [])

    def test_syntax_error_marca(self) -> None:
        src = "def f(:\n    return 1\n"
        achados = im.scan_python_source(src, "m.py")
        self.assertTrue(achados)
        self.assertIn("SyntaxError", achados[0][1])

    def test_pyi_ignorado(self) -> None:
        src = "def f() -> int: ...\n"
        self.assertEqual(im.scan_python_source(src, "stubs.pyi"), [])


class TestFindIncompleteDiff(unittest.TestCase):
    """Integração: cruza marcadores com as linhas ADICIONADAS do diff."""

    def test_baseline_so_linhas_adicionadas(self) -> None:
        # Marcador presente apenas em linha de CONTEXTO (não adicionada) → não dispara.
        diff = (
            "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n"
            "@@ -1,3 +1,3 @@\n"
            " # ... existing code ...\n"   # contexto (pré-existente)
            "-old = 1\n"
            "+new = 1\n"
        )
        self.assertEqual(im.find_incomplete(diff, lambda p: None), [])

    def test_marcador_em_linha_adicionada_dispara(self) -> None:
        diff = _diff("web/api.ts", ["function f() {", "  // ... existing code ...", "}"])
        achados = im.find_incomplete(diff, lambda p: None)
        self.assertEqual(len(achados), 1)
        self.assertEqual(achados[0].path, "web/api.ts")

    def test_allowlist_testes_ignorado(self) -> None:
        diff = _diff("tests/test_x.py", ["def test_x():", "    raise NotImplementedError"])
        self.assertEqual(im.find_incomplete(diff, lambda p: None), [])

    def test_docs_markdown_ignorado(self) -> None:
        # .md não é código: "..." é legítimo em exemplos de documentação.
        diff = _diff("README.md", ["Exemplo:", "    # ... existing code ..."])
        self.assertEqual(im.find_incomplete(diff, lambda p: None), [])

    def test_ast_so_reporta_stub_em_linha_adicionada(self) -> None:
        # Arquivo completo tem 2 funções-stub, mas só a segunda foi adicionada no diff.
        source = (
            "def antiga():\n"
            "    raise NotImplementedError\n"   # linha 2 (pré-existente)
            "def nova():\n"
            "    raise NotImplementedError\n"   # linha 4 (adicionada)
        )
        diff = _diff("svc/m.py", ["def nova():", "    raise NotImplementedError"], start=3)
        achados = im.find_incomplete(diff, lambda p: source)
        linhas = {f.line for f in achados}
        self.assertIn(4, linhas)
        self.assertNotIn(2, linhas)

    def test_supressao_stub_ok_em_py(self) -> None:
        source = "def f():\n    raise NotImplementedError  # stub-ok\n"
        diff = _diff("svc/m.py", ["def f():", "    raise NotImplementedError  # stub-ok"])
        self.assertEqual(im.find_incomplete(diff, lambda p: source), [])


class TestParseAddedLines(unittest.TestCase):
    def test_parse_basico(self) -> None:
        diff = _diff("a.py", ["linha1", "linha2"], start=5)
        added = im.parse_added_lines(diff)
        self.assertEqual(added["a.py"], {5: "linha1", 6: "linha2"})

    def test_dev_null_ignora_arquivo_removido(self) -> None:
        diff = (
            "diff --git a/x.py b/x.py\n--- a/x.py\n+++ /dev/null\n"
            "@@ -1,1 +0,0 @@\n-x = 1\n"
        )
        self.assertEqual(im.parse_added_lines(diff), {})


if __name__ == "__main__":
    unittest.main()
