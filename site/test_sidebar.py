#!/usr/bin/env python3
"""Selenium: validar sidebar lateral vs conteúdo."""
import sys, time
from selenium import webdriver
from selenium.webdriver.common.by import By

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8081"

options = webdriver.ChromeOptions()
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1920,1080')

driver = webdriver.Chrome(options=options)
driver.set_page_load_timeout(30)

try:
    driver.get(URL)
    time.sleep(2)
    driver.find_element(By.CSS_SELECTOR, '[data-target="ide"]').click()
    time.sleep(2)

    def info(sel):
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            r = el.rect
            cs = driver.execute_script(
                "var s=window.getComputedStyle(arguments[0]);"
                "return {display:s.display, flexDir:s.flexDirection};", el)
            return {'x': r['x'], 'y': r['y'], 'w': r['width'], 'h': r['height'], **cs, 'ok': True}
        except:
            return {'ok': False}

    container = info('.ide-container')
    sidebar = info('.ide-sidebar')
    content = info('.ide-content')
    toolbar = info('.ide-toolbar')
    aibar = info('.ide-ai-bar')
    main = info('.ide-main')

    print("="*60)
    print("📐 LAYOUT SIDEBAR VS CONTEÚDO")
    print("="*60)

    for name, d in [('container', container), ('sidebar', sidebar), ('content', content),
                     ('toolbar', toolbar), ('ai-bar', aibar), ('main', main)]:
        if d['ok']:
            print(f"  {name:12} → x={d['x']:6.0f}  y={d['y']:6.0f}  w={d['w']:6.0f}  h={d['h']:6.0f}  display={d['display']}  flex-dir={d['flexDir']}")
        else:
            print(f"  {name:12} → ❌ NÃO ENCONTRADO")

    print()

    if sidebar['ok'] and content['ok']:
        sidebar_right = sidebar['x'] + sidebar['w']
        side_by_side = content['x'] >= sidebar_right - 5

        if side_by_side:
            print(f"✅ SIDEBAR LATERAL! sidebar acaba em x={sidebar_right:.0f}, content começa em x={content['x']:.0f}")
            print(f"   Sidebar: {sidebar['w']:.0f}px largo, Content: {content['w']:.0f}px largo")
        else:
            print(f"❌ EMPILHADO! sidebar x={sidebar['x']:.0f}, content x={content['x']:.0f}")
            print(f"   sidebar y={sidebar['y']:.0f}, content y={content['y']:.0f}")
    else:
        print("❌ Elementos não encontrados!")

    driver.save_screenshot('/tmp/ide_sidebar_test.png')
    print(f"\n📸 Screenshot: /tmp/ide_sidebar_test.png")

finally:
    driver.quit()
