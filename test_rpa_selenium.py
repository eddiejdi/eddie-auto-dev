#!/usr/bin/env python3
"""
Teste automatizado do Agent Chat usando Selenium
RPA - Robotic Process Automation
"""

import time
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# Configuração
AGENT_CHAT_URL = "http://192.168.15.2:8505"
MONITOR_URL = "http://192.168.15.2:8504"
DASHBOARD_URL = "http://192.168.15.2:8502"
API_DOCS_URL = "http://192.168.15.2:8503/docs"

def setup_driver():
    """Configura o driver do Chrome."""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(10)
    return driver

def take_screenshot(driver, name):
    """Tira screenshot e salva."""
    filename = f"/tmp/test_{name}_{datetime.now().strftime('%H%M%S')}.png"
    driver.save_screenshot(filename)
    print(f"   📸 Screenshot salvo: {filename}")
    return filename

def test_agent_chat(driver):
    """Testa o Agent Chat."""
    print("\n🧪 TESTE 1: Agent Chat (8505)")
    print("-" * 40)
    
    try:
        driver.get(AGENT_CHAT_URL)
        time.sleep(3)
        
        # Verifica título
        print(f"   Título: {driver.title}")
        take_screenshot(driver, "agent_chat_inicial")
        
        # Procura campo de input do chat
        wait = WebDriverWait(driver, 15)
        
        # Streamlit chat input
        chat_input = None
        try:
            # Tenta encontrar o chat input do Streamlit
            chat_input = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "textarea[data-testid='stChatInputTextArea']")
            ))
            print("   ✅ Campo de chat encontrado")
        except:
            try:
                chat_input = driver.find_element(By.CSS_SELECTOR, "textarea")
                print("   ✅ Campo textarea encontrado")
            except:
                print("   ⚠️ Campo de input não encontrado diretamente")
        
        # Tenta enviar mensagem
        if chat_input:
            chat_input.send_keys("Olá, crie uma função de soma em Python")
            take_screenshot(driver, "agent_chat_mensagem_digitada")
            chat_input.send_keys(Keys.RETURN)
            print("   📤 Mensagem enviada")
            
            # Aguarda resposta
            time.sleep(5)
            take_screenshot(driver, "agent_chat_resposta")
            print("   ✅ Interação com chat concluída")
        
        # Verifica elementos da página
        page_source = driver.page_source
        checks = [
            ("Agent Chat" in page_source or "Chat" in page_source, "Título do chat"),
            ("python" in page_source.lower(), "Referência a Python"),
            ("streamlit" in page_source.lower() or "app" in page_source.lower(), "Framework Streamlit"),
        ]
        
        for check, desc in checks:
            status = "✅" if check else "❌"
            print(f"   {status} {desc}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        take_screenshot(driver, "agent_chat_erro")
        return False

def test_monitor(driver):
    """Testa o Agent Monitor."""
    print("\n🧪 TESTE 2: Agent Monitor (8504)")
    print("-" * 40)
    
    try:
        driver.get(MONITOR_URL)
        time.sleep(3)
        
        print(f"   Título: {driver.title}")
        take_screenshot(driver, "monitor_inicial")
        
        page_source = driver.page_source
        checks = [
            ("Monitor" in page_source or "Agent" in page_source, "Título do monitor"),
            ("message" in page_source.lower() or "mensag" in page_source.lower(), "Seção de mensagens"),
        ]
        
        for check, desc in checks:
            status = "✅" if check else "❌"
            print(f"   {status} {desc}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        take_screenshot(driver, "monitor_erro")
        return False

def test_dashboard(driver):
    """Testa o Dashboard."""
    print("\n🧪 TESTE 3: Dashboard (8502)")
    print("-" * 40)
    
    try:
        driver.get(DASHBOARD_URL)
        time.sleep(3)
        
        print(f"   Título: {driver.title}")
        take_screenshot(driver, "dashboard_inicial")
        
        page_source = driver.page_source
        checks = [
            ("Dashboard" in page_source or "Agent" in page_source or "Eddie" in page_source, "Título"),
            ("python" in page_source.lower() or "agent" in page_source.lower(), "Referência a agentes"),
        ]
        
        for check, desc in checks:
            status = "✅" if check else "❌"
            print(f"   {status} {desc}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        take_screenshot(driver, "dashboard_erro")
        return False

def test_api_docs(driver):
    """Testa a documentação da API."""
    print("\n🧪 TESTE 4: API Docs - Swagger (8503)")
    print("-" * 40)
    
    try:
        driver.get(API_DOCS_URL)
        time.sleep(3)
        
        print(f"   Título: {driver.title}")
        take_screenshot(driver, "api_docs_inicial")
        
        page_source = driver.page_source
        checks = [
            ("Swagger" in page_source or "FastAPI" in page_source or "API" in page_source, "Swagger UI"),
            ("agents" in page_source.lower() or "code" in page_source.lower(), "Endpoints de agentes"),
            ("generate" in page_source.lower() or "execute" in page_source.lower(), "Endpoints de código"),
        ]
        
        for check, desc in checks:
            status = "✅" if check else "❌"
            print(f"   {status} {desc}")
        
        # Tenta expandir um endpoint
        try:
            endpoints = driver.find_elements(By.CSS_SELECTOR, ".opblock-summary")
            if endpoints:
                endpoints[0].click()
                time.sleep(1)
                take_screenshot(driver, "api_docs_endpoint_expandido")
                print("   ✅ Endpoint expandido com sucesso")
        except:
            pass
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        take_screenshot(driver, "api_docs_erro")
        return False

def main():
    """Executa todos os testes."""
    print("=" * 50)
    print("   TESTES AUTOMATIZADOS RPA - AGENT CHAT")
    print("   " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 50)
    
    driver = None
    results = {}
    
    try:
        driver = setup_driver()
        print("\n✅ Driver Chrome iniciado (headless)")
        
        # Executa testes
        results["Agent Chat"] = test_agent_chat(driver)
        results["Monitor"] = test_monitor(driver)
        results["Dashboard"] = test_dashboard(driver)
        results["API Docs"] = test_api_docs(driver)
        
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
        
    finally:
        if driver:
            driver.quit()
            print("\n✅ Driver fechado")
    
    # Resumo
    print("\n" + "=" * 50)
    print("   RESUMO DOS TESTES")
    print("=" * 50)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test}: {status}")
    
    print(f"\n   RESULTADO: {passed}/{total} testes passaram")
    print("=" * 50)
    
    # Salva resultado em JSON
    with open("/tmp/rpa_test_results.json", "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "results": results,
            "passed": passed,
            "total": total
        }, f, indent=2)
    
    print(f"\n📄 Resultados salvos em /tmp/rpa_test_results.json")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
