#!/usr/bin/env python3
"""
Navegador Visual OAuth - Conecta ao Chrome existente e navega automaticamente
"""
import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime

SCREENSHOT_DIR = '/home/homelab/myClaude/screenshots/oauth_auto'
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.system('mkdir -p /mnt/c/temp/oauth_auto')

class OAuthNavigator:
    def __init__(self):
        self.driver = None
        self.step = 0
        
    def connect(self):
        print('Conectando ao Chrome...')
        options = Options()
        options.add_experimental_option("debuggerAddress", "localhost:9222")
        self.driver = webdriver.Chrome(options=options)
        print(f'Conectado! Pagina atual: {self.driver.title}')
        return True
    
    def screenshot(self, name):
        self.step += 1
        filename = f'{SCREENSHOT_DIR}/step_{self.step:02d}_{name}.png'
        self.driver.save_screenshot(filename)
        # Copiar para Windows
        os.system(f'cp "{filename}" /mnt/c/temp/oauth_auto/')
        print(f'[{self.step}] Screenshot: {name}')
        return filename
    
    def wait_click(self, xpaths, desc, timeout=10):
        print(f'  -> Clicando: {desc}')
        for xpath in xpaths if isinstance(xpaths, list) else [xpaths]:
            try:
                elem = WebDriverWait(self.driver, timeout).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                elem.click()
                time.sleep(1)
                return True
            except:
                continue
        print(f'     Nao encontrado: {desc}')
        return False
    
    def wait_type(self, xpaths, text, desc, timeout=10):
        print(f'  -> Digitando: {desc}')
        for xpath in xpaths if isinstance(xpaths, list) else [xpaths]:
            try:
                elem = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )
                elem.clear()
                elem.send_keys(text)
                time.sleep(0.5)
                return True
            except:
                continue
        print(f'     Campo nao encontrado: {desc}')
        return False
    
    def run(self):
        print('='*60)
        print('NAVEGACAO AUTOMATICA OAUTH')
        print('='*60)
        
        # PASSO 1: Ir para OAuth Consent
        print('\n[PASSO 1] Indo para OAuth Consent...')
        self.driver.get('https://console.cloud.google.com/apis/credentials/consent')
        time.sleep(5)
        self.screenshot('01_oauth_consent')
        
        # Verificar se precisa selecionar projeto
        if 'project' in self.driver.current_url.lower() or 'select' in self.driver.title.lower():
            print('  Selecionando projeto...')
            self.screenshot('01b_select_project')
            time.sleep(2)
        
        # PASSO 2: Selecionar External
        print('\n[PASSO 2] Selecionando tipo External...')
        time.sleep(2)
        self.screenshot('02_before_external')
        
        clicked = self.wait_click([
            "//mat-radio-button[contains(.,'External')]",
            "//mat-radio-button[contains(.,'Externo')]",
            "//div[contains(text(),'External')]/ancestor::mat-radio-button",
            "//span[contains(text(),'External')]/ancestor::mat-radio-button",
        ], 'External option', timeout=5)
        
        if clicked:
            time.sleep(1)
            self.screenshot('02_external_selected')
            
            # Clicar Create
            print('\n[PASSO 3] Clicando Create...')
            self.wait_click([
                "//button[.//span[contains(text(),'Create')]]",
                "//button[.//span[contains(text(),'Criar')]]",
                "//button[contains(@class,'primary')]",
            ], 'Create button')
            time.sleep(3)
            self.screenshot('03_after_create')
        
        # PASSO 4: Preencher App Info
        print('\n[PASSO 4] Preenchendo informacoes do app...')
        self.screenshot('04_app_form')
        
        # Nome do app
        self.wait_type([
            "//input[@formcontrolname='displayName']",
            "//input[contains(@aria-label,'App name')]",
            "//input[@id='input-0']",
        ], 'Eddie Assistant', 'App name')
        
        time.sleep(1)
        self.screenshot('04b_name_filled')
        
        # Email de suporte (dropdown)
        print('  -> Selecionando email de suporte...')
        self.wait_click([
            "//mat-select[@formcontrolname='supportEmail']",
            "//mat-select[contains(@aria-label,'support')]",
        ], 'Support email dropdown', timeout=5)
        time.sleep(1)
        self.screenshot('04c_email_dropdown')
        
        self.wait_click([
            "//mat-option[1]",
            "//mat-option",
        ], 'First email option', timeout=5)
        time.sleep(1)
        
        # Scroll para baixo
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)
        self.screenshot('04d_scrolled')
        
        # Email do desenvolvedor
        self.wait_type([
            "//textarea",
            "//input[@type='email']",
        ], 'eduardo.motta@gmail.com', 'Developer email')
        
        self.screenshot('04e_dev_email')
        
        # PASSO 5: Salvar e continuar
        print('\n[PASSO 5] Salvando e continuando...')
        self.wait_click([
            "//button[.//span[contains(text(),'Save and Continue')]]",
            "//button[.//span[contains(text(),'Salvar e continuar')]]",
            "//button[contains(@class,'save')]",
        ], 'Save and Continue')
        time.sleep(4)
        self.screenshot('05_scopes_page')
        
        # PASSO 6: Adicionar escopos
        print('\n[PASSO 6] Adicionando escopos...')
        self.wait_click([
            "//button[contains(.,'Add or remove scopes')]",
            "//button[contains(.,'Adicionar ou remover escopos')]",
        ], 'Add scopes button', timeout=5)
        time.sleep(2)
        self.screenshot('06_scopes_panel')
        
        # Marcar escopos
        scopes = ['gmail.readonly', 'gmail.modify', 'calendar']
        for scope in scopes:
            try:
                # Filtrar
                self.wait_type("//input[@placeholder='Filter']", scope, f'Filter {scope}', timeout=3)
                time.sleep(1)
                # Marcar
                self.wait_click(f"//tr[contains(.,'{scope}')]//mat-checkbox", f'Checkbox {scope}', timeout=3)
            except:
                print(f'     Escopo {scope} nao encontrado')
        
        self.screenshot('06b_scopes_selected')
        
        # Update
        self.wait_click([
            "//button[contains(.,'Update')]",
            "//button[contains(.,'Atualizar')]",
        ], 'Update button', timeout=5)
        time.sleep(2)
        
        # Salvar e continuar
        self.wait_click([
            "//button[.//span[contains(text(),'Save and Continue')]]",
            "//button[.//span[contains(text(),'Salvar e continuar')]]",
        ], 'Save and Continue')
        time.sleep(3)
        self.screenshot('07_test_users')
        
        # PASSO 7: Adicionar usuarios de teste
        print('\n[PASSO 7] Adicionando usuarios de teste...')
        self.wait_click([
            "//button[contains(.,'Add users')]",
            "//button[contains(.,'Adicionar usuarios')]",
        ], 'Add users', timeout=5)
        time.sleep(2)
        self.screenshot('07b_add_users_dialog')
        
        self.wait_type([
            "//input[@type='email']",
            "//textarea",
        ], 'eduardo.motta@gmail.com', 'Test user email')
        
        self.wait_click([
            "//button[contains(.,'Add') and @type='button']",
            "//button[contains(.,'Adicionar')]",
        ], 'Confirm add', timeout=5)
        time.sleep(2)
        
        # Salvar e continuar
        self.wait_click([
            "//button[.//span[contains(text(),'Save and Continue')]]",
            "//button[.//span[contains(text(),'Salvar e continuar')]]",
        ], 'Save and Continue')
        time.sleep(3)
        self.screenshot('08_summary')
        
        # PASSO 8: Ir para credenciais
        print('\n[PASSO 8] Indo para Credentials...')
        self.driver.get('https://console.cloud.google.com/apis/credentials')
        time.sleep(4)
        self.screenshot('09_credentials_page')
        
        # PASSO 9: Criar credenciais OAuth
        print('\n[PASSO 9] Criando credenciais OAuth...')
        self.wait_click([
            "//button[contains(.,'Create credentials')]",
            "//button[contains(.,'Criar credenciais')]",
        ], 'Create credentials', timeout=5)
        time.sleep(1)
        self.screenshot('09b_credentials_menu')
        
        self.wait_click([
            "//button[contains(.,'OAuth client ID')]",
            "//span[contains(text(),'OAuth client ID')]",
            "//mat-option[contains(.,'OAuth')]",
        ], 'OAuth client ID', timeout=5)
        time.sleep(3)
        self.screenshot('10_oauth_form')
        
        # PASSO 10: Configurar cliente
        print('\n[PASSO 10] Configurando cliente OAuth...')
        self.wait_click([
            "//mat-select[@formcontrolname='applicationType']",
            "//mat-select",
        ], 'Application type', timeout=5)
        time.sleep(1)
        
        self.wait_click([
            "//mat-option[contains(.,'Desktop')]",
            "//mat-option[contains(.,'Computador')]",
        ], 'Desktop option', timeout=5)
        time.sleep(1)
        self.screenshot('10b_desktop_selected')
        
        self.wait_type([
            "//input[@formcontrolname='displayName']",
            "//input[@type='text']",
        ], 'Eddie Assistant Desktop', 'Client name')
        self.screenshot('10c_client_named')
        
        # Criar
        self.wait_click([
            "//button[contains(@class,'primary')][contains(.,'Create')]",
            "//button[contains(.,'Criar')]",
        ], 'Create final', timeout=5)
        time.sleep(4)
        self.screenshot('11_credentials_created')
        
        print('\n' + '='*60)
        print('NAVEGACAO COMPLETA!')
        print(f'Screenshots em: {SCREENSHOT_DIR}')
        print(f'E em: C:\\temp\\oauth_auto')
        print('='*60)
        
        # Listar screenshots
        print('\nScreenshots:')
        for f in sorted(os.listdir(SCREENSHOT_DIR)):
            print(f'  - {f}')

if __name__ == '__main__':
    nav = OAuthNavigator()
    try:
        nav.connect()
        nav.run()
    except Exception as e:
        print(f'\nErro: {e}')
        import traceback
        traceback.print_exc()
    
    input('\nPressione ENTER para finalizar...')
