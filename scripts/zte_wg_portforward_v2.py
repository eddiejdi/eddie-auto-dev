#!/usr/bin/env python3
"""Adiciona port forward UDP 51820 (WireGuard) no ZTE GPON Modem — versão 2.

Tenta login com:
1. Password plain text
2. Password MD5 (padrão ZTE)
3. Selenium headless se Chrome disponível

Destino: ZTE_WG_DEST env (padrão 192.168.14.2)
Credenciais: ZTE_USER / ZTE_PASS env vars.
"""
import sys
import os
import re
import hashlib
import urllib.parse
import http.cookiejar
import urllib.request

BASE = "http://192.168.14.1"
ZTE_USER = os.environ.get("ZTE_USER", "admin")
ZTE_PASS = os.environ.get("ZTE_PASS", "admin")
WG_DEST = os.environ.get("ZTE_WG_DEST", "192.168.14.2")
WG_PORT = "51820"

# URL do módulo pode variar entre firmware ZTE — find_pf_page testa a lista
PF_PATH = "/getpage.gch?pid=1002&nextpage=Internet_app_virtual_conf_t.gch"

HEADERS = [
    ("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
    ("Accept-Language", "pt-BR,pt;q=0.9,en;q=0.8"),
    ("Connection", "keep-alive"),
]


def build_opener() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = HEADERS
    return opener


def get_login_token(opener: urllib.request.OpenerDirector) -> tuple[str, str]:
    page = opener.open(BASE + "/", timeout=12).read().decode("utf-8", "ignore")
    # Token é SETADO pelo dosubmit() no JS: getObj("Frm_Logintoken").value = "N"
    # Não está no value="" do HTML — está embutido no código JS pelo servidor
    m_js = re.search(r'Frm_Logintoken["\']?\)\.value\s*=\s*["\'](\w+)["\']', page, re.I)
    if m_js:
        token = m_js.group(1)
    else:
        # Fallback: atributo HTML (normalmente vazio)
        m_html = re.search(r'name="Frm_Logintoken"[^>]*value="([^"]*)"', page, re.I)
        token = m_html.group(1) if (m_html and m_html.group(1)) else "1"
    print(f"  Frm_Logintoken: {token!r}")
    return token, page


def try_login(opener: urllib.request.OpenerDirector, password: str, token: str) -> tuple[bool, str]:
    """Retorna (sucesso, body)."""
    data = urllib.parse.urlencode({
        "_lang": "",
        "frashnum": "",
        "action": "login",
        "Frm_Logintoken": token,
        "Username": ZTE_USER,
        "Password": password,
    }).encode()
    req = urllib.request.Request(BASE + "/", data=data,
                                  headers={"Referer": BASE + "/"})
    resp = opener.open(req, timeout=12)
    body = resp.read().decode("utf-8", "ignore")
    # Indicadores de login bem-sucedido
    logged_in = (
        "logout" in body.lower()
        or "Frm_Username" not in body
        and "logoff" in body.lower()
        or "mainFrame" in body
        or "top.gch" in body
        or len(body) > 3000 and "Username" not in body
    )
    return logged_in, body


# URLs candidatas para Port Forward Virtual Server em firmware ZTE GPON
PF_PATHS = [
    "/getpage.gch?pid=1002&nextpage=Internet_app_virtual_conf_t.gch",
    "/getpage.gch?pid=1002&nextpage=nat_vserver.gch",
    "/getpage.gch?pid=1001&nextpage=nat_vserver.gch",
]


def find_pf_page(opener: urllib.request.OpenerDirector) -> tuple[str, str]:
    """Descobre qual URL de port forward funciona. Retorna (path, body) ou ('', '')."""
    for path in PF_PATHS:
        try:
            body = opener.open(BASE + path, timeout=12).read().decode("utf-8", "ignore")
            print(f"  PF page {path}: {len(body)} bytes")
            if len(body) > 2000 and "Username" not in body:
                print(f"  → PF_PATH válido: {path}")
                # Mostrar campos do formulário de adição
                form_inputs = re.findall(r'<input[^>]+>', body, re.I)
                for inp in form_inputs[:30]:
                    if any(k in inp.lower() for k in ["frm_", "if_action", "name=", "hidden"]):
                        print(f"    FORM INPUT: {re.sub(r'\\s+', ' ', inp[:200])}")
                return path, body
        except Exception as exc:
            print(f"  PF page {path}: ERRO {exc!s:.60}")
    return "", ""


def check_wg_exists(opener: urllib.request.OpenerDirector, path: str) -> bool:
    try:
        body = opener.open(BASE + path, timeout=12).read().decode("utf-8", "ignore")
        found = WG_PORT in body
        print(f"  check_wg_exists: {len(body)} bytes, {WG_PORT} found={found}")
        if len(body) < 1000:
            print(f"  [DEBUG GET response]: {re.sub(r'\\s+', ' ', body[:500])!r}")
        return found
    except Exception as exc:
        print(f"  check_wg_exists ERRO: {exc!s:.100}")
        return False


def add_wg_rule(opener: urllib.request.OpenerDirector, path: str) -> bool:
    data = urllib.parse.urlencode({
        "IF_ACTION": "add",
        "Frm_Num": "",
        "Frm_SrvName": "WireGuard-VPN",
        "Frm_Protocol": "UDP",
        "Frm_ExtPort": WG_PORT,
        "Frm_InternalPort": WG_PORT,
        "Frm_InternalClient": WG_DEST,
        "Frm_Status": "1",
    }).encode()
    try:
        resp = opener.open(
            urllib.request.Request(BASE + path, data=data,
                                   headers={"Referer": BASE + path}),
            timeout=12,
        )
        body = resp.read().decode("utf-8", "ignore")
        print(f"  add_wg_rule POST: {len(body)} bytes")
        if len(body) < 1000:
            # Resposta anômala — imprimir para debug
            print(f"  [DEBUG POST response]: {re.sub(r'\\s+', ' ', body[:500])!r}")
    except Exception as exc:
        print(f"  add_wg_rule POST ERRO: {exc!s:.100}")
    return check_wg_exists(opener, path)


def login_urllib() -> bool:
    """Tenta login via urllib. Retorna True se WG foi configurado."""
    # Senhas extras via env para facilitar testes com senha não-padrão
    extra = os.environ.get("ZTE_PASS_EXTRA", "")
    extra_list = [p for p in extra.split(",") if p] if extra else []

    passwords_to_try = [
        ("plain", ZTE_PASS),
        ("MD5", hashlib.md5(ZTE_PASS.encode()).hexdigest()),
    ] + [("extra:" + p, p) for p in extra_list]

    for label, pwd in passwords_to_try:
        print(f"\n--- Tentando login [{label}] ---")
        opener = build_opener()
        try:
            token, login_page = get_login_token(opener)
            # Se token é dinâmico (lido do JS), tentar MD5(pass+token) também
            if token not in ("1", "") and label == "MD5":
                pwd2 = hashlib.md5((ZTE_PASS + token).encode()).hexdigest()
                print(f"  (variant: MD5(pass+token)={pwd2[:16]}...)")
            logged_in, body = try_login(opener, pwd, token)
            print(f"  logged_in heuristic: {logged_in}  body_len={len(body)}")
            snippet = re.sub(r"\s+", " ", body[:200])
            print(f"  snippet: {snippet}")
            if logged_in:
                print(f"  Login OK com [{label}]!")
                pf_path, pf_body = find_pf_page(opener)
                if not pf_path:
                    print("  ⚠ Nenhuma URL de port forward funcionou")
                    return False
                if check_wg_exists(opener, pf_path):
                    print(f"  WireGuard {WG_PORT} já configurado!")
                    return True
                print(f"  Adicionando WireGuard UDP {WG_PORT} → {WG_DEST}…")
                if add_wg_rule(opener, pf_path):
                    print(f"  ✅ Port forward {WG_PORT} → {WG_DEST} adicionado!")
                    return True
                else:
                    print("  ⚠ Regra pode não ter sido salva — verifique manualmente")
                    return False
        except Exception as exc:
            print(f"  Erro [{label}]: {type(exc).__name__}: {exc}")
    print("\nTodos os métodos urllib falharam.")
    return False


def login_selenium() -> bool:
    """Tenta via Selenium como fallback. Retorna True se WG configurado."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select, WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        import time
    except ImportError:
        print("Selenium não disponível — pulando.")
        return False

    print("\n--- Tentando Selenium ---")

    # Binários Chrome/Chromium conhecidos — testa na ordem
    CHROME_BINS = [
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
        "/usr/bin/chromium",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
    ]

    driver = None
    for bin_path in CHROME_BINS:
        if not os.path.isfile(bin_path):
            continue
        opts = Options()
        opts.binary_location = bin_path
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1440,1200")
        opts.add_argument("--no-proxy-server")
        try:
            driver = webdriver.Chrome(options=opts)
            print(f"  Browser iniciado: {bin_path}")
            break
        except Exception as exc:
            print(f"  {bin_path} falhou: {str(exc)[:120]}")

    if driver is None:
        print("Chrome/chromedriver não disponível em nenhum path conhecido.")
        return False

    try:
        driver.get(BASE + "/")
        wait = WebDriverWait(driver, 12)

        # Login
        wait.until(EC.presence_of_element_located((By.ID, "Frm_Username")))
        token_before = driver.find_element(By.ID, "Frm_Logintoken").get_attribute("value")
        print(f"  Frm_Logintoken antes: {token_before!r}")

        # Verificar se o botão está desabilitado (lockout ativo)
        login_btn_el = driver.find_element(By.ID, "LoginId")
        is_disabled = driver.execute_script("return document.getElementById('LoginId').disabled;")
        if is_disabled:
            print("  ⚠ Botão LoginId desabilitado (lockout ativo)")
            # Buscar tempo de lockout e aguardar
            lockout_secs = driver.execute_script("""
                try { return parseInt(maxtime || window.name || '0', 10); }
                catch(e) { return 0; }
            """)
            wait_secs = int(lockout_secs) + 5 if lockout_secs and int(lockout_secs) > 0 else 65
            print(f"  Aguardando {wait_secs}s para lockout expirar...")
            time.sleep(wait_secs)
            # Recarregar página após lockout
            driver.get(BASE + "/")
            wait.until(EC.presence_of_element_located((By.ID, "Frm_Username")))
            print("  Página recarregada após lockout")
            login_btn_el = driver.find_element(By.ID, "LoginId")

        # Preencher credenciais e clicar no botão de login nativamente
        try:
            usr_field = driver.find_element(By.ID, "Frm_Username")
            pwd_field = driver.find_element(By.ID, "Frm_Password")
            usr_field.clear()
            usr_field.send_keys(ZTE_USER)
            pwd_field.clear()
            pwd_field.send_keys(ZTE_PASS)

            # Se ainda desabilitado, forçar via JS e submeter
            still_disabled = driver.execute_script(
                "return document.getElementById('LoginId').disabled;"
            )
            if still_disabled:
                print("  Botão ainda disabled — forçando via JS")
                driver.execute_script("document.getElementById('LoginId').disabled = false;")

            login_btn_el.click()
            print("  Login button clicked (nativo)")
        except Exception as exc:
            print(f"  Falha preenchimento/click: {exc!s:.150}")

        # Aguardar navegação ou mudança de página por até 15 segundos
        try:
            wait.until(lambda d: d.current_url != BASE + "/"
                       or not d.find_elements(By.ID, "Frm_Username"))
        except Exception:
            pass  # timeout — continua para verificar

        time.sleep(2)  # buffer extra para AJAX

        url_after = driver.current_url
        print(f"  URL após login: {url_after}")
        src_snippet = re.sub(r"\s+", " ", driver.page_source[:300])
        print(f"  Page snippet: {src_snippet!r}")

        # Login falhou se a página de login ainda está ativa
        frm_fields = driver.find_elements(By.ID, "Frm_Username")
        if frm_fields:
            print("  Selenium: Login falhou (Frm_Username ainda presente)")
            # Dump diagnóstico da página atual
            full_src = driver.page_source
            print(f"  [DIAG] Page source ({len(full_src)} chars):")
            print(re.sub(r"\s+", " ", full_src[:1500]))
            return False
        print("  Selenium: Login OK")

        def dismiss_alerts(drv: webdriver.Chrome) -> None:
            """Fecha qualquer alert JS aberto."""
            try:
                alert = drv.switch_to.alert
                txt = alert.text
                print(f"  [alert] {txt!r} — dismissed")
                alert.accept()
            except Exception:
                pass

        # Navegar para Port Forwarding — tentar múltiplos paths conhecidos
        pf_path_sel = ""
        for candidate in PF_PATHS:
            driver.get(BASE + candidate)
            time.sleep(2)
            dismiss_alerts(driver)
            try:
                page_len = len(driver.page_source)
                print(f"  PF candidate {candidate}: {page_len} bytes  url={driver.current_url}")
                if page_len > 2000 and "Username" not in driver.page_source:
                    pf_path_sel = candidate
                    print(f"  → PF URL válida: {pf_path_sel}")
                    break
                elif "Username" in driver.page_source:
                    print(f"  → Redirecionou para login (sessão expirada?)")
            except Exception as exc2:
                dismiss_alerts(driver)
                print(f"  PF candidate {candidate}: ERRO {exc2!s:.80}")

        if not pf_path_sel:
            print("  Nenhum PF_PATH Selenium válido — abortando")
            return False

        # Verificar se 51820 já existe
        dismiss_alerts(driver)
        try:
            if WG_PORT in driver.page_source:
                print(f"  WireGuard {WG_PORT} já configurado!")
                return True
        except Exception:
            dismiss_alerts(driver)

        # Preencher formulário
        try:
            driver.find_element(By.NAME, "Frm_SrvName").send_keys("WireGuard-VPN")
        except Exception:
            pass

        # Selecionar protocolo UDP
        for sel_name in ["Frm_Protocol", "IF_Protocol", "protocol"]:
            try:
                sel = Select(driver.find_element(By.NAME, sel_name))
                sel.select_by_value("UDP")
                break
            except Exception:
                pass

        for field, val in [
            ("Frm_ExtPort", WG_PORT),
            ("Frm_InternalPort", WG_PORT),
            ("Frm_InternalClient", WG_DEST),
        ]:
            try:
                el = driver.find_element(By.NAME, field)
                el.clear()
                el.send_keys(val)
            except Exception:
                pass

        # Submeter
        for btn_id in ["bt_add", "BtnAdd", "save", "apply"]:
            try:
                driver.find_element(By.ID, btn_id).click()
                time.sleep(2)
                break
            except Exception:
                pass
        else:
            # Tentar por tipo submit
            try:
                driver.find_element(By.CSS_SELECTOR, "input[type='submit']").click()
                time.sleep(2)
            except Exception:
                pass

        driver.get(BASE + pf_path_sel)
        dismiss_alerts(driver)
        time.sleep(2)
        if WG_PORT in driver.page_source:
            print(f"  ✅ Selenium: WireGuard {WG_PORT} adicionado!")
            return True
        print("  Selenium: regra não confirmada")
        return False
    finally:
        driver.quit()


def main() -> None:
    print(f"ZTE WG Port Forward v2  —  {BASE}")
    print(f"  user={ZTE_USER!r}  dest={WG_DEST}  port={WG_PORT}")
    print(f"  MD5(pass)={hashlib.md5(ZTE_PASS.encode()).hexdigest()}\n")

    # Testar conectividade
    try:
        urllib.request.urlopen(BASE + "/", timeout=6)
    except Exception as exc:
        print(f"ZTE inacessível: {exc}")
        sys.exit(1)

    if login_urllib():
        sys.exit(0)

    if login_selenium():
        sys.exit(0)

    print("\n❌ Não foi possível configurar WireGuard no ZTE.")
    sys.exit(1)


if __name__ == "__main__":
    main()
