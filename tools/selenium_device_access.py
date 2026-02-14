#!/usr/bin/env python3
"""Selenium helper para Device Access Console.

Fluxo:
- Abre https://console.nest.google.com/device-access
- Aguarda você fazer login e selecionar o projeto
- Após Enter, captura screenshot(s) e tenta extrair IDs visíveis

Uso:
  pip install selenium webdriver-manager
  python3 tools/selenium_device_access.py

Observação: o script é interativo — você precisará autenticar manualmente no navegador.
"""
import re
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


def main():
    url = "https://console.nest.google.com/device-access/"
    print("Iniciando Chrome (webdriver-manager)...")
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    # interactive mode (do not run headless)
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
    try:
        driver.get(url)
        print("Navegador aberto em:", url)
        print("Faça login na sua conta Google e navegue até o projeto Device Access desejado.")
        input("Quando estiver na página do projeto (visível), pressione Enter aqui para continuar...\n")

        time.sleep(1)
        out_dir = Path("./tmp_selenium_device_access")
        out_dir.mkdir(parents=True, exist_ok=True)
        ss_path = out_dir / "device_access_full.png"
        driver.save_screenshot(str(ss_path))
        print(f"Screenshot salva em: {ss_path}")

        # tentar heurísticas para encontrar IDs na página
        texts = set()
        # procurar por elementos com texto contendo 'home-lab' ou 'projects/' ou apenas números longos
        candidates = driver.find_elements(By.XPATH, "//*[contains(text(),'home-lab') or contains(text(),'projects/') or contains(text(),'home_lab')]")
        for el in candidates:
            t = el.text.strip()
            if t:
                texts.add(t)

        # procurar por longos números (project numbers)
        body = driver.find_element(By.TAG_NAME, "body").text
        for m in re.findall(r"\b\d{6,15}\b", body):
            texts.add(m)

        print("Possíveis IDs/extratos encontrados:")
        for t in sorted(texts):
            print("- ", repr(t))

        print("Se o ID correto não aparecer, abra a página do projeto e copie o 'Project ID' mostrado na UI, então cole aqui.")
        manual = input("Cole o ID aqui (ou deixe vazio para sair): ").strip()
        if manual:
            print("Você informou:", manual)
        else:
            print("Nenhum ID informado — finalizei.")

    finally:
        print("Fechando navegador em 3s...")
        time.sleep(3)
        driver.quit()


if __name__ == '__main__':
    main()
