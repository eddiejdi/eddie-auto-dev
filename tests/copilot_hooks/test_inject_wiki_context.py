from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "copilot_hooks" / "inject_wiki_context.py"


def _run(payload: dict, mode: str | None = None, env: dict | None = None) -> dict:
    cmd = [sys.executable, str(SCRIPT)]
    if mode:
        cmd.append(f"--mode={mode}")
    full_env = dict(os.environ)
    full_env.setdefault("RPA4ALL_WIKI_URL", "http://127.0.0.1:1/graphql")
    full_env.setdefault("RPA4ALL_WIKI_TTL", "0")
    if env:
        full_env.update(env)
    result = subprocess.run(
        cmd,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=full_env,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


class TestInjectWikiContext(unittest.TestCase):
    def test_session_injects_index(self) -> None:
        out = _run({}, mode="session")
        self.assertTrue(out["continue"])
        ctx = out["additionalContext"]
        self.assertIn("Índice Wiki RPA4All", ctx)
        self.assertIn("trading/guardrails-tuning", ctx)
        self.assertIn("operations/rpa4all-snapshot-monitoring", ctx)

    def test_tool_injects_wiki_for_trading(self) -> None:
        out = _run({
            "hookEventName": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "systemctl restart crypto-agent trading"},
        }, mode="tool")
        self.assertTrue(out["continue"])
        ctx = out["additionalContext"]
        self.assertIn("Wiki RPA4All", ctx)
        self.assertIn("trading-guardrails", ctx)

    def test_tool_injects_wiki_for_monitoring(self) -> None:
        out = _run({
            "hookEventName": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "prometheus grafana alerta monitor snapshot rpa4all"},
        }, mode="tool")
        self.assertTrue(out["continue"])
        ctx = out["additionalContext"]
        self.assertIn("rpa4all-monitoring", ctx)

    def test_tool_skips_unrelated(self) -> None:
        out = _run({
            "hookEventName": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
        }, mode="tool")
        self.assertEqual(out, {"continue": True})

    def test_skips_empty_payload(self) -> None:
        out = _run({}, mode="tool")
        self.assertEqual(out, {"continue": True})

    def test_block_with_incomplete_markers(self) -> None:
        # Cria um repo git temporário com um stub de alto sinal para forçar o modo block.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
            # Copia uma página wiki mínima para o índice ser descoberto.
            (root / "wiki_trading-guardrails.md").write_text(
                "# Trading Guardrails Tuning\n\nRegras de guardrail e rebuy lock.\n", encoding="utf-8"
            )
            subprocess.run(["git", "add", "-A"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "init"], cwd=root, check=True)
            # Trabalho incompleto (stub) no working tree.
            (root / "trading_agent.py").write_text(
                "def get_guardrail_sell_verdict():\n    ...\n", encoding="utf-8"
            )
            # Precisa estar no índice do git: `git diff HEAD` não enxerga untracked.
            subprocess.run(["git", "add", "trading_agent.py"], cwd=root, check=True)

            prev = os.environ.get("CLAUDE_PROJECT_DIR")
            os.environ["CLAUDE_PROJECT_DIR"] = str(root)
            try:
                out = _run({"cwd": str(root), "session_id": "s1"}, mode="block")
            finally:
                if prev is None:
                    os.environ.pop("CLAUDE_PROJECT_DIR", None)
                else:
                    os.environ["CLAUDE_PROJECT_DIR"] = prev
            self.assertTrue(out["continue"])
            ctx = out.get("additionalContext", "")
            self.assertIn("Wiki RPA4All", ctx)
            self.assertIn("trading", ctx)

    def test_block_no_markers_returns_continue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
            subprocess.run(["git", "commit", "--allow-empty", "-qm", "init"], cwd=root, check=True)

            prev = os.environ.get("CLAUDE_PROJECT_DIR")
            os.environ["CLAUDE_PROJECT_DIR"] = str(root)
            try:
                out = _run({"cwd": str(root), "session_id": "s2"}, mode="block")
            finally:
                if prev is None:
                    os.environ.pop("CLAUDE_PROJECT_DIR", None)
                else:
                    os.environ["CLAUDE_PROJECT_DIR"] = prev
            self.assertEqual(out, {"continue": True})

    def test_mode_off(self) -> None:
        prev = os.environ.get("RPA4ALL_WIKI_MODE")
        os.environ["RPA4ALL_WIKI_MODE"] = "off"
        try:
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--mode=session"],
                input=json.dumps({"cwd": str(Path(__file__).parents[2])}),
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(json.loads(result.stdout), {"continue": True})
        finally:
            if prev is None:
                os.environ.pop("RPA4ALL_WIKI_MODE", None)
            else:
                os.environ["RPA4ALL_WIKI_MODE"] = prev


if __name__ == "__main__":
    unittest.main()