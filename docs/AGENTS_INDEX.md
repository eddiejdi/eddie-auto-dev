# 📚 Índice de Agentes e Documentação

> Gerado automaticamente por `agent_documentation_manager.py`

## Agentes Descobertos


### `home_automation/`

- ❌ **GoogleAssistantAgent** — Google Assistant Agent — controla automações residenciais via Google Home.
  - 🔐 Secrets: url

### `homelab_recovery/`

- ❌ **** — (sem desc)
- ❌ **** — (sem desc)
  - 🔐 Secrets: url

### `jira/`

- ❌ **JiraAgentMixin** — Jira Agent Mixin — Integração dos agentes especializados com o Jira RPA4ALL.
- ❌ **ProductOwnerAgent** — Product Owner Agent — Agente PO para o Jira RPA4ALL.

### `secrets_agent/`

- ❌ **** — Secrets Agent — gateway unificado para secrets com auto-unlock Bitwarden.
  - 🔐 Secrets: url

### `specialized_agents/`

- ❌ **BPMAgent** — Agente Especializado em BPM e Desenhos Técnicos
  - 🔐 Secrets: url
- ❌ **BankingAgent** — Banking Integration Agent — Eddie Auto-Dev
- ❌ **ConfluenceAgent** — Agente Especializado em Confluence
  - 🔐 Secrets: url
- ❌ **DataAgent** — Data Agent para Eddie Auto-Dev
  - 🔐 Secrets: url
- ❌ **LLMSubAgent** — Agente Base Especializado
- ❌ **OpenSearchAgent** — OpenSearch Agent — Agente especializado em OpenSearch
- ❌ **PerformanceAgent** — Performance Agent para Eddie Auto-Dev
  - 🔐 Secrets: url
- ❌ **PythonAgent** — Agentes Especializados por Linguagem
- ❌ **QwenImageAgent** — Agente Qwen de Geração de Imagem
- ❌ **ReviewAgent** — ReviewAgent — Agente especializado em Quality Gate + CI/CD Review
- ❌ **SecurityAgent** — Security Agent para Eddie Auto-Dev
  - 🔐 Secrets: secret, url
- ❌ **** — Agent Chat - Interface de Chat com Agentes Especializados
- ❌ **** — Agent Communication Bus
- ❌ **** — Agent Conversation Interceptor
- ❌ **** — Gerenciador de Agentes
  - 🔐 Secrets: url
- ❌ **** — Integration helpers for AgentManager (minimal stubs).
- ❌ **** — Agent Memory System - Memória Persistente para Agentes
- ❌ **** — Agent Communication Monitor
  - 🔐 Secrets: url
- ❌ **** — Agent Network Metrics Exporter
- ❌ **** — Agent bridge: consume LLM requests from the Agent Communication Bus and
- ✅ **** — Agent responder for coordinator test broadcasts.
- ❌ **** — Ponte de integração entre Agentes Especializados e OpenWebUI
- ❌ **** — (sem desc)
- ❌ **** — Agent Instrutor - Treinamento Automático dos Agents

### `tools/`

- ❌ **SecretsAgentClient** — Client para consumir dados do Secrets Agent.
  - 🔐 Secrets: api_key, key
- ❌ **** — Simple client for local Agent RCA API.
- ❌ **** — Agent Documentation Manager
- ❌ **** — Simple DB-backed agent IPC helper using PostgreSQL.
- ❌ **** — Collect agent responses from the local AgentCommunicationBus for a short period.
- ❌ **** — (sem desc)
  - 🔐 Secrets: password
- ❌ **** — OperationsAgent (standalone) - DB-backed and bus-backed remediation handler.
- ❌ **** — Desk tests para validar os 13 bugs corrigidos
- ❌ **** — Mega-patch para trading_agent.py — corrige 13 bugs identificados na revisão completa.
- ❌ **** — Trigger documentation agents: BPMAgent and ConfluenceAgent.
- ❌ **** — Watch agent stdout (systemd + local log files) and stream updates.

### `x_agent/`

- ❌ **** — X Agent — serviço FastAPI para interação com X.com (Twitter).
  - 🔐 Secrets: url


## 📊 Estatísticas

- Total de agentes: **42**
- Documentados: **1** ✅
- Não documentados: **41** ❌
- Cobertura: **2.4%**
