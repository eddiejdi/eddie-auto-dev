# rpa4all-hooks (Pi extension)

Bridge between **Pi coding agent** lifecycle events and the existing Claude Code Python hooks in this monorepo.

## What it does

| Pi event | Python scripts |
|----------|----------------|
| `before_agent_start` | `inject_memory_context.py` + `sidequest_nonblocking.py` + `inject_wiki_context.py --mode=session` |
| `tool_call` | `pre_tool_guardrails.py`, `variable|table|api_registry_validate.py`, `record_stopped.py` |
| `tool_result` | `post_edit_validate.py`, `ai_response_analyzer.py` |
| `agent_settled` | `sidequest_nonblocking.py`, `block_incomplete_stop.py`, `restore_stopped.py`; se bloqueado → `inject_wiki_context.py --mode=block` |

Rules stay in Python (single source of truth). TypeScript only maps payloads and translates:

- `permissionDecision: deny` → `{ block: true }`
- `permissionDecision: ask` → UI confirm (headless → block)
- errors/timeouts → **fail-open** (logged)

## Requirements

- Project trust enabled for this repo (`~/.pi/agent/trust.json` or `/trust` in TUI).
- `python3` on PATH.
- Scripts under `tools/copilot_hooks` and `tools/hooks`.

## Manual tests

```bash
cd /workspace/eddie-auto-dev
export PATH="$HOME/.local/bin:$HOME/.local/node-v22.19.0/bin:$PATH"

# Should block via pre_tool_guardrails
pi -p --provider ollama --model llama3.1:8b --approve \
  "Use the bash tool to run exactly: rm -rf /tmp/pi-hook-test-xyz"

# Should block tape bypass
pi -p --provider ollama --model llama3.1:8b --approve \
  "Use the bash tool to run exactly: ltfsck /dev/sg0"
```

## Limitations vs Claude Code

- Stop hook cannot force Claude-identical re-prompt loops; it notifies on incomplete work.
- Tool names are mapped (`bash`→`Bash`, etc.); exotic custom tools may need payload tweaks in `payload.ts`.
