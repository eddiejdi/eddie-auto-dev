#!/usr/bin/env python3
"""
Automatiza a criação de port forwarding UDP 28967 no roteador legado
para corrigir o QUIC do Storj Storage Node.

O roteador legado tem port forwarding em "Jogos & Aplicativos"
(settings-games.asp). O login usa #txtUser/#txtPass via JS.

Uso:
  ROUTER_URL=http://router.local python3 scripts/router_udp_port_forward.py
"""

import json
import logging
import os
import sys
import time
import urllib.request
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

ROUTER_URL = os.environ.get("ROUTER_URL", "")
SCREENSHOT_DIR = Path("/tmp")
TARGET_IP = "192.168.15.2"
TARGET_PORT = "28967"
SECRETS_API = os.environ.get(
    "SECRETS_API_URL", "http://192.168.15.2:8088"
)
SECRETS_KEY = os.environ.get(
    "SECRETS_API_KEY",
    "188bbf4c1b43ed1730005288f89ad2d0708c071eca142a2b335e026e95e8cee3",
)


def _fetch_credentials() -> tuple[str, str]:
    """Busca credenciais do roteador no Secrets Agent."""
    url = f"{SECRETS_API}/secrets/eddie%2Frouter_credentials"
    req = urllib.request.Request(url, headers={"X-API-KEY": SECRETS_KEY})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    creds = json.loads(data["value"]) if isinstance(data["value"], str) else data["value"]
    return creds["username"], creds["password"]


def _save_screenshot(driver: webdriver.Chrome, name: str) -> str:
    """Salva screenshot para debug."""
    path = SCREENSHOT_DIR / f"router_{name}_{int(time.time())}.png"
    driver.save_screenshot(str(path))
    log.info("Screenshot: %s", path)
    return str(path)


def _create_driver() -> webdriver.Chrome:
    """Cria driver Chrome headless."""
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,900")
    return webdriver.Chrome(options=opts)


def _login(driver: webdriver.Chrome, username: str, password: str) -> bool:
    """Faz login no roteador Vivo/GVT."""
    if not ROUTER_URL:
        log.error("ROUTER_URL não definido. O roteador legado não faz parte do contrato operacional padrão.")
        return False

    log.info("Abrindo roteador: %s", ROUTER_URL)
    driver.get(ROUTER_URL)
    time.sleep(2)
    _save_screenshot(driver, "01_initial")

    try:
        wait = WebDriverWait(driver, 10)
        user_field = wait.until(EC.presence_of_element_located((By.ID, "txtUser")))
        pass_field = driver.find_element(By.ID, "txtPass")

        user_field.clear()
        user_field.send_keys(username)
        pass_field.clear()
        pass_field.send_keys(password)

        btn = driver.find_element(By.ID, "btnLogin")
        btn.click()
        log.info("Login enviado, aguardando...")
        time.sleep(3)
        _save_screenshot(driver, "02_after_login")

        # Verificar se login deu certo (sidebar visível)
        page_src = driver.page_source
        if "Falha no login" in page_src and "txtUser" in page_src:
            log.error("Login falhou - credenciais inválidas")
            return False

        log.info("Login bem-sucedido")
        return True

    except TimeoutException:
        log.error("Timeout esperando formulário de login")
        _save_screenshot(driver, "02_login_timeout")
        return False


def _navigate_to_games(driver: webdriver.Chrome) -> bool:
    """Navega para Jogos & Aplicativos (port forwarding)."""
    log.info("Navegando para Jogos & Aplicativos...")
    driver.get(f"{ROUTER_URL}/settings-games.asp")
    time.sleep(3)
    _save_screenshot(driver, "03_games_page")

    page_src = driver.page_source
    if "txtUser" in page_src and "Autenticação" in page_src:
        log.error("Sessão expirou, precisa re-logar")
        return False

    log.info("Página de Jogos & Aplicativos carregada")
    return True


def _check_existing_rules(driver: webdriver.Chrome) -> list[dict[str, str]]:
    """Lista regras existentes de port forwarding."""
    rules: list[dict[str, str]] = []
    try:
        # Tentar encontrar tabela de regras existentes
        tables = driver.find_elements(By.TAG_NAME, "table")
        for table in tables:
            text = table.text
            if TARGET_PORT in text or "28967" in text:
                log.info("Regra existente encontrada contendo porta %s", TARGET_PORT)
                rules.append({"text": text[:200]})
    except NoSuchElementException:
        pass
    return rules


def _add_udp_port_forward(driver: webdriver.Chrome) -> bool:
    """Adiciona regra de port forwarding UDP 28967."""
    log.info("Analisando formulário de port forwarding...")
    _save_screenshot(driver, "04_before_add")

    page_src = driver.page_source
    log.info("Tamanho da página: %d chars", len(page_src))

    # Dump da página para análise
    dump_path = SCREENSHOT_DIR / f"router_games_dump_{int(time.time())}.html"
    dump_path.write_text(page_src, encoding="utf-8")
    log.info("HTML dump: %s", dump_path)

    # Listar todos os elementos de formulário
    inputs = driver.find_elements(By.TAG_NAME, "input")
    selects = driver.find_elements(By.TAG_NAME, "select")
    buttons = driver.find_elements(By.TAG_NAME, "button")
    links = driver.find_elements(By.TAG_NAME, "a")

    log.info("Formulário: %d inputs, %d selects, %d buttons, %d links",
             len(inputs), len(selects), len(buttons), len(links))

    for inp in inputs:
        inp_id = inp.get_attribute("id") or ""
        inp_name = inp.get_attribute("name") or ""
        inp_type = inp.get_attribute("type") or ""
        inp_val = inp.get_attribute("value") or ""
        if inp_type not in ("hidden",):
            log.info("  Input: id=%s name=%s type=%s value=%s",
                     inp_id, inp_name, inp_type, inp_val)

    for sel in selects:
        sel_id = sel.get_attribute("id") or ""
        sel_name = sel.get_attribute("name") or ""
        options = [o.text for o in sel.find_elements(By.TAG_NAME, "option")]
        log.info("  Select: id=%s name=%s options=%s", sel_id, sel_name, options[:5])

    # A interface do Vivo/GVT normalmente tem:
    # - Select para escolher tipo (TCP, UDP, TCP+UDP, Personalizado)
    # - Input para porta inicial / porta final
    # - Input para IP do dispositivo
    # - Botão para adicionar

    # Estratégia 1: Procurar por seletores conhecidos do Vivo/GVT
    try:
        return _try_vivo_gvt_form(driver)
    except Exception as e:
        log.warning("Estratégia Vivo/GVT falhou: %s", e)

    # Estratégia 2: Procurar por padrão genérico
    try:
        return _try_generic_form(driver)
    except Exception as e:
        log.warning("Estratégia genérica falhou: %s", e)

    log.error("Não consegui preencher o formulário automaticamente")
    log.info("Verifique o dump HTML em %s para análise manual", dump_path)
    return False


def _try_vivo_gvt_form(driver: webdriver.Chrome) -> bool:
    """Tenta preencher formulário padrão Vivo/GVT."""
    # Formulários GVT costumam ter IDs como:
    # Protocol select: selProtocol, protocol, ddlProtocol
    # Port start: txtPortStart, startPort, portaInicio
    # Port end: txtPortEnd, endPort, portaFim
    # IP: txtIP, ipAddress, host
    # Add button: btnAdd, addRule, btnAplicar

    protocol_selectors = [
        "selProtocol", "protocol", "ddlProtocol", "cboProtocol",
        "protocolType", "cbProtocol",
    ]
    port_start_selectors = [
        "txtPortStart", "startPort", "portaInicio", "txtStartPort",
        "txtExternalPortStart", "PublicPortStart", "txtSPort",
    ]
    port_end_selectors = [
        "txtPortEnd", "endPort", "portaFim", "txtEndPort",
        "txtExternalPortEnd", "PublicPortEnd", "txtEPort",
    ]
    ip_selectors = [
        "txtIP", "ipAddress", "host", "txtHost",
        "txtInternalIP", "InternalIP", "txtServerIP",
    ]
    add_selectors = [
        "btnAdd", "addRule", "btnAplicar", "btnSave",
        "btnAddRule", "btnSubmit", "btn_apply",
    ]

    def _find_by_ids(ids: list[str]) -> webdriver.Chrome | None:
        for id_ in ids:
            try:
                el = driver.find_element(By.ID, id_)
                if el.is_displayed():
                    return el
            except NoSuchElementException:
                continue
        return None

    # Encontrar protocol select
    protocol_el = _find_by_ids(protocol_selectors)
    if not protocol_el:
        # Tentar por name
        for sel in driver.find_elements(By.TAG_NAME, "select"):
            opts_text = " ".join(o.text.lower() for o in sel.find_elements(By.TAG_NAME, "option"))
            if "udp" in opts_text:
                protocol_el = sel
                log.info("Encontrado select de protocolo por conteúdo de opções")
                break

    if not protocol_el:
        raise RuntimeError("Select de protocolo não encontrado")

    # Selecionar UDP
    sel = Select(protocol_el)
    udp_found = False
    for opt in sel.options:
        opt_text = opt.text.strip().upper()
        if opt_text == "UDP":
            sel.select_by_visible_text(opt.text.strip())
            udp_found = True
            log.info("Selecionado protocolo: %s", opt.text.strip())
            break
    if not udp_found:
        # Tentar por value
        for opt in sel.options:
            if "udp" in (opt.get_attribute("value") or "").lower():
                sel.select_by_value(opt.get_attribute("value"))
                udp_found = True
                log.info("Selecionado protocolo por value: %s", opt.get_attribute("value"))
                break
    if not udp_found:
        raise RuntimeError("Opção UDP não encontrada no select de protocolo")

    time.sleep(1)

    # Preencher porta start
    port_start_el = _find_by_ids(port_start_selectors)
    if not port_start_el:
        visible_inputs = [i for i in driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
                          if i.is_displayed() and not i.get_attribute("readonly")]
        if len(visible_inputs) >= 2:
            port_start_el = visible_inputs[0]
            log.info("Usando primeiro input visível como porta início")
    if port_start_el:
        port_start_el.clear()
        port_start_el.send_keys(TARGET_PORT)
        log.info("Porta início: %s", TARGET_PORT)

    # Preencher porta end
    port_end_el = _find_by_ids(port_end_selectors)
    if not port_end_el and port_start_el:
        visible_inputs = [i for i in driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
                          if i.is_displayed() and not i.get_attribute("readonly")
                          and i != port_start_el]
        if visible_inputs:
            port_end_el = visible_inputs[0]
            log.info("Usando próximo input visível como porta fim")
    if port_end_el:
        port_end_el.clear()
        port_end_el.send_keys(TARGET_PORT)
        log.info("Porta fim: %s", TARGET_PORT)

    # Preencher IP
    ip_el = _find_by_ids(ip_selectors)
    if ip_el:
        ip_el.clear()
        ip_el.send_keys(TARGET_IP)
        log.info("IP destino: %s", TARGET_IP)
    else:
        # Pode ser que o IP seja preenchido via octetos separados
        ip_parts = TARGET_IP.split(".")
        for i, part in enumerate(ip_parts):
            for suffix in [str(i + 1), f"_{i}", f"[{i}]"]:
                for prefix in ["txtIP", "ip", "IP"]:
                    try:
                        el = driver.find_element(By.ID, f"{prefix}{suffix}")
                        if el.is_displayed():
                            el.clear()
                            el.send_keys(part)
                            log.info("IP octeto %d: %s", i + 1, part)
                            break
                    except NoSuchElementException:
                        continue

    _save_screenshot(driver, "05_form_filled")

    # Clicar botão de adicionar
    add_el = _find_by_ids(add_selectors)
    if not add_el:
        # Procurar por links/botões com texto "Adicionar", "Aplicar", "Salvar"
        for tag in ["a", "button", "input"]:
            for el in driver.find_elements(By.TAG_NAME, tag):
                el_text = (el.text or el.get_attribute("value") or "").lower()
                if any(k in el_text for k in ["adicionar", "aplicar", "salvar", "add", "save"]):
                    add_el = el
                    log.info("Encontrado botão: %s (tag=%s)", el_text, tag)
                    break
            if add_el:
                break

    if add_el:
        add_el.click()
        log.info("Botão de adicionar clicado")
        time.sleep(3)
        _save_screenshot(driver, "06_after_add")
        return True

    raise RuntimeError("Botão de adicionar não encontrado")


def _try_generic_form(driver: webdriver.Chrome) -> bool:
    """Tenta preencher formulário por heurísticas genéricas."""
    # Procurar iframes (alguns roteadores usam iframes)
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    if iframes:
        log.info("Encontrados %d iframes, tentando switchar", len(iframes))
        for i, iframe in enumerate(iframes):
            try:
                driver.switch_to.frame(iframe)
                log.info("Switched to iframe %d", i)
                result = _try_vivo_gvt_form(driver)
                if result:
                    driver.switch_to.default_content()
                    return True
                driver.switch_to.default_content()
            except Exception:
                driver.switch_to.default_content()

    raise RuntimeError("Nenhum formulário genérico encontrado")


def main() -> int:
    """Ponto de entrada principal."""
    log.info("=== Router UDP Port Forward - Storj QUIC Fix ===")

    # Buscar credenciais
    try:
        username, password = _fetch_credentials()
        log.info("Credenciais obtidas do Secrets Agent (user: %s)", username)
    except Exception as e:
        log.error("Falha ao obter credenciais: %s", e)
        return 1

    # Criar driver
    try:
        driver = _create_driver()
    except WebDriverException as e:
        log.error("Falha ao criar Chrome WebDriver: %s", e)
        return 1

    try:
        # Login
        if not _login(driver, username, password):
            return 1

        # Navegar para port forwarding
        if not _navigate_to_games(driver):
            return 1

        # Verificar regras existentes
        existing = _check_existing_rules(driver)
        if existing:
            log.info("Regras existentes com porta %s: %s", TARGET_PORT, existing)

        # Adicionar regra UDP
        if _add_udp_port_forward(driver):
            log.info("Regra UDP %s adicionada com sucesso!", TARGET_PORT)
            return 0
        else:
            log.error("Falha ao adicionar regra UDP")
            return 1

    except Exception as e:
        log.error("Erro inesperado: %s", e, exc_info=True)
        _save_screenshot(driver, "error")
        return 1
    finally:
        driver.quit()


if __name__ == "__main__":
    sys.exit(main())
