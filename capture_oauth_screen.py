#!/usr/bin/env python3
"""Captura rapida de screenshot do Google Cloud Console"""
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

os.makedirs('/home/homelab/myClaude/screenshots', exist_ok=True)

options = Options()
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-gpu')
options.add_argument('--window-size=1920,1080')

print('Iniciando Chrome headless...')
driver = webdriver.Chrome(options=options)
print('Chrome iniciado!')

print('Navegando para Google Cloud Console...')
driver.get('https://console.cloud.google.com/apis/credentials/consent')
time.sleep(5)

print('Capturando screenshot...')
driver.save_screenshot('/home/homelab/myClaude/screenshots/oauth_screen.png')
print('Screenshot salvo: /home/homelab/myClaude/screenshots/oauth_screen.png')

print('URL:', driver.current_url)
print('Titulo:', driver.title)

driver.quit()
print('Concluido!')
