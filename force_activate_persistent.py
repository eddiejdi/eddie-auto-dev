#!/usr/bin/env python3
"""
Força ativação persistente da função - testa múltiplas abordagens
"""
import os
import subprocess
import time
import requests

SERVER = os.environ.get('HOMELAB_SSH', 'homelab@192.168.15.2')
HOMELAB_HOST = os.environ.get('HOMELAB_HOST', '192.168.15.2')
WEBUI_URL = os.environ.get('WEBUI_URL', f"http://{HOMELAB_HOST}:8002")
EMAIL = "edenilson.teixeira@rpa4all.com"
PASSWORD = "Shared@2026"

def run_ssh(cmd):
    """Executa comando SSH"""
    result = subprocess.run(
        ['ssh', SERVER, cmd],
        capture_output=True,
        text=True
    )
    return result.stdout, result.stderr, result.returncode

def get_auth_token():
    """Obtém token de autenticação"""
    response = requests.post(
        f"{WEBUI_URL}/api/v1/auths/signin",
        json={"email": EMAIL, "password": PASSWORD}
    )
    return response.json()["token"]

def check_function_status():
    """Verifica status da função"""
    token = get_auth_token()
    response = requests.get(
        f"{WEBUI_URL}/api/v1/functions/",
        headers={"Authorization": f"Bearer {token}"}
    )
    funcs = response.json()
    for f in funcs:
        if f["id"] == "printer_etiqueta":
            return f["is_active"], f["is_global"]
    return None, None

print("="*80)
print("FORÇANDO ATIVAÇÃO PERSISTENTE")
print("="*80)

# Método 1: Parar container, modificar banco, reiniciar
print("\n🔧 Método 1: Stop → Update DB → Start")
print("1. Parando container...")
run_ssh("docker stop open-webui")
time.sleep(2)

print("2. Modificando banco de dados diretamente no volume...")
update_script = """
sudo python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('/var/lib/docker/volumes/open-webui/_data/webui.db')
cursor = conn.cursor()

# Atualizar
cursor.execute("UPDATE function SET is_active=1, is_global=1 WHERE id='printer_etiqueta'")
conn.commit()
print(f"Linhas atualizadas: {cursor.rowcount}")

# Verificar
cursor.execute("SELECT id, is_active, is_global FROM function WHERE id='printer_etiqueta'")
result = cursor.fetchone()
if result:
    print(f"Verificação: ID={result[0]}, Ativo={result[1]}, Global={result[2]}")
else:
    print("ERRO: Função não encontrada!")

conn.close()
EOF
"""
stdout, stderr, _ = run_ssh(update_script)
print(stdout)
if stderr:
    print(f"Stderr: {stderr}")

print("3. Iniciando container...")
run_ssh("docker start open-webui")
time.sleep(10)  # Aguardar inicialização

print("4. Verificando via API...")
is_active, is_global = check_function_status()
if is_active and is_global:
    print("✅ SUCESSO! Função ativada e persistente!")
else:
    print(f"⚠️ Status: Active={is_active}, Global={is_global}")

print("\n" + "="*80)
print("TESTE AGORA:")
print(f"  Acesse: {WEBUI_URL}")
print("  Digite: Imprima TESTE 123")
print("="*80)
