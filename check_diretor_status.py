#!/usr/bin/env python3
"""
Script de verificação do status do Diretor Shared.
Execute para ver o estado atual.
"""
import os
import requests
import json
BASE = os.environ.get('OPENWEBUI_URL') or f"http://{os.environ.get('HOMELAB_HOST','localhost')}:3000"
session = requests.Session()
r = session.post(f'{BASE}/api/v1/auths/signin', json={'email':'edenilson.teixeira@rpa4all.com','password':'Shared@2026'})
token = r.json().get('token')
headers = {'Authorization': f'Bearer {token}'}

print('='*60)
print('STATUS DO DIRETOR SHARED')
print('='*60)

# 1. Função
print('\n[1] FUNÇÃO director_eddie:')
r = session.get(f'{BASE}/api/v1/functions/id/director_eddie', headers=headers)
if r.status_code == 200:
    f = r.json()
    print(f'    ✅ Existe')
    print(f'    Ativa: {f.get("is_active")}')
    print(f'    Tipo: {f.get("type")}')
    print(f'    Conteúdo: {len(f.get("content", ""))} bytes')
else:
    print(f'    ❌ Não existe (status {r.status_code})')

# 2. Modelo interno
print('\n[2] MODELO INTERNO director_eddie:')
r = session.get(f'{BASE}/api/v1/models/model?id=director_eddie', headers=headers)
if r.status_code == 200:
    m = r.json()
    print(f'    ✅ Existe')
    print(f'    base_model_id: {m.get("base_model_id")}')
    print(f'    is_active: {m.get("is_active")}')
else:
    print(f'    ❌ Não existe (status {r.status_code})')

# 3. Aparece como modelo?
print('\n[3] APARECE NA LISTA DE MODELOS?')
r = session.get(f'{BASE}/api/v1/models', headers=headers)
models = r.json().get('data', [])
found_openai = False
for m in models:
    if m.get('id') == 'director_eddie':
        print(f'    ✅ SIM (owned_by: {m.get("owned_by")})')
        found_openai = True
        break
if not found_openai:
    print(f'    ❌ NÃO - Precisa reiniciar Open WebUI')

# 4. Modelo Ollama
print('\n[4] MODELO OLLAMA diretor-shared:')
for m in models:
    if m.get('id') == 'diretor-shared':
        print(f'    ✅ Existe')
        print(f'    owned_by: {m.get("owned_by")}')
        break

# 5. Verificar system prompt
print('\n[5] SYSTEM PROMPT CONFIGURADO?')
r = session.get(f'{BASE}/api/v1/models/model?id=diretor-shared', headers=headers)
if r.status_code == 200:
    m = r.json()
    params = m.get('params', {})
    system = params.get('system', '')
    if 'DIRETOR' in system.upper():
        print(f'    ✅ SIM - System prompt do Diretor configurado')
        print(f'    Tamanho: {len(system)} chars')
    else:
        print(f'    ❌ NÃO - System prompt não configurado')

print('\n' + '='*60)
print('RESUMO:')
print('='*60)
print('''
O modelo "👔 Diretor Shared" (diretor-shared) está configurado
com um system prompt que define seu comportamento como Diretor.

Para testar:
1. Acesse http://192.168.15.2:3000
2. Selecione "👔 Diretor Shared"
3. Envie: /equipe, /regras, /status

Para que a função pipe apareça como modelo separado,
é necessário reiniciar o container Open WebUI:
  docker restart open-webui
''')
