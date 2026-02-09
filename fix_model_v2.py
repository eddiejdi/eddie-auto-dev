#!/usr/bin/env python3
"""Corrigir modelo diretor-eddie usando API correta"""
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

# Payload completo
update_payload = {
    "id": "diretor-eddie",
    "name": "👔 Diretor Eddie",
    "base_model_id": "qwen2.5-coder:7b",  # CORREÇÃO AQUI!
    "meta": {
        "profile_image_url": "",
        "description": "Diretor principal do sistema Eddie Auto-Dev. Coordena agents, aplica regras e gera relatórios.",
        "capabilities": {
            "vision": False,
            "usage": True
        }
    },
    "params": {},
    "access_control": None
}

print(f"\nPayload: {json.dumps(update_payload, indent=2)}")

# Tentar POST /api/v1/models/model/update
r = session.post(f'{BASE}/api/v1/models/model/update', headers=headers, json=update_payload)
print(f"\nPOST /api/v1/models/model/update: {r.status_code}")
print(f"Resposta: {r.text[:300]}")

if r.status_code == 200:
    print("\n✅ MODELO ATUALIZADO COM SUCESSO!")
else:
    # Tentar outros endpoints
    print("\nTentando outros endpoints...")
    
    # POST /api/v1/models/update
    r = session.post(f'{BASE}/api/v1/models/update', headers=headers, json=update_payload)
    print(f"POST /api/v1/models/update: {r.status_code} - {r.text[:100]}")
    
    # Verificar se precisa deletar e recriar
    if r.status_code != 200:
        print("\nTentando deletar modelo primeiro...")
        
        # DELETE com body
        r = session.request("DELETE", f'{BASE}/api/v1/models/model/delete', headers=headers, json={"id": "diretor-eddie"})
        print(f"DELETE /api/v1/models/model/delete: {r.status_code} - {r.text[:100]}")
        
        if r.status_code == 200:
            # Recriar
            r = session.post(f'{BASE}/api/v1/models/create', headers=headers, json=update_payload)
            print(f"POST /api/v1/models/create: {r.status_code} - {r.text[:100]}")

# Verificar resultado final
print("\n" + "=" * 60)
print("VERIFICANDO RESULTADO")
print("=" * 60)

r = session.get(f'{BASE}/api/v1/models', headers=headers)
data = r.json()
models = data.get('data', [])

for m in models:
    if m.get('id') == 'diretor-eddie':
        base = m.get('info', {}).get('base_model_id', 'N/A')
        print(f"\nModelo: {m.get('name')}")
        print(f"base_model_id: {base}")
        
        if base == 'qwen2.5-coder:7b':
            print("\n🎉 SUCESSO! Modelo corrigido!")
        else:
            print(f"\n❌ AINDA ERRADO! Base: {base}")
