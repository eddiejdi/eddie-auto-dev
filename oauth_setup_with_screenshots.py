#!/usr/bin/env python3
"""
Script Selenium para configurar OAuth com captura de cada passo
Executa no Windows usando Chrome com perfil logado
"""

import os

# Diretorio para screenshots
SCREENSHOT_DIR = "/home/homelab/myClaude/screenshots/oauth_setup"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def run_selenium_windows():
    """Executa Selenium no Windows via PowerShell"""

    # Script Python para Windows
    windows_script = r"""
import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime

class OAuthSetupCapture:
    def __init__(self):
        self.options = Options()
        # Usar perfil Chrome existente (onde usuario ja esta logado)
        user_data = os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\User Data')
        # Usar diretorio temporario para evitar conflito com Chrome aberto
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--window-size=1920,1080')
        self.options.add_argument('--disable-blink-features=AutomationControlled')
        self.options.add_experimental_option('excludeSwitches', ['enable-automation'])
        self.driver = None
        self.screenshot_dir = r'C:\screenshots_oauth'
        os.makedirs(self.screenshot_dir, exist_ok=True)
        self.step = 0
        
    def start(self):
        print('Iniciando Chrome...')
        self.driver = webdriver.Chrome(options=self.options)
        self.driver.implicitly_wait(10)
        print('Chrome iniciado!')
        
    def close(self):
        if self.driver:
            self.driver.quit()
    
    def screenshot(self, name):
        self.step += 1
        filename = f'{self.screenshot_dir}\\step_{self.step:02d}_{name}.png'
        self.driver.save_screenshot(filename)
        print(f'[SCREENSHOT {self.step}] {filename}')
        return filename
    
    def wait_for_page(self, timeout=10):
        time.sleep(3)
        
    def run_setup(self):
        print('='*60)
        print('OAUTH SETUP - CAPTURA DE TELA DE CADA PASSO')
        print('='*60)
        
        # Passo 1: Ir para tela de consentimento
        print('\n[PASSO 1] Navegando para tela de consentimento OAuth...')
        self.driver.get('https://console.cloud.google.com/apis/credentials/consent')
        self.wait_for_page()
        self.screenshot('consent_screen_initial')
        
        # Verificar se precisa login
        if 'accounts.google.com' in self.driver.current_url:
            print('\n*** ATENCAO: Faca login no Google ***')
            print('Aguardando login... (60 segundos)')
            time.sleep(60)
            self.screenshot('after_login')
        
        # Passo 2: Selecionar tipo externo
        print('\n[PASSO 2] Procurando opcao External/Externo...')
        self.screenshot('user_type_selection')
        
        try:
            # Tentar clicar em External
            for xpath in [
                "//mat-radio-button[contains(.,'External')]",
                "//mat-radio-button[contains(.,'Externo')]",
                "//div[contains(text(),'External')]",
                "//div[contains(text(),'Externo')]"
            ]:
                try:
                    elem = self.driver.find_element(By.XPATH, xpath)
                    elem.click()
                    print('Opcao External selecionada!')
                    break
                except:
                    continue
            
            self.screenshot('external_selected')
            time.sleep(1)
            
            # Clicar em Create/Criar
            for xpath in [
                "//button[contains(.,'Create')]",
                "//button[contains(.,'Criar')]",
                "//span[text()='Create']/parent::button",
                "//span[text()='Criar']/parent::button"
            ]:
                try:
                    btn = self.driver.find_element(By.XPATH, xpath)
                    btn.click()
                    print('Botao Create clicado!')
                    break
                except:
                    continue
                    
            self.wait_for_page()
            self.screenshot('after_create')
            
        except Exception as e:
            print(f'Erro no passo 2: {e}')
            self.screenshot('error_step2')
        
        # Passo 3: Preencher informacoes do app
        print('\n[PASSO 3] Preenchendo informacoes do app...')
        self.screenshot('app_info_form')
        
        try:
            # Nome do app
            inputs = self.driver.find_elements(By.TAG_NAME, 'input')
            for inp in inputs:
                formcontrol = inp.get_attribute('formcontrolname') or ''
                if 'displayName' in formcontrol or 'name' in formcontrol.lower():
                    inp.clear()
                    inp.send_keys('Eddie Assistant')
                    print('Nome do app preenchido: Eddie Assistant')
                    break
            
            self.screenshot('app_name_filled')
            
            # Email de suporte (dropdown)
            selects = self.driver.find_elements(By.TAG_NAME, 'mat-select')
            for sel in selects:
                try:
                    sel.click()
                    time.sleep(1)
                    self.screenshot('email_dropdown_open')
                    # Selecionar primeira opcao
                    option = self.driver.find_element(By.CSS_SELECTOR, 'mat-option')
                    option.click()
                    print('Email de suporte selecionado')
                    break
                except:
                    continue
            
            self.screenshot('support_email_selected')
            
            # Scroll para baixo
            self.driver.execute_script('window.scrollTo(0, document.body.scrollHeight)')
            time.sleep(1)
            self.screenshot('scrolled_down')
            
            # Email do desenvolvedor
            for elem in self.driver.find_elements(By.TAG_NAME, 'textarea'):
                try:
                    elem.send_keys('eddie@example.com')
                    print('Email do desenvolvedor preenchido')
                    break
                except:
                    continue
            
            self.screenshot('developer_email_filled')
            
        except Exception as e:
            print(f'Erro no passo 3: {e}')
            self.screenshot('error_step3')
        
        # Passo 4: Salvar e continuar
        print('\n[PASSO 4] Clicando em Salvar e Continuar...')
        try:
            for xpath in [
                "//button[contains(.,'Save and Continue')]",
                "//button[contains(.,'Salvar e continuar')]",
                "//span[contains(text(),'Save and Continue')]/parent::button"
            ]:
                try:
                    btn = self.driver.find_element(By.XPATH, xpath)
                    btn.click()
                    print('Salvar e Continuar clicado!')
                    break
                except:
                    continue
            
            self.wait_for_page()
            self.screenshot('scopes_page')
            
        except Exception as e:
            print(f'Erro no passo 4: {e}')
            self.screenshot('error_step4')
        
        # Passo 5: Adicionar escopos
        print('\n[PASSO 5] Adicionando escopos...')
        try:
            for xpath in [
                "//button[contains(.,'Add or remove scopes')]",
                "//button[contains(.,'Adicionar ou remover escopos')]"
            ]:
                try:
                    btn = self.driver.find_element(By.XPATH, xpath)
                    btn.click()
                    print('Painel de escopos aberto!')
                    break
                except:
                    continue
            
            time.sleep(2)
            self.screenshot('scopes_panel')
            
            # Adicionar escopos
            scopes_to_add = ['gmail.readonly', 'gmail.modify', 'calendar']
            for scope in scopes_to_add:
                try:
                    # Usar filtro
                    filter_input = self.driver.find_element(By.XPATH, "//input[@placeholder='Filter']")
                    filter_input.clear()
                    filter_input.send_keys(scope)
                    time.sleep(1)
                    
                    # Marcar checkbox
                    checkbox = self.driver.find_element(By.XPATH, f"//tr[contains(.,'{scope}')]//mat-checkbox")
                    if 'checked' not in checkbox.get_attribute('class'):
                        checkbox.click()
                    print(f'Escopo adicionado: {scope}')
                except:
                    pass
            
            self.screenshot('scopes_selected')
            
            # Clicar Update
            for xpath in ["//button[contains(.,'Update')]", "//button[contains(.,'Atualizar')]"]:
                try:
                    btn = self.driver.find_element(By.XPATH, xpath)
                    btn.click()
                    break
                except:
                    continue
            
            time.sleep(2)
            self.screenshot('scopes_updated')
            
            # Salvar e continuar
            for xpath in [
                "//button[contains(.,'Save and Continue')]",
                "//button[contains(.,'Salvar e continuar')]"
            ]:
                try:
                    btn = self.driver.find_element(By.XPATH, xpath)
                    btn.click()
                    break
                except:
                    continue
            
            self.wait_for_page()
            self.screenshot('test_users_page')
            
        except Exception as e:
            print(f'Erro no passo 5: {e}')
            self.screenshot('error_step5')
        
        # Passo 6: Adicionar usuarios de teste
        print('\n[PASSO 6] Adicionando usuarios de teste...')
        try:
            for xpath in [
                "//button[contains(.,'Add users')]",
                "//button[contains(.,'Adicionar usuarios')]"
            ]:
                try:
                    btn = self.driver.find_element(By.XPATH, xpath)
                    btn.click()
                    break
                except:
                    continue
            
            time.sleep(2)
            self.screenshot('add_users_dialog')
            
            # Digitar email
            for elem in self.driver.find_elements(By.XPATH, "//input[@type='email'] | //textarea"):
                try:
                    elem.send_keys('eddie@example.com')
                    break
                except:
                    continue
            
            self.screenshot('user_email_entered')
            
            # Confirmar
            for xpath in ["//button[contains(.,'Add')]", "//button[contains(.,'Adicionar')]"]:
                try:
                    buttons = self.driver.find_elements(By.XPATH, xpath)
                    for btn in buttons:
                        if btn.is_displayed():
                            btn.click()
                            break
                    break
                except:
                    continue
            
            time.sleep(2)
            self.screenshot('users_added')
            
            # Salvar e continuar
            for xpath in [
                "//button[contains(.,'Save and Continue')]",
                "//button[contains(.,'Salvar e continuar')]"
            ]:
                try:
                    btn = self.driver.find_element(By.XPATH, xpath)
                    btn.click()
                    break
                except:
                    continue
            
            self.wait_for_page()
            self.screenshot('summary_page')
            
        except Exception as e:
            print(f'Erro no passo 6: {e}')
            self.screenshot('error_step6')
        
        # Passo 7: Criar credenciais
        print('\n[PASSO 7] Criando credenciais OAuth...')
        try:
            self.driver.get('https://console.cloud.google.com/apis/credentials')
            self.wait_for_page()
            self.screenshot('credentials_page')
            
            # Clicar Create Credentials
            for xpath in [
                "//button[contains(.,'Create credentials')]",
                "//button[contains(.,'Criar credenciais')]"
            ]:
                try:
                    btn = self.driver.find_element(By.XPATH, xpath)
                    btn.click()
                    break
                except:
                    continue
            
            time.sleep(1)
            self.screenshot('credentials_menu')
            
            # Selecionar OAuth client ID
            for xpath in [
                "//button[contains(.,'OAuth client ID')]",
                "//span[contains(text(),'OAuth client ID')]"
            ]:
                try:
                    elem = self.driver.find_element(By.XPATH, xpath)
                    elem.click()
                    break
                except:
                    continue
            
            self.wait_for_page()
            self.screenshot('oauth_client_form')
            
            # Selecionar tipo Desktop
            selects = self.driver.find_elements(By.TAG_NAME, 'mat-select')
            for sel in selects:
                try:
                    sel.click()
                    time.sleep(1)
                    option = self.driver.find_element(By.XPATH, "//mat-option[contains(.,'Desktop')]")
                    option.click()
                    break
                except:
                    continue
            
            self.screenshot('desktop_selected')
            
            # Nome do cliente
            for inp in self.driver.find_elements(By.TAG_NAME, 'input'):
                formcontrol = inp.get_attribute('formcontrolname') or ''
                if 'displayName' in formcontrol or 'name' in formcontrol.lower():
                    inp.clear()
                    inp.send_keys('Eddie Assistant Desktop')
                    break
            
            self.screenshot('client_name_filled')
            
            # Criar
            for xpath in ["//button[contains(.,'Create')]", "//button[contains(.,'Criar')]"]:
                try:
                    buttons = self.driver.find_elements(By.XPATH, xpath)
                    for btn in buttons:
                        if btn.is_enabled():
                            btn.click()
                            break
                    break
                except:
                    continue
            
            self.wait_for_page()
            self.screenshot('credentials_created')
            
        except Exception as e:
            print(f'Erro no passo 7: {e}')
            self.screenshot('error_step7')
        
        print('\n' + '='*60)
        print('CAPTURA CONCLUIDA!')
        print(f'Screenshots salvos em: {self.screenshot_dir}')
        print('='*60)

def main():
    setup = OAuthSetupCapture()
    setup.start()
    try:
        setup.run_setup()
    finally:
        input('\nPressione ENTER para fechar o navegador...')
        setup.close()

if __name__ == '__main__':
    main()
"""

    # Salvar script temporario
    with open("C:/temp_oauth_setup.py", "w") as f:
        f.write(windows_script)

    print("Executando no Windows...")


if __name__ == "__main__":
    print("Este script deve ser executado no Windows.")
    print("Use: python oauth_setup_with_screenshots.py")
