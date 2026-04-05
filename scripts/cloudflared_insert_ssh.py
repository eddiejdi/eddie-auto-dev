#!/usr/bin/env python3
"""Insere ingress SSH no config cloudflared antes da linha de fallback http_status:404."""
import sys
from pathlib import Path


def insert_ssh_ingress(conf_path: str) -> None:
    """Insere entrada SSH se não existir."""
    path = Path(conf_path)
    content = path.read_text()

    if "ssh.rpa4all.com" in content:
        print("SSH ingress já presente — nada a fazer")
        return

    ssh_block = "  - hostname: ssh.rpa4all.com\n    service: ssh://localhost:22\n"

    if "http_status:404" in content:
        lines = content.splitlines(keepends=True)
        new_lines = []
        inserted = False
        for line in lines:
            if "http_status:404" in line and not inserted:
                new_lines.append(ssh_block)
                inserted = True
            new_lines.append(line)
        path.write_text("".join(new_lines))
        print("SSH ingress inserido antes do fallback http_status:404")
    else:
        # Sem fallback — appenda no final da seção ingress
        path.write_text(content.rstrip("\n") + "\n" + ssh_block)
        print("SSH ingress adicionado ao final do config")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: cloudflared_insert_ssh.py <caminho_config.yml>")
        sys.exit(1)
    insert_ssh_ingress(sys.argv[1])
