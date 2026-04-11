#!/usr/bin/env python3
"""Sincroniza o endereco externo do Storj com o IP publico atual.

Atualiza o `contact.external-address` no config.yaml e, quando necessario,
recria o container com a env `ADDRESS` corrigida preservando rede macvlan,
bind mounts e politica de restart.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [storj-sync] %(message)s")
log = logging.getLogger("storj-sync")

PUBLIC_IP_URLS = [
    "https://api.ipify.org",
    "https://ifconfig.me/ip",
    "https://checkip.amazonaws.com",
]


def detect_public_ip(urls: list[str]) -> str:
    """Descobre o IP publico atual consultando endpoints simples."""

    for url in urls:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "storj-sync/1.0"})
            with urllib.request.urlopen(request, timeout=8) as response:
                value = response.read().decode("utf-8").strip()
            if value:
                return value
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            continue
    raise RuntimeError("Nao foi possivel descobrir o IP publico atual")


def detect_container_public_ip(container_name: str, urls: list[str]) -> str:
    """Descobre o IP publico observado pelo container Storj."""

    for url in urls:
        command = [
            "docker",
            "exec",
            container_name,
            "wget",
            "-qO-",
            "--timeout=8",
            "-U",
            "storj-sync/1.0",
            url,
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        value = result.stdout.strip()
        if result.returncode == 0 and value and "<html" not in value.lower():
            return value
    raise RuntimeError("Nao foi possivel descobrir o IP publico a partir do container")


def build_updated_config_text(original_text: str, external_address: str) -> str:
    """Atualiza ou adiciona a linha `contact.external-address` no config."""

    lines = original_text.splitlines()
    updated_lines: list[str] = []
    replaced = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("contact.external-address:"):
            indent = line[: len(line) - len(line.lstrip())]
            updated_lines.append(f'{indent}contact.external-address: "{external_address}"')
            replaced = True
        else:
            updated_lines.append(line)
    if not replaced:
        updated_lines.append(f'contact.external-address: "{external_address}"')
    return "\n".join(updated_lines) + "\n"


def load_container_inspect(container_name: str) -> dict[str, Any]:
    """Retorna o JSON completo de `docker inspect` do container informado."""

    result = subprocess.run(
        ["docker", "inspect", container_name],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"docker inspect falhou para {container_name}")
    payload = json.loads(result.stdout)
    if not payload:
        raise RuntimeError(f"docker inspect retornou vazio para {container_name}")
    return payload[0]


def build_recreate_command(inspect_payload: dict[str, Any], external_address: str) -> list[str]:
    """Monta o comando `docker run` preservando parametros essenciais do container."""

    config = inspect_payload["Config"]
    host_config = inspect_payload["HostConfig"]
    networks = inspect_payload["NetworkSettings"]["Networks"]
    network_name = next(iter(networks))
    network_config = networks[network_name]
    restart_name = host_config.get("RestartPolicy", {}).get("Name") or "unless-stopped"
    env_vars = [env for env in config.get("Env", []) if not env.startswith("ADDRESS=")]
    env_vars.append(f"ADDRESS={external_address}")

    command = [
        "docker",
        "run",
        "-d",
        "--name",
        inspect_payload["Name"].lstrip("/"),
        "--restart",
        restart_name,
        "--network",
        network_name,
    ]

    ipv4_address = network_config.get("IPAMConfig", {}).get("IPv4Address") or network_config.get("IPAddress")
    if ipv4_address:
        command.extend(["--ip", ipv4_address])

    for bind in host_config.get("Binds", []) or []:
        command.extend(["-v", bind])
    for env_var in env_vars:
        command.extend(["-e", env_var])

    entrypoint = config.get("Entrypoint") or []
    if len(entrypoint) > 1:
        raise RuntimeError("Entrypoint complexo nao suportado automaticamente")
    if len(entrypoint) == 1:
        command.extend(["--entrypoint", entrypoint[0]])

    command.append(config["Image"])
    for item in config.get("Cmd") or []:
        command.append(item)
    return command


def run_command(command: list[str]) -> str:
    """Executa um comando e retorna a saida principal."""

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "comando falhou")
    return result.stdout.strip()


def sync_public_address(container_name: str, config_path: str, port: int) -> str:
    """Sincroniza config e container do Storj com o IP publico atual."""

    try:
        public_ip = detect_container_public_ip(container_name, PUBLIC_IP_URLS)
        log.info("IP publico resolvido pelo container %s: %s", container_name, public_ip)
    except RuntimeError:
        public_ip = detect_public_ip(PUBLIC_IP_URLS)
        log.info("IP publico resolvido pelo host: %s", public_ip)
    external_address = f"{public_ip}:{port}"
    config_file = Path(config_path)
    updated_text = build_updated_config_text(
        config_file.read_text(encoding="utf-8"),
        external_address,
    )
    config_file.write_text(updated_text, encoding="utf-8")

    inspect_payload = load_container_inspect(container_name)
    current_address = next(
        (env.split("=", 1)[1] for env in inspect_payload["Config"].get("Env", []) if env.startswith("ADDRESS=")),
        "",
    )
    if current_address == external_address:
        log.info("Container ADDRESS ja esta sincronizado em %s", external_address)
        return external_address

    recreate_command = build_recreate_command(inspect_payload, external_address)
    run_command(["docker", "rm", "-f", container_name])
    run_command(recreate_command)
    log.info("Container recriado com ADDRESS=%s", external_address)
    return external_address


def main() -> None:
    """Executa a sincronizacao do endereco publico do Storj."""

    parser = argparse.ArgumentParser(description="Sincroniza ADDRESS do Storj com IP publico atual")
    parser.add_argument("--container", required=True, help="nome do container Storj")
    parser.add_argument("--config", required=True, help="caminho do config.yaml")
    parser.add_argument("--port", type=int, required=True, help="porta publica do Storj")
    args = parser.parse_args()

    address = sync_public_address(args.container, args.config, args.port)
    print(address)


if __name__ == "__main__":
    main()