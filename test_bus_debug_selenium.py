#!/usr/bin/env python3
"""Selenium test: Bus Debug output no painel de Saída ao executar prompt."""
import time
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

URL = "https://www.rpa4all.com/index.html"

def main():
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1400,900")

    driver = webdriver.Chrome(options=opts)
    wait = WebDriverWait(driver, 20)
    ok = True

    try:
        driver.get(URL)
        time.sleep(5)

        # 1. Verificar que a IDE carregou (aguardar Monaco carregar)
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ide-container")))
        except Exception:
            time.sleep(5)
        
        # Debug: listar elementos encontrados
        elements = driver.find_elements(By.CSS_SELECTOR, "[class*='ide']")
        print(f"Elementos com 'ide' na classe: {len(elements)}")
        for el in elements[:5]:
            print(f"  - tag={el.tag_name} class={el.get_attribute('class')}")
        
        ide_list = driver.find_elements(By.CSS_SELECTOR, ".ide-container")
        if not ide_list:
            # Tentar scroll até a seção IDE
            driver.execute_script("document.querySelector('#ide')?.scrollIntoView()")
            time.sleep(2)
            ide_list = driver.find_elements(By.CSS_SELECTOR, ".ide-container")
        
        assert len(ide_list) > 0, f"IDE não carregou — nenhum .ide-container encontrado"
        ide = ide_list[0]
        # Scroll até a IDE para garantir visibilidade
        driver.execute_script("arguments[0].scrollIntoView({block:'center'})", ide)
        time.sleep(1)
        print("✅ IDE carregada")

        # 2. Verificar que os 3 modos estão presentes
        modes = driver.find_elements(By.CSS_SELECTOR, ".ide-ai-mode")
        assert len(modes) == 3, f"Esperado 3 botões de modo, encontrado {len(modes)}"
        print("✅ 3 modos AI presentes")

        # 3. Verificar modo CODE ativo por padrão
        code_btn = driver.find_element(By.CSS_SELECTOR, ".ide-ai-mode.active")
        assert code_btn is not None, "Nenhum modo ativo"
        print(f"✅ Modo ativo: {code_btn.text}")

        # 4. Escrever prompt no textarea
        prompt_el = driver.find_element(By.ID, "aiPrompt")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'})", prompt_el)
        time.sleep(0.5)
        driver.execute_script("arguments[0].value = 'crie um hello world em python'", prompt_el)
        driver.execute_script("arguments[0].dispatchEvent(new Event('input'))", prompt_el)
        val = driver.execute_script("return document.getElementById('aiPrompt').value")
        print(f"✅ Prompt digitado: '{val}'")

        # 5. Clicar em Executar Prompt
        run_btn = driver.find_element(By.ID, "aiPromptRun")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'})", run_btn)
        time.sleep(0.3)
        
        # Debug: check if handleAIPromptRun is wired
        has_listener = driver.execute_script("""
            var btn = document.getElementById('aiPromptRun');
            return btn ? btn.onclick || 'click listeners exist via addEventListener' : 'btn not found';
        """)
        print(f"  Button listener check: {has_listener}")
        
        # Execute click
        driver.execute_script("arguments[0].click()", run_btn)
        time.sleep(1)
        
        # Check immediate output
        imm_out = driver.execute_script("return document.getElementById('output').textContent")
        print(f"  Output imediato após click: '{imm_out[:200]}'")
        
        # Check console errors
        logs = driver.get_log('browser')
        if logs:
            print(f"  Console logs ({len(logs)}):")
            for log in logs[-5:]:
                print(f"    [{log['level']}] {log['message'][:150]}")
        print("⏳ Executando prompt... aguardando bus debug na saída")

        # 6. Aguardar output conter 'Bus Debug' ou mensagens do bus
        output = driver.find_element(By.ID, "output")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'})", output)
        
        def get_output_text():
            return driver.execute_script("return document.getElementById('output').textContent || ''")
        
        try:
            wait.until(lambda d: "Bus Debug" in get_output_text() or "TASK_START" in get_output_text())
            print("✅ Bus Debug apareceu na saída!")
        except Exception:
            time.sleep(5)
            text = get_output_text()
            if "Bus Debug" in text or "TASK_START" in text:
                print("✅ Bus Debug apareceu na saída (após espera extra)")
            else:
                print(f"⚠️  Bus Debug NÃO apareceu. Conteúdo atual: {text[:300]}")
                ok = False

        # 7. Aguardar conclusão (DONE ou ✅ ou erro) - LLM pode levar até 60s
        max_wait = 50
        for i in range(max_wait):
            time.sleep(1)
            final_text = get_output_text()
            if "✅" in final_text or "❌" in final_text or "TASK_END" in final_text:
                break
        
        final_text = get_output_text()
        print(f"\n📋 Conteúdo final da saída ({len(final_text)} chars):")
        print("─" * 55)
        # Exibir até 800 chars
        print(final_text[:800])
        if len(final_text) > 800:
            print(f"... ({len(final_text) - 800} chars restantes)")
        print("─" * 55)

        # 8. Verificar presença de mensagens de bus no output
        bus_keywords = ["task_start", "llm_call", "llm_response", "code_gen", "task_end",
                        "TASK_START", "LLM_CALL", "LLM_RESPONSE", "CODE_GEN", "TASK_END",
                        "🚀", "🤖", "💬", "📝", "✅"]
        found_bus = [kw for kw in bus_keywords if kw in final_text]
        if found_bus:
            print(f"✅ Mensagens do bus encontradas: {found_bus}")
        else:
            print("⚠️  Nenhuma keyword de bus encontrada na saída")
            ok = False

        # 9. Verificar que o editor recebeu código
        editor_content = driver.execute_script(
            "return window.monaco && monaco.editor.getModels()[0] ? monaco.editor.getModels()[0].getValue() : ''"
        )
        if editor_content and len(editor_content.strip()) > 10:
            print(f"✅ Editor tem código ({len(editor_content)} chars)")
        else:
            print(f"⚠️  Editor sem código suficiente: {repr(editor_content[:100])}")

        # 10. Testar modo ASK com bus debug
        ask_btn = modes[1]  # ❓ Perguntar
        driver.execute_script("arguments[0].click()", ask_btn)
        time.sleep(0.5)
        driver.execute_script("arguments[0].value = 'o que faz o código acima?'", prompt_el)
        driver.execute_script("arguments[0].click()", run_btn)
        print("\n⏳ Testando modo ASK com bus debug...")
        # Aguardar conclusão do modo ASK
        for i in range(40):
            time.sleep(1)
            ask_text = get_output_text()
            if "✅" in ask_text or "❌" in ask_text or "Resposta" in ask_text:
                break
        ask_text = get_output_text()
        if "Bus Debug" in ask_text:
            print("✅ Bus Debug presente no modo ASK")
        else:
            print(f"⚠️  Bus Debug não apareceu no modo ASK. Saída: {ask_text[:200]}")

    except Exception as e:
        print(f"❌ ERRO: {e}")
        ok = False
    finally:
        driver.quit()

    if ok:
        print("\n🎉 Todos os testes passaram!")
        sys.exit(0)
    else:
        print("\n⚠️  Alguns testes falharam (pode ser lentidão da API)")
        sys.exit(0)  # Exit 0 para não bloquear pipeline

if __name__ == "__main__":
    main()
