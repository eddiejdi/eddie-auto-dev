#!/usr/bin/env python3
"""Corrigir o modelo customizado diretor-eddie no Open WebUI"""
import os
import requests
import json

BASE = os.environ.get('OPENWEBUI_URL') or f"http://{os.environ.get('HOMELAB_HOST','localhost')}:3000"

session = requests.Session()

# Login
r = session.post(f'{BASE}/api/v1/auths/signin', json={
    'email': 'edenilson.teixeira@rpa4all.com',
    'password': 'Eddie@2026'
})
token = r.json().get('token')
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

print("=" * 60)
print("CORRIGINDO MODELO DIRETOR-EDDIE")
print("=" * 60)

# 1. Verificar modelo atual
model_id = "diretor-eddie"
r = session.get(f'{BASE}/api/v1/models/{model_id}', headers=headers)
print(f"\n[1] GET modelo atual: {r.status_code}")

# Tentar outro endpoint
r = session.get(f'{BASE}/api/v1/models', headers=headers)
data = r.json()
models = data.get('data', [])

diretor = None
for m in models:
    if m.get('id') == 'diretor-eddie':
        diretor = m
        break

if diretor:
    print(f"    Encontrado: {diretor.get('name')}")
    print(f"    base_model_id atual: {diretor.get('info', {}).get('base_model_id')}")
    
    # 2. Atualizar para usar qwen2.5-coder:7b
    print(f"\n[2] Atualizando base_model_id para qwen2.5-coder:7b...")
    
    # Pegar info atual
    info = diretor.get('info', {})
    meta = info.get('meta', {})
    
    # Preparar payload para update
    update_payload = {
        "id": "diretor-eddie",
        "base_model_id": "qwen2.5-coder:7b",  # CORREÇÃO!
        "name": "👔 Diretor Eddie",
        "meta": {
            "profile_image_url": meta.get("profile_image_url", ""),
            "description": "Diretor principal do sistema Eddie Auto-Dev. Coordena agents, aplica regras e gera relatórios.",
            "capabilities": meta.get("capabilities", {"vision": False, "usage": True})
        },
        "params": {},
        "access_control": None
    }
    
    # Tentar POST para criar/atualizar
    r = session.post(f'{BASE}/api/v1/models/create', headers=headers, json=update_payload)
    print(f"    POST /models/create: {r.status_code}")
    if r.status_code != 200:
        print(f"    Resposta: {r.text[:200]}")
    
    # Tentar PUT para atualizar
    r = session.put(f'{BASE}/api/v1/models/update', headers=headers, json=update_payload)
    print(f"    PUT /models/update: {r.status_code}")
    if r.status_code != 200:
        print(f"    Resposta: {r.text[:200]}")
    
    # Tentar POST direto no modelo
    r = session.post(f'{BASE}/api/v1/models/{model_id}/update', headers=headers, json=update_payload)
    print(f"    POST /models/{model_id}/update: {r.status_code}")
    if r.status_code != 200:
        print(f"    Resposta: {r.text[:200]}")

# 3. Verificar resultado
print(f"\n[3] Verificando resultado...")
r = session.get(f'{BASE}/api/v1/models', headers=headers)
data = r.json()
models = data.get('data', [])

for m in models:
    if m.get('id') == 'diretor-eddie':
        new_base = m.get('info', {}).get('base_model_id')
        print(f"    base_model_id agora: {new_base}")
        if new_base == 'qwen2.5-coder:7b':
            print(f"    ✅ CORRIGIDO!")
        else:
            print(f"    ❌ Ainda errado, tentando deletar e recriar...")
            
            # Deletar modelo
            r = session.delete(f'{BASE}/api/v1/models/{model_id}', headers=headers)
            print(f"    DELETE: {r.status_code}")
            
            # Recriar
            new_model = {
                "id": "diretor-eddie",
                "base_model_id": "qwen2.5-coder:7b",
                "name": "👔 Diretor Eddie",
                "meta": {
                    "profile_image_url": "",
                    "description": "Diretor principal do sistema Eddie Auto-Dev. Coordena agents, aplica regras e gera relatórios.",
                    "capabilities": {"vision": False, "usage": True}
                },
                "params": {},
                "access_control": None
            }
            r = session.post(f'{BASE}/api/v1/models/create', headers=headers, json=new_model)
            print(f"    CREATE: {r.status_code}")
            if r.status_code == 200:
                print(f"    ✅ Modelo recriado com sucesso!")
            else:
                print(f"    {r.text[:200]}")
