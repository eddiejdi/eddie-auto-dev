from __future__ import annotations

import json
import re
import sys
from typing import Any

DANGEROUS_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+checkout\s+--\b",
    r"\bdd\s+if=",
    r"\bmkfs(\.|\s)",
    r"\bdrop\s+table\b",
]

CAUTION_PATTERNS = [
    r"\bsystemctl\s+restart\s+(ssh|sshd|docker|networking|ufw|systemd-resolved)\b",
    r"\bshutdown\b",
    r"\breboot\b",
]


def _load_input() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    return json.loads(raw) if raw else {}


def _matches_any(patterns: list[str], text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def _extract_command_blob(payload: dict[str, Any]) -> str:
    tool_input = payload.get("tool_input", {})
    if isinstance(tool_input, str):
        return tool_input
    return json.dumps(tool_input, ensure_ascii=False)


def _is_command_like_tool(tool_name: str) -> bool:
    lowered = tool_name.lower()
    return any(token in lowered for token in ["terminal", "execute", "command", "run"])


def main() -> int:
    payload = _load_input()
    tool_name = str(payload.get("tool_name", ""))
    command_blob = _extract_command_blob(payload)

    if not _is_command_like_tool(tool_name):
        print(json.dumps({"continue": True}))
        return 0

    if _matches_any(DANGEROUS_PATTERNS, command_blob):
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "Dangerous command blocked by workspace guardrails",
                        "additionalContext": "The requested command matches a destructive pattern forbidden by repository policy.",
                    }
                }
            )
        )
        return 0

    if _matches_any(CAUTION_PATTERNS, command_blob):
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "ask",
                        "permissionDecisionReason": "Critical service operation requires explicit approval",
                        "additionalContext": "This command affects a critical service and should be confirmed before execution.",
                    }
                }
            )
        )
        return 0

    print(json.dumps({"continue": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
