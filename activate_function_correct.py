#!/usr/bin/env python3
"""
SOLUÇÃO CORRETA: Usar endpoint /toggle para ativar função
Baseado no código-fonte do Open WebUI
"""
import requests

WEBUI_URL = "http://192.168.15.2:8002"
EMAIL = "edenilson.adm@gmail.com"
PASSWORD = "Eddie@2026"
FUNCTION_ID = "printer_etiqueta"

# 1. Autenticar
print("1️⃣ Autenticando...")
auth_response = requests.post(
    f"{WEBUI_URL}/api/v1/auths/signin",
    json={"email": EMAIL, "password": PASSWORD}
)

token = auth_response.json()["token"]
print(f"✅ Token obtido")

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# 2. Toggle Active (ativa/desativa)
print("\n2️⃣ Ativando função via /toggle...")
toggle_response = requests.post(
    f"{WEBUI_URL}/api/v1/functions/id/{FUNCTION_ID}/toggle",
    headers=headers
)

print(f"Status: {toggle_response.status_code}")
if toggle_response.status_code == 200:
    result = toggle_response.json()
    print(f"✅ is_active: {result.get('is_active')}")
else:
    print(f"❌ Erro: {toggle_response.text}")

# 3. Toggle Global 
print("\n3️⃣ Ativando global via /toggle/global...")
global_response = requests.post(
    f"{WEBUI_URL}/api/v1/functions/id/{FUNCTION_ID}/toggle/global",
    headers=headers
)

print(f"Status: {global_response.status_code}")
if global_response.status_code == 200:
    result = global_response.json()
    print(f"✅ is_global: {result.get('is_global')}")
else:
    print(f"❌ Erro: {global_response.text}")

# 4. Verificar resultado final
print("\n4️⃣ Verificando...")
get_response = requests.get(
    f"{WEBUI_URL}/api/v1/functions/",
    headers=headers
)

for func in get_response.json():
    if func["id"] == FUNCTION_ID:
        print(f"\n📊 Status Final:")
        print(f"   Nome: {func['name']}")
        print(f"   Ativo: {'✅' if func['is_active'] else '❌'} {func['is_active']}")
        print(f"   Global: {'✅' if func['is_global'] else '❌'} {func['is_global']}")

print("\n" + "="*80)
print("✅ CONCLUÍDO!")
print("="*80)
print("\n💡 Agora teste no chat: 'Imprima Júlia Teixeira'")
print("="*80)
