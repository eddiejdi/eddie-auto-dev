#!/usr/bin/env python3
"""Selenium agent para análise e validação do layout IDE."""
import sys, time, json
import requests
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8081"
# Se o pytest (ou outro runner) passou flags como argv (ex: '-q'),
# evitar usar isso como URL inválido para o Selenium.
if not URL.startswith("http"):
    URL = "http://localhost:8081"

# Se o servidor não estiver escutando, pular os testes de UI (evita falha no CI local)
try:
    requests.head(URL, timeout=1)
except Exception:
    pytest.skip(f"Servidor {URL} indisponível — pulando testes de UI", allow_module_level=True)

options = webdriver.ChromeOptions()
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1920,1080')

driver = webdriver.Chrome(options=options)
driver.set_page_load_timeout(30)

try:
    print(f"🔍 Acessando {URL}...")
    driver.get(URL)
    time.sleep(2)

    # Clicar na aba IDE Python
    ide_tab = driver.find_element(By.CSS_SELECTOR, '[data-target="ide"]')
    ide_tab.click()
    time.sleep(2)

    # Screenshot do estado original
    driver.save_screenshot('/tmp/ide_layout_original.png')
    print("📸 Screenshot salvo: /tmp/ide_layout_original.png")

    # Analisar estrutura do IDE
    def get_rect(sel):
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            r = el.rect
            cs = driver.execute_script(
                "var s=window.getComputedStyle(arguments[0]);"
                "return {display:s.display, flexDir:s.flexDirection, gridCols:s.gridTemplateColumns,"
                " gridRows:s.gridTemplateRows, gridAreas:s.gridTemplateAreas,"
                " position:s.position, overflow:s.overflow};", el)
            return {
                'sel': sel,
                'x': r['x'], 'y': r['y'], 'w': r['width'], 'h': r['height'],
                'visible': el.is_displayed(),
                **cs
            }
        except Exception as e:
            return {'sel': sel, 'error': str(e)}

    elements = [
        '.ide-container',
        '.ide-toolbar',
        '.ide-file-tabs',
        '.ide-file-tabs-list',
        '.ide-actions',
        '.ide-ai-bar',
        '.ide-main',
        '.ide-editor-wrapper',
        '.ide-output-wrapper',
    ]

    print("\n" + "="*70)
    print("📐 ANÁLISE DE LAYOUT DO IDE")
    print("="*70)

    results = {}
    for sel in elements:
        info = get_rect(sel)
        results[sel] = info
        if 'error' in info:
            print(f"  ❌ {sel}: {info['error']}")
        else:
            print(f"  {'✅' if info['visible'] else '❌'} {sel}")
            print(f"     pos=({info['x']:.0f},{info['y']:.0f}) size={info['w']:.0f}x{info['h']:.0f}")
            print(f"     display={info['display']} grid-cols={info['gridCols']}")
            if info.get('gridAreas', 'none') != 'none':
                print(f"     grid-areas={info['gridAreas']}")

    # Verificar se toolbar e ai-bar estão lado a lado (sidebar) vs empilhados
    container = results.get('.ide-container', {})
    toolbar = results.get('.ide-toolbar', {})
    ai_bar = results.get('.ide-ai-bar', {})
    main = results.get('.ide-main', {})

    print("\n" + "="*70)
    print("🔎 DIAGNÓSTICO")
    print("="*70)

    if 'error' not in container:
        print(f"  Container: {container['display']}, {container['w']:.0f}x{container['h']:.0f}")
        print(f"  Grid cols: {container['gridCols']}")
        print(f"  Grid rows: {container['gridRows']}")

    if 'error' not in toolbar and 'error' not in ai_bar:
        stacked = abs(toolbar['x'] - ai_bar['x']) < 10 and toolbar['y'] < ai_bar['y']
        side_by_side = toolbar['x'] != ai_bar['x']
        print(f"  Toolbar y={toolbar['y']:.0f}, AI-bar y={ai_bar['y']:.0f}")
        print(f"  Layout: {'EMPILHADO ❌' if stacked else 'LADO A LADO ✅'}")

    if 'error' not in main:
        print(f"  Main: {main['display']}, grid-cols={main['gridCols']}")
        print(f"  Main size: {main['w']:.0f}x{main['h']:.0f}")

    # Salvar JSON
    with open('/tmp/ide_layout_analysis.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print("\n📊 JSON salvo: /tmp/ide_layout_analysis.json")

    print("\n✅ Análise concluída!")

finally:
    driver.quit()
