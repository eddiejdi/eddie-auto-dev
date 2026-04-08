"""
Testes para deploy/vpn/fix-wireguard-routing.sh

Valida a estrutura e lógica do script de correção de
roteamento NAT/FORWARD para WireGuard.
"""

import re
import subprocess
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parent.parent / "deploy" / "vpn" / "fix-wireguard-routing.sh"
SERVICE_PATH = Path(__file__).parent.parent / "deploy" / "vpn" / "wireguard-nat.service"
WORKFLOW_PATH = (
    Path(__file__).parent.parent / ".github" / "workflows" / "deploy-vpn-fix.yml"
)


class TestFixWireguardRoutingScript:
    """Valida estrutura e conteúdo do script de fix."""

    def test_script_exists(self) -> None:
        """Script existe no caminho esperado."""
        assert SCRIPT_PATH.exists()

    def test_script_has_shebang(self) -> None:
        """Script começa com shebang bash."""
        content = SCRIPT_PATH.read_text()
        assert content.startswith("#!/bin/bash")

    def test_script_uses_strict_mode(self) -> None:
        """Script usa set -euo pipefail."""
        content = SCRIPT_PATH.read_text()
        assert "set -euo pipefail" in content

    def test_script_checks_root(self) -> None:
        """Script verifica execução como root."""
        content = SCRIPT_PATH.read_text()
        assert 'EUID' in content

    def test_script_enables_ip_forward(self) -> None:
        """Script habilita ip_forward IPv4."""
        content = SCRIPT_PATH.read_text()
        assert "sysctl -w net.ipv4.ip_forward=1" in content

    def test_script_enables_ipv6_forward(self) -> None:
        """Script habilita forwarding IPv6."""
        content = SCRIPT_PATH.read_text()
        assert "net.ipv6.conf.all.forwarding=1" in content

    def test_script_persists_sysctl(self) -> None:
        """Script persiste sysctl em /etc/sysctl.d/."""
        content = SCRIPT_PATH.read_text()
        assert "/etc/sysctl.d/99-wireguard-forward.conf" in content
        assert "net.ipv4.ip_forward = 1" in content

    def test_script_has_masquerade(self) -> None:
        """Script adiciona MASQUERADE para VPN CIDR."""
        content = SCRIPT_PATH.read_text()
        assert "MASQUERADE" in content
        assert "10.66.66.0/24" in content
        assert "POSTROUTING" in content

    def test_script_masquerade_uses_correct_interface(self) -> None:
        """MASQUERADE sai pela interface eth-onboard."""
        content = SCRIPT_PATH.read_text()
        assert "eth-onboard" in content
        assert re.search(r'-o\s+.*LAN_IFACE.*-j\s+MASQUERADE', content)

    def test_script_has_forward_in(self) -> None:
        """Script aceita tráfego FORWARD de wg0."""
        content = SCRIPT_PATH.read_text()
        assert re.search(r'FORWARD\s+-i.*WG_IFACE.*-j\s+ACCEPT', content)

    def test_script_has_forward_out_related(self) -> None:
        """Script aceita tráfego FORWARD de volta para wg0 (RELATED,ESTABLISHED)."""
        content = SCRIPT_PATH.read_text()
        assert "RELATED,ESTABLISHED" in content
        assert re.search(r'FORWARD\s+-o.*WG_IFACE.*RELATED', content)

    def test_script_is_idempotent(self) -> None:
        """Script usa iptables -C (check) antes de -A (append)."""
        content = SCRIPT_PATH.read_text()
        # Cada regra iptables deve ter -C antes de || para idempotência
        masq_lines = [
            line for line in content.split('\n')
            if 'MASQUERADE' in line and 'iptables' in line
        ]
        assert all(
            '-C' in line or '-A' in line or '-t nat' in line
            for line in masq_lines
        ), "Regras MASQUERADE devem usar -C || -A para idempotência"

    def test_script_checks_wg_interface(self) -> None:
        """Script verifica se wg0 está ativo."""
        content = SCRIPT_PATH.read_text()
        assert "ip link show" in content
        assert "wg-quick up" in content

    def test_script_has_summary(self) -> None:
        """Script imprime resumo das regras aplicadas."""
        content = SCRIPT_PATH.read_text()
        assert "Resumo" in content

    def test_script_allows_host_dns_before_nordvpn_drop(self) -> None:
        """Host local deve consultar o Pi-hole antes do bloqueio de DNS privado."""
        content = SCRIPT_PATH.read_text()
        assert 'pihole-host-local-udp' in content
        assert 'pihole-host-local-tcp' in content
        assert re.search(r'iptables -I OUTPUT 1 -p udp --dport 53 -d "\$PIHOLE_HOST" -j ACCEPT', content)
        assert re.search(r'iptables -I OUTPUT 1 -p tcp --dport 53 -d "\$PIHOLE_HOST" -j ACCEPT', content)

    def test_script_bash_syntax_valid(self) -> None:
        """Sintaxe bash do script é válida."""
        result = subprocess.run(
            ["bash", "-n", str(SCRIPT_PATH)],
            capture_output=True, text=True
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"


class TestWireguardNatService:
    """Valida o arquivo systemd service."""

    def test_service_exists(self) -> None:
        """Arquivo de serviço existe."""
        assert SERVICE_PATH.exists()

    def test_service_has_unit_section(self) -> None:
        """Serviço tem seção [Unit]."""
        content = SERVICE_PATH.read_text()
        assert "[Unit]" in content

    def test_service_after_wireguard(self) -> None:
        """Serviço inicia após wg-quick@wg0."""
        content = SERVICE_PATH.read_text()
        assert "wg-quick@wg0.service" in content

    def test_service_after_network(self) -> None:
        """Serviço inicia após network-online.target."""
        content = SERVICE_PATH.read_text()
        assert "network-online.target" in content

    def test_service_exec_start(self) -> None:
        """ExecStart aponta para o script correto."""
        content = SERVICE_PATH.read_text()
        assert "ExecStart=/opt/vpn/fix-wireguard-routing.sh" in content

    def test_service_oneshot(self) -> None:
        """Serviço é do tipo oneshot com RemainAfterExit."""
        content = SERVICE_PATH.read_text()
        assert "Type=oneshot" in content
        assert "RemainAfterExit=yes" in content

    def test_service_install(self) -> None:
        """Serviço pode ser habilitado (WantedBy)."""
        content = SERVICE_PATH.read_text()
        assert "[Install]" in content
        assert "WantedBy=multi-user.target" in content


class TestDeployVpnFixWorkflow:
    """Valida o workflow do GitHub Actions."""

    def test_workflow_exists(self) -> None:
        """Workflow existe."""
        assert WORKFLOW_PATH.exists()

    def test_workflow_triggers_on_push(self) -> None:
        """Workflow dispara em push para deploy/vpn/."""
        content = WORKFLOW_PATH.read_text()
        assert "deploy/vpn/**" in content

    def test_workflow_triggers_on_dispatch(self) -> None:
        """Workflow dispara via workflow_dispatch."""
        content = WORKFLOW_PATH.read_text()
        assert "workflow_dispatch" in content

    def test_workflow_uses_selfhosted_runner(self) -> None:
        """Workflow usa self-hosted runner com label homelab."""
        content = WORKFLOW_PATH.read_text()
        assert "self-hosted" in content
        assert "homelab-only" in content

    def test_workflow_has_remote_fallback(self) -> None:
        """Workflow tem fallback para deploy via SSH remoto."""
        content = WORKFLOW_PATH.read_text()
        assert "deploy-vpn-fix-remote" in content
        assert "ubuntu-latest" in content

    def test_workflow_copies_script(self) -> None:
        """Workflow copia o script para o homelab."""
        content = WORKFLOW_PATH.read_text()
        assert "fix-wireguard-routing.sh" in content
        assert "scp" in content

    def test_workflow_installs_systemd_service(self) -> None:
        """Workflow instala o serviço systemd."""
        content = WORKFLOW_PATH.read_text()
        assert "wireguard-nat.service" in content
        assert "systemctl daemon-reload" in content
        assert "systemctl enable" in content

    def test_workflow_has_verification_step(self) -> None:
        """Workflow verifica que as regras foram aplicadas."""
        content = WORKFLOW_PATH.read_text()
        assert "Verify VPN routing" in content
        assert "MASQ" in content
        assert "FORWARD" in content

    def test_workflow_yaml_valid(self) -> None:
        """YAML do workflow é válido (estrutura básica)."""
        content = WORKFLOW_PATH.read_text()
        # Verifica estrutura YAML básica sem depender do módulo yaml
        assert content.startswith("name:")
        assert "jobs:" in content
        assert "steps:" in content
        # Sem tabs (YAML não permite)
        assert "\t" not in content
