#!/usr/bin/env python3
"""Cria modelo Diretor no Open WebUI que usa a função"""
import requests
import json

email = 'edenilson.adm@gmail.com'
password = 'Eddie@2026'
base_url = 'http://192.168.15.2:3000'

# Login
r = requests.post(f'{base_url}/api/v1/auths/signin', json={'email': email, 'password': password}, timeout=10)
token = r.json().get('token')
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

print('✅ Login OK')

# Criar modelo que usa a função Diretor
model_data = {
    "id": "diretor-eddie",
    "name": "👔 Diretor Eddie",
    "meta": {
        "description": "Diretor principal do sistema Eddie Auto-Dev. Coordena agents, aplica regras e gera relatórios.",
        "profile_image_url": "",
        "capabilities": {
            "vision": False,
            "usage": True
        }
    },
    # CORRIGIDO: 14b não existe, usar 7b que está disponível no Ollama
    "base_model_id": "qwen2.5-coder:7b",
    "params": {
        "system": """Você é o DIRETOR do sistema Eddie Auto-Dev.

COMANDOS DISPONÍVEIS:
- /diretor <instrução> - Instrução direta
- /autocoinbot ou /acb - Relatório do AutoCoinBot  
- /equipe - Status da equipe
- /regras - Lista as 10 regras
- /pipeline <tarefa> - Pipeline completo
- /delegar <agent> <tarefa> - Delegar tarefa
- /status - Status do sistema

SUAS RESPONSABILIDADES:
1. Coordenar a equipe de agents especializados
2. Aplicar as 10 regras do sistema
3. Garantir o pipeline: Análise → Design → Código → Testes → Deploy
4. Economizar tokens (preferir Ollama local)
5. Validar todas as entregas

Quando pedirem relatório do AutoCoinBot, acesse http://192.168.15.2:8510/api/status para dados reais.
""",
        "temperature": 0.7
    },
    "access_control": None
}

# Verificar se já existe
r = requests.get(f'{base_url}/api/v1/models/', headers=headers)
existing_models = []
if r.status_code == 200:
    try:
        existing_models = r.json()
    except:
        pass

model_exists = any(m.get('id') == 'diretor-eddie' for m in existing_models if isinstance(m, dict))

if model_exists:
    print('🔄 Atualizando modelo existente...')
    r = requests.post(f'{base_url}/api/v1/models/update', headers=headers, json=model_data)
else:
    print('➕ Criando novo modelo...')
    r = requests.post(f'{base_url}/api/v1/models/create', headers=headers, json=model_data)

if r.status_code in [200, 201]:
    print('✅ Modelo "Diretor Eddie" criado/atualizado!')
    print()
    print('=' * 50)
    print('COMO USAR:')
    print('1. No Open WebUI, selecione o modelo "👔 Diretor Eddie"')
    print('2. Digite comandos como:')
    print('   - /autocoinbot')
    print('   - /diretor me envie um relatório')
    print('   - /equipe')
    print('   - /status')
    print('=' * 50)
else:
    print(f'Status: {r.status_code}')
    print(f'Resposta: {r.text[:500]}')
