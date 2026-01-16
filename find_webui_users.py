#!/usr/bin/env python3
"""Busca usuários do Open WebUI via SSH"""
import subprocess
import sys

cmd = '''ssh eddie@192.168.15.2 "sqlite3 ~/.local/share/open-webui/webui.db 'SELECT email FROM user LIMIT 5;'" 2>/dev/null'''

try:
    result = subprocess.run(['bash', '-c', cmd], capture_output=True, text=True, timeout=10)
    if result.stdout:
        print("Emails encontrados no Open WebUI:")
        for email in result.stdout.strip().split('\n'):
            print(f"  - {email}")
    else:
        print("Nenhum email encontrado ou SSH não disponível")
        print(f"stderr: {result.stderr}")
except Exception as e:
    print(f"Erro: {e}")
