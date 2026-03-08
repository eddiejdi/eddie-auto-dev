#!/usr/bin/env python3
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

class GoogleOAuthSetup:
    def __init__(self):
        self.options = Options()
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--window-size=1920,1080')
        self.driver = None
        
    def start(self):
        print('Iniciando Chrome...')
        self.driver = webdriver.Chrome(options=self.options)
        print('Navegador iniciado!')
        
    def close(self):
        if self.driver:
            self.driver.quit()

def main():
    print('GOOGLE OAUTH SETUP')
    setup = GoogleOAuthSetup()
    setup.start()
    setup.driver.get('https://console.cloud.google.com/apis/credentials/consent')
    print('Faca a configuracao manualmente no navegador.')
    print('O navegador vai permanecer aberto para voce configurar.')
    input('Pressione ENTER para fechar...')
    setup.close()

if __name__ == '__main__':
    main()
