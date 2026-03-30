from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HOOK_DIR = ROOT / ".github" / "hooks"


class TestHookConfigs(unittest.TestCase):
    """Valida integridade minima dos arquivos JSON de hooks."""

    def test_hook_json_files_are_parseable(self) -> None:
        for file_path in [
            HOOK_DIR / "pre-tooluse-guardrails.json",
            HOOK_DIR / "post-edit-validate.json",
        ]:
            with self.subTest(file=file_path.name):
                data = json.loads(file_path.read_text(encoding="utf-8"))
                self.assertIn("hooks", data)

    def test_hook_commands_reference_existing_scripts(self) -> None:
        expected = {
            HOOK_DIR / "pre-tooluse-guardrails.json": ROOT / "tools" / "copilot_hooks" / "pre_tool_guardrails.py",
            HOOK_DIR / "post-edit-validate.json": ROOT / "tools" / "copilot_hooks" / "post_edit_validate.py",
        }
        for config_path, script_path in expected.items():
            with self.subTest(file=config_path.name):
                data = json.loads(config_path.read_text(encoding="utf-8"))
                command_entries = [
                    entry
                    for event_entries in data["hooks"].values()
                    for entry in event_entries
                ]
                self.assertTrue(command_entries)
                self.assertTrue(script_path.exists())
                self.assertTrue(any(script_path.name in (entry.get("command", "") + entry.get("linux", "")) for entry in command_entries))


if __name__ == "__main__":
    unittest.main()
