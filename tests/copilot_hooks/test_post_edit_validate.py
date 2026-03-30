from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "copilot_hooks" / "post_edit_validate.py"
ROOT = Path(__file__).resolve().parents[2]


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


class TestPostEditValidate(unittest.TestCase):
    """Valida o hook de pos-edicao para artefatos de customizacao."""

    def test_skips_non_edit_tool(self) -> None:
        output = _run({"tool_name": "run_in_terminal", "tool_input": {}, "cwd": str(ROOT)})
        self.assertTrue(output["continue"])

    def test_skips_non_customization_edit(self) -> None:
        output = _run(
            {
                "tool_name": "editFiles",
                "tool_input": {"files": ["src/app.py"]},
                "cwd": str(ROOT),
            }
        )
        self.assertTrue(output["continue"])

    def test_validates_customization_edit_and_returns_context(self) -> None:
        output = _run(
            {
                "tool_name": "editFiles",
                "tool_input": {"files": [str(ROOT / ".github" / "prompts" / "generic.prompt.md")]},
                "cwd": str(ROOT),
            }
        )

        self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        self.assertIn("validated successfully", output["hookSpecificOutput"]["additionalContext"])


if __name__ == "__main__":
    unittest.main()
