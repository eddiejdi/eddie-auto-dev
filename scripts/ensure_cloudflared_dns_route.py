#!/usr/bin/env python3
"""Garante as rotas DNS do Cloudflare Tunnel para SSH e VPN."""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
from pathlib import Path


LOGGER = logging.getLogger(__name__)
REQUIRED_HOSTNAMES = ("ssh.rpa4all.com", "vpn.rpa4all.com")
ORIGIN_CERT_CANDIDATES = (
    "/home/homelab/.cloudflared/cert.pem",
    "/etc/cloudflared/cert.pem",
)
ALREADY_EXISTS_MARKERS = (
    "already exists",
    "already routed",
    "already configured",
)


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Executa comando shell sem lançar exceção para o chamador."""
    return subprocess.run(command, capture_output=True, text=True, check=False)


def get_tunnel_name(config_path: Path) -> str | None:
    """Extrai o nome/ID do tunnel a partir do config do cloudflared."""
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("tunnel:"):
            tunnel_name = line.split(":", maxsplit=1)[1].strip()
            return tunnel_name or None
    return None


def get_origin_cert_path(explicit_path: str | None = None) -> Path | None:
    """Resolve o cert.pem necessário para comandos de route dns."""
    candidates = []
    if explicit_path:
        candidates.append(explicit_path)
    env_path = os.environ.get("TUNNEL_ORIGIN_CERT")
    if env_path:
        candidates.append(env_path)
    candidates.extend(ORIGIN_CERT_CANDIDATES)

    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return path
    return None


def ensure_dns_route(cloudflared_bin: str, tunnel_name: str, hostname: str, origin_cert: Path) -> bool:
    """Cria a rota DNS do hostname para o tunnel quando necessário."""
    result = run_command(
        [
            cloudflared_bin,
            "tunnel",
            "--origincert",
            str(origin_cert),
            "route",
            "dns",
            tunnel_name,
            hostname,
        ]
    )
    if result.returncode == 0:
        LOGGER.info("Hostname %s roteado para tunnel %s", hostname, tunnel_name)
        return True

    combined_output = f"{result.stdout}\n{result.stderr}".lower()
    if any(marker in combined_output for marker in ALREADY_EXISTS_MARKERS):
        LOGGER.info("Hostname %s já possui rota DNS no tunnel %s", hostname, tunnel_name)
        return True

    LOGGER.error("Falha ao criar rota DNS para %s: %s", hostname, combined_output.strip())
    return False


def ensure_dns_routes(config_path: Path, cloudflared_bin: str, origin_cert: Path) -> bool:
    """Garante todas as rotas DNS necessárias para o tunnel principal."""
    tunnel_name = get_tunnel_name(config_path)
    if not tunnel_name:
        LOGGER.error("Campo 'tunnel:' não encontrado em %s", config_path)
        return False

    return all(ensure_dns_route(cloudflared_bin, tunnel_name, hostname, origin_cert) for hostname in REQUIRED_HOSTNAMES)


def main() -> int:
    """CLI principal do helper de rotas DNS do Cloudflare Tunnel."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="Garante rotas DNS do Cloudflare Tunnel")
    parser.add_argument("--config", required=True, help="Caminho para o config.yml do cloudflared")
    parser.add_argument("--cloudflared-bin", default="cloudflared", help="Binário cloudflared a executar")
    parser.add_argument("--origincert", help="Caminho explícito para o cert.pem do Cloudflare Tunnel")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        LOGGER.error("Config do cloudflared não encontrado: %s", config_path)
        return 1

    origin_cert = get_origin_cert_path(args.origincert)
    if not origin_cert:
        LOGGER.error("cert.pem do Cloudflare Tunnel não encontrado")
        return 1

    if ensure_dns_routes(config_path, args.cloudflared_bin, origin_cert):
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())