#!/usr/bin/env python3
"""Prometheus exporter com self-heal para Storj Storage Node.

Monitora o no Storj via API local, consistencia do endereco anunciado,
alcance da porta 28967 no macvlan e aplica acoes graduais de recuperacao.

Uso:
  python3 storj_selfheal_exporter.py --port 9112 --status-port 9113 \
      --config /etc/eddie/storj_selfheal.json
"""

from __future__ import annotations

import argparse
import collections
import json
import logging
import shlex
import signal
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

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

DATA_DIR = Path(
    __import__("os").environ.get("STORJ_HEAL_DATA_DIR", "/var/lib/eddie/storj-heal")
)
AUDIT_LOG = DATA_DIR / "storj_heal_audit.jsonl"
MAX_ACTIONS_PER_HOUR = int(__import__("os").environ.get("STORJ_HEAL_MAX_ACTIONS", "6"))
CHECK_INTERVAL = int(__import__("os").environ.get("STORJ_HEAL_INTERVAL", "30"))
ACTION_COOLDOWN = int(__import__("os").environ.get("STORJ_HEAL_COOLDOWN", "90"))
AUDIT_MAX_SIZE_MB = int(__import__("os").environ.get("STORJ_HEAL_AUDIT_MAX_MB", "10"))
DEFAULT_PUBLIC_IP_URLS = [
    "https://api.ipify.org",
    "https://ifconfig.me/ip",
    "https://checkip.amazonaws.com",
]


@dataclass
class StorjNodeDef:
    """Define um no Storj monitorado pelo self-heal."""

    name: str
    api_url: str
    container_name: str
    expected_external_address: str
    config_path: str
    probe_host: str
    probe_port: int
    port_forward_command: str
    port_forward_service: str
    host_shim_service: str = "storj-host-shim.service"
    failure_threshold: int = 2
    container_restart_threshold: int = 6
    max_last_ping_age_seconds: int = 900
    enabled: bool = True
    recreate_on_address_drift: bool = False
    recreate_command: str = ""
    api_external_address_required: bool = True
    dynamic_public_ip: bool = False
    public_ip_urls: list[str] = field(default_factory=lambda: list(DEFAULT_PUBLIC_IP_URLS))
    sync_public_address_command: str = ""


@dataclass
class StorjNodeState:
    """Estado dinamico do no Storj monitorado."""

    up: bool = False
    api_up: bool = False
    quic_ok: bool = False
    port_open: bool = False
    address_drift: bool = False
    api_external_address_ok: bool = False
    last_quic_status: str = "unknown"
    last_ping_age_seconds: float = 0.0
    last_check: float = 0.0
    consecutive_failures: int = 0
    actions_this_hour: int = 0
    actions_total: dict[str, int] = field(default_factory=dict)
    last_action: str = ""
    last_action_at: float = 0.0
    hour_window_start: float = 0.0
    container_address: str | None = None
    config_address: str | None = None
    api_external_address: str | None = None
    expected_external_address: str | None = None
    configured_port: int | None = None
    last_issues: list[str] = field(default_factory=list)


DEFAULT_NODES = [
    StorjNodeDef(
        name="storagenode",
        api_url="http://127.0.0.1:14002/api/sno",
        container_name="storagenode",
        expected_external_address="191.202.237.52:28967",
        config_path="/mnt/disk3/storj/data/config.yaml",
        probe_host="192.168.15.250",
        probe_port=28967,
        port_forward_command="bash /home/homelab/eddie-auto-dev/grafana/exporters/storj_sync_port_forward.sh",
        port_forward_service="storj-port-forward.service",
        dynamic_public_ip=True,
        sync_public_address_command=(
            "python3 /home/homelab/eddie-auto-dev/grafana/exporters/"
            "storj_sync_public_address.py --container storagenode "
            "--config /mnt/disk3/storj/data/config.yaml --port 28967"
        ),
    )
]


def load_node_config(config_path: str) -> list[StorjNodeDef]:
    """Carrega definicoes do arquivo JSON ou usa defaults."""

    if config_path and Path(config_path).is_file():
        try:
            payload = json.loads(Path(config_path).read_text(encoding="utf-8"))
            nodes = [StorjNodeDef(**item) for item in payload.get("nodes", [])]
            if nodes:
                log.info("Loaded %d Storj node definitions from %s", len(nodes), config_path)
                return nodes
        except (OSError, TypeError, ValueError) as exc:
            log.warning("Failed to load config %s: %s", config_path, exc)
    return DEFAULT_NODES


def parse_timestamp(value: str | None) -> datetime | None:
    """Converte timestamp RFC3339 do Storj para datetime UTC."""

    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def parse_port(value: Any) -> int | None:
    """Normaliza portas vindas da API para inteiro quando possivel."""

    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def detect_public_ip(urls: list[str]) -> str | None:
    """Consulta endpoints simples para descobrir o IP publico atual."""

    for url in urls:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "storj-selfheal/1.0"})
            with urllib.request.urlopen(request, timeout=8) as response:
                value = response.read().decode("utf-8").strip()
            if value:
                return value
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            continue
    return None


def detect_container_public_ip(container_name: str, urls: list[str]) -> str | None:
    """Consulta endpoints simples a partir do namespace de rede do container."""

    for url in urls:
        command = [
            "docker",
            "exec",
            container_name,
            "wget",
            "-qO-",
            "--timeout=8",
            "-U",
            "storj-selfheal/1.0",
            url,
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue

        if result.returncode == 0:
            value = result.stdout.strip()
            if value and "<html" not in value.lower():
                return value
    return None


class StorjHealthChecker:
    """Executa checks de saude e acoes de self-heal para Storj."""

    def __init__(self, nodes: list[StorjNodeDef], dry_run: bool = False) -> None:
        """Inicializa o checker com os nos monitorados."""

        self.nodes = {node.name: node for node in nodes}
        self.states = {node.name: StorjNodeState() for node in nodes}
        self.dry_run = dry_run
        self._lock = threading.Lock()

    def fetch_api_payload(self, url: str) -> dict[str, Any] | None:
        """Consulta a API do Storj e retorna o payload JSON."""

        try:
            request = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            log.warning("Storj API unavailable at %s: %s", url, exc)
            return None

    def read_container_address(self, container_name: str) -> str | None:
        """Le o ADDRESS efetivo do container Storj."""

        command = [
            "docker",
            "inspect",
            container_name,
            "--format",
            "{{range .Config.Env}}{{println .}}{{end}}",
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            log.warning("Failed to inspect %s env: %s", container_name, exc)
            return None

        if result.returncode != 0:
            return None
        for line in result.stdout.splitlines():
            if line.startswith("ADDRESS="):
                return line.split("=", 1)[1].strip() or None
        return None

    def read_config_external_address(self, config_path: str) -> str | None:
        """Extrai contact.external-address do config.yaml."""

        try:
            for raw_line in Path(config_path).read_text(encoding="utf-8").splitlines():
                stripped = raw_line.strip()
                if stripped.startswith("contact.external-address:"):
                    return stripped.split(":", 1)[1].strip().strip('"') or None
        except OSError as exc:
            log.warning("Failed to read Storj config %s: %s", config_path, exc)
        return None

    def probe_tcp_port(self, host: str, port: int, timeout_seconds: float = 3.0) -> bool:
        """Verifica se a porta TCP responde no destino informado."""

        try:
            with socket.create_connection((host, port), timeout=timeout_seconds):
                return True
        except OSError:
            return False

    def resolve_expected_external_address(self, node: StorjNodeDef) -> str:
        """Resolve o endereco externo esperado, estatico ou dinamico."""

        if not node.dynamic_public_ip:
            return node.expected_external_address
        public_ip = detect_container_public_ip(node.container_name, node.public_ip_urls)
        if not public_ip:
            public_ip = detect_public_ip(node.public_ip_urls)
        if public_ip:
            return f"{public_ip}:{node.probe_port}"
        return node.expected_external_address

    def _record_action(self, state: StorjNodeState, action: str) -> None:
        """Atualiza contadores de acoes no estado."""

        state.actions_total[action] = state.actions_total.get(action, 0) + 1
        state.actions_this_hour += 1
        state.last_action = action
        state.last_action_at = time.time()

    def _run_command(self, command: str, timeout_seconds: int = 120) -> tuple[bool, str]:
        """Executa um comando shell simples e retorna status e saida."""

        try:
            result = subprocess.run(
                shlex.split(command),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return False, str(exc)

        output = result.stdout.strip() or result.stderr.strip()
        return result.returncode == 0, output

    def _audit(self, node_name: str, action: str, success: bool, detail: str = "") -> None:
        """Escreve uma linha de auditoria em JSONL."""

        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            entry = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "node": node_name,
                "action": action,
                "success": success,
                "detail": detail,
            }
            with AUDIT_LOG.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
        except OSError:
            log.exception("Failed to write Storj self-heal audit log")

    def _rotate_audit_if_needed(self) -> None:
        """Rotaciona o audit log mantendo as ultimas 1000 linhas."""

        try:
            if not AUDIT_LOG.is_file():
                return
            size_mb = AUDIT_LOG.stat().st_size / (1024 * 1024)
            if size_mb < AUDIT_MAX_SIZE_MB:
                return
            with AUDIT_LOG.open(encoding="utf-8") as handle:
                tail = collections.deque(handle, maxlen=1000)
            with AUDIT_LOG.open("w", encoding="utf-8") as handle:
                handle.writelines(tail)
        except OSError:
            log.exception("Failed to rotate Storj self-heal audit log")

    def decide_action(self, node: StorjNodeDef, state: StorjNodeState) -> str | None:
        """Seleciona a proxima acao com base nas falhas observadas."""

        if state.consecutive_failures < node.failure_threshold:
            return None

        issues = set(state.last_issues)
        if "address_drift" in issues:
            if node.sync_public_address_command and state.last_action != "sync_public_address":
                return "sync_public_address"
            if node.recreate_on_address_drift and node.recreate_command:
                return "recreate_container"
            return "restart_container"

        if (
            {"configured_port_mismatch", "api_external_address_mismatch"} & issues
            and not {"port_closed", "quic_misconfigured"} & issues
        ):
            if state.last_action != "restart_container":
                return "restart_container"
            if (
                state.consecutive_failures >= node.container_restart_threshold
                and state.last_action != "restart_host_shim_service"
                and node.host_shim_service
            ):
                return "restart_host_shim_service"

        if {"port_closed", "quic_misconfigured"} & issues:
            if state.consecutive_failures >= node.container_restart_threshold:
                return "restart_container"
            if (
                state.consecutive_failures >= node.failure_threshold + 2
                and state.last_action != "restart_port_forward_service"
                and state.last_action != "restart_host_shim_service"
            ):
                return "restart_port_forward_service"
            if (
                state.consecutive_failures >= node.failure_threshold + 3
                and state.last_action != "restart_host_shim_service"
                and node.host_shim_service
            ):
                return "restart_host_shim_service"
            if state.last_action not in {
                "sync_port_forward",
                "restart_port_forward_service",
                "restart_host_shim_service",
                "restart_container",
            }:
                return "sync_port_forward"

        if "api_down" in issues and state.consecutive_failures >= node.container_restart_threshold:
            return "restart_container"

        if "last_ping_stale" in issues and state.consecutive_failures >= node.container_restart_threshold:
            return "restart_container"

        return None

    def perform_action(self, node: StorjNodeDef, state: StorjNodeState, action: str) -> bool:
        """Executa uma acao corretiva obedecendo cooldown e rate limit."""

        now = time.time()
        if now - state.hour_window_start > 3600:
            state.actions_this_hour = 0
            state.hour_window_start = now

        if state.actions_this_hour >= MAX_ACTIONS_PER_HOUR:
            detail = f"max {MAX_ACTIONS_PER_HOUR} actions per hour exceeded"
            log.warning("RATE LIMIT: %s", detail)
            self._audit(node.name, "rate_limited", False, detail)
            return False

        if now - state.last_action_at < ACTION_COOLDOWN:
            detail = f"cooldown active after {state.last_action}"
            log.info("COOLDOWN: %s", detail)
            self._audit(node.name, "cooldown", False, detail)
            return False

        command_map = {
            "sync_public_address": node.sync_public_address_command,
            "sync_port_forward": node.port_forward_command,
            "restart_port_forward_service": f"systemctl restart {node.port_forward_service}",
            "restart_host_shim_service": f"systemctl restart {node.host_shim_service}",
            "restart_container": f"docker restart {node.container_name}",
            "recreate_container": node.recreate_command,
        }
        command = command_map.get(action, "")
        if not command:
            self._audit(node.name, action, False, "missing command")
            return False

        if self.dry_run:
            self._record_action(state, action)
            self._audit(node.name, action, True, f"dry-run: {command}")
            log.info("DRY-RUN: would execute %s", command)
            return True

        success, output = self._run_command(command)
        self._record_action(state, action)
        self._audit(node.name, action, success, output)
        if success:
            log.warning("SELF-HEAL: %s executed successfully", action)
        else:
            log.error("SELF-HEAL: %s failed: %s", action, output)
        return success

    def check_node(self, node_name: str) -> bool:
        """Executa todos os checks do no e dispara self-heal se necessario."""

        node = self.nodes[node_name]
        state = self.states[node_name]
        if not node.enabled:
            state.up = False
            state.last_check = time.time()
            return False

        payload = self.fetch_api_payload(node.api_url)
        expected_external_address = self.resolve_expected_external_address(node)
        quic_status = payload.get("quicStatus") if payload else None
        state.api_up = payload is not None
        state.quic_ok = quic_status == "OK"
        state.last_quic_status = quic_status if quic_status is not None else "unknown"
        state.configured_port = parse_port(payload.get("configuredPort") if payload else None)
        state.expected_external_address = expected_external_address
        state.api_external_address = (
            payload.get("contact", {}).get("externalAddress") if payload else None
        )
        state.container_address = self.read_container_address(node.container_name)
        state.config_address = self.read_config_external_address(node.config_path)
        state.port_open = self.probe_tcp_port(node.probe_host, node.probe_port)

        state.address_drift = any(
            address not in (None, expected_external_address)
            for address in (state.container_address, state.config_address)
        )
        state.api_external_address_ok = (
            not node.api_external_address_required
            or state.api_external_address in (None, expected_external_address)
        )

        last_ping_at = parse_timestamp(payload.get("lastPinged") if payload else None)
        if last_ping_at is not None:
            state.last_ping_age_seconds = max(
                0.0,
                (datetime.now(timezone.utc) - last_ping_at).total_seconds(),
            )
        else:
            state.last_ping_age_seconds = 0.0

        has_fresh_ping = (
            state.api_up
            and state.last_ping_age_seconds <= node.max_last_ping_age_seconds
        )
        port_effectively_open = state.port_open or (state.quic_ok and has_fresh_ping)

        issues: list[str] = []
        if not state.api_up:
            issues.append("api_down")
        if state.address_drift:
            issues.append("address_drift")
        if not port_effectively_open:
            issues.append("port_closed")
        if state.last_quic_status == "Misconfigured":
            issues.append("quic_misconfigured")
        if state.api_up and state.api_external_address not in (None, expected_external_address):
            issues.append("api_external_address_mismatch")
        if (
            state.api_up
            and state.last_ping_age_seconds > node.max_last_ping_age_seconds
        ):
            issues.append("last_ping_stale")
        if (
            state.api_up
            and state.configured_port is not None
            and state.configured_port != node.probe_port
        ):
            issues.append("configured_port_mismatch")

        state.last_issues = issues
        state.last_check = time.time()

        healthy = not issues
        if healthy:
            if state.consecutive_failures > 0:
                self._audit(node.name, "recovered", True, f"after {state.consecutive_failures} failures")
                log.info("RECOVERED: %s healthy again", node.name)
            state.consecutive_failures = 0
            state.up = True
        else:
            state.consecutive_failures += 1
            state.up = False
            log.warning(
                "UNHEALTHY: %s issues=%s failures=%d",
                node.name,
                issues,
                state.consecutive_failures,
            )
            action = self.decide_action(node, state)
            if action:
                self.perform_action(node, state, action)

        return healthy

    def check_all(self) -> None:
        """Executa checks em todos os nos monitorados."""

        with self._lock:
            for node_name in self.nodes:
                try:
                    self.check_node(node_name)
                except Exception as exc:  # pragma: no cover - safety net
                    log.exception("CHECK ERROR for %s: %s", node_name, exc)
            self._rotate_audit_if_needed()

    def get_summary(self) -> dict[str, Any]:
        """Retorna o resumo de estado de todos os nos."""

        summary: dict[str, Any] = {}
        with self._lock:
            for node_name, state in self.states.items():
                summary[node_name] = {
                    "up": state.up,
                    "api_up": state.api_up,
                    "quic_ok": state.quic_ok,
                    "port_open": state.port_open,
                    "address_drift": state.address_drift,
                    "api_external_address_ok": state.api_external_address_ok,
                    "quic_status": state.last_quic_status,
                    "last_ping_age_seconds": round(state.last_ping_age_seconds, 2),
                    "consecutive_failures": state.consecutive_failures,
                    "last_action": state.last_action,
                    "actions_total": state.actions_total,
                    "expected_external_address": state.expected_external_address,
                    "container_address": state.container_address,
                    "config_address": state.config_address,
                    "api_external_address": state.api_external_address,
                    "configured_port": state.configured_port,
                    "issues": state.last_issues,
                    "last_check": datetime.fromtimestamp(
                        state.last_check,
                        tz=timezone.utc,
                    ).isoformat() if state.last_check else None,
                }
        return summary


def setup_prometheus_metrics() -> dict[str, Any] | None:
    """Cria metricas Prometheus se a dependencia estiver presente."""

    if not HAS_PROM:
        return None
    return {
        "up": Gauge("storj_node_health", "Estado geral do Storj (1=ok)", ["name"]),
        "api_up": Gauge("storj_node_api_up", "API do Storj acessivel (1=sim)", ["name"]),
        "quic_ok": Gauge("storj_node_quic_ok", "QUIC funcional (1=sim)", ["name"]),
        "port_open": Gauge("storj_node_port_open", "Porta do no acessivel (1=sim)", ["name"]),
        "address_drift": Gauge(
            "storj_node_address_drift",
            "Drift entre config/ADDRESS e endereco esperado (1=sim)",
            ["name"],
        ),
        "api_external_address_ok": Gauge(
            "storj_node_api_external_address_ok",
            "Endereco anunciado pela API bate com o esperado (1=sim)",
            ["name"],
        ),
        "last_ping_age": Gauge(
            "storj_node_last_ping_age_seconds",
            "Segundos desde o ultimo ping confirmado",
            ["name"],
        ),
        "consecutive_failures": Gauge(
            "storj_node_consecutive_failures",
            "Falhas consecutivas detectadas",
            ["name"],
        ),
        "actions_total": Counter(
            "storj_selfheal_actions_total",
            "Total de acoes de self-heal",
            ["name", "action"],
        ),
    }


_action_counter_sync: dict[tuple[str, str], int] = {}


def update_prometheus(checker: StorjHealthChecker, prom_metrics: dict[str, Any] | None) -> None:
    """Atualiza as metricas Prometheus com o estado atual."""

    if not prom_metrics:
        return
    for node_name, state in checker.states.items():
        prom_metrics["up"].labels(name=node_name).set(1 if state.up else 0)
        prom_metrics["api_up"].labels(name=node_name).set(1 if state.api_up else 0)
        prom_metrics["quic_ok"].labels(name=node_name).set(1 if state.quic_ok else 0)
        prom_metrics["port_open"].labels(name=node_name).set(1 if state.port_open else 0)
        prom_metrics["address_drift"].labels(name=node_name).set(1 if state.address_drift else 0)
        prom_metrics["api_external_address_ok"].labels(name=node_name).set(
            1 if state.api_external_address_ok else 0
        )
        prom_metrics["last_ping_age"].labels(name=node_name).set(state.last_ping_age_seconds)
        prom_metrics["consecutive_failures"].labels(name=node_name).set(state.consecutive_failures)
        for action_name, total in state.actions_total.items():
            key = (node_name, action_name)
            previous = _action_counter_sync.get(key, 0)
            if total > previous:
                prom_metrics["actions_total"].labels(
                    name=node_name,
                    action=action_name,
                ).inc(total - previous)
                _action_counter_sync[key] = total


class StatusHandler(BaseHTTPRequestHandler):
    """Expõe endpoints simples de status para o exporter."""

    checker: StorjHealthChecker | None = None

    def do_GET(self) -> None:
        """Atende requests GET de health, status e audit."""

        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))
            return

        if self.path == "/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = self.checker.get_summary() if self.checker else {}
            self.wfile.write(json.dumps(payload, indent=2).encode("utf-8"))
            return

        if self.path.startswith("/audit"):
            self._serve_audit()
            return

        self.send_response(404)
        self.end_headers()

    def _serve_audit(self) -> None:
        """Retorna as ultimas entradas do audit log."""

        try:
            lines: list[str] = []
            if AUDIT_LOG.is_file():
                with AUDIT_LOG.open(encoding="utf-8") as handle:
                    lines = list(collections.deque(handle, maxlen=50))
            entries = [json.loads(line) for line in lines if line.strip()]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(entries, indent=2).encode("utf-8"))
        except (OSError, ValueError) as exc:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(exc).encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:
        """Silencia access log do servidor embutido."""

        return None


def main() -> None:
    """Inicializa metrics, status API e loop principal de checks."""

    parser = argparse.ArgumentParser(description="Storj self-heal exporter")
    parser.add_argument("--port", type=int, default=9112, help="porta Prometheus")
    parser.add_argument("--status-port", type=int, default=9113, help="porta status/audit")
    parser.add_argument("--config", type=str, default="", help="arquivo JSON de configuracao")
    parser.add_argument("--interval", type=int, default=CHECK_INTERVAL, help="intervalo entre checks")
    parser.add_argument("--dry-run", action="store_true", help="nao executa acoes corretivas")
    args = parser.parse_args()

    checker = StorjHealthChecker(load_node_config(args.config), dry_run=args.dry_run)

    prom_metrics = setup_prometheus_metrics()
    if prom_metrics:
        start_http_server(args.port)
        log.info("Prometheus metrics on :%d", args.port)
    else:
        log.warning("prometheus_client not installed - metrics disabled")

    StatusHandler.checker = checker
    status_server = HTTPServer(("0.0.0.0", args.status_port), StatusHandler)
    status_thread = threading.Thread(target=status_server.serve_forever, daemon=True)
    status_thread.start()
    log.info("Status API on :%d (/health, /status, /audit)", args.status_port)

    stop_event = threading.Event()

    def shutdown(sig: int, _frame: Any) -> None:
        log.info("Shutting down on signal %s", sig)
        stop_event.set()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    log.info("Starting Storj health-check loop (interval=%ds dry_run=%s)", args.interval, args.dry_run)
    while not stop_event.is_set():
        try:
            checker.check_all()
            update_prometheus(checker, prom_metrics)
            summary = checker.get_summary()
            statuses = {name: ("UP" if item["up"] else "DOWN") for name, item in summary.items()}
            log.info("Status: %s", statuses)
        except Exception as exc:  # pragma: no cover - safety net
            log.exception("Storj check loop error: %s", exc)
        stop_event.wait(args.interval)

    status_server.shutdown()
    log.info("Storj self-heal stopped")


if __name__ == "__main__":
    main()
