#!/usr/bin/env python3
"""Garante que o relay TCP->UDP da VPN externa esteja escutando em 51821."""

from __future__ import annotations

import argparse
import logging
import subprocess
import time
from pathlib import Path


LOGGER = logging.getLogger(__name__)
RELAY_PORT = 51821
WG_TARGET = "127.0.0.1:51824"
SERVICE_NAME = "udp-tcp-relay.service"
FALLBACK_UNIT = "udp-tcp-relay-fallback"


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Executa comando shell e retorna stdout/stderr sem lançar exceção."""
    return subprocess.run(command, capture_output=True, text=True, check=False)


def is_port_listening(port: int) -> bool:
    """Retorna True quando a porta TCP informada já está em escuta."""
    result = run_command(["ss", "-tln"])
    return f":{port} " in result.stdout or f":{port}\n" in result.stdout


def service_exists(service_name: str) -> bool:
    """Retorna True quando o unit systemd existe no host."""
    result = run_command(["systemctl", "list-unit-files", service_name])
    return result.returncode == 0


def start_systemd_service(service_name: str) -> None:
    """Reinicia ou inicia o serviço systemd do relay."""
    active = run_command(["sudo", "systemctl", "is-active", "--quiet", service_name])
    if active.returncode == 0:
        run_command(["sudo", "systemctl", "restart", service_name])
    else:
        run_command(["sudo", "systemctl", "start", service_name])


def start_fallback_unit(relay_script: Path) -> None:
    """Inicia um unit transitório do systemd como fallback operacional."""
    run_command(
        [
            "sudo",
            "systemd-run",
            "--unit",
            FALLBACK_UNIT,
            "--property",
            "Restart=always",
            "--collect",
            "/usr/bin/python3",
            str(relay_script),
            "server",
            "--tcp-listen",
            str(RELAY_PORT),
            "--udp-target",
            WG_TARGET,
        ]
    )


def wait_for_port(port: int, attempts: int = 8, delay_seconds: float = 1.0) -> bool:
    """Aguarda a porta ficar disponível por um número finito de tentativas."""
    for _ in range(attempts):
        if is_port_listening(port):
            return True
        time.sleep(delay_seconds)
    return False


def ensure_vpn_relay(relay_script: Path) -> bool:
    """Garante que o backend TCP 51821 da VPN esteja ativo."""
    if is_port_listening(RELAY_PORT):
        LOGGER.info("Relay VPN já ativo em TCP %s", RELAY_PORT)
        return True

    if service_exists(SERVICE_NAME):
        LOGGER.info("Porta %s indisponível; iniciando %s", RELAY_PORT, SERVICE_NAME)
        start_systemd_service(SERVICE_NAME)
        if wait_for_port(RELAY_PORT):
            return True

    LOGGER.warning("Serviço %s ausente ou não subiu; usando fallback transitório", SERVICE_NAME)
    start_fallback_unit(relay_script)
    return wait_for_port(RELAY_PORT)


def main() -> int:
    """CLI principal do helper operacional do relay VPN."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="Garante relay TCP->UDP da VPN externa")
    parser.add_argument("--relay-script", required=True, help="Caminho para tools/udp_tcp_relay.py")
    args = parser.parse_args()

    relay_script = Path(args.relay_script)
    if not relay_script.exists():
        LOGGER.error("Relay script não encontrado: %s", relay_script)
        return 1

    if ensure_vpn_relay(relay_script):
        LOGGER.info("Relay VPN confirmado em TCP %s", RELAY_PORT)
        return 0

    LOGGER.error("Relay VPN não ficou disponível em TCP %s", RELAY_PORT)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())