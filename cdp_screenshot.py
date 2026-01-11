#!/usr/bin/env python3
"""
Script para capturar screenshots do Chrome usando CDP direto
Sem precisar de Selenium conectar remotamente
"""
import time
import os
import json
import base64
import urllib.request
import urllib.parse

SCREENSHOT_DIR = '/home/homelab/myClaude/screenshots/oauth_visual'
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# IP do Windows visto do WSL
WINDOWS_IP = '10.255.255.254'
CDP_PORT = 9222

def get_ws_url():
    """Obtem WebSocket URL do Chrome"""
    try:
        url = f'http://{WINDOWS_IP}:{CDP_PORT}/json/version'
        req = urllib.request.urlopen(url, timeout=5)
        data = json.loads(req.read().decode())
        return data.get('webSocketDebuggerUrl')
    except Exception as e:
        print(f'Erro ao conectar: {e}')
        return None

def take_screenshot_via_devtools():
    """Captura screenshot usando Chrome DevTools Protocol"""
    import websocket
    import json
    
    ws_url = get_ws_url()
    if not ws_url:
        print('Nao foi possivel obter WebSocket URL')
        return
    
    print(f'Conectando a: {ws_url}')
    ws = websocket.create_connection(ws_url)
    
    # Enviar comando para capturar screenshot
    cmd = {
        "id": 1,
        "method": "Page.captureScreenshot",
        "params": {"format": "png"}
    }
    ws.send(json.dumps(cmd))
    
    # Receber resposta
    result = json.loads(ws.recv())
    
    if 'result' in result and 'data' in result['result']:
        img_data = base64.b64decode(result['result']['data'])
        filename = f'{SCREENSHOT_DIR}/capture_{int(time.time())}.png'
        with open(filename, 'wb') as f:
            f.write(img_data)
        print(f'Screenshot salvo: {filename}')
        # Copiar para Windows
        os.system(f'cp "{filename}" /mnt/c/temp/oauth_visual/ 2>/dev/null')
    
    ws.close()

if __name__ == '__main__':
    print('Testando conexao com Chrome...')
    ws_url = get_ws_url()
    if ws_url:
        print(f'Chrome conectado!')
        take_screenshot_via_devtools()
    else:
        print('Chrome nao acessivel')
