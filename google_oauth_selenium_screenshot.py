#!/usr/bin/env python3
"""
Script Selenium com captura de tela para configurar OAuth no Google Cloud
"""
import time
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

class GoogleOAuthSetup:
    def __init__(self, headless=True):
        self.options = Options()
        if headless:
            self.options.add_argument('--headless=new')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--disable-gpu')
        self.options.add_argument('--window-size=1920,1080')
        self.options.add_argument('--force-device-scale-factor=1')
        self.driver = None
        self.screenshot_dir = '/home/home-lab/myClaude/screenshots'
        os.makedirs(self.screenshot_dir, exist_ok=True)
        
    def start(self):
        print('Iniciando Chrome...')
        self.driver = webdriver.Chrome(options=self.options)
        print('Navegador iniciado!')
        
    def close(self):
        if self.driver:
            self.driver.quit()
    
    def screenshot(self, name=None):
        """Captura screenshot da tela atual"""
        if not name:
            name = datetime.now().strftime('%Y%m%d_%H%M%S')
        filepath = f'{self.screenshot_dir}/screen_{name}.png'
        self.driver.save_screenshot(filepath)
        print(f'Screenshot salvo: {filepath}')
        return filepath
    
    def get_page_info(self):
        """Retorna informacoes da pagina atual"""
        return {
            'url': self.driver.current_url,
            'title': self.driver.title
        }

def main():
    print('='*50)
    print('GOOGLE OAUTH SETUP - COM CAPTURA DE TELA')
    print('='*50)
    
    setup = GoogleOAuthSetup()
    setup.start()
    
    # Navegar para pagina OAuth
    print('\nNavegando para Google Cloud Console...')
    setup.driver.get('https://console.cloud.google.com/apis/credentials/consent')
    time.sleep(5)
    
    # Capturar tela inicial
    setup.screenshot('01_inicial')
    info = setup.get_page_info()
    print(f'URL: {info["url"]}')
    print(f'Titulo: {info["title"]}')
    
    print('\n' + '='*50)
    print('COMANDOS DISPONIVEIS:')
    print('  s - Capturar screenshot')
    print('  i - Info da pagina atual')
    print('  g <url> - Navegar para URL')
    print('  c - Ir para Credentials')
    print('  o - Ir para OAuth Consent')
    print('  q - Sair')
    print('='*50)
    
    while True:
        cmd = input('\n> ').strip()
        
        if cmd == 's':
            setup.screenshot()
        elif cmd == 'i':
            info = setup.get_page_info()
            print(f'URL: {info["url"]}')
            print(f'Titulo: {info["title"]}')
        elif cmd.startswith('g '):
            url = cmd[2:].strip()
            setup.driver.get(url)
            time.sleep(3)
            setup.screenshot()
        elif cmd == 'c':
            setup.driver.get('https://console.cloud.google.com/apis/credentials')
            time.sleep(3)
            setup.screenshot('credentials')
        elif cmd == 'o':
            setup.driver.get('https://console.cloud.google.com/apis/credentials/consent')
            time.sleep(3)
            setup.screenshot('oauth_consent')
        elif cmd == 'q':
            break
        else:
            print('Comando invalido. Use: s, i, g <url>, c, o, q')
    
    setup.close()
    print('\nScreenshots salvos em: /home/home-lab/myClaude/screenshots/')

if __name__ == '__main__':
    main()
