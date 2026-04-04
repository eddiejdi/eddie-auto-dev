"""
Testes Selenium end-to-end para o portal VPN WireGuard.

Sobe um servidor HTTP local com mock do .conf,
abre o portal no Firefox headless e valida:
- Renderização e elementos visíveis
- Troca de abas (tabs)
- Detecção de OS
- Carregamento e parsing da config VPN
- Geração de scripts instaladores (.bat / .sh)
- Downloads (conteúdo gerado via Blob)
"""

import http.server
import json
import os
import threading
import time
from pa
from typing import Generator

import pytest

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.firefox.service import Service as FirefoxService
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError:
    webdriver = None

try:
    from webdriver_manager.firefox import GeckoDriverManager
except ImportError:
    GeckoDriverManager = None


# ── Constantes ──

HTML_PATH = Path(__file__).parent.parent / "deploy" / "vpn-portal" / "index.html"
MOCK_PORT = 18932  # Porta alta para evitar conflito

MOCK_WG_CONF = """\
[Interface]
PrivateKey = AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=
Address = 10.66.66.3/32
DNS = 1.1.1.1

[Peer]
PublicKey = BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB=
PresharedKey = CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC=
Endpoint = 152.234.122.4:51820
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25"""


# ── Servidor HTTP local com mock ──

class _MockVPNHandler(http.server.SimpleHTTPRequestHandler):
    """Serve o HTML e mock do .conf para testes locais."""

    def do_GET(self) -> None:
        if self.path == "/vpn/eddie-phone.conf":
            self._serve_text(MOCK_WG_CONF, "text/plain")
        elif self.path in ("/vpn/index.html", "/", "/index.html"):
            content = HTML_PATH.read_bytes()
            self._serve_bytes(content, "text/html")
        elif self.path == "/vpn/eddie-phone.png":
            # 1x1 transparent PNG para não quebrar img
            import base64
            png = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
                "nGNgYPgPAAEDAQAIicLsAAAABJRU5ErkJggg=="
            )
            self._serve_bytes(png, "image/png")
        else:
            self.send_error(404)

    def _serve_text(self, text: str, content_type: str) -> None:
        data = text.encode("utf-8")
        self._serve_bytes(data, content_type)

    def _serve_bytes(self, data: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:
        """Silencia logs do servidor HTTP."""
        pass


@pytest.fixture(scope="module")
def local_server() -> Generator[str, None, None]:
    """Sobe servidor HTTP local com mock VPN."""
    server = http.server.HTTPServer(("127.0.0.1", MOCK_PORT), _MockVPNHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{MOCK_PORT}"
    server.shutdown()


@pytest.fixture(scope="module")
def browser(local_server: str, tmp_path_factory: pytest.TempPathFactory) -> Generator:
    """Inicia Firefox headless com diretório de downloads configurado."""
    if webdriver is None:
        pytest.skip("selenium não instalado")

    download_dir = str(tmp_path_factory.mktemp("downloads"))

    opts = FirefoxOptions()
    opts.add_argument("--headless")
    opts.set_preference("browser.download.folderList", 2)
    opts.set_preference("browser.download.dir", download_dir)
    opts.set_preference("browser.download.useDownloadDir", True)
    opts.set_preference("browser.helperApps.neverAsk.saveToDisk",
                        "application/octet-stream,text/plain")
    opts.set_preference("browser.download.manager.showWhenStarting", False)

    try:
        if GeckoDriverManager is not None:
            service = FirefoxService(GeckoDriverManager().install())
            drv = webdriver.Firefox(service=service, options=opts)
        else:
            drv = webdriver.Firefox(options=opts)
    except Exception as e:
        pytest.skip(f"Firefox/geckodriver indisponível: {e}")
        return

    drv._download_dir = download_dir
    drv.get(f"{local_server}/vpn/index.html")
    # Esperar config carregar verificando o elemento de status (não page_source,
    # que contém "alert-success" na definição CSS)
    WebDriverWait(drv, 15).until(
        lambda d: d.execute_script(
            "var el = document.getElementById('config-status');"
            "return el && (el.querySelector('.alert-success') !== null"
            " || el.querySelector('.alert-error') !== null);"
        )
    )

    yield drv

    try:
        drv.quit()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════
# TESTES SELENIUM — Renderização
# ═══════════════════════════════════════════════════════

@pytest.mark.integration
class TestSeleniumRendering:
    """Valida que a página renderiza corretamente no browser."""

    def test_page_title(self, browser: webdriver.Firefox) -> None:
        """Título da página está correto."""
        assert "VPN WireGuard" in browser.title

    def test_header_visible(self, browser: webdriver.Firefox) -> None:
        """Header com título principal está visível."""
        h1 = browser.find_element(By.CSS_SELECTOR, ".header h1")
        assert h1.is_displayed()
        assert "VPN WireGuard" in h1.text

    def test_os_banner_visible(self, browser: webdriver.Firefox) -> None:
        """Banner de detecção de OS está visível."""
        banner = browser.find_element(By.ID, "os-banner")
        assert banner.is_displayed()

    def test_config_loaded_successfully(self, browser: webdriver.Firefox) -> None:
        """Config VPN carregou com sucesso (alert-success visível)."""
        status = browser.find_element(By.ID, "config-status")
        assert "alert-success" in status.get_attribute("innerHTML")
        assert "Configuração carregada" in status.text

    def test_five_tabs_visible(self, browser: webdriver.Firefox) -> None:
        """As 5 abas de plataformas estão visíveis."""
        tabs = browser.find_elements(By.CSS_SELECTOR, ".tab-btn")
        assert len(tabs) == 5
        for tab in tabs:
            assert tab.is_displayed()

    def test_one_tab_is_active(self, browser: webdriver.Firefox) -> None:
        """Exatamente uma aba está ativa."""
        active = browser.find_elements(By.CSS_SELECTOR, ".tab-btn.active")
        assert len(active) == 1

    def test_connection_info_populated(self, browser: webdriver.Firefox) -> None:
        """Painel de dados da conexão foi preenchido com a config."""
        endpoint = browser.find_element(By.ID, "info-endpoint")
        assert endpoint.text == "152.234.122.4:51820"
        address = browser.find_element(By.ID, "info-address")
        assert address.text == "10.66.66.3/32"
        dns = browser.find_element(By.ID, "info-dns")
        assert dns.text == "1.1.1.1"


# ═══════════════════════════════════════════════════════
# TESTES SELENIUM — Navegação por Abas
# ═══════════════════════════════════════════════════════

@pytest.mark.integration
class TestSeleniumTabs:
    """Valida que troca de abas funciona corretamente."""

    def test_switch_to_windows(self, browser: webdriver.Firefox) -> None:
        """Clicar na aba Windows mostra conteúdo Windows."""
        browser.find_element(By.CSS_SELECTOR, '[data-tab="windows"]').click()
        content = browser.find_element(By.CSS_SELECTOR, '[data-content="windows"]')
        assert content.is_displayed()
        assert "Windows 10/11" in content.text

    def test_switch_to_linux(self, browser: webdriver.Firefox) -> None:
        """Clicar na aba Linux mostra conteúdo Linux."""
        browser.find_element(By.CSS_SELECTOR, '[data-tab="linux"]').click()
        content = browser.find_element(By.CSS_SELECTOR, '[data-content="linux"]')
        assert content.is_displayed()

    def test_switch_to_macos(self, browser: webdriver.Firefox) -> None:
        """Clicar na aba macOS mostra conteúdo macOS."""
        browser.find_element(By.CSS_SELECTOR, '[data-tab="macos"]').click()
        content = browser.find_element(By.CSS_SELECTOR, '[data-content="macos"]')
        assert content.is_displayed()
        assert "macOS" in content.text

    def test_switch_to_android(self, browser: webdriver.Firefox) -> None:
        """Clicar na aba Android mostra conteúdo Android com QR."""
        browser.find_element(By.CSS_SELECTOR, '[data-tab="android"]').click()
        content = browser.find_element(By.CSS_SELECTOR, '[data-content="android"]')
        assert content.is_displayed()
        qr = content.find_element(By.CSS_SELECTOR, ".qr-img img")
        assert qr.is_displayed()

    def test_switch_to_ios(self, browser: webdriver.Firefox) -> None:
        """Clicar na aba iOS mostra conteúdo iOS com QR."""
        browser.find_element(By.CSS_SELECTOR, '[data-tab="ios"]').click()
        content = browser.find_element(By.CSS_SELECTOR, '[data-content="ios"]')
        assert content.is_displayed()

    def test_only_one_content_visible(self, browser: webdriver.Firefox) -> None:
        """Apenas um conteúdo de aba é visível por vez."""
        browser.find_element(By.CSS_SELECTOR, '[data-tab="linux"]').click()
        visible = [
            c for c in browser.find_elements(By.CSS_SELECTOR, ".tab-content")
            if c.is_displayed()
        ]
        assert len(visible) == 1
        assert visible[0].get_attribute("data-content") == "linux"


# ═══════════════════════════════════════════════════════
# TESTES SELENIUM — API JavaScript (__vpnPortal)
# ═══════════════════════════════════════════════════════

@pytest.mark.integration
class TestSeleniumJSAPI:
    """Valida a API JS exposta para testes."""

    def test_detect_os_returns_linux(self, browser: webdriver.Firefox) -> None:
        """Em Firefox Linux headless, detectOS retorna 'linux'."""
        result = browser.execute_script("return window.__vpnPortal.detectOS();")
        assert result == "linux"

    def test_parse_wg_config(self, browser: webdriver.Firefox) -> None:
        """parseWgConfig extrai campos corretamente."""
        result = browser.execute_script("""
            var cfg = window.__vpnPortal.parseWgConfig(
                "[Interface]\\nPrivateKey = xyz\\nAddress = 10.0.0.1/32\\nDNS = 8.8.8.8\\n" +
                "[Peer]\\nEndpoint = 1.2.3.4:51820\\nAllowedIPs = 0.0.0.0/0"
            );
            return JSON.stringify(cfg);
        """)
        cfg = json.loads(result)
        assert cfg["PrivateKey"] == "xyz"
        assert cfg["Address"] == "10.0.0.1/32"
        assert cfg["DNS"] == "8.8.8.8"
        assert cfg["Endpoint"] == "1.2.3.4:51820"
        assert cfg["AllowedIPs"] == "0.0.0.0/0"

    def test_config_loaded_via_api(self, browser: webdriver.Firefox) -> None:
        """Config VPN foi carregada e está acessível via API."""
        raw = browser.execute_script("return window.__vpnPortal.getConfig();")
        assert raw is not None
        assert "[Interface]" in raw
        assert "PrivateKey" in raw

    def test_parsed_config_has_fields(self, browser: webdriver.Firefox) -> None:
        """Config parseada tem todos os campos esperados."""
        parsed = browser.execute_script("return window.__vpnPortal.getParsed();")
        assert parsed["Endpoint"] == "152.234.122.4:51820"
        assert parsed["Address"] == "10.66.66.3/32"
        assert parsed["DNS"] == "1.1.1.1"
        assert "0.0.0.0/0" in parsed["AllowedIPs"]

    def test_os_labels_complete(self, browser: webdriver.Firefox) -> None:
        """OS_LABELS tem todos os 5 sistemas."""
        labels = browser.execute_script("return window.__vpnPortal.OS_LABELS;")
        assert labels["windows"] == "Windows"
        assert labels["macos"] == "macOS"
        assert labels["linux"] == "Linux"
        assert labels["android"] == "Android"
        assert labels["ios"] == "iPhone / iPad"


# ═══════════════════════════════════════════════════════
# TESTES SELENIUM — Geração de Scripts Instaladores
# ═══════════════════════════════════════════════════════

@pytest.mark.integration
class TestSeleniumScriptGeneration:
    """Valida que os scripts gerados têm conteúdo correto."""

    def test_windows_bat_has_uac_elevation(self, browser: webdriver.Firefox) -> None:
        """Script Windows .bat inclui auto-elevação UAC."""
        script = browser.execute_script("""
            var cfg = window.__vpnPortal.getParsed();
            return window.__vpnPortal.genWindowsScript(
                window.__vpnPortal.getConfig(), cfg
            );
        """)
        assert "@echo off" in script
        assert "net session" in script
        assert "Verb RunAs" in script
        assert "WireGuard.WireGuard" in script

    def test_windows_bat_embeds_config(self, browser: webdriver.Firefox) -> None:
        """Script Windows .bat embarca a config VPN."""
        script = browser.execute_script("""
            return window.__vpnPortal.genWindowsScript(
                window.__vpnPortal.getConfig(),
                window.__vpnPortal.getParsed()
            );
        """)
        assert "10.66.66.3/32" in script
        assert "152.234.122.4:51820" in script
        assert "Add-Content" in script

    def test_linux_script_has_shebang(self, browser: webdriver.Firefox) -> None:
        """Script Linux começa com shebang e tem estrutura correta."""
        script = browser.execute_script("""
            return window.__vpnPortal.genUnixScript(
                window.__vpnPortal.getConfig(),
                window.__vpnPortal.getParsed(),
                'linux'
            );
        """)
        assert script.startswith("#!/bin/bash")
        assert "apt-get" in script
        assert "dnf" in script
        assert "pacman" in script
        assert "systemctl enable wg-quick@wg0" in script

    def test_linux_script_embeds_config(self, browser: webdriver.Firefox) -> None:
        """Script Linux embarca a config VPN."""
        script = browser.execute_script("""
            return window.__vpnPortal.genUnixScript(
                window.__vpnPortal.getConfig(),
                window.__vpnPortal.getParsed(),
                'linux'
            );
        """)
        assert "[Interface]" in script
        assert "10.66.66.3/32" in script
        assert "chmod 600" in script

    def test_macos_script_uses_brew(self, browser: webdriver.Firefox) -> None:
        """Script macOS usa Homebrew."""
        script = browser.execute_script("""
            return window.__vpnPortal.genUnixScript(
                window.__vpnPortal.getConfig(),
                window.__vpnPortal.getParsed(),
                'macos'
            );
        """)
        assert "brew install wireguard-tools" in script
        # macOS NÃO deve ter systemctl
        assert "systemctl enable" not in script

    def test_macos_script_has_shebang(self, browser: webdriver.Firefox) -> None:
        """Script macOS começa com shebang."""
        script = browser.execute_script("""
            return window.__vpnPortal.genUnixScript(
                window.__vpnPortal.getConfig(),
                window.__vpnPortal.getParsed(),
                'macos'
            );
        """)
        assert script.startswith("#!/bin/bash")


# ═══════════════════════════════════════════════════════
# TESTES SELENIUM — Download de Arquivos
# ═══════════════════════════════════════════════════════

@pytest.mark.integration
class TestSeleniumDownloads:
    """Valida que downloads são disparados com conteúdo correto."""

    def _wait_for_download(self, download_dir: str, filename: str,
                           timeout: int = 10) -> Path:
        """Aguarda arquivo aparecer no diretório de downloads."""
        deadline = time.time() + timeout
        target = Path(download_dir) / filename
        while time.time() < deadline:
            if target.exists() and target.stat().st_size > 0:
                # Espera .part desaparecer (Firefox baixando)
                part = Path(f"{target}.part")
                if not part.exists():
                    return target
            time.sleep(0.3)
        # Lista o que existe para debug
        existing = list(Path(download_dir).iterdir())
        pytest.fail(f"Download '{filename}' não completou em {timeout}s. "
                    f"Arquivos: {[f.name for f in existing]}")

    def test_download_windows_bat(self, browser: webdriver.Firefox) -> None:
        """Download do install-vpn.bat gera arquivo com conteúdo correto."""
        download_dir = browser._download_dir
        # Navegar para aba Windows e clicar download
        browser.find_element(By.CSS_SELECTOR, '[data-tab="windows"]').click()
        browser.find_element(By.ID, "btn-win-installer").click()

        path = self._wait_for_download(download_dir, "install-vpn.bat")
        content = path.read_text(encoding="utf-8", errors="replace")
        assert "@echo off" in content
        assert "net session" in content
        assert "WireGuard" in content
        assert "10.66.66.3/32" in content

    def test_download_linux_sh(self, browser: webdriver.Firefox) -> None:
        """Download do install-vpn.sh (Linux) gera script bash válido."""
        download_dir = browser._download_dir
        # Limpar download anterior se existir
        sh_path = Path(download_dir) / "install-vpn.sh"
        if sh_path.exists():
            sh_path.unlink()

        browser.find_element(By.CSS_SELECTOR, '[data-tab="linux"]').click()
        browser.find_element(By.ID, "btn-linux-installer").click()

        path = self._wait_for_download(download_dir, "install-vpn.sh")
        content = path.read_text(encoding="utf-8")
        assert content.startswith("#!/bin/bash")
        assert "apt-get" in content
        assert "[Interface]" in content

    def test_download_conf_file(self, browser: webdriver.Firefox) -> None:
        """Download do .conf gera arquivo WireGuard válido."""
        download_dir = browser._download_dir
        conf_path = Path(download_dir) / "rpa4all-vpn.conf"
        if conf_path.exists():
            conf_path.unlink()

        browser.find_element(By.CSS_SELECTOR, '[data-tab="windows"]').click()
        browser.find_element(By.ID, "btn-win-conf").click()

        path = self._wait_for_download(download_dir, "rpa4all-vpn.conf")
        content = path.read_text(encoding="utf-8")
        assert "[Interface]" in content
        assert "[Peer]" in content
        assert "Endpoint = 152.234.122.4:51820" in content

    def test_download_macos_sh(self, browser: webdriver.Firefox) -> None:
        """Download do install-vpn.sh (macOS) gera script com brew."""
        download_dir = browser._download_dir
        sh_path = Path(download_dir) / "install-vpn.sh"
        if sh_path.exists():
            sh_path.unlink()

        browser.find_element(By.CSS_SELECTOR, '[data-tab="macos"]').click()
        browser.find_element(By.ID, "btn-mac-installer").click()

        path = self._wait_for_download(download_dir, "install-vpn.sh")
        content = path.read_text(encoding="utf-8")
        assert "brew install" in content
        assert "systemctl enable" not in content


# ═══════════════════════════════════════════════════════
# TESTES SELENIUM — Botões desabilitados/habilitados
# ═══════════════════════════════════════════════════════

@pytest.mark.integration
class TestSeleniumButtonStates:
    """Valida que botões mudam de estado após config carregar."""

    def test_installer_buttons_enabled_after_load(self, browser: webdriver.Firefox) -> None:
        """Todos os botões de instalador estão habilitados após config carregar."""
        btn_ids = ["btn-win-installer", "btn-mac-installer", "btn-linux-installer"]
        for btn_id in btn_ids:
            btn = browser.find_element(By.ID, btn_id)
            assert not btn.get_attribute("disabled"), \
                f"Botão {btn_id} ainda desabilitado após config carregar"

    def test_conf_buttons_enabled_after_load(self, browser: webdriver.Firefox) -> None:
        """Todos os botões de download .conf estão habilitados."""
        btn_ids = ["btn-win-conf", "btn-mac-conf", "btn-linux-conf",
                   "btn-android-conf", "btn-ios-conf"]
        for btn_id in btn_ids:
            btn = browser.find_element(By.ID, btn_id)
            assert not btn.get_attribute("disabled"), \
                f"Botão {btn_id} ainda desabilitado"
