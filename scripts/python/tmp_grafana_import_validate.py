#!/usr/bin/env python3
import time, json, sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

GRAFANA_URL = 'http://192.168.15.2:3001'
CREDS = ('admin', 'Eddie@2026')
DASH_JSON = 'btc_trading_agent/grafana_dashboard.json'

opts = Options()
opts.add_argument('--headless=new')
opts.add_argument('--no-sandbox')
opts.add_argument('--disable-dev-shm-usage')
opts.add_argument("--disable-blink-features=AutomationControlled")
service = Service(ChromeDriverManager().install())

driver = webdriver.Chrome(service=service, options=opts)
wait = WebDriverWait(driver, 20)
try:
    driver.get(GRAFANA_URL + '/login')
    # login form
    wait.until(EC.presence_of_element_located((By.NAME, 'user')))
    driver.find_element(By.NAME, 'user').send_keys(CREDS[0])
    driver.find_element(By.NAME, 'password').send_keys(CREDS[1])
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    time.sleep(2)
    if '/login' in driver.current_url:
        print('LOGIN_FAILED')
        sys.exit(2)
    print('LOGIN_OK')

    # go to import page
    driver.get(GRAFANA_URL + '/dashboard/import')
    time.sleep(2)

    # try file input first
    file_input = None
    try:
        file_input = driver.find_element(By.CSS_SELECTOR, "input[type='file']")
    except:
        file_input = None

    if file_input:
        # send absolute path
        import os
        fn = os.path.abspath(DASH_JSON)
        file_input.send_keys(fn)
        time.sleep(2)
    else:
        # fallback: paste JSON into textarea
        try:
            with open(DASH_JSON) as f:
                j = f.read()
        except Exception as e:
            print('READ_FAIL', e)
            sys.exit(3)
        # try to find textarea
        try:
            ta = driver.find_element(By.CSS_SELECTOR, 'textarea')
            ta.clear()
            ta.send_keys(j)
            time.sleep(1)
        except Exception as e:
            print('IMPORT_NO_INPUT', e)
            sys.exit(4)

    # click Upload/Load button
    try:
        btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Upload') or contains(., 'Load') or contains(., 'Import')]")))
        btn.click()
    except Exception:
        pass
    time.sleep(3)

    # find and click 'Import' confirmation button
    try:
        import_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Import') and not(contains(@class,'btn-danger'))]")))
        import_btn.click()
        time.sleep(3)
    except Exception:
        pass

    # after import, try to detect success by URL change to /d/
    if '/d/' in driver.current_url:
        print('IMPORT_OK', driver.current_url)
    else:
        # try to find success message
        try:
            success = driver.find_element(By.CSS_SELECTOR, '.alert-success')
            print('IMPORT_OK_MSG')
        except:
            print('IMPORT_MAYBE_FAILED')
            # capture page snapshot for debug
            print('PAGE_TITLE:', driver.title)
            # dump html length
            print('HTML_LEN', len(driver.page_source))
            sys.exit(5)

    # validate presence of panels
    time.sleep(2)
    panels = driver.find_elements(By.CSS_SELECTOR, '.panel-container, [data-testid="panel"]')
    print('PANELS_FOUND', len(panels))
    valid = 0
    for i,p in enumerate(panels[:10]):
        try:
            if p.find_elements(By.CSS_SELECTOR, 'canvas, svg'):
                valid += 1
        except:
            pass
    print('PANELS_WITH_VIS', valid)
    sys.exit(0)
finally:
    driver.quit()
