#!/usr/bin/env python3
"""
Codex Agent MCP Server
Wraps `codex exec` as MCP tools with automatic model selection based on task complexity.

Model routing:
  gpt-5.4-mini  → quick fixes, explain, review, rename, format          (cheap)
  gpt-5.4       → implement feature, write tests, debug, create module  (medium)
  gpt-5.5       → refactor entire codebase, architect, complex migrate  (expensive)

Architecture:
  Claude → MCP call → this server (local) → codex exec --model <auto> → result
                                              ↓ (optional)
                                         homelab bus notification
"""

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

def _find_codex_bin() -> Path:
    """Find the codex binary dynamically — survives VS Code extension updates."""
    import glob
    pattern = str(Path.home() / ".vscode/extensions/openai.chatgpt-*/bin/linux-x86_64/codex")
    candidates = sorted(glob.glob(pattern), reverse=True)
    if candidates:
        return Path(candidates[0])
    return Path.home() / ".vscode/extensions/openai.chatgpt-UNKNOWN/bin/linux-x86_64/codex"

CODEX_BIN = _find_codex_bin()
HOMELAB_BUS_URL = os.environ.get("HOMELAB_URL", "http://192.168.15.2:8503")
DEFAULT_WORKSPACE = os.environ.get("CODEX_WORKSPACE", str(Path.home() / "workspace"))
LOG_DIR = Path("/apps/codex-agent/logs") if Path("/apps/codex-agent").exists() else Path("/tmp")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [codex-mcp] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),
    ],
)
log = logging.getLogger("codex-mcp")

MINI_TRIGGERS = re.compile(
    r"\b(fix typo|add comment|rename|format|explain|what is|list|show|describe|"
    r"simple fix|quick fix|typo|whitespace|lint|docstring|clarify|summarize)\b",
    re.IGNORECASE,
)
PRO_TRIGGERS = re.compile(
    r"\b(implement|create|build|write tests?|add tests?|add feature|develop|generate|"
    r"add function|add class|write module|debug|fix bug|handle error|add unit)\b",
    re.IGNORECASE,
)
MAX_TRIGGERS = re.compile(
    r"\b(refactor entire|migrate|architect|design system|optimize performance|"
    r"rewrite|major refactor|full migration|comprehensive|entire codebase|"
    r"overhaul|restructure)\b",
    re.IGNORECASE,
)


def select_model(prompt: str, hint: str = "auto") -> str:
    if hint and hint != "auto":
        return hint
    words = len(prompt.split())
    # Heavy keywords always win, regardless of length
    if MAX_TRIGGERS.search(prompt) or words > 600:
        return "gpt-5.5"
    # Medium keywords upgrade from mini
    if PRO_TRIGGERS.search(prompt):
        return "gpt-5.4"
    # Explicit cheap keywords or very short prompt → mini
    if MINI_TRIGGERS.search(prompt) or words < 80:
        return "gpt-5.4-mini"
    return "gpt-5.4"


def _parse_jsonl_output(raw: str) -> str:
    """Extract agent messages from codex exec --json JSONL event stream.

    Codex emits events like:
      {"type": "item.completed", "item": {"type": "agent_message", "text": "..."}}
      {"type": "turn.completed", "usage": {...}}
    We collect all agent_message texts in order and return the last one (final answer).
    """
    messages: list[str] = []
    usage_info: str = ""
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        evt_type = evt.get("type", "")
        if evt_type == "item.completed":
            item = evt.get("item", {})
            if item.get("type") == "agent_message":
                text = item.get("text", "")
                if text:
                    messages.append(text)
        elif evt_type == "turn.completed":
            usage = evt.get("usage", {})
            if usage:
                usage_info = (
                    f"[tokens in={usage.get('input_tokens',0)} "
                    f"cached={usage.get('cached_input_tokens',0)} "
                    f"out={usage.get('output_tokens',0)}]"
                )
        elif evt_type == "error":
            messages.append(f"[error] {evt.get('message', str(evt))}")
    if not messages:
        return raw.strip()
    result = messages[-1]  # final agent message is the answer
    if usage_info:
        result = f"{result}\n\n{usage_info}"
    return result


def run_codex(prompt: str, cwd: str, model: str, timeout: int = 300) -> dict[str, Any]:
    cmd = [
        str(CODEX_BIN),
        "exec",
        "--model", model,
        "--sandbox", "workspace-write",
        "--color", "never",
        "--json",
        "-C", cwd,
        prompt,
    ]
    log.info("model=%s cwd=%s prompt_words=%d", model, cwd, len(prompt.split()))
    start = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = time.monotonic() - start
        raw_out = result.stdout.strip()
        output = _parse_jsonl_output(raw_out) if raw_out else ""
        stderr = result.stderr.strip()
        if result.returncode != 0 and not output:
            output = stderr
        return {
            "model": model,
            "elapsed_s": round(elapsed, 1),
            "exit_code": result.returncode,
            "output": output,
            "error": stderr if result.returncode != 0 else None,
        }
    except subprocess.TimeoutExpired:
        return {"model": model, "elapsed_s": timeout, "exit_code": -1, "output": "", "error": "timeout"}
    except FileNotFoundError:
        return {"model": model, "elapsed_s": 0, "exit_code": -1, "output": "", "error": f"codex binary not found: {CODEX_BIN}"}


def post_to_bus(agent: str, event_type: str, payload: dict) -> None:
    try:
        import urllib.request
        body = json.dumps({"agent": agent, "event_type": event_type, "payload": payload}).encode()
        req = urllib.request.Request(
            f"{HOMELAB_BUS_URL}/events",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as exc:
        log.warning("bus notification failed: %s", exc)


TOOLS = [
    {
        "name": "codex_run_task",
        "description": (
            "Run a coding task using the Codex agent. "
            "Automatically selects the cheapest model that can handle the task complexity. "
            "Use this to offload implementation work, code reviews, refactoring, or debugging "
            "without consuming Claude tokens. "
            "model_hint: 'auto' (default), 'gpt-5.4-mini', 'gpt-5.4', or 'gpt-5.5'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Task description for the Codex agent. Be specific about files and expected changes.",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory (absolute path). Defaults to ~/workspace.",
                },
                "model_hint": {
                    "type": "string",
                    "description": "Force a specific model or 'auto' for automatic selection.",
                    "enum": ["auto", "gpt-5.4-mini", "gpt-5.4", "gpt-5.5"],
                    "default": "auto",
                },
                "timeout_s": {
                    "type": "integer",
                    "description": "Max seconds to wait for codex (default 300).",
                    "default": 300,
                },
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "codex_review_code",
        "description": (
            "Run a non-interactive code review using Codex on the current repository. "
            "Always uses gpt-5.4-mini for cost efficiency."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "cwd": {
                    "type": "string",
                    "description": "Repository path to review. Defaults to ~/workspace.",
                },
                "focus": {
                    "type": "string",
                    "description": "Optional: what to focus the review on (security, performance, correctness, etc.).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "codex_model_info",
        "description": "Return available models and current routing heuristic for diagnostics.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
]


def handle_codex_run_task(args: dict) -> dict:
    prompt = args["prompt"]
    cwd = args.get("cwd") or DEFAULT_WORKSPACE
    hint = args.get("model_hint", "auto")
    timeout = int(args.get("timeout_s", 300))

    model = select_model(prompt, hint)
    result = run_codex(prompt, cwd, model, timeout)

    post_to_bus("codex-agent", "task_completed", {
        "model": model,
        "cwd": cwd,
        "exit_code": result["exit_code"],
        "elapsed_s": result["elapsed_s"],
        "prompt_words": len(prompt.split()),
    })

    lines = [f"[codex-agent] model={model} ({result['elapsed_s']}s)"]
    if result.get("error"):
        lines.append(f"ERROR: {result['error']}")
    if result.get("output"):
        lines.append(result["output"])
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


def handle_codex_review_code(args: dict) -> dict:
    cwd = args.get("cwd") or DEFAULT_WORKSPACE
    focus = args.get("focus", "")
    prompt = f"Review this codebase for issues.{' Focus on: ' + focus if focus else ''} Be concise."
    result = run_codex(prompt, cwd, "gpt-5.4-mini")
    text = f"[codex-review] model=gpt-5.4-mini ({result['elapsed_s']}s)\n"
    text += result.get("output") or result.get("error") or "(no output)"
    return {"content": [{"type": "text", "text": text}]}


def handle_codex_model_info(_args: dict) -> dict:
    info = {
        "models": {
            "gpt-5.4-mini": "cheap — quick fixes, explain, format, short prompts (<80 words)",
            "gpt-5.4": "medium — implement features, write tests, debug (80–600 words)",
            "gpt-5.5": "expensive — major refactor, architecture, complex migrations (>600 words or heavy keywords)",
        },
        "codex_binary": str(CODEX_BIN),
        "codex_binary_exists": CODEX_BIN.exists(),
        "default_workspace": DEFAULT_WORKSPACE,
    }
    return {"content": [{"type": "text", "text": json.dumps(info, indent=2)}]}


HANDLERS = {
    "codex_run_task": handle_codex_run_task,
    "codex_review_code": handle_codex_review_code,
    "codex_model_info": handle_codex_model_info,
}


def mcp_response(id_: Any, result: Any) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": id_, "result": result})


def mcp_error(id_: Any, code: int, message: str) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}})


def main() -> None:
    log.info("codex-mcp-server started (binary=%s)", CODEX_BIN)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            print(mcp_error(None, -32700, f"parse error: {e}"), flush=True)
            continue

        id_ = msg.get("id")
        method = msg.get("method", "")
        params = msg.get("params", {})

        if method == "initialize":
            print(mcp_response(id_, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "codex-agent", "version": "1.0.0"},
            }), flush=True)

        elif method == "notifications/initialized":
            pass

        elif method == "tools/list":
            print(mcp_response(id_, {"tools": TOOLS}), flush=True)

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            if tool_name not in HANDLERS:
                print(mcp_error(id_, -32601, f"unknown tool: {tool_name}"), flush=True)
                continue
            try:
                result = HANDLERS[tool_name](arguments)
                print(mcp_response(id_, result), flush=True)
            except Exception as e:
                log.exception("tool %s failed", tool_name)
                print(mcp_error(id_, -32000, str(e)), flush=True)

        elif method == "ping":
            print(mcp_response(id_, {}), flush=True)

        else:
            if id_ is not None:
                print(mcp_error(id_, -32601, f"method not found: {method}"), flush=True)


if __name__ == "__main__":
    main()
