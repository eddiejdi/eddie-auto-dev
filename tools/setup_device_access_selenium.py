#!/usr/bin/env python3
"""
Selenium automation para configurar Google Device Access + SDM.

Passos automatizados:
1. Abre Device Access Console (https://console.nest.google.com/device-access)
2. Verifica se já existe projeto ou cria um novo
3. Extrai o Enterprise/Project ID
4. Faz OAuth com scope sdm.service usando o client_id correto
5. Troca código por tokens e salva em .env e google_home_credentials.json
6. Testa a API SDM listando dispositivos

Uso:
  python3 tools/setup_device_access_selenium.py
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
CREDS_FILE = REPO_ROOT / "credentials_google.json"
ENV_FILE = REPO_ROOT / ".env"
HOME_CREDS_FILE = REPO_ROOT / "google_home_credentials.json"
SCREENSHOT_DIR = REPO_ROOT / "tmp_selenium_device_access"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

DEVICE_ACCESS_URL = "https://console.nest.google.com/device-access"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SDM_API_BASE = "https://smartdevicemanagement.googleapis.com/v1"

# Carrega credenciais do arquivo
with open(CREDS_FILE) as f:
    cj = json.load(f)
    inst = cj.get("installed", cj.get("web", {}))
    CLIENT_ID = inst["client_id"]
    CLIENT_SECRET = inst["client_secret"]

REDIRECT_URI = "http://localhost:8080"


def screenshot(driver, name):
    path = SCREENSHOT_DIR / f"{name}.png"
    driver.save_screenshot(str(path))
    print(f"  Screenshot: {path}")
    return path


def create_driver():
    """Cria Chrome driver com perfil do usuário para manter sessão Google."""
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    # Usar perfil temporário (evita conflito com Chrome já aberto)
    # O usuário precisará fazer login manualmente
    driver = webdriver.Chrome(options=options)
    return driver


def wait_for_login(driver, timeout=120):
    """Espera o usuário estar logado no Google."""
    print("Verificando se está logado no Google...")
    try:
        # Se já estiver na página do Device Access, está logado
        WebDriverWait(driver, timeout).until(
            lambda d: "device-access" in d.current_url.lower()
            or "accounts.google.com" not in d.current_url.lower()
            or d.find_elements(By.CSS_SELECTOR, "[data-project-id], .project-card, mat-card, .mdc-card")
        )
    except Exception:
        pass


def extract_enterprise_ids(driver):
    """Tenta extrair Enterprise/Project IDs da página."""
    ids_found = set()
    body_text = driver.find_element(By.TAG_NAME, "body").text

    # Padrões comuns
    patterns = [
        r"(?:Project ID|Enterprise ID|project.id)[:\s]*([a-f0-9\-]{30,50})",
        r"enterprises/([a-f0-9\-]{30,50})",
        r"([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})",  # UUID
    ]
    for pat in patterns:
        for m in re.finditer(pat, body_text, re.IGNORECASE):
            ids_found.add(m.group(1))

    # Procurar em atributos de elementos
    for el in driver.find_elements(By.CSS_SELECTOR, "[data-project-id], [data-enterprise-id]"):
        for attr in ["data-project-id", "data-enterprise-id"]:
            val = el.get_attribute(attr)
            if val:
                ids_found.add(val)

    # Procurar em links href
    for el in driver.find_elements(By.TAG_NAME, "a"):
        href = el.get_attribute("href") or ""
        for m in re.finditer(r"project/([a-f0-9\-]+)", href):
            ids_found.add(m.group(1))

    return ids_found


def step1_open_device_access(driver):
    """Passo 1: Abrir Device Access Console e verificar projetos existentes."""
    print("\n" + "=" * 60)
    print("PASSO 1: Abrindo Device Access Console")
    print("=" * 60)

    driver.get(DEVICE_ACCESS_URL)
    time.sleep(5)
    screenshot(driver, "01_device_access_initial")

    # Se redirecionou para login, aguardar
    if "accounts.google.com" in driver.current_url:
        print("Aguardando login no Google (faça login no navegador)...")
        WebDriverWait(driver, 180).until(
            lambda d: "accounts.google.com" not in d.current_url
        )
        time.sleep(3)
        screenshot(driver, "01b_after_login")

    print(f"URL atual: {driver.current_url}")
    return True


def step2_find_or_create_project(driver):
    """Passo 2: Encontrar projeto existente ou criar um novo."""
    print("\n" + "=" * 60)
    print("PASSO 2: Procurando projetos Device Access")
    print("=" * 60)

    time.sleep(3)
    screenshot(driver, "02_projects_page")

    body_text = driver.find_element(By.TAG_NAME, "body").text
    page_source = driver.page_source

    # Extrair IDs
    ids = extract_enterprise_ids(driver)
    if ids:
        print(f"IDs encontrados na página: {ids}")
        return ids

    # Procurar botão "Create project" se não há projetos
    create_buttons = driver.find_elements(By.XPATH,
        "//*[contains(text(),'Create project') or contains(text(),'Create a project') or contains(text(),'Criar projeto')]")

    if create_buttons:
        print("Nenhum projeto encontrado. Criando novo projeto...")
        create_buttons[0].click()
        time.sleep(3)
        screenshot(driver, "02b_create_project_dialog")

        # Preencher nome do projeto
        name_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[name*='name'], input[placeholder*='name']")
        for inp in name_inputs:
            if inp.is_displayed():
                inp.clear()
                inp.send_keys("Eddie Home Access")
                print("Nome do projeto preenchido: Eddie Home Access")
                break

        time.sleep(1)
        screenshot(driver, "02c_project_name_filled")

        # Procurar campo de OAuth Client ID e preencher
        oauth_inputs = driver.find_elements(By.CSS_SELECTOR,
            "input[placeholder*='client'], input[placeholder*='OAuth'], input[name*='oauth'], input[name*='client']")
        for inp in oauth_inputs:
            if inp.is_displayed():
                inp.clear()
                inp.send_keys(CLIENT_ID)
                print(f"OAuth Client ID preenchido: {CLIENT_ID[:30]}...")
                break

        time.sleep(1)
        screenshot(driver, "02d_oauth_filled")

        # Aceitar termos (checkbox)
        checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox'], mat-checkbox, .mdc-checkbox")
        for cb in checkboxes:
            if cb.is_displayed():
                try:
                    cb.click()
                    print("Checkbox de termos marcado")
                except Exception:
                    driver.execute_script("arguments[0].click()", cb)

        time.sleep(1)

        # Clicar em Next/Create/Submit
        submit_buttons = driver.find_elements(By.XPATH,
            "//button[contains(text(),'Next') or contains(text(),'Create') or contains(text(),'Submit') or contains(text(),'Próximo') or contains(text(),'Criar')]")
        for btn in submit_buttons:
            if btn.is_displayed() and btn.is_enabled():
                btn.click()
                print("Botão de criação clicado")
                break

        time.sleep(5)
        screenshot(driver, "02e_after_create")

        # Tentar extrair IDs novamente
        ids = extract_enterprise_ids(driver)
        if ids:
            print(f"IDs encontrados após criação: {ids}")
            return ids

    # Se ainda não encontrou, tentar navegar por links de projeto
    project_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='project']")
    for link in project_links:
        href = link.get_attribute("href") or ""
        if "project/" in href:
            print(f"Encontrado link de projeto: {href}")
            link.click()
            time.sleep(3)
            screenshot(driver, "02f_project_detail")
            ids = extract_enterprise_ids(driver)
            if ids:
                return ids

    # Último recurso: imprimir todo o texto da página para análise
    print("\nTexto completo da página (para debug):")
    print(body_text[:3000])
    print("\n--- Fim do texto ---")

    return ids


def step3_oauth_sdm(driver, enterprise_id):
    """Passo 3: Fazer OAuth com scope sdm.service e obter tokens."""
    print("\n" + "=" * 60)
    print(f"PASSO 3: OAuth SDM (Enterprise: {enterprise_id})")
    print("=" * 60)

    # Construir URL OAuth com scope sdm.service
    auth_params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/sdm.service",
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(auth_params)

    print(f"Abrindo URL de autorização SDM...")
    driver.get(auth_url)
    time.sleep(3)
    screenshot(driver, "03_oauth_consent")

    # Aguardar redirecionamento para localhost com code
    print("Aguardando autorização (selecione conta e autorize)...")
    try:
        WebDriverWait(driver, 180).until(
            lambda d: "localhost" in d.current_url and "code=" in d.current_url
        )
    except Exception:
        screenshot(driver, "03b_oauth_timeout")
        print("Timeout aguardando OAuth callback.")
        # Tentar extrair code da URL atual
        if "code=" not in driver.current_url:
            print(f"URL atual: {driver.current_url}")
            return None

    # Extrair código da URL
    url = driver.current_url
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    code = params.get("code", [None])[0]

    if not code:
        print("Não foi possível extrair o código de autorização.")
        return None

    print(f"Código obtido: {code[:20]}...")

    # Trocar código por tokens
    print("Trocando código por tokens...")
    data = urllib.parse.urlencode({
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req) as resp:
            tokens = json.loads(resp.read())
    except Exception as e:
        print(f"Erro ao trocar código: {e}")
        return None

    if "access_token" not in tokens:
        print(f"Resposta inesperada: {tokens}")
        return None

    print("Tokens obtidos com sucesso!")
    return tokens


def step4_save_credentials(tokens, enterprise_id):
    """Passo 4: Salvar credenciais em .env e JSON."""
    print("\n" + "=" * 60)
    print("PASSO 4: Salvando credenciais")
    print("=" * 60)

    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token", "")

    # Salvar google_home_credentials.json
    creds = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": tokens.get("token_type", "Bearer"),
        "expires_in": tokens.get("expires_in", 3599),
        "sdm_project_id": enterprise_id,
    }
    with open(HOME_CREDS_FILE, "w") as f:
        json.dump(creds, f, indent=2)
    print(f"Salvo: {HOME_CREDS_FILE}")

    # Atualizar .env
    env_lines = []
    if ENV_FILE.exists():
        with open(ENV_FILE) as f:
            env_lines = [
                l for l in f.readlines()
                if not l.startswith("GOOGLE_HOME_TOKEN=")
                and not l.startswith("GOOGLE_HOME_REFRESH_TOKEN=")
                and not l.startswith("GOOGLE_SDM_PROJECT_ID=")
            ]
    env_lines.append(f"GOOGLE_HOME_TOKEN={access_token}\n")
    if refresh_token:
        env_lines.append(f"GOOGLE_HOME_REFRESH_TOKEN={refresh_token}\n")
    env_lines.append(f"GOOGLE_SDM_PROJECT_ID={enterprise_id}\n")
    with open(ENV_FILE, "w") as f:
        f.writelines(env_lines)
    print(f"Salvo: {ENV_FILE}")

    # Salvar em agent_data
    agent_creds_dir = REPO_ROOT / "agent_data" / "home_automation"
    agent_creds_dir.mkdir(parents=True, exist_ok=True)
    agent_creds_file = agent_creds_dir / "google_credentials.json"
    with open(agent_creds_file, "w") as f:
        json.dump(creds, f, indent=2)
    print(f"Salvo: {agent_creds_file}")

    return access_token


def step5_test_sdm(access_token, enterprise_id):
    """Passo 5: Testar API SDM listando dispositivos."""
    print("\n" + "=" * 60)
    print("PASSO 5: Testando API SDM")
    print("=" * 60)

    url = f"{SDM_API_BASE}/enterprises/{enterprise_id}/devices"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        devices = data.get("devices", [])
        print(f"\nDispositivos encontrados: {len(devices)}")
        for dev in devices:
            name = dev.get("name", "?")
            dtype = dev.get("type", "?")
            traits = list(dev.get("traits", {}).keys())
            parent = dev.get("parentRelations", [{}])
            room = parent[0].get("displayName", "?") if parent else "?"
            print(f"  - {name}")
            print(f"    Tipo: {dtype}")
            print(f"    Sala: {room}")
            print(f"    Traits: {', '.join(t.split('.')[-1] for t in traits[:5])}")
        return devices
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"Erro HTTP {e.code}: {body[:500]}")
        return []
    except Exception as e:
        print(f"Erro: {e}")
        return []


def main():
    print("=" * 60)
    print("SETUP COMPLETO: Google Device Access + SDM")
    print("=" * 60)
    print(f"Client ID: {CLIENT_ID[:40]}...")
    print(f"Redirect URI: {REDIRECT_URI}")

    driver = create_driver()
    enterprise_id = None

    try:
        # Passo 1: Abrir Device Access Console
        step1_open_device_access(driver)

        # Passo 2: Encontrar ou criar projeto
        ids = step2_find_or_create_project(driver)

        if ids:
            enterprise_id = list(ids)[0]
            print(f"\nEnterprise ID selecionado: {enterprise_id}")
        else:
            print("\nNão foi possível extrair ID automaticamente.")
            print("Verifique os screenshots em:", SCREENSHOT_DIR)
            manual = input("Cole o Enterprise/Project ID aqui: ").strip()
            if manual:
                enterprise_id = manual
            else:
                print("Abortando.")
                return 1

        # Passo 3: OAuth com scope sdm.service
        tokens = step3_oauth_sdm(driver, enterprise_id)
        if not tokens:
            print("Falha ao obter tokens OAuth.")
            return 1

        # Passo 4: Salvar credenciais
        access_token = step4_save_credentials(tokens, enterprise_id)

        # Passo 5: Testar API SDM
        devices = step5_test_sdm(access_token, enterprise_id)

        print("\n" + "=" * 60)
        if devices:
            print(f"SUCESSO! {len(devices)} dispositivos sincronizados.")
        else:
            print("CONCLUÍDO — mas nenhum dispositivo encontrado.")
            print("Verifique se há dispositivos vinculados ao Google Home.")
        print("=" * 60)

        print(f"\nexport GOOGLE_HOME_TOKEN='{access_token[:30]}...'")
        print(f"export GOOGLE_SDM_PROJECT_ID='{enterprise_id}'")

        return 0

    except KeyboardInterrupt:
        print("\nOperação cancelada.")
        return 1
    except Exception as e:
        print(f"\nErro: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        screenshot(driver, "99_final")
        print("Fechando navegador em 3s...")
        time.sleep(3)
        driver.quit()


if __name__ == "__main__":
    sys.exit(main())
