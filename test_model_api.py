#!/usr/bin/env python3
"""Investigar e corrigir modelo diretor-eddie usando a API correta"""
import requests
import json

BASE = 'http://192.168.15.2:3000'

session = requests.Session()

# Login
r = session.post(f'{BASE}/api/v1/auths/signin', json={
    'email': 'edenilson.adm@gmail.com',
    'password': 'Eddie@2026'
})
token = r.json().get('token')
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

print("Testando endpoints da API de modelos...\n")

model_id = "diretor-eddie"

# Testar diferentes métodos
endpoints = [
    ("GET", f"/api/v1/models/{model_id}", None),
    ("GET", f"/api/models/{model_id}", None),
    ("POST", f"/api/v1/models/{model_id}", {"base_model_id": "qwen2.5-coder:7b"}),
    ("PUT", f"/api/v1/models/{model_id}", {"base_model_id": "qwen2.5-coder:7b"}),
    ("DELETE", f"/api/v1/models/delete", {"id": model_id}),
    ("DELETE", f"/api/v1/models/{model_id}/delete", None),
    ("POST", f"/api/v1/models/model/update", {"id": model_id, "base_model_id": "qwen2.5-coder:7b"}),
]

for method, endpoint, payload in endpoints:
    try:
        if method == "GET":
            r = session.get(f"{BASE}{endpoint}", headers=headers)
        elif method == "POST":
            r = session.post(f"{BASE}{endpoint}", headers=headers, json=payload)
        elif method == "PUT":
            r = session.put(f"{BASE}{endpoint}", headers=headers, json=payload)
        elif method == "DELETE":
            if payload:
                r = session.request("DELETE", f"{BASE}{endpoint}", headers=headers, json=payload)
            else:
                r = session.delete(f"{BASE}{endpoint}", headers=headers)
        
        ct = r.headers.get('Content-Type', '')
        is_json = 'json' in ct
        body = r.text[:100] if not is_json else str(r.json())[:100]
        print(f"{method} {endpoint}: {r.status_code} - {body}")
    except Exception as e:
        print(f"{method} {endpoint}: ERROR - {e}")

# Ver documentação da API
print("\n\nProcurando endpoint de update na docs...")
try:
    r = session.get(f"{BASE}/docs", headers=headers)
    print(f"GET /docs: {r.status_code}")
except:
    pass

try:
    r = session.get(f"{BASE}/openapi.json", headers=headers)
    if r.status_code == 200:
        spec = r.json()
        paths = spec.get('paths', {})
        model_paths = [p for p in paths.keys() if 'model' in p.lower()]
        print(f"\nEndpoints de model encontrados:")
        for p in model_paths[:15]:
            methods = list(paths[p].keys())
            print(f"  {p}: {methods}")
except Exception as e:
    print(f"Erro: {e}")
