#!/usr/bin/env python3
"""Investigação final - encontrar o modelo com base_model_id errado"""
import requests
import json

BASE = "http://192.168.15.2:3000"

session = requests.Session()

# Login
r = session.post(f"{BASE}/api/v1/auths/signin", json={
    "email": "edenilson.teixeira@rpa4all.com",
    "password": "Eddie@2026"
})
token = r.json().get("token")
headers = {"Authorization": f"Bearer {token}"}
print(f"Login: OK\n")

# Tentar diferentes endpoints para modelos
endpoints = [
    "/api/v1/models",
    "/api/models",
    "/api/models/all",
    "/api/v1/models/all",
    "/api/v1/users/models",
]

for ep in endpoints:
    r = session.get(f"{BASE}{ep}", headers=headers)
    ct = r.headers.get("Content-Type", "")
    print(f"{ep}: {r.status_code} ({ct[:30]})")
    if "json" in ct and r.status_code == 200:
        try:
            data = r.json()
            print(f"  -> Tipo: {type(data)}")
            if isinstance(data, list):
                print(f"  -> Items: {len(data)}")
                for item in data[:3]:
                    print(f"     {item.get('id', item.get('name', '?'))}")
            elif isinstance(data, dict):
                print(f"  -> Keys: {list(data.keys())}")
        except:
            pass
    print()

# Verificar funções detalhadamente
print("\n" + "=" * 50)
print("FUNÇÕES DETALHADAS")
print("=" * 50)

r = session.get(f"{BASE}/api/v1/functions/", headers=headers)
functions = r.json()

for f in functions:
    fid = f.get("id")
    name = f.get("name")
    ftype = f.get("type")
    active = f.get("is_active")
    content = f.get("content", "")
    
    print(f"\nID: {fid}")
    print(f"Nome: {name}")
    print(f"Tipo: {ftype}")
    print(f"Ativo: {active}")
    
    # Procurar qualquer referência a modelo
    import re
    
    # Procurar qwen2.5-coder:14b
    if "14b" in content:
        print(f"  !!! ALERTA: '14b' encontrado no código!")
        for i, line in enumerate(content.split('\n')):
            if "14b" in line:
                print(f"  Linha {i}: {line.strip()[:100]}")
    
    # Procurar DIRECTOR_MODEL
    match = re.search(r'DIRECTOR_MODEL.*?=.*?["\']([^"\']+)["\']', content)
    if match:
        print(f"  DIRECTOR_MODEL = {match.group(1)}")
    
    # Procurar model =
    matches = re.findall(r'model\s*[=:]\s*["\']([^"\']+)["\']', content, re.IGNORECASE)
    if matches:
        print(f"  Referencias a model: {matches}")

# Verificar se há modelo com nome Diretor
print("\n" + "=" * 50)
print("PROCURANDO MODELOS CUSTOMIZADOS")
print("=" * 50)

# Tentar pegar modelo específico por ID
possible_ids = [
    "diretor_eddie",
    "diretor-eddie",
    "director_eddie",
    "Diretor Eddie",
    "diretor_eddie:latest"
]

for mid in possible_ids:
    try:
        r = session.get(f"{BASE}/api/v1/models/{mid}", headers=headers)
        print(f"/api/v1/models/{mid}: {r.status_code}")
        if r.status_code == 200 and "json" in r.headers.get("Content-Type", ""):
            data = r.json()
            print(f"  Info: {json.dumps(data, indent=4)[:500]}")
    except:
        pass

# Verificar chats recentes para ver qual modelo está sendo usado
print("\n" + "=" * 50)
print("VERIFICANDO CHATS RECENTES")
print("=" * 50)

r = session.get(f"{BASE}/api/v1/chats", headers=headers)
if r.status_code == 200:
    chats = r.json()
    if isinstance(chats, list) and chats:
        for chat in chats[:3]:
            chat_id = chat.get("id")
            chat_model = chat.get("model", chat.get("models", "?"))
            print(f"Chat: {chat_id[:20]}... Model: {chat_model}")
