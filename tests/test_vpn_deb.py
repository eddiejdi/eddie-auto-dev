"""
Testes unitários para o pacote .deb rpa4all-vpn.

Valida estrutura do pacote, scripts de controle, CLI e DDNS updater.
"""

import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

# ── Constantes ──

DEB_DIR = Path(__file__).parent.parent / "deploy" / "vpn-deb"
PKG_DIR = DEB_DIR / "rpa4all-vpn"
DEB_FILE = DEB_DIR / "rpa4all-vpn_1.0.0_all.deb"
DEBIAN_DIR = PKG_DIR / "DEBIAN"
BIN_DIR = PKG_DIR / "usr" / "bin"
SHARE_DIR = PKG_DIR / "usr" / "share" / "rpa4all-vpn"

SERVER_PUBKEY = "RJTM75HsZRGG2Jcr2ylA/wC1rcT1QE4POOB/hw3PIWA="
VPN_SUBNET = "10.66.66.0/24"
LAN_SUBNET = "192.168.15.0/24"
DNS_SERVER = "192.168.15.2"
DDNS_HOST = "vpn.rpa4all.com"
WG_PORT = "51820"


# ═══════════════════════════════════════════════════════
# TESTES UNITÁRIOS — Estrutura do pacote
# ═══════════════════════════════════════════════════════

class TestPackageStructure:
    """Valida a árvore de diretórios e arquivos do pacote."""

    def test_control_file_exists(self) -> None:
        """Arquivo DEBIAN/control deve existir."""
        assert (DEBIAN_DIR / "control").exists()

    def test_postinst_exists(self) -> None:
        """Script postinst deve existir."""
        assert (DEBIAN_DIR / "postinst").exists()

    def test_prerm_exists(self) -> None:
        """Script prerm deve existir."""
        assert (DEBIAN_DIR / "prerm").exists()

    def test_postrm_exists(self) -> None:
        """Script postrm deve existir."""
        assert (DEBIAN_DIR / "postrm").exists()

    def test_cli_binary_exists(self) -> None:
        """Binário CLI deve existir."""
        assert (BIN_DIR / "rpa4all-vpn").exists()

    def test_ddns_updater_exists(self) -> None:
        """Script DDNS updater deve existir."""
        assert (BIN_DIR / "rpa4all-vpn-update-endpoint").exists()

    def test_systemd_service_exists(self) -> None:
        """Unit service do systemd deve existir."""
        assert (SHARE_DIR / "rpa4all-vpn-ddns.service").exists()

    def test_systemd_timer_exists(self) -> None:
        """Unit timer do systemd deve existir."""
        assert (SHARE_DIR / "rpa4all-vpn-ddns.timer").exists()

    def test_scripts_are_executable(self) -> None:
        """Scripts em usr/bin devem ter permissão de execução."""
        for script in BIN_DIR.iterdir():
            mode = script.stat().st_mode
            assert mode & stat.S_IXUSR, f"{script.name} não é executável"

    def test_control_scripts_are_executable(self) -> None:
        """Scripts de controle devem ter permissão de execução."""
        for name in ("postinst", "prerm", "postrm"):
            script = DEBIAN_DIR / name
            mode = script.stat().st_mode
            assert mode & stat.S_IXUSR, f"{name} não é executável"


# ═══════════════════════════════════════════════════════
# TESTES UNITÁRIOS — Arquivo control
# ═══════════════════════════════════════════════════════

class TestControlFile:
    """Valida campos do DEBIAN/control."""

    @pytest.fixture
    def control(self) -> str:
        """Carrega conteúdo do control."""
        return (DEBIAN_DIR / "control").read_text()

    def test_package_name(self, control: str) -> None:
        """Nome do pacote deve ser rpa4all-vpn."""
        assert "Package: rpa4all-vpn" in control

    def test_version_format(self, control: str) -> None:
        """Versão deve seguir formato semver."""
        match = re.search(r"Version: (\d+\.\d+\.\d+)", control)
        assert match, "Versão não encontrada no formato X.Y.Z"

    def test_architecture_is_all(self, control: str) -> None:
        """Pacote é arch-independent (shell scripts)."""
        assert "Architecture: all" in control

    def test_depends_wireguard(self, control: str) -> None:
        """Deve depender de wireguard-tools."""
        assert "wireguard-tools" in control

    def test_depends_network_manager(self, control: str) -> None:
        """Deve depender de network-manager."""
        assert "network-manager" in control

    def test_depends_curl(self, control: str) -> None:
        """Deve depender de curl."""
        assert "curl" in control

    def test_has_maintainer(self, control: str) -> None:
        """Deve ter campo Maintainer."""
        assert "Maintainer:" in control

    def test_has_description(self, control: str) -> None:
        """Deve ter descrição."""
        assert "Description:" in control

    def test_has_homepage(self, control: str) -> None:
        """Deve apontar para portal VPN."""
        assert "auth.rpa4all.com/vpn/" in control


# ═══════════════════════════════════════════════════════
# TESTES UNITÁRIOS — Script postinst
# ═══════════════════════════════════════════════════════

class TestPostinstScript:
    """Valida o script de pós-instalação."""

    @pytest.fixture
    def postinst(self) -> str:
        """Carrega conteúdo do postinst."""
        return (DEBIAN_DIR / "postinst").read_text()

    def test_starts_with_shebang(self, postinst: str) -> None:
        """Deve começar com shebang bash."""
        assert postinst.startswith("#!/bin/bash")

    def test_uses_set_e(self, postinst: str) -> None:
        """Deve usar set -e para falhar em erros."""
        assert "set -e" in postinst

    def test_generates_keys(self, postinst: str) -> None:
        """Deve gerar par de chaves WireGuard."""
        assert "wg genkey" in postinst
        assert "wg pubkey" in postinst

    def test_uses_correct_server_pubkey(self, postinst: str) -> None:
        """Deve usar a chave pública do servidor."""
        assert SERVER_PUBKEY in postinst

    def test_creates_wireguard_conf(self, postinst: str) -> None:
        """Deve criar config WireGuard."""
        assert "/etc/wireguard/rpa4all.conf" in postinst

    def test_creates_nm_connection(self, postinst: str) -> None:
        """Deve criar conexão NetworkManager."""
        assert "rpa4all-vpn.nmconnection" in postinst

    def test_uses_correct_subnets(self, postinst: str) -> None:
        """Deve configurar subnets corretas."""
        assert VPN_SUBNET in postinst
        assert LAN_SUBNET in postinst

    def test_uses_correct_dns(self, postinst: str) -> None:
        """Deve configurar DNS do homelab."""
        assert DNS_SERVER in postinst

    def test_sets_file_permissions(self, postinst: str) -> None:
        """Deve definir permissão 600 para configs."""
        assert "chmod 600" in postinst

    def test_installs_systemd_units(self, postinst: str) -> None:
        """Deve instalar units do systemd."""
        assert "rpa4all-vpn-ddns.timer" in postinst
        assert "systemctl enable" in postinst

    def test_does_not_hardcode_private_keys(self, postinst: str) -> None:
        """NÃO deve ter chaves privadas hardcoded."""
        # Padrão WireGuard key: 44 chars base64
        wg_key_re = re.compile(r'[A-Za-z0-9+/]{43}=')
        for match in wg_key_re.finditer(postinst):
            key = match.group()
            # A server pubkey é esperada
            if key == SERVER_PUBKEY:
                continue
            # Verificar que não é usada como PrivateKey
            context = postinst[max(0, match.start() - 50):match.start()]
            assert "PrivateKey" not in context, \
                f"Possível chave privada hardcoded: {key[:10]}..."

    def test_uses_ddns_endpoint(self, postinst: str) -> None:
        """Deve usar hostname DDNS, não IP fixo."""
        assert DDNS_HOST in postinst

    def test_shows_user_instructions(self, postinst: str) -> None:
        """Deve mostrar instruções ao usuário."""
        assert "rpa4all-vpn up" in postinst
        assert "rpa4all-vpn down" in postinst

    def test_copies_pubkey_to_readable_dir(self, postinst: str) -> None:
        """Deve copiar pubkey para /var/lib/rpa4all-vpn/ (legível sem sudo)."""
        assert "/var/lib/rpa4all-vpn" in postinst
        assert "public.key" in postinst

    def test_preserves_existing_configs(self, postinst: str) -> None:
        """Deve verificar antes de sobrescrever configs."""
        assert "already exists" in postinst.lower() or "já existe" in postinst.lower() or \
               '! -f' in postinst


# ═══════════════════════════════════════════════════════
# TESTES UNITÁRIOS — CLI rpa4all-vpn
# ═══════════════════════════════════════════════════════

class TestCLIScript:
    """Valida o script CLI principal."""

    @pytest.fixture
    def cli(self) -> str:
        """Carrega conteúdo do CLI."""
        return (BIN_DIR / "rpa4all-vpn").read_text()

    def test_starts_with_shebang(self, cli: str) -> None:
        """Deve começar com shebang bash."""
        assert cli.startswith("#!/bin/bash")

    def test_has_version(self, cli: str) -> None:
        """Deve ter versão definida."""
        assert 'VERSION="1.0.0"' in cli

    def test_has_all_commands(self, cli: str) -> None:
        """Deve suportar todos os comandos."""
        for cmd in ("up", "down", "status", "update-endpoint", "pubkey", "logs", "help"):
            assert cmd in cli, f"Comando '{cmd}' não encontrado"

    def test_up_updates_endpoint(self, cli: str) -> None:
        """Comando up deve atualizar endpoint antes de conectar."""
        assert "rpa4all-vpn-update-endpoint" in cli

    def test_up_removes_conflicting_route(self, cli: str) -> None:
        """Comando up deve remover rota LAN conflitante na rede local."""
        assert "ip route del 192.168.15.0/24" in cli

    def test_down_uses_nmcli(self, cli: str) -> None:
        """Comando down deve usar nmcli."""
        assert "nmcli connection down" in cli

    def test_status_checks_ping(self, cli: str) -> None:
        """Status deve verificar ping ao gateway."""
        assert "ping" in cli
        assert "10.66.66.1" in cli

    def test_requires_root_for_actions(self, cli: str) -> None:
        """Deve exigir root para up/down."""
        assert "need_root" in cli

    def test_pubkey_fallback_locations(self, cli: str) -> None:
        """Pubkey deve ter fallback de /var/lib para /etc/wireguard."""
        assert "/var/lib/rpa4all-vpn/public.key" in cli
        assert "/etc/wireguard/rpa4all-public.key" in cli

    def test_help_shows_portal_url(self, cli: str) -> None:
        """Help deve mostrar URL do portal."""
        assert "auth.rpa4all.com/vpn/" in cli


# ═══════════════════════════════════════════════════════
# TESTES UNITÁRIOS — Script DDNS updater
# ═══════════════════════════════════════════════════════

class TestDDNSUpdater:
    """Valida o script de atualização de endpoint DDNS."""

    @pytest.fixture
    def ddns(self) -> str:
        """Carrega conteúdo do DDNS updater."""
        return (BIN_DIR / "rpa4all-vpn-update-endpoint").read_text()

    def test_starts_with_shebang(self, ddns: str) -> None:
        """Deve começar com shebang bash."""
        assert ddns.startswith("#!/bin/bash")

    def test_uses_ddns_host(self, ddns: str) -> None:
        """Deve resolver o hostname DDNS correto."""
        assert DDNS_HOST in ddns

    def test_uses_correct_port(self, ddns: str) -> None:
        """Deve usar porta WireGuard correta."""
        assert f'PORT="{WG_PORT}"' in ddns

    def test_resolves_via_dig(self, ddns: str) -> None:
        """Deve tentar resolver via dig."""
        assert "dig" in ddns

    def test_has_fallback_resolution(self, ddns: str) -> None:
        """Deve ter fallback de resolução DNS."""
        assert "getent" in ddns or "nslookup" in ddns

    def test_updates_nm_config(self, ddns: str) -> None:
        """Deve atualizar config do NetworkManager."""
        assert "rpa4all-vpn.nmconnection" in ddns

    def test_updates_wg_config(self, ddns: str) -> None:
        """Deve atualizar config wg-quick."""
        assert "rpa4all.conf" in ddns

    def test_updates_live_interface(self, ddns: str) -> None:
        """Deve atualizar endpoint na interface live."""
        assert "wg set" in ddns

    def test_caches_ip(self, ddns: str) -> None:
        """Deve cachear IP para evitar atualizações desnecessárias."""
        assert "CACHE_FILE" in ddns

    def test_skips_if_unchanged(self, ddns: str) -> None:
        """Deve pular se IP não mudou."""
        assert "já atualizado" in ddns.lower() or "Endpoint já atualizado" in ddns


# ═══════════════════════════════════════════════════════
# TESTES UNITÁRIOS — Systemd units
# ═══════════════════════════════════════════════════════

class TestSystemdUnits:
    """Valida os units do systemd."""

    @pytest.fixture
    def service(self) -> str:
        """Carrega unit service."""
        return (SHARE_DIR / "rpa4all-vpn-ddns.service").read_text()

    @pytest.fixture
    def timer(self) -> str:
        """Carrega unit timer."""
        return (SHARE_DIR / "rpa4all-vpn-ddns.timer").read_text()

    def test_service_has_sections(self, service: str) -> None:
        """Service deve ter seções obrigatórias."""
        assert "[Unit]" in service
        assert "[Service]" in service

    def test_service_is_oneshot(self, service: str) -> None:
        """Service deve ser oneshot."""
        assert "Type=oneshot" in service

    def test_service_runs_updater(self, service: str) -> None:
        """Service deve executar o updater."""
        assert "/usr/bin/rpa4all-vpn-update-endpoint" in service

    def test_timer_has_sections(self, timer: str) -> None:
        """Timer deve ter seções obrigatórias."""
        assert "[Unit]" in timer
        assert "[Timer]" in timer
        assert "[Install]" in timer

    def test_timer_wants_timers_target(self, timer: str) -> None:
        """Timer deve ser habilitado em timers.target."""
        assert "WantedBy=timers.target" in timer

    def test_timer_triggers_periodically(self, timer: str) -> None:
        """Timer deve ter intervalo configurado."""
        assert "OnUnitActiveSec=" in timer


# ═══════════════════════════════════════════════════════
# TESTES UNITÁRIOS — Segurança
# ═══════════════════════════════════════════════════════

class TestSecurity:
    """Valida aspectos de segurança do pacote."""

    def test_no_private_keys_in_package(self) -> None:
        """Nenhum arquivo do pacote deve conter chaves privadas."""
        wg_key_re = re.compile(r'[A-Za-z0-9+/]{43}=')
        for root, _dirs, files in os.walk(PKG_DIR):
            for f in files:
                filepath = Path(root) / f
                try:
                    content = filepath.read_text()
                except (UnicodeDecodeError, PermissionError):
                    continue
                for match in wg_key_re.finditer(content):
                    key = match.group()
                    if key == SERVER_PUBKEY:
                        continue
                    context = content[max(0, match.start() - 30):match.start()]
                    assert "PrivateKey" not in context, \
                        f"Chave privada em {filepath}: {key[:10]}..."

    def test_postrm_cleans_var_lib(self) -> None:
        """Purge deve remover /var/lib/rpa4all-vpn."""
        postrm = (DEBIAN_DIR / "postrm").read_text()
        assert "/var/lib/rpa4all-vpn" in postrm

    def test_no_hardcoded_passwords(self) -> None:
        """Nenhum arquivo deve conter senhas hardcoded."""
        for root, _dirs, files in os.walk(PKG_DIR):
            for f in files:
                filepath = Path(root) / f
                try:
                    content = filepath.read_text().lower()
                except (UnicodeDecodeError, PermissionError):
                    continue
                for pattern in ("password=", "passwd=", "secret="):
                    assert pattern not in content, \
                        f"Possível senha em {filepath}"

    def test_postinst_sets_umask(self) -> None:
        """Postinst deve usar umask para proteger chaves."""
        postinst = (DEBIAN_DIR / "postinst").read_text()
        assert "umask 077" in postinst

    def test_no_curl_insecure(self) -> None:
        """Scripts não devem usar curl --insecure ou -k."""
        for script in BIN_DIR.iterdir():
            content = script.read_text()
            assert "--insecure" not in content, f"{script.name} usa --insecure"
            # -k pode ser ambíguo, verificar explicitamente com curl
            assert "curl -k " not in content and "curl.*-k " not in content, \
                f"{script.name} pode usar curl -k"


# ═══════════════════════════════════════════════════════
# TESTES DE INTEGRAÇÃO — Build do .deb
# ═══════════════════════════════════════════════════════

class TestDebBuild:
    """Valida o build do pacote .deb."""

    @pytest.fixture(scope="class")
    def build_deb(self) -> Path:
        """Builda o .deb se necessário e retorna o path."""
        build_script = DEB_DIR / "build-deb.sh"
        if not DEB_FILE.exists() or DEB_FILE.stat().st_mtime < build_script.stat().st_mtime:
            result = subprocess.run(
                ["bash", str(build_script)],
                capture_output=True, text=True, timeout=30
            )
            assert result.returncode == 0, f"Build falhou: {result.stderr}"
        return DEB_FILE

    def test_deb_file_created(self, build_deb: Path) -> None:
        """O .deb deve ser gerado."""
        assert build_deb.exists()

    def test_deb_file_has_content(self, build_deb: Path) -> None:
        """O .deb não deve estar vazio."""
        assert build_deb.stat().st_size > 1000

    def test_deb_contains_binaries(self, build_deb: Path) -> None:
        """O .deb deve conter os binários."""
        result = subprocess.run(
            ["dpkg-deb", "-c", str(build_deb)],
            capture_output=True, text=True, timeout=10
        )
        assert "usr/bin/rpa4all-vpn" in result.stdout
        assert "usr/bin/rpa4all-vpn-update-endpoint" in result.stdout

    def test_deb_metadata(self, build_deb: Path) -> None:
        """Metadados do .deb devem estar corretos."""
        result = subprocess.run(
            ["dpkg-deb", "-I", str(build_deb)],
            capture_output=True, text=True, timeout=10
        )
        assert "Package: rpa4all-vpn" in result.stdout
        assert "Version: 1.0.0" in result.stdout

    def test_deb_has_control_scripts(self, build_deb: Path) -> None:
        """O .deb deve incluir scripts de controle."""
        result = subprocess.run(
            ["dpkg-deb", "-I", str(build_deb)],
            capture_output=True, text=True, timeout=10
        )
        assert "postinst" in result.stdout
        assert "prerm" in result.stdout
        assert "postrm" in result.stdout


# ═══════════════════════════════════════════════════════
# TESTES — Consistência entre componentes
# ═══════════════════════════════════════════════════════

class TestConsistency:
    """Valida que todos os componentes referem os mesmos valores."""

    def test_server_pubkey_consistent(self) -> None:
        """Chave pública do servidor deve ser a mesma em todos os arquivos."""
        files_with_key = []
        for root, _dirs, files in os.walk(PKG_DIR):
            for f in files:
                filepath = Path(root) / f
                try:
                    content = filepath.read_text()
                except (UnicodeDecodeError, PermissionError):
                    continue
                if SERVER_PUBKEY in content:
                    files_with_key.append(filepath.name)

        # postinst e CLI referem a mesma key
        assert "postinst" in files_with_key, "postinst deve conter server pubkey"

    def test_vpn_name_consistent(self) -> None:
        """Nome da VPN deve ser consistente."""
        vpn_name = "rpa4all-vpn"
        cli_content = (BIN_DIR / "rpa4all-vpn").read_text()
        postinst_content = (DEBIAN_DIR / "postinst").read_text()
        ddns_content = (BIN_DIR / "rpa4all-vpn-update-endpoint").read_text()

        assert vpn_name in cli_content
        assert vpn_name in postinst_content
        assert vpn_name in ddns_content

    def test_port_consistent(self) -> None:
        """Porta WireGuard deve ser consistente."""
        postinst = (DEBIAN_DIR / "postinst").read_text()
        ddns = (BIN_DIR / "rpa4all-vpn-update-endpoint").read_text()

        assert WG_PORT in postinst
        assert WG_PORT in ddns
