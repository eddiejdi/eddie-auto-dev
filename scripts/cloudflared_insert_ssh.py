#!/usr/bin/env python3
"""Garante ingressos SSH e VPN no config cloudflared antes do fallback."""
import sys
from pathlib import Path


REQUIRED_INGRESSES = (
    ("ssh.rpa4all.com", "ssh://localhost:22"),
    ("vpn.rpa4all.com", "tcp://localhost:51821"),
)


def insert_ssh_ingress(conf_path: str) -> None:
    """Garante os ingressos SSH e VPN sem duplicar entradas existentes."""
    path = Path(conf_path)
    content = path.read_text()

    missing_blocks = [
        f"  - hostname: {hostname}\n    service: {service}\n"
        for hostname, service in REQUIRED_INGRESSES
        if hostname not in content
    ]

    if not missing_blocks:
        print("Ingressos SSH/VPN já presentes — nada a fazer")
        return

    block = "".join(missing_blocks)

    if "http_status:404" in content:
        lines = content.splitlines(keepends=True)
        new_lines = []
        inserted = False
        for line in lines:
            if "http_status:404" in line and not inserted:
                new_lines.append(block)
                inserted = True
            new_lines.append(line)
        path.write_text("".join(new_lines))
        print("Ingressos SSH/VPN inseridos antes do fallback http_status:404")
    else:
        path.write_text(content.rstrip("\n") + "\n" + block)
        print("Ingressos SSH/VPN adicionados ao final do config")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: cloudflared_insert_ssh.py <caminho_config.yml>")
        sys.exit(1)
    insert_ssh_ingress(sys.argv[1])
