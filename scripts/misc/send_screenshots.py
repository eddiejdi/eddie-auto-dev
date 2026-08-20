#!/usr/bin/env python3
"""Enviar screenshots do Playwright para o Telegram"""
import glob
import os

import requests

from tools.secrets_loader import get_telegram_chat_id, get_telegram_token

TELEGRAM_TOKEN = get_telegram_token()
CHAT_ID = get_telegram_chat_id() or ""
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def send_photo(photo_path, caption):
    """Envia uma foto para o Telegram"""
    with open(photo_path, 'rb') as photo:
        response = requests.post(
            f"{BASE_URL}/sendPhoto",
            data={"chat_id": CHAT_ID, "caption": caption},
            files={"photo": photo}
        )
    return response.json()

def send_message(text):
    """Envia mensagem de texto para o Telegram"""
    response = requests.post(
        f"{BASE_URL}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text}
    )
    return response.json()

def send_all_screenshots(directory="/tmp", pattern="screenshot_*.png"):
    """Envia todos os screenshots do diretório para o Telegram"""
    
    screenshots = glob.glob(os.path.join(directory, pattern))
    
    if not screenshots:
        print(f"❌ Nenhum screenshot encontrado em {directory}/{pattern}")
        return 0
    
    print(f"📸 Encontrados {len(screenshots)} screenshots\n")
    
    sent = 0
    for screenshot_path in sorted(screenshots):
        filename = os.path.basename(screenshot_path)
        caption = f"📸 {filename.replace('screenshot_', '').replace('_', ' ').replace('.png', '').title()}"
        
        try:
            result = send_photo(screenshot_path, caption)
            if result.get("ok"):
                print(f"✅ Enviado: {filename}")
                sent += 1
            else:
                print(f"❌ Erro ao enviar {filename}: {result.get('description', 'Unknown error')}")
        
        except Exception as e:
            print(f"❌ Erro ao enviar {filename}: {e}")
    
    print(f"\n📤 Total: {sent}/{len(screenshots)} screenshots enviados!")
    return sent

def main():
    print("📸 Enviando screenshots para o Telegram...\n")
    
    # Enviar automaticamente todos os screenshots encontrados
    sent = send_all_screenshots()
    
    if sent > 0:
        print("\n✅ Screenshots enviados com sucesso!")
        send_message("📌 Evidências enviadas. Está esperado que os prints venham assim?")

if __name__ == "__main__":
    import sys
    
    # Aceita diretório e padrão como argumentos
    directory = sys.argv[1] if len(sys.argv) > 1 else "/tmp"
    pattern = sys.argv[2] if len(sys.argv) > 2 else "screenshot_*.png"
    
    sent = send_all_screenshots(directory, pattern)
    if sent > 0:
        send_message("📌 Evidências enviadas. Está esperado que os prints venham assim?")
