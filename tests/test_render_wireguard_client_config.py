"""Testes do renderer de configuração cliente WireGuard."""

from __future__ import annotations

from pathlib import Path

from scripts.render_wireguard_client_config import render_client_config, write_client_config


def test_render_client_config_contains_expected_fields() -> None:
    """Deve renderizar interface e peer com os campos esperados."""
    rendered = render_client_config(
        "priv-key",
        "10.66.66.20",
        "server-pub",
        "vpn.rpa4all.com",
        "51820",
    )

    assert "PrivateKey = priv-key" in rendered
    assert "Address = 10.66.66.20/24" in rendered
    assert "PublicKey = server-pub" in rendered
    assert "Endpoint = vpn.rpa4all.com:51820" in rendered
    assert "AllowedIPs = 192.168.15.0/24, 10.66.66.0/24" in rendered


def test_write_client_config_uses_restricted_permissions(tmp_path: Path) -> None:
    """O arquivo gerado deve ficar com permissão 600."""
    output_path = tmp_path / "client.conf"

    write_client_config(str(output_path), "[Interface]\n")

    assert output_path.read_text(encoding="utf-8") == "[Interface]\n"
    assert oct(output_path.stat().st_mode & 0o777) == "0o600"