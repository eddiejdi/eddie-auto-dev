#!/usr/bin/env python3
"""
Agente de administração do modem ZTE GPON via Selenium.

Operações suportadas:
  reboot      — Reinicia o modem (Administration → System Management → Reboot)
  status      — Exibe status WAN, firmware e informações do dispositivo
  diagnose    — Mede latência, packet loss e testa conectividade
  wifi        — Lista clientes WiFi conectados
  ping        — Executa ping via ferramenta de diagnóstico do modem

Estrutura da interface descoberta:
  - Login: Frm_Username / Frm_Password / LoginId
  - Pós-login: start.ghtml com 2 iframes (topFrame, mainFrame)
  - Navegação: openLink() dentro do mainFrame
  - Administração: mmManager → smSysMgr → manager_dev_conf_t.gch
  - Reboot: botão Submit1 (onclick="DevRestartSubmit()")
  - Timeout de sessão: 300 segundos

Uso:
  python3 scripts/zte_modem_admin.py reboot
  python3 scripts/zte_modem_admin.py status
  python3 scripts/zte_modem_admin.py diagnose
  python3 scripts/zte_modem_admin.py wifi
  python3 scripts/zte_modem_admin.py ping --host 8.8.8.8

  MODEM_URL=http://192.168.15.1 MODEM_USER=admin MODEM_PASS=admin \\
      python3 scripts/zte_modem_admin.py reboot [--dry-run]
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    UnexpectedAlertPresentException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# ─── Configuração ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

MODEM_URL   = os.environ.get("MODEM_URL", "http://192.168.15.1")
SECRETS_API = os.environ.get("SECRETS_API_URL", "http://192.168.15.2:8088")
SECRETS_KEY = os.environ.get(
    "SECRETS_API_KEY",
    "188bbf4c1b43ed1730005288f89ad2d0708c071eca142a2b335e026e95e8cee3",
)
SCREENSHOT_DIR = Path("/tmp/zte_modem_screenshots")


# ─── Credenciais ─────────────────────────────────────────────────────────────

def _fetch_credentials() -> tuple[str, str]:
    """Busca credenciais: env vars → Secrets Agent → padrão admin/admin."""
    user = os.environ.get("MODEM_USER")
    passwd = os.environ.get("MODEM_PASS")
    if user and passwd:
        return user, passwd

    try:
        req = urllib.request.Request(
            f"{SECRETS_API}/secrets/eddie%2Frouter_credentials",
            headers={"X-API-KEY": SECRETS_KEY},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        creds = json.loads(data.get("value", "{}"))
        if creds.get("username") and creds.get("password"):
            log.info("Credenciais obtidas do Secrets Agent")
            return creds["username"], creds["password"]
    except Exception as exc:
        log.warning("Secrets Agent indisponível: %s", exc)

    log.warning("Usando credenciais padrão admin/admin")
    return "admin", "admin"


# ─── WebDriver ───────────────────────────────────────────────────────────────

def _create_driver() -> webdriver.Chrome:
    """Cria Chrome headless para acesso ao modem."""
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,900")
    opts.add_argument("--no-proxy-server")
    try:
        return webdriver.Chrome(options=opts)
    except Exception:
        return webdriver.Chrome(
            service=Service("/usr/bin/chromedriver"), options=opts
        )


def _dismiss_alert(driver: webdriver.Chrome, accept: bool = True) -> Optional[str]:
    """Fecha alert JS se presente. Retorna o texto ou None."""
    try:
        alert = driver.switch_to.alert
        text = alert.text
        alert.accept() if accept else alert.dismiss()
        log.debug("Alert fechado: %s", text)
        return text
    except Exception:
        return None


def _screenshot(driver: webdriver.Chrome, name: str) -> None:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOT_DIR / f"{name}_{int(time.time())}.png"
    try:
        driver.save_screenshot(str(path))
        log.debug("Screenshot: %s", path)
    except Exception:
        pass


# ─── Login e navegação ───────────────────────────────────────────────────────

def _login(driver: webdriver.Chrome, user: str, passwd: str) -> bool:
    """Autentica no ZTE GPON. Retorna True se bem-sucedido."""
    log.info("Conectando ao modem: %s", MODEM_URL)
    driver.get(f"{MODEM_URL}/")
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "Frm_Username"))
        )
    except TimeoutException:
        log.error("Formulário de login não encontrado em %s", MODEM_URL)
        _screenshot(driver, "login_timeout")
        return False

    driver.find_element(By.ID, "Frm_Username").send_keys(user)
    driver.find_element(By.ID, "Frm_Password").send_keys(passwd)
    driver.find_element(By.ID, "LoginId").click()
    time.sleep(2)
    _dismiss_alert(driver)

    if "start.ghtml" in driver.current_url or "start" in driver.current_url:
        log.info("Login bem-sucedido ✓ (%s)", driver.current_url)
        return True

    log.error("Login falhou — URL atual: %s", driver.current_url)
    _screenshot(driver, "login_failed")
    return False


def _switch_main_frame(driver: webdriver.Chrome) -> bool:
    """Muda foco para o mainFrame onde está a navegação."""
    try:
        driver.switch_to.default_content()
        driver.switch_to.frame("mainFrame")
        return True
    except Exception as exc:
        log.error("Não foi possível acessar mainFrame: %s", exc)
        return False


def _navigate_admin_sysmgr(driver: webdriver.Chrome) -> bool:
    """Abre Administration → System Management no mainFrame."""
    if not _switch_main_frame(driver):
        return False
    try:
        driver.find_element(By.ID, "mmManager").click()
        time.sleep(0.5)
        _dismiss_alert(driver)
        driver.find_element(By.ID, "smSysMgr").click()
        time.sleep(2)
        _dismiss_alert(driver)
        return True
    except NoSuchElementException as exc:
        log.error("Menu Administration não encontrado: %s", exc)
        _screenshot(driver, "nav_failed")
        return False


def _navigate_status(driver: webdriver.Chrome, page: str) -> bool:
    """Navega para uma página de status via openLink no mainFrame."""
    if not _switch_main_frame(driver):
        return False
    try:
        driver.execute_script(
            f"openLink('getpage.gch?pid=1002&nextpage={page}');"
        )
        time.sleep(2)
        _dismiss_alert(driver)
        return True
    except Exception as exc:
        log.error("Falha ao navegar para %s: %s", page, exc)
        return False


# ─── Operação: reboot ────────────────────────────────────────────────────────

def op_reboot(driver: webdriver.Chrome, dry_run: bool) -> int:
    """Reinicia o modem via Administration → System Management → Reboot."""
    log.info("=== REBOOT DO MODEM ===")

    if not _navigate_admin_sysmgr(driver):
        return 1

    try:
        btn = driver.find_element(By.ID, "Submit1")
        label = btn.get_attribute("value") or btn.text
        log.info("Botão encontrado: '%s'", label)
    except NoSuchElementException:
        log.error("Botão Reboot (Submit1) não encontrado na página")
        _screenshot(driver, "reboot_no_button")
        return 1

    if dry_run:
        log.info("[DRY-RUN] Reboot NÃO executado")
        return 0

    _screenshot(driver, "before_reboot")
    btn.click()
    time.sleep(1)
    alert_text = _dismiss_alert(driver, accept=True)
    if alert_text:
        log.info("Confirmação: %s", alert_text)
    _dismiss_alert(driver, accept=True)

    log.info("Comando de reboot enviado — modem reiniciará em ~2-3 minutos")
    _wait_modem_back(MODEM_URL.replace("http://", "").split("/")[0])
    return 0


def _wait_modem_back(host: str, timeout: int = 180) -> None:
    """Aguarda o modem voltar online após reboot."""
    log.info("Aguardando modem voltar online (timeout %ds)...", timeout)
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(10)
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "2", host],
            capture_output=True,
        )
        if result.returncode == 0:
            elapsed = int(time.time() - start)
            log.info("Modem online após %ds ✓", elapsed)
            return
        log.info("Aguardando... %.0fs", time.time() - start)
    log.warning("Modem não voltou dentro de %ds", timeout)


# ─── Operação: status ────────────────────────────────────────────────────────

def op_status(driver: webdriver.Chrome, dry_run: bool) -> int:
    """Exibe informações de status do dispositivo e WAN."""
    log.info("=== STATUS DO MODEM ===")

    pages = {
        "Informações do dispositivo": "status_dev_info_t.gch",
        "Status WAN":                 "IPv46_status_wan_if_t.gch",
        "Interface LAN":              "pon_status_lan_info_t.gch",
    }

    for label, page in pages.items():
        log.info("--- %s ---", label)
        if not _navigate_status(driver, page):
            log.warning("Não foi possível carregar: %s", page)
            continue

        if not _switch_main_frame(driver):
            continue

        try:
            # Tentar pegar conteúdo do iframe interno se existir
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            if iframes:
                driver.switch_to.frame(iframes[0])

            src = driver.page_source
            # Extrair pares chave:valor visíveis
            text = re.sub(r"<[^>]+>", " ", src)
            text = re.sub(r"\s+", " ", text).strip()
            # Filtrar só linhas com conteúdo relevante
            for line in text.split("  "):
                line = line.strip()
                if len(line) > 3 and len(line) < 200:
                    log.info("  %s", line)
        except Exception as exc:
            log.warning("Erro ao ler %s: %s", page, exc)
        finally:
            driver.switch_to.default_content()

    return 0


# ─── Operação: diagnose ──────────────────────────────────────────────────────

def op_diagnose(driver: webdriver.Chrome, dry_run: bool) -> int:
    """Diagnóstico de rede: latência ao gateway, connectivitycheck, DNS."""
    log.info("=== DIAGNÓSTICO DE REDE ===")
    host = MODEM_URL.replace("http://", "").split("/")[0]

    # 1. Ping ao gateway
    log.info("Ping ao gateway (%s):", host)
    result = subprocess.run(
        ["ping", "-c", "10", "-W", "2", host],
        capture_output=True, text=True,
    )
    for line in result.stdout.splitlines():
        if any(k in line for k in ["rtt", "packet", "bytes from"]):
            log.info("  %s", line)

    # 2. Connectivity check (endpoint usado pelo Chromecast/Android)
    log.info("Connectivity check (connectivitycheck.gstatic.com):")
    result2 = subprocess.run(
        ["curl", "-s", "--max-time", "5", "-o", "/dev/null",
         "-w", "%{http_code} em %{time_total}s",
         "http://connectivitycheck.gstatic.com/generate_204"],
        capture_output=True, text=True,
    )
    code_time = result2.stdout.strip()
    ok = code_time.startswith("204")
    log.info("  Resultado: %s %s", code_time, "✓" if ok else "✗ (timeout Chromecast > 2s)")

    # 3. DNS via Pi-hole
    log.info("DNS via Pi-hole (192.168.15.2):")
    for domain in ["youtube.com", "connectivitycheck.gstatic.com"]:
        r = subprocess.run(
            ["dig", f"@192.168.15.2", domain, "+short", "+time=3"],
            capture_output=True, text=True,
        )
        ans = r.stdout.strip().split("\n")[0] if r.stdout.strip() else "SEM RESPOSTA"
        log.info("  %s → %s", domain, ans)

    # 4. YouTube accessibility
    log.info("Acesso ao YouTube:")
    for url in ["https://youtube.com", "https://youtubei.googleapis.com"]:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "5", "-o", "/dev/null",
             "-w", "%{http_code} em %{time_total}s", url],
            capture_output=True, text=True,
        )
        log.info("  %s → %s", url, r.stdout.strip())

    return 0


# ─── Operação: wifi ──────────────────────────────────────────────────────────

def op_wifi(driver: webdriver.Chrome, dry_run: bool) -> int:
    """Lista clientes WiFi conectados ao modem."""
    log.info("=== CLIENTES WIFI ===")

    # Tentar páginas conhecidas de WiFi status
    wifi_pages = [
        "pon_status_wlan_client_t.gch",
        "status_wlan_assoc_t.gch",
        "wlan_assoc_sta_t.gch",
    ]

    for page in wifi_pages:
        if not _navigate_status(driver, page):
            continue
        if not _switch_main_frame(driver):
            continue
        try:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            if iframes:
                driver.switch_to.frame(iframes[0])
            src = driver.page_source
            if len(src) < 500:
                driver.switch_to.default_content()
                continue
            # Extrair MACs e IPs
            macs = re.findall(r"([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})", src)
            ips  = re.findall(r"\b(192\.168\.\d+\.\d+)\b", src)
            if macs:
                log.info("Clientes encontrados em %s:", page)
                for mac in set(macs):
                    log.info("  MAC: %s", mac)
                for ip in set(ips):
                    log.info("  IP:  %s", ip)
                driver.switch_to.default_content()
                return 0
        except Exception as exc:
            log.warning("Erro em %s: %s", page, exc)
        finally:
            driver.switch_to.default_content()

    log.warning("Página de clientes WiFi não encontrada — listando via ARP local")
    r = subprocess.run(["arp", "-n"], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if "192.168.15" in line and "incomplete" not in line:
            log.info("  %s", line)
    return 0


# ─── Operação: ping (via modem) ──────────────────────────────────────────────

def op_ping(driver: webdriver.Chrome, dry_run: bool, host: str) -> int:
    """Executa ping via ferramenta de diagnóstico do modem ZTE."""
    log.info("=== PING VIA MODEM → %s ===", host)

    if not _navigate_status(driver, "manager_dev_ping_t.gch"):
        log.warning("Página de ping não acessível — usando ping local")
        r = subprocess.run(
            ["ping", "-c", "5", host], capture_output=True, text=True
        )
        log.info(r.stdout)
        return 0

    if not _switch_main_frame(driver):
        return 1

    try:
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        if iframes:
            driver.switch_to.frame(iframes[0])

        # Preencher host e executar
        try:
            host_field = driver.find_element(By.XPATH, "//input[@type='text']")
            host_field.clear()
            host_field.send_keys(host)
            driver.find_element(By.XPATH, "//input[@type='button' or @type='submit']").click()
            time.sleep(5)
            _dismiss_alert(driver)
            # Ler resultado
            src = driver.page_source
            text = re.sub(r"<[^>]+>", " ", src)
            text = re.sub(r"\s+", " ", text)
            log.info("Resultado: %s", text[:500])
        except NoSuchElementException:
            log.warning("Formulário de ping não encontrado na página")
    except Exception as exc:
        log.error("Erro no ping via modem: %s", exc)
    finally:
        driver.switch_to.default_content()

    return 0


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Agente de administração do modem ZTE GPON"
    )
    parser.add_argument(
        "operation",
        choices=["reboot", "status", "diagnose", "wifi", "ping"],
        help="Operação a executar",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simula sem executar ações destrutivas (reboot)",
    )
    parser.add_argument(
        "--host", default="8.8.8.8",
        help="Host para operação ping (padrão: 8.8.8.8)",
    )
    args = parser.parse_args()

    # diagnose não precisa de Selenium
    if args.operation == "diagnose":
        return op_diagnose(None, args.dry_run)  # type: ignore[arg-type]

    user, passwd = _fetch_credentials()
    driver = _create_driver()
    try:
        if not _login(driver, user, passwd):
            log.error("Falha no login — verifique MODEM_USER/MODEM_PASS ou credenciais do Secrets Agent")
            return 1

        ops = {
            "reboot":  lambda: op_reboot(driver, args.dry_run),
            "status":  lambda: op_status(driver, args.dry_run),
            "wifi":    lambda: op_wifi(driver, args.dry_run),
            "ping":    lambda: op_ping(driver, args.dry_run, args.host),
        }
        return ops[args.operation]()

    except WebDriverException as exc:
        log.error("Erro WebDriver: %s", exc)
        _screenshot(driver, "error")
        return 1
    finally:
        driver.quit()


if __name__ == "__main__":
    sys.exit(main())
