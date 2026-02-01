from playwright.sync_api import sync_playwright
import os
import time
import sys


def load_env(p):
    d = {}
    try:
        with open(p) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    d[k] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return d


env = load_env("/tmp/openwebui.env")
email = env.get("WEBUI_ADMIN_EMAIL")
password = env.get("WEBUI_ADMIN_PASSWORD")
host_base = os.environ.get("WEBUI_BASE")
if host_base:
    base = host_base
else:
    # container PORT may be internal (8080); host maps 3000 -> 8080, so default to host port 3000
    base = os.environ.get("WEBUI_HOST") or "http://localhost:3000"


def log(msg):
    print(msg, flush=True)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    page = browser.new_page()
    try:
        r = page.goto(base + "/auth", timeout=20000)
        log("goto_status=" + (str(r.status) if r else "noresponse"))
        time.sleep(1)
        # wait for login fields to appear in the SPA (be tolerant of different attribute names)
        form_email = None
        form_pass = None
        submit_btn = None
        try:
            page.wait_for_selector(
                'input[name="email"], input[type="email"], input[placeholder*="Email"], input[placeholder*="email"]',
                timeout=10000,
            )
            form_email = (
                page.query_selector('input[name="email"]')
                or page.query_selector('input[type="email"]')
                or page.query_selector('input[placeholder*="Email"]')
                or page.query_selector('input[placeholder*="email"]')
            )
            form_pass = page.query_selector(
                'input[name="password"]'
            ) or page.query_selector('input[type="password"]')
            submit_btn = page.query_selector(
                'button[type="submit"]'
            ) or page.query_selector("button")
        except Exception:
            form_email = None
        if form_email and submit_btn and email and password:
            log("login_form_found — attempting login")
            # try robustly to find password field
            possible_pw = [
                'input[name="password"]',
                'input[type="password"]',
                'input[id*="password"]',
                'input[placeholder*="Password"]',
                'input[placeholder*="password"]',
            ]
            pw_selector = None
            for sel in possible_pw:
                try:
                    if page.query_selector(sel):
                        pw_selector = sel
                        break
                except Exception:
                    continue
            if not pw_selector:
                # dump input elements for debugging
                inputs = page.query_selector_all("input")
                log(f"found_input_count={len(inputs)}")
                for i, inp in enumerate(inputs[:10]):
                    try:
                        outer = inp.evaluate("e=>e.outerHTML")
                    except Exception:
                        outer = "<error>"
                    log(f"input[{i}]=" + outer)
                log("no_password_field_found")
            else:
                page.fill('input[name="email"]', email)
                page.fill(pw_selector, password)
                submit_btn.click()
            token = None
            for i in range(20):
                time.sleep(0.5)
                token = page.evaluate(
                    "() => window.localStorage.getItem('token') || window.localStorage.getItem('access_token')"
                )
                if token:
                    log("login_success token_len=" + str(len(token)))
                    break
            else:
                log("login_failed — no token in localStorage")
                print(page.content()[:1500])
                sys.exit(2)
        else:
            log("login_form_not_found_or_missing_creds")
        token = page.evaluate(
            "() => window.localStorage.getItem('token') || window.localStorage.getItem('access_token')"
        )
        if not token:
            import requests

            try:
                r = requests.post(
                    base + "/api/v1/auths/signin",
                    json={"email": email, "password": password},
                    timeout=10,
                )
                log("signin_api_status=" + str(r.status_code))
                if r.status_code == 200:
                    j = r.json()
                    token = (
                        j.get("token")
                        or j.get("access_token")
                        or j.get("data", {}).get("token")
                    )
            except Exception as e:
                log("signin_api_exception=" + repr(e))
        headers = {"Authorization": "Bearer " + token} if token else {}
        import requests

        try:
            # API expects a 'chat' object in the body
            r = requests.post(
                base + "/api/v1/chats/new",
                headers=headers,
                json={"chat": {"title": "playwright-check"}},
                timeout=10,
            )
            log(
                "create_chat_status="
                + str(r.status_code)
                + " body="
                + (r.text[:200] if r.text else "")
            )
            r2 = requests.get(base + "/api/v1/chats/list", headers=headers, timeout=10)
            log(
                "list_chats_status="
                + str(r2.status_code)
                + " body_len="
                + str(len(r2.text))
            )
        except Exception as e:
            log("chat_api_exception=" + repr(e))
            print("PAGE HTML PREVIEW:\n")
            print(page.content()[:1500])
            sys.exit(4)
        print("PLAYWRIGHT_OK")
    except Exception as e:
        log("exception:" + repr(e))
        try:
            print(page.content()[:1500])
        except Exception:
            pass
        sys.exit(5)
    finally:
        browser.close()
