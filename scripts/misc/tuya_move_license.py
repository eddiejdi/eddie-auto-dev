#!/usr/bin/env python3
"""
Move IoT Core trial do projeto China para o projeto ativo.
Credenciais lidas do secrets agent em runtime (nenhum valor hardcoded).

Uso:
    SECRETS_AGENT_URL=http://192.168.15.2:8088 \
    SECRETS_AGENT_API_KEY=<key> \
    python3 tuya_move_license.py
"""
import time
import sys
import json
import os
import hmac
import hashlib
import re
import urllib.request
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException, StaleElementReferenceException,
    ElementClickInterceptedException,
)

SECRETS_URL    = os.environ.get("SECRETS_AGENT_URL", "http://192.168.15.2:8088")
API_KEY        = os.environ.get("SECRETS_AGENT_API_KEY", "")
TARGET_PROJECT = "p1768171340520uw8ar4"
PROFILE_DIR    = os.path.expanduser("~/.tuya_chrome_profile")
SS_DIR         = "/workspace/eddie-auto-dev/scripts/misc/screenshots/tuya_move"
OTP_FILE       = "/tmp/tuya_otp.txt"
LOGIN_DONE     = "/tmp/tuya_login_done"

os.makedirs(SS_DIR, exist_ok=True)
_ctr = [0]


# ─── SECRETS AGENT ─────────────────────────────────────────────────────────────

def get_secret(name, field="password"):
    req = urllib.request.Request(
        f"{SECRETS_URL}/secrets/{name}?field={field}",
        headers={"X-API-Key": API_KEY},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())["value"]


def load_credentials():
    try:
        email  = get_secret("notebook/tuya_platform", "email")
        passwd = get_secret("notebook/tuya_platform", "password")
        client_id     = get_secret("notebook/tuya", "access_id")
        client_secret = get_secret("notebook/tuya", "access_secret")
        return email, passwd, client_id, client_secret
    except Exception as exc:
        print(f"[ERRO] Não foi possível ler credenciais do secrets agent: {exc}")
        sys.exit(1)


# ─── HELPERS ───────────────────────────────────────────────────────────────────

def ss(driver, name):
    _ctr[0] += 1
    path = f"{SS_DIR}/{_ctr[0]:02d}_{name}.png"
    driver.save_screenshot(path)
    print(f"  [ss] {path}")
    return path


def wait_file(path, timeout=180, prompt=""):
    if prompt:
        print(prompt)
    for _ in range(timeout):
        if os.path.exists(path):
            val = open(path).read().strip()
            os.remove(path)
            return val
        time.sleep(1)
    return None


def click_any(driver, xpaths, label=""):
    for x in xpaths:
        try:
            els = driver.find_elements(By.XPATH, x)
            for el in els:
                if el.is_displayed():
                    try:
                        el.click()
                    except ElementClickInterceptedException:
                        driver.execute_script("arguments[0].click();", el)
                    if label:
                        print(f"  [{label}] clicou: {x}")
                    return True
        except StaleElementReferenceException:
            pass
    return False


def page_text(driver):
    try:
        return driver.find_element(By.TAG_NAME, "body").text
    except Exception:
        return ""


def api_token_test(base_url, client_id, client_secret):
    t = str(int(time.time() * 1000))
    path = "/v1.0/token?grant_type=1"
    body_hash = hashlib.sha256(b"").hexdigest()
    sts = f"GET\n{body_hash}\n\n{path}"
    payload = client_id + t + sts
    sign = hmac.new(client_secret.encode(), payload.encode(), hashlib.sha256).hexdigest().upper()
    req = urllib.request.Request(
        base_url + path,
        headers={"client_id": client_id, "sign": sign,
                 "sign_method": "HMAC-SHA256", "t": t, "lang": "en"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


# ─── MAIN ──────────────────────────────────────────────────────────────────────

def wait_spinner(driver, timeout=20):
    """Aguarda spinner de carregamento sumir."""
    try:
        WebDriverWait(driver, timeout).until_not(
            EC.presence_of_element_located((By.CSS_SELECTOR,
                ".ant-spin-spinning, .loading, [class*='spin'][class*='ing']"))
        )
    except TimeoutException:
        pass
    time.sleep(2)


def dismiss_dialogs(driver):
    """Fecha dialogs/modals e banner de cookies."""
    # Cookie banner
    click_any(driver, [
        "//button[contains(text(),'Accept All')]",
        "//button[contains(text(),'Only Necessary')]",
    ], "cookie-banner")
    time.sleep(1)
    # Qualquer modal com OK/Close/×
    for _ in range(3):
        if not click_any(driver, [
            "//button[contains(text(),'OK')]",
            "//button[contains(text(),'Close')]",
            "//span[@aria-label='close']",
            "//*[contains(@class,'modal')]//button[contains(text(),'OK')]",
            "//*[contains(@class,'ant-modal')]//button[last()]",
        ], "modal-close"):
            break
        time.sleep(1)


def main():
    print("[INIT] Carregando credenciais do secrets agent...")
    email, passwd, client_id, client_secret = load_credentials()
    print(f"  email: {email}  client_id: {client_id[:6]}...")

    # Chrome com perfil salvo (preserva cookies/sessão)
    opts = Options()
    opts.add_argument(f"--user-data-dir={PROFILE_DIR}")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])

    print("[INIT] Abrindo Chrome...")
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(30)

    try:
        # ── 1. LOGIN ───────────────────────────────────────────────────────────
        print("\n[1] Acessando auth.tuya.com...")
        driver.get("https://auth.tuya.com/")
        time.sleep(5)
        ss(driver, "auth_home")

        txt = page_text(driver)
        needs_login = ("auth.tuya.com" in driver.current_url
                       or "sign in" in txt.lower()
                       or "log in" in txt.lower())

        if needs_login:
            print("  Preenchendo email...")
            for xpath in [
                "//input[@type='email']",
                "//input[@placeholder[contains(.,'email') or contains(.,'Email')]]",
                "//input[@name='email']",
                "//input[@id='email']",
            ]:
                try:
                    el = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, xpath))
                    )
                    el.clear()
                    el.send_keys(email)
                    print(f"  Email preenchido via {xpath}")
                    break
                except (TimeoutException, NoSuchElementException):
                    continue

            click_any(driver, [
                "//button[contains(text(),'Next')]",
                "//span[contains(text(),'Next')]/..",
                "//button[contains(text(),'Continue')]",
            ], "next")
            time.sleep(3)

            print("  Preenchendo senha...")
            for xpath in ["//input[@type='password']", "//input[@name='password']"]:
                try:
                    el = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, xpath))
                    )
                    if el.is_displayed():
                        el.clear()
                        el.send_keys(passwd)
                        print(f"  Senha preenchida via {xpath}")
                        break
                except (TimeoutException, NoSuchElementException):
                    continue

            time.sleep(1)
            click_any(driver, [
                "//button[@type='submit']",
                "//button[contains(text(),'Log In')]",
                "//button[contains(text(),'Sign In')]",
                "//button[contains(text(),'Login')]",
            ], "submit")
            time.sleep(4)
            ss(driver, "after_login_attempt")

            # Se ainda em auth.tuya.com, pode ser CAPTCHA ou OTP — pausa para o usuário
            if "auth.tuya.com" in driver.current_url:
                print("\n" + "="*60)
                print("  CAPTCHA ou verificação adicional detectada no browser.")
                print("  >> Complete o login manualmente no browser que abriu <<")
                print(f"  Após estar logado, execute em outro terminal:")
                print(f"    touch {LOGIN_DONE}")
                print("="*60)
                if os.path.exists(LOGIN_DONE):
                    os.remove(LOGIN_DONE)
                result = wait_file(LOGIN_DONE, timeout=300)
                if result is None:
                    print("  TIMEOUT aguardando login manual.")
                    sys.exit(1)
                time.sleep(2)

            ss(driver, "after_login")
            print(f"  URL pós-login: {driver.current_url}")

        # ── 2. OTP SE SOLICITADO ───────────────────────────────────────────────
        txt = page_text(driver)
        if any(k in txt.lower() for k in ["verification", "otp", "verify your"]):
            print("\n[2] OTP solicitado!")
            ss(driver, "otp_required")
            if os.path.exists(OTP_FILE):
                os.remove(OTP_FILE)
            otp = wait_file(
                OTP_FILE,
                timeout=180,
                prompt=(
                    "\n" + "="*60 +
                    f"\n  OTP enviado para {email}."
                    f"\n  Execute em outro terminal:"
                    f"\n    echo SEU_OTP > {OTP_FILE}"
                    "\n" + "="*60
                ),
            )
            if otp:
                for inp in driver.find_elements(By.XPATH,
                        "//input[@type='text' or @type='number']"):
                    if inp.is_displayed():
                        inp.clear()
                        inp.send_keys(otp)
                        break
                click_any(driver, [
                    "//button[contains(text(),'Verify')]",
                    "//button[contains(text(),'Submit')]",
                    "//button[@type='submit']",
                ], "otp-submit")
                time.sleep(5)
                ss(driver, "after_otp")

        # ── 3. CLOUD HOME — verificar sessão ──────────────────────────────────
        print("\n[3] Verificando sessão...")
        driver.get("https://platform.tuya.com/cloud")
        time.sleep(6)
        # NÃO chamar dismiss_dialogs aqui — pode navegar para fora do site!
        # Só fechar o banner de cookies via JS direto
        _cookie_js = """
            var found = null;
            document.querySelectorAll('button').forEach(function(b) {
                var t = (b.innerText||b.textContent||'').trim();
                if (!found && (t==='Accept All'||t==='Only Necessary'||
                               t.includes('Accept All')||t.includes('Only Necessary'))) {
                    found = t; b.click();
                }
            });
            return found || 'no-cookie-banner';
        """
        time.sleep(3)
        driver.execute_script(_cookie_js)
        time.sleep(2)
        wait_spinner(driver)
        ss(driver, "cloud_home")

        if "auth.tuya.com" in driver.current_url or "google.com" in driver.current_url:
            print(f"  ⚠  Login não persistido — URL: {driver.current_url}")
            print(f"  Forçando navegação direta para platform.tuya.com/cloud...")
            driver.get("https://platform.tuya.com/cloud")
            time.sleep(8)
            if "platform.tuya.com" not in driver.current_url:
                print("  Login falhou. Execute o script novamente e faça login manual.")
                sys.exit(1)
        print(f"  Logado. URL: {driver.current_url}")

        # ── 4. CLOUD SERVICES — mudar DC de China para Western America ────────
        print("\n[4] Abrindo Cloud Services...")
        driver.get("https://platform.tuya.com/cloud/products?productType=all")
        time.sleep(8)
        driver.execute_script(_cookie_js)
        time.sleep(2)
        wait_spinner(driver)
        ss(driver, "cloud_services")

        # Verificar se está mostrando China DC e mudar para Western America
        dc_text = driver.execute_script("""
            for (var el of document.querySelectorAll('*')) {
                var t = (el.innerText||el.textContent||'').trim();
                if (t === 'China Data Center' || t === 'Western America Data Center' ||
                    t === 'Central Europe Data Center' || t === 'India Data Center') {
                    return t;
                }
            }
            return 'DC_NOT_FOUND';
        """)
        print(f"  Data Center atual: {dc_text}")

        if "China" in str(dc_text):
            print("  Mudando para Western America Data Center...")
            # Clicar no dropdown de data center
            dc_btn = driver.execute_script("""
                for (var el of document.querySelectorAll('*')) {
                    var t = (el.innerText||el.textContent||'').trim();
                    if (t === 'China Data Center') {
                        // Encontrar o elemento menor (o próprio botão/dropdown)
                        var rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.width < 300 && rect.height > 0) {
                            el.scrollIntoView({behavior:'instant', block:'center'});
                            return el;
                        }
                    }
                }
                return null;
            """)
            if dc_btn:
                time.sleep(0.5)
                try:
                    ActionChains(driver).move_to_element(dc_btn).pause(0.3).click().perform()
                    print("  Dropdown clicado via ActionChains")
                except Exception as e:
                    driver.execute_script("arguments[0].click();", dc_btn)
                    print(f"  Dropdown clicado via JS (fallback: {e})")
                time.sleep(3)
                ss(driver, "dc_dropdown_open")

                # Selecionar "Western America Data Center"
                wa_option = driver.execute_script("""
                    var opts = ['Western America Data Center', 'Americas Data Center',
                                'Western America', 'Americas'];
                    for (var opt of opts) {
                        for (var el of document.querySelectorAll('*')) {
                            var t = (el.innerText||el.textContent||'').trim();
                            if (t === opt) {
                                el.scrollIntoView({behavior:'instant'});
                                return el;
                            }
                        }
                    }
                    // Dump all dropdown items for diagnosis
                    var items = [];
                    document.querySelectorAll('.ant-dropdown-menu-item, [role="menuitem"], li').forEach(function(li) {
                        var t = (li.innerText||li.textContent||'').trim();
                        if (t.includes('Data Center') || t.includes('America') || t.includes('Europe')) {
                            items.push(t);
                        }
                    });
                    return 'ITEMS: ' + items.join(' | ');
                """)
                if isinstance(wa_option, str):
                    print(f"  Opções encontradas: {wa_option}")
                    # Tentar clicar qualquer opção não-China
                    driver.execute_script("""
                        document.querySelectorAll('.ant-dropdown-menu-item, [role="menuitem"], li').forEach(function(li) {
                            var t = (li.innerText||li.textContent||'').trim();
                            if ((t.includes('America') || t.includes('Europe') || t.includes('India')) && !t.includes('China')) {
                                li.click();
                            }
                        });
                    """)
                else:
                    print("  'Western America Data Center' encontrado, clicando...")
                    try:
                        ActionChains(driver).move_to_element(wa_option).pause(0.3).click().perform()
                    except Exception:
                        driver.execute_script("arguments[0].click();", wa_option)

                time.sleep(5)
                wait_spinner(driver)
                ss(driver, "dc_switched")
                new_dc = driver.execute_script("""
                    for (var el of document.querySelectorAll('*')) {
                        var t = (el.innerText||el.textContent||'').trim();
                        if (t.includes('Data Center') && t.length < 50) return t;
                    }
                    return 'unknown';
                """)
                print(f"  Data Center agora: {new_dc}")
            else:
                print("  ⚠  Botão dropdown não encontrado — continuando...")

        # Scroll horizontal para expor a coluna Operation (com Subscribe button)
        scroll_r = driver.execute_script("""
            var best = null, bestScroll = 0;
            document.querySelectorAll('*').forEach(function(el) {
                var s = window.getComputedStyle(el);
                if ((s.overflowX === 'auto' || s.overflowX === 'scroll') &&
                    el.scrollWidth > el.clientWidth + 20) {
                    if (el.scrollWidth - el.clientWidth > bestScroll) {
                        bestScroll = el.scrollWidth - el.clientWidth;
                        best = el;
                    }
                }
            });
            if (best) { best.scrollLeft = 9999; return 'SCROLLED sw=' + best.scrollWidth; }
            return 'NO_SCROLL_CONTAINER';
        """)
        print(f"  Scroll: {scroll_r}")
        time.sleep(2)
        ss(driver, "cloud_services_scrolled")

        # ── 5. PAUSA PARA AÇÃO MANUAL ─────────────────────────────────────────
        SUBSCRIBED_FILE = "/tmp/tuya_subscribed"
        if os.path.exists(SUBSCRIBED_FILE):
            os.remove(SUBSCRIBED_FILE)

        dc_now = driver.execute_script("""
            for (var el of document.querySelectorAll('*')) {
                var t = (el.innerText||el.textContent||'').trim();
                if (t.includes('Data Center') && t.length < 60) return t;
            }
            return '?';
        """)
        print("\n" + "="*60)
        print(f"  Data Center atual: {dc_now}")
        print("  AÇÃO NECESSÁRIA NO BROWSER:")
        print("  1. Se o Data Center ainda for 'China', mude manualmente pelo dropdown (canto sup. direito)")
        print("  2. Na coluna 'Operation' da linha 'IoT Core', clique em 'Subscribe to Resource Pack'")
        print("  3. Complete o processo de subscription no modal que aparecer")
        print("  4. Após concluir, execute em outro terminal:")
        print(f"       touch {SUBSCRIBED_FILE}")
        print("="*60)

        result = wait_file(SUBSCRIBED_FILE, timeout=600,
                           prompt="  Aguardando sinal de conclusão...")
        if result is None:
            print("  TIMEOUT — prosseguindo com validação de API de qualquer forma.")
        else:
            print("  Sinal recebido! Aguardando propagação...")
            time.sleep(15)

        ss(driver, "after_manual_action")

        # ── 5b. VERIFICAR ESTADO PÓS-AÇÃO ─────────────────────────────────────
        driver.get("https://platform.tuya.com/cloud/products?productType=all")
        time.sleep(8)
        driver.execute_script(_cookie_js)
        time.sleep(1)
        wait_spinner(driver)
        ss(driver, "cloud_services_after")
        txt_after = page_text(driver)
        print("  Estado pós-ação:")
        for line in txt_after.split("\n"):
            s = line.strip()
            if s and any(k in s for k in ["IoT Core", "Alerting", "Active", "In service",
                                           "Expir", "notebook", "home-lab"]):
                print(f"    {s[:120]}")

        # ── 6. TESTAR CREDENCIAIS ────────────────────────────────────────────
        print("\n[6] Testando credenciais via API (aguardar 10s para propagação)...")
        time.sleep(10)
        endpoints = {
            "US": "https://openapi.tuyaus.com",
            "EU": "https://openapi.tuyaeu.com",
            "India": "https://openapi.tuyain.com",
        }
        working_url = None
        for region, url in endpoints.items():
            r = api_token_test(url, client_id, client_secret)
            ok = r.get("success", False)
            code = r.get("code", "?")
            print(f"  {region}: code={code} success={ok}")
            if ok and working_url is None:
                working_url = url

        # ── 7. RESULTADO FINAL ────────────────────────────────────────────────
        ss(driver, "final")
        print("\n" + "="*60)
        if working_url:
            print(f" ✅ Credenciais FUNCIONANDO — região: {working_url}")
        else:
            print(" ⚠  API ainda retorna erro (code=2009).")
            print("    Verifique se o IoT Core foi renovado na aba Cloud Services.")
            print("    Se foi renovado, aguarde 5 minutos e execute novamente.")
        print(f" Screenshots em: {SS_DIR}/")
        print("="*60)

    except KeyboardInterrupt:
        print("\n[CANCELADO]")
    except Exception:
        import traceback
        traceback.print_exc()
        try:
            ss(driver, "error")
        except Exception:
            pass

    print("\n[INFO] Fechando browser em 5s...")
    time.sleep(5)
    driver.quit()
    print("[OK] Finalizado")


if __name__ == "__main__":
    main()
