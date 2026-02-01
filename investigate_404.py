#!/usr/bin/env python3
"""Investigação profunda do erro 404 no Open WebUI"""

import requests
import json
import re

BASE = "http://192.168.15.2:3000"
OLLAMA = "http://192.168.15.2:11434"

print("=" * 60)
print("INVESTIGAÇÃO PROFUNDA - ERRO 404")
print("=" * 60)

# 1. Login
session = requests.Session()
r = session.post(
    f"{BASE}/api/v1/auths/signin",
    json={"email": "edenilson.adm@gmail.com", "password": "Eddie@2026"},
)
token = r.json().get("token")
headers = {"Authorization": f"Bearer {token}"}
print(f"\n[1] Login: {'OK' if token else 'FALHOU'}")

# 2. Funções instaladas
r = session.get(f"{BASE}/api/v1/functions", headers=headers)
print(f"\n[2] Funções - Status: {r.status_code}")
if r.status_code != 200:
    print(f"    Erro: {r.text[:200]}")
    functions = []
else:
    functions = r.json()
    print(f"    Encontradas: {len(functions)}")
for f in functions:
    fid = f.get("id")
    name = f.get("name")
    ftype = f.get("type")
    active = f.get("is_active")
    content = f.get("content", "")

    print(f"\n    ID: {fid}")
    print(f"    Nome: {name}")
    print(f"    Tipo: {ftype}")
    print(f"    Ativo: {active}")

    # Procurar modelo no código
    if "DIRECTOR_MODEL" in content:
        match = re.search(
            r'DIRECTOR_MODEL.*?default\s*=\s*["\']([^"\']+)["\']', content
        )
        if match:
            print(f"    >>> DIRECTOR_MODEL = {match.group(1)}")

    # Procurar qualquer referência a modelo 14b
    if "14b" in content:
        print("    !!! ALERTA: Encontrado '14b' no código!")
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "14b" in line:
                print(f"        Linha {i}: {line.strip()[:80]}")

# 3. Modelos no Open WebUI
r = session.get(f"{BASE}/api/v1/models", headers=headers)
models_data = r.json()
print("\n[3] Modelos no Open WebUI:")

if isinstance(models_data, list):
    models = models_data
else:
    models = models_data.get("models", [])

for m in models[:10]:
    mid = m.get("id", "?")
    mname = m.get("name", mid)
    info = m.get("info", {})
    base_model = info.get("base_model_id", "")
    owned = m.get("owned_by", "")

    # Verificar se é o modelo que está causando 404
    if (
        "diretor" in mid.lower()
        or "diretor" in mname.lower()
        or "director" in mid.lower()
    ):
        print("\n    !!! MODELO DIRETOR ENCONTRADO !!!")
        print(f"        ID: {mid}")
        print(f"        Name: {mname}")
        print(f"        Base Model: {base_model}")
        print(f"        Info completa: {json.dumps(info, indent=8)}")
    else:
        print(f"    - {mid} (base: {base_model or owned})")

# 4. Verificar Ollama
print(f"\n[4] Verificando Ollama ({OLLAMA}):")
try:
    r = requests.get(f"{OLLAMA}/api/tags", timeout=5)
    ollama_models = r.json().get("models", [])
    print(f"    Modelos disponíveis: {len(ollama_models)}")

    # Verificar qwen2.5-coder
    qwen_models = [m["name"] for m in ollama_models if "qwen" in m["name"].lower()]
    print(f"    Modelos qwen: {qwen_models}")

    # Testar chamada direta
    print("\n[5] Testando Ollama diretamente com qwen2.5-coder:7b:")
    r = requests.post(
        f"{OLLAMA}/api/generate",
        json={
            "model": "qwen2.5-coder:7b",
            "prompt": "test",
            "stream": False,
            "options": {"num_predict": 5},
        },
        timeout=30,
    )
    if r.status_code == 200:
        print("    ✅ Ollama responde OK")
    else:
        print(f"    ❌ Erro: {r.status_code} - {r.text[:100]}")
except Exception as e:
    print(f"    ❌ Erro: {e}")

# 5. Verificar conexão WebUI -> Ollama
print("\n[6] Verificando conexão Open WebUI -> Ollama:")
try:
    r = session.get(f"{BASE}/ollama/api/tags", headers=headers)
    print(f"    Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"    Modelos via WebUI: {len(data.get('models', []))}")
    else:
        print(f"    Erro: {r.text[:200]}")
except Exception as e:
    print(f"    Erro: {e}")

# 6. Verificar se o Diretor é um "Model" customizado
print("\n[7] Procurando 'Diretor Eddie' como modelo customizado:")
for m in models:
    mid = m.get("id", "")
    mname = m.get("name", "")
    if "diretor" in mid.lower() or "diretor" in mname.lower() or "eddie" in mid.lower():
        print(f"\n    ENCONTRADO: {mid}")
        print("    Dados completos:")
        print(json.dumps(m, indent=4, default=str))

# 7. Verificar config global
print("\n[8] Verificando configurações globais:")
try:
    r = session.get(f"{BASE}/api/v1/configs", headers=headers)
    print(f"    Status: {r.status_code}")
except:
    pass

try:
    r = session.get(f"{BASE}/api/v1/config", headers=headers)
    print(f"    Config: {r.status_code}")
    if r.status_code == 200:
        cfg = r.json()
        if "default_models" in str(cfg):
            print(f"    Default models: {cfg.get('default_models', 'N/A')}")
except:
    pass

print("\n" + "=" * 60)
print("FIM DA INVESTIGAÇÃO")
print("=" * 60)
