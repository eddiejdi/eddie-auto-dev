"""Testes do hook global de sidequest não-bloqueante."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


HOOKS = Path(__file__).resolve().parents[2] / "tools" / "hooks"


def _load(name: str):
    path = HOOKS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


runtime_env = _load("runtime_env")
picker = _load("free_worker_picker")
sidequest = _load("sidequest_nonblocking")


class TestRuntimeEnv(unittest.TestCase):
    def test_explicit_prod_env_wins(self) -> None:
        self.assertEqual(
            runtime_env.resolve_runtime_env(cwd="/tmp", environ={"RPA4ALL_ENV": "prod"}),
            "prod",
        )

    def test_explicit_dev_env_wins(self) -> None:
        self.assertEqual(
            runtime_env.resolve_runtime_env(
                cwd="/home/homelab/agents_workspace/prod",
                environ={"RPA4ALL_ENV": "dev"},
            ),
            "dev",
        )

    def test_prod_path_without_env(self) -> None:
        self.assertEqual(
            runtime_env.resolve_runtime_env(
                cwd="/home/homelab/agents_workspace/prod/api",
                environ={},
            ),
            "prod",
        )

    def test_default_worktree_is_dev(self) -> None:
        self.assertEqual(
            runtime_env.resolve_runtime_env(
                cwd="/home/edenilson/.traycer/worktrees/eddiejdi__eddie-auto-dev/x",
                environ={},
            ),
            "dev",
        )


class TestFreeWorkerPicker(unittest.TestCase):
    def test_dev_prefers_mimo_when_catalog_lists_it(self) -> None:
        pick = picker.pick_worker(
            cwd="/tmp/dev",
            environ={"RPA4ALL_ENV": "dev"},
            catalog={"xiaomi/mimo-v2.5", "deepseek/deepseek-chat"},
            use_network=False,
        )
        self.assertEqual(pick.family, "mimo")
        self.assertIn("mimo", pick.model)

    def test_dev_falls_to_deepseek_if_mimo_missing(self) -> None:
        pick = picker.pick_worker(
            cwd="/tmp/dev",
            environ={"RPA4ALL_ENV": "dev"},
            catalog={"deepseek/deepseek-v3.2"},
            use_network=False,
        )
        self.assertEqual(pick.family, "deepseek")

    def test_prod_never_picks_chinese_family(self) -> None:
        fleet = (
            "active:\n"
            "  - name: free-north-mini-code\n"
            "    model: openrouter:cohere/north-mini-code:free\n"
            "    status: pass\n"
            "excluded:\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fleet.yaml"
            path.write_text(fleet, encoding="utf-8")
            pick = picker.pick_worker(
                cwd="/home/homelab/agents_workspace/prod",
                environ={"RPA4ALL_ENV": "prod"},
                fleet_path=path,
                catalog={"cohere/north-mini-code:free"},
                use_network=False,
            )
        self.assertNotIn(pick.family, {"mimo", "deepseek"})
        self.assertIn("north-mini", pick.model)


class TestSidequestHook(unittest.TestCase):
    def test_injects_policy_on_prompt(self) -> None:
        payload = {"hookEventName": "UserPromptSubmit", "cwd": "/tmp"}
        out = sidequest._inject(
            payload,
            picker.WorkerPick(
                name="mimo",
                harness="openrouter",
                model="openrouter:xiaomi/mimo-v2.5",
                family="mimo",
                source="test",
                env="dev",
                functional=True,
                reason="t",
            ),
            "dev",
        )
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("SIDEQUEST", ctx)
        self.assertIn("DEV", ctx)

    def test_stop_blocks_derail_without_dispatch(self) -> None:
        pick = picker.WorkerPick(
            "mimo", "openrouter", "openrouter:xiaomi/mimo-v2.5",
            "mimo", "test", "dev", True, "t",
        )
        payload = {
            "hookEventName": "Stop",
            "reason": "end_turn",
            "sessionId": f"test-derail-{os.getpid()}-{id(self)}",
            "lastAssistantMessage": "Vou parar para corrigir esse bug de lint antes.",
        }
        out = sidequest._handle_stop(payload, pick)
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("subagente", out["reason"])

    def test_stop_allows_when_blocking(self) -> None:
        pick = picker.WorkerPick(
            "mimo", "openrouter", "openrouter:xiaomi/mimo-v2.5",
            "mimo", "test", "dev", True, "t",
        )
        payload = {
            "hookEventName": "Stop",
            "reason": "end_turn",
            "lastAssistantMessage": "Isso é bloqueante: não consigo continuar sem esse fix.",
        }
        out = sidequest._handle_stop(payload, pick)
        self.assertTrue(out.get("continue"))

    def test_stop_allows_when_already_dispatched(self) -> None:
        pick = picker.WorkerPick(
            "mimo", "openrouter", "openrouter:xiaomi/mimo-v2.5",
            "mimo", "test", "dev", True, "t",
        )
        payload = {
            "hookEventName": "Stop",
            "reason": "end_turn",
            "lastAssistantMessage": (
                "Vou parar para corrigir o lint. "
                "Designei sidequest via spawn_subagent."
            ),
        }
        out = sidequest._handle_stop(payload, pick)
        self.assertTrue(out.get("continue"))

    def test_dispatch_writes_ticket(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            orig = sidequest.SIDEQUEST_ROOT
            sidequest.SIDEQUEST_ROOT = Path(tmp)
            try:
                record = sidequest.dispatch_sidequest(
                    kind="ajuste",
                    title="typo no hook",
                    body="corrigir docstring",
                    cwd="/tmp",
                    session="pytest",
                )
                self.assertTrue(Path(record["path"]).is_file())
                self.assertEqual(record["kind"], "ajuste")
            finally:
                sidequest.SIDEQUEST_ROOT = orig


class TestHookJsonWiresScript(unittest.TestCase):
    def test_project_hook_json_points_to_script(self) -> None:
        root = Path(__file__).resolve().parents[2]
        data = json.loads((root / ".grok/hooks/sidequest-nonblocking.json").read_text())
        self.assertIn("Stop", data["hooks"])
        blob = json.dumps(data)
        self.assertIn("sidequest_nonblocking.py", blob)


if __name__ == "__main__":
    unittest.main()
