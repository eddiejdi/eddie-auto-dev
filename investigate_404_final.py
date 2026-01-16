#!/usr/bin/env python3
"""Investigação FINAL - Ver conteúdo real das funções e modelos"""
import requests
import json

BASE = "http://192.168.15.2:3000"

session = requests.Session()

# Login
r = session.post(f"{BASE}/api/v1/auths/signin", json={
    "email": "edenilson.adm@gmail.com",
    "password": "Eddie@2026"
})
token = r.json().get("token")
headers = {"Authorization": f"Bearer {token}"}
print(f"Login: OK\n")

# Pegar função director_eddie
print("=" * 60)
print("CONTEÚDO DA FUNÇÃO DIRECTOR_EDDIE")
print("=" * 60)

r = session.get(f"{BASE}/api/v1/functions/director_eddie", headers=headers)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    func = r.json()
    content = func.get("content", "")
    
    # Mostrar linhas relevantes
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if any(x in line.lower() for x in ['director_model', 'ollama', 'model', '14b', '7b', 'qwen']):
            print(f"{i:3}: {line}")

# Verificar modelos no data
print("\n" + "=" * 60)
print("MODELOS NO OPEN WEBUI (data)")
print("=" * 60)

r = session.get(f"{BASE}/api/v1/models", headers=headers)
data = r.json()
models = data.get("data", [])
print(f"Total: {len(models)} modelos\n")

for m in models:
    mid = m.get("id", "?")
    mname = m.get("name", "")
    base = m.get("base_model_id", "")
    info = m.get("info", {})
    base_from_info = info.get("base_model_id", "")
    meta = m.get("meta", {})
    
    # Procurar qualquer coisa relacionada ao Diretor
    if "diretor" in mid.lower() or "diretor" in mname.lower() or "eddie" in mid.lower():
        print(f"!!! MODELO DIRETOR ENCONTRADO !!!")
        print(f"    id: {mid}")
        print(f"    name: {mname}")
        print(f"    base_model_id: {base}")
        print(f"    info.base_model_id: {base_from_info}")
        print(f"    meta: {meta}")
        print(f"    COMPLETO: {json.dumps(m, indent=4)[:1000]}")
        print()
    else:
        # Mostrar outros
        actual_base = base or base_from_info
        print(f"  {mid}: base={actual_base}")

# Verificar se há modelos usando qwen2.5-coder:14b
print("\n" + "=" * 60)
print("PROCURANDO REFERÊNCIAS A 14b")
print("=" * 60)

for m in models:
    m_str = json.dumps(m)
    if "14b" in m_str:
        print(f"!!! MODELO COM 14b: {m.get('id')}")
        print(json.dumps(m, indent=2)[:500])

# Verificar também a versão da API
print("\n" + "=" * 60)
print("VERSÃO DO OPEN WEBUI")
print("=" * 60)

try:
    r = session.get(f"{BASE}/api/version", headers=headers)
    print(f"Versão: {r.json()}")
except:
    pass

try:
    r = session.get(f"{BASE}/api/config", headers=headers)
    print(f"Config status: {r.status_code}")
except:
    pass
