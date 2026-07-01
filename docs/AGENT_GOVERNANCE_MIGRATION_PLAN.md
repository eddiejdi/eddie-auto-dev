# Plano de Migração: Agent Governance Layer

**Documento:** Planejamento de longo prazo  
**Data de criação:** 2026-06-28  
**Autor:** Infrastructure Agent  
**Status:** PLANEJAMENTO  
**Versão:** 1.0

---

## Índice

1. [Contexto e Motivação](#1-contexto-e-motivação)
2. [Diagnóstico do Estado Atual](#2-diagnóstico-do-estado-atual)
3. [Visão de Destino](#3-visão-de-destino)
4. [Arquitetura Alvo](#4-arquitetura-alvo)
5. [Fase 0 — Fundação: Action Journal + Tabela de Intenções](#fase-0--fundação-action-journal--tabela-de-intenções)
6. [Fase 1 — Approval Gateway via Telegram](#fase-1--approval-gateway-via-telegram)
7. [Fase 2 — Shared Memory Layer](#fase-2--shared-memory-layer)
8. [Fase 3 — LangGraph para Agentes Novos](#fase-3--langgraph-para-agentes-novos)
9. [Fase 4 — Migração do Coordinator para LangGraph](#fase-4--migração-do-coordinator-para-langgraph)
10. [Fase 5 — Migração Gradual dos Agentes Existentes](#fase-5--migração-gradual-dos-agentes-existentes)
11. [Matriz de Riscos](#11-matriz-de-riscos)
12. [Métricas de Sucesso](#12-métricas-de-sucesso)
13. [Dependências entre Fases](#13-dependências-entre-fases)
14. [Registro de Decisões (ADR)](#14-registro-de-decisões-adr)

---

## 1. Contexto e Motivação

### Problema central

O homelab opera hoje com **15+ agentes especializados rodando em produção de forma autônoma e silenciosa**. O resultado prático:

- Agentes desfazem implantações uns dos outros sem saber
- Não há histórico auditável de "quem fez o quê e por quê"
- O responsável humano não é notificado antes de mudanças no ambiente
- Agentes não compartilham contexto — o que o `nextcloud_agent` sabe sobre o NAS não chega ao `cmdb_agent`
- O bus de comunicação existente tem buffer circular de 1.000 mensagens (não persistente, não consultável)

### Incidentes documentados que motivam este plano

| Data | Incidente | Causa raiz relacionada |
|---|---|---|
| 2026-04-21 | Homelab inacessível após mudança iptables | Agente sem aprovação humana |
| 2026-04-23 | Serviços de produção quarentinados | Agente sem contexto do ambiente |
| 2026-05-23 | Posições de trading liquidadas | Restart de crypto-agent sem confirmação |
| 2026-06-02 | Authentik fora do ar | Chown em volumes sem registro de intenção |

### Oportunidade

A infraestrutura existente já tem componentes que podem ser estendidos:
- `pre_tool_guardrails.py` — já classifica ações por risco
- `telegram_mcp_server.py` — integração Telegram já existe no homelab
- PostgreSQL disponível — base para Action Journal persistente
- ChromaDB em uso — base para memória vetorial
- `homelab_mcp_server.py` — ponto central de extensão de ferramentas MCP

---

## 2. Diagnóstico do Estado Atual

### Inventário de agentes (15 agentes identificados)

| Agente | Arquivo | LOC | Tem aprovação? | Documenta ações? |
|---|---|---|---|---|
| BN Acervo | `bn_acervo_agent.py` | 4.675 | ❌ | ❌ |
| CMDB | `cmdb_agent.py` | 1.666 | ❌ | ❌ |
| Nextcloud | `nextcloud_agent.py` | 1.371 | ❌ | ❌ |
| Wiki | `wiki_agent.py` | 566 | ❌ | ❌ |
| Conube | `conube_agent.py` | 536 | ❌ | ❌ |
| Trading BTC | `trading_agent.py` | ~3.000 | Parcial¹ | Parcial¹ |
| Coordinator | `coordinator.service` | — | ❌ | ❌ |
| Job Monitor | `job-monitor.service` | — | ❌ | ❌ |
| GitHub Agent | `github-agent.service` | — | ❌ | ❌ |
| Ollama GPU Coord | `ollama_gpu_coordinator.py` | — | ❌ | ❌ |
| LTFS Recovery | `ltfs_recovery.py` | — | ❌ | ❌ |
| Notebook Power | `notebook-power-agent.service` | — | ❌ | ❌ |
| Banking Metrics | `banking-metrics-exporter.service` | — | ❌ | ❌ |
| Agent Network Exporter | `agent_network_exporter.py` | 371 | ❌ | ❌ |
| Tape QC Narrator | `tape-quality-ollama-narrator.service` | — | ❌ | ❌ |

> ¹ Trading tem `RiskGuardianMixin` protegendo guardrails de venda, mas não tem approval humano para restarts ou mudanças de config.

### Lacunas críticas no modelo atual

```
[Claude Code]
     ↓ pre_tool_guardrails.py ← ÚNICA proteção existente
     ↓ (protege apenas Claude, não os outros agentes)

[Demais agentes] → agem diretamente → ambiente de produção
                                           ↑
                              sem log, sem aprovação, sem contexto
```

### O que já funciona e deve ser preservado

- **`pre_tool_guardrails.py`** — lógica de classificação por risco é sólida, reutilizar
- **`agent_communication_bus.py`** — pub/sub funciona, usar como camada de eventos
- **`homelab_mcp_server.py`** — ponto de extensão correto para novas ferramentas
- **Telegram MCP** — integração já operacional, apenas estender
- **Secrets Agent** — pipeline de segredos funciona, não alterar

---

## 3. Visão de Destino

Ao final de todas as fases, o homelab terá:

```
┌────────────────────────────────────────────────────────────────┐
│                     VOCÊ (Telegram)                            │
│         ✅ Aprovar   ❌ Rejeitar   💬 Detalhes                 │
└────────────────────────┬───────────────────────────────────────┘
                         │ aprovação antes de qualquer mudança
┌────────────────────────▼───────────────────────────────────────┐
│                  APPROVAL GATEWAY                              │
│  • Recebe intenção do agente                                   │
│  • Envia notificação Telegram (botões + texto livre)           │
│  • Aguarda resposta (timeout = auto-reject seguro)             │
│  • Libera ou bloqueia — registra tudo                          │
└──────────────┬─────────────────────────┬───────────────────────┘
               │                         │
┌──────────────▼──────────┐   ┌──────────▼──────────────────────┐
│    ACTION JOURNAL        │   │      SHARED MEMORY              │
│    (PostgreSQL)          │   │      (Mem0 + ChromaDB)          │
│                          │   │                                  │
│  Registro persistente    │   │  Git commits → indexados        │
│  de toda ação:           │   │  Wiki.js → indexado             │
│   - quem                 │   │  Action Journal → indexado      │
│   - o quê                │   │  Alertas Grafana → indexados    │
│   - quando               │   │                                  │
│   - por quê              │   │  Agentes consultam antes        │
│   - resultado            │   │  de agir                        │
└──────────────────────────┘   └──────────────────────────────────┘
               ▲                         ▲
               │     MCP Tools           │
┌──────────────┴─────────────────────────┴───────────────────────┐
│              homelab_mcp_server.py (estendido)                  │
│                                                                  │
│  intent_declare()        memory_search()                        │
│  intent_check_status()   memory_store()                         │
│  journal_query()         journal_summary()                      │
└─────────┬────────────────────────────────────────┬─────────────┘
          │                                        │
  [Claude Code]                          [Agentes LangGraph]
  [wiki_agent]                           [coordinator (futuro)]
  [nextcloud_agent]                      [novos agentes]
  [cmdb_agent]
  [trading_agent]
```

---

## 4. Arquitetura Alvo

### Componentes novos a criar

| Componente | Tipo | Localização | Depende de |
|---|---|---|---|
| `agent_actions` | Tabela PostgreSQL | DB existente | — |
| `approval_gateway.py` | Serviço Python | `specialized_agents/` | Telegram MCP, PostgreSQL |
| `approval-gateway.service` | systemd | `systemd/` | `approval_gateway.py` |
| Mem0 MCP Server | Docker ou processo | `.mcp.json` | ChromaDB existente |
| `git-memory-ingestor.sh` | Git hook | `.git/hooks/post-commit` | Mem0 |
| Wiki webhook handler | Endpoint FastAPI | `specialized_agents/api.py` | Mem0 |
| Novas ferramentas MCP | Python functions | `homelab_mcp_server.py` | Action Journal, Mem0 |

### Componentes a estender

| Componente | Extensão | Impacto |
|---|---|---|
| `pre_tool_guardrails.py` | Ações CAUTION → Telegram em vez de terminal | Apenas Claude Code |
| `homelab_mcp_server.py` | +6 novas ferramentas MCP | Todos os agentes Claude |
| `telegram_mcp_server.py` | +callback handler para botões inline | Approval Gateway |
| `agent_communication_bus.py` | +drain para PostgreSQL (persistência) | Todos os agentes |

### Componentes que NÃO mudam nesta migração

- `btc_trading_agent/` — estável, não mexer (ver `feedback_btc_trading_safety.md`)
- `secrets_helper.py` e Secrets Agent — pipeline de segredos está correto
- `RiskGuardianMixin` — protegida por policy desde 2026-04-13
- Grafana dashboards existentes — apenas adicionar panels novos

---

## Fase 0 — Fundação: Action Journal + Tabela de Intenções

**Estimativa:** 2–3 dias  
**Pré-requisito:** Nenhum  
**Risco:** Baixo (só cria tabelas e funções, nada é alterado)

### Objetivo

Criar a infraestrutura de dados que todas as fases seguintes irão usar. Sem isso, não há onde registrar intenções nem histórico de aprovações.

### Passos

#### 0.1 — Criar schema no PostgreSQL

```sql
-- Migration: 001_agent_governance.sql

CREATE TABLE agent_actions (
    id                  SERIAL PRIMARY KEY,
    intent_id           TEXT UNIQUE NOT NULL,
    agent_id            TEXT NOT NULL,
    action_type         TEXT NOT NULL,
    -- valores: restart, deploy, modify, delete, create, query, config
    description         TEXT NOT NULL,
    target              TEXT,
    -- serviço, arquivo, host, URL
    risk_level          TEXT NOT NULL DEFAULT 'medium',
    -- valores: none, low, medium, high, critical
    status              TEXT NOT NULL DEFAULT 'pending',
    -- valores: pending, approved, rejected, in_progress, done, failed, expired
    approved_by         TEXT,
    telegram_msg_id     BIGINT,
    context_snapshot    JSONB,
    -- estado da memória e ambiente no momento da declaração
    outcome             TEXT,
    error_detail        TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at         TIMESTAMPTZ,
    executed_at         TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ
);

CREATE INDEX idx_agent_actions_agent_id ON agent_actions(agent_id);
CREATE INDEX idx_agent_actions_status ON agent_actions(status);
CREATE INDEX idx_agent_actions_created_at ON agent_actions(created_at DESC);
CREATE INDEX idx_agent_actions_risk ON agent_actions(risk_level, status);

-- View para auditoria fácil
CREATE VIEW agent_audit_log AS
SELECT
    intent_id,
    agent_id,
    action_type,
    description,
    target,
    risk_level,
    status,
    approved_by,
    EXTRACT(EPOCH FROM (resolved_at - created_at))::INT AS approval_seconds,
    EXTRACT(EPOCH FROM (completed_at - executed_at))::INT AS execution_seconds,
    outcome,
    created_at
FROM agent_actions
ORDER BY created_at DESC;
```

**Arquivo a criar:** `tools/migrations/001_agent_governance.sql`  
**Como executar:** via `mcp__homelab__db_execute_query` ou `psql` direto

#### 0.2 — Adicionar ferramentas MCP ao homelab_mcp_server.py

Novas funções a adicionar em `scripts/homelab_mcp_server.py`:

```python
@mcp.tool()
async def intent_declare(
    agent_id: str,
    action_type: str,
    description: str,
    target: str = None,
    risk_level: str = "medium",
    context: dict = None
) -> dict:
    """
    Declara intenção de ação antes de executá-la.
    Retorna intent_id para uso em intent_check_status().
    Ações com risk_level >= medium ficam em status 'pending' até aprovação.
    Ações com risk_level 'none' ou 'low' são auto-aprovadas.
    """

@mcp.tool()
async def intent_check_status(intent_id: str) -> dict:
    """
    Verifica se uma intenção foi aprovada, rejeitada ou ainda está pendente.
    Agente deve chamar em loop com backoff antes de executar.
    """

@mcp.tool()
async def intent_complete(
    intent_id: str,
    outcome: str,
    error_detail: str = None
) -> dict:
    """
    Marca intenção como concluída (done) ou falhou (failed).
    Deve ser chamado após execução, independente do resultado.
    """

@mcp.tool()
async def journal_query(
    agent_id: str = None,
    action_type: str = None,
    target: str = None,
    status: str = None,
    limit: int = 20
) -> list:
    """
    Consulta o Action Journal. Agentes usam isso para saber
    o que outros agentes já fizeram antes de agir.
    """
```

#### 0.3 — Criar migration runner

**Arquivo a criar:** `tools/migrations/run_migration.py`

Script simples que aplica migrations numeradas em sequência, registrando quais já foram aplicadas em tabela `schema_migrations`.

#### 0.4 — Validação da Fase 0

- [ ] Tabela `agent_actions` criada no PostgreSQL
- [ ] View `agent_audit_log` funcionando
- [ ] `intent_declare()` retorna `intent_id` válido
- [ ] `intent_check_status()` retorna status correto
- [ ] `journal_query()` retorna lista filtrável
- [ ] `intent_complete()` atualiza status e timestamps
- [ ] Auto-aprovação funciona para `risk_level = "none"` e `"low"`

---

## Fase 1 — Approval Gateway via Telegram

**Estimativa:** 3–5 dias  
**Pré-requisito:** Fase 0 completa  
**Risco:** Médio (estende componentes existentes, sem remover nada)

### Objetivo

Qualquer agente que declare uma intenção com `risk_level >= medium` recebe uma notificação Telegram com botões inline. O humano aprova ou rejeita antes da ação acontecer.

### Passos

#### 1.1 — Criar approval_gateway.py

**Arquivo a criar:** `specialized_agents/approval_gateway.py`

Responsabilidades:
- Ouvir a tabela `agent_actions` por registros com `status = 'pending'` (polling ou trigger PostgreSQL LISTEN/NOTIFY)
- Para cada registro pendente, montar e enviar mensagem Telegram formatada
- Receber callbacks de botões inline e atualizar status
- Receber texto livre e adicionar como nota ao registro
- Aplicar timeout automático (padrão: 10 minutos → status `expired` → equivale a rejeição)

**Estrutura da mensagem Telegram:**

```
🤖 [nextcloud_agent] quer executar uma ação

📋 Tipo: restart de serviço
🎯 Alvo: nextcloud.service @ 192.168.15.2
📝 Descrição: Config OIDC atualizada — precisa reload para aplicar
⚠️  Risco: 🟡 MÉDIO

🧠 Contexto relevante da memória:
  • 2026-06-04: nextcloud reiniciado após fix de fstab (OK)
  • 2026-06-02: Authentik fora do ar — NÃO estava relacionado ao Nextcloud

⏰ Expira em: 10 minutos

[✅ Aprovar]  [❌ Rejeitar]  [🔍 Ver detalhes]
```

**Fluxo de texto livre:**
- Usuário manda qualquer texto após ver a notificação
- Gateway interpreta se é aprovação, rejeição ou pergunta
- Se for pergunta, envia contexto adicional via `memory_search()`

**Mapeamento de risco para cor/emoji:**

| risk_level | Emoji | Comportamento |
|---|---|---|
| none | — | Auto-aprovado, sem notificação |
| low | 🟢 | Notifica sem bloquear (informativo) |
| medium | 🟡 | Bloqueia, aguarda aprovação |
| high | 🔴 | Bloqueia, delay 30s antes de enviar |
| critical | 🚨 | Bloqueia, menciona `@edenilson`, delay 60s |

#### 1.2 — Criar systemd service para o gateway

**Arquivo a criar:** `systemd/approval-gateway.service`

```ini
[Unit]
Description=Agent Approval Gateway
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=homelab
WorkingDirectory=/apps/eddie-auto-dev
ExecStart=/apps/eddie-auto-dev/.venv/bin/python -m specialized_agents.approval_gateway
Restart=always
RestartSec=10
Environment=PYTHONPATH=/apps/eddie-auto-dev

[Install]
WantedBy=multi-user.target
```

#### 1.3 — Estender pre_tool_guardrails.py

**Arquivo a modificar:** `tools/copilot_hooks/pre_tool_guardrails.py`

Mudança: ações classificadas como CAUTION (hoje pedem confirmação no terminal) passam a:
1. Chamar `intent_declare()` via MCP
2. Aguardar aprovação Telegram em vez de input no terminal
3. Continuar ou abortar conforme resposta

Isso é uma extensão não-destrutiva: o fluxo de aprovação existente continua funcionando, apenas o canal muda de "terminal" para "Telegram".

#### 1.4 — Documentar contrato de uso para agentes

Criar guia curto em `docs/agents/approval_contract.md` explicando:
- Como declarar intenção antes de agir
- Quais `action_type` existem
- Como interpretar status retornado
- O que fazer quando a aprovação expira

#### 1.5 — Validação da Fase 1

- [ ] Notificação Telegram aparece quando agente declara intenção medium/high/critical
- [ ] Botão ✅ atualiza status para `approved` no banco
- [ ] Botão ❌ atualiza status para `rejected`
- [ ] Botão 🔍 envia contexto adicional ao chat
- [ ] Texto livre é aceito e adicionado como nota
- [ ] Timeout de 10 minutos rejeita automaticamente
- [ ] Agentes com `risk_level low` recebem notificação informativa sem bloquear
- [ ] `pre_tool_guardrails.py` roteia CAUTION para Telegram
- [ ] Ação `critical` menciona usuário no Telegram

---

## Fase 2 — Shared Memory Layer

**Estimativa:** 4–6 dias  
**Pré-requisito:** Fase 0 completa (Fase 1 pode rodar em paralelo)  
**Risco:** Baixo (leitura apenas; não interfere com agentes em operação)

### Objetivo

Criar um banco de memória compartilhada que todos os agentes possam consultar antes de agir. Agentes param de "reinventar a roda" e de desfazer trabalho uns dos outros.

### Passos

#### 2.1 — Avaliar e instalar Mem0

**Decisão a tomar antes de iniciar:** Mem0 self-hosted ou implementação própria sobre ChromaDB existente.

| Opção | Prós | Contras |
|---|---|---|
| **Mem0 self-hosted** | 48k stars, MCP server oficial, multi-store nativo | Dependência externa, container adicional |
| **Implementação própria** | Usa ChromaDB já instalado, sem deps novas | Mais código para manter |

**Recomendação:** Mem0 self-hosted via Docker, com ChromaDB e PostgreSQL já existentes como backends. O MCP server oficial do Mem0 é adicionado ao `.mcp.json` e todos os agentes Claude Code ganham memória imediatamente.

**Arquivo a modificar:** `.mcp.json` — adicionar entrada para Mem0 MCP server

#### 2.2 — Criar ingestores de conhecimento

**a) Git post-commit hook**

**Arquivo a criar:** `tools/memory_ingestors/git_ingestor.sh`

Executado automaticamente após cada commit. Indexa:
- Mensagem do commit
- Lista de arquivos alterados
- Diff resumido (primeiros 500 caracteres por arquivo)
- Branch e autor

**b) Wiki.js webhook handler**

**Arquivo a modificar:** `specialized_agents/api.py` — adicionar endpoint `POST /webhooks/wiki`

Configurar no Wiki.js: webhook em `page:updated` e `page:created` → envia para o endpoint.  
Handler indexa: título, path, conteúdo resumido, tags, data de modificação.

**c) Action Journal ingestor**

**Arquivo a criar:** `tools/memory_ingestors/journal_ingestor.py`

Roda como cronjob a cada hora. Indexa ações `done` e `failed` do Action Journal com contexto: quem fez, o quê, em qual target, qual resultado.

**d) AlertManager webhook**

**Arquivo a modificar:** `specialized_agents/api.py` — adicionar endpoint `POST /webhooks/alerts`

Indexa alertas do Grafana quando disparam e quando resolvem. Permite que agentes saibam "na última semana, o serviço X ficou fora 3 vezes".

#### 2.3 — Adicionar ferramentas MCP de memória

Novas funções a adicionar em `scripts/homelab_mcp_server.py`:

```python
@mcp.tool()
async def memory_search(
    query: str,
    sources: list = None,
    # ["git", "wiki", "journal", "alerts"] — None = todas
    limit: int = 5
) -> list:
    """
    Busca semântica na memória compartilhada do homelab.
    Retorna fatos relevantes com fonte, data e confiança.
    Use antes de agir para saber o que já foi feito.
    """

@mcp.tool()
async def memory_store(
    fact: str,
    source: str,
    tags: list = None,
    agent_id: str = None
) -> dict:
    """
    Registra um fato na memória compartilhada.
    Use após concluir uma ação significativa.
    """

@mcp.tool()
async def memory_context(target: str) -> dict:
    """
    Retorna tudo que a memória sabe sobre um target específico
    (serviço, host, arquivo, componente).
    Atalho para memory_search() com foco em um alvo.
    """
```

#### 2.4 — Criar dashboard Grafana de memória

**Arquivo a criar:** `grafana/dashboards/agent_governance.json`

Panels:
- Ações por agente (últimos 30 dias)
- Aprovadas vs. Rejeitadas vs. Expiradas
- Tempo médio de aprovação por risco
- Timeline de ações por target (quem mexeu no quê, quando)
- Top 10 targets mais acessados

#### 2.5 — Validação da Fase 2

- [ ] `memory_search("nextcloud ltfs")` retorna resultados do git e wiki
- [ ] Post-commit hook indexa commits automaticamente
- [ ] Wiki.js webhook indexa páginas ao atualizar
- [ ] `memory_context("nextcloud.service")` retorna histórico do serviço
- [ ] `memory_store()` persiste e é recuperável via `memory_search()`
- [ ] Dashboard Grafana exibe histórico de ações
- [ ] Agentes conseguem consultar o que outros agentes fizeram

---

## Fase 3 — LangGraph para Agentes Novos

**Estimativa:** Contínuo (a partir do primeiro agente novo após Fase 2)  
**Pré-requisito:** Fases 0, 1 e 2 completas  
**Risco:** Nenhum para o sistema atual (isolado em agentes novos)

### Objetivo

Todo agente **novo** criado a partir desta fase é construído em LangGraph desde o início. Agentes existentes não são tocados ainda. Esta fase estabelece o padrão e acumula experiência com o framework.

### Por que LangGraph para agentes novos

LangGraph oferece três capacidades que justificam o custo de aprendizado:

**1. Interrupt nativo** — o grafo pausa enquanto aguarda aprovação humana e retoma exatamente onde parou, com todo o estado preservado. Sem isso, é preciso implementar polling manual.

**2. Checkpointing** — todo estado intermediário é serializado em disco. Se o processo morrer durante uma operação de 10 passos, recomeça do passo 7, não do zero.

**3. Time-travel debug** — é possível voltar ao estado exato em que o agente tomou uma decisão e re-executar com outra escolha. Crítico para auditar o `trading_agent` e o `ltfs_recovery.py`.

### Passos

#### 3.1 — Instalar e configurar LangGraph

```bash
pip install langgraph langchain-anthropic
```

**Arquivo a criar:** `requirements-langgraph.txt` (separado para não contaminar deps existentes)

Checkpointer a usar: `PostgresSaver` (usa o PostgreSQL já disponível) — não adicionar Redis ou SQLite.

#### 3.2 — Criar template de agente LangGraph

**Arquivo a criar:** `specialized_agents/langgraph_base.py`

Template que todo agente novo herda. Inclui:
- Nó padrão `declare_intent` (integra com Fase 0)
- Nó padrão `await_approval` (integra com Fase 1, usa interrupt)
- Nó padrão `store_memory` (integra com Fase 2)
- Nó padrão `complete_intent`
- Estado base com campos: `agent_id`, `intent_id`, `context`, `memory`

```
Grafo base de todo agente LangGraph:

[START]
   ↓
[analyze]          ← agente pensa e planeja
   ↓
[declare_intent]   ← registra intenção no Action Journal
   ↓
[await_approval]   ← interrupt: aguarda Telegram
   ↓ (aprovado)
[execute]          ← ação específica do agente
   ↓
[store_memory]     ← registra o que foi feito na memória
   ↓
[complete_intent]  ← marca como done/failed no Journal
   ↓
[END]
```

#### 3.3 — Criar o primeiro agente em LangGraph (piloto)

**Candidato sugerido:** agente de rotação de logs do LTO (hoje é um script shell sem state machine)

Motivo: baixo risco, operação bem definida, sem dependências de outros agentes.

**Arquivo a criar:** `specialized_agents/ltfs_log_rotation_agent.py`

Este agente serve como prova de conceito e documentação viva do padrão.

#### 3.4 — Criar guia de desenvolvimento

**Arquivo a criar:** `docs/agents/langgraph_agent_guide.md`

Deve cobrir:
- Como criar um agente novo (passo a passo com o template)
- Como usar `interrupt()` para aprovação humana
- Como integrar com Action Journal e Shared Memory
- Como testar localmente (mock do Telegram)
- Como fazer deploy via systemd

#### 3.5 — Validação da Fase 3

- [ ] Template `langgraph_base.py` funcional com todos os nós padrão
- [ ] Primeiro agente piloto deployado e operando
- [ ] Checkpoint funciona: matar processo e reiniciar retoma de onde parou
- [ ] Interrupt funciona: agente pausa e aguarda aprovação Telegram
- [ ] Time-travel: é possível inspecionar estado histórico via LangGraph Studio ou CLI
- [ ] Guia de desenvolvimento publicado na wiki

---

## Fase 4 — Migração do Coordinator para LangGraph

**Estimativa:** 2–3 semanas  
**Pré-requisito:** Fase 3 completa, pelo menos 2 agentes piloto rodando  
**Risco:** Alto (coordinator.service é central — plano de rollback obrigatório)

### Objetivo

Substituir `coordinator.service` + `job-monitor.service` por um orquestrador LangGraph. Estes dois serviços são o coração da coordenação — migrá-los sem tocar nos agentes folha traz checkpointing e time-travel para toda a orquestração.

### Por que o coordinator primeiro

- É o único ponto que orquestra outros agentes — migrá-lo dá visibilidade sobre todos os fluxos
- Não tem lógica de negócio específica (apenas roteamento e monitoramento)
- Se falhar, os agentes folha continuam operando de forma degradada

### Passos

#### 4.1 — Mapear todos os fluxos do coordinator atual

Antes de qualquer código, documentar em `docs/COORDINATOR_FLOWS.md`:
- Quais agentes o coordinator invoca
- Em que condições
- Dependências entre eles (A deve rodar antes de B?)
- Tratamento de falha atual (retry? notificação? nada?)

#### 4.2 — Implementar coordinator em LangGraph com feature flag

**Arquivo a criar:** `specialized_agents/coordinator_v2.py`

O coordinator novo roda em paralelo com o antigo, controlado por variável de ambiente:

```bash
COORDINATOR_VERSION=v2  # v1 (atual) ou v2 (LangGraph)
```

Inicialmente `v1` em produção. Muda para `v2` após validação.

#### 4.3 — Plano de rollback

- Variável `COORDINATOR_VERSION=v1` reverte imediatamente
- Job monitor antigo permanece ativo como fallback por 30 dias após migração
- Alertas Grafana comparando outputs de v1 e v2 em paralelo antes do corte

#### 4.4 — Corte para v2

Após 7 dias de operação paralela sem divergências:
1. Mudar `COORDINATOR_VERSION=v2` em produção
2. Desabilitar (não remover) `coordinator.service` antigo por 30 dias
3. Monitorar por divergências por mais 7 dias
4. Remover v1 após 30 dias

#### 4.5 — Validação da Fase 4

- [ ] Coordinator v2 em LangGraph operando em paralelo sem divergências por 7 dias
- [ ] Checkpoint testado: kill -9 no processo e verificar retomada correta
- [ ] Time-travel: inspecionar estado de uma orquestração histórica
- [ ] Rollback testado: mudança de v2 para v1 sem perda de jobs em execução
- [ ] `job-monitor.service` substituído pelos observability hooks do LangGraph
- [ ] Dashboard Grafana mostrando estado dos workflows do coordinator

---

## Fase 5 — Migração Gradual dos Agentes Existentes

**Estimativa:** 3–6 meses  
**Pré-requisito:** Fase 4 completa  
**Risco:** Variável por agente (ver tabela de prioridade abaixo)

### Objetivo

Migrar os agentes existentes para LangGraph gradualmente, por ordem de prioridade. Esta fase não tem prazo fixo — cada agente é migrado quando há janela de tempo e motivação (refatoração planejada, bug a corrigir, feature nova).

### Ordem de migração recomendada

Critérios: risco × complexidade × frequência de mudança

| Ordem | Agente | Motivo da prioridade | LOC a migrar | Risco |
|---|---|---|---|---|
| 1 | `wiki_agent.py` | Menor, bem definido, baixo risco | 566 | Baixo |
| 2 | `cmdb_agent.py` | Alto valor (inventário), sem lógica financeira | 1.666 | Médio |
| 3 | `nextcloud_agent.py` | Integra com muitos sistemas, checkpointing útil | 1.371 | Médio |
| 4 | `conube_agent.py` | Automação web (Selenium), state machine natural | 536 | Médio |
| 5 | `bn_acervo_agent.py` | Maior e mais complexo, migrar por último | 4.675 | Alto |
| — | `trading_agent.py` | **NÃO migrar** sem revisão profunda e janela dedicada | ~3.000 | Crítico |

> **Nota sobre o trading_agent:** ver `feedback_btc_trading_safety.md`. Qualquer migração do trading agent exige: dry_run=True por 2 semanas mínimo, revisão do RiskGuardianMixin, aprovação explícita do usuário antes de ativar em produção.

### Padrão de migração por agente

Para cada agente, seguir este checklist:

```
[ ] 1. Criar versão v2 em arquivo separado (ex: wiki_agent_v2.py)
[ ] 2. Mapear fluxos existentes em grafo LangGraph
[ ] 3. Implementar com template langgraph_base.py (Fase 3)
[ ] 4. Rodar em paralelo com v1 por 7 dias (feature flag)
[ ] 5. Validar outputs idênticos entre v1 e v2
[ ] 6. Cortar para v2, manter v1 por 30 dias
[ ] 7. Remover v1 após 30 dias sem incidentes
[ ] 8. Atualizar documentação na wiki
```

---

## 11. Matriz de Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Approval Gateway fica fora do ar durante incidente urgente | Média | Alto | Modo bypass por variável de ambiente `APPROVAL_GATEWAY_BYPASS=true`; alertas monitora o serviço |
| Timeout de aprovação Telegram bloqueia operação crítica | Baixa | Alto | Timeout configurável por `risk_level`; ações `critical` têm bypass manual via SSH |
| Mem0 indexa informação sensível (tokens, senhas) | Média | Crítico | Sanitizador antes de indexar (mascarar padrões de token/senha); Mem0 não indexa `secrets_agent` |
| LangGraph coordinator perde jobs em andamento durante migração | Baixa | Alto | Feature flag; migração em janela de manutenção; rollback em 1 min |
| Mem0 fica fora de sincronia com o estado real do ambiente | Alta | Médio | Memória é contexto, não verdade — agentes sempre verificam estado real antes de agir |
| Agente em LangGraph entra em loop aguardando aprovação infinita | Baixa | Médio | `intent_check_status()` verifica `expired`; agente aborta após timeout |
| Migração do trading_agent introduz bug em guardrails | Muito Baixa | Crítico | Trading_agent na última ordem, dry_run obrigatório, sem deadline |

---

## 12. Métricas de Sucesso

### Fase 0 (Action Journal)
- 100% das intenções declaradas persistem no banco
- Latência de `intent_declare()` < 100ms
- `journal_query()` retorna resultados em < 500ms

### Fase 1 (Telegram Approval)
- 0 ações com `risk_level >= medium` executadas sem registro no banco
- Taxa de resposta humana em < 5 minutos para > 80% das notificações
- 0 falsos positivos (notificações para ações de leitura)
- Approval Gateway uptime > 99.5%

### Fase 2 (Shared Memory)
- Agentes consultam `memory_search()` antes de agir em > 90% das ações medium+
- Git commits indexados em < 30 segundos após push
- Wiki pages indexadas em < 60 segundos após atualização
- Redução de 50% em incidentes do tipo "agente desfez trabalho de outro agente"

### Fase 3 (LangGraph novos agentes)
- Primeiro agente piloto rodando sem incidentes por 30 dias
- Checkpointing testado e documentado
- 0 agentes novos criados fora do padrão LangGraph após esta fase

### Fase 4 (Coordinator)
- Coordinator v2 em produção por 30 dias sem rollback
- Time-travel debug usado com sucesso em pelo menos 1 incidente real
- `job-monitor.service` descomissionado

### Fase 5 (Migração agentes existentes)
- Cada agente migrado: 30 dias sem incidente pós-migração
- 0 regressões documentadas
- Todos os agentes migrados têm aprovação Telegram funcional

---

## 13. Dependências entre Fases

```
Fase 0 ──────────────────────────────────────┐
  (Action Journal + MCP tools)               │
                                             ▼
Fase 0 ──────────► Fase 1                Fase 2
                   (Telegram)            (Memória)
                       │                    │
                       └─────────┬──────────┘
                                 ▼
                              Fase 3
                           (LangGraph novos)
                                 │
                                 ▼
                              Fase 4
                           (Coordinator)
                                 │
                                 ▼
                              Fase 5
                        (Migração existentes)
```

**Fases 1 e 2 podem ser executadas em paralelo** após a Fase 0 estar completa.

**Fase 3 pode iniciar** assim que as Fases 1 e 2 estiverem estáveis (não precisa esperar 100% completas).

**Fases 4 e 5 são sequenciais** — coordinator primeiro, depois agentes folha.

---

## 14. Registro de Decisões (ADR)

### ADR-001: PostgreSQL como backend principal do Action Journal

**Data:** 2026-06-28  
**Status:** Aceito  
**Contexto:** Precisávamos de um store persistente para o Action Journal. Opções: PostgreSQL (já disponível), SQLite, Redis.  
**Decisão:** PostgreSQL — já está instalado, já tem dados dos agentes, suporta JSONB para `context_snapshot`, e `LISTEN/NOTIFY` para notificações de novos registros pendentes.  
**Consequência:** Sem nova dependência de infraestrutura. Se o PostgreSQL ficar fora do ar, o Approval Gateway também fica — mitigado com alertas no Prometheus.

### ADR-002: Mem0 como Shared Memory Layer (avaliação pendente)

**Data:** 2026-06-28  
**Status:** Proposto — avaliar antes de iniciar Fase 2  
**Contexto:** Mem0 oferece MCP server oficial, integração com ChromaDB e PostgreSQL (já existentes), e multi-store nativo. Alternativa é implementação própria sobre ChromaDB.  
**Decisão pendente:** Validar se o Mem0 MCP server funciona com Claude Code sem modificações; se sim, adotar. Se não, implementar wrapper próprio sobre ChromaDB existente.

### ADR-003: trading_agent fora do escopo de migração LangGraph

**Data:** 2026-06-28  
**Status:** Aceito  
**Contexto:** Trading agent opera 24/7 com dinheiro real. `dry_run=False` na config padrão. RiskGuardianMixin tem histórico de proteção crítica (incidente 2026-04-13).  
**Decisão:** Trading agent não entra no roadmap de migração LangGraph sem: (1) janela de manutenção dedicada, (2) dry_run=True por mínimo 2 semanas, (3) aprovação explícita do usuário. Não tem prazo definido.

### ADR-004: Approval Gateway como serviço independente (não embutido nos agentes)

**Data:** 2026-06-28  
**Status:** Aceito  
**Contexto:** Poderíamos embutir a lógica de aprovação em cada agente individualmente, ou criar um serviço centralizado.  
**Decisão:** Serviço centralizado (`approval_gateway.py`). Motivo: agentes existentes não precisam ser modificados para ganhar aprovação — apenas passam a declarar intenções via MCP. O gateway ouve o banco e envia Telegram de forma independente.  
**Consequência:** Se o gateway cair, intenções ficam em `pending` indefinidamente. Mitigado com: alertas no Prometheus + modo bypass para emergências.

### ADR-005: LangGraph checkpointer via PostgresSaver (não SQLite/Redis)

**Data:** 2026-06-28  
**Status:** Proposto  
**Contexto:** LangGraph suporta múltiplos checkpointers. PostgreSQL já disponível.  
**Decisão:** Usar `PostgresSaver` — mesma instância do banco existente, sem adicionar Redis ou SQLite ao stack.  
**Consequência:** Checkpoint e Action Journal no mesmo banco. Simplicidade operacional em troca de acoplamento — aceitável dado que PostgreSQL já é dependência crítica.

---

## Apêndice A — Comandos de referência rápida

```bash
# Verificar Action Journal
psql -c "SELECT * FROM agent_audit_log LIMIT 10;"

# Verificar intenções pendentes
psql -c "SELECT intent_id, agent_id, description, created_at FROM agent_actions WHERE status = 'pending';"

# Forçar aprovação de emergência (bypass Telegram)
psql -c "UPDATE agent_actions SET status='approved', approved_by='bypass-emergency' WHERE intent_id='...';"

# Reiniciar Approval Gateway
systemctl restart approval-gateway

# Ver logs do Approval Gateway
journalctl -u approval-gateway -f

# Modo bypass de emergência (desativa bloqueio de aprovação)
APPROVAL_GATEWAY_BYPASS=true systemctl restart approval-gateway
```

## Apêndice B — Referências

- [LangGraph Docs — Human in the Loop](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/)
- [LangGraph PostgresSaver](https://langchain-ai.github.io/langgraph/how-tos/persistence-postgres/)
- [Mem0 MCP Server](https://github.com/mem0ai/mem0/tree/main/mcp)
- [python-telegram-bot — InlineKeyboard](https://github.com/python-telegram-bot/python-telegram-bot/wiki/InlineKeyboard-Example)
- `docs/ARCHITECTURE.md` — arquitetura atual do homelab
- `tools/copilot_hooks/pre_tool_guardrails.py` — guardrails existentes
- `scripts/homelab_mcp_server.py` — MCP server a estender
- `feedback_btc_trading_safety.md` — restrições do trading agent
