"""
Testes unitários e de integração para o portal VPN WireGuard.

Valida estrutura HTML, detecção de OS, geração de scripts instaladores,
e deploy no homelab via SSH.
"""

import re
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ── Constantes ──

HTML_PATH = Path(__file__).parent.parent / "deploy" / "vpn-portal" / "index.html"
HOMELAB_HOST = "192.168.15.2"
HOMELAB_USER = "homelab"
REMOTE_HTML_PATH = "/var/www/vpn-auth/index.html"

# Config de exemplo para testes (não usa chaves reais)
SAMPLE_CONFIG = """[Interface]
PrivateKey = AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=
Address = 10.66.66.3/32
DNS = 1.1.1.1

[Peer]
PublicKey = BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB=
PresharedKey = CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC=
Endpoint = 152.234.122.4:51820
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25"""


@pytest.fixture
def html_content() -> str:
    """Carrega o conteúdo HTML do portal VPN."""
    assert HTML_PATH.exists(), f"HTML não encontrado: {HTML_PATH}"
    return HTML_PATH.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════
# TESTES UNITÁRIOS — Estrutura HTML
# ═══════════════════════════════════════════════════════

class TestHTMLStructure:
    """Valida a estrutura e integridade do HTML do portal."""

    def test_html_is_valid_document(self, html_content: str) -> None:
        """HTML tem doctype, tags essenciais e encoding correto."""
        assert "<!doctype html>" in html_content.lower()
        assert '<html lang="pt-BR">' in html_content
        assert '<meta charset="utf-8">' in html_content
        assert "<title>" in html_content
        assert "</html>" in html_content

    def test_has_all_platform_tabs(self, html_content: str) -> None:
        """Todas as 5 plataformas têm abas."""
        tabs = ["windows", "macos", "linux", "android", "ios"]
        for tab in tabs:
            assert f'data-tab="{tab}"' in html_content, f"Aba {tab} ausente"
            assert f'data-content="{tab}"' in html_content, f"Conteúdo {tab} ausente"

    def test_has_installer_buttons(self, html_content: str) -> None:
        """Botões de download de instalador existem para desktop."""
        assert "btn-win-installer" in html_content
        assert "btn-mac-installer" in html_content
        assert "btn-linux-installer" in html_content

    def test_has_conf_download_buttons(self, html_content: str) -> None:
        """Botões de download de .conf existem para todas as plataformas."""
        conf_btns = ["btn-win-conf", "btn-mac-conf", "btn-linux-conf",
                     "btn-android-conf", "btn-ios-conf"]
        for btn_id in conf_btns:
            assert btn_id in html_content, f"Botão {btn_id} ausente"

    def test_has_qr_code_for_mobile(self, html_content: str) -> None:
        """Android e iOS têm referência ao QR Code."""
        qr_refs = html_content.count("eddie-phone.png")
        assert qr_refs >= 2, f"QR Code referenciado apenas {qr_refs}x (esperado >=2 para Android+iOS)"

    def test_has_app_store_links(self, html_content: str) -> None:
        """Links para stores oficiais existem."""
        assert "play.google.com" in html_content, "Link Play Store ausente"
        assert "apps.apple.com" in html_content, "Link App Store ausente"

    def test_no_hardcoded_private_keys(self, html_content: str) -> None:
        """HTML não contém chaves privadas hardcoded."""
        # Padrão base64 com comprimento de chave WireGuard (44 chars)
        wg_key_pattern = re.compile(r'[A-Za-z0-9+/]{43}=')
        # Exclui padrões que não são chaves (como IDs de gradientes, etc.)
        matches = wg_key_pattern.findall(html_content)
        # Filtrar apenas matches que parecem chaves (não estão em SVG/CSS)
        suspect = [m for m in matches if m not in ("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",)]
        # Em HTML estático não deve haver chaves reais embarcadas
        for key in suspect:
            assert "PrivateKey" not in html_content.split(key)[0][-50:], \
                f"Possível chave privada hardcoded encontrada: {key[:10]}..."

    def test_config_status_element_exists(self, html_content: str) -> None:
        """Elemento de status de carregamento existe."""
        assert 'id="config-status"' in html_content

    def test_connection_info_panel_exists(self, html_content: str) -> None:
        """Painel de informações de conexão existe com campos corretos."""
        info_ids = ["info-endpoint", "info-address", "info-dns", "info-allowed"]
        for info_id in info_ids:
            assert f'id="{info_id}"' in html_content, f"Campo {info_id} ausente"

    def test_no_mixed_content_fetch(self, html_content: str) -> None:
        """Não há fetch para HTTP de página HTTPS (mixed content)."""
        # Procurar fetch("http://...) que causaria mixed content
        http_fetch = re.findall(r'fetch\s*\(\s*["\']http://', html_content)
        assert len(http_fetch) == 0, \
            f"Mixed content: {len(http_fetch)} fetch(s) para HTTP encontrado(s)"

    def test_macos_is_separate_tab(self, html_content: str) -> None:
        """macOS tem aba própria (não mapeado para iOS)."""
        assert 'data-tab="macos"' in html_content
        assert 'data-content="macos"' in html_content
        # Verificar que detectOS retorna "macos" para Mac
        assert '"macos"' in html_content


# ═══════════════════════════════════════════════════════
# TESTES UNITÁRIOS — Lógica JavaScript (via regex no HTML)
# ═══════════════════════════════════════════════════════

class TestJavaScriptLogic:
    """Valida a lógica JavaScript embarcada no HTML."""

    def test_detect_os_function_exists(self, html_content: str) -> None:
        """Função detectOS está definida."""
        assert "function detectOS()" in html_content

    def test_detect_os_covers_all_platforms(self, html_content: str) -> None:
        """detectOS retorna valores para todas as plataformas."""
        for platform in ["android", "ios", "macos", "windows", "linux"]:
            assert f'return "{platform}"' in html_content, \
                f"detectOS não retorna '{platform}'"

    def test_detect_os_checks_android_before_linux(self, html_content: str) -> None:
        """Android é detectado antes de Linux (userAgent dos dois contém 'Linux')."""
        android_pos = html_content.index('return "android"')
        linux_pos = html_content.index('return "linux"')
        assert android_pos < linux_pos, "Android deve ser detectado antes de Linux"

    def test_detect_os_checks_ios_before_macos(self, html_content: str) -> None:
        """iOS (iphone/ipad) é detectado antes de macOS."""
        ios_pos = html_content.index('return "ios"')
        macos_pos = html_content.index('return "macos"')
        assert ios_pos < macos_pos, "iOS deve ser detectado antes de macOS"

    def test_parse_wg_config_function_exists(self, html_content: str) -> None:
        """Função parseWgConfig está definida."""
        assert "function parseWgConfig(" in html_content

    def test_gen_windows_script_function_exists(self, html_content: str) -> None:
        """Gerador de script Windows existe."""
        assert "function genWindowsScript(" in html_content

    def test_gen_unix_script_function_exists(self, html_content: str) -> None:
        """Gerador de script Unix (Linux/macOS) existe."""
        assert "function genUnixScript(" in html_content

    def test_fetch_uses_same_origin_credentials(self, html_content: str) -> None:
        """Fetch da config usa credentials same-origin para auth cookie."""
        assert 'credentials: "same-origin"' in html_content

    def test_fetch_endpoint_is_same_origin(self, html_content: str) -> None:
        """Fetch busca config do mesmo domínio (sem URL absoluta)."""
        fetch_match = re.search(r'fetch\s*\(\s*"([^"]+)"', html_content)
        assert fetch_match, "Nenhum fetch encontrado"
        url = fetch_match.group(1)
        assert url.startswith("/"), f"URL do fetch deve ser relativa: {url}"

    def test_download_installer_function_exists(self, html_content: str) -> None:
        """Função downloadInstaller está exposta globalmente."""
        assert "window.downloadInstaller" in html_content

    def test_download_conf_function_exists(self, html_content: str) -> None:
        """Função downloadConf está exposta globalmente."""
        assert "window.downloadConf" in html_content

    def test_copy_code_function_exists(self, html_content: str) -> None:
        """Função copyCode está exposta globalmente."""
        assert "window.copyCode" in html_content

    def test_testing_api_exposed(self, html_content: str) -> None:
        """API de teste exposta via window.__vpnPortal."""
        assert "__vpnPortal" in html_content
        for func in ["detectOS", "parseWgConfig", "genWindowsScript", "genUnixScript"]:
            assert f"{func}:" in html_content or f"{func} :" in html_content, \
                f"{func} não exposta em __vpnPortal"

    def test_buttons_start_disabled(self, html_content: str) -> None:
        """Botões de download iniciam desabilitados (até config carregar)."""
        installer_btns = re.findall(
            r'id="btn-(?:win|mac|linux|android|ios)-(?:installer|conf)"[^>]*disabled',
            html_content
        )
        assert len(installer_btns) >= 5, \
            f"Apenas {len(installer_btns)} botões com disabled (esperado >=5)"

    def test_xss_protection_on_error(self, html_content: str) -> None:
        """Mensagem de erro sanitiza HTML para prevenir XSS."""
        # Verificar que err.message é escapada antes de inserir no DOM
        assert 'replace(/</g' in html_content or 'textContent' in html_content


# ═══════════════════════════════════════════════════════
# TESTES UNITÁRIOS — Validação de Scripts Gerados
# ═══════════════════════════════════════════════════════

class TestScriptTemplates:
    """Valida que os templates de script estão corretos no HTML."""

    def test_windows_script_has_winget_install(self, html_content: str) -> None:
        """Script Windows usa winget como método principal de instalação."""
        assert "winget install" in html_content
        assert "WireGuard.WireGuard" in html_content

    def test_windows_script_has_fallback_installer(self, html_content: str) -> None:
        """Script Windows tem fallback para download direto se winget falhar."""
        assert "wireguard-installer.exe" in html_content

    def test_windows_script_requires_admin(self, html_content: str) -> None:
        """Script Windows exige admin."""
        assert "#Requires -RunAsAdministrator" in html_content

    def test_linux_script_supports_multiple_distros(self, html_content: str) -> None:
        """Script Linux suporta múltiplos gerenciadores de pacotes."""
        for pkg_mgr in ["apt-get", "dnf", "pacman", "zypper"]:
            assert pkg_mgr in html_content, f"Gerenciador {pkg_mgr} não suportado"

    def test_linux_script_enables_boot_service(self, html_content: str) -> None:
        """Script Linux habilita serviço no boot."""
        assert "systemctl enable wg-quick@wg0" in html_content

    def test_linux_script_sets_permissions(self, html_content: str) -> None:
        """Script Linux define permissões 600 no config."""
        assert "chmod 600" in html_content

    def test_unix_script_checks_root(self, html_content: str) -> None:
        """Script Unix verifica execução como root."""
        assert '"$EUID" -eq 0' in html_content

    def test_macos_script_uses_brew(self, html_content: str) -> None:
        """Script macOS usa Homebrew para instalar."""
        assert "brew install wireguard-tools" in html_content

    def test_scripts_embed_config_dynamically(self, html_content: str) -> None:
        """Scripts recebem config como parâmetro (não hardcoded)."""
        # genWindowsScript e genUnixScript recebem 'conf' como argumento
        assert "genWindowsScript(vpnConfig" in html_content
        assert "genUnixScript(vpnConfig" in html_content


# ═══════════════════════════════════════════════════════
# TESTES UNITÁRIOS — Acessibilidade e Responsividade
# ═══════════════════════════════════════════════════════

class TestAccessibility:
    """Valida acessibilidade básica do portal."""

    def test_has_viewport_meta(self, html_content: str) -> None:
        """Meta viewport está presente para responsividade."""
        assert 'name="viewport"' in html_content
        assert "width=device-width" in html_content

    def test_tabs_have_role(self, html_content: str) -> None:
        """Abas têm role ARIA."""
        assert 'role="tablist"' in html_content
        assert 'role="tab"' in html_content

    def test_images_have_alt(self, html_content: str) -> None:
        """Imagens têm atributo alt."""
        img_tags = re.findall(r'<img\s[^>]*>', html_content)
        for img in img_tags:
            assert 'alt=' in img, f"Imagem sem alt: {img[:60]}"

    def test_has_responsive_media_query(self, html_content: str) -> None:
        """CSS tem media query para mobile."""
        assert "@media" in html_content
        assert "max-width" in html_content


# ═══════════════════════════════════════════════════════
# TESTES DE INTEGRAÇÃO — Deploy e Nginx (requer SSH)
# ═══════════════════════════════════════════════════════

def _ssh_available() -> bool:
    """Verifica se SSH para o homelab está disponível."""
    key_path = Path.home() / ".ssh" / "homelab_key"
    if not key_path.exists():
        return False
    try:
        result = subprocess.run(
            ["ssh", "-i", str(key_path), "-o", "ConnectTimeout=3",
             "-o", "StrictHostKeyChecking=no",
             f"{HOMELAB_USER}@{HOMELAB_HOST}", "echo ok"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0 and "ok" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _ssh_run(cmd: str) -> subprocess.CompletedProcess:
    """Executa comando via SSH no homelab."""
    key_path = Path.home() / ".ssh" / "homelab_key"
    return subprocess.run(
        ["ssh", "-i", str(key_path), "-o", "StrictHostKeyChecking=no",
         f"{HOMELAB_USER}@{HOMELAB_HOST}", cmd],
        capture_output=True, text=True, timeout=30
    )


@pytest.mark.integration
class TestHomelabDeploy:
    """Testes de integração que verificam o deploy no homelab via SSH."""

    @pytest.fixture(autouse=True)
    def check_ssh(self) -> None:
        """Pula testes se SSH não disponível."""
        if not _ssh_available():
            pytest.skip("SSH para homelab indisponível")

    def test_nginx_serves_vpn_location(self) -> None:
        """Nginx tem location /vpn/ configurado."""
        result = _ssh_run("grep -c '/vpn/' /etc/nginx/sites-enabled/auth.rpa4all.com")
        count = int(result.stdout.strip()) if result.returncode == 0 else 0
        assert count >= 1, "Nginx não tem location /vpn/"

    def test_html_file_exists_on_server(self) -> None:
        """Arquivo HTML existe no servidor."""
        result = _ssh_run(f"test -f {REMOTE_HTML_PATH} && echo exists")
        assert "exists" in result.stdout

    def test_conf_file_exists_on_server(self) -> None:
        """Arquivo .conf existe no servidor."""
        result = _ssh_run("test -f /var/www/vpn-auth/eddie-phone.conf && echo exists")
        assert "exists" in result.stdout

    def test_qr_image_exists_on_server(self) -> None:
        """QR Code existe no servidor."""
        result = _ssh_run("test -f /var/www/vpn-auth/eddie-phone.png && echo exists")
        assert "exists" in result.stdout

    def test_nginx_conf_has_auth_request(self) -> None:
        """Nginx protege /vpn/ com auth_request."""
        result = _ssh_run("grep 'auth_request' /etc/nginx/sites-enabled/auth.rpa4all.com | head -5")
        assert "auth_request" in result.stdout

    def test_wireguard_server_running(self) -> None:
        """WireGuard server está ativo no homelab."""
        result = _ssh_run("sudo wg show wg0 2>/dev/null | head -3")
        assert "interface: wg0" in result.stdout or "wg0" in result.stdout

    def test_remote_html_has_installer_functions(self) -> None:
        """HTML no servidor contém as funções de instalador."""
        result = _ssh_run(f"grep -c 'genWindowsScript\\|genUnixScript\\|downloadInstaller' {REMOTE_HTML_PATH}")
        count = int(result.stdout.strip()) if result.returncode == 0 else 0
        assert count >= 3, "Funções de instalador ausentes no HTML remoto"

    def test_remote_html_no_mixed_content(self) -> None:
        """HTML remoto não tem fetch para HTTP (mixed content)."""
        result = _ssh_run(f"grep -c 'fetch.*http://' {REMOTE_HTML_PATH}")
        count = int(result.stdout.strip()) if result.returncode == 0 else 0
        assert count == 0, f"Mixed content encontrado no HTML remoto ({count} ocorrências)"
