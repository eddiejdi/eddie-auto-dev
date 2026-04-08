"""Testes para o modo on-demand do workstation Win11L."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).parent.parent
RUNNER = ROOT / "systemd" / "workstation-win11l-run.sh"
HTTP_SOCKET = ROOT / "systemd" / "workstation-win11l-http.socket"
HTTP_SERVICE = ROOT / "systemd" / "workstation-win11l-http@.service"
RDP_SOCKET = ROOT / "systemd" / "workstation-win11l-rdp.socket"
RDP_SERVICE = ROOT / "systemd" / "workstation-win11l-rdp@.service"
SEED_SCRIPT = ROOT / "tools" / "seed_workstation_boot_iso.sh"


def test_runner_uses_internal_ports() -> None:
    content = RUNNER.read_text()
    assert "-p 127.0.0.1:${WEB_PORT}:8006" in content
    assert "-p 127.0.0.1:${RDP_PORT}:3389/tcp" in content
    assert "-p 127.0.0.1:${RDP_PORT}:3389/udp" in content
    assert "if [ -f /opt/workstation-win11l/storage/boot.iso ]; then" in content
    assert "-v /opt/workstation-win11l/storage/boot.iso:/boot.iso" in content
    assert "--restart no" in content


def test_runner_bash_syntax_valid() -> None:
    result = subprocess.run(["bash", "-n", str(RUNNER)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_seed_script_stages_boot_iso() -> None:
    content = SEED_SCRIPT.read_text()
    assert 'wget -c "$ISO_URL" -O "$LOCAL_ISO"' in content
    assert 'REMOTE_BOOT_ISO="${REMOTE_BOOT_ISO:-/opt/workstation-win11l/storage/boot.iso}"' in content
    assert 'docker stop workstation-win11l >/dev/null 2>&1 || true' in content
    assert 'curl -fsS http://127.0.0.1:8400/ >/dev/null' in content


def test_seed_script_bash_syntax_valid() -> None:
    result = subprocess.run(["bash", "-n", str(SEED_SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_http_socket_listens_public_port() -> None:
    content = HTTP_SOCKET.read_text()
    assert "ListenStream=127.0.0.1:8400" in content
    assert "Accept=yes" in content
    assert "WantedBy=sockets.target" in content


def test_http_service_proxies_internal_port() -> None:
    content = HTTP_SERVICE.read_text()
    assert "ExecStartPre=/usr/local/bin/workstation-win11l-run.sh" in content
    assert "curl -fsS -o /dev/null --max-time 2 http://127.0.0.1:18400/" in content
    assert "ExecStart=/usr/bin/nc 127.0.0.1 18400" in content
    assert "StandardInput=socket" in content
    assert "StandardOutput=socket" in content


def test_rdp_socket_listens_public_port() -> None:
    content = RDP_SOCKET.read_text()
    assert "ListenStream=127.0.0.1:3391" in content
    assert "Accept=yes" in content
    assert "WantedBy=sockets.target" in content


def test_rdp_service_proxies_internal_port() -> None:
    content = RDP_SERVICE.read_text()
    assert "ExecStartPre=/usr/local/bin/workstation-win11l-run.sh" in content
    assert "nc -z 127.0.0.1 13391" in content
    assert "ExecStart=/usr/bin/nc 127.0.0.1 13391" in content
    assert "StandardInput=socket" in content
    assert "StandardOutput=socket" in content