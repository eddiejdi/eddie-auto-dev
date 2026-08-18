"""Stop do web-agent só vale na sessão que chamou a tool."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "hooks" / "web_agent_live_log.py"


def _load():
    spec = importlib.util.spec_from_file_location("web_agent_live_log", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["web_agent_live_log"] = mod
    spec.loader.exec_module(mod)
    return mod


wal = _load()


class TestSessionOwnsWebAgent(unittest.TestCase):
    def test_missing_meta_is_not_owner(self) -> None:
        self.assertFalse(wal._session_owns_web_agent(Path("/tmp/does-not-exist-wal.meta.json")))

    def test_fresh_meta_is_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            meta = Path(tmp) / "s.meta.json"
            meta.write_text(json.dumps({"startedAt": time.time()}), encoding="utf-8")
            self.assertTrue(wal._session_owns_web_agent(meta))

    def test_stale_meta_is_not_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            meta = Path(tmp) / "s.meta.json"
            meta.write_text(json.dumps({"startedAt": time.time() - 10_000}), encoding="utf-8")
            self.assertFalse(wal._session_owns_web_agent(meta))


class TestStopGateScopedToSession(unittest.TestCase):
    def _run(self, payload: dict, tmp: Path, *, with_meta: bool) -> dict:
        log = tmp / "web-agent.stderr.log"
        log.write_text(
            "2026-08-17 22:08:26,569 agent.orchestrator INFO Passo 40: click\n",
            encoding="utf-8",
        )
        state = tmp / "state"
        state.mkdir()
        if with_meta:
            sid = payload.get("sessionId", "s1")
            (state / f"{sid}.meta.json").write_text(
                json.dumps({"startedAt": time.time(), "sessionId": sid}),
                encoding="utf-8",
            )
            (state / f"{sid}.cursor").write_text("0", encoding="utf-8")
        env = {
            **os.environ,
            "WEB_AGENT_LIVE_LOG_PATH": str(log),
            "WEB_AGENT_LIVE_LOG_STATE": str(state),
        }
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--mode=stop"],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_stop_allows_unrelated_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = self._run(
                {"hookEventName": "Stop", "reason": "end_turn", "sessionId": "hook-session"},
                Path(tmp),
                with_meta=False,
            )
        self.assertTrue(out.get("continue"))
        self.assertNotEqual(out.get("decision"), "block")

    def test_stop_blocks_owner_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = self._run(
                {"hookEventName": "Stop", "reason": "end_turn", "sessionId": "web-session"},
                Path(tmp),
                with_meta=True,
            )
        self.assertEqual(out.get("decision"), "block")


if __name__ == "__main__":
    unittest.main()
