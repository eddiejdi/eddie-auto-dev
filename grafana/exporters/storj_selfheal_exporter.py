#!/usr/bin/env python3
"""Prometheus exporter + self-healing for Storj Storage Node.

Detects the main failure modes seen in homelab operation:
1. Storj container stopped or unhealthy
2. Local API on port 14002 unavailable
3. Drift between current public IPv4 and contact.external-address

When the public IP drifts, the exporter updates config.yaml and recreates the
container with the new ADDRESS env var while preserving the current runtime
definition extracted from docker inspect.
"""

from __future__ import annotations

import argparse
import collections
import json
import logging
import os
import re
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
from typing import Any, Dict, List, Optional, Tuple

try:
    from prometheus_client import Counter, Gauge, start_http_server

    HAS_PROM = True
except ImportError:
    HAS_PROM = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [storj-heal] %(message)s",
)
log = logging.getLogger("storj-heal")

DATA_DIR = os.environ.get("STORJ_HEAL_DATA_DIR", "/var/lib/eddie/storj-heal")
AUDIT_LOG = os.path.join(DATA_DIR, "storj_heal_audit.jsonl")
AUDIT_MAX_SIZE_MB = int(os.environ.get("STORJ_HEAL_AUDIT_MAX_MB", "10"))
DEFAULT_INTERVAL = int(os.environ.get("STORJ_HEAL_INTERVAL", "60"))
DEFAULT_MAX_ACTIONS = int(os.environ.get("STORJ_HEAL_MAX_ACTIONS", "3"))
DEFAULT_COOLDOWN = int(os.environ.get("STORJ_HEAL_COOLDOWN", "900"))


@dataclass
class StorjDef:
    enabled: bool = True
    container_name: str = "storagenode"
    config_path: str = "/mnt/disk3/storj/data/config.yaml"
    health_url: str = "http://127.0.0.1:14002/api/sno/satellites"
    public_port: int = 28967
    max_actions_per_hour: int = DEFAULT_MAX_ACTIONS
    cooldown_after_action_seconds: int = DEFAULT_COOLDOWN
    consecutive_failures_before_restart: int = 2
    recreate_on_address_drift: bool = True
    public_ip_sources: List[str] = field(
        default_factory=lambda: [
            "https://api.ipify.org",
            "https://ifconfig.me/ip",
        ]
    )


@dataclass
class StorjState:
    healthy: bool = False
    container_up: bool = False
    api_up: bool = False
    address_match: bool = False
    last_check: float = 0.0
    consecutive_failures: int = 0
    actions_this_hour: int = 0
    actions_total: int = 0
    restart_total: int = 0
    recreate_total: int = 0
    last_action: str = ""
    last_action_detail: str = ""
    last_action_at: float = 0.0
    hour_window_start: float = 0.0
    current_public_ip: str = ""
    expected_address: str = ""
    configured_address: str = ""
    container_address: str = ""


class StorjHealthChecker:
    """Checks Storj health and performs bounded self-healing actions."""

    def __init__(self, node: StorjDef):
        self.node = node
        self.state = StorjState()
        self._lock = threading.Lock()
        self._action_counters = collections.Counter()

    def run_command(self, cmd: List[str], timeout: int = 30) -> subprocess.CompletedProcess:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    def get_public_ip(self) -> str:
        for url in self.node.public_ip_sources:
            try:
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    value = resp.read().decode("utf-8", "replace").strip()
                if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", value):
                    return value
            except Exception as exc:
                log.warning("Public IP source failed (%s): %s", url, exc)
        return ""

    def http_ok(self, url: str) -> bool:
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status < 500
        except Exception:
            return False

    def get_container_inspect(self) -> Optional[Dict[str, Any]]:
        result = self.run_command(["docker", "inspect", self.node.container_name])
        if result.returncode != 0 or not result.stdout.strip():
            return None
        try:
            return json.loads(result.stdout)[0]
        except Exception as exc:
            log.error("Failed to parse docker inspect: %s", exc)
            return None

    def is_container_running(self, inspect_obj: Optional[Dict[str, Any]]) -> bool:
        if not inspect_obj:
            return False
        return bool(inspect_obj.get("State", {}).get("Running"))

    def get_container_address(self, inspect_obj: Optional[Dict[str, Any]]) -> str:
        if not inspect_obj:
            return ""
        for item in inspect_obj.get("Config", {}).get("Env", []) or []:
            if item.startswith("ADDRESS="):
                return item.split("=", 1)[1]
        return ""

    def get_configured_address(self) -> str:
        path = self.node.config_path
        if not os.path.isfile(path):
            return ""
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("contact.external-address:"):
                        match = re.search(r'"([^"]+)"', line)
                        if match:
                            return match.group(1).strip()
                        value = line.split(":", 1)[1].strip()
                        return value.strip('"')
        except Exception as exc:
            log.warning("Failed reading %s: %s", path, exc)
        return ""

    def update_config_address(self, expected_address: str) -> bool:
        path = self.node.config_path
        if not os.path.isfile(path):
            return False

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = f"{path}.bak_{timestamp}"
        try:
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()

            if "contact.external-address:" in content:
                new_content = re.sub(
                    r'^contact\.external-address:\s*"?[^"\n]+"?\s*$',
                    f'contact.external-address: "{expected_address}"',
                    content,
                    flags=re.MULTILINE,
                )
            else:
                suffix = "" if content.endswith("\n") else "\n"
                new_content = (
                    content
                    + suffix
                    + f'contact.external-address: "{expected_address}"\n'
                )

            if new_content == content:
                return True

            with open(backup_path, "w", encoding="utf-8") as fh:
                fh.write(content)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(new_content)
            return True
        except Exception as exc:
            log.error("Failed updating %s: %s", path, exc)
            return False

    def _format_restart_policy(self, inspect_obj: Dict[str, Any]) -> List[str]:
        policy = inspect_obj.get("HostConfig", {}).get("RestartPolicy", {}) or {}
        name = policy.get("Name") or "no"
        count = policy.get("MaximumRetryCount", 0) or 0
        if name == "no":
            return []
        if name == "on-failure" and count:
            return ["--restart", f"{name}:{count}"]
        return ["--restart", name]

    def _format_ports(self, inspect_obj: Dict[str, Any]) -> List[str]:
        args: List[str] = []
        bindings = inspect_obj.get("HostConfig", {}).get("PortBindings", {}) or {}
        for container_port in sorted(bindings.keys()):
            for binding in bindings.get(container_port) or []:
                host_ip = binding.get("HostIp") or ""
                host_port = binding.get("HostPort") or ""
                if host_ip:
                    mapping = f"{host_ip}:{host_port}:{container_port}"
                else:
                    mapping = f"{host_port}:{container_port}"
                args.extend(["-p", mapping])
        return args

    def _format_binds(self, inspect_obj: Dict[str, Any]) -> List[str]:
        args: List[str] = []
        for bind in inspect_obj.get("HostConfig", {}).get("Binds", []) or []:
            args.extend(["-v", bind])
        return args

    def _format_env(self, inspect_obj: Dict[str, Any], expected_address: str) -> List[str]:
        args: List[str] = []
        seen_address = False
        for item in inspect_obj.get("Config", {}).get("Env", []) or []:
            if item.startswith("ADDRESS="):
                item = f"ADDRESS={expected_address}"
                seen_address = True
            args.extend(["-e", item])
        if not seen_address:
            args.extend(["-e", f"ADDRESS={expected_address}"])
        return args

    def _format_entrypoint_cmd(self, inspect_obj: Dict[str, Any]) -> List[str]:
        args: List[str] = []
        entrypoint = inspect_obj.get("Config", {}).get("Entrypoint")
        if entrypoint:
            args.extend(["--entrypoint", json.dumps(entrypoint) if isinstance(entrypoint, str) else entrypoint[0]])
        return args

    def _format_log_opts(self, inspect_obj: Dict[str, Any]) -> List[str]:
        args: List[str] = []
        log_config = inspect_obj.get("HostConfig", {}).get("LogConfig", {}) or {}
        log_type = log_config.get("Type")
        if log_type and log_type != "json-file":
            args.extend(["--log-driver", log_type])
        for key, value in sorted((log_config.get("Config") or {}).items()):
            args.extend(["--log-opt", f"{key}={value}"])
        return args

    def recreate_with_new_address(self, inspect_obj: Optional[Dict[str, Any]], expected_address: str) -> bool:
        if not inspect_obj:
            self._audit("recreate_missing_container", False, "docker inspect returned empty")
            return False

        name = inspect_obj.get("Name", f"/{self.node.container_name}").lstrip("/")
        backup_name = f"{name}-bak-{int(time.time())}"
        image = inspect_obj.get("Config", {}).get("Image")
        if not image:
            self._audit("recreate_missing_image", False, "container has no image")
            return False

        run_cmd = ["docker", "run", "-d", "--name", name]
        run_cmd += self._format_restart_policy(inspect_obj)
        run_cmd += self._format_ports(inspect_obj)
        run_cmd += self._format_binds(inspect_obj)
        run_cmd += self._format_env(inspect_obj, expected_address)
        run_cmd += self._format_log_opts(inspect_obj)
        run_cmd.append(image)

        if inspect_obj.get("Config", {}).get("Cmd"):
            run_cmd.extend(inspect_obj["Config"]["Cmd"])

        rename = self.run_command(["docker", "rename", name, backup_name], timeout=20)
        if rename.returncode != 0:
            self._audit("recreate_rename_failed", False, rename.stderr.strip())
            return False

        stop_old = self.run_command(["docker", "stop", backup_name], timeout=90)
        if stop_old.returncode != 0:
            self.run_command(["docker", "rename", backup_name, name], timeout=20)
            self._audit("recreate_stop_old_failed", False, stop_old.stderr.strip())
            return False

        start_new = self.run_command(run_cmd, timeout=120)
        if start_new.returncode == 0:
            self.run_command(["docker", "rm", backup_name], timeout=30)
            self._audit("recreate_with_new_address", True, expected_address)
            return True

        log.error("Failed to recreate %s: %s", name, start_new.stderr.strip())
        self.run_command(["docker", "start", backup_name], timeout=90)
        self.run_command(["docker", "rename", backup_name, name], timeout=20)
        self._audit("recreate_with_new_address", False, start_new.stderr.strip())
        return False

    def restart_container(self) -> bool:
        result = self.run_command(["docker", "restart", self.node.container_name], timeout=90)
        success = result.returncode == 0
        self._audit("restart", success, result.stderr.strip() if result.stderr else result.stdout.strip())
        if success:
            self.state.restart_total += 1
        return success

    def _can_act(self) -> bool:
        now = time.time()
        if now - self.state.hour_window_start > 3600:
            self.state.actions_this_hour = 0
            self.state.hour_window_start = now
        if self.state.actions_this_hour >= self.node.max_actions_per_hour:
            self._audit(
                "rate_limited",
                False,
                f"exceeded {self.node.max_actions_per_hour} actions/hour",
            )
            return False
        if now - self.state.last_action_at < self.node.cooldown_after_action_seconds:
            return False
        return True

    def _mark_action(self, action: str, detail: str = "") -> None:
        now = time.time()
        self.state.last_action = action
        self.state.last_action_detail = detail
        self.state.last_action_at = now
        self.state.actions_this_hour += 1
        self.state.actions_total += 1
        self._action_counters[action] += 1

    def _audit(self, action: str, success: bool, detail: str = "") -> None:
        try:
            os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
            with open(AUDIT_LOG, "a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "action": action,
                            "success": success,
                            "detail": detail,
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass

    def check_once(self) -> None:
        with self._lock:
            inspect_obj = self.get_container_inspect()
            current_public_ip = self.get_public_ip()
            expected_address = (
                f"{current_public_ip}:{self.node.public_port}" if current_public_ip else ""
            )
            configured_address = self.get_configured_address()
            container_address = self.get_container_address(inspect_obj)
            container_up = self.is_container_running(inspect_obj)
            api_up = self.http_ok(self.node.health_url) if container_up else False
            address_match = bool(
                expected_address
                and configured_address == expected_address
                and container_address == expected_address
            )

            self.state.current_public_ip = current_public_ip
            self.state.expected_address = expected_address
            self.state.configured_address = configured_address
            self.state.container_address = container_address
            self.state.container_up = container_up
            self.state.api_up = api_up
            self.state.address_match = address_match
            self.state.last_check = time.time()

            healthy = container_up and api_up and (address_match or not expected_address)
            self.state.healthy = healthy

            if healthy:
                if self.state.consecutive_failures > 0:
                    self._audit(
                        "recovered",
                        True,
                        f"after {self.state.consecutive_failures} failures",
                    )
                self.state.consecutive_failures = 0
                return

            self.state.consecutive_failures += 1
            log.warning(
                "Storj unhealthy: container_up=%s api_up=%s address_match=%s expected=%s configured=%s container=%s attempt=%d",
                container_up,
                api_up,
                address_match,
                expected_address,
                configured_address,
                container_address,
                self.state.consecutive_failures,
            )

            if expected_address and self.node.recreate_on_address_drift and not address_match:
                if self._can_act():
                    updated = self.update_config_address(expected_address)
                    success = False
                    detail = expected_address
                    if updated:
                        success = self.recreate_with_new_address(inspect_obj, expected_address)
                    else:
                        detail = "failed to update config.yaml"
                    self._mark_action("recreate_address_drift", detail)
                    if success:
                        self.state.recreate_total += 1
                        return

            if self.state.consecutive_failures >= self.node.consecutive_failures_before_restart:
                if self._can_act():
                    success = self.restart_container()
                    self._mark_action("restart_container", self.node.container_name)
                    if success:
                        return

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "enabled": self.node.enabled,
                "healthy": self.state.healthy,
                "container_up": self.state.container_up,
                "api_up": self.state.api_up,
                "address_match": self.state.address_match,
                "current_public_ip": self.state.current_public_ip,
                "expected_address": self.state.expected_address,
                "configured_address": self.state.configured_address,
                "container_address": self.state.container_address,
                "consecutive_failures": self.state.consecutive_failures,
                "actions_this_hour": self.state.actions_this_hour,
                "actions_total": self.state.actions_total,
                "restart_total": self.state.restart_total,
                "recreate_total": self.state.recreate_total,
                "last_action": self.state.last_action,
                "last_action_detail": self.state.last_action_detail,
                "last_check": datetime.fromtimestamp(
                    self.state.last_check, tz=timezone.utc
                ).isoformat()
                if self.state.last_check
                else None,
                "last_action_at": datetime.fromtimestamp(
                    self.state.last_action_at, tz=timezone.utc
                ).isoformat()
                if self.state.last_action_at
                else None,
            }


def load_config(path: str) -> StorjDef:
    if path and os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return StorjDef(**data)
        except Exception as exc:
            log.warning("Failed to load config %s: %s", path, exc)
    return StorjDef()


def rotate_audit_if_needed() -> None:
    try:
        if not os.path.isfile(AUDIT_LOG):
            return
        size_mb = os.path.getsize(AUDIT_LOG) / (1024 * 1024)
        if size_mb < AUDIT_MAX_SIZE_MB:
            return
        with open(AUDIT_LOG, "r", encoding="utf-8") as fh:
            tail = collections.deque(fh, maxlen=1000)
        with open(AUDIT_LOG, "w", encoding="utf-8") as fh:
            fh.writelines(tail)
    except Exception as exc:
        log.warning("Audit rotation failed: %s", exc)


def setup_prom_metrics() -> Optional[Dict[str, Any]]:
    if not HAS_PROM:
        return None
    return {
        "healthy": Gauge("storj_selfheal_healthy", "Storj self-heal overall health (1=healthy)"),
        "container_up": Gauge("storj_selfheal_container_up", "Storj container running (1=yes)"),
        "api_up": Gauge("storj_selfheal_api_up", "Storj local API reachable (1=yes)"),
        "address_match": Gauge(
            "storj_selfheal_address_match",
            "Current public IP matches Storj advertised external address (1=yes)",
        ),
        "consecutive_failures": Gauge(
            "storj_selfheal_consecutive_failures",
            "Storj self-heal consecutive unhealthy checks",
        ),
        "last_check": Gauge(
            "storj_selfheal_last_check_timestamp",
            "Unix timestamp of the last self-heal check",
        ),
        "last_action": Gauge(
            "storj_selfheal_last_action_timestamp",
            "Unix timestamp of the last self-heal action",
        ),
        "restart_total": Counter(
            "storj_selfheal_restart_total",
            "Storj self-heal restarts performed",
        ),
        "recreate_total": Counter(
            "storj_selfheal_recreate_total",
            "Storj self-heal recreates performed",
        ),
        "actions_total": Counter(
            "storj_selfheal_actions_total",
            "Storj self-heal actions",
            ["action"],
        ),
        "address_info": Gauge(
            "storj_selfheal_address_info",
            "Storj address context",
            ["current_public_ip", "expected_address", "configured_address", "container_address"],
        ),
    }


_counter_sync = {"restart_total": 0, "recreate_total": 0}
_action_sync: Dict[str, int] = {}
_info_labels: Optional[Tuple[str, str, str, str]] = None


def update_prometheus(checker: StorjHealthChecker, prom: Dict[str, Any]) -> None:
    global _info_labels

    state = checker.state
    prom["healthy"].set(1 if state.healthy else 0)
    prom["container_up"].set(1 if state.container_up else 0)
    prom["api_up"].set(1 if state.api_up else 0)
    prom["address_match"].set(1 if state.address_match else 0)
    prom["consecutive_failures"].set(state.consecutive_failures)
    prom["last_check"].set(state.last_check)
    prom["last_action"].set(state.last_action_at)

    for name in ("restart_total", "recreate_total"):
        current = getattr(state, name)
        previous = _counter_sync.get(name, 0)
        if current > previous:
            prom[name].inc(current - previous)
            _counter_sync[name] = current

    for action, current in checker._action_counters.items():
        previous = _action_sync.get(action, 0)
        if current > previous:
            prom["actions_total"].labels(action=action).inc(current - previous)
            _action_sync[action] = current

    new_labels = (
        state.current_public_ip or "unknown",
        state.expected_address or "unknown",
        state.configured_address or "unknown",
        state.container_address or "unknown",
    )
    if _info_labels and _info_labels != new_labels:
        try:
            prom["address_info"].remove(*_info_labels)
        except KeyError:
            pass
    _info_labels = new_labels
    prom["address_info"].labels(*new_labels).set(1)


class StatusHandler(BaseHTTPRequestHandler):
    checker: Optional[StorjHealthChecker] = None

    def do_GET(self) -> None:
        if self.path == "/health":
            self._write_json(200, {"status": "ok"})
            return
        if self.path == "/status":
            self._write_json(200, self.checker.get_summary() if self.checker else {})
            return
        if self.path == "/audit" or self.path.startswith("/audit?"):
            lines: List[str] = []
            if os.path.isfile(AUDIT_LOG):
                with open(AUDIT_LOG, "r", encoding="utf-8") as fh:
                    lines = list(collections.deque(fh, maxlen=50))
            entries = [json.loads(line) for line in lines if line.strip()]
            self._write_json(200, entries)
            return
        self.send_response(404)
        self.end_headers()

    def _write_json(self, code: int, payload: Any) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload, indent=2).encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Storj health-check + self-healing exporter")
    parser.add_argument("--port", type=int, default=9652, help="Prometheus metrics port")
    parser.add_argument("--status-port", type=int, default=9653, help="Status API port")
    parser.add_argument("--config", type=str, default="", help="Path to Storj self-heal JSON config")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL, help="Check interval in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Observe only, do not restart/recreate")
    args = parser.parse_args()

    node = load_config(args.config)
    checker = StorjHealthChecker(node)

    if args.dry_run:
        checker.restart_container = lambda: False
        checker.recreate_with_new_address = lambda inspect_obj, expected: False

    prom = None
    if HAS_PROM:
        prom = setup_prom_metrics()
        start_http_server(args.port)
        log.info("Prometheus metrics on :%d", args.port)
    else:
        log.warning("prometheus_client not installed — metrics disabled")

    StatusHandler.checker = checker
    status_server = HTTPServer(("0.0.0.0", args.status_port), StatusHandler)
    status_thread = threading.Thread(target=status_server.serve_forever, daemon=True)
    status_thread.start()
    log.info("Status/audit API on :%d (/health, /status, /audit)", args.status_port)

    stop_event = threading.Event()

    def shutdown(sig: int, frame: Any) -> None:
        log.info("Shutting down (signal %s)...", sig)
        stop_event.set()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    log.info(
        "Starting Storj self-heal loop (interval=%ds, container=%s, dry_run=%s)",
        args.interval,
        node.container_name,
        args.dry_run,
    )

    while not stop_event.is_set():
        try:
            if node.enabled:
                checker.check_once()
                if prom:
                    update_prometheus(checker, prom)
                summary = checker.get_summary()
                log.info(
                    "Status: healthy=%s container=%s api=%s address_match=%s failures=%d",
                    summary["healthy"],
                    summary["container_up"],
                    summary["api_up"],
                    summary["address_match"],
                    summary["consecutive_failures"],
                )
            rotate_audit_if_needed()
        except Exception as exc:
            log.error("Check loop error: %s", exc)
        stop_event.wait(args.interval)

    status_server.shutdown()
    log.info("Shutdown complete.")


if __name__ == "__main__":
    main()
