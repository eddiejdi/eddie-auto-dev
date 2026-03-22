#!/usr/bin/env python3
"""Prometheus exporter + self-healing for RPA4All Nextcloud."""

from __future__ import annotations

import argparse
import collections
import json
import logging
import os
import shlex
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from prometheus_client import Counter, Gauge, start_http_server

    HAS_PROM = True
except ImportError:
    HAS_PROM = False


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [nextcloud-heal] %(message)s",
)
log = logging.getLogger("nextcloud-heal")

DATA_DIR = os.environ.get("NEXTCLOUD_HEAL_DATA_DIR", "/var/lib/eddie/nextcloud-heal")
AUDIT_LOG = os.path.join(DATA_DIR, "nextcloud_heal_audit.jsonl")
AUDIT_MAX_SIZE_MB = int(os.environ.get("NEXTCLOUD_HEAL_AUDIT_MAX_MB", "10"))
DEFAULT_INTERVAL = int(os.environ.get("NEXTCLOUD_HEAL_INTERVAL", "30"))
DEFAULT_MAX_ACTIONS = int(os.environ.get("NEXTCLOUD_HEAL_MAX_ACTIONS", "4"))
DEFAULT_COOLDOWN = int(os.environ.get("NEXTCLOUD_HEAL_COOLDOWN", "120"))


@dataclass
class ProbeDef:
    name: str
    url: str
    method: str = "GET"
    timeout: int = 8
    expected_status: List[int] = field(default_factory=lambda: [200])
    expect_json: bool = False
    probe_type: str = "generic"
    enabled: bool = True


@dataclass
class ContainerDef:
    name: str
    role: str
    restart_command: str
    restart_on_unhealthy: bool = True
    enabled: bool = True


@dataclass
class NextcloudConfig:
    name: str = "nextcloud-rpa4all"
    public_ok_after_local_ok_failures: int = 2
    local_failures_before_restart: int = 2
    container_failures_before_restart: int = 2
    max_actions_per_hour: int = DEFAULT_MAX_ACTIONS
    cooldown_after_action_seconds: int = DEFAULT_COOLDOWN
    edge_restart_command: str = "systemctl restart cloudflared-rpa4all.service"
    app_restart_command: str = "docker restart nextcloud-app"
    probes: List[ProbeDef] = field(default_factory=list)
    containers: List[ContainerDef] = field(default_factory=list)


@dataclass
class ProbeResult:
    up: bool = False
    http_status: int = 0
    response_time: float = 0.0
    detail: str = ""
    last_success: float = 0.0


@dataclass
class ContainerResult:
    running: bool = False
    healthy: bool = False
    detail: str = ""
    last_success: float = 0.0


@dataclass
class ExporterState:
    last_check: float = 0.0
    last_action: str = ""
    last_action_detail: str = ""
    last_action_at: float = 0.0
    hour_window_start: float = 0.0
    actions_this_hour: int = 0
    consecutive_failures: Dict[str, int] = field(default_factory=lambda: collections.defaultdict(int))
    probe_results: Dict[str, ProbeResult] = field(default_factory=dict)
    container_results: Dict[str, ContainerResult] = field(default_factory=dict)


def default_config() -> NextcloudConfig:
    return NextcloudConfig(
        probes=[
            ProbeDef(
                name="public_status",
                url="https://nextcloud.rpa4all.com/status.php",
                method="GET",
                expected_status=[200],
                expect_json=True,
                probe_type="status",
            ),
            ProbeDef(
                name="local_status",
                url="http://127.0.0.1:8880/status.php",
                method="GET",
                expected_status=[200],
                expect_json=True,
                probe_type="status",
            ),
            ProbeDef(
                name="public_login",
                url="https://nextcloud.rpa4all.com/index.php/login/v2",
                method="POST",
                expected_status=[200],
                expect_json=True,
                probe_type="login",
            ),
            ProbeDef(
                name="local_login",
                url="http://127.0.0.1:8880/index.php/login/v2",
                method="POST",
                expected_status=[200],
                expect_json=True,
                probe_type="login",
            ),
        ],
        containers=[
            ContainerDef("nextcloud-app", "app", "docker restart nextcloud-app"),
            ContainerDef("nextcloud-cron", "cron", "docker restart nextcloud-cron"),
            ContainerDef("nextcloud-redis", "redis", "docker restart nextcloud-redis"),
            ContainerDef("nextcloud-db", "db", "docker restart nextcloud-db", restart_on_unhealthy=False),
        ],
    )


def load_config(config_path: Optional[str]) -> NextcloudConfig:
    cfg = default_config()
    if not config_path:
        return cfg

    path = Path(config_path)
    if not path.is_file():
        log.warning("Config %s not found, using defaults", config_path)
        return cfg

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        probes = [ProbeDef(**item) for item in payload.get("probes", [])] or cfg.probes
        containers = [ContainerDef(**item) for item in payload.get("containers", [])] or cfg.containers
        return NextcloudConfig(
            name=payload.get("name", cfg.name),
            public_ok_after_local_ok_failures=payload.get("public_ok_after_local_ok_failures", cfg.public_ok_after_local_ok_failures),
            local_failures_before_restart=payload.get("local_failures_before_restart", cfg.local_failures_before_restart),
            container_failures_before_restart=payload.get("container_failures_before_restart", cfg.container_failures_before_restart),
            max_actions_per_hour=payload.get("max_actions_per_hour", cfg.max_actions_per_hour),
            cooldown_after_action_seconds=payload.get("cooldown_after_action_seconds", cfg.cooldown_after_action_seconds),
            edge_restart_command=payload.get("edge_restart_command", cfg.edge_restart_command),
            app_restart_command=payload.get("app_restart_command", cfg.app_restart_command),
            probes=probes,
            containers=containers,
        )
    except Exception as exc:
        log.warning("Failed to load config %s: %s. Using defaults", config_path, exc)
        return cfg


class NextcloudHealthChecker:
    def __init__(self, config: NextcloudConfig):
        self.config = config
        self.state = ExporterState(
            probe_results={probe.name: ProbeResult() for probe in config.probes},
            container_results={container.name: ContainerResult() for container in config.containers},
        )
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self.metrics = self._create_metrics()

    def _create_metrics(self) -> Dict[str, Any]:
        return {
            "probe_up": Gauge("nextcloud_probe_up", "1 if probe is healthy", ["target", "probe_type"]),
            "probe_http_status": Gauge(
                "nextcloud_probe_http_status_code",
                "HTTP status code returned by Nextcloud probes",
                ["target", "probe_type"],
            ),
            "probe_latency": Gauge(
                "nextcloud_probe_response_time_seconds",
                "Latency in seconds for Nextcloud probes",
                ["target", "probe_type"],
            ),
            "probe_last_success": Gauge(
                "nextcloud_probe_last_success_timestamp",
                "Unix timestamp of the last successful probe",
                ["target", "probe_type"],
            ),
            "container_running": Gauge(
                "nextcloud_container_running",
                "1 if the monitored container is running",
                ["container", "role"],
            ),
            "container_healthy": Gauge(
                "nextcloud_container_healthy",
                "1 if the monitored container is healthy",
                ["container", "role"],
            ),
            "container_last_success": Gauge(
                "nextcloud_container_last_success_timestamp",
                "Unix timestamp of the last healthy container state",
                ["container", "role"],
            ),
            "overall_health": Gauge("nextcloud_overall_health", "Aggregate Nextcloud health"),
            "consecutive_failures": Gauge(
                "nextcloud_consecutive_failures",
                "Consecutive failures by monitored scope",
                ["scope"],
            ),
            "selfheal_actions_total": Counter(
                "nextcloud_selfheal_actions_total",
                "Total self-healing actions",
                ["action"],
            ),
            "restart_total": Counter(
                "nextcloud_restart_total",
                "Total restart actions by component",
                ["component"],
            ),
            "last_check": Gauge("nextcloud_last_check_timestamp", "Unix timestamp of last check"),
        }

    def run_command(self, command: str, timeout: int = 60) -> subprocess.CompletedProcess:
        return subprocess.run(
            shlex.split(command),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    def _parse_json(self, body: bytes) -> Optional[dict[str, Any]]:
        if not body:
            return None
        try:
            return json.loads(body.decode("utf-8", "replace"))
        except Exception:
            return None

    def probe(self, probe: ProbeDef) -> ProbeResult:
        if not probe.enabled:
            return ProbeResult(detail="disabled")

        start = time.monotonic()
        status = 0
        detail = ""
        body = b""
        try:
            data = b"" if probe.method.upper() == "POST" else None
            request = urllib.request.Request(probe.url, data=data, method=probe.method.upper())
            with urllib.request.urlopen(request, timeout=probe.timeout) as response:
                status = response.status
                body = response.read(8192)
        except urllib.error.HTTPError as exc:
            status = exc.code
            body = exc.read(8192) if hasattr(exc, "read") else b""
            detail = str(exc)
        except Exception as exc:
            detail = str(exc)

        latency = time.monotonic() - start
        payload = self._parse_json(body) if probe.expect_json else None
        up = status in probe.expected_status

        if probe.probe_type == "status":
            installed = bool(payload and payload.get("installed"))
            maintenance = bool(payload and payload.get("maintenance"))
            up = up and installed and not maintenance
            if payload:
                detail = f"installed={installed} maintenance={maintenance}"
        elif probe.probe_type == "login":
            has_login = bool(payload and payload.get("login"))
            has_poll = bool(payload and payload.get("poll"))
            up = up and has_login and has_poll
            if payload:
                detail = f"has_login={has_login} has_poll={has_poll}"

        prev = self.state.probe_results[probe.name]
        return ProbeResult(
            up=up,
            http_status=status,
            response_time=latency,
            detail=detail or ("ok" if up else "failed"),
            last_success=time.time() if up else prev.last_success,
        )

    def inspect_container(self, container: ContainerDef) -> ContainerResult:
        if not container.enabled:
            return ContainerResult(detail="disabled")

        result = self.run_command(f"docker inspect {container.name}", timeout=20)
        prev = self.state.container_results[container.name]
        if result.returncode != 0 or not result.stdout.strip():
            return ContainerResult(False, False, result.stderr.strip() or "inspect_failed", prev.last_success)

        try:
            payload = json.loads(result.stdout)[0]
        except Exception as exc:
            return ContainerResult(False, False, f"bad_inspect:{exc}", prev.last_success)

        running = bool(payload.get("State", {}).get("Running"))
        health_status = payload.get("State", {}).get("Health", {}).get("Status")
        healthy = running if not health_status else (running and health_status == "healthy")
        return ContainerResult(
            running=running,
            healthy=healthy,
            detail=health_status or ("running" if running else "stopped"),
            last_success=time.time() if healthy else prev.last_success,
        )

    def _rotate_audit_log(self) -> None:
        path = Path(AUDIT_LOG)
        if not path.exists():
            return
        if path.stat().st_size < AUDIT_MAX_SIZE_MB * 1024 * 1024:
            return
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path.rename(path.with_name(f"{path.name}.{timestamp}"))

    def _audit(self, action: str, success: bool, detail: str) -> None:
        os.makedirs(DATA_DIR, exist_ok=True)
        self._rotate_audit_log()
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "success": success,
            "detail": detail,
        }
        with open(AUDIT_LOG, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")

    def _can_act(self) -> bool:
        now = time.time()
        if now - self.state.hour_window_start > 3600:
            self.state.hour_window_start = now
            self.state.actions_this_hour = 0
        if self.state.actions_this_hour >= self.config.max_actions_per_hour:
            return False
        if now - self.state.last_action_at < self.config.cooldown_after_action_seconds:
            return False
        return True

    def _run_action(self, action: str, command: str, component: str) -> bool:
        if not self._can_act():
            self._audit(action, False, "rate_limited")
            log.warning("Blocked self-heal action due to rate limit/cooldown: %s", action)
            return False

        result = self.run_command(command, timeout=90)
        success = result.returncode == 0
        detail = result.stderr.strip() or result.stdout.strip() or "ok"
        self.state.last_action = action
        self.state.last_action_detail = detail
        self.state.last_action_at = time.time()
        self.state.actions_this_hour += 1
        self.metrics["selfheal_actions_total"].labels(action=action).inc()
        if success:
            self.metrics["restart_total"].labels(component=component).inc()
        self._audit(action, success, detail)
        return success

    def _update_failure_counter(self, scope: str, ok: bool) -> None:
        self.state.consecutive_failures[scope] = 0 if ok else self.state.consecutive_failures[scope] + 1
        self.metrics["consecutive_failures"].labels(scope=scope).set(self.state.consecutive_failures[scope])

    def evaluate_once(self) -> None:
        with self._lock:
            for probe in self.config.probes:
                result = self.probe(probe)
                self.state.probe_results[probe.name] = result
                self.metrics["probe_up"].labels(target=probe.name, probe_type=probe.probe_type).set(1 if result.up else 0)
                self.metrics["probe_http_status"].labels(target=probe.name, probe_type=probe.probe_type).set(result.http_status)
                self.metrics["probe_latency"].labels(target=probe.name, probe_type=probe.probe_type).set(result.response_time)
                self.metrics["probe_last_success"].labels(target=probe.name, probe_type=probe.probe_type).set(result.last_success)

            for container in self.config.containers:
                result = self.inspect_container(container)
                self.state.container_results[container.name] = result
                self.metrics["container_running"].labels(container=container.name, role=container.role).set(1 if result.running else 0)
                self.metrics["container_healthy"].labels(container=container.name, role=container.role).set(1 if result.healthy else 0)
                self.metrics["container_last_success"].labels(container=container.name, role=container.role).set(result.last_success)

            public_ok = self.state.probe_results["public_status"].up
            local_ok = self.state.probe_results["local_status"].up
            app_ok = self.state.container_results["nextcloud-app"].healthy

            self._update_failure_counter("public", public_ok)
            self._update_failure_counter("local", local_ok)
            self._update_failure_counter("app", app_ok)

            for container in self.config.containers:
                self._update_failure_counter(f"container:{container.name}", self.state.container_results[container.name].healthy)

            self.metrics["overall_health"].set(1 if public_ok and local_ok and app_ok else 0)
            self.state.last_check = time.time()
            self.metrics["last_check"].set(self.state.last_check)

            for container in self.config.containers:
                scope = f"container:{container.name}"
                if (
                    container.restart_on_unhealthy
                    and self.state.consecutive_failures[scope] >= self.config.container_failures_before_restart
                    and not self.state.container_results[container.name].healthy
                ):
                    if self._run_action(f"restart_{container.role}", container.restart_command, container.role):
                        self.state.consecutive_failures[scope] = 0
                    return

            if (
                (self.state.consecutive_failures["local"] >= self.config.local_failures_before_restart or
                 self.state.consecutive_failures["app"] >= self.config.container_failures_before_restart)
                and (not local_ok or not app_ok)
            ):
                if self._run_action("restart_app", self.config.app_restart_command, "app"):
                    self.state.consecutive_failures["local"] = 0
                    self.state.consecutive_failures["app"] = 0
                return

            if (
                self.state.consecutive_failures["public"] >= self.config.public_ok_after_local_ok_failures
                and local_ok
                and not public_ok
            ):
                if self._run_action("restart_edge", self.config.edge_restart_command, "edge"):
                    self.state.consecutive_failures["public"] = 0
                return

    def status_snapshot(self) -> Dict[str, Any]:
        return {
            "name": self.config.name,
            "last_check": self.state.last_check,
            "last_action": self.state.last_action,
            "last_action_detail": self.state.last_action_detail,
            "last_action_at": self.state.last_action_at,
            "actions_this_hour": self.state.actions_this_hour,
            "consecutive_failures": dict(self.state.consecutive_failures),
            "probes": {k: vars(v) for k, v in self.state.probe_results.items()},
            "containers": {k: vars(v) for k, v in self.state.container_results.items()},
        }

    def serve_status_api(self, port: int) -> HTTPServer:
        checker = self

        class Handler(BaseHTTPRequestHandler):
            def _send_json(self, payload: Dict[str, Any], status_code: int = 200) -> None:
                body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/status":
                    self._send_json(checker.status_snapshot())
                    return
                if self.path == "/health":
                    self._send_json({"status": "ok", "ts": time.time()})
                    return
                self._send_json({"error": "not_found"}, 404)

            def log_message(self, _format: str, *args: Any) -> None:
                return

        server = HTTPServer(("0.0.0.0", port), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server

    def run_forever(self, interval: int) -> None:
        while not self._stop_event.is_set():
            try:
                self.evaluate_once()
            except Exception as exc:
                log.exception("Check cycle failed: %s", exc)
            self._stop_event.wait(interval)

    def stop(self) -> None:
        self._stop_event.set()


def main() -> int:
    parser = argparse.ArgumentParser(description="Nextcloud self-healing exporter")
    parser.add_argument("--port", type=int, default=9130, help="Prometheus port")
    parser.add_argument("--status-port", type=int, default=9131, help="Status API port")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL, help="Interval in seconds")
    parser.add_argument("--config", default="", help="Path to JSON config")
    args = parser.parse_args()

    if not HAS_PROM:
        log.error("prometheus_client is required")
        return 1

    config = load_config(args.config or None)
    checker = NextcloudHealthChecker(config)
    os.makedirs(DATA_DIR, exist_ok=True)
    start_http_server(args.port)
    status_server = checker.serve_status_api(args.status_port)

    def handle_signal(signum: int, _frame: Any) -> None:
        log.info("Received signal %s, shutting down", signum)
        checker.stop()
        status_server.shutdown()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    log.info("Starting Nextcloud self-healing exporter on :%s", args.port)
    checker.run_forever(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
