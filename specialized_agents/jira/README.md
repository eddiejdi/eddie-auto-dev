# Jira RPA4ALL — Sistema de Gerenciamento de Projetos

Sistema integrado de gerenciamento de projetos, tickets, sprints e apontamento de horas para a empresa **RPA4ALL**, conectado a todos os agentes especializados do Eddie.

## Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                     Jira RPA4ALL                        │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │  Epics   │  │ Sprints  │  │ Tickets  │             │
│  └──────────┘  └──────────┘  └──────────┘             │
│       │              │             │                    │
│  ┌────┴──────────────┴─────────────┴────┐              │
│  │           JiraBoard (Core)           │              │
│  │  CRUD · Persistência · Métricas      │              │
│  └──────────────────────────────────────┘              │
│       │                    │                            │
│  ┌────┴────┐   ┌──────────┴──────────┐                │
│  │PO Agent │   │  JiraAgentMixin     │                │
│  │(Product │   │  (herança em todos  │                │
│  │ Owner)  │   │  os agentes)        │                │
│  └─────────┘   └─────────────────────┘                │
│                        │                                │
│  ┌─────────────────────┴────────────────────────────┐  │
│  │ Python · JS · TS · Go · Rust · Java · C# · PHP   │  │
│  │           (todos com Jira integrado)              │  │
│  └───────────────────────────────────────────────────┘  │
│                        │                                │
│  ┌─────────────────────┴──────────────┐                │
│  │    AgentCommunicationBus           │                │
│  │    (eventos publicados via bus)    │                │
│  └────────────────────────────────────┘                │
└─────────────────────────────────────────────────────────┘
```

## Componentes

### 1. JiraBoard (`jira_board.py`)
Core do sistema — gerencia projeto, epics, sprints, tickets e worklogs com persistência em JSON.

### 2. PO Agent (`po_agent.py`)
Agente Product Owner que:
- Cria Epics com Stories detalhadas
- Planeja Sprints (auto-seleção por prioridade)
- Distribui tickets entre agentes por skills
- Revisa e aceita/rejeita entregas
- Gera relatórios (daily standup, sprint report, burndown)
- Usa LLM para criar tarefas a partir de descrição de projeto

### 3. JiraAgentMixin (`agent_mixin.py`)
Mixin integrado ao `SpecializedAgent` base. Todos os agentes herdam automaticamente:
- `jira_my_tickets()` — tickets atribuídos
- `jira_next_ticket()` — próximo ticket por prioridade
- `jira_start_ticket(id)` — move para IN_PROGRESS
- `jira_log_work(id, desc, minutes)` — apontamento de horas
- `jira_auto_log(id, desc, start_time)` — auto-apontamento
- `jira_submit_for_review(id)` — envia para review do PO
- `jira_agent_summary()` — resumo de atividade

### 4. API REST (`routes.py`)
Endpoints em `/jira/*` na API FastAPI (porta 8503).

## Uso Rápido

### Criar Epic + Stories (via API)
```bash
curl -X POST http://localhost:8503/jira/epics/with-stories \
  -H 'Content-Type: application/json' \
  -d '{
    "epic_title": "Sistema de Autenticação",
    "epic_description": "Auth completo com OAuth2",
    "stories": [
      {"title": "API de Login", "labels": ["python", "fastapi"], "points": 5},
      {"title": "Frontend OAuth", "labels": ["typescript", "nextjs"], "points": 3}
    ]
  }'
```

### Criar ticket
```bash
curl -X POST http://localhost:8503/jira/tickets \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "Implementar endpoint de pagamento",
    "description": "Critérios de Aceitação:\n- Aceitar PIX\n- Aceitar cartão",
    "priority": "high",
    "assignee": "python_agent",
    "story_points": 5,
    "labels": ["python", "api"]
  }'
```

### Planejar Sprint (auto-seleção)
```bash
curl -X POST http://localhost:8503/jira/sprints/plan \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Sprint 1",
    "goal": "Entregar MVP de auth",
    "auto_select": true,
    "duration_days": 14
  }'
```

### Apontar horas
```bash
curl -X POST http://localhost:8503/jira/tickets/{ticket_id}/worklogs \
  -H 'Content-Type: application/json' \
  -d '{
    "agent_name": "python_agent",
    "description": "Implementação do endpoint",
    "time_spent_minutes": 120
  }'
```

### Obter tickets de um agente
```bash
curl http://localhost:8503/jira/agents/python_agent/tickets
curl http://localhost:8503/jira/agents/python_agent/next
curl http://localhost:8503/jira/agents/python_agent/summary
```

### Daily Standup Report
```bash
curl http://localhost:8503/jira/po/standup
```

### PO auto-cria tarefas via LLM
```bash
curl -X POST http://localhost:8503/jira/po/auto-create \
  -H 'Content-Type: application/json' \
  -d '{"project_description": "Criar um sistema de RPA que automatize o processo de faturamento com integração SAP e envio de NF-e"}'
```

## Uso no Código (agentes)

```python
from specialized_agents.language_agents import PythonAgent

agent = PythonAgent()

# Ver meus tickets
tickets = agent.jira_my_tickets()

# Pegar próximo ticket
next_ticket = agent.jira_next_ticket()

# Começar a trabalhar
agent.jira_start_ticket(next_ticket["id"])

# Apontar horas
agent.jira_log_work(next_ticket["id"], "Codificação da API", 90)

# Auto-log (calcula duração automaticamente)
from datetime import datetime
start = datetime.now()
# ... trabalho ...
agent.jira_auto_log(next_ticket["id"], "Build e testes", start)

# Submeter para review do PO
agent.jira_submit_for_review(next_ticket["id"], "Implementação completa, testes OK")

# Resumo do agente
summary = agent.jira_agent_summary()
```

## Uso do PO Agent

```python
from specialized_agents.jira import ProductOwnerAgent

po = ProductOwnerAgent()

# Status geral
po.get_status()

# Criar Epic com Stories
import asyncio
result = asyncio.run(po.create_epic_with_stories(
    "Microserviço de Pagamentos",
    "Serviço independente de processamento de pagamentos",
    stories=[
        {"title": "Gateway PIX", "labels": ["python", "api"], "points": 5},
        {"title": "Gateway Cartão", "labels": ["java", "spring"], "points": 8},
        {"title": "Dashboard pagamentos", "labels": ["typescript", "nextjs"], "points": 3},
    ]
))

# Planejar sprint
sprint = asyncio.run(po.plan_sprint("Sprint 2", "Pagamentos MVP", auto_select=True))

# Distribuir tickets
assignments = asyncio.run(po.distribute_tickets())

# Revisar entrega
asyncio.run(po.review_delivery("ticket_id", accept=True, feedback="Excelente!"))
```

## Métricas e Board
```bash
# Métricas gerais
curl http://localhost:8503/jira/metrics

# Relatório do sprint
curl http://localhost:8503/jira/po/sprint-report
```

## Testes
```bash
pytest tests/test_jira_rpa4all.py -v
```

## Persistência
Dados salvos em `agent_data/jira/jira_rpa4all.json`. O bus de comunicação também propaga eventos para o interceptor (SQLite/Postgres).
