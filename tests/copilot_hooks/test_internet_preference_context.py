from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "copilot_hooks" / "internet_preference_context.py"


def _run(payload: dict) -> dict:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


class TestInternetPreferenceContext(unittest.TestCase):
    def test_triggers_on_minha_internet(self) -> None:
        out = _run({"hookEventName": "UserPromptSubmit", "prompt": "minha internet está instável, verifique"})
        self.assertTrue(out["continue"])
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("RJ45", ctx)
        self.assertIn("GVT-38AA", ctx)
        self.assertIn("TANK", ctx)
        self.assertIn("não preferidos", ctx)

    def test_triggers_on_wifi_and_rj45(self) -> None:
        out = _run({"prompt": "conecte no wifi gvt-38aa e no rj45"})
        self.assertIn("enp0s31f6", out["additionalContext"])

    def test_skips_unrelated_prompt(self) -> None:
        out = _run({"prompt": "refatore o agent de trading BTC"})
        self.assertEqual(out, {"continue": True})
        self.assertNotIn("additionalContext", out)

    def test_skips_empty_payload(self) -> None:
        out = _run({})
        self.assertEqual(out, {"continue": True})

    def test_matches_helper(self) -> None:
        # import local helpers
        sys.path.insert(0, str(SCRIPT.parent))
        import internet_preference_context as mod  # type: ignore

        self.assertTrue(mod.matches_internet_topic("sem internet no notebook"))
        self.assertTrue(mod.matches_internet_topic("packet loss no cabo"))
        self.assertFalse(mod.matches_internet_topic("atualizar dashboard grafana"))


if __name__ == "__main__":
    unittest.main()
