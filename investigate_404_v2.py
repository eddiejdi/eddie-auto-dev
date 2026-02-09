#!/usr/bin/env python3
"""Investigação direta e robusta do erro 404"""
import requests
import json

import os

BASE = os.environ.get('BASE_URL') or f"http://{os.environ.get('HOMELAB_HOST','localhost')}:3000"
OLLAMA = os.environ.get('OLLAMA_URL') or f"http://{os.environ.get('HOMELAB_HOST','localhost')}:11434"

print("=" * 60)
print("INVESTIGAÇÃO 404 - VERSÃO ROBUSTA")
print("=" * 60)

session = requests.Session()

# 1. Login
r = session.post(f"{BASE}/api/v1/auths/signin", json={
    "email": "edenilson.teixeira@rpa4all.com",
    "password": "Eddie@2026"
})
print(f"\n[1] Login status: {r.status_code}")
data = r.json()
token = data.get("token")
print(f"    Token: {'OK' if token else 'FALHOU'}")
headers = {"Authorization": f"Bearer {token}"}

# 2. Listar funções
print("\n[2] Funções:")
r = session.get(f"{BASE}/api/v1/functions/", headers=headers)  # Note trailing /
print(f"    Status: {r.status_code}")
print(f"    Content-Type: {r.headers.get('Content-Type')}")
print(f"    Body (primeiros 500 chars): {r.text[:500]}")

# 3. Listar modelos
print("\n[3] Modelos:")
r = session.get(f"{BASE}/api/v1/models/", headers=headers)
print(f"    Status: {r.status_code}")
print(f"    Content-Type: {r.headers.get('Content-Type')}")
try:
    models = r.json()
    if isinstance(models, list):
        print(f"    Total: {len(models)}")
        for m in models[:5]:
            print(f"      - {m.get('id', m.get('name', '?'))}")
    elif isinstance(models, dict):
        if "models" in models:
            print(f"    Total: {len(models['models'])}")
            for m in models["models"][:5]:
                mid = m.get("id", "?")
                base = m.get("info", {}).get("base_model_id", "")
                print(f"      - {mid} -> base: {base}")
        else:
            print(f"    Keys: {list(models.keys())}")
except Exception as e:
    print(f"    Erro parse: {e}")
    print(f"    Raw: {r.text[:300]}")

# 4. Verificar diretamente modelos Ollama via WebUI proxy
print("\n[4] Ollama via WebUI proxy:")
r = session.get(f"{BASE}/ollama/api/tags", headers=headers)
print(f"    Status: {r.status_code}")
if r.status_code == 200:
    try:
        tags = r.json()
        ollama_models = [m["name"] for m in tags.get("models", [])]
        print(f"    Modelos Ollama: {ollama_models}")
    except:
        print(f"    Erro parse: {r.text[:200]}")

# 5. Verificar qwen diretamente no Ollama
print("\n[5] Ollama direto:")
try:
    r = requests.get(f"{OLLAMA}/api/tags", timeout=5)
    models = r.json().get("models", [])
    qwen = [m["name"] for m in models if "qwen" in m["name"]]
    print(f"    Modelos qwen: {qwen}")
except Exception as e:
    print(f"    Erro: {e}")

# 6. Testar modelo que dá 404
print("\n[6] Testando modelos que podem dar 404:")
test_models = [
    "qwen2.5-coder:7b",
    "qwen2.5-coder:14b",  # Este não existe
    "diretor-eddie",
    "eddie-coder:latest"
]
for model in test_models:
    try:
        r = requests.post(f"{OLLAMA}/api/generate", json={
            "model": model,
            "prompt": "hi",
            "stream": False,
            "options": {"num_predict": 1}
        }, timeout=10)
        if r.status_code == 200:
            print(f"    ✅ {model}: OK")
        else:
            err = r.json().get("error", r.text[:50])
            print(f"    ❌ {model}: {r.status_code} - {err}")
    except Exception as e:
        print(f"    ❌ {model}: {e}")

# 7. Verificar qual modelo está selecionado no WebUI
print("\n[7] Verificando configuração de modelo padrão:")
try:
    r = session.get(f"{BASE}/api/v1/configs", headers=headers)
    print(f"    /configs: {r.status_code}")
except:
    pass

try:
    r = session.get(f"{BASE}/api/v1/config", headers=headers)
    print(f"    /config: {r.status_code}")
    if r.status_code == 200:
        cfg = r.json()
        print(f"    Config keys: {list(cfg.keys())[:10]}")
except Exception as e:
    print(f"    Erro: {e}")

# 8. Procurar o modelo "Diretor Eddie" especificamente
print("\n[8] Procurando modelo customizado 'Diretor Eddie':")
r = session.get(f"{BASE}/api/v1/models/", headers=headers)
if r.status_code == 200:
    try:
        models = r.json()
        model_list = models if isinstance(models, list) else models.get("models", [])
        
        for m in model_list:
            mid = m.get("id", "").lower()
            mname = m.get("name", "").lower()
            
            if "diretor" in mid or "diretor" in mname or "director" in mid:
                print(f"\n    !!! ENCONTRADO: {m.get('id')}")
                print(f"    Nome: {m.get('name')}")
                info = m.get("info", {})
                base = info.get("base_model_id", "N/A")
                print(f"    Base Model ID: {base}")
                
                # Este é o problema!
                if base and "14b" in base:
                    print(f"\n    ⚠️  PROBLEMA IDENTIFICADO!")
                    print(f"    O modelo usa base_model_id: {base}")
                    print(f"    Mas esse modelo NÃO EXISTE no Ollama!")
                    
                params = info.get("params", {})
                print(f"    Params: {json.dumps(params, indent=6)}")
    except Exception as e:
        print(f"    Erro: {e}")

print("\n" + "=" * 60)
