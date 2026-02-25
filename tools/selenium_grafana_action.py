#!/usr/bin/env python3
"""
Automatiza uma ação no Grafana (por exemplo clicar no botão que chama /set-live).

Uso:
  source .venv_selenium/bin/activate
  GRAFANA_URL="http://192.168.15.2:3000/d/your-dashboard" \
  ACTION_SELECTOR='button[aria-label="Set Live"]' \
  python3 tools/selenium_grafana_action.py

Variáveis de ambiente opcionais:
- GRAFANA_URL: URL do painel do Grafana (obrigatório)
- GRAFANA_USER, GRAFANA_PASS: credenciais de login (se necessário)
- LOGIN_USER_SELECTOR, LOGIN_PASS_SELECTOR, LOGIN_BUTTON_SELECTOR: seletores CSS para o formulário de login
- ACTION_SELECTOR: seletor CSS do elemento a ser clicado (obrigatório)
- HEADLESS: '1' para rodar sem cabeça

Retorna 0 em sucesso, imprime log simples.
"""

import os
import sys
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, WebDriverException

GRAFANA_URL = os.environ.get('GRAFANA_URL')
ACTION_SELECTOR = os.environ.get('ACTION_SELECTOR')
GRAFANA_USER = os.environ.get('GRAFANA_USER')
GRAFANA_PASS = os.environ.get('GRAFANA_PASS')
HEADLESS = os.environ.get('HEADLESS', '1') == '1'

LOGIN_USER_SELECTOR = os.environ.get('LOGIN_USER_SELECTOR', 'input[name="user"]')
LOGIN_PASS_SELECTOR = os.environ.get('LOGIN_PASS_SELECTOR', 'input[name="password"]')
LOGIN_BUTTON_SELECTOR = os.environ.get('LOGIN_BUTTON_SELECTOR', 'button[type="submit"]')

if not GRAFANA_URL or not ACTION_SELECTOR:
    print('ERROR: defina GRAFANA_URL e ACTION_SELECTOR como variáveis de ambiente')
    sys.exit(2)

opts = Options()
if HEADLESS:
    opts.add_argument('--headless=new')
opts.add_argument('--no-sandbox')
opts.add_argument('--disable-dev-shm-usage')

try:
    driver = webdriver.Chrome(options=opts)
except WebDriverException as e:
    print('ERROR: não foi possível iniciar o Chrome WebDriver:', e)
    sys.exit(3)

try:
    print('Abrindo', GRAFANA_URL)
    driver.get(GRAFANA_URL)
    time.sleep(2)

    # Tentar login se credenciais fornecidas e form visível
    if GRAFANA_USER and GRAFANA_PASS:
        try:
            user_field = driver.find_element(By.CSS_SELECTOR, LOGIN_USER_SELECTOR)
            pass_field = driver.find_element(By.CSS_SELECTOR, LOGIN_PASS_SELECTOR)
            user_field.clear(); user_field.send_keys(GRAFANA_USER)
            pass_field.clear(); pass_field.send_keys(GRAFANA_PASS)
            btn = driver.find_element(By.CSS_SELECTOR, LOGIN_BUTTON_SELECTOR)
            btn.click()
            print('Login enviado, aguardando...')
            time.sleep(3)
        except NoSuchElementException:
            print('Formulário de login não encontrado com os seletores padrão; assumindo já logado')

    # Tentar encontrar e clicar o elemento
    def try_click(selector):
        try:
            el = driver.find_element(By.CSS_SELECTOR, selector)
            el.click()
            print('Elemento clicado (CSS):', selector)
            return True
        except Exception:
            return False

    def try_click_xpath(xpath):
        try:
            el = driver.find_element(By.XPATH, xpath)
            el.click()
            print('Elemento clicado (XPATH):', xpath)
            return True
        except Exception:
            return False

    clicked = False
    if ACTION_SELECTOR == 'AUTO':
        # tentativas comuns
        css_attempts = [
            'button[aria-label="Set Live"]',
            'button[title*="Live"]',
            'button[aria-label*="Live"]',
            'button.btn-primary',
            'button[class*="set-live"]',
        ]
        xpath_attempts = [
            "//button[contains(normalize-space(.), 'Set Live')]",
            "//button[contains(normalize-space(.), 'Live')]",
            "//a[contains(normalize-space(.), 'Live')]",
        ]

        for s in css_attempts:
            if try_click(s):
                clicked = True
                break

        if not clicked:
            for x in xpath_attempts:
                if try_click_xpath(x):
                    clicked = True
                    break

        # se URL contém viewPanel, tentar encontrar dentro do painel
        if not clicked and 'viewPanel=' in driver.current_url:
            try:
                import re
                m = re.search(r'viewPanel=(panel-\d+)', driver.current_url)
                if m:
                    panel_id = m.group(1)
                    try_click(f'#{panel_id} button')
            except Exception:
                pass

    else:
        try:
            el = driver.find_element(By.CSS_SELECTOR, ACTION_SELECTOR)
            el.click()
            print('Elemento clicado:', ACTION_SELECTOR)
            clicked = True
            time.sleep(1)
        except NoSuchElementException:
            clicked = False

    if not clicked:
        print('Elemento não encontrado com os seletores tentados:', ACTION_SELECTOR)
        print('Tentar capturar screenshot em /tmp/selenium_grafana.png')
        driver.save_screenshot('/tmp/selenium_grafana.png')
        sys.exit(4)

    # opcional: aguardar ou verificar resultado
    print('Ação realizada com sucesso.')
    sys.exit(0)
finally:
    driver.quit()
