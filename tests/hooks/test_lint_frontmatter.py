from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


def _load_module():
    """Carrega dinamicamente o modulo de lint para testes unitarios."""
    module_path = Path(__file__).resolve().parents[2] / ".github" / "hooks" / "lint-frontmatter.py"
    spec = importlib.util.spec_from_file_location("lint_frontmatter", module_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestLintFrontmatter(unittest.TestCase):
    """Suite para validar regras essenciais do lint de frontmatter."""

    def test_valid_instruction_has_no_issues(self) -> None:
        """Deve aceitar frontmatter valido com description e applyTo especifico."""
        mod = _load_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "example.instructions.md"
            file_path.write_text(
                "---\n"
                "description: 'Use when: editing Python files'\n"
                "applyTo: '**/*.py'\n"
                "---\n"
                "# body\n",
                encoding="utf-8",
            )

            issues = mod.validate_file(file_path)

        self.assertEqual(issues, [])

    def test_missing_frontmatter_is_reported(self) -> None:
        """Deve reportar ausencia de frontmatter para artefatos suportados."""
        mod = _load_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "sample.agent.md"
            file_path.write_text("# body only\n", encoding="utf-8")

            issues = mod.validate_file(file_path)

        self.assertEqual(len(issues), 1)
        self.assertIn("missing or malformed frontmatter block", issues[0].message)

    def test_missing_description_is_reported(self) -> None:
        """Deve exigir description para arquivos .prompt.md."""
        mod = _load_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "sample.prompt.md"
            file_path.write_text("---\napplyTo: '**/*.py'\n---\ncontent\n", encoding="utf-8")

            issues = mod.validate_file(file_path)

        self.assertTrue(any("missing required field: description" in issue.message for issue in issues))

    def test_apply_to_too_broad_is_reported(self) -> None:
        """Deve sinalizar applyTo muito amplo como risco de governanca."""
        mod = _load_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "sample.instructions.md"
            file_path.write_text(
                "---\n"
                "description: 'Use when: anything'\n"
                "applyTo: '**'\n"
                "---\n"
                "content\n",
                encoding="utf-8",
            )

            issues = mod.validate_file(file_path)

        self.assertTrue(any("applyTo is too broad" in issue.message for issue in issues))


if __name__ == "__main__":
    unittest.main()
