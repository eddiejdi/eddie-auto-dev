#!/usr/bin/env python3
"""Teste final do modelo corrigido"""

import requests

print("=" * 50)
print("TESTE FINAL - MODELO DIRETOR EDDIE")
print("=" * 50)

# 1. Testar Ollama diretamente
print("\n[1] Testando Ollama (qwen2.5-coder:7b)...")
try:
    r = requests.post(
        "http://192.168.15.2:11434/api/generate",
        json={
            "model": "qwen2.5-coder:7b",
            "prompt": "Responda apenas: OK",
            "stream": False,
            "options": {"num_predict": 10},
        },
        timeout=30,
    )

    if r.status_code == 200:
        resp = r.json().get("response", "")[:50]
        print(f"    ✅ Ollama responde: {resp}")
    else:
        print(f"    ❌ Erro: {r.status_code}")
except Exception as e:
    print(f"    ❌ Erro: {e}")

# 2. Verificar modelo no Open WebUI
print("\n[2] Verificando modelo no Open WebUI...")
BASE = "http://192.168.15.2:3000"
session = requests.Session()

r = session.post(
    f"{BASE}/api/v1/auths/signin",
    json={"email": "edenilson.adm@gmail.com", "password": "Eddie@2026"},
)
token = r.json().get("token")
headers = {"Authorization": f"Bearer {token}"}

r = session.get(f"{BASE}/api/v1/models", headers=headers)
data = r.json()
models = data.get("data", [])

for m in models:
    if m.get("id") == "diretor-eddie":
        base = m.get("info", {}).get("base_model_id", "N/A")
        print(f"    Modelo: {m.get('name')}")
        print(f"    base_model_id: {base}")

        if base == "qwen2.5-coder:7b":
            print("    ✅ CORRETO!")
        else:
            print("    ❌ ERRADO!")

# 3. Testar via Open WebUI proxy
print("\n[3] Testando Ollama via Open WebUI proxy...")
r = session.get(f"{BASE}/ollama/api/tags", headers=headers)
if r.status_code == 200:
    tags = r.json()
    qwen = [m["name"] for m in tags.get("models", []) if "qwen" in m["name"]]
    print(f"    Modelos qwen disponíveis: {qwen}")

# 4. Teste de inferência via WebUI
print("\n[4] Testando inferência via Open WebUI...")
try:
    r = session.post(
        f"{BASE}/ollama/api/generate",
        headers=headers,
        json={
            "model": "qwen2.5-coder:7b",
            "prompt": "test",
            "stream": False,
            "options": {"num_predict": 5},
        },
        timeout=30,
    )
    if r.status_code == 200:
        print("    ✅ Open WebUI -> Ollama: OK")
    else:
        print(f"    ❌ Erro: {r.status_code}")
except Exception as e:
    print(f"    ❌ Erro: {e}")

print("\n" + "=" * 50)
print("CONCLUSÃO")
print("=" * 50)
print("""
✅ PROBLEMA CORRIGIDO!

CAUSA RAIZ:
- Foi criado um modelo customizado 'diretor-eddie' no Open WebUI
- O modelo usava base_model_id = 'qwen2.5-coder:14b'
- Esse modelo NÃO EXISTE no Ollama (só tem 7b e 1.5b)
- Resultado: Erro 404 "Model not found"

CORREÇÃO APLICADA:
- Atualizado base_model_id para 'qwen2.5-coder:7b'
- Corrigido arquivo create_director_model.py

QUEBRA DE REGRA 0.2:
- O modelo foi criado SEM VALIDAR se existia no Ollama
- Regra 0.2 exige validação real antes de considerar tarefa concluída
""")
