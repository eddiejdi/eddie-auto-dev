#!/usr/bin/env python3
"""
Configura rede local no roteador legado via Selenium.

Ações executadas:
  1. Faz login no roteador legado com credenciais do Secrets Agent
  2. Acessa Configurações → Rede Local (settings-local-network.asp)
  3. Define DNS primário como 192.168.15.2 (Pi-hole)
  4. Define DNS secundário como 8.8.8.8 (fallback)
  5. Salva a configuração
  6. (Opcional) Acessa Jogos & Aplicativos para verificar proxy WPAD

Pré-requisitos:
  - google-chrome + chromedriver instalados no homelab
  - pip3 install selenium

Uso:
  ROUTER_URL=http://router.local python3 scripts/router_network_config.py [--dry-run] [--screenshot-only]
  ROUTER_URL=http://router.local ROUTER_USER=admin ROUTER_PASS=admin python3 scripts/router_network_config.py
"""

import argparse
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.common.exceptions import (
    ElementNotInteractableException,
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

# ─── Configuração ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

ROUTER_URL = os.environ.get("ROUTER_URL", "")
HOMELAB_IP = "192.168.15.2"
PIHOLE_DNS = HOMELAB_IP          # Pi-hole escuta na porta 53
FALLBACK_DNS = "8.8.8.8"
SQUID_PORT = 3128
SCREENSHOT_DIR = Path("/tmp/router_config_screenshots")
SECRETS_API = os.environ.get("SECRETS_API_URL", f"http://{HOMELAB_IP}:8088")
SECRETS_KEY = os.environ.get(
    "SECRETS_API_KEY",
    "188bbf4c1b43ed1730005288f89ad2d0708c071eca142a2b335e026e95e8cee3",
)


# ─── Credenciais ─────────────────────────────────────────────────────────────

def _fetch_credentials() -> tuple[str, str]:
    """Busca credenciais do roteador: Secrets Agent → env vars → padrão."""
    # 1. Variáveis de ambiente (mais rápido)
    env_user = os.environ.get("ROUTER_USER")
    env_pass = os.environ.get("ROUTER_PASS")
    if env_user and env_pass:
        return env_user, env_pass

    # 2. Secrets Agent
    try:
        url = f"{SECRETS_API}/secrets/eddie%2Frouter_credentials"
        req = urllib.request.Request(
            url, headers={"X-API-KEY": SECRETS_KEY}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        value = data.get("value", "{}")
        creds = json.loads(value) if isinstance(value, str) else value
        if creds.get("username") and creds.get("password"):
            log.info("Credenciais obtidas do Secrets Agent")
            return creds["username"], creds["password"]
    except Exception as exc:
        log.warning("Secrets Agent indisponível: %s", exc)

    # 3. Padrão Vivo/GVT
    log.warning("Usando credenciais padrão admin/admin")
    return "admin", "admin"


# ─── WebDriver ───────────────────────────────────────────────────────────────

def _create_driver() -> webdriver.Chrome:
    """Cria Chrome headless configurado para acesso local."""
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,900")
    opts.add_argument("--disable-web-security")
    opts.add_argument("--allow-running-insecure-content")
    # Desabilitar proxy system para acesso direto ao roteador
    opts.add_argument("--no-proxy-server")
    try:
        return webdriver.Chrome(options=opts)
    except Exception:
        # Fallback: usar chromedriver explícito
        service = Service("/usr/bin/chromedriver")
        return webdriver.Chrome(service=service, options=opts)


def _screenshot(driver: webdriver.Chrome, name: str) -> Path:
    """Salva screenshot para debug."""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOT_DIR / f"{name}_{int(time.time())}.png"
    driver.save_screenshot(str(path))
    log.info("Screenshot: %s", path)
    return path


def _dump_html(driver: webdriver.Chrome, name: str) -> Path:
    """Salva HTML da página para análise."""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOT_DIR / f"{name}_{int(time.time())}.html"
    path.write_text(driver.page_source, encoding="utf-8")
    log.info("HTML dump: %s", path)
    return path


# ─── Login ───────────────────────────────────────────────────────────────────

def _login(driver: webdriver.Chrome, username: str, password: str) -> bool:
    """Faz login no roteador Vivo/GVT via formulário JS."""
    if not ROUTER_URL:
        log.error("ROUTER_URL não definido. O roteador legado não faz parte do contrato operacional padrão.")
        return False

    log.info("Abrindo roteador: %s", ROUTER_URL)
    driver.get(ROUTER_URL)
    time.sleep(2)
    _screenshot(driver, "01_initial")

    try:
        wait = WebDriverWait(driver, 15)

        # Aguardar campo de usuário
        user_field = wait.until(
            EC.presence_of_element_located((By.ID, "txtUser"))
        )
        pass_field = driver.find_element(By.ID, "txtPass")

        user_field.clear()
        user_field.send_keys(username)
        pass_field.clear()
        pass_field.send_keys(password)

        # Botão de login (é um <a> com id=btnLogin, não um submit)
        btn = driver.find_element(By.ID, "btnLogin")
        btn.click()
        log.info("Credenciais enviadas, aguardando sessão...")
        time.sleep(4)

        _screenshot(driver, "02_after_login")
        page_src = driver.page_source

        if "Falha no login" in page_src or "txtUser" in page_src:
            log.error("Login falhou — credenciais inválidas ou CAPTCHA ativo")
            _dump_html(driver, "02_login_failed")
            return False

        # Verificar presença do sidebar/menu (indica login bem-sucedido)
        if any(x in page_src for x in ["accordion", "settings-local-network", "Configurações"]):
            log.info("Login bem-sucedido ✓")
            return True

        # Verificar por redirecionamento para página de status
        if "index_cliente" in driver.current_url or "status" in driver.current_url:
            log.info("Login bem-sucedido (redirecionamento para status) ✓")
            return True

        log.warning("Estado pós-login incerto — tentando continuar")
        _dump_html(driver, "02_login_uncertain")
        return True

    except TimeoutException:
        log.error("Timeout aguardando formulário de login")
        _screenshot(driver, "02_login_timeout")
        return False


# ─── Rede Local / DHCP ───────────────────────────────────────────────────────

def _navigate_to_local_network(driver: webdriver.Chrome) -> bool:
    """Navega para a página Rede Local."""
    log.info("Navegando para Rede Local (DHCP)...")
    driver.get(f"{ROUTER_URL}/settings-local-network.asp")
    time.sleep(3)
    _screenshot(driver, "03_local_network")

    page_src = driver.page_source
    if "txtUser" in page_src and "Autenticação" in page_src:
        log.error("Sessão expirou — precisa re-logar")
        return False

    _dump_html(driver, "03_local_network")
    log.info("Página de Rede Local carregada. URL: %s", driver.current_url)
    return True


def _log_form_fields(driver: webdriver.Chrome) -> None:
    """Registra todos os campos de formulário encontrados na página."""
    inputs = driver.find_elements(By.TAG_NAME, "input")
    selects = driver.find_elements(By.TAG_NAME, "select")
    log.info("Campos encontrados: %d inputs, %d selects", len(inputs), len(selects))

    for inp in inputs:
        id_ = inp.get_attribute("id") or ""
        name = inp.get_attribute("name") or ""
        type_ = inp.get_attribute("type") or "text"
        value = inp.get_attribute("value") or ""
        if type_ not in ("hidden",) and (id_ or name):
            log.info("  [INPUT] id=%-25s name=%-25s type=%-10s val=%s",
                     id_ or "-", name or "-", type_, value[:30])

    for sel in selects:
        id_ = sel.get_attribute("id") or ""
        name = sel.get_attribute("name") or ""
        try:
            selected = Select(sel).first_selected_option.text
        except Exception:
            selected = "?"
        log.info("  [SELECT] id=%-25s name=%-25s selected=%s",
                 id_ or "-", name or "-", selected)


def _find_field(driver: webdriver.Chrome, candidates: list[str]) -> Optional[webdriver.Chrome]:
    """Tenta encontrar um elemento por lista de IDs/names."""
    for id_ in candidates:
        try:
            el = driver.find_element(By.ID, id_)
            if el.is_displayed() or el.is_enabled():
                return el
        except NoSuchElementException:
            pass
    for name in candidates:
        try:
            el = driver.find_element(By.NAME, name)
            if el.is_displayed() or el.is_enabled():
                return el
        except NoSuchElementException:
            pass
    return None


def _set_dns_config(
    driver: webdriver.Chrome, primary_dns: str, secondary_dns: str, dry_run: bool
) -> bool:
    """Configura DNS primário e secundário no DHCP do roteador.

    O Vivo/GVT usa nomes de campo variáveis. Tenta múltiplos padrões.
    """
    # IDs conhecidos do Vivo/GVT para DNS primário e secundário
    primary_candidates = [
        "txtDns1", "dns1", "primaryDNS", "DNS1", "txtPrimaryDNS",
        "dhcpDns1", "txtDNS1", "priDNS", "dnsServer1",
    ]
    secondary_candidates = [
        "txtDns2", "dns2", "secondaryDNS", "DNS2", "txtSecondaryDNS",
        "dhcpDns2", "txtDNS2", "secDNS", "dnsServer2",
    ]

    # Também tentar por xpath: campos com label "DNS" próximos
    primary_field = _find_field(driver, primary_candidates)
    secondary_field = _find_field(driver, secondary_candidates)

    # Fallback: procurar inputs que já contêm IPs de DNS
    if not primary_field:
        for inp in driver.find_elements(By.XPATH, "//input[@type='text']"):
            val = inp.get_attribute("value") or ""
            # Campo com IP de DNS (ex: 8.8.8.8, 1.1.1.1, 192.168.x.x)
            if val and all(p.isdigit() for p in val.split(".")) and len(val.split(".")) == 4:
                name = (inp.get_attribute("id") or inp.get_attribute("name") or "").lower()
                if "dns" in name and "2" not in name:
                    primary_field = inp
                    log.info("DNS primário detectado por valor IP: id=%s val=%s",
                             inp.get_attribute("id"), val)
                    break

    if not primary_field:
        log.warning("Campo de DNS primário não encontrado — listando todos os campos")
        _log_form_fields(driver)
        return False

    log.info("Campo DNS primário encontrado: id=%s",
             primary_field.get_attribute("id") or primary_field.get_attribute("name"))

    if not dry_run:
        primary_field.clear()
        primary_field.send_keys(primary_dns)
        log.info("DNS primário configurado: %s", primary_dns)

    if secondary_field:
        log.info("Campo DNS secundário encontrado: id=%s",
                 secondary_field.get_attribute("id") or secondary_field.get_attribute("name"))
        if not dry_run:
            secondary_field.clear()
            secondary_field.send_keys(secondary_dns)
            log.info("DNS secundário configurado: %s", secondary_dns)
    else:
        log.warning("Campo de DNS secundário não encontrado")

    return True


def _save_config(driver: webdriver.Chrome, dry_run: bool) -> bool:
    """Tenta clicar no botão de salvar configuração."""
    if dry_run:
        log.info("[DRY-RUN] Pulando salvamento")
        return True

    save_candidates = [
        "btnSave", "btnApply", "btnAplicar", "btnSubmit",
        "save", "apply", "btn_apply", "btn_save",
    ]

    # Procurar por ID primeiro
    save_btn = _find_field(driver, save_candidates)

    # Fallback: procurar por texto do botão
    if not save_btn:
        for btn in driver.find_elements(By.XPATH, "//input[@type='submit'] | //button | //a[@class[contains(.,'btn')]]"):
            txt = (btn.text or btn.get_attribute("value") or "").lower()
            if any(w in txt for w in ["salvar", "aplicar", "save", "apply"]):
                save_btn = btn
                log.info("Botão de salvar encontrado por texto: '%s'", txt)
                break

    if not save_btn:
        log.warning("Botão de salvar não encontrado — listando botões:")
        for btn in driver.find_elements(By.XPATH, "//input[@type='submit'] | //button"):
            log.warning("  Botão: id=%s text=%s value=%s",
                        btn.get_attribute("id"), btn.text, btn.get_attribute("value"))
        return False

    _screenshot(driver, "04_before_save")
    try:
        save_btn.click()
        time.sleep(3)
        _screenshot(driver, "05_after_save")
        log.info("Configuração salva ✓")
        return True
    except ElementNotInteractableException as exc:
        log.error("Botão de salvar não está interativo: %s", exc)
        # Tentar via JavaScript
        try:
            driver.execute_script("arguments[0].click();", save_btn)
            time.sleep(3)
            _screenshot(driver, "05_after_save_js")
            log.info("Configuração salva via JS ✓")
            return True
        except Exception as exc2:
            log.error("Falha ao salvar via JS: %s", exc2)
            return False


# ─── Validação pós-configuração ──────────────────────────────────────────────

def _validate_dhcp_settings(driver: webdriver.Chrome) -> dict[str, str]:
    """Re-abre a página e verifica os valores configurados."""
    log.info("Validando configuração...")
    driver.get(f"{ROUTER_URL}/settings-local-network.asp")
    time.sleep(3)
    result: dict[str, str] = {}

    for inp in driver.find_elements(By.XPATH, "//input[@type='text']"):
        val = inp.get_attribute("value") or ""
        id_ = inp.get_attribute("id") or inp.get_attribute("name") or ""
        if "dns" in id_.lower():
            result[id_] = val
            log.info("  DNS field %s = %s", id_, val)
    return result


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    """Ponto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Configura DNS/proxy no roteador Vivo/GVT via Selenium"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Apenas lê e mostra a página, sem salvar alterações"
    )
    parser.add_argument(
        "--screenshot-only", action="store_true",
        help="Apenas faz login e captura screenshots de diagnóstico"
    )
    parser.add_argument(
        "--primary-dns", default=PIHOLE_DNS,
        help=f"DNS primário a configurar (padrão: {PIHOLE_DNS})"
    )
    parser.add_argument(
        "--secondary-dns", default=FALLBACK_DNS,
        help=f"DNS secundário (padrão: {FALLBACK_DNS})"
    )
    args = parser.parse_args()

    username, password = _fetch_credentials()
    log.info("Configuração alvo — DNS primário: %s, secundário: %s",
             args.primary_dns, args.secondary_dns)
    if args.dry_run:
        log.info("Modo DRY-RUN ativo — nenhuma alteração será salva")

    driver = _create_driver()
    success = False
    try:
        # 1. Login
        if not _login(driver, username, password):
            log.error("Falha no login — verifique as credenciais")
            log.error("Dica: ROUTER_USER=xxx ROUTER_PASS=yyy python3 %s", __file__)
            return 1

        if args.screenshot_only:
            _navigate_to_local_network(driver)
            _log_form_fields(driver)
            log.info("Modo screenshot-only concluído")
            return 0

        # 2. Navegar para Rede Local
        if not _navigate_to_local_network(driver):
            log.error("Não foi possível acessar a página de Rede Local")
            return 1

        # 3. Mapear todos os campos disponíveis
        _log_form_fields(driver)

        # 4. Configurar DNS
        if not _set_dns_config(driver, args.primary_dns, args.secondary_dns, args.dry_run):
            log.error("Falha ao configurar DNS — veja HTML dump para análise manual")
            log.error("Próximo passo: ROUTER_USER=xxx ROUTER_PASS=yyy python3 %s --screenshot-only", __file__)
            return 1

        # 5. Salvar
        if not _save_config(driver, args.dry_run):
            log.warning("Botão de salvar não encontrado — configuração pode não ter sido persistida")

        # 6. Validar
        if not args.dry_run:
            result = _validate_dhcp_settings(driver)
            if any(PIHOLE_DNS in v for v in result.values()):
                log.info("Validação OK — Pi-hole (%s) está configurado como DNS ✓", PIHOLE_DNS)
                success = True
            else:
                log.warning("Validação: Pi-hole não encontrado nos campos DNS após salvar")
                log.warning("Resultado: %s", result)
                success = False
        else:
            log.info("Dry-run concluído — nenhuma alteração foi salva")
            success = True

        log.info("Processo concluído. Screenshots em: %s", SCREENSHOT_DIR)
        return 0 if success or args.dry_run else 1

    except WebDriverException as exc:
        log.error("Erro do WebDriver: %s", exc)
        _screenshot(driver, "error")
        return 1
    finally:
        time.sleep(1)
        driver.quit()


if __name__ == "__main__":
    sys.exit(main())
