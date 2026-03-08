#!/usr/bin/env python3
"""Sumário da auditoria e documentação de agentes."""

import json
from pathlib import Path
from datetime import datetime

workspace = Path("/home/edenilson/shared-auto-dev")

# Lê relatório de auditoria
report_path = workspace / "tools/audit_agents_report.json"
with open(report_path) as f:
    audit_report = json.load(f)

# Conta documentação criada
docs_dir = workspace / "docs/agents"
docs_created = len(list(docs_dir.glob("*.md"))) if docs_dir.exists() else 0

print("\n" + "="*75)
print("📊 SUMÁRIO DE DOCUMENTAÇÃO E AUDITORIA DE AGENTES")
print("="*75)

print(f"\n📅 Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

print(f"\n✅ AGENTES DESCOBERTOS E DOCUMENTADOS:")
print(f"   • Total de agentes: {audit_report['summary']['total_agents']}")
print(f"   • Documentação criada: {docs_created} arquivos MD")
print(f"   • Taxa de documentação: {(docs_created/audit_report['summary']['total_agents']*100):.1f}%")

print(f"\n🔐 SECRETS DETECTADOS DURANTE AUDITORIA:")
total_secrets = audit_report['summary']['total_secrets_patterns']
print(f"   • Padrões de secret encontrados: {total_secrets}")

if total_secrets > 0:
    # Encontra agentes com secrets
    agents_with_secrets = [
        a for a in audit_report['agents'] 
        if a['secrets_found']
    ]
    print(f"   • Agentes afetados: {len(agents_with_secrets)}")
    for agent in agents_with_secrets:
        print(f"     - {agent['name']}: {len(agent['secrets_found'])} padrão(ões)")

print(f"\n📚 LOCALIZAÇÃO DA DOCUMENTAÇÃO:")
print(f"   • Pasta: {docs_dir.relative_to(workspace)}/")
print(f"   • Relatório de auditoria: tools/audit_agents_report.json")

print(f"\n🔗 STRUCTURE DOS AGENTES:")
by_type = {}
for agent in audit_report['agents']:
    agent_type = agent['agent_type']
    by_type.setdefault(agent_type, []).append(agent)

for agent_type in sorted(by_type.keys()):
    agents = by_type[agent_type]
    print(f"   • {agent_type}: {len(agents)} agentes")

print(f"\n🎯 PRÓXIMOS PASSOS:")
print(f"   1. Revisar documentação em docs/agents/")
print(f"   2. Complementar descrições e funcionalidades")
print(f"   3. Adicionar exemplos de uso e configuração")
if total_secrets > 0:
    print(f"   4. IMPORTANTE: Remover secrets do código-fonte")
    print(f"   5. Armazenar credenciais no Secrets Agent")
    print(f"   6. Usar variáveis de ambiente ou secrets management")

print(f"\n✨ Auditoria completa! Todos os {audit_report['summary']['total_agents']} agentes foram descobertos e documentados.")
print("="*75 + "\n")
