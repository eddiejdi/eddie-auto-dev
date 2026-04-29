from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

CUSTOMIZATION_SEGMENTS = [
    ".github/instructions/",
    ".github/prompts/",
    ".github/agents/",
    ".github/skills/",
]

EDIT_TOOL_HINTS = ["edit", "create", "file", "write", "replace", "patch"]


def _load_input() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    return json.loads(raw) if raw else {}


def _payload_get(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Busca variantes de chaves usadas por Copilot/Codex."""
    for key in keys:
        if key in payload:
            return payload[key]
    return default


def _is_edit_like_tool(tool_name: str) -> bool:
    lowered = tool_name.lower()
    return any(token in lowered for token in EDIT_TOOL_HINTS)


def _collect_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(_collect_strings(item))
        return result
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(_collect_strings(item))
        return result
    return []


def _touches_customization(payload: dict[str, Any]) -> bool:
    tool_input = _payload_get(payload, "tool_input", "toolInput", "input", default={})
    strings = _collect_strings(tool_input)
    return any(segment in text.replace('\\', '/') for text in strings for segment in CUSTOMIZATION_SEGMENTS)


def main() -> int:
    payload = _load_input()
    tool_name = str(_payload_get(payload, "tool_name", "toolName", "tool", default=""))
    cwd = Path(str(_payload_get(payload, "cwd", "working_directory", "workingDirectory", default="."))).resolve()
    lint_script = cwd / ".github" / "hooks" / "lint-frontmatter.py"

    if not _is_edit_like_tool(tool_name) or not _touches_customization(payload) or not lint_script.exists():
        print(json.dumps({"continue": True}))
        return 0

    result = subprocess.run(
        [sys.executable, str(lint_script)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        output = (result.stdout or result.stderr).strip()
        print(
            json.dumps(
                {
                    "decision": "block",
                    "reason": "Customization validation failed after file edit",
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": output[:2000],
                    },
                }
            )
        )
        return 0

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": "Customization files validated successfully by lint-frontmatter.py",
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
