#!/usr/bin/env python3
"""Garante ingressos SSH e VPN no config cloudflared antes do fallback."""

from __future__ import annotations

import sys
from pathlib import Path


REQUIRED_INGRESSES = (
    ("ssh.rpa4all.com", "ssh://localhost:22"),
    ("vpn.rpa4all.com", "tcp://localhost:51821"),
)


def insert_ssh_ingress(conf_path: str) -> None:
    """Garante os ingressos SSH e VPN antes do wildcard/fallback."""
    path = Path(conf_path)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

    cleaned_lines: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        matching_hostnames = [hostname for hostname, _service in REQUIRED_INGRESSES if stripped == f"- hostname: {hostname}"]
        if matching_hostnames:
            index += 1
            if index < len(lines) and lines[index].strip().startswith("service:"):
                index += 1
            continue
        cleaned_lines.append(line)
        index += 1

    required_block: list[str] = []
    for hostname, service in REQUIRED_INGRESSES:
        required_block.extend(
            [
                f"  - hostname: {hostname}\n",
                f"    service: {service}\n",
            ]
        )

    insert_at = None
    inserted_before = "final"
    for index, line in enumerate(cleaned_lines):
        stripped = line.strip()
        if stripped == "- hostname: '*.rpa4all.com'":
            insert_at = index
            inserted_before = "wildcard"
            break
        if "http_status:404" in stripped:
            insert_at = index
            inserted_before = "fallback http_status:404"
            break

    if insert_at is None:
        new_lines = cleaned_lines + required_block
    else:
        new_lines = cleaned_lines[:insert_at] + required_block + cleaned_lines[insert_at:]

    new_content = "".join(new_lines)
    old_content = path.read_text(encoding="utf-8")
    if new_content == old_content:
        print("Ingressos SSH/VPN já presentes — nada a fazer")
        return

    path.write_text(new_content, encoding="utf-8")
    if inserted_before == "final":
        print("Ingressos SSH/VPN adicionados ao final do config")
    else:
        print(f"Ingressos SSH/VPN inseridos antes do {inserted_before}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: cloudflared_insert_ssh.py <caminho_config.yml>")
        sys.exit(1)
    insert_ssh_ingress(sys.argv[1])
