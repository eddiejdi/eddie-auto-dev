"""Testes do helper que garante rotas DNS do Cloudflare Tunnel."""

from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

from scripts.ensure_cloudflared_dns_route import ensure_dns_route, ensure_dns_routes, get_tunnel_name, main


def test_get_tunnel_name_returns_value_from_config(tmp_path: Path) -> None:
    """Deve extrair o nome do tunnel do config do cloudflared."""
    config_path = tmp_path / "config.yml"
    config_path.write_text("tunnel: rpa4all-tunnel\ningress:\n", encoding="utf-8")

    assert get_tunnel_name(config_path) == "rpa4all-tunnel"


def test_ensure_dns_route_returns_true_on_success(monkeypatch) -> None:
    """Deve considerar sucesso quando cloudflared retorna código zero."""
    monkeypatch.setattr(
        "scripts.ensure_cloudflared_dns_route.run_command",
        lambda _command: CompletedProcess(["cloudflared"], 0, "ok", ""),
    )

    assert ensure_dns_route("cloudflared", "rpa4all-tunnel", "vpn.rpa4all.com") is True


def test_ensure_dns_route_accepts_existing_route(monkeypatch) -> None:
    """Falhas idempotentes devem ser tratadas como sucesso."""
    monkeypatch.setattr(
        "scripts.ensure_cloudflared_dns_route.run_command",
        lambda _command: CompletedProcess(["cloudflared"], 1, "", "Error: record already exists"),
    )

    assert ensure_dns_route("cloudflared", "rpa4all-tunnel", "vpn.rpa4all.com") is True


def test_ensure_dns_route_returns_false_on_unexpected_error(monkeypatch) -> None:
    """Erros reais do CLI devem falhar o helper."""
    monkeypatch.setattr(
        "scripts.ensure_cloudflared_dns_route.run_command",
        lambda _command: CompletedProcess(["cloudflared"], 1, "", "permission denied"),
    )

    assert ensure_dns_route("cloudflared", "rpa4all-tunnel", "vpn.rpa4all.com") is False


def test_ensure_dns_routes_requests_all_required_hostnames(monkeypatch, tmp_path: Path) -> None:
    """Deve garantir SSH e VPN para o mesmo tunnel."""
    config_path = tmp_path / "config.yml"
    config_path.write_text("tunnel: rpa4all-tunnel\n", encoding="utf-8")
    calls: list[tuple[str, str, str]] = []

    def fake_ensure(cloudflared_bin: str, tunnel_name: str, hostname: str) -> bool:
        calls.append((cloudflared_bin, tunnel_name, hostname))
        return True

    monkeypatch.setattr("scripts.ensure_cloudflared_dns_route.ensure_dns_route", fake_ensure)

    assert ensure_dns_routes(config_path, "cloudflared") is True
    assert calls == [
        ("cloudflared", "rpa4all-tunnel", "ssh.rpa4all.com"),
        ("cloudflared", "rpa4all-tunnel", "vpn.rpa4all.com"),
    ]


def test_main_returns_error_when_config_is_missing(monkeypatch, tmp_path: Path) -> None:
    """A CLI deve falhar cedo quando o config não existe."""
    monkeypatch.setattr(
        "sys.argv",
        [
            "ensure_cloudflared_dns_route.py",
            "--config",
            str(tmp_path / "missing.yml"),
        ],
    )

    assert main() == 1