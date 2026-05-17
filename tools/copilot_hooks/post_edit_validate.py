from __future__ import annotations

import json
import re
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

# Padrões de arquivos de hook — qualquer edição nesses arquivos dispara notificação ao wiki agent
HOOK_FILE_PATTERNS = [
    r"hooks\.json$",
    r"tools/copilot_hooks/[^/]+\.py$",
    r"\.github/hooks/[^/]+\.py$",
]


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


def _extract_touched_files(payload: dict[str, Any]) -> list[str]:
    """Extrai todos os caminhos de arquivo tocados pela tool."""
    tool_input = _payload_get(payload, "tool_input", "toolInput", "input", default={})
    paths: list[str] = []
    if isinstance(tool_input, dict):
        for key in ("filePath", "file_path", "path", "target", "uri"):
            val = tool_input.get(key, "")
            if isinstance(val, str) and val:
                paths.append(val)
        for item in tool_input.get("replacements", []):
            if isinstance(item, dict):
                val = item.get("filePath", "")
                if isinstance(val, str) and val:
                    paths.append(val)
    return paths


def _is_hook_file(file_paths: list[str]) -> list[str]:
    """Retorna os arquivos que correspondem a arquivos de hook."""
    matched = []
    for p in file_paths:
        normalized = p.replace("\\", "/")
        if any(re.search(pattern, normalized) for pattern in HOOK_FILE_PATTERNS):
            matched.append(p)
    return matched


def _notify_wiki_agent(hook_files: list[str], cwd: Path) -> None:
    """Envia notificação ao agent wiki sobre alteração em arquivos de hook."""
    files_list = "\n".join(f"  - {f}" for f in hook_files)
    message = (
        f"Hook files updated:\n{files_list}\n\n"
        "Update the wiki page 'Infraestrutura/Copilot Hooks' with the current state of the hook files. "
        "Read each modified file and document: purpose, trigger conditions, actions taken (deny/ask/allow), "
        "and any new patterns added."
    )

    bus_script = cwd / "tools" / "agent_ipc.py"
    if not bus_script.exists():
        return

    try:
        subprocess.run(
            [
                sys.executable,
                str(bus_script),
                "publish",
                "--agent", "wiki_rpa4all",
                "--task-type", "wiki_update",
                "--message", message,
                "--priority", "low",
            ],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception:
        pass  # Falha silenciosa — notificação wiki nunca deve bloquear o fluxo


def _touches_customization(payload: dict[str, Any]) -> bool:
    tool_input = _payload_get(payload, "tool_input", "toolInput", "input", default={})
    strings = _collect_strings(tool_input)
    return any(segment in text.replace('\\', '/') for text in strings for segment in CUSTOMIZATION_SEGMENTS)


def main() -> int:
    payload = _load_input()
    tool_name = str(_payload_get(payload, "tool_name", "toolName", "tool", default=""))
    cwd = Path(str(_payload_get(payload, "cwd", "working_directory", "workingDirectory", default="."))).resolve()
    lint_script = cwd / ".github" / "hooks" / "lint-frontmatter.py"

    # --- Notificação wiki para arquivos de hook ---
    if _is_edit_like_tool(tool_name):
        touched_files = _extract_touched_files(payload)
        hook_files_touched = _is_hook_file(touched_files)
        if hook_files_touched:
            _notify_wiki_agent(hook_files_touched, cwd)

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
