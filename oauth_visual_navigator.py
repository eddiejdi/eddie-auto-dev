#!/usr/bin/env python3
"""
Script para conectar Selenium a Chrome existente e navegar visualmente
Captura screenshot de cada passo
"""
import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime

# Configuracoes
SCREENSHOT_DIR = '/home/homelab/myClaude/screenshots/oauth_visual'
CHROME_DEBUG_PORT = 9222
WINDOWS_IP = '10.255.255.254'  # IP do Windows visto do WSL
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

class VisualOAuthNavigator:
    def __init__(self):
        self.driver = None
        self.step = 0
        
    def connect_to_chrome(self):
        """Conecta ao Chrome existente via debug port"""
        print(f'Conectando ao Chrome em {WINDOWS_IP}:{CHROME_DEBUG_PORT}...')
        
        options = Options()
        options.add_experimental_option("debuggerAddress", f"{WINDOWS_IP}:{CHROME_DEBUG_PORT}")
        
        self.driver = webdriver.Chrome(options=options)
        print(f'Conectado! URL atual: {self.driver.current_url}')
        print(f'Titulo: {self.driver.title}')
        return True
    
    def screenshot(self, name):
        """Captura screenshot com nome descritivo"""
        self.step += 1
        timestamp = datetime.now().strftime('%H%M%S')
        filename = f'{SCREENSHOT_DIR}/step_{self.step:02d}_{name}_{timestamp}.png'
        self.driver.save_screenshot(filename)
        print(f'📸 [{self.step}] {name}')
        # Copiar para Windows
        os.system(f'cp "{filename}" /mnt/c/temp/oauth_visual/ 2>/dev/null')
        return filename
    
    def wait_and_click(self, xpaths, description, timeout=10):
        """Espera elemento e clica"""
        print(f'🔍 Procurando: {description}')
        for xpath in xpaths:
            try:
                element = WebDriverWait(self.driver, timeout).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                self.screenshot(f'before_click_{description.replace(" ", "_")}')
                element.click()
                print(f'✅ Clicado: {description}')
                time.sleep(2)
                self.screenshot(f'after_click_{description.replace(" ", "_")}')
                return True
            except:
                continue
        print(f'⚠️ Nao encontrado: {description}')
        return False
    
    def wait_and_type(self, xpaths, text, description, timeout=10):
        """Espera campo e digita"""
        print(f'⌨️ Preenchendo: {description}')
        for xpath in xpaths:
            try:
                element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )
                element.clear()
                element.send_keys(text)
                print(f'✅ Digitado: {text}')
                self.screenshot(f'typed_{description.replace(" ", "_")}')
                return True
            except:
                continue
        print(f'⚠️ Campo nao encontrado: {description}')
        return False
    
    def navigate_oauth_setup(self, email):
        """Navega por todo o fluxo OAuth capturando cada passo"""
        
        print('\n' + '='*60)
        print('🚀 INICIANDO NAVEGACAO VISUAL DO OAUTH')
        print('='*60)
        
        # Criar pasta no Windows
        os.system('mkdir -p /mnt/c/temp/oauth_visual')
        
        # PASSO 1: Ir para tela de consentimento
        print('\n📌 PASSO 1: Tela de Consentimento OAuth')
        self.driver.get('https://console.cloud.google.com/apis/credentials/consent')
        time.sleep(3)
        self.screenshot('01_consent_screen')
        
        # PASSO 2: Selecionar External
        print('\n📌 PASSO 2: Selecionando tipo External')
        self.wait_and_click([
            "//mat-radio-button[contains(.,'External')]",
            "//mat-radio-button[contains(.,'Externo')]",
            "//div[contains(@class,'mdc-radio')]//following-sibling::*[contains(.,'External')]/..",
        ], 'External_option')
        
        # PASSO 3: Clicar Create
        print('\n📌 PASSO 3: Clicando Create')
        self.wait_and_click([
            "//button[contains(.,'Create')]",
            "//button[contains(.,'Criar')]",
            "//span[text()='Create']/ancestor::button",
        ], 'Create_button')
        time.sleep(3)
        self.screenshot('03_app_info_form')
        
        # PASSO 4: Preencher nome do app
        print('\n📌 PASSO 4: Preenchendo nome do app')
        self.wait_and_type([
            "//input[@formcontrolname='displayName']",
            "//input[contains(@aria-label,'App name')]",
            "//input[@type='text']",
        ], 'Eddie Assistant', 'app_name')
        
        # PASSO 5: Selecionar email de suporte
        print('\n📌 PASSO 5: Selecionando email de suporte')
        self.wait_and_click([
            "//mat-select[@formcontrolname='supportEmail']",
            "//mat-select[contains(@aria-label,'support')]",
        ], 'support_email_dropdown')
        time.sleep(1)
        self.wait_and_click([
            f"//mat-option[contains(.,'{email}')]",
            "//mat-option[1]",
        ], 'email_option')
        
        # PASSO 6: Scroll e preencher email desenvolvedor
        print('\n📌 PASSO 6: Email do desenvolvedor')
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)
        self.screenshot('06_scrolled_down')
        self.wait_and_type([
            "//textarea",
            "//input[@type='email']",
        ], email, 'developer_email')
        
        # PASSO 7: Salvar e continuar
        print('\n📌 PASSO 7: Salvar e Continuar')
        self.wait_and_click([
            "//button[contains(.,'Save and Continue')]",
            "//button[contains(.,'Salvar e continuar')]",
        ], 'save_continue_1')
        time.sleep(3)
        self.screenshot('07_scopes_page')
        
        # PASSO 8: Adicionar escopos
        print('\n📌 PASSO 8: Abrindo painel de escopos')
        self.wait_and_click([
            "//button[contains(.,'Add or remove scopes')]",
            "//button[contains(.,'Adicionar ou remover escopos')]",
        ], 'add_scopes_button')
        time.sleep(2)
        self.screenshot('08_scopes_panel')
        
        # PASSO 9: Buscar e adicionar escopos
        print('\n📌 PASSO 9: Adicionando escopos Gmail e Calendar')
        scopes = ['gmail.readonly', 'gmail.modify', 'calendar']
        for scope in scopes:
            try:
                # Filtrar
                filter_input = self.driver.find_element(By.XPATH, "//input[@placeholder='Filter' or @placeholder='Filtrar']")
                filter_input.clear()
                filter_input.send_keys(scope)
                time.sleep(1)
                # Marcar checkbox
                checkbox = self.driver.find_element(By.XPATH, f"//tr[contains(.,'{scope}')]//mat-checkbox")
                checkbox.click()
                print(f'   ✅ Escopo: {scope}')
            except Exception as e:
                print(f'   ⚠️ Escopo {scope}: {e}')
        self.screenshot('09_scopes_selected')
        
        # PASSO 10: Update e continuar
        print('\n📌 PASSO 10: Atualizando escopos')
        self.wait_and_click([
            "//button[contains(.,'Update')]",
            "//button[contains(.,'Atualizar')]",
        ], 'update_scopes')
        time.sleep(2)
        self.wait_and_click([
            "//button[contains(.,'Save and Continue')]",
            "//button[contains(.,'Salvar e continuar')]",
        ], 'save_continue_2')
        time.sleep(3)
        self.screenshot('10_test_users_page')
        
        # PASSO 11: Adicionar usuario de teste
        print('\n📌 PASSO 11: Adicionando usuario de teste')
        self.wait_and_click([
            "//button[contains(.,'Add users')]",
            "//button[contains(.,'Adicionar usuarios')]",
        ], 'add_users_button')
        time.sleep(2)
        self.screenshot('11_add_users_dialog')
        self.wait_and_type([
            "//input[@type='email']",
            "//textarea",
        ], email, 'test_user_email')
        self.wait_and_click([
            "//button[contains(.,'Add') and not(contains(.,'users'))]",
            "//button[contains(.,'Adicionar') and not(contains(.,'usuarios'))]",
        ], 'confirm_add_user')
        time.sleep(2)
        self.screenshot('12_user_added')
        
        # PASSO 12: Finalizar
        print('\n📌 PASSO 12: Salvando configuracao')
        self.wait_and_click([
            "//button[contains(.,'Save and Continue')]",
            "//button[contains(.,'Salvar e continuar')]",
        ], 'save_continue_3')
        time.sleep(3)
        self.screenshot('13_summary')
        
        # PASSO 13: Ir para credenciais
        print('\n📌 PASSO 13: Indo para Credenciais')
        self.driver.get('https://console.cloud.google.com/apis/credentials')
        time.sleep(3)
        self.screenshot('14_credentials_page')
        
        # PASSO 14: Criar credenciais
        print('\n📌 PASSO 14: Criando credenciais OAuth')
        self.wait_and_click([
            "//button[contains(.,'Create credentials')]",
            "//button[contains(.,'Criar credenciais')]",
        ], 'create_credentials')
        time.sleep(1)
        self.screenshot('15_credentials_menu')
        self.wait_and_click([
            "//button[contains(.,'OAuth client ID')]",
            "//span[contains(text(),'OAuth client ID')]",
        ], 'oauth_client_option')
        time.sleep(3)
        self.screenshot('16_oauth_form')
        
        # PASSO 15: Configurar cliente
        print('\n📌 PASSO 15: Configurando cliente OAuth')
        self.wait_and_click([
            "//mat-select[@formcontrolname='applicationType']",
            "//mat-select",
        ], 'app_type_dropdown')
        time.sleep(1)
        self.wait_and_click([
            "//mat-option[contains(.,'Desktop')]",
        ], 'desktop_option')
        self.wait_and_type([
            "//input[@formcontrolname='displayName']",
            "//input[@type='text']",
        ], 'Eddie Assistant Desktop', 'client_name')
        self.screenshot('17_client_configured')
        
        # PASSO 16: Criar
        print('\n📌 PASSO 16: Criando cliente')
        self.wait_and_click([
            "//button[contains(.,'Create') and @type='submit']",
            "//button[contains(.,'Criar')]",
        ], 'create_final')
        time.sleep(3)
        self.screenshot('18_credentials_created')
        
        print('\n' + '='*60)
        print('✅ NAVEGACAO COMPLETA!')
        print(f'📁 Screenshots salvos em: {SCREENSHOT_DIR}')
        print(f'📁 E em: C:\\temp\\oauth_visual')
        print('='*60)
        
        # Listar screenshots
        print('\n📸 Screenshots capturados:')
        for f in sorted(os.listdir(SCREENSHOT_DIR)):
            print(f'   - {f}')

def main():
    print('='*60)
    print('OAUTH VISUAL NAVIGATOR - SELENIUM')
    print('='*60)
    
    email = input('\n📧 Digite seu email Gmail: ').strip()
    if not email:
        email = 'user@gmail.com'
    
    navigator = VisualOAuthNavigator()
    
    try:
        navigator.connect_to_chrome()
        navigator.navigate_oauth_setup(email)
    except Exception as e:
        print(f'\n❌ Erro: {e}')
        import traceback
        traceback.print_exc()
    
    input('\n\nPressione ENTER para finalizar...')

if __name__ == '__main__':
    main()
