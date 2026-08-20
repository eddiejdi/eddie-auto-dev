#!/usr/bin/env python3
"""PreToolUse — abre um terminal com tail -F do log do agent.

Simples e visual: toda vez que uma tool web-agent__* (ou matcher de agent)
é chamada, garante UMA janela de terminal com o log em tempo real.

- Não duplica janela se o tailer da sessão ainda estiver vivo
- Usa gnome-terminal (ou x-terminal-emulator) no DISPLAY do usuário
- Fail-open: se não houver DISPLAY/terminal, só registra e segue

Chamado pelo hook JSON com stdin = envelope PreToolUse.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

LOG_CANDIDATES = [
    Path.home() / ".grok" / "logs" / "mcp" / "web-agent.stderr.log",
    Path("/tmp/web-agent.stderr.log"),
]
STATE_DIR = Path.home() / ".grok" / "state" / "agent-log-terminal"

# tools que disparam a janela (além do matcher do hook)
WEB_AGENT_RE = re.compile(
    r"web-agent__|web_agent__|web_run_task|web_fill_form|web_scrape|"
    r"web_ask_human|web_apply|web_analyze",
    re.IGNORECASE,
)


def _load() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    return json.loads(raw) if raw else {}


def _find_log() -> Path | None:
    for p in LOG_CANDIDATES:
        if p.is_file():
            return p
    # cria vazio para o tail -F não falhar de cara
    preferred = LOG_CANDIDATES[0]
    try:
        preferred.parent.mkdir(parents=True, exist_ok=True)
        preferred.touch(exist_ok=True)
        return preferred
    except OSError:
        return None


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _tail_already_running(log_path: Path) -> int | None:
    """Retorna PID de um `tail -F <log>` já ativo, se houver.

    gnome-terminal devolve o PID do launcher (morre logo); o processo estável
    é o `tail -F`. Por isso a dedupe olha o tail, não o launcher.
    """
    try:
        out = subprocess.check_output(["pgrep", "-af", "tail"], text=True, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    needle = str(log_path)
    for line in out.splitlines():
        if "tail" not in line or "-F" not in line:
            continue
        if needle not in line:
            continue
        # ignora o próprio pgrep/grep e este script
        if "open_agent_log_terminal" in line or "pgrep" in line:
            continue
        try:
            return int(line.split(None, 1)[0])
        except ValueError:
            continue
    return None


def _state_path(session_id: str) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", session_id or "nosession")[:80]
    return STATE_DIR / f"{safe}.json"


def _load_state(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(path: Path, data: dict[str, Any]) -> None:
    try:
        path.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def _pick_terminal() -> list[str] | None:
    # prefer gnome-terminal on this workstation
    if subprocess.call(["which", "gnome-terminal"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
        return ["gnome-terminal"]
    if subprocess.call(["which", "x-terminal-emulator"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
        return ["x-terminal-emulator"]
    if subprocess.call(["which", "xterm"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
        return ["xterm"]
    return None


def _open_terminal(log_path: Path, title: str) -> int | None:
    """Abre terminal com tail -F; retorna PID do processo lançador ou None."""
    display = os.environ.get("DISPLAY") or ":0"
    env = os.environ.copy()
    env["DISPLAY"] = display
    # herdar DBUS do usuário gráfico quando possível
    if "DBUS_SESSION_BUS_ADDRESS" not in env:
        # tentativa best-effort via runtime dir
        uid = os.getuid()
        bus = Path(f"/run/user/{uid}/bus")
        if bus.exists():
            env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={bus}"

    term = _pick_terminal()
    if not term:
        return None

    # comando dentro do terminal
    inner = (
        f"echo '=== {title} ==='; "
        f"echo 'log: {log_path}'; "
        f"echo 'Ctrl+C fecha só o tail; feche a aba quando quiser.'; "
        f"echo; "
        f"tail -n 50 -F '{log_path}'"
    )

    if term[0] == "gnome-terminal":
        cmd = [
            "gnome-terminal",
            "--title", title,
            "--",
            "bash", "-lc", inner,
        ]
    elif term[0] == "xterm":
        cmd = ["xterm", "-T", title, "-e", "bash", "-lc", inner]
    else:
        # x-terminal-emulator: tenta -e
        cmd = [term[0], "-T", title, "-e", "bash", "-lc", inner]

    try:
        # start_new_session: desacopla do hook (hook tem timeout curto)
        proc = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return proc.pid
    except Exception:
        return None


def _should_open(tool_name: str) -> bool:
    if not tool_name:
        return True  # matcher do hook já filtrou
    return bool(WEB_AGENT_RE.search(tool_name))


def main() -> int:
    payload = _load()
    tool_name = str(payload.get("toolName") or payload.get("tool_name") or "")
    session_id = str(
        payload.get("sessionId")
        or payload.get("session_id")
        or os.environ.get("GROK_SESSION_ID")
        or "nosession"
    )

    if not _should_open(tool_name):
        print(json.dumps({"continue": True}))
        return 0

    log_path = _find_log()
    if not log_path:
        print(json.dumps({"continue": True, "additionalContext": "web-agent log não encontrado; janela não aberta."}))
        return 0

    state_path = _state_path(session_id)
    existing_tail = _tail_already_running(log_path)
    if existing_tail:
        _save_state(
            state_path,
            {
                "tailPid": existing_tail,
                "log": str(log_path),
                "sessionId": session_id,
                "reusedAt": time.time(),
            },
        )
        print(
            json.dumps(
                {
                    "continue": True,
                    "additionalContext": (
                        f"## Web-agent log\n"
                        f"Terminal já aberto (tail pid={existing_tail}) em `{log_path}`.\n"
                    ),
                },
                ensure_ascii=False,
            )
        )
        return 0

    title = f"web-agent log [{session_id[:8]}]"
    launcher_pid = _open_terminal(log_path, title)
    # espera o tail subir (gnome-terminal é assíncrono)
    tail_pid = None
    for _ in range(20):
        time.sleep(0.15)
        tail_pid = _tail_already_running(log_path)
        if tail_pid:
            break

    if launcher_pid or tail_pid:
        _save_state(
            state_path,
            {
                "launcherPid": launcher_pid,
                "tailPid": tail_pid,
                "log": str(log_path),
                "sessionId": session_id,
                "openedAt": time.time(),
                "title": title,
            },
        )
        ctx = (
            f"## Web-agent log — terminal aberto\n"
            f"Janela: **{title}**\n"
            f"Arquivo: `{log_path}`\n"
            f"tail pid: {tail_pid or 'subindo…'} | launcher: {launcher_pid}\n"
        )
    else:
        ctx = (
            f"## Web-agent log — falha ao abrir terminal\n"
            f"Log em `{log_path}`. Abra manualmente:\n"
            f"```bash\ngnome-terminal -- title 'web-agent log' -- bash -lc \"tail -n 50 -F '{log_path}'\"\n```\n"
        )

    print(json.dumps({"continue": True, "additionalContext": ctx}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
