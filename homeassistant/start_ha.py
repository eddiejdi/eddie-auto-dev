#!/usr/bin/env python3
import subprocess
import os
import sys

CONFIG_DIR = os.path.expanduser("~/myClaude/homeassistant/config")
os.makedirs(CONFIG_DIR, exist_ok=True)

print(" Iniciando Home Assistant...")
print(f" Diretório de configuração: {CONFIG_DIR}")
print("=" * 60)
print()
print(" O Home Assistant está iniciando...")
print(" Acesse: http://localhost:8123")
print()
print("Pressione Ctrl+C para parar o servidor")
print("=" * 60)

subprocess.run(
    [sys.executable, "-m", "homeassistant", "--config", CONFIG_DIR, "--skip-pip"]
)
