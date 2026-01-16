#!/usr/bin/env python3
"""Teste do navegador headless Playwright"""
import asyncio
import sys
import requests
sys.path.insert(0, '/home/homelab/.local/lib/python3.12/site-packages')

from playwright.async_api import async_playwright

TELEGRAM_TOKEN = "1105143633:AAEC1kmqDD_MDSpRFgEVHctwAfvfjVSp8B4"
CHAT_ID = "948686300"
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def send_screenshot_to_telegram(screenshot_path, caption):
    """Envia um screenshot para o Telegram"""
    try:
        with open(screenshot_path, 'rb') as photo:
            response = requests.post(
                f"{BASE_URL}/sendPhoto",
                data={"chat_id": CHAT_ID, "caption": caption},
                files={"photo": photo}
            )
        result = response.json()
        if result.get("ok"):
            return True
        return False
    except Exception as e:
        print(f"Erro ao enviar {screenshot_path}: {e}")
        return False

def send_message_to_telegram(text):
    """Envia mensagem de texto para o Telegram"""
    try:
        response = requests.post(
            f"{BASE_URL}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text}
        )
        result = response.json()
        return bool(result.get("ok"))
    except Exception as e:
        print(f"Erro ao enviar mensagem: {e}")
        return False

async def test_headless_browser():
    print("🌐 TESTE DO NAVEGADOR HEADLESS (Playwright + Chromium)\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        
        tests = [
            ("Dashboard", "http://localhost:8502"),
            ("API Docs", "http://localhost:8503/docs"),
            ("Monitor", "http://localhost:8504"),
            ("Agent Chat", "http://localhost:8505"),
        ]
        
        results = []
        
        for name, url in tests:
            try:
                response = await page.goto(url, timeout=20000, wait_until="domcontentloaded")
                try:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass
                await page.wait_for_timeout(3000)
                status = response.status if response else 0
                title = await page.title()
                
                # Screenshot
                screenshot_path = f"/tmp/screenshot_{name.lower().replace(' ', '_')}.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                
                # Enviar screenshot para o Telegram
                caption = f"📸 {name}\nStatus: {status}\nTitle: {title[:50]}"
                if send_screenshot_to_telegram(screenshot_path, caption):
                    telegram_status = "📤"
                else:
                    telegram_status = "⚠️"
                
                if status == 200:
                    results.append(f"✅ {name}: OK (status={status}, title='{title[:30]}') {telegram_status}")
                else:
                    results.append(f"⚠️ {name}: Status {status} {telegram_status}")
                    
            except Exception as e:
                results.append(f"❌ {name}: {str(e)[:50]}")
        
        await browser.close()
        
        print("\n".join(results))
        
        passed = sum(1 for r in results if r.startswith("✅"))
        print(f"\n📊 Resultado: {passed}/{len(tests)} testes passaram")
        
        if passed == len(tests):
            print("🎉 TODOS OS TESTES PASSARAM!")
        
        print("\n📸 Screenshots salvos em /tmp/screenshot_*.png")
        print("📤 Screenshots enviados para o Telegram!")

        send_message_to_telegram(
            "📌 Evidências enviadas. Está esperado que os prints venham assim?"
        )

if __name__ == "__main__":
    asyncio.run(test_headless_browser())
