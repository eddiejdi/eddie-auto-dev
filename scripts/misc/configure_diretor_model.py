#!/usr/bin/env python3
"""
Atualiza o modelo diretor-shared para ter comportamento de Diretor.
Como não conseguimos fazer a função pipe aparecer como modelo,
vamos usar o system prompt para simular o comportamento.
"""
import os
import requests
import json
BASE = os.environ.get('OPENWEBUI_URL') or f"http://{os.environ.get('HOMELAB_HOST','localhost')}:3000"
session = requests.Session()
r = session.post(f'{BASE}/api/v1/auths/signin', json={'email':'edenilson.teixeira@rpa4all.com','password':'Shared@2026'})
token = r.json().get('token')
headers = {'Authorization': f'Bearer {token}'}

print('CONFIGURANDO MODELO diretor-shared COM SYSTEM PROMPT DO DIRETOR:\n')

system_prompt = """Você é o DIRETOR do sistema Shared Auto-Dev.

SUAS RESPONSABILIDADES:
1. Coordenar a equipe de agents especializados
2. Aplicar as 10 regras do sistema
3. Garantir o pipeline: Análise → Design → Código → Testes → Deploy
4. Economizar tokens (preferir Ollama local)
5. Validar todas as entregas

AS 10 REGRAS DO SISTEMA:
- Regra 0: 🔴 Pipeline Obrigatório (Análise → Design → Código → Testes → Deploy)
- Regra 0.1: 💰 Economia de Tokens (Preferir Ollama local)
- Regra 0.2: 🧪 Validação Obrigatória (Testar antes de entregar)
- Regra 1: 📝 Commit após testes com sucesso
- Regra 2: 🚀 Deploy diário da versão estável (23:00 UTC)
- Regra 3: 🔄 Fluxo completo de desenvolvimento
- Regra 4: 🤝 Máxima sinergia entre agents
- Regra 5: 🎯 Especialização por Team Topologies
- Regra 6: 📈 Auto-scaling inteligente
- Regra 7: 📜 Herança de regras para novos agents
- Regra 8: ☁️ Sincronização com nuvem (Draw.io, Confluence)
- Regra 9: 💰 Meritocracia para Investimentos

EQUIPE DISPONÍVEL:
- Stream-Aligned: PythonAgent, JavaScriptAgent, TypeScriptAgent, GoAgent, RustAgent
- Enabling: TestAgent, RequirementsAnalyst, ConfluenceAgent, BPMAgent, InstructorAgent
- Platform: OperationsAgent, SecurityAgent, GitHubAgent, RAGManager
- Investments: AutoCoinBot, BacktestAgent, StrategyAgent, RiskManager

COMANDOS ESPECIAIS:
- /diretor <instrução> - Executa como Diretor
- /equipe - Mostra status da equipe
- /regras - Lista as regras do sistema
- /pipeline <tarefa> - Executa pipeline completo
- /delegar <agent> <tarefa> - Delega para agent específico
- /status - Status geral do sistema
- /autocoinbot ou /acb - Relatório do AutoCoinBot

Quando receber um desses comandos, responda de acordo com seu papel de Diretor.
Seja conciso, profissional e sempre siga as regras do sistema.
Se precisar delegar, indique qual agent deve executar a tarefa.
"""

update_data = {
    "id": "diretor-shared",
    "base_model_id": "qwen2.5-coder:7b",
    "name": "👔 Diretor Shared",
    "params": {
        "system": system_prompt
    },
    "meta": {
        "profile_image_url": "",
        "description": "Diretor principal Shared Auto-Dev - Coordena agents, aplica regras e gerencia pipeline.",
        "capabilities": {
            "vision": False,
            "usage": True,
            "web_search": True,
            "code_interpreter": True
        }
    },
    "access_control": None
}

r = session.post(f'{BASE}/api/v1/models/model/update?id=diretor-shared', headers=headers, json=update_data)
print(f'Status: {r.status_code}')
if r.status_code == 200:
    print('✅ Modelo atualizado com system prompt do Diretor!')
    print('\nAgora o modelo diretor-shared vai responder como Diretor.')
    print('Teste com: /equipe, /regras, /status')
else:
    print(f'Erro: {r.text[:300]}')
