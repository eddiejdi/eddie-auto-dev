#!/usr/bin/env python3
"""
Script para ativar a função de impressora no Open WebUI
"""
import requests
import json

WEBUI_URL = "http://127.0.0.1:8002"
EMAIL = "edenilson.adm@gmail.com"
PASSWORD = "Eddie@2026"

# 1. Login
r = requests.post(
    f"{WEBUI_URL}/api/v1/auths/signin",
    json={"email": EMAIL, "password": PASSWORD}
)
token = r.json()["token"]
headers = {"Authorization": f"Bearer {token}"}

print("✅ Autenticado")

# 2. Buscar função atual
r = requests.get(
    f"{WEBUI_URL}/api/v1/functions/printer_etiqueta",
    headers=headers
)

if r.status_code != 200:
    print(f"❌ Erro ao buscar função: {r.status_code}")
    print(r.text)
    exit(1)

func = r.json()
print(f"📋 Função encontrada: {func.get('name')}")
print(f"   Status atual: {'ATIVO' if func.get('is_active') else 'INATIVO'}")
print(f"   Global: {'SIM' if func.get('is_global') else 'NÃO'}")

# 3. Atualizar para ativar
func["is_active"] = True
func["is_global"] = True  # Tornar global para ficar disponível em todos os chats

print("\n🔄 Ativando função...")

r = requests.post(
    f"{WEBUI_URL}/api/v1/functions/id/printer_etiqueta/update",
    json=func,
    headers=headers
)

if r.status_code in [200, 201]:
    print("✅ Função ativada com sucesso!")
    
    # Verificar
    r = requests.get(
        f"{WEBUI_URL}/api/v1/functions/printer_etiqueta",
        headers=headers
    )
    func_updated = r.json()
    print(f"\n📊 Status atualizado:")
    print(f"   Ativo: {'✅ SIM' if func_updated.get('is_active') else '❌ NÃO'}")
    print(f"   Global: {'✅ SIM' if func_updated.get('is_global') else '❌ NÃO'}")
else:
    print(f"❌ Erro ao ativar: {r.status_code}")
    print(r.text[:500])
