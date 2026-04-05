#!/usr/bin/env python3
"""Renderiza configuração de cliente WireGuard em arquivo local."""

from __future__ import annotations

import argparse
from pathlib import Path


DEFAULT_ALLOWED_IPS: tuple[str, ...] = (
    "192.168.15.0/24",
    "10.66.66.0/24",
)


def render_client_config(
    private_key: str,
    client_ip: str,
    server_public_key: str,
    endpoint_host: str,
    endpoint_port: str,
    *,
    dns: str = "1.1.1.1",
    allowed_ips: tuple[str, ...] = DEFAULT_ALLOWED_IPS,
) -> str:
    """Retorna o conteúdo da configuração do cliente WireGuard."""
    allowed_ips_value = ", ".join(allowed_ips)
    return (
        "[Interface]\n"
        f"PrivateKey = {private_key}\n"
        f"Address = {client_ip}/24\n"
        f"DNS = {dns}\n\n"
        "[Peer]\n"
        f"PublicKey = {server_public_key}\n"
        f"AllowedIPs = {allowed_ips_value}\n"
        f"Endpoint = {endpoint_host}:{endpoint_port}\n"
        "PersistentKeepalive = 25\n"
    )


def write_client_config(output_path: str, content: str) -> None:
    """Grava a configuração em disco com permissão restrita."""
    path = Path(output_path)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o600)


def parse_args() -> argparse.Namespace:
    """Converte argumentos de linha de comando para namespace."""
    parser = argparse.ArgumentParser(description="Renderiza config de cliente WireGuard")
    parser.add_argument("--private-key", required=True)
    parser.add_argument("--client-ip", required=True)
    parser.add_argument("--server-public-key", required=True)
    parser.add_argument("--endpoint-host", required=True)
    parser.add_argument("--endpoint-port", required=True)
    parser.add_argument("--dns", default="1.1.1.1")
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    """Executa o renderer e grava o arquivo de configuração."""
    args = parse_args()
    content = render_client_config(
        args.private_key,
        args.client_ip,
        args.server_public_key,
        args.endpoint_host,
        args.endpoint_port,
        dns=args.dns,
    )
    write_client_config(args.output, content)
    print(f"wireguard_client_config_written={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())