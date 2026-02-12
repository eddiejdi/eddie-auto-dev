#!/usr/bin/env python3
"""
🤖 AGENTE SELENIUM v3 — OAuth com servidor HTTP callback integrado

Arquitetura correta:
  1. Encontra porta TCP livre
  2. Inicia servidor HTTP nessa porta (captura o redirect do Google)
  3. Gera URL OAuth COM redirect_uri=http://localhost:PORT
  4. Selenium abre URL, usuário faz login + consent
  5. Google redireciona para http://localhost:PORT/?code=XXX
  6. Servidor HTTP captura o code automaticamente
  7. Troca code por token (mesmo flow, redirect_uri coincide)
  8. Busca currículos no Drive
"""

import http.server
import json
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# ── Configuração ──────────────────────────────────────────────────────────────
LOCAL_CREDS = Path("/home/edenilson/eddie-auto-dev/credentials_google.json")
DRIVE_DIR   = Path("/home/edenilson/eddie-auto-dev/drive_data")
DRIVE_TOKEN = DRIVE_DIR / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
]


# ── 1. Porta livre ────────────────────────────────────────────────────────────
def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ── 2. Servidor HTTP callback ─────────────────────────────────────────────────
class CallbackHandler(http.server.BaseHTTPRequestHandler):
    auth_code = None
    auth_error = None

    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        if "code" in qs:
            CallbackHandler.auth_code = qs["code"][0]
            self._respond(200, "<h1>&#10004; Autorizado!</h1><p>Pode fechar esta janela.</p>")
        elif "error" in qs:
            CallbackHandler.auth_error = qs["error"][0]
            self._respond(400, f"<h1>Erro: {qs['error'][0]}</h1>")
        else:
            self._respond(200, "OK")

    def _respond(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"<html><body>{body}</body></html>".encode())

    def log_message(self, *_):
        pass  # silencia


def start_callback_server(port):
    srv = http.server.HTTPServer(("127.0.0.1", port), CallbackHandler)
    srv.timeout = 180
    # handle_request atende UM request e retorna
    t = threading.Thread(target=srv.handle_request, daemon=True)
    t.start()
    return srv, t


# ── 3. Flow OAuth ────────────────────────────────────────────────────────────
def create_flow(port):
    flow = InstalledAppFlow.from_client_secrets_file(str(LOCAL_CREDS), SCOPES)
    flow.redirect_uri = f"http://localhost:{port}"
    auth_url, state = flow.authorization_url(
        access_type="offline", prompt="consent",
    )
    # Validar
    assert "redirect_uri=" in auth_url, "BUG: redirect_uri ausente!"
    assert f"localhost%3A{port}" in auth_url or f"localhost:{port}" in auth_url, \
        f"BUG: porta {port} não está na URL!"
    return flow, auth_url, state


# ── 4. Selenium ──────────────────────────────────────────────────────────────
def create_driver():
    opts = Options()
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    svc = Service(ChromeDriverManager().install())
    drv = webdriver.Chrome(service=svc, options=opts)
    drv.set_window_size(1280, 900)
    return drv


def selenium_login_and_consent(driver, auth_url):
    """Navega, faz login (se possível) e clica nos botões de consent."""
    driver.get(auth_url)
    time.sleep(3)

    # ── Login automático (se credenciais salvas) ──
    cred_file = Path.home() / ".google_credentials.json"
    email = password = None
    if cred_file.exists():
        try:
            d = json.loads(cred_file.read_text())
            email, password = d.get("email"), d.get("password")
        except Exception:
            pass

    if email and password:
        try:
            # Pode ser que o Chrome já tenha sessão — verificar se identifierId existe
            try:
                ef = WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((By.ID, "identifierId"))
                )
                ef.clear(); ef.send_keys(email)
                time.sleep(0.5)
                driver.find_element(By.ID, "identifierNext").click()
                time.sleep(4)
            except Exception:
                print("  ℹ️  Campo de email não encontrado (sessão existente?)")

            # Tentar senha
            try:
                pf = WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((By.NAME, "password"))
                )
                pf.clear(); pf.send_keys(password)
                time.sleep(0.5)
                driver.find_element(By.ID, "passwordNext").click()
                print("  ✓ Credenciais enviadas automaticamente")
                time.sleep(5)
            except Exception:
                print("  ℹ️  Campo de senha não encontrado (já logado?)")
                time.sleep(3)
        except Exception as e:
            print(f"  ⚠️  Login automático falhou ({type(e).__name__})")
            print("  👉 Faça login manualmente no navegador aberto.")
            print("  ⏳ Aguardando 60s para login manual...")
            time.sleep(60)
    else:
        print("  ℹ️  Sem credenciais salvas — faça login no navegador.")
        print("  ⏳ Aguardando 60s para login manual...")
        time.sleep(60)

    # ── Consent buttons ──
    time.sleep(3)
    btn_xpaths = [
        "//button[contains(., 'Continuar')]",
        "//button[contains(., 'Continue')]",
        "//button[contains(., 'Permitir')]",
        "//button[contains(., 'Allow')]",
        "//span[contains(text(),'Continuar')]/..",
        "//span[contains(text(),'Continue')]/..",
        "//*[@id='submit_approve_access']",
    ]
    for attempt in range(2):  # até 2 telas de consent
        clicked = False
        for xp in btn_xpaths:
            try:
                btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, xp))
                )
                btn.click()
                clicked = True
                print(f"  ✓ Botão clicado: {btn.text!r}")
                time.sleep(3)
                break
            except Exception:
                continue
        if not clicked and attempt == 0:
            print("  ⚠️  Botão não encontrado — clique manualmente no navegador.")
            print("  ⏳ Aguardando 30s para clique manual...")
            time.sleep(30)
        time.sleep(2)


# ── 5. Buscar currículos ─────────────────────────────────────────────────────
def search_resumes(creds):
    print("\n" + "=" * 70)
    print("  📂 BUSCANDO CURRÍCULOS NO GOOGLE DRIVE")
    print("=" * 70)

    drive = build("drive", "v3", credentials=creds)
    terms = ["curriculo", "currículo", "curriculum", "cv", "resume"]
    all_files = []

    for term in terms:
        q = f"name contains '{term}' and trashed=false"
        try:
            res = drive.files().list(
                q=q, pageSize=10, orderBy="modifiedTime desc",
                fields="files(id,name,mimeType,size,modifiedTime,webViewLink)",
            ).execute()
            files = res.get("files", [])
            if files:
                print(f"  ✓ '{term}': {len(files)} arquivo(s)")
                all_files.extend(files)
        except Exception:
            pass

    if not all_files:
        print("  ℹ️  Nenhum com nome de currículo. Buscando PDFs recentes…")
        try:
            res = drive.files().list(
                q="mimeType='application/pdf' and trashed=false",
                pageSize=20, orderBy="modifiedTime desc",
                fields="files(id,name,mimeType,size,modifiedTime,webViewLink)",
            ).execute()
            all_files = res.get("files", [])
        except Exception:
            pass

    if not all_files:
        print("  ❌ Nenhum arquivo encontrado.")
        return

    unique = {f["id"]: f for f in all_files}
    ordered = sorted(unique.values(), key=lambda f: f.get("modifiedTime", ""), reverse=True)

    print(f"\n  📊 {len(ordered)} arquivo(s):\n")
    for i, f in enumerate(ordered[:10], 1):
        name = f.get("name", "?")
        size = int(f.get("size", 0)) / 1024
        mod  = f.get("modifiedTime", "")[:10]
        link = f.get("webViewLink", "N/A")
        star = " ⭐ MAIS RECENTE" if i == 1 else ""
        print(f"  [{i}] {name}{star}")
        print(f"      {size:.0f} KB · {mod}")
        print(f"      🔗 {link}\n")

    print("=" * 70)


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("\n" + "=" * 70)
    print("  🤖 AGENTE SELENIUM v3 — OAuth + Servidor Callback")
    print("=" * 70)

    if not LOCAL_CREDS.exists():
        print("\n📥 Baixando credentials.json do servidor…")
        subprocess.run(
            ["scp", "homelab@192.168.15.2:/home/homelab/myClaude/credentials.json",
             str(LOCAL_CREDS)],
            check=True, timeout=15,
        )
    DRIVE_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Porta livre
    port = find_free_port()
    print(f"\n[1/6] Porta livre: {port}")

    # 2. Servidor callback
    print(f"[2/6] Servidor callback em 127.0.0.1:{port}…")
    srv, srv_thread = start_callback_server(port)
    print(f"  ✅ Servidor ativo, aguardando redirect do Google")

    # 3. Gerar URL OAuth
    print(f"[3/6] Gerando URL de autorização…")
    flow, auth_url, state = create_flow(port)
    print(f"  ✅ URL contém redirect_uri=http://localhost:{port}")

    # 4. Selenium
    print(f"\n[4/6] Abrindo navegador…")
    driver = create_driver()
    try:
        selenium_login_and_consent(driver, auth_url)

        # 5. Esperar código
        print(f"\n[5/6] Aguardando código via callback server…")
        srv_thread.join(timeout=90)

        code = CallbackHandler.auth_code
        error = CallbackHandler.auth_error

        # Fallback: tentar extrair da URL do browser
        if not code and not error:
            try:
                url = driver.current_url
                m = re.search(r"code=([^&]+)", url)
                if m:
                    code = m.group(1)
                    print(f"  ✓ Código extraído da URL do browser (fallback)")
            except Exception:
                pass
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    if error:
        print(f"\n❌ Google retornou erro: {error}")
        sys.exit(1)
    if not code:
        print("\n❌ Código não capturado. Possíveis causas:")
        print("   - Autorização não foi completada")
        print("   - Timeout de 90s expirou")
        sys.exit(1)

    print(f"  ✅ Código: {code[:20]}…")

    # 6. Token + busca
    print(f"\n[6/6] Trocando código por token…")
    flow.fetch_token(code=code)
    creds = flow.credentials

    token_data = {
        "token":         creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri":     creds.token_uri,
        "client_id":     creds.client_id,
        "client_secret": creds.client_secret,
        "scopes":        list(creds.scopes) if creds.scopes else SCOPES,
    }
    DRIVE_TOKEN.write_text(json.dumps(token_data, indent=2))
    print(f"  ✅ Token salvo: {DRIVE_TOKEN}")

    # Enviar token ao servidor
    try:
        subprocess.run(
            ["ssh", "homelab@192.168.15.2",
             "mkdir -p /home/homelab/myClaude/drive_data"],
            capture_output=True, timeout=10,
        )
        subprocess.run(
            ["scp", str(DRIVE_TOKEN),
             "homelab@192.168.15.2:/home/homelab/myClaude/drive_data/token.json"],
            capture_output=True, timeout=15,
        )
        print(f"  ✅ Token copiado para servidor")
    except Exception as e:
        print(f"  ⚠️  Falha ao copiar token: {e}")

    # Buscar currículos
    search_resumes(creds)
    print("\n✅ PROCESSO CONCLUÍDO COM SUCESSO!\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️  Interrompido")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
