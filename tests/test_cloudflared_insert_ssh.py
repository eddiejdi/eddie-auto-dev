"""Testes do helper de inserção de ingress SSH no cloudflared."""

from __future__ import annotations

from pathlib import Path

from scripts.cloudflared_insert_ssh import insert_ssh_ingress


def test_insert_ssh_before_http_status_fallback(tmp_path: Path) -> None:
    """Deve inserir os blocos SSH e VPN antes do fallback http_status:404."""
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "ingress:\n"
        "  - hostname: nextcloud.rpa4all.com\n"
        "    service: http://127.0.0.1:8880\n"
        "  - service: http_status:404\n",
        encoding="utf-8",
    )

    insert_ssh_ingress(str(config_path))

    content = config_path.read_text(encoding="utf-8")
    assert "hostname: ssh.rpa4all.com" in content
    assert "hostname: vpn.rpa4all.com" in content
    assert content.index("hostname: ssh.rpa4all.com") < content.index("http_status:404")
    assert content.index("hostname: vpn.rpa4all.com") < content.index("http_status:404")


def test_insert_ssh_is_idempotent(tmp_path: Path) -> None:
    """Não deve duplicar ingressos quando SSH e VPN já existem."""
    config_path = tmp_path / "config.yml"
    original = (
        "ingress:\n"
        "  - hostname: ssh.rpa4all.com\n"
        "    service: ssh://localhost:22\n"
        "  - hostname: vpn.rpa4all.com\n"
        "    service: tcp://localhost:51821\n"
        "  - service: http_status:404\n"
    )
    config_path.write_text(original, encoding="utf-8")

    insert_ssh_ingress(str(config_path))

    assert config_path.read_text(encoding="utf-8") == original


def test_insert_ssh_appends_when_no_fallback_exists(tmp_path: Path) -> None:
    """Sem fallback explícito, os blocos obrigatórios devem ir ao final."""
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "ingress:\n"
        "  - hostname: grafana.rpa4all.com\n"
        "    service: http://127.0.0.1:3002\n",
        encoding="utf-8",
    )

    insert_ssh_ingress(str(config_path))

    content = config_path.read_text(encoding="utf-8")
    assert "hostname: ssh.rpa4all.com" in content
    assert content.rstrip().endswith("service: tcp://localhost:51821")


def test_insert_ssh_adds_missing_vpn_when_ssh_already_exists(tmp_path: Path) -> None:
    """Deve reinserir VPN mesmo quando o SSH já estiver presente."""
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "ingress:\n"
        "  - hostname: ssh.rpa4all.com\n"
        "    service: ssh://localhost:22\n"
        "  - service: http_status:404\n",
        encoding="utf-8",
    )

    insert_ssh_ingress(str(config_path))

    content = config_path.read_text(encoding="utf-8")
    assert content.count("hostname: ssh.rpa4all.com") == 1
    assert "hostname: vpn.rpa4all.com" in content
    assert content.index("hostname: vpn.rpa4all.com") < content.index("http_status:404")


def test_insert_ssh_repositions_entries_before_wildcard(tmp_path: Path) -> None:
    """Entradas específicas devem ficar antes do wildcard *.rpa4all.com."""
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "ingress:\n"
        "  - hostname: '*.rpa4all.com'\n"
        "    service: http://localhost:8090\n"
        "  - hostname: ssh.rpa4all.com\n"
        "    service: ssh://localhost:22\n"
        "  - hostname: vpn.rpa4all.com\n"
        "    service: tcp://localhost:51821\n"
        "  - service: http_status:404\n",
        encoding="utf-8",
    )

    insert_ssh_ingress(str(config_path))

    content = config_path.read_text(encoding="utf-8")
    assert content.index("hostname: ssh.rpa4all.com") < content.index("hostname: '*.rpa4all.com'")
    assert content.index("hostname: vpn.rpa4all.com") < content.index("hostname: '*.rpa4all.com'")
    assert content.count("hostname: ssh.rpa4all.com") == 1
    assert content.count("hostname: vpn.rpa4all.com") == 1
