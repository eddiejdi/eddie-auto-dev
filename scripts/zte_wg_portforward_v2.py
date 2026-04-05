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


def get_login_token(opener: urllib.request.OpenerDirector) -> str:
    page = opener.open(BASE + "/", timeout=12).read().decode("utf-8", "ignore")
    m = re.search(r'Frm_Logintoken[^>]*value=["\']?([^"\'>\s]+)', page, re.I)
    token = m.group(1) if m else "1"
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


def check_wg_exists(opener: urllib.request.OpenerDirector) -> bool:
    try:
        body = opener.open(BASE + PF_PATH, timeout=12).read().decode("utf-8", "ignore")
        return WG_PORT in body
    except Exception:
        return False


def add_wg_rule(opener: urllib.request.OpenerDirector) -> bool:
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
    opener.open(
        urllib.request.Request(BASE + PF_PATH, data=data,
                               headers={"Referer": BASE + PF_PATH}),
        timeout=12,
    )
    return check_wg_exists(opener)


def login_urllib() -> bool:
    """Tenta login via urllib. Retorna True se WG foi configurado."""
    passwords_to_try = [
        ("plain", ZTE_PASS),
        ("MD5", hashlib.md5(ZTE_PASS.encode()).hexdigest()),
        ("MD5-upper", hashlib.md5(ZTE_PASS.encode()).hexdigest().upper()),
        ("MD5(user+pass)", hashlib.md5((ZTE_USER + ZTE_PASS).encode()).hexdigest()),
        ("MD5(pass+user)", hashlib.md5((ZTE_PASS + ZTE_USER).encode()).hexdigest()),
    ]
    for label, pwd in passwords_to_try:
        print(f"\n--- Tentando login [{label}] ---")
        opener = build_opener()
        try:
            token, login_page = get_login_token(opener)
            # Tentar também MD5(pass+token) quando token != "1"
            if token not in ("1", "") and label == "MD5":
                pwd = hashlib.md5((ZTE_PASS + token).encode()).hexdigest()
                print(f"  (token={token!r} → MD5(pass+token)={pwd[:16]}...)")
            logged_in, body = try_login(opener, pwd, token)
            print(f"  logged_in heuristic: {logged_in}  body_len={len(body)}")
            snippet = re.sub(r"\s+", " ", body[:200])
            print(f"  snippet: {snippet}")
            if logged_in:
                print(f"  Login OK com [{label}]!")
                if check_wg_exists(opener):
                    print(f"  WireGuard {WG_PORT} já configurado!")
                    return True
                print(f"  Adicionando WireGuard UDP {WG_PORT} → {WG_DEST}…")
                if add_wg_rule(opener):
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

        # Tentar chamar dosubmit() via JS (preenche token e hasheia password)
        md5_pass = hashlib.md5(ZTE_PASS.encode()).hexdigest()
        try:
            driver.find_element(By.ID, "Frm_Username").send_keys(ZTE_USER)
            driver.find_element(By.ID, "Frm_Password").send_keys(ZTE_PASS)
            # Tenta dosubmit (pode estar em JS externo)
            result = driver.execute_script("""
                try {
                    var un = document.getElementById('Frm_Username');
                    if (un) un.value = arguments[0];
                    var pd = document.getElementById('Frm_Password');
                    if (pd) pd.value = arguments[1];
                    if (typeof dosubmit === 'function') {
                        dosubmit();
                        return 'dosubmit_called';
                    } else {
                        return 'dosubmit_undefined';
                    }
                } catch(e) { return 'error:' + e.toString(); }
            """, ZTE_USER, ZTE_PASS)
            print(f"  execute_script dosubmit: {result!r}")
        except Exception as exc:
            print(f"  execute_script falhou: {exc!s:.100}")

        time.sleep(3)
        token_mid = ""
        try:
            token_mid = driver.find_element(By.ID, "Frm_Logintoken").get_attribute("value")
        except Exception:
            pass
        print(f"  Frm_Logintoken após dosubmit attempt: {token_mid!r}")

        # Se dosubmit() não funcionou (token ainda empty), enviar form via JS com MD5
        if not token_mid:
            print("  dosubmit() ineficaz — submetendo form via JS com MD5 manual")
            try:
                driver.execute_script(f"""
                    document.getElementById('Frm_Username').value = '{ZTE_USER}';
                    document.getElementById('Frm_Password').value = '{md5_pass}';
                    document.getElementById('Frm_Logintoken').value = '0';
                    // Tentar submeter o form pelo nome ou ID
                    var f = document.mainform || document.getElementById('mainform')
                           || document.forms[0];
                    if (f) f.submit();
                """)
                time.sleep(5)
            except Exception as exc2:
                print(f"  Falha JS submit: {exc2!s:.100}")
        else:
            time.sleep(5)

        url_after = driver.current_url
        print(f"  URL após login: {url_after}")
        src_snippet = re.sub(r"\s+", " ", driver.page_source[:300])
        print(f"  Page snippet: {src_snippet!r}")

        # Login falhou se a página de login ainda está ativa
        frm_fields = driver.find_elements(By.ID, "Frm_Username")
        if frm_fields:
            print("  Selenium: Login falhou (Frm_Username ainda presente)")
            return False
        print("  Selenium: Login OK")

        # Navegar para Port Forwarding
        driver.get(BASE + PF_PATH)
        time.sleep(2)

        # Verificar se 51820 já existe
        if WG_PORT in driver.page_source:
            print(f"  WireGuard {WG_PORT} já configurado!")
            return True

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

        driver.get(BASE + PF_PATH)
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
