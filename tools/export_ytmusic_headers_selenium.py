#!/usr/bin/env python3
"""Captura headers de requisições do YouTube Music usando Selenium + selenium-wire.

O script abre um navegador Chromium (visível), pede para você fazer login
e navegar até 'Liked songs' (Curtidas). Depois captura requisições
direcionadas a music.youtube.com e salva os headers em JSON.

Instalação mínima:
  pip install selenium selenium-wire
  # Opção útil para gerenciar chromedriver automaticamente:
  pip install webdriver-manager

Uso:
  python tools/export_ytmusic_headers_selenium.py --output .cache/ytmusic_headers_selenium.json

Observações:
 - Mantenha o navegador aberto até que a captura seja concluída.
 - Você pode fornecer `--profile DIR` para usar um perfil Chrome existente
   (útil para manter sessão logada).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

try:
    from seleniumwire import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
except Exception as e:  # pragma: no cover - runtime environment
    print(
        "Dependência ausente: instale com 'pip install selenium selenium-wire' (opcional: webdriver-manager).",
        file=sys.stderr,
    )
    raise


def capture_requests(driver: webdriver.Chrome, timeout: int, patterns: List[str]) -> List[Dict[str, Any]]:
    driver.requests.clear()
    start = time.time()
    captured: List[Dict[str, Any]] = []
    seen: set[str] = set()
    while time.time() - start < timeout:
        for req in driver.requests:
            try:
                url = req.url
                if not url:
                    continue
                if any(p in url for p in patterns):
                    key = url + (req.method or "")
                    if key in seen:
                        continue
                    seen.add(key)
                    hdrs = dict(req.headers)
                    captured.append({"url": url, "method": req.method, "headers": hdrs})
                    print("Captured:", url)
            except Exception:
                # Ignore malformed request objects or other per-request errors
                continue
        if captured:
            # wait a bit more to collect additional related requests
            time.sleep(1)
            break
        time.sleep(0.5)
    return captured


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capturar headers do YouTube Music usando Selenium + selenium-wire")
    parser.add_argument("--output", type=str, default=".cache/ytmusic_headers_selenium.json")
    parser.add_argument("--timeout", type=int, default=180, help="Timeout em segundos para capturar headers")
    parser.add_argument("--profile", type=str, default=None, help="Caminho para Chrome user-data-dir (opcional)")
    parser.add_argument("--headless", action="store_true", help="Executar em modo headless (não recomendado para login)")
    args = parser.parse_args(argv)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    chrome_options = Options()
    if args.headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    if args.profile:
        chrome_options.add_argument(f"--user-data-dir={args.profile}")

    # Inicializa webdriver (assume chromedriver no PATH)
        # Tenta instanciar o ChromeDriver diretamente; se falhar, tenta usar webdriver-manager
        try:
            driver = webdriver.Chrome(options=chrome_options)
        except Exception:
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                # usar Service para fornecer o binário do chromedriver recém-baixado
                driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
            except Exception:
                print(
                    "Falha ao iniciar Chrome webdriver. Instale 'webdriver-manager' e verifique o chromedriver.",
                    file=sys.stderr,
                )
                raise

    try:
        print("Abrindo https://music.youtube.com — faça login se necessário.")
        driver.get("https://music.youtube.com/library/songs")

        print("Quando estiver logado e com a página 'Liked songs' aberta, pressione Enter para iniciar captura (ou aguarde autom.)")
        try:
            input("Pressione Enter para começar a capturar (ou Ctrl+C para cancelar)...\n")
        except KeyboardInterrupt:
            print("Cancelado pelo usuário.")
            driver.quit()
            return 2

        patterns = ["music.youtube.com", "/youtubei/", "/browse", "/next"]
        print(f"Capturando requisições por até {args.timeout} segundos...")
        captured = capture_requests(driver, args.timeout, patterns)

        if not captured:
            print("Nenhuma requisição relevante capturada. Tente rolar a página 'Liked songs' para forçar chamadas da API.")
            driver.quit()
            return 3

        with out_path.open("w", encoding="utf-8") as fh:
            json.dump({"captured_at": time.time(), "requests": captured}, fh, ensure_ascii=False, indent=2)

        print(f"Headers salvos em: {out_path} (total {len(captured)} requisições)")
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
