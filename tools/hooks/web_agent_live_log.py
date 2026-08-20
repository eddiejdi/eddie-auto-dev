#!/usr/bin/env python3
"""PreToolUse / Stop — traz logs do web-agent para o contexto do chat.

Dois modos:

1. PreToolUse em ferramentas `web-agent__*`
   - Marca o início de uma execução
   - Garante um tailer de fundo (estado por sessão)
   - Injeta as últimas linhas filtradas como additionalContext
   - Instrui o agente a manter um `monitor` ativo no log (stream real no chat)

2. PreToolUse em QUALQUER ferramenta (matcher .*)
   - Se o log do web-agent cresceu desde o último cursor da sessão,
     injeta só o delta (linhas novas) — assim, enquanto o agent faz outras
     tools em paralelo, o chat recebe progresso via additionalContext.

3. Stop (opcional, chamado com --mode=stop)
   - Se ainda houver linhas novas e a execução parecer ativa, devolve
     decision=block com o delta (mantém o turno vivo e joga log no chat).

Segredos (API keys, Bearer, cartão) são redatados antes de qualquer output.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

LOG_CANDIDATES = [
    Path(p)
    for p in (
        os.environ.get("WEB_AGENT_LIVE_LOG_PATH"),
        str(Path.home() / ".grok" / "logs" / "mcp" / "web-agent.stderr.log"),
        "/tmp/web-agent.stderr.log",
    )
    if p
]

STATE_DIR = Path(
    os.environ.get("WEB_AGENT_LIVE_LOG_STATE")
    or (Path.home() / ".grok" / "state" / "web-agent-live-log")
)
MAX_INJECT_LINES = 40
MAX_INJECT_CHARS = 4500
ACTIVE_WINDOW_SEC = 900  # 15 min sem mtime = inativo
INTERESTING = re.compile(
    r"(Passo\s+\d+|ERROR|WARNING|INFO|Telegram|web_ask|fill_field|click|"
    r"navigate|STATUS:|API_KEY|BILLING|FAILED|OK|login|signup|Sign Up|"
    r"console\.runpod|billing|OTP|humano|ask_human|screenshot|PAGE)",
    re.IGNORECASE,
)
REDACT_PATTERNS = [
    (re.compile(r"(?i)(api[_-]?key|token|bearer|authorization|password|secret)\s*[:=]\s*\S+"), r"\1=<redacted>"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"), "sk-<redacted>"),
    (re.compile(r"\brp_[A-Za-z0-9_-]{16,}\b"), "rp_<redacted>"),
    (re.compile(r"\b(?:\d[ -]*?){13,19}\b"), "<card-redacted>"),
    (re.compile(r"(?i)\bcvv\s*[:=]?\s*\d{3,4}\b"), "cvv=<redacted>"),
]


def _load_input() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    return json.loads(raw) if raw else {}


def _find_log() -> Path | None:
    for p in LOG_CANDIDATES:
        if p.is_file():
            return p
    return None


def _state_paths(session_id: str) -> tuple[Path, Path]:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", session_id or "nosession")[:80]
    return STATE_DIR / f"{safe}.cursor", STATE_DIR / f"{safe}.meta.json"


def _read_cursor(cursor_path: Path) -> int:
    try:
        return int(cursor_path.read_text(encoding="utf-8").strip() or "0")
    except Exception:
        return 0


def _write_cursor(cursor_path: Path, pos: int) -> None:
    try:
        cursor_path.write_text(str(pos), encoding="utf-8")
    except Exception:
        pass


def _redact(line: str) -> str:
    out = line
    for pat, rep in REDACT_PATTERNS:
        out = pat.sub(rep, out)
    return out


def _interesting(line: str) -> bool:
    if not line.strip():
        return False
    if INTERESTING.search(line):
        return True
    # fallback: keep non-debug short agent lines
    if " DEBUG " in line or "debug:" in line.lower():
        return False
    return "agent" in line.lower()


def _read_delta(log_path: Path, from_pos: int, *, consume: bool, cursor_path: Path) -> tuple[list[str], int]:
    """Lê bytes novos desde from_pos (modo binário — tell() após next() quebra em text IO)."""
    try:
        size = log_path.stat().st_size
    except OSError:
        return [], from_pos

    # log rotated / truncated
    if from_pos > size:
        from_pos = 0

    lines: list[str] = []
    new_pos = from_pos
    try:
        with log_path.open("rb") as fh:
            fh.seek(from_pos)
            data = fh.read()
            new_pos = fh.tell()
    except OSError:
        return [], from_pos

    if data:
        # só descarta o 1º fragmento se o cursor NÃO estava no início de uma linha
        at_line_start = from_pos == 0
        if from_pos > 0:
            try:
                with log_path.open("rb") as fh:
                    fh.seek(from_pos - 1)
                    at_line_start = fh.read(1) == b"\n"
            except OSError:
                at_line_start = False
        text = data.decode("utf-8", errors="replace")
        if not at_line_start:
            nl = text.find("\n")
            if nl >= 0:
                text = text[nl + 1 :]
            else:
                text = ""
        for raw in text.splitlines():
            line = _redact(raw.rstrip("\n"))
            if _interesting(line):
                lines.append(line)

    if consume:
        _write_cursor(cursor_path, new_pos)
    if len(lines) > MAX_INJECT_LINES:
        lines = lines[-MAX_INJECT_LINES:]
    return lines, new_pos


def _log_active(log_path: Path) -> bool:
    try:
        age = time.time() - log_path.stat().st_mtime
        return age <= ACTIVE_WINDOW_SEC
    except OSError:
        return False


def _session_owns_web_agent(meta_path: Path, now: float | None = None) -> bool:
    """True só se ESTA sessão chamou web-agent recentemente (meta do modo pre).

    O log MCP é compartilhado: sem este gate, o Stop de qualquer chat
    bloqueia quando *outro* agent escreve no mesmo arquivo.
    """
    if not meta_path.is_file():
        return False
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return False
    if not isinstance(meta, dict):
        return False
    started = float(meta.get("startedAt") or 0)
    if started <= 0:
        return False
    stamp = time.time() if now is None else now
    return (stamp - started) <= ACTIVE_WINDOW_SEC


def _format_block(title: str, lines: list[str], log_path: Path) -> str:
    body = "\n".join(lines)
    if len(body) > MAX_INJECT_CHARS:
        body = "…\n" + body[-MAX_INJECT_CHARS:]
    monitor_cmd = (
        f'tail -n 0 -F "{log_path}" | '
        r"""grep --line-buffered -E 'Passo |ERROR|WARNING|INFO|Telegram|ask_human|STATUS:|BILLING|FAILED|navigate|fill_field|click'"""
    )
    return (
        f"## {title}\n"
        f"Fonte: `{log_path}`\n\n"
        f"```\n{body}\n```\n\n"
        f"**Stream em tempo real no chat:** use a tool `monitor` com:\n"
        f"`command`: `{monitor_cmd}`\n"
        f"`description`: `web-agent live log`\n"
        f"`persistent`: true\n"
        "Inicie o monitor **em paralelo** com `web-agent__*` (mesma rodada de tools) "
        "para cada linha aparecer como notificação no chat. Redação de secrets já no hook.\n"
    )


def _is_web_agent_tool(tool_name: str) -> bool:
    n = (tool_name or "").lower()
    return (
        n.startswith("web-agent__")
        or n.startswith("web_agent__")
        or "web-agent" in n
        or n.endswith("web_run_task")
        or n.endswith("web_fill_form")
        or n.endswith("web_scrape")
        or n.endswith("web_ask_human")
    )


def _mode_from_argv() -> str:
    # --mode=pre|stop|delta  (default pre, but auto-detects tool)
    for a in sys.argv[1:]:
        if a.startswith("--mode="):
            return a.split("=", 1)[1].strip().lower()
    if "--stop" in sys.argv[1:]:
        return "stop"
    return "auto"


def main() -> int:
    payload = _load_input()
    mode = _mode_from_argv()
    tool_name = str(payload.get("toolName") or payload.get("tool_name") or "")
    session_id = str(payload.get("sessionId") or payload.get("session_id") or os.environ.get("GROK_SESSION_ID") or "nosession")
    event = str(payload.get("hookEventName") or os.environ.get("GROK_HOOK_EVENT") or "").lower()

    log_path = _find_log()
    if not log_path:
        print(json.dumps({"continue": True}))
        return 0

    cursor_path, meta_path = _state_paths(session_id)
    cursor = _read_cursor(cursor_path)
    active = _log_active(log_path)

    if mode == "auto":
        if event in ("stop", "subagent_stop") or payload.get("reason") == "end_turn":
            mode = "stop"
        elif _is_web_agent_tool(tool_name):
            mode = "pre"
        else:
            mode = "delta"

    # --- Stop gate: keep turn alive briefly if new log lines arrived ---
    if mode == "stop":
        reason = str(payload.get("reason") or "")
        if reason and reason != "end_turn":
            print(json.dumps({"continue": True}))
            return 0
        if payload.get("stopHookActive") is True:
            # already continued once — allow stop to avoid loop
            print(json.dumps({"continue": True}))
            return 0
        if not _session_owns_web_agent(meta_path):
            print(json.dumps({"continue": True}))
            return 0
        lines, _ = _read_delta(log_path, cursor, consume=True, cursor_path=cursor_path)
        if lines and active:
            snippet = "\n".join(lines[-25:])
            if len(snippet) > 2500:
                snippet = snippet[-2500:]
            print(
                json.dumps(
                    {
                        "decision": "block",
                        "reason": (
                            "Web-agent ainda produziu log recente. "
                            "Revise o progresso abaixo e só finalize se a tarefa acabou.\n\n"
                            f"{snippet}"
                        ),
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        print(json.dumps({"continue": True}))
        return 0

    # --- PreToolUse on web-agent tool ---
    if mode == "pre":
        # Snapshot: últimas linhas interessantes do arquivo (contexto da run)
        # + cursor no EOF para que o modo delta só mostre linhas NOVAS depois.
        try:
            size = log_path.stat().st_size
            start = max(0, size - 200_000)
        except OSError:
            start = 0
            size = 0

        lines, _ = _read_delta(log_path, start, consume=False, cursor_path=cursor_path)
        if len(lines) > MAX_INJECT_LINES:
            lines = lines[-MAX_INJECT_LINES:]
        # A partir de agora, delta = só o que crescer após este momento
        _write_cursor(cursor_path, size)

        try:
            meta_path.write_text(
                json.dumps(
                    {
                        "sessionId": session_id,
                        "toolName": tool_name,
                        "startedAt": time.time(),
                        "log": str(log_path),
                        "cursorAtStart": size,
                    }
                ),
                encoding="utf-8",
            )
        except Exception:
            pass

        if not lines:
            ctx = (
                "## Web-agent iniciando\n"
                f"Log: `{log_path}` (ainda sem linhas filtradas).\n\n"
                "Obrigatório para stream no chat: chame **em paralelo** a tool `monitor`:\n"
                f"- command: `\"$CLAUDE_PROJECT_DIR\"/tools/hooks/web_agent_log_monitor.sh` "
                f"(ou path absoluto do repo)\n"
                "- description: `web-agent live log`\n"
                "- persistent: true\n"
            )
        else:
            ctx = _format_block("Web-agent — log (pré-tool / recente)", lines, log_path)

        print(
            json.dumps(
                {
                    "continue": True,
                    "additionalContext": ctx,
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "additionalContext": ctx,
                    },
                },
                ensure_ascii=False,
            )
        )
        return 0

    # --- Delta mode: any other tool while THIS session's web-agent is warm ---
    if mode == "delta":
        if not active or not _session_owns_web_agent(meta_path):
            print(json.dumps({"continue": True}))
            return 0
        lines, _ = _read_delta(log_path, cursor, consume=True, cursor_path=cursor_path)
        if not lines:
            print(json.dumps({"continue": True}))
            return 0
        ctx = _format_block("Web-agent — log em tempo real (delta)", lines, log_path)
        print(
            json.dumps(
                {
                    "continue": True,
                    "additionalContext": ctx,
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "additionalContext": ctx,
                    },
                },
                ensure_ascii=False,
            )
        )
        return 0

    print(json.dumps({"continue": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
