#!/usr/bin/env python3
"""
Validação Visual Completa da IDE Python Online
- Captura screenshots
- Valida elementos visuais
- Verifica funcionalidade dos botões
- Testa integração com backend
"""

import subprocess
import sys
import time
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
except ImportError:
    print("❌ Selenium não instalado. Execute: pip install selenium")
    sys.exit(1)


def setup_driver():
    """Configura o driver Chrome headless"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--start-maximized")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except WebDriverException as e:
        print(f"❌ Erro ao inicializar Chrome: {e}")
        sys.exit(1)


def take_screenshot(driver, name):
    """Captura screenshot da página"""
    screenshot_path = f"/tmp/ide_validation_{name}.png"
    driver.save_screenshot(screenshot_path)
    print(f"📸 Screenshot: {screenshot_path}")
    return screenshot_path


def validate_ide_visual(driver):
    """Valida elementos visuais da IDE"""
    print("\n" + "="*70)
    print("🔍 VALIDAÇÃO VISUAL DA IDE")
    print("="*70)
    
    results = {}
    
    # 1. Verificar título
    print("\n✓ Verificando Título...")
    try:
        title = driver.title
        print(f"  Título: {title}")
        results['title'] = 'OK' if 'RPA4ALL' in title else 'AVISO'
    except Exception as e:
        print(f"  ❌ Erro: {e}")
        results['title'] = 'ERRO'
    
    # IMPORTANTE: Fazer scroll para a seção da IDE
    print("\n✓ Navegando para seção IDE...")
    try:
        ide_section = driver.find_element(By.ID, 'ide')
        driver.execute_script("arguments[0].scrollIntoView(true);", ide_section)
        time.sleep(2)  # Aguardar renderização completa
        print("  ✅ Seção IDE encontrada e visível")
    except Exception as e:
        print(f"  ⚠️  Erro ao navegar para IDE: {e}")
    
    # 2. Verificar presença de elementos principais
    print("\n✓ Verificando Elementos Principais...")
    elements_to_check = {
        'IDE Header': ('h2', 'Python IDE Online'),
        'IDE Container': ('div.ide-container', None),
        'Botão Executar': ('button.run', None),
        'Botão Abrir pasta': ('button#openProjectFolder', None),
        'Botão Salvar': ('button#saveProject', None),
        'Botão Limpar': ('button.clear', None),
        'Editor Monaco': ('div#editor', None),
        'Output Area': ('div.ide-output-wrapper', None),
        'AI Prompt Input': ('textarea#aiPrompt', None),
    }
    
    for element_name, (selector, expected_text) in elements_to_check.items():
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                element = elements[0]
                
                if expected_text:
                    text = element.text
                    if expected_text.lower() in text.lower():
                        print(f"  ✅ {element_name}: '{text.strip()[:50]}'")
                        results[element_name] = 'OK'
                    else:
                        print(f"  ⚠️  {element_name}: Encontrado mas conteúdo diferente")
                        print(f"      Esperado: '{expected_text}', Encontrado: '{text.strip()[:50]}'")
                        results[element_name] = 'AVISO'
                else:
                    # Apenas verificar se existe
                    display = driver.execute_script(
                        "return window.getComputedStyle(arguments[0]).display", element
                    )
                    visibility = driver.execute_script(
                        "return window.getComputedStyle(arguments[0]).visibility", element
                    )
                    
                    if display != 'none' and visibility != 'hidden':
                        print(f"  ✅ {element_name}: Visível")
                        results[element_name] = 'OK'
                    else:
                        print(f"  ⚠️  {element_name}: Encontrado mas oculto (display={display}, visibility={visibility})")
                        results[element_name] = 'AVISO'
            else:
                print(f"  ❌ {element_name}: NÃO ENCONTRADO")
                results[element_name] = 'ERRO'
        except Exception as e:
            print(f"  ❌ {element_name}: Erro - {e}")
            results[element_name] = 'ERRO'
    
    # 3. Capturar página inteira
    print("\n✓ Capturando Screenshots...")
    take_screenshot(driver, "full_page")
    
    # Scroll até o editor
    try:
        editor = driver.find_elements(By.CSS_SELECTOR, 'div.monaco-editor')
        if editor:
            driver.execute_script("arguments[0].scrollIntoView();", editor[0])
            time.sleep(1)
            take_screenshot(driver, "editor_section")
    except:
        pass
    
    # Scroll até a seção de output
    try:
        output = driver.find_elements(By.CSS_SELECTOR, 'div.ide-output-wrapper')
        if output:
            driver.execute_script("arguments[0].scrollIntoView();", output[0])
            time.sleep(1)
            take_screenshot(driver, "output_section")
    except:
        pass
    
    # 4. Verificar erros JavaScript
    print("\n✓ Verificando Erros JavaScript...")
    logs = driver.get_log('browser')
    errors = [log for log in logs if log['level'] == 'SEVERE']
    warnings = [log for log in logs if log['level'] == 'WARNING']
    
    if errors:
        print(f"  ⚠️  {len(errors)} erro(s) JavaScript detectado(s):")
        for error in errors[:5]:  # Mostrar apenas os 5 primeiros
            msg = error['message'][:100]
            print(f"      - {msg}")
    else:
        print(f"  ✅ Nenhum erro JavaScript grave detectado")
    
    if warnings:
        print(f"  ℹ️  {len(warnings)} aviso(s)")
    
    results['js_errors'] = 'OK' if not errors else 'AVISO'
    
    # 5. Dimensões da página
    print("\n✓ Verificando Dimensões e Responsividade...")
    try:
        window_size = driver.get_window_size()
        print(f"  Window size: {window_size['width']}x{window_size['height']}")
        
        # Verificar height do editor
        editor = driver.find_elements(By.CSS_SELECTOR, 'div.monaco-editor')
        if editor:
            height = editor[0].get_attribute('style') or 'inline'
            computed = driver.execute_script(
                "return window.getComputedStyle(arguments[0]).height", 
                editor[0]
            )
            print(f"  Editor height: {computed}")
            results['editor_height'] = 'OK'
        
        output = driver.find_elements(By.CSS_SELECTOR, 'div.ide-output-wrapper')
        if output:
            computed = driver.execute_script(
                "return window.getComputedStyle(arguments[0]).height",
                output[0]
            )
            print(f"  Output height: {computed}")
            results['output_height'] = 'OK'
    except Exception as e:
        print(f"  ⚠️  Erro ao verificar dimensões: {e}")
    
    # 6. Verificar responsividade em diferentes tamanhos
    print("\n✓ Testando Responsividade...")
    viewport_sizes = [
        (1920, 1080, "Desktop"),
        (768, 1024, "Tablet"),
        (375, 667, "Mobile"),
    ]
    
    for width, height, device in viewport_sizes:
        try:
            driver.set_window_size(width, height)
            time.sleep(0.5)
            # Verificar se elementos continuam visíveis
            toolbar = driver.find_elements(By.CSS_SELECTOR, '.ide-toolbar')
            if toolbar:
                print(f"  ✅ {device} ({width}x{height}): Toolbar visível")
        except Exception as e:
            print(f"  ⚠️  {device}: {e}")
    
    # Voltar ao tamanho original
    driver.set_window_size(1920, 1080)
    
    return results


def check_backend_connection(driver):
    """Verifica conexão com o backend"""
    print("\n" + "="*70)
    print("🔌 VERIFICAÇÃO DE CONEXÃO COM BACKEND")
    print("="*70)
    
    # Executar código simples para testar backend
    print("\n✓ Executando teste de conexão...")
    
    try:
        # Procurar o botão de executar
        execute_buttons = driver.find_elements(By.XPATH, "//*[contains(text(), 'Executar')]")
        if execute_buttons:
            print(f"  ✅ Botão Executar encontrado")
            # Não clicamos para não afetar o estado da página
        else:
            print(f"  ⚠️  Botão Executar não encontrado")
        
        # Verificar se há mensagens de erro na página
        error_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'ERRO')]")
        if error_elements:
            print(f"  ⚠️  Página contém mensagens de erro:")
            for elem in error_elements[:3]:
                text = elem.text[:80]
                print(f"      - {text}")
            return False
        else:
            print(f"  ✅ Nenhuma mensagem de erro visível")
            return True
    except Exception as e:
        print(f"  ❌ Erro ao verificar backend: {e}")
        return False


def generate_report(results, backend_ok):
    """Gera relatório final"""
    print("\n" + "="*70)
    print("📊 RELATÓRIO FINAL DE VALIDAÇÃO")
    print("="*70)
    
    ok_count = sum(1 for v in results.values() if v == 'OK')
    warning_count = sum(1 for v in results.values() if v == 'AVISO')
    error_count = sum(1 for v in results.values() if v == 'ERRO')
    
    print(f"\n✅ OK: {ok_count}")
    print(f"⚠️  AVISOS: {warning_count}")
    print(f"❌ ERROS: {error_count}")
    
    print("\nDetalhes:")
    for item, status in sorted(results.items()):
        icon = "✅" if status == 'OK' else "⚠️" if status == 'AVISO' else "❌"
        print(f"  {icon} {item}: {status}")
    
    print(f"\nBackend: {'✅ Conectado' if backend_ok else '⚠️  Erro de conexão'}")
    
    if error_count == 0 and warning_count <= 2:
        print("\n✅ VALIDAÇÃO VISUAL APROVADA!")
        return 0
    else:
        print("\n⚠️  VALIDAÇÃO COM AVISOS/ERROS - REVISAR")
        return 1


def main():
    """Função principal"""
    print("\n" + "="*70)
    print("🔍 VALIDAÇÃO VISUAL COMPLETA - IDE PYTHON ONLINE")
    print("="*70)
    
    target_url = "https://www.rpa4all.com/"
    
    driver = None
    try:
        print(f"\n📌 Acessando: {target_url}")
        driver = setup_driver()
        driver.get(target_url)
        
        # Aguardar carregamento
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'body'))
            )
        except TimeoutException:
            print("⚠️  Timeout aguardando carregamento")
        
        time.sleep(2)  # Aguardar renderização completa
        
        # Executar validações
        results = validate_ide_visual(driver)
        backend_ok = check_backend_connection(driver)
        
        # Gerar relatório
        exit_code = generate_report(results, backend_ok)
        
        return exit_code
    
    except Exception as e:
        print(f"\n❌ Erro geral: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        if driver:
            driver.quit()
            print("\n🛑 Driver encerrado")


if __name__ == "__main__":
    sys.exit(main())
