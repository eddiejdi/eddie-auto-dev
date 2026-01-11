#!/usr/bin/env python3
"""
Script simples para capturar screenshots do Google Cloud Console
Usa Chrome headless no WSL
"""
import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from datetime import datetime

# Configurar diretorio
SCREENSHOT_DIR = '/home/eddie/myClaude/screenshots/oauth_steps'
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def capture_steps():
    # Configurar Chrome headless
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    
    print('='*60)
    print('OAUTH SETUP - CAPTURA DE CADA PASSO')
    print('='*60)
    
    print('\nIniciando Chrome headless...')
    driver = webdriver.Chrome(options=options)
    step = 0
    
    def screenshot(name):
        nonlocal step
        step += 1
        filepath = f'{SCREENSHOT_DIR}/step_{step:02d}_{name}.png'
        driver.save_screenshot(filepath)
        print(f'[{step}] Screenshot: {name}')
        return filepath
    
    try:
        # Passo 1: Tela de consentimento OAuth
        print('\n[PASSO 1] Tela de Consentimento OAuth')
        driver.get('https://console.cloud.google.com/apis/credentials/consent')
        time.sleep(3)
        screenshot('consent_initial')
        print(f'    URL: {driver.current_url}')
        print(f'    Titulo: {driver.title}')
        
        # Passo 2: Pagina de login (se redirecionado)
        if 'accounts.google.com' in driver.current_url:
            screenshot('login_page')
            print('    -> Redirecionado para login')
        
        # Passo 3: Pagina de credenciais
        print('\n[PASSO 2] Pagina de Credenciais')
        driver.get('https://console.cloud.google.com/apis/credentials')
        time.sleep(3)
        screenshot('credentials_page')
        print(f'    URL: {driver.current_url}')
        
        # Passo 4: API Library
        print('\n[PASSO 3] API Library')
        driver.get('https://console.cloud.google.com/apis/library')
        time.sleep(3)
        screenshot('api_library')
        print(f'    URL: {driver.current_url}')
        
        # Passo 5: Gmail API
        print('\n[PASSO 4] Gmail API')
        driver.get('https://console.cloud.google.com/apis/library/gmail.googleapis.com')
        time.sleep(3)
        screenshot('gmail_api')
        print(f'    URL: {driver.current_url}')
        
        # Passo 6: Calendar API
        print('\n[PASSO 5] Calendar API')
        driver.get('https://console.cloud.google.com/apis/library/calendar-json.googleapis.com')
        time.sleep(3)
        screenshot('calendar_api')
        print(f'    URL: {driver.current_url}')
        
        print('\n' + '='*60)
        print(f'CONCLUIDO! {step} screenshots salvos em:')
        print(f'{SCREENSHOT_DIR}')
        print('='*60)
        
        # Listar arquivos
        print('\nArquivos gerados:')
        for f in sorted(os.listdir(SCREENSHOT_DIR)):
            filepath = os.path.join(SCREENSHOT_DIR, f)
            size = os.path.getsize(filepath)
            print(f'  - {f} ({size/1024:.1f} KB)')
        
    finally:
        driver.quit()

if __name__ == '__main__':
    capture_steps()
