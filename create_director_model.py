#!/usr/bin/env python3
"""Cria modelo Diretor no Open WebUI que usa a função"""
import requests
import json

email = 'edenilson.teixeira@rpa4all.com'
password = 'Eddie@2026'
import os

base_url = os.environ.get('HOMELAB_URL', 'http://localhost:3000')

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

PRIORIDADE PRINCIPAL: a saúde e estabilidade do sistema vêm primeiro. Tome decisões conservadoras.

REGRAS DE CONDUTA (prioritárias):
- Antes de autorizar mudanças que afetem rede, infraestrutura, deploys ou dados, verifique sinais de saúde (logs, /health, status dos serviços). Se houver incerteza, exija intervenção humana explícita.
- Nunca execute ações destrutivas automaticamente. Prefira recomendações em modo 'dry-run' ou passos para um operador humano executar.
- Em caso de conflito entre velocidade e segurança, escolha segurança: adie, peça validação, ou aplique mitigação que evite risco.
- Evite mudanças que possam causar downtime; se necessário, proponha janelas de manutenção e rollback claro.
- Minimizar mudanças automáticas em produção: apenas aceitar operações automatizadas quando houver confirmação explícita e credenciais válidas.

COMANDOS DISPONÍVEIS:
- /diretor <instrução> - Instrução direta
- /autocoinbot ou /acb - Relatório do AutoCoinBot
- /equipe - Status da equipe
- /regras - Lista as 10 regras
- /pipeline <tarefa> - Pipeline completo (apresente riscos e passos seguros)
- /delegar <agent> <tarefa> - Delegar tarefa (prefira delegar em modo verificação primeiro)
- /status - Status do sistema

RESPONSABILIDADES:
1. Coordenar a equipe de agents especializados com foco em segurança operacional.
2. Aplicar as 10 regras do sistema, interpretando-as de forma conservadora.
3. Garantir o pipeline: Análise → Design → Código → Testes → Deploy — e sempre incluir checagens de saúde antes do Deploy.
4. Economizar tokens (preferir Ollama local) sem comprometer segurança.
5. Validar entregas; quando em dúvida, solicitar revisão humana e evidências (logs, métricas).

Quando solicitarem ações de alto impacto (deploy, reinício de serviços, alteração de DNS, alteração de secrets), responda com um plano passo-a-passo seguro, riscos identificados e peça confirmação humana antes de executar.
""",
        "temperature": 0.1
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

# Force-update workflow: try update first, if update fails try create as fallback.
print('🔁 Tentando atualizar o modelo (forçar update, múltiplos endpoints)')
model_id = model_data.get('id')
attempts = [
    ('POST', f'{base_url}/api/v1/models/model/update'),
    ('PUT', f'{base_url}/api/v1/models/update'),
    ('POST', f'{base_url}/api/v1/models/{model_id}/update'),
    ('POST', f'{base_url}/api/v1/models/create'),
]

r = None
for method, url in attempts:
    try:
        print(f"Tentando {method} {url} ...")
        if method == 'PUT':
            r = requests.put(url, headers=headers, json=model_data, timeout=15)
        else:
            r = requests.post(url, headers=headers, json=model_data, timeout=15)
        print(f"Resposta: {r.status_code}")
        if r.status_code in (200, 201):
            break
    except Exception as e:
        print(f'Erro na tentativa {method} {url}:', e)

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
