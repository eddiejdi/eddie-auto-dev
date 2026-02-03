#!/usr/bin/env python3
"""
Remove função de impressora e reinstala com código correto
"""
import requests
import json
import os

WEBUI_URL = "http://127.0.0.1:8002"
EMAIL = "edenilson.adm@gmail.com"
PASSWORD = "Eddie@2026"
FUNCTION_ID = "printer_etiqueta"

# 1. Login
r = requests.post(
    f"{WEBUI_URL}/api/v1/auths/signin",
    json={"email": EMAIL, "password": PASSWORD}
)
token = r.json()["token"]
headers = {"Authorization": f"Bearer {token}"}

print("✅ Autenticado")

# 2. Tentar deletar função antiga
print("\n🗑️ Removendo função antiga...")
r = requests.delete(
    f"{WEBUI_URL}/api/v1/functions/id/{FUNCTION_ID}/delete",
    headers=headers
)

if r.status_code in [200, 204]:
    print("   ✅ Função anterior removida")
elif r.status_code == 405:
    print(f"   ⚠️ Método DELETE não permitido (405), tentando via POST...")
    r = requests.post(
        f"{WEBUI_URL}/api/v1/functions/id/{FUNCTION_ID}/delete",
        headers=headers
    )
    if r.status_code in [200, 204]:
        print("   ✅ Função anterior removida")
    else:
        print(f"   ⚠️ Não foi possível remover ({r.status_code})")
else:
    print(f"   ⚠️ Não foi possível remover ({r.status_code}): {r.text[:200]}")

# 3. Ler novo código
func_file = "/home/homelab/agents_workspace/openwebui_printer_function.py"
with open(func_file, 'r') as f:
    function_code = f.read()

# 4. Reinstalar função com código corrigido
print("\n📥 Instalando função corrigida...")
payload = {
    "id": FUNCTION_ID,
    "name": "🖨️ Impressora de Etiquetas",
    "type": "pipe",
    "content": function_code,
    "is_active": True,  # JÁ ATIVAR!
    "is_global": True,   # GLOBAL para todos os chats
    "meta": {
        "description": "Imprime etiquetas no Phomemo Q30 com validação automática de tamanho (PIPE corrigido)",
        "author": "Eddie Auto-Dev",
        "tags": ["printer", "etiqueta", "phomemo"]
    }
}

r = requests.post(
    f"{WEBUI_URL}/api/v1/functions/create",
    json=payload,
    headers=headers
)

if r.status_code in [200, 201]:
    print("✅ Função instalada!")
elif r.status_code == 400 and "already registered" in r.text:
    print("⚠️ ID já existe, tentando atualizar...")
    
    # Tentar atualizar
    r = requests.post(
        f"{WEBUI_URL}/api/v1/functions/id/{FUNCTION_ID}/update",
        json=payload,
        headers=headers
    )
    
    if r.status_code in [200, 201]:
        print("✅ Função atualizada!")
    else:
        print(f"❌ Erro ao atualizar: {r.status_code}")
        print(r.text[:300])
        exit(1)
else:
    print(f"❌ Erro: {r.status_code}")
    print(r.text[:300])
    exit(1)

print(f"\n✅ CONCLUÍDO!")
print(f"   • Função: {FUNCTION_ID}")
print(f"   • Status: ATIVO ✅")
print(f"   • Global: SIM ✅")
print(f"\n🎯 Agora teste no chat: 'Imprima TESTE 123'")
