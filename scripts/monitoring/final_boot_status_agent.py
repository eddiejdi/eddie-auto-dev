#!/usr/bin/env python3
"""Resumo final de boot enviado ao Telegram via Specialized Agents API."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib import error, request

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

AGENT_NOTIFY_URL = "http://127.0.0.1:8503/notify/telegram"
AGENT_NOTIFY_LEGACY_URL = "http://127.0.0.1:8503/api/notify"

CRITICAL_SERVICES = (
    "docker",
    "nginx",
    "cloudflared-rpa4all.service",
    "homelab-lan-dhcp.service",
    "pihole.service",
    "specialized-agents-api.service",
    "secrets_agent.service",
)

OPTIONAL_SERVICES = (
    "eddie-telegram-bot.service",
    "eddie-whatsapp-bot.service",
    "storage-portal-api.service",
    "personaide-rag.service",
    "trading-guardrails-control.service",
)

LOCAL_URLS = (
    ("site", "http://127.0.0.1:8090"),
    ("openwebui", "http://127.0.0.1:3000"),
    ("grafana", "http://127.0.0.1:3002"),
    ("wikijs", "http://127.0.0.1:3009"),
    ("agents-api", "http://127.0.0.1:8503/docs"),
    ("homeassistant", "http://127.0.0.1:8123"),
    ("roundcube", "http://127.0.0.1:9080"),
)


@dataclass
class ServiceState:
    name: str
    state: str

    @property
    def ok(self) -> bool:
        return self.state == "active"


def run_command(args: list[str], timeout: int = 10) -> tuple[int, str]:
    """Executa comando e retorna exit code e stdout limpo."""
    proc = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
        check=False,
    )
    return proc.returncode, proc.stdout.strip()


def service_state(name: str) -> ServiceState:
    """Consulta o estado atual de um servico systemd."""
    rc, output = run_command(["systemctl", "is-active", name], timeout=8)
    state = output.splitlines()[-1].strip() if output else "unknown"
    if rc != 0 and not state:
        state = "unknown"
    return ServiceState(name=name, state=state)


def list_failed_units() -> list[str]:
    """Lista units em falha no systemd."""
    _, output = run_command(
        ["systemctl", "--failed", "--no-legend", "--plain", "--no-pager"],
        timeout=10,
    )
    failed: list[str] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        failed.append(line.split()[0])
    return failed


def read_first_line(args: list[str], timeout: int = 10, fallback: str = "n/a") -> str:
    """Retorna a primeira linha de um comando, com fallback."""
    try:
        _, output = run_command(args, timeout=timeout)
    except Exception:
        return fallback
    return output.splitlines()[0].strip() if output else fallback


def url_status(url: str, timeout: int = 5) -> str:
    """Retorna o status HTTP de uma URL local."""
    req = request.Request(url, headers={"User-Agent": "boot-status-agent/1.0"})
    try:
        with request.urlopen(req, timeout=timeout) as response:
            return str(response.status)
    except error.HTTPError as exc:
        return str(exc.code)
    except Exception:
        return "down"


def format_states(states: Iterable[ServiceState]) -> str:
    """Formata estados em uma linha curta."""
    parts = []
    for item in states:
        icon = "OK" if item.ok else item.state.upper()
        parts.append(f"{item.name}={icon}")
    return ", ".join(parts)


def collect_summary() -> str:
    """Monta a mensagem final de boot."""
    hostname = socket.gethostname()
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    uptime = read_first_line(["uptime", "-p"])
    boot_time = read_first_line(["systemd-analyze"])
    route = read_first_line(["sh", "-lc", "ip route show default | head -n 1"], fallback="sem rota default")

    critical = [service_state(name) for name in CRITICAL_SERVICES]
    optional = [service_state(name) for name in OPTIONAL_SERVICES]
    failed_units = list_failed_units()

    urls = []
    for name, url in LOCAL_URLS:
        urls.append(f"{name}={url_status(url)}")

    critical_failures = [item.name for item in critical if not item.ok]
    optional_issues = [item.name for item in optional if not item.ok]

    if critical_failures:
        headline = f"ALERTA boot finalizado com {len(critical_failures)} falha(s) critica(s)"
    elif failed_units or optional_issues:
        headline = f"AVISO boot finalizado com {len(optional_issues)} servico(s) degradado(s)"
    else:
        headline = "OK boot finalizado sem falhas criticas"

    lines = [
        f"[{hostname}] {headline}",
        f"Horario: {now}",
        f"Uptime: {uptime}",
        f"Boot: {boot_time}",
        f"Rota: {route}",
        f"Criticos: {format_states(critical)}",
        f"Opcionais: {format_states(optional)}",
        f"URLs: {', '.join(urls)}",
    ]

    if failed_units:
        lines.append(f"Failed units: {', '.join(failed_units[:8])}")

    return "\n".join(lines)


def post_json(url: str, payload: dict[str, object], timeout: int = 10) -> dict[str, object]:
    """POST JSON simples usando stdlib."""
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw)


def send_via_agent_api(message: str) -> dict[str, object]:
    """Envia mensagem usando a API de agents; cai no endpoint legado se preciso."""
    payload = {"message": message}
    last_error: Exception | None = None
    for url in (AGENT_NOTIFY_URL, AGENT_NOTIFY_LEGACY_URL):
        try:
            return post_json(url, payload, timeout=10)
        except Exception as exc:  # pragma: no cover - fallback path
            last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError("No notify endpoint configured")


def main() -> int:
    """Coleta status final de boot e notifica no Telegram."""
    message = collect_summary()
    print(message)
    try:
        result = send_via_agent_api(message)
        print(f"Telegram notify OK: {result}")
        return 0
    except Exception as exc:
        print(f"Telegram notify failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
