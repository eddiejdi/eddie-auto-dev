#!/usr/bin/env python3
"""Corrige o modelo Diretor Shared no Open WebUI"""
import os
import requests

email = 'edenilson.teixeira@rpa4all.com'
password = 'Shared@2026'
base_url = os.environ.get('OPENWEBUI_URL') or f"http://{os.environ.get('HOMELAB_HOST','localhost')}:3000"

r = requests.post(f'{base_url}/api/v1/auths/signin', json={'email': email, 'password': password}, timeout=10)
token = r.json().get('token')
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

print('✅ Login OK')

# Atualizar modelo existente com base_model correto
model_data = {
    'id': 'diretor-shared',
    'name': '👔 Diretor Shared',
    'meta': {
        'description': 'Diretor principal do sistema Shared Auto-Dev. Coordena agents, aplica regras e gera relatórios.',
        'profile_image_url': ''
    },
    'base_model_id': 'qwen2.5-coder:7b',  # Modelo que EXISTE no Ollama
    'params': {
        'system': """Você é o DIRETOR do sistema Shared Auto-Dev.

COMANDOS DISPONÍVEIS:
- /diretor <instrução> - Instrução direta
- /autocoinbot ou /acb - Relatório do AutoCoinBot  
- /equipe - Status da equipe
- /regras - Lista as 10 regras
- /pipeline <tarefa> - Pipeline completo
- /status - Status do sistema

SUAS RESPONSABILIDADES:
1. Coordenar a equipe de agents especializados
2. Aplicar as 10 regras do sistema
3. Garantir o pipeline: Análise → Design → Código → Testes → Deploy
4. Economizar tokens (preferir Ollama local)
5. Validar todas as entregas

Para relatório do AutoCoinBot, consulte:
- API: http://${HOMELAB_HOST}:8510/api/status
- Dashboard: http://${HOMELAB_HOST}:8520
""",
        'temperature': 0.7
    }
}

# Tentar atualizar
r = requests.post(f'{base_url}/api/v1/models/id/diretor-shared/update', headers=headers, json=model_data)
print(f'Update status: {r.status_code}')

if r.status_code != 200:
    # Tentar outro endpoint
    r = requests.post(f'{base_url}/api/v1/models/update', headers=headers, json=model_data)
    print(f'Update v2: {r.status_code}')

# Listar modelos para verificar
r = requests.get(f'{base_url}/api/v1/models/', headers=headers)
if r.status_code == 200:
    models = r.json()
    print('\nModelos customizados:')
    for m in models:
        base = m.get('base_model_id', 'N/A')
        print(f"  - {m.get('id')}: base={base}")
