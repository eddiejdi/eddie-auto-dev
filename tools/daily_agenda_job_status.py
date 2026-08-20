#!/usr/bin/env python3
"""Status + log ao vivo do job da agenda diária (painel e broadcast).

Qualquer processo (painel /api/run, systemd, Telegram regenerate) grava o mesmo
``panel_job.json`` + ``panel_job.log``. Com ``DAILY_AGENDA_PANEL_URL`` definido,
também envia heartbeats/log para o painel remoto (ex.: workstation → :8093).
"""
from __future__ import annotations

import json
import logging
import os
import socket
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import request

from daily_agenda_config import DEFAULT_ARTIFACTS_DIR, DEFAULT_JOB_PATH

logger = logging.getLogger(__name__)

JOB_LOG_JSON_TAIL = int(os.environ.get("DAILY_AGENDA_JOB_LOG_JSON_TAIL", "24000"))
DEFAULT_FLUSH_SECONDS = float(os.environ.get("DAILY_AGENDA_JOB_LOG_FLUSH_SECONDS", "0.75"))
DEFAULT_PANEL_URL = os.environ.get("DAILY_AGENDA_PANEL_URL", "").strip().rstrip("/")
DEFAULT_PANEL_KEY = os.environ.get("PANEL_API_KEY", "").strip()


def job_log_path(artifacts_dir: Path | None = None) -> Path:
    base = Path(artifacts_dir) if artifacts_dir else DEFAULT_ARTIFACTS_DIR
    env = os.environ.get("DAILY_AGENDA_JOB_LOG", "").strip()
    if env:
        return Path(env)
    return base / "panel_job.log"


def job_state_path(artifacts_dir: Path | None = None) -> Path:
    if artifacts_dir is None:
        return DEFAULT_JOB_PATH
    return Path(artifacts_dir) / "panel_job.json"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _host_name() -> str:
    return socket.gethostname()


class PanelJobReporter:
    """Grava status/log local e opcionalmente empurra para o painel HTTP."""

    def __init__(
        self,
        *,
        artifacts_dir: Path | None = None,
        source: str = "broadcast",
        panel_url: str | None = None,
        panel_api_key: str | None = None,
        flush_seconds: float = DEFAULT_FLUSH_SECONDS,
        log_level: int = logging.INFO,
    ) -> None:
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else DEFAULT_ARTIFACTS_DIR
        self.job_path = job_state_path(self.artifacts_dir)
        self.log_path = job_log_path(self.artifacts_dir)
        self.source = source
        self.host = _host_name()
        self.pid = os.getpid()
        self.panel_url = (panel_url if panel_url is not None else DEFAULT_PANEL_URL).rstrip("/")
        self.panel_api_key = panel_api_key if panel_api_key is not None else DEFAULT_PANEL_KEY
        self.flush_seconds = max(0.2, float(flush_seconds))
        self.log_level = log_level
        self._lock = threading.Lock()
        self._state: dict[str, Any] = {"status": "idle"}
        self._last_flush = 0.0
        self._line_count = 0
        self._handler: logging.Handler | None = None
        self._remote_warned = False

    # ── local I/O ──────────────────────────────────────────────────────────

    def _read_log_tail(self, max_bytes: int = JOB_LOG_JSON_TAIL) -> str:
        if not self.log_path.exists():
            return ""
        try:
            data = self.log_path.read_bytes()
        except OSError:
            return ""
        if len(data) > max_bytes:
            data = data[-max_bytes:]
            nl = data.find(b"\n")
            if nl != -1 and nl + 1 < len(data):
                data = data[nl + 1 :]
        return data.decode("utf-8", errors="replace")

    def _log_size(self) -> int:
        try:
            return self.log_path.stat().st_size if self.log_path.exists() else 0
        except OSError:
            return 0

    def _write_state(self, state: dict[str, Any], *, force_flush: bool = True) -> None:
        state = dict(state)
        state.setdefault("source", self.source)
        state.setdefault("host", self.host)
        state.setdefault("pid", self.pid)
        state["heartbeat_at"] = _now_iso()
        state["log_path"] = str(self.log_path)
        state["log_bytes"] = self._log_size()
        state["log_lines"] = self._line_count
        if force_flush or not state.get("log"):
            state["log"] = self._read_log_tail()
        self.job_path.parent.mkdir(parents=True, exist_ok=True)
        self.job_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self._state = state
        self._last_flush = time.monotonic()
        self._push_remote(state, log_append="")

    def _append_local(self, line: str) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        text = line if line.endswith("\n") else line + "\n"
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(text)
        self._line_count += 1

    def _push_remote(self, state: dict[str, Any], *, log_append: str) -> None:
        if not self.panel_url:
            return
        payload = {
            "status": state.get("status"),
            "phase": state.get("phase"),
            "date": state.get("date"),
            "source": state.get("source", self.source),
            "host": state.get("host", self.host),
            "pid": state.get("pid", self.pid),
            "started_at": state.get("started_at"),
            "finished_at": state.get("finished_at"),
            "error": state.get("error"),
            "returncode": state.get("returncode"),
            "heartbeat_at": state.get("heartbeat_at"),
            "log_lines": state.get("log_lines", self._line_count),
            "log_append": log_append,
            "reset_log": False,
            "external": True,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.panel_api_key:
            headers["X-API-Key"] = self.panel_api_key
        url = f"{self.panel_url}/api/job/report"
        try:
            req = request.Request(url, data=body, headers=headers, method="POST")
            with request.urlopen(req, timeout=5) as resp:
                resp.read(256)
        except Exception as exc:  # noqa: BLE001 — best-effort remote mirror
            if not self._remote_warned:
                logger.warning("Falha ao reportar job ao painel %s: %s", url, exc)
                self._remote_warned = True

    # ── public API ─────────────────────────────────────────────────────────

    def start(
        self,
        *,
        date: str,
        phase: str = "broadcast",
        command: list[str] | str | None = None,
        note: str = "",
        reset_log: bool = True,
    ) -> None:
        with self._lock:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            if reset_log:
                self.log_path.write_text("", encoding="utf-8")
                self._line_count = 0
            started = _now_iso()
            if note:
                self._append_local(f"[{started}] {note}")
            else:
                self._append_local(
                    f"[{started}] Job agenda iniciado source={self.source} "
                    f"host={self.host} pid={self.pid} date={date}"
                )
            if command:
                cmd_s = command if isinstance(command, str) else " ".join(str(c) for c in command)
                self._append_local(f"$ {cmd_s}")
            state = {
                "status": "running",
                "phase": phase,
                "started_at": started,
                "date": date,
                "source": self.source,
                "host": self.host,
                "pid": self.pid,
                "command": command if isinstance(command, list) else ([command] if command else []),
                "external": True,
            }
            # remote reset on start
            if self.panel_url and reset_log:
                self._push_remote_reset(state)
            self._write_state(state)

    def _push_remote_reset(self, state: dict[str, Any]) -> None:
        payload = {
            "status": "running",
            "phase": state.get("phase"),
            "date": state.get("date"),
            "source": self.source,
            "host": self.host,
            "pid": self.pid,
            "started_at": state.get("started_at"),
            "log_append": "",
            "reset_log": True,
            "external": True,
            "heartbeat_at": _now_iso(),
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.panel_api_key:
            headers["X-API-Key"] = self.panel_api_key
        try:
            req = request.Request(
                f"{self.panel_url}/api/job/report",
                data=body,
                headers=headers,
                method="POST",
            )
            with request.urlopen(req, timeout=5) as resp:
                resp.read(256)
        except Exception as exc:  # noqa: BLE001
            if not self._remote_warned:
                logger.warning("Falha ao resetar job remoto no painel: %s", exc)
                self._remote_warned = True

    def append(self, line: str, *, force_flush: bool = False) -> None:
        if line is None:
            return
        text = str(line).rstrip("\n")
        if not text:
            return
        with self._lock:
            self._append_local(text)
            now = time.monotonic()
            should = force_flush or (now - self._last_flush >= self.flush_seconds) or self._line_count <= 3
            if should:
                state = dict(self._state)
                state["status"] = state.get("status") or "running"
                state["log"] = self._read_log_tail()
                state["log_bytes"] = self._log_size()
                state["log_lines"] = self._line_count
                state["heartbeat_at"] = _now_iso()
                self.job_path.parent.mkdir(parents=True, exist_ok=True)
                self.job_path.write_text(
                    json.dumps(state, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                self._state = state
                self._last_flush = now
                self._push_remote(state, log_append=text + "\n")
            else:
                # still push log chunk often enough for live view
                self._push_remote(self._state, log_append=text + "\n")

    def set_phase(self, phase: str, *, note: str = "") -> None:
        with self._lock:
            if note:
                self._append_local(f"[{_now_iso()}] {note}")
            state = dict(self._state)
            state["status"] = "running"
            state["phase"] = phase
            self._write_state(state)

    def finish(
        self,
        *,
        status: str = "done",
        returncode: int | None = None,
        error: str | None = None,
        note: str = "",
        extra: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            msg = note or f"job {status}" + (f" returncode={returncode}" if returncode is not None else "")
            self._append_local(f"[{_now_iso()}] {msg}")
            state = dict(self._state)
            state["status"] = status
            state["finished_at"] = _now_iso()
            if returncode is not None:
                state["returncode"] = returncode
            if error:
                state["error"] = error
            if extra:
                state.update(extra)
            self._write_state(state)

    def attach_logging(self, logger_name: str | None = None, level: int | None = None) -> logging.Handler:
        """Anexa handler que espelha logs no panel_job.log."""
        reporter = self
        lvl = self.log_level if level is None else level

        class _Handler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                try:
                    if record.levelno < lvl:
                        return
                    # evita recursão se o reporter logar
                    if record.name.startswith("daily_agenda_job_status"):
                        return
                    msg = self.format(record)
                    reporter.append(msg)
                except Exception:  # noqa: BLE001
                    self.handleError(record)

        handler = _Handler(level=lvl)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        target = logging.getLogger(logger_name) if logger_name else logging.getLogger()
        target.addHandler(handler)
        self._handler = handler
        return handler

    def detach_logging(self) -> None:
        if self._handler is None:
            return
        logging.getLogger().removeHandler(self._handler)
        self._handler.close()
        self._handler = None


def ingest_job_report(
    payload: dict[str, Any],
    *,
    artifacts_dir: Path | None = None,
    job_path: Path | None = None,
    log_path: Path | None = None,
) -> dict[str, Any]:
    """Aplica um report externo (POST /api/job/report) nos arquivos do painel."""
    artifacts = Path(artifacts_dir) if artifacts_dir else DEFAULT_ARTIFACTS_DIR
    jpath = Path(job_path) if job_path else job_state_path(artifacts)
    lpath = Path(log_path) if log_path else job_log_path(artifacts)
    lpath.parent.mkdir(parents=True, exist_ok=True)
    jpath.parent.mkdir(parents=True, exist_ok=True)

    if payload.get("reset_log"):
        lpath.write_text("", encoding="utf-8")

    log_append = payload.get("log_append") or ""
    if log_append:
        with lpath.open("a", encoding="utf-8") as handle:
            handle.write(log_append if log_append.endswith("\n") else log_append + "\n")

    # merge com estado atual
    current: dict[str, Any] = {}
    if jpath.exists():
        try:
            current = json.loads(jpath.read_text(encoding="utf-8"))
            if not isinstance(current, dict):
                current = {}
        except Exception:  # noqa: BLE001
            current = {}

    state = dict(current)
    for key in (
        "status",
        "phase",
        "date",
        "source",
        "host",
        "pid",
        "started_at",
        "finished_at",
        "error",
        "returncode",
        "log_lines",
    ):
        if key in payload and payload[key] is not None:
            state[key] = payload[key]
    state["external"] = True
    state["heartbeat_at"] = payload.get("heartbeat_at") or _now_iso()
    state["log_path"] = str(lpath)
    try:
        state["log_bytes"] = lpath.stat().st_size if lpath.exists() else 0
    except OSError:
        state["log_bytes"] = 0

    # tail do log no JSON
    try:
        data = lpath.read_bytes() if lpath.exists() else b""
        if len(data) > JOB_LOG_JSON_TAIL:
            data = data[-JOB_LOG_JSON_TAIL:]
            nl = data.find(b"\n")
            if nl != -1 and nl + 1 < len(data):
                data = data[nl + 1 :]
        state["log"] = data.decode("utf-8", errors="replace")
    except OSError:
        state["log"] = state.get("log") or ""

    jpath.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return state
