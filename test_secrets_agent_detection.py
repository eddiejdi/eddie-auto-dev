#!/usr/bin/env python3
"""
Teste rápido: verifica se o worker detectaria tickets do secrets_agent
"""
import json
import sys
sys.path.insert(0, '/home/edenilson/eddie-auto-dev')

# Ler board JSON diretamente (sem dependências pesadas)
with open('agent_data/jira/jira_rpa4all.json', 'r') as f:
    board_data = json.load(f)

# Simular a lógica do worker
print("🔍 Simulando lógica do worker...\n")

# 1. Verificar team_members
team_members = board_data['project']['team_members']
print(f"👥 Team members ({len(team_members)}):")
for member in team_members:
    marker = "✅" if member in ['secrets_agent', 'po_agent', 'bpm_agent', 'home_agent'] else "  "
    print(f"  {marker} {member}")

# 2. Lista de agentes que seriam consultados
# Linguagens disponíveis (hardcoded para evitar import pesado)
available_langs = {'python', 'javascript', 'typescript', 'go', 'rust', 'java', 'csharp', 'php'}
agent_names = set(f"{lang}_agent" for lang in available_langs)
agent_names.update(team_members)

print(f"\n🤖 Agentes que serão consultados ({len(agent_names)}):")
for agent in sorted(agent_names):
    marker = "✅" if agent in ['secrets_agent', 'po_agent', 'bpm_agent', 'home_agent'] else "  "
    print(f"  {marker} {agent}")

# 3. Verificar tickets do secrets_agent
tickets_data = board_data['tickets']
# tickets pode ser dict {key: ticket_data} ou list[ticket_data]
if isinstance(tickets_data, dict):
    tickets = list(tickets_data.values())
else:
    tickets = tickets_data

secrets_tickets = [t for t in tickets if isinstance(t, dict) and t.get('assignee') == 'secrets_agent']

print(f"\n📋 Tickets atribuídos ao secrets_agent ({len(secrets_tickets)}):")
for t in secrets_tickets:
    print(f"  ✅ {t['key']}: {t['title'][:60]} ({t['status']})")

# 4. Conclusão
print(f"\n{'='*60}")
if 'secrets_agent' in agent_names and len(secrets_tickets) > 0:
    print("✅ SUCESSO: Worker detectaria tickets do secrets_agent!")
    print(f"   - secrets_agent está nos agent_names")
    print(f"   - {len(secrets_tickets)} ticket(s) disponível(is) para processamento")
else:
    print("❌ FALHA: Worker NÃO detectaria tickets do secrets_agent")
    if 'secrets_agent' not in agent_names:
        print("   - secrets_agent NÃO está nos agent_names")
    if len(secrets_tickets) == 0:
        print("   - Nenhum ticket atribuído ao secrets_agent")
print('='*60)
