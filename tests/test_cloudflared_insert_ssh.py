"""Testes do helper de inserção de ingress SSH no cloudflared."""

from __future__ import annotations

from pathlib import Path

from scripts.cloudflared_insert_ssh import insert_ssh_ingress


def test_insert_ssh_before_http_status_fallback(tmp_path: Path) -> None:
    """Deve inserir o bloco SSH antes do fallback http_status:404."""
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
    assert content.index("hostname: ssh.rpa4all.com") < content.index("http_status:404")


def test_insert_ssh_is_idempotent(tmp_path: Path) -> None:
    """Não deve duplicar o ingress SSH quando ele já existe."""
    config_path = tmp_path / "config.yml"
    original = (
        "ingress:\n"
        "  - hostname: ssh.rpa4all.com\n"
        "    service: ssh://localhost:22\n"
        "  - service: http_status:404\n"
    )
    config_path.write_text(original, encoding="utf-8")

    insert_ssh_ingress(str(config_path))

    assert config_path.read_text(encoding="utf-8") == original


def test_insert_ssh_appends_when_no_fallback_exists(tmp_path: Path) -> None:
    """Sem fallback explícito, o bloco SSH deve ser adicionado ao final."""
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "ingress:\n"
        "  - hostname: grafana.rpa4all.com\n"
        "    service: http://127.0.0.1:3002\n",
        encoding="utf-8",
    )

    insert_ssh_ingress(str(config_path))

    content = config_path.read_text(encoding="utf-8")
    assert content.rstrip().endswith("service: ssh://localhost:22")
