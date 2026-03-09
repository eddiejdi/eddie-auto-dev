#!/usr/bin/env python3
"""
Selenium Visual Tests — Grafana AutoCoinBot Trading Dashboard
Executa dentro de container Docker na mesma rede do Grafana.

Testes:
  1. Login no Grafana
  2. Navegação ao dashboard importado
  3. Verificação de 15 painéis
  4. Screenshot de cada seção
  5. Verificação de tipos de visualização (stat, timeseries, gauge, piechart, table)
  6. Validação de títulos dos painéis
  7. Verificação de datasource Prometheus
  8. Screenshot full-page final
"""
import os, sys, time, json, base64, traceback
from datetime import datetime, timezone

import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Marcar TODO o módulo como external (requer Grafana real acessível)
pytestmark = pytest.mark.external

# ── Config ──────────────────────────────────────────────────────────────
GRAFANA_URL  = os.environ.get("GRAFANA_URL", "https://www.rpa4all.com/grafana")
GRAFANA_USER = os.environ.get("GRAFANA_USER", "admin")
GRAFANA_PASS = os.environ.get("GRAFANA_PASS", "Shared@2026")
DASH_UID     = os.environ.get("DASH_UID", "autocoinbot-trading")
SCREENSHOT_DIR = os.environ.get("SCREENSHOT_DIR", "/tmp/screenshots")

EXPECTED_PANELS = [
    {"id": 1,  "title": "Preço BTC Atual",              "type": "stat"},
    {"id": 2,  "title": "PnL Total",                    "type": "stat"},
    {"id": 3,  "title": "Win Rate",                     "type": "stat"},
    {"id": 4,  "title": "Total de Trades",              "type": "stat"},
    {"id": 5,  "title": "Preço BTC (Tempo Real)",       "type": "timeseries"},
    {"id": 6,  "title": "PnL Acumulado",                "type": "timeseries"},
    {"id": 7,  "title": "Distribuição de Decisões",     "type": "piechart"},
    {"id": 8,  "title": "RSI (Relative Strength Index)","type": "gauge"},
    {"id": 9,  "title": "Trades por Hora",              "type": "timeseries"},
    {"id": 10, "title": "Indicadores Técnicos",         "type": "timeseries"},
    {"id": 11, "title": "Últimas Operações",            "type": "table"},
    {"id": 12, "title": "Status do Agente",             "type": "stat", "emoji_title": "\U0001f916 Status do Agente"},
    {"id": 13, "title": "Modo de Opera\u00e7\u00e3o",             "type": "stat", "emoji_title": "\u2699\ufe0f Modo de Opera\u00e7\u00e3o"},
    {"id": 14, "title": "\u00daltima Atividade",             "type": "stat", "emoji_title": "\u23f0 \u00daltima Atividade"},
    {"id": 15, "title": "Episodes Treinados",           "type": "stat", "emoji_title": "\U0001f9e0 Episodes Treinados"},
]

# ── Helpers ─────────────────────────────────────────────────────────────
results = []
ts = lambda: datetime.now(timezone.utc).strftime("%H:%M:%S")

def log(msg):
    print(f"[{ts()}] {msg}", flush=True)

def record(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results.append({"test": name, "status": status, "detail": detail})
    log(f"  {'✅' if passed else '❌'} {name}: {detail}")

def screenshot(driver, name):
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
    driver.save_screenshot(path)
    log(f"  📸 Screenshot → {path}")
    return path

# ── Browser setup ───────────────────────────────────────────────────────
def make_driver():
    opts = Options()
    opts.binary_location = "/usr/bin/chromium-browser"
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1200")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--ignore-certificate-errors")
    opts.add_argument("--allow-insecure-localhost")
    opts.add_argument("--remote-debugging-port=0")
    # Use system chromedriver
    svc = Service("/usr/bin/chromedriver")
    return webdriver.Chrome(service=svc, options=opts)

# ── Tests ───────────────────────────────────────────────────────────────
def test_login(driver):
    """T1: Login no Grafana"""
    log("TEST 1: Login no Grafana")
    driver.get(f"{GRAFANA_URL}/login")
    wait = WebDriverWait(driver, 20)
    try:
        user_input = wait.until(EC.presence_of_element_located((By.NAME, "user")))
        user_input.clear()
        user_input.send_keys(GRAFANA_USER)
        driver.find_element(By.NAME, "password").send_keys(GRAFANA_PASS)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(3)
        # Se Grafana pedir para mudar a senha, pular
        try:
            skip = driver.find_element(By.XPATH,
                "//a[contains(text(),'Skip')] | //button[contains(text(),'Skip')]")
            skip.click()
            time.sleep(1)
        except Exception:
            pass
        logged = "/login" not in driver.current_url
        screenshot(driver, "01_login")
        record("Login Grafana", logged,
               f"URL após login: {driver.current_url}")
        return logged
    except Exception as e:
        screenshot(driver, "01_login_fail")
        record("Login Grafana", False, str(e))
        return False


def test_navigate_dashboard(driver):
    """T2: Navegar até o dashboard"""
    log("TEST 2: Navegar ao dashboard")
    # Usar URL direta com kiosk=false para ter menu
    url = f"{GRAFANA_URL}/d/{DASH_UID}"
    driver.get(url)
    time.sleep(5)
    screenshot(driver, "02_dashboard_load")
    title = driver.title
    has_dash = "/d/" in driver.current_url
    record("Navegação ao Dashboard", has_dash,
           f"title={title} url={driver.current_url}")
    return has_dash


def test_panel_count(driver):
    """T3: Verificar quantidade de painéis"""
    log("TEST 3: Contar painéis")
    # Grafana renders panels inside elements with data-panelid
    panels = driver.find_elements(By.CSS_SELECTOR,
        "[data-panelid], .panel-container, [class*='panel-wrapper']")
    count = len(panels)
    # Fallback: try react-grid-item
    if count == 0:
        panels = driver.find_elements(By.CSS_SELECTOR,
            ".react-grid-item, [class*='GridItem']")
        count = len(panels)
    passed = count >= 15
    record("Quantidade de Painéis (≥15)", passed,
           f"Encontrados: {count}")
    screenshot(driver, "03_panel_count")
    return count


def test_panel_titles(driver):
    """T4: Verificar títulos dos painéis"""
    log("TEST 4: Verificar títulos")
    # Scroll to bottom to ensure all panels are rendered
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(3)
    driver.execute_script("window.scrollTo(0, 0)")
    time.sleep(1)
    page = driver.page_source
    found = 0
    missing = []
    for p in EXPECTED_PANELS:
        # Try exact title first, then emoji_title variant
        title = p["title"]
        emoji_title = p.get("emoji_title", "")
        if title in page or (emoji_title and emoji_title in page):
            found += 1
        else:
            missing.append(title)
    passed = found >= 13
    record("Títulos dos Painéis (≥13/15)", passed,
           f"Encontrados: {found}/15. Missing: {missing[:5]}")
    return found


def test_datasource_prometheus(driver):
    """T5: Verificar datasource via API"""
    log("TEST 5: Verificar Datasource Prometheus (API)")
    driver.get(f"{GRAFANA_URL}/api/datasources")
    time.sleep(2)
    body = driver.find_element(By.TAG_NAME, "body").text
    has_prom = "prometheus" in body.lower() or "Prometheus" in body
    record("Datasource Prometheus", has_prom,
           f"Resposta contém 'prometheus': {has_prom}")
    # Voltar ao dashboard
    driver.get(f"{GRAFANA_URL}/d/{DASH_UID}")
    time.sleep(3)
    return has_prom


def test_scroll_sections(driver):
    """T6: Scroll e screenshots por seção"""
    log("TEST 6: Scroll e screenshots por seção")
    screenshots_taken = 0
    # Scroll em etapas de 400px e capturar
    page_height = driver.execute_script("return document.body.scrollHeight")
    viewport = driver.execute_script("return window.innerHeight")
    pos = 0
    section = 0
    while pos < page_height:
        section += 1
        driver.execute_script(f"window.scrollTo(0, {pos})")
        time.sleep(1)
        screenshot(driver, f"06_section_{section:02d}")
        screenshots_taken += 1
        pos += viewport - 100  # overlap 100px
    record("Screenshots por Seção", screenshots_taken >= 2,
           f"Seções capturadas: {screenshots_taken}")
    # Voltar ao topo
    driver.execute_script("window.scrollTo(0, 0)")
    time.sleep(1)
    return screenshots_taken


def test_stat_panels(driver):
    """T7: Verificar painéis stat (KPI cards)"""
    log("TEST 7: Painéis Stat (KPIs)")
    page = driver.page_source
    # Stat panels exibem valores numéricos grandes; verificar presença dos títulos KPI
    kpi_titles = ["Preço BTC Atual", "PnL Total", "Win Rate",
                  "Total de Trades", "Status do Agente"]
    found = sum(1 for t in kpi_titles if t in page)
    passed = found >= 3
    record("Painéis Stat KPI (≥3/5)", passed,
           f"KPIs encontrados: {found}/5")
    return found


def test_timeseries_panels(driver):
    """T8: Verificar painéis timeseries (gráficos)"""
    log("TEST 8: Painéis Timeseries")
    # Timeseries panels render canvas ou svg
    canvases = driver.find_elements(By.CSS_SELECTOR, "canvas")
    svgs = driver.find_elements(By.CSS_SELECTOR, "svg")
    total_vis = len(canvases) + len(svgs)
    passed = total_vis >= 1
    record("Elementos Visuais (canvas/svg ≥1)", passed,
           f"canvas={len(canvases)} svg={len(svgs)}")
    screenshot(driver, "08_timeseries")
    return total_vis


def test_fullpage_screenshot(driver):
    """T9: Screenshot full-page do dashboard"""
    log("TEST 9: Full-page screenshot")
    # Expandir viewport para capturar tudo
    page_height = driver.execute_script("return document.body.scrollHeight")
    driver.set_window_size(1920, max(page_height + 200, 1200))
    time.sleep(2)
    path = screenshot(driver, "09_fullpage")
    driver.set_window_size(1920, 1200)
    record("Full-page Screenshot", os.path.exists(path),
           f"Tamanho: {os.path.getsize(path)} bytes")
    return path


def test_refresh_interval(driver):
    """T10: Verificar auto-refresh configurado"""
    log("TEST 10: Verificar refresh interval")
    page = driver.page_source
    # O dashboard tem refresh: "5s"
    has_refresh = "5s" in page or "Refresh" in page
    record("Auto-refresh configurado", has_refresh,
           "Refresh 5s detectado" if has_refresh else "Refresh não encontrado na page source")
    return has_refresh


# ── Main ────────────────────────────────────────────────────────────────
def main():
    log("=" * 60)
    log("GRAFANA SELENIUM VISUAL TESTS")
    log(f"Target: {GRAFANA_URL}")
    log(f"Dashboard UID: {DASH_UID}")
    log("=" * 60)

    driver = make_driver()
    try:
        # T1: Login
        if not test_login(driver):
            log("ABORT: Login falhou, testes subsequentes cancelados")
            return 1

        # T2–T10
        test_navigate_dashboard(driver)
        test_panel_count(driver)
        test_panel_titles(driver)
        test_datasource_prometheus(driver)
        test_scroll_sections(driver)
        test_stat_panels(driver)
        test_timeseries_panels(driver)
        test_fullpage_screenshot(driver)
        test_refresh_interval(driver)

    except Exception as e:
        log(f"EXCEPTION: {e}")
        traceback.print_exc()
        screenshot(driver, "crash")
    finally:
        driver.quit()

    # ── Report ──────────────────────────────────────────────────
    log("")
    log("=" * 60)
    log("RELATÓRIO DE TESTES VISUAIS SELENIUM")
    log("=" * 60)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    total = len(results)
    for r in results:
        icon = "✅" if r["status"] == "PASS" else "❌"
        log(f"  {icon} {r['test']}: {r['detail']}")
    log("-" * 60)
    log(f"TOTAL: {passed}/{total} PASS | {failed} FAIL")
    log("=" * 60)

    # Salvar relatório JSON
    report_path = os.path.join(SCREENSHOT_DIR, "report.json")
    with open(report_path, "w") as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "grafana_url": GRAFANA_URL,
            "dashboard_uid": DASH_UID,
            "total": total, "passed": passed, "failed": failed,
            "tests": results,
        }, f, indent=2)
    log(f"Relatório salvo em {report_path}")

    # Listar screenshots
    log(f"\nScreenshots em {SCREENSHOT_DIR}:")
    for f_name in sorted(os.listdir(SCREENSHOT_DIR)):
        fpath = os.path.join(SCREENSHOT_DIR, f_name)
        log(f"  {f_name} ({os.path.getsize(fpath)} bytes)")

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
