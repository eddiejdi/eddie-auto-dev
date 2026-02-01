#!/usr/bin/env python3
"""Corrige e testa o Diretor Eddie no Open WebUI"""

import requests

email = "edenilson.adm@gmail.com"
password = "Eddie@2026"
base_url = "http://192.168.15.2:3000"

# Login
r = requests.post(
    f"{base_url}/api/v1/auths/signin",
    json={"email": email, "password": password},
    timeout=10,
)
token = r.json().get("token")
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

print("✅ Login OK")

# Deletar modelo customizado se existir
r = requests.get(f"{base_url}/api/v1/models/", headers=headers)
if r.status_code == 200:
    try:
        data = r.json()
        models = data.get("models", data) if isinstance(data, dict) else data
        for m in models:
            if isinstance(m, dict) and m.get("id") == "diretor-eddie":
                print(f"Encontrado modelo customizado: {m.get('id')}")
                # Tentar deletar
                r = requests.delete(
                    f"{base_url}/api/v1/models/id/diretor-eddie", headers=headers
                )
                print(f"Delete: {r.status_code}")
    except Exception as e:
        print(f"Erro ao listar modelos: {e}")

# Verificar funções
r = requests.get(f"{base_url}/api/v1/functions/", headers=headers)
print("\n📦 Funções instaladas:")
for f in r.json():
    active = "✅" if f.get("is_active") else "❌"
    print(f"  {active} {f.get('id')}: {f.get('name')}")

# Testar a função diretamente
print("\n🧪 Testando função...")

# Em Open WebUI, funções Pipe aparecem como modelos com prefixo especial
# O ID do modelo seria algo como: "director_eddie" (mesmo ID da função)
print("""
📋 COMO USAR NO OPEN WEBUI:
1. Vá para http://192.168.15.2:3000
2. Clique no dropdown de modelos
3. Procure por "Diretor Eddie" ou "director_eddie"
4. Se não aparecer, use um modelo Ollama normal como "qwen2.5-coder:7b"

ALTERNATIVA - USE O MODELO OLLAMA DIRETO:
1. Selecione "qwen2.5-coder:7b" 
2. Digite sua pergunta normalmente
""")
