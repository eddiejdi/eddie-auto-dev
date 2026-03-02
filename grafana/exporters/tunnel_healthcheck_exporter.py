#!/usr/bin/env python3
"""Prometheus exporter + self-healing for Cloudflare/SSH tunnels on homelab.

Usage:
  python3 tunnel_healthcheck_exporter.py --port 9110

Metrics exposed (Prometheus format):
  tunnel_up{name, type}                  — 1 if healthy, 0 if down
  tunnel_restart_total{name, type}       — counter of auto-restarts
  tunnel_response_time_seconds{name}     — HTTP probe latency
  tunnel_last_check_timestamp{name}      — unix ts of last check
  tunnel_selfheal_actions_total{action}  — total self-heal actions taken
  tunnel_consecutive_failures{name}      — sequential failures before recovery

Systemd service:  tunnel-healthcheck-exporter.service
Self-healing:     restarts systemd units when health checks fail (max 3 retries/hour)
"""

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Dict, List, Optional

try:
    from prometheus_client import start_http_server, Counter, Gauge, Summary
    HAS_PROM = True
except ImportError:
    HAS_PROM = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [tunnel-heal] %(message)s",
)
log = logging.getLogger("tunnel-heal")

# ── Configuration ──────────────────────────────────────────────────────
DATA_DIR = os.environ.get("TUNNEL_HEAL_DATA_DIR", "/var/lib/eddie/tunnel-heal")
AUDIT_LOG = os.path.join(DATA_DIR, "tunnel_heal_audit.jsonl")
MAX_RESTARTS_PER_HOUR = int(os.environ.get("TUNNEL_HEAL_MAX_RESTARTS", "3"))
CHECK_INTERVAL = int(os.environ.get("TUNNEL_HEAL_INTERVAL", "30"))  # seconds
COOLDOWN_AFTER_RESTART = int(os.environ.get("TUNNEL_HEAL_COOLDOWN", "60"))  # seconds

# ── Tunnel definitions ─────────────────────────────────────────────────

@dataclass
class TunnelDef:
    """Definition of a tunnel to monitor."""
    name: str
    tunnel_type: str  # cloudflared | ssh_reverse | nginx | docker
    systemd_unit: str
    health_url: Optional[str] = None  # HTTP endpoint to probe
    health_port: Optional[int] = None  # TCP port to check
    expected_process: Optional[str] = None  # grep pattern for ps
    restart_command: Optional[str] = None  # override for restart
    docker_container: Optional[str] = None  # Docker container name (for type=docker)
    enabled: bool = True


# Default tunnel definitions — can be overridden via JSON config
DEFAULT_TUNNELS: List[TunnelDef] = [
    TunnelDef(
        name="cloudflared-rpa4all",
        tunnel_type="cloudflared",
        systemd_unit="cloudflared-rpa4all.service",
        health_url="http://127.0.0.1:20241/ready",
        expected_process="cloudflared.*tunnel run",
    ),
    TunnelDef(
        name="openwebui-ssh-tunnel",
        tunnel_type="ssh_reverse",
        systemd_unit="openwebui-ssh-tunnel.service",
        health_port=13300,
        expected_process="ssh .* -R",
        enabled=False,  # Currently disabled per homelab scan
    ),
    TunnelDef(
        name="nginx-proxy",
        tunnel_type="nginx",
        systemd_unit="nginx.service",
        health_url="http://127.0.0.1:8090/",
        expected_process="nginx: master",
    ),
]


def load_tunnel_config(config_path: str) -> List[TunnelDef]:
    """Load tunnel definitions from JSON file, falling back to defaults."""
    if config_path and os.path.isfile(config_path):
        try:
            with open(config_path) as f:
                data = json.load(f)
            tunnels = []
            for t in data.get("tunnels", []):
                tunnels.append(TunnelDef(**t))
            log.info("Loaded %d tunnel definitions from %s", len(tunnels), config_path)
            return tunnels
        except Exception as e:
            log.warning("Failed to load config %s: %s — using defaults", config_path, e)
    return DEFAULT_TUNNELS


# ── Health check engine ────────────────────────────────────────────────

@dataclass
class TunnelState:
    up: bool = False
    last_check: float = 0
    consecutive_failures: int = 0
    restarts_this_hour: int = 0
    restarts_total: int = 0
    last_restart: float = 0
    response_time: float = 0
    hour_window_start: float = 0


class TunnelHealthChecker:
    """Checks tunnel health and performs self-healing restarts."""

    def __init__(self, tunnels: List[TunnelDef]):
        self.tunnels = {t.name: t for t in tunnels}
        self.states: Dict[str, TunnelState] = {t.name: TunnelState() for t in tunnels}
        self._lock = threading.Lock()

    def check_systemd_active(self, unit: str) -> bool:
        """Check if a systemd unit is active."""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", unit],
                capture_output=True, text=True, timeout=5,
            )
            return result.stdout.strip() == "active"
        except Exception:
            return False

    def check_http(self, url: str, timeout: float = 5) -> tuple:
        """HTTP probe. Returns (ok, response_time_seconds)."""
        import urllib.request
        import urllib.error
        start = time.monotonic()
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                elapsed = time.monotonic() - start
                return resp.status < 500, elapsed
        except Exception:
            return False, time.monotonic() - start

    def check_tcp_port(self, port: int, host: str = "127.0.0.1", timeout: float = 3) -> bool:
        """Check if a TCP port is listening."""
        import socket
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
            return False

    def check_process(self, pattern: str) -> bool:
        """Check if a process matching pattern is running."""
        try:
            result = subprocess.run(
                ["pgrep", "-f", pattern],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def restart_service(self, tunnel: TunnelDef, state: TunnelState) -> bool:
        """Restart a systemd service with rate limiting."""
        now = time.time()

        # Reset hourly counter if window expired
        if now - state.hour_window_start > 3600:
            state.restarts_this_hour = 0
            state.hour_window_start = now

        # Rate limit
        if state.restarts_this_hour >= MAX_RESTARTS_PER_HOUR:
            log.warning(
                "RATE LIMIT: %s already restarted %d times this hour — skipping",
                tunnel.name, state.restarts_this_hour,
            )
            return False

        # Cooldown
        if now - state.last_restart < COOLDOWN_AFTER_RESTART:
            log.info("COOLDOWN: %s restarted recently — waiting", tunnel.name)
            return False

        # Determine restart command:
        # 1. Explicit restart_command if set
        # 2. For Docker containers: docker restart <container> (fast, doesn't restart daemon)
        # 3. Default: systemctl restart <unit>
        if tunnel.restart_command:
            cmd = tunnel.restart_command
        elif tunnel.tunnel_type == "docker":
            container_name = tunnel.docker_container or tunnel.name
            cmd = f"docker restart {container_name}"
        else:
            cmd = f"systemctl restart {tunnel.systemd_unit}"

        log.warning("SELF-HEAL: restarting %s via: %s", tunnel.name, cmd)
        try:
            result = subprocess.run(
                cmd.split(), capture_output=True, text=True, timeout=60,
            )
            success = result.returncode == 0
            state.last_restart = now
            state.restarts_this_hour += 1
            state.restarts_total += 1
            self._audit("restart", tunnel.name, success, result.stderr.strip())
            if success:
                log.info("SELF-HEAL: %s restarted successfully", tunnel.name)
            else:
                log.error("SELF-HEAL: %s restart FAILED: %s", tunnel.name, result.stderr)
            return success
        except Exception as e:
            log.error("SELF-HEAL: %s restart EXCEPTION: %s", tunnel.name, e)
            self._audit("restart", tunnel.name, False, str(e))
            return False

    def check_tunnel(self, name: str) -> bool:
        """Run all health checks for a tunnel. Returns True if healthy."""
        tunnel = self.tunnels[name]
        state = self.states[name]

        if not tunnel.enabled:
            state.up = False
            state.last_check = time.time()
            return False

        checks = []

        # 1. Systemd unit active
        systemd_ok = self.check_systemd_active(tunnel.systemd_unit)
        checks.append(("systemd", systemd_ok))

        # 2. HTTP health (if configured)
        response_time = 0
        if tunnel.health_url:
            http_ok, response_time = self.check_http(tunnel.health_url)
            checks.append(("http", http_ok))
            state.response_time = response_time

        # 3. TCP port (if configured)
        if tunnel.health_port:
            tcp_ok = self.check_tcp_port(tunnel.health_port)
            checks.append(("tcp", tcp_ok))

        # 4. Process running (if configured)
        if tunnel.expected_process:
            proc_ok = self.check_process(tunnel.expected_process)
            checks.append(("process", proc_ok))

        # Determine overall health — all checks must pass
        all_ok = all(ok for _, ok in checks) and len(checks) > 0
        state.last_check = time.time()

        if all_ok:
            if state.consecutive_failures > 0:
                log.info("RECOVERED: %s is healthy again after %d failures",
                         name, state.consecutive_failures)
                self._audit("recovered", name, True,
                            f"after {state.consecutive_failures} failures")
            state.consecutive_failures = 0
            state.up = True
        else:
            state.consecutive_failures += 1
            state.up = False
            failed = [c for c, ok in checks if not ok]
            log.warning("UNHEALTHY: %s — failed checks: %s (attempt %d)",
                        name, failed, state.consecutive_failures)

            # Self-heal after 2 consecutive failures
            if state.consecutive_failures >= 2:
                self.restart_service(tunnel, state)

        return all_ok

    def check_all(self):
        """Run checks on all tunnels."""
        for name in self.tunnels:
            try:
                self.check_tunnel(name)
            except Exception as e:
                log.error("CHECK ERROR for %s: %s", name, e)

    def _audit(self, action: str, tunnel: str, success: bool, detail: str = ""):
        """Append to audit log."""
        try:
            os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
            entry = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "action": action,
                "tunnel": tunnel,
                "success": success,
                "detail": detail,
            }
            with open(AUDIT_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def get_summary(self) -> Dict:
        """Return current state summary."""
        result = {}
        for name, state in self.states.items():
            tunnel = self.tunnels[name]
            result[name] = {
                "type": tunnel.tunnel_type,
                "enabled": tunnel.enabled,
                "up": state.up,
                "consecutive_failures": state.consecutive_failures,
                "restarts_total": state.restarts_total,
                "restarts_this_hour": state.restarts_this_hour,
                "response_time_ms": round(state.response_time * 1000, 2),
                "last_check": datetime.fromtimestamp(
                    state.last_check, tz=timezone.utc
                ).isoformat() if state.last_check else None,
            }
        return result


# ── Prometheus metrics ─────────────────────────────────────────────────

def setup_prometheus_metrics():
    """Create Prometheus metric objects."""
    if not HAS_PROM:
        return None

    metrics = {
        "up": Gauge(
            "tunnel_up", "Tunnel health status (1=up, 0=down)",
            ["name", "type"],
        ),
        "restart_total": Counter(
            "tunnel_restart_total", "Total self-heal restarts",
            ["name", "type"],
        ),
        "response_time": Gauge(
            "tunnel_response_time_seconds", "HTTP probe response time",
            ["name"],
        ),
        "last_check": Gauge(
            "tunnel_last_check_timestamp", "Unix timestamp of last health check",
            ["name"],
        ),
        "consecutive_failures": Gauge(
            "tunnel_consecutive_failures", "Consecutive health check failures",
            ["name"],
        ),
        "selfheal_actions": Counter(
            "tunnel_selfheal_actions_total", "Total self-healing actions",
            ["action"],
        ),
    }
    return metrics


def update_prometheus(checker: TunnelHealthChecker, prom_metrics: dict):
    """Push current state to Prometheus gauges/counters."""
    if not prom_metrics:
        return
    for name, state in checker.states.items():
        tunnel = checker.tunnels[name]
        prom_metrics["up"].labels(name=name, type=tunnel.tunnel_type).set(
            1 if state.up else 0
        )
        prom_metrics["response_time"].labels(name=name).set(state.response_time)
        prom_metrics["last_check"].labels(name=name).set(state.last_check)
        prom_metrics["consecutive_failures"].labels(name=name).set(
            state.consecutive_failures
        )
        # Counter: set to total (Prometheus counters only go up)
        # We track via _created to avoid double counts
        restart_counter = prom_metrics["restart_total"].labels(
            name=name, type=tunnel.tunnel_type
        )
        # Increment by delta since last update
        current_val = restart_counter._value.get()
        if state.restarts_total > current_val:
            restart_counter.inc(state.restarts_total - current_val)


# ── HTTP status endpoint (non-Prometheus) ──────────────────────────────

class StatusHandler(BaseHTTPRequestHandler):
    checker: TunnelHealthChecker = None

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        elif self.path == "/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            summary = self.checker.get_summary() if self.checker else {}
            self.wfile.write(json.dumps(summary, indent=2).encode())
        elif self.path == "/audit" or self.path.startswith("/audit?"):
            self._serve_audit()
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_audit(self):
        try:
            lines = []
            if os.path.isfile(AUDIT_LOG):
                with open(AUDIT_LOG) as f:
                    lines = f.readlines()[-50:]  # last 50 entries
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            entries = [json.loads(l) for l in lines if l.strip()]
            self.wfile.write(json.dumps(entries, indent=2).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())

    def log_message(self, format, *args):
        pass  # silence access logs


# ── Main loop ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Tunnel health-check + self-healing exporter")
    parser.add_argument("--port", type=int, default=9110, help="Prometheus metrics port")
    parser.add_argument("--status-port", type=int, default=9111, help="HTTP status/audit port")
    parser.add_argument("--config", type=str, default="", help="Path to tunnels JSON config")
    parser.add_argument("--interval", type=int, default=CHECK_INTERVAL, help="Check interval (s)")
    parser.add_argument("--dry-run", action="store_true", help="Check but don't restart")
    args = parser.parse_args()

    tunnels = load_tunnel_config(args.config)
    checker = TunnelHealthChecker(tunnels)

    # Prometheus
    prom_metrics = None
    if HAS_PROM:
        prom_metrics = setup_prometheus_metrics()
        start_http_server(args.port)
        log.info("Prometheus metrics on :%d", args.port)
    else:
        log.warning("prometheus_client not installed — metrics disabled (pip install prometheus_client)")

    # Status HTTP server
    StatusHandler.checker = checker
    status_server = HTTPServer(("0.0.0.0", args.status_port), StatusHandler)
    status_thread = threading.Thread(target=status_server.serve_forever, daemon=True)
    status_thread.start()
    log.info("Status/audit API on :%d (/health, /status, /audit)", args.status_port)

    # Signal handling
    running = True

    def shutdown(sig, frame):
        nonlocal running
        log.info("Shutting down (signal %s)...", sig)
        running = False

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    log.info("Starting tunnel health-check loop (interval=%ds, dry_run=%s)",
             args.interval, args.dry_run)
    log.info("Monitoring %d tunnels: %s",
             len(tunnels), [t.name for t in tunnels if t.enabled])

    if args.dry_run:
        # Patch restart to no-op
        original_restart = checker.restart_service
        def noop_restart(tunnel, state):
            log.info("DRY-RUN: would restart %s", tunnel.name)
            return False
        checker.restart_service = noop_restart

    while running:
        try:
            checker.check_all()
            if prom_metrics:
                update_prometheus(checker, prom_metrics)

            # Log summary periodically
            summary = checker.get_summary()
            statuses = {n: ("UP" if s["up"] else "DOWN") for n, s in summary.items() if s["enabled"]}
            log.info("Status: %s", statuses)

        except Exception as e:
            log.error("Check loop error: %s", e)

        time.sleep(args.interval)

    log.info("Shutdown complete.")


if __name__ == "__main__":
    main()
