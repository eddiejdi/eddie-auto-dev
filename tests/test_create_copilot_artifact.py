#!/usr/bin/env python3
"""Testes unitários para tools/create_copilot_artifact.py"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from create_copilot_artifact import (
    ArtifactConfig,
    _sanitize_name,
    _generate_frontmatter,
    _get_artifact_path,
)


class TestSanitizeName(unittest.TestCase):
    """Testes para sanitização de nomes."""

    def test_lowercase_conversion(self) -> None:
        """Converte para lowercase."""
        self.assertEqual(_sanitize_name("MySkill"), "myskill")

    def test_spaces_to_hyphens(self) -> None:
        """Substitui espaços por hífens."""
        self.assertEqual(_sanitize_name("My Skill"), "my-skill")

    def test_underscores_to_hyphens(self) -> None:
        """Substitui underscores por hífens."""
        self.assertEqual(_sanitize_name("my_skill"), "my-skill")

    def test_combined(self) -> None:
        """Aplica todas as transformações."""
        self.assertEqual(
            _sanitize_name("My Long Skill_Name"),
            "my-long-skill-name"
        )


class TestGenerateFrontmatter(unittest.TestCase):
    """Testes para geração de frontmatter YAML."""

    def test_skill_frontmatter(self) -> None:
        """Gera frontmatter para skill."""
        config = ArtifactConfig(
            artifact_type="skill",
            name="test-skill",
            description="Use when: testing skills",
        )
        frontmatter = _generate_frontmatter(config)

        self.assertIn("---", frontmatter)
        self.assertIn('description: "Use when: testing skills"', frontmatter)
        self.assertTrue(frontmatter.startswith("---"))
        self.assertTrue(frontmatter.strip().endswith("---"))

    def test_instruction_frontmatter_with_applies_to(self) -> None:
        """Gera frontmatter para instruction com applyTo."""
        config = ArtifactConfig(
            artifact_type="instruction",
            name="api-coding",
            description="API coding standards",
            applies_to="src/api/**.py",
        )
        frontmatter = _generate_frontmatter(config)

        self.assertIn('applyTo: "src/api/**.py"', frontmatter)
        self.assertIn('description: "API coding standards"', frontmatter)

    def test_agent_frontmatter_includes_tools(self) -> None:
        """Gera frontmatter para agent com tools."""
        config = ArtifactConfig(
            artifact_type="agent",
            name="test-agent",
            description="Test agent",
        )
        frontmatter = _generate_frontmatter(config)

        self.assertIn("tools:", frontmatter)


class TestGetArtifactPath(unittest.TestCase):
    """Testes para determinação de paths de artefatos."""

    def test_skill_path(self) -> None:
        """Path para skill é .github/skills/<name>/SKILL.md"""
        config = ArtifactConfig(
            artifact_type="skill",
            name="test-skill",
            description="",
        )
        path = _get_artifact_path(config)

        self.assertTrue(str(path).endswith("skills/test-skill/SKILL.md"))

    def test_agent_path(self) -> None:
        """Path para agent é .github/agents/<name>.agent.md"""
        config = ArtifactConfig(
            artifact_type="agent",
            name="test-agent",
            description="",
        )
        path = _get_artifact_path(config)

        self.assertTrue(str(path).endswith("agents/test-agent.agent.md"))

    def test_prompt_path(self) -> None:
        """Path para prompt é .github/prompts/<name>.prompt.md"""
        config = ArtifactConfig(
            artifact_type="prompt",
            name="test-prompt",
            description="",
        )
        path = _get_artifact_path(config)

        self.assertTrue(str(path).endswith("prompts/test-prompt.prompt.md"))

    def test_instruction_path(self) -> None:
        """Path para instruction é .github/instructions/<name>.instructions.md"""
        config = ArtifactConfig(
            artifact_type="instruction",
            name="test-instruction",
            description="",
        )
        path = _get_artifact_path(config)

        self.assertTrue(str(path).endswith("instructions/test-instruction.instructions.md"))


if __name__ == "__main__":
    unittest.main()
