#!/usr/bin/env python3
"""Hook global — não pare a atividade por bug/ajuste não-bloqueante.

Encontrou bug, melhoria ou ajuste no meio da tarefa?
- Se **não for bloqueante**: registre sidequest e designe um worker free
  (DEV: MiMo → DeepSeek → fleet PASS; PROD: só fleet PASS). Continue a atividade.
- Se **for bloqueante**: trate agora (pode parar a atividade principal).

Eventos: SessionStart, UserPromptSubmit, SubagentStart (contexto),
Stop / SubagentStop (barra derail sem dispatch).
CLI: ``dispatch --kind bug --title ... --body ...``
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

_HOOKS_DIR = Path(__file__).resolve().parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from free_worker_picker import WorkerPick, pick_worker
from runtime_env import resolve_runtime_env

SIDEQUEST_ROOT = Path.home() / ".grok/state/sidequests"
MAX_STOP_BLOCKS = 2

DERAIL_RE = re.compile(
    r"("
    r"vou\s+parar\s+(para|pra)\s+(corrigir|consertar|resolver|ajustar)"
    r"|antes\s+de\s+continuar\s+(preciso|vou)\s+(corrigir|consertar|ajustar)"
    r"|interrompendo\s+(a\s+)?(atividade|tarefa)"
    r"|pausando\s+(a\s+)?(atividade|tarefa)\s+(para|pra)"
    r"|primeiro\s+(vou|preciso)\s+(corrigir|consertar)\s+(esse|este|o)\s+(bug|erro|problema)"
    r"|switching\s+to\s+fix"
    r"|let\s+me\s+stop\s+and\s+fix"
    r"|stop(ping)?\s+(the\s+)?(main\s+)?task\s+to\s+fix"
    r")",
    re.IGNORECASE,
)

DISPATCHED_RE = re.compile(
    r"(sidequest|spawn_subagent|traycer_create_agent|deleg(ad|uei)|designei"
    r"|park(ed|ei)|encaminh(ei|ado)\s+ao\s+worker)",
    re.IGNORECASE,
)

BLOCKING_RE = re.compile(
    r"(bloqueante|blocking\s+bug|n[aã]o\s+(consigo|posso)\s+continuar"
    r"|imposs[ií]vel\s+continuar|blocker\b|atividade\s+travada)",
    re.IGNORECASE,
)

INJECT_EVENTS = {
    "session_start",
    "sessionstart",
    "user_prompt_submit",
    "userpromptsubmit",
    "subagent_start",
    "subagentstart",
    "",
}

STOP_EVENTS = {
    "stop",
    "subagent_stop",
    "subagentstop",
    "subagent_end",
    "subagentend",
}


def _load_input() -> dict[str, Any]:
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    raw = raw.strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _event_key(payload: dict[str, Any]) -> str:
    event = str(
        payload.get("hookEventName")
        or payload.get("hook_event_name")
        or os.environ.get("GROK_HOOK_EVENT")
        or ""
    )
    return event.replace("-", "_").lower()


def _session_id(payload: dict[str, Any]) -> str:
    raw = str(payload.get("sessionId") or payload.get("session_id") or "default")
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in raw)[:64] or "default"


def _cwd(payload: dict[str, Any]) -> str | None:
    cwd = payload.get("cwd") or payload.get("working_directory") or payload.get("workingDirectory")
    return str(cwd) if cwd else None


def _counter_path(session: str) -> Path:
    return Path(f"/tmp/sidequest-stop-{session}.count")


def _read_count(path: Path) -> int:
    try:
        return int(path.read_text(encoding="utf-8").strip() or "0")
    except (OSError, ValueError):
        return 0


def _write_count(path: Path, value: int) -> None:
    try:
        path.write_text(str(value), encoding="utf-8")
    except OSError:
        pass


def _last_message(payload: dict[str, Any]) -> str:
    return str(
        payload.get("lastAssistantMessage")
        or payload.get("last_assistant_message")
        or ""
    )


def _policy_text(pick: WorkerPick, env_name: str) -> str:
    prod_note = (
        "PROD: não use MiMo/DeepSeek/Qwen; só fleet PASS."
        if env_name == "prod"
        else "DEV: MiMo ou DeepSeek são permitidos se funcionais. Banimento de LLM chinês vale só em PROD."
    )
    return (
        "SIDEQUEST NÃO-BLOQUEANTE (global): se no meio da atividade atual "
        "encontrar bug, ajuste ou melhoria que NÃO bloqueia o objetivo, "
        "NÃO pare a atividade. Registre o item e designe um subagente free "
        f"funcional: {pick.one_liner()}. "
        f"{prod_note} "
        "Handoff: spawn_subagent ou traycer_create_agent com harness/model acima, "
        "permissionMode=full_access, critério de done explícito; continue a tarefa principal. "
        "Só interrompa se for bloqueante (não dá para avançar sem resolver). "
        "CLI: python3 tools/hooks/sidequest_nonblocking.py dispatch "
        "--kind bug|ajuste|melhoria --title '...' --body '...'"
    )


def _inject(payload: dict[str, Any], pick: WorkerPick, env_name: str) -> dict[str, Any]:
    event = str(payload.get("hookEventName") or payload.get("hook_event_name") or "UserPromptSubmit")
    return {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": _policy_text(pick, env_name),
        }
    }


def _allow() -> dict[str, Any]:
    return {"continue": True}


def _handle_stop(payload: dict[str, Any], pick: WorkerPick) -> dict[str, Any]:
    reason = str(payload.get("reason") or "")
    if reason and reason != "end_turn":
        return _allow()

    if str(os.environ.get("ALLOW_SIDEQUEST_STOP", "")).strip().lower() in {"1", "true", "yes"}:
        return _allow()

    if payload.get("stopHookActive") or payload.get("stop_hook_active"):
        return _allow()

    msg = _last_message(payload)
    if not msg:
        return _allow()

    if BLOCKING_RE.search(msg):
        return _allow()

    if not DERAIL_RE.search(msg):
        return _allow()

    if DISPATCHED_RE.search(msg):
        return _allow()

    session = _session_id(payload)
    counter = _counter_path(session)
    count = _read_count(counter)
    if count >= MAX_STOP_BLOCKS:
        try:
            counter.unlink()
        except OSError:
            pass
        return _allow()

    _write_count(counter, count + 1)
    block_reason = (
        "Você está encerrando/interrompendo a atividade principal por um bug/ajuste "
        "não-bloqueante. NÃO pare. "
        f"Designe um subagente free funcional agora ({pick.one_liner()}) "
        "com spawn_subagent ou traycer_create_agent (full_access), "
        "registre o sidequest e CONTINUE a atividade original. "
        "Se for bloqueante de verdade, diga explicitamente que é bloqueante. "
        f"(tentativa {count + 1}/{MAX_STOP_BLOCKS})"
    )
    return {"decision": "block", "reason": block_reason}


def _safe_slug(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", title.strip().lower()).strip("-")
    return (slug[:48] or "item")


def dispatch_sidequest(
    *,
    kind: str,
    title: str,
    body: str,
    blocking: bool = False,
    cwd: str | None = None,
    session: str = "cli",
) -> dict[str, Any]:
    """Grava um sidequest em disco e devolve o worker escolhido."""
    pick = pick_worker(cwd=cwd, use_network=True)
    env_name = resolve_runtime_env(cwd=cwd)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    sid = uuid.uuid4().hex[:8]
    dest_dir = SIDEQUEST_ROOT / session
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{stamp}-{_safe_slug(title)}-{sid}.md"
    record = {
        "kind": kind,
        "title": title,
        "body": body,
        "blocking": blocking,
        "env": env_name,
        "worker": pick.as_dict(),
        "created_at": stamp,
        "session": session,
    }
    front = (
        f"---\nkind: ticket\nstatus: {1 if not blocking else 0}\n"
        f"title: \"[sidequest:{kind}] {title}\"\n---\n\n"
        f"- blocking: {blocking}\n"
        f"- env: {env_name}\n"
        f"- worker: `{pick.harness}` / `{pick.model}`\n\n"
        f"{body.strip()}\n"
    )
    path.write_text(front, encoding="utf-8")
    record["path"] = str(path)
    meta = dest_dir / f"{path.stem}.json"
    meta.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def _cli_dispatch(argv: list[str]) -> int:
    kind = "bug"
    title = ""
    body = ""
    blocking = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--kind" and i + 1 < len(argv):
            kind = argv[i + 1]
            i += 2
            continue
        if arg == "--title" and i + 1 < len(argv):
            title = argv[i + 1]
            i += 2
            continue
        if arg == "--body" and i + 1 < len(argv):
            body = argv[i + 1]
            i += 2
            continue
        if arg in {"--blocking", "--blocking=1"}:
            blocking = True
            i += 1
            continue
        i += 1
    if not title:
        print("uso: sidequest_nonblocking.py dispatch --kind bug|ajuste|melhoria --title T --body B", file=sys.stderr)
        return 2
    record = dispatch_sidequest(kind=kind, title=title, body=body, blocking=blocking)
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "dispatch":
        return _cli_dispatch(args[1:])
    if args and args[0] == "pick":
        pick = pick_worker()
        print(json.dumps(pick.as_dict(), ensure_ascii=False, indent=2))
        return 0

    try:
        payload = _load_input()
        cwd = _cwd(payload)
        env_name = resolve_runtime_env(cwd=cwd)
        pick = pick_worker(cwd=cwd, use_network=False)
        key = _event_key(payload)
        if key in STOP_EVENTS:
            print(json.dumps(_handle_stop(payload, pick), ensure_ascii=False))
            return 0
        if key in INJECT_EVENTS:
            print(json.dumps(_inject(payload, pick, env_name), ensure_ascii=False))
            return 0
        print(json.dumps(_allow()))
        return 0
    except Exception as exc:  # fail-open
        print(f"[sidequest_nonblocking] fail-open ({exc})", file=sys.stderr)
        print(json.dumps(_allow()))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
