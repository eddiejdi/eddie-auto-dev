#!/usr/bin/env python3
"""Testes unitários para validator_universal.py e sync_codex_from_copilot.py"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from validator_universal import (
    validate_customization,
    _validate_yaml_frontmatter,
    _validate_json_schema,
)
from sync_codex_from_copilot import (
    _extract_yaml_field,
    _extract_yaml_list_field,
    sync_codex_from_copilot,
)


class TestValidatorUniversal(unittest.TestCase):
    """Testes para validador agnóstico."""

    def test_validate_yaml_with_description(self) -> None:
        """YAML com description válido passa."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write('---\ndescription: "Use when: testing"\n---\n# Content')
            f.flush()
            path = Path(f.name)

        try:
            result = validate_customization(path, "yaml")
            self.assertTrue(result.is_valid)
            self.assertEqual(len(result.errors), 0)
        finally:
            path.unlink()

    def test_validate_yaml_without_description(self) -> None:
        """YAML sem description falha."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write("---\napplyTo: '**.py'\n---\n# Content")
            f.flush()
            path = Path(f.name)

        try:
            result = validate_customization(path, "yaml")
            self.assertFalse(result.is_valid)
            self.assertTrue(any("description" in e for e in result.errors))
        finally:
            path.unlink()

    def test_validate_yaml_missing_frontmatter(self) -> None:
        """YAML sem frontmatter delimitador falha."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write("# No frontmatter\n")
            f.flush()
            path = Path(f.name)

        try:
            result = validate_customization(path, "yaml")
            self.assertFalse(result.is_valid)
            self.assertTrue(any("frontmatter" in e for e in result.errors))
        finally:
            path.unlink()

    def test_validate_json_with_agents(self) -> None:
        """JSON com agents válidos passa."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            config = {
                "agents": [
                    {
                        "id": "test-agent",
                        "description": "Use when: testing",
                    }
                ]
            }
            json.dump(config, f)
            f.flush()
            path = Path(f.name)

        try:
            result = validate_customization(path, "json")
            self.assertTrue(result.is_valid)
        finally:
            path.unlink()

    def test_validate_json_agent_missing_description(self) -> None:
        """JSON com agent sem description falha."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            config = {"agents": [{"id": "test-agent"}]}
            json.dump(config, f)
            f.flush()
            path = Path(f.name)

        try:
            result = validate_customization(path, "json")
            self.assertFalse(result.is_valid)
            self.assertTrue(any("description" in e for e in result.errors))
        finally:
            path.unlink()

    def test_validate_json_invalid_json(self) -> None:
        """JSON malformado falha."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("{invalid json")
            f.flush()
            path = Path(f.name)

        try:
            result = validate_customization(path, "json")
            self.assertFalse(result.is_valid)
            self.assertTrue(any("JSON" in e for e in result.errors))
        finally:
            path.unlink()

    def test_auto_detect_format_yaml(self) -> None:
        """Auto-detecta YAML por extensão."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".prompt.md", delete=False
        ) as f:
            f.write('---\ndescription: "Use when: testing"\n---\n')
            f.flush()
            path = Path(f.name)

        try:
            result = validate_customization(path)
            self.assertEqual(result.format, "yaml")
        finally:
            path.unlink()

    def test_auto_detect_format_json(self) -> None:
        """Auto-detecta JSON por extensão."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({"agents": []}, f)
            f.flush()
            path = Path(f.name)

        try:
            result = validate_customization(path)
            self.assertEqual(result.format, "json")
        finally:
            path.unlink()


class TestSyncCodexFromCopilot(unittest.TestCase):
    """Testes para sync de Copilot → Codex."""

    def test_extract_yaml_field(self) -> None:
        """Extrai campo YAML simples."""
        yaml = 'description: "Use when: testing API"'
        result = _extract_yaml_field(yaml, "description")
        self.assertEqual(result, "Use when: testing API")

    def test_extract_yaml_field_case_insensitive(self) -> None:
        """Extrai field case-insensitivo."""
        yaml = "Description: Test"
        result = _extract_yaml_field(yaml, "description")
        self.assertEqual(result, "Test")

    def test_extract_yaml_field_not_found(self) -> None:
        """Retorna None se field não existe."""
        yaml = 'description: "Test"'
        result = _extract_yaml_field(yaml, "nonexistent")
        self.assertIsNone(result)

    def test_extract_yaml_list(self) -> None:
        """Extrai lista YAML."""
        yaml = 'tools: [read, edit, execute]'
        result = _extract_yaml_list_field(yaml, "tools")
        self.assertEqual(result, ["read", "edit", "execute"])

    def test_extract_yaml_list_with_quotes(self) -> None:
        """Extrai lista com valores quoted."""
        yaml = 'tools: ["read", "edit"]'
        result = _extract_yaml_list_field(yaml, "tools")
        self.assertEqual(result, ["read", "edit"])

    def test_extract_yaml_list_not_found(self) -> None:
        """Retorna None se lista não existe."""
        yaml = 'description: "Test"'
        result = _extract_yaml_list_field(yaml, "tools")
        self.assertIsNone(result)

    def test_sync_creates_config(self) -> None:
        """Sync cria config dict com estrutura correta."""
        config = sync_codex_from_copilot(".github")
        
        self.assertIn("version", config)
        self.assertIn("metadata", config)
        self.assertIn("agents", config)
        self.assertIn("prompts", config)
        
        # Deve ter pelo menos os agentes/prompts criados
        self.assertGreater(len(config["agents"]), 0)
        self.assertGreater(len(config["prompts"]), 0)

    def test_sync_agents_have_required_fields(self) -> None:
        """Agentes sincronizados têm campos obrigatórios."""
        config = sync_codex_from_copilot(".github")
        
        for agent in config.get("agents", []):
            self.assertIn("id", agent)
            self.assertIn("description", agent)
            self.assertIn("sourceFile", agent)
            self.assertIn("type", agent)

    def test_sync_prompts_have_required_fields(self) -> None:
        """Prompts sincronizados têm campos obrigatórios."""
        config = sync_codex_from_copilot(".github")
        
        for prompt in config.get("prompts", []):
            self.assertIn("id", prompt)
            self.assertIn("description", prompt)
            self.assertIn("sourceFile", prompt)
            self.assertIn("type", prompt)


if __name__ == "__main__":
    unittest.main()
