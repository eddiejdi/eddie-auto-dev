from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "copilot_hooks" / "pre_tool_guardrails.py"


def _run(payload: dict) -> dict:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    return json.loads(result.stdout)


class TestPreToolGuardrails(unittest.TestCase):
    """Valida decisoes do hook de guardrails antes de usar ferramentas."""

    def test_denies_destructive_terminal_command(self) -> None:
        payload = {
            "tool_name": "run_in_terminal",
            "tool_input": {"command": "rm -rf /tmp/demo"},
        }

        output = _run(payload)

        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_asks_for_critical_service_restart(self) -> None:
        payload = {
            "tool_name": "executeCommand",
            "tool_input": {"command": "systemctl restart sshd"},
        }

        output = _run(payload)

        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "ask")

    def test_allows_non_command_tool(self) -> None:
        payload = {
            "tool_name": "editFiles",
            "tool_input": {"files": ["src/app.py"]},
        }

        output = _run(payload)

        self.assertTrue(output["continue"])


if __name__ == "__main__":
    unittest.main()
