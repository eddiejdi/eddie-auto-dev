"""Testes do helper operacional que garante o relay da VPN externa."""

from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import MagicMock

from scripts.ensure_vpn_relay import ensure_vpn_relay, main


def test_ensure_vpn_relay_returns_immediately_when_port_is_listening(monkeypatch) -> None:
    """Não deve reiniciar nada se a porta 51821 já estiver ativa."""
    calls: list[str] = []

    monkeypatch.setattr("scripts.ensure_vpn_relay.is_port_listening", lambda port: calls.append(f"listen:{port}") or True)
    monkeypatch.setattr("scripts.ensure_vpn_relay.service_exists", lambda _name: False)
    monkeypatch.setattr("scripts.ensure_vpn_relay.start_systemd_service", lambda _name: calls.append("start-service"))
    monkeypatch.setattr("scripts.ensure_vpn_relay.start_fallback_unit", lambda _path: calls.append("fallback"))

    assert ensure_vpn_relay(Path("tools/udp_tcp_relay.py")) is True
    assert calls == ["listen:51821"]


def test_ensure_vpn_relay_starts_systemd_service_when_available(monkeypatch) -> None:
    """Deve usar o unit dedicado quando ele existe no homelab."""
    listen_states = iter([False, True])
    actions: list[str] = []

    monkeypatch.setattr("scripts.ensure_vpn_relay.is_port_listening", lambda _port: next(listen_states))
    monkeypatch.setattr("scripts.ensure_vpn_relay.service_exists", lambda _name: True)
    monkeypatch.setattr("scripts.ensure_vpn_relay.start_systemd_service", lambda name: actions.append(name))
    monkeypatch.setattr("scripts.ensure_vpn_relay.wait_for_port", lambda _port: True)
    monkeypatch.setattr("scripts.ensure_vpn_relay.start_fallback_unit", lambda _path: actions.append("fallback"))

    assert ensure_vpn_relay(Path("tools/udp_tcp_relay.py")) is True
    assert actions == ["udp-tcp-relay.service"]


def test_ensure_vpn_relay_uses_fallback_when_service_is_missing(monkeypatch) -> None:
    """Sem unit systemd, deve subir o relay por unit transitório."""
    actions: list[str] = []

    monkeypatch.setattr("scripts.ensure_vpn_relay.is_port_listening", lambda _port: False)
    monkeypatch.setattr("scripts.ensure_vpn_relay.service_exists", lambda _name: False)
    monkeypatch.setattr("scripts.ensure_vpn_relay.start_systemd_service", lambda name: actions.append(name))
    monkeypatch.setattr("scripts.ensure_vpn_relay.start_fallback_unit", lambda path: actions.append(str(path)))
    monkeypatch.setattr("scripts.ensure_vpn_relay.wait_for_port", lambda _port: True)

    assert ensure_vpn_relay(Path("tools/udp_tcp_relay.py")) is True
    assert actions == ["tools/udp_tcp_relay.py"]


def test_main_returns_error_when_relay_script_is_missing(monkeypatch, tmp_path: Path) -> None:
    """A CLI deve falhar cedo se o script do relay não existir."""
    monkeypatch.setattr("sys.argv", ["ensure_vpn_relay.py", "--relay-script", str(tmp_path / "missing.py")])

    assert main() == 1


def test_start_systemd_service_restarts_active_service(monkeypatch) -> None:
    """Serviço ativo deve ser reiniciado para recuperar backend quebrado."""
    commands: list[list[str]] = []

    def fake_run(command: list[str]) -> CompletedProcess[str]:
        commands.append(command)
        if command[:4] == ["sudo", "systemctl", "is-active", "--quiet"]:
            return CompletedProcess(command, 0, "", "")
        return CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("scripts.ensure_vpn_relay.run_command", fake_run)

    from scripts.ensure_vpn_relay import start_systemd_service

    start_systemd_service("udp-tcp-relay.service")

    assert commands == [
        ["sudo", "systemctl", "is-active", "--quiet", "udp-tcp-relay.service"],
        ["sudo", "systemctl", "restart", "udp-tcp-relay.service"],
    ]