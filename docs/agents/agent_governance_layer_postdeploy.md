# Agent Governance Layer — Documentação Pós-Deploy

**Data de deploy:** 2026-06-28
**Branch:** `fix/btc-panel114-calendar`
**Status:** Fase 0–5 completas. Todos os agentes em modo `v1` (feature flags desativadas).

---

## O que foi entregue

O homelab operava com 15+ agentes autônomos e silenciosos — sem log auditável, sem aprovação humana, sem contexto compartilhado. Este projeto implementou uma **camada de governança** completa em 5 fases, sem quebrar nenhum agente existente em produção.

---

## Arquitetura implantada

```
                    VOCÊ (Telegram)
                  ✅ Aprovar  ❌ Rejeitar
                        │
              ┌─────────▼──────────┐
              │  Approval Gateway  │
              │  approval-gateway  │
              │  .service :8510    │
              └─────────┬──────────┘
                        │
         ┌──────────────▼──────────────────┐
         │         HomelabAgent            │
         │         (langgraph_base.py)     │
         │                                 │
         │  declare_intent                 │
         │    → agent_actions (PostgreSQL) │
         │  [await_approval se risk≥medium]│
         │  execute                        │
         │  store_memory (ChromaDB)        │
         │  complete_intent                │
         └─────────────────────────────────┘
```

---

## Fases e arquivos criados

### Fase 0+1 — Action Journal + Approval Gateway

| Arquivo | Descrição |
|---|---|
| `specialized_agents/approval_gateway.py` | Serviço Telegram: envia botões inline, aguarda aprovação |
| `systemd/approval-gateway.service` | Serviço systemd (ativo em produção) |
| Tabela `agent_actions` | PostgreSQL — registro de toda intenção declarada |

**Como funciona:** o agente declara uma intenção antes de agir. Se `risk=medium` ou `high`, o Approval Gateway envia mensagem Telegram com botões ✅/❌. O agente fica suspenso via `interrupt_before=["await_approval"]` até a resposta.

---

### Fase 2 — Shared Memory Layer

| Arquivo | Descrição |
|---|---|
| `specialized_agents/langgraph_base.py` | `_memory_store()` — indexa fatos no ChromaDB |
| Ingestores de git/wiki | Post-commit hook, webhook handler |

---

### Fase 3 — LangGraph Base Template + Agentes Piloto

**Arquivo central:** `specialized_agents/langgraph_base.py`

#### Classe `HomelabAgent` (base para todos os agentes)

```python
class MeuAgente(HomelabAgent):
    AGENT_ID    = "meu_agente"
    ACTION_TYPE = "minha_acao"
    RISK_LEVEL  = "low"   # low | medium | high | critical

    def _describe_work(self, state: AgentState) -> str:
        return f"Descrição da ação: {state['target']}"

    def _execute_work(self, state: AgentState) -> dict:
        # lógica de negócio aqui
        return {"outcome": "...", "memory_fact": "..."}
```

**Grafo de estados:**
```
START → declare_intent → [await_approval*] → execute → store_memory → complete_intent → END
                                  ↑ interrupt aqui se risk≥medium
```

**API pública:**
```python
agent = MeuAgente()

# Executar (bloqueia se precisar de aprovação)
state = agent.run(target="descricao", extra={"param": "valor"})

# Retomar após aprovação Telegram
state = agent.resume(thread_id="...")

# Time-travel debug
history = agent.get_history(thread_id="...")

# Liberar recursos
agent.close()
```

**Checkpointing:** usa `PostgresSaver.from_conn_string(DATABASE_URL)`. Se o processo morrer durante uma investigação longa, basta chamar `agent.resume(thread_id)` para continuar do ponto exato.

**Agentes piloto criados:**

| Arquivo | Agente | Risk | Scheduler |
|---|---|---|---|
| `specialized_agents/ltfs_log_rotation_agent.py` | `LtfsLogRotationAgent` | low/medium | `systemd/ltfs-log-rotation.timer` (03:00 diário) |
| `specialized_agents/alert_digest_agent.py` | `AlertDigestAgent` | low | manual / cron |

---

### Fase 4 — Coordinator v2 em LangGraph

| Arquivo | Descrição |
|---|---|
| `specialized_agents/coordinator_langgraph.py` | Reimplementação do coordinator em LangGraph |
| `docs/COORDINATOR_FLOWS.md` | Mapa de fluxos do coordinator v1, invariantes, plano de cutover |
| `systemd/coordinator-agent.service.d/coordinator-version.conf` | Drop-in com `COORDINATOR_VERSION=v1` |
| `tools/start_coordinator.sh` | Script de start com seleção por feature flag |

**Para ativar o coordinator v2:**
```bash
# No homelab:
sudo sed -i 's/COORDINATOR_VERSION=v1/COORDINATOR_VERSION=v2/' \
  /etc/systemd/system/coordinator-agent.service.d/coordinator-version.conf
sudo systemctl daemon-reload && sudo systemctl restart coordinator-agent
```

**Para rollback:**
```bash
sudo sed -i 's/COORDINATOR_VERSION=v2/COORDINATOR_VERSION=v1/' \
  /etc/systemd/system/coordinator-agent.service.d/coordinator-version.conf
sudo systemctl daemon-reload && sudo systemctl restart coordinator-agent
```

---

### Fase 5 — Migração Gradual dos Agentes Existentes

Todos os agentes existentes receberam wrapper de governança. Cada um tem sua **feature flag** independente — padrão `v1` (produção inalterada).

| Agente | Wrapper LangGraph | Feature Flag | Sub-agentes criados |
|---|---|---|---|
| Wiki | `wiki_agent_langgraph.py` | `WIKI_AGENT_VERSION` | `WikiPublishAgent` (low), `WikiEvolveAgent` (low) |
| CMDB | `cmdb_agent_langgraph.py` | `CMDB_AGENT_VERSION` | `CmdbRunAgent` (low), `CmdbApplyNetboxAgent` (low/medium), `CmdbApplyGlpiAgent` (low/medium) |
| Nextcloud | `nextcloud_agent_langgraph.py` | `NEXTCLOUD_AGENT_VERSION` | `NextcloudChatAgent` (medium), `NextcloudOccAgent` (medium), `NextcloudFileUploadAgent` (medium), `NextcloudShareCreateAgent` (medium), `NextcloudVpnAgent` (high) |
| Conube | `conube_agent_langgraph.py` | `CONUBE_AGENT_VERSION` | `ConubeTestLoginAgent` (medium), `ConubeDailySummaryAgent` (medium) |
| BN Acervo | `bn_acervo_agent_langgraph.py` | `BN_ACERVO_AGENT_VERSION` | `BnAcervoStoryAgent` (medium), `BnAcervoDossierAgent` (medium), `BnAcervoJobAgent` (medium), `BnAcervoCancelAgent` (medium) |

**Risk levels por agente/operação:**

| Risk | Comportamento |
|---|---|
| `low` | Executa direto, sem interrução, sem Telegram |
| `medium` | Pausa e envia Telegram para aprovação |
| `high` | Pausa obrigatória, sem timeout automático |
| `critical` | Sempre bloqueado até aprovação explícita |

---

## Pré-requisitos de runtime

```
# requirements-langgraph.txt
langgraph
langchain-anthropic
langgraph-checkpoint-postgres
```

**Variáveis de ambiente (via `/etc/default/eddie-common`):**

| Variável | Obrigatória | Descrição |
|---|---|---|
| `DATABASE_URL` | Sim | PostgreSQL para checkpointer e `agent_actions` |
| `CHROMA_DB_PATH` | Não | ChromaDB path (default `/home/homelab/myClaude/chroma_db`) |
| `TELEGRAM_BOT_TOKEN` | Para approvals | Token do bot Telegram |
| `TELEGRAM_CHAT_ID` | Para approvals | Chat ID de notificações |

---

## Como ativar governança em produção

**Passo a passo recomendado (7 dias por agente):**

1. Ativar apenas `WIKI_AGENT_VERSION=v2` (menor risco — operações low)
2. Observar durante 7 dias: `agent_actions` no PostgreSQL, Telegram, ChromaDB
3. Ativar próximo agente (`CMDB_AGENT_VERSION=v2`)
4. Repetir para os demais na ordem: `NEXTCLOUD_AGENT_VERSION`, `CONUBE_AGENT_VERSION`, `BN_ACERVO_AGENT_VERSION`
5. Ativar coordinator por último (`COORDINATOR_VERSION=v2`)

**Para um agente específico:**
```bash
# Via drop-in systemd (método recomendado para specialized-agents-api):
sudo mkdir -p /etc/systemd/system/specialized-agents-api.service.d/
cat | sudo tee /etc/systemd/system/specialized-agents-api.service.d/governance.conf <<'EOF'
[Service]
Environment="WIKI_AGENT_VERSION=v2"
Environment="CMDB_AGENT_VERSION=v2"
EOF
sudo systemctl daemon-reload && sudo systemctl restart specialized-agents-api
```

**Para rollback imediato:**
```bash
sudo rm /etc/systemd/system/specialized-agents-api.service.d/governance.conf
sudo systemctl daemon-reload && sudo systemctl restart specialized-agents-api
```

---

## Monitoramento pós-ativação

**Verificar intenções registradas:**
```sql
-- Últimas 20 ações registradas
SELECT intent_id, agent_id, action_type, risk_level, status, created_at
FROM agent_actions
ORDER BY created_at DESC
LIMIT 20;

-- Ações pendentes de aprovação
SELECT * FROM agent_actions WHERE status = 'pending' ORDER BY created_at DESC;

-- Taxa de aprovação por agente
SELECT agent_id, status, count(*) 
FROM agent_actions 
GROUP BY agent_id, status;
```

**Verificar checkpoints LangGraph:**
```sql
-- Threads ativos (investigações em andamento)
SELECT thread_id, created_at FROM checkpoints ORDER BY created_at DESC LIMIT 10;
```

**Retomar uma investigação pausada:**
```python
from specialized_agents.bn_acervo_agent_langgraph import BnAcervoStoryAgent
agent = BnAcervoStoryAgent()
state = agent.resume("thread-id-aqui")
agent.close()
```

---

## Troubleshooting

| Sintoma | Causa | Fix |
|---|---|---|
| `TypeError: Invalid connection type: psycopg2.extensions.connection` | PostgresSaver exige psycopg3 | Verificar `import psycopg` (não `psycopg2`) em langgraph_base.py |
| `CREATE INDEX CONCURRENTLY cannot run inside transaction` | autocommit=False no setup | Usar `PostgresSaver.from_conn_string()` — já corrigido na base |
| Checkpoints com 0 rows | Conexão direta sem context manager | Usar `from_conn_string()`, nunca `PostgresSaver(conn)` |
| `EmptyInputError: Received no input for __start__` | thread_id não tem checkpoint | Verificar se `run()` foi chamado antes de `resume()` |
| Agente não pausa para aprovação | `RISK_LEVEL = "low"` ou approval_gateway.service parado | Checar `systemctl status approval-gateway` |
| Telegram sem resposta | Token defasado em `.env` | Usar token de `/etc/default/eddie-common` (canônico) |

---

## Guia completo para desenvolvedores

Ver: `docs/agents/langgraph_agent_guide.md`

---

## Commits desta feature

| Commit | Fase | Descrição |
|---|---|---|
| `996f125d` | 0+1 | Action Journal + Approval Gateway via Telegram |
| `1f058653` | 2 | Shared Memory Layer via ChromaDB + ingestores |
| `8ba2b2ef` | 3 | LangGraph base template + LTFS log rotation pilot |
| `7d408da5` | 4 | coordinator_v2 em LangGraph + feature flag |
| `7a0087bd` | 5.1 | wiki_agent_langgraph + feature flag |
| `f4107966` | 5.2/5.3 | cmdb_agent_langgraph + nextcloud_agent_langgraph |
| `44eefb86` | — | Renomear _v2.py → _langgraph.py (convenção sem sufixo de versão) |
| `3c5df740` | 5.4 | conube_agent_langgraph + feature flag |
| `a3044e76` | 5.5 | bn_acervo_agent_langgraph + feature flag |
