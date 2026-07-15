#!/usr/bin/env python3
"""Testes para o gate de taxonomia de variáveis (tools/hooks/variable_registry_validate.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.hooks import variable_registry_validate as vrv


CATALOG = {
    "WIKI_API": "services",
    "OLLAMA_HOST": "infrastructure",
    "TRADING_API_TOKEN": "authentication",
}


class TestExtractCandidates:
    def test_python_os_getenv(self):
        blob = 'x = os.getenv("SOME_NEW_VAR")'
        assert "SOME_NEW_VAR" in vrv.extract_candidates(blob)

    def test_python_os_environ_bracket(self):
        blob = 'x = os.environ["ANOTHER_VAR"]'
        assert "ANOTHER_VAR" in vrv.extract_candidates(blob)

    def test_node_process_env(self):
        blob = "const x = process.env.NODE_VAR;"
        assert "NODE_VAR" in vrv.extract_candidates(blob)

    def test_systemd_environment_line(self):
        blob = 'Environment="SYSTEMD_VAR=value"'
        assert "SYSTEMD_VAR" in vrv.extract_candidates(blob)

    def test_env_file_requires_env_path(self):
        blob = "PLAIN_KEY=value\n"
        assert vrv.extract_candidates(blob, "some/file.py") == set()
        assert "PLAIN_KEY" in vrv.extract_candidates(blob, ".env")
        assert "PLAIN_KEY" in vrv.extract_candidates(blob, "config/service.env.example")


class TestClassify:
    def test_exact_match_is_ok(self):
        status, _ = vrv.classify("WIKI_API", CATALOG)
        assert status == "ok"

    def test_separator_variant_is_duplicate(self):
        status, msg = vrv.classify("WIKIAPI", CATALOG)
        assert status == "duplicate"
        assert "WIKI_API" in msg

    def test_fuzzy_typo_is_duplicate(self):
        status, msg = vrv.classify("OLLAMA_HSOT", CATALOG)
        assert status == "duplicate"
        assert "OLLAMA_HOST" in msg

    def test_lowercase_gets_lint(self):
        status, msg = vrv.classify("some_new_var", CATALOG)
        assert status == "lint"
        assert "SOME_NEW_VAR" in msg

    def test_genuinely_new_name(self):
        status, _ = vrv.classify("COMPLETELY_UNRELATED_NAME", CATALOG)
        assert status == "new"


class TestEvaluate:
    def test_skips_ok_entries(self):
        blob = 'x = os.getenv("WIKI_API")'
        assert vrv.evaluate(blob) == [] or all(
            name != "WIKI_API" for name, _, _ in vrv.evaluate(blob)
        )
