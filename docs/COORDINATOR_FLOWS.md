# Coordinator Flows — Mapeamento para Migração LangGraph

Documento de pré-migração (passo 4.1 do `AGENT_GOVERNANCE_MIGRATION_PLAN.md`).
Serve como contrato entre v1 (atual) e v2 (LangGraph).

## Serviços envolvidos

| Serviço | Status | Processo | Porta/socket |
|---|---|---|---|
| `coordinator-agent.service` | **active (running)** | `/home/homelab/myClaude/.venv/bin/python dev_agent/run_coordinator_service.py` | In-process bus |
| `job-monitor.service` | inactive (disabled) | WhatsApp job scanner, fora de escopo v2 |
| `eddie-coordinator.service` | active | Streamlit dashboard `:8502`, apenas UI |
| `cpu-monitor.service` | active | Dashboard de CPU, independente |

## Arquitetura atual (v1)

```
AgentCommunicationBus (singleton in-process)
     │
     ├── subscribe(handle_message)  ← coordinator-agent.service
     │        │
     │        ▼
     │   msg.target == "CoordinatorAgent"?
     │        │ YES
     │        ▼
     │   _build_coordinator()
     │   (nova instância por request — resets state)
     │        │
     │        ▼
     │   CoordinatorAgent.decide_and_execute(msg.content)
     │        │
     │        ├── DevAgent.develop()  ← tenta até max_retries=3
     │        │        │
     │        │        ▼ falha
     │        ├── web_search.search(description)
     │        │   enriquece descrição + retry
     │        │        │
     │        │        ▼ ainda falha após max_retries
     │        └── {"success": False, "requires_user": True, "errors": [...]}
     │
     └── bus.publish(RESPONSE, source="CoordinatorAgent", target=msg.source)
```

## Fluxo passo a passo

### 1. Entrada — REQUEST no Bus

Campos obrigatórios:
```python
AgentMessage(
    message_type = MessageType.REQUEST,
    target       = "CoordinatorAgent",  # ou "agent_coordinator"
    source       = "<agente-solicitante>",
    content      = "<descrição da tarefa em texto livre>",
    metadata     = {"request_id": "<uuid>"},  # opcional
)
```

### 2. Processamento — `decide_and_execute`

```
for attempt in range(max_retries):           # default: 3
    result = dev_agent.develop(description)
    if result["success"]:
        return {"success": True, ...}
    errors.append(result["error"])

    if attempt < max_retries - 1 AND web_search:
        results = web_search.search(description)
        description += "\n\nInformações da web:\n" + results   # enriquece e retenta
        
return {"success": False, "requires_user": True, "errors": errors}
```

### 3. Saída — RESPONSE no Bus

```python
AgentMessage(
    message_type = MessageType.RESPONSE,
    source       = "CoordinatorAgent",
    target       = <msg.source original>,
    content      = str(result),    # JSON serializado como string
    metadata     = {"request_id": <msg.metadata["request_id"]>},
)
```

### 4. DevAgent.develop internals

```
DevAgent.develop(description, language)
    → create_task(description, language)   # gera task_id, cria TaskRecord
    → execute_task(task_id)
         → LLMClient.generate_sync(prompt)
         → (opcional) DockerManager.run_code(code)
         → (opcional) CodeGen.fix_code(code)
```

## Callers identificados

| Caller | Frequência | Método de envio |
|---|---|---|
| `send_to_coordinator.py` | manual/script | `bus.publish(REQUEST, target="CoordinatorAgent")` |
| `ask_director_coordinator.py` | manual/script | idem |
| Outros agentes via bus | dinâmico | qualquer publish com target correto |

Nota: nenhum caller identificado que envie `target="agent_coordinator"` atualmente.
O alias existe como fallback.

## Problemas do v1 endereçados pela migração

| Problema | Impacto | Solução v2 |
|---|---|---|
| Sem checkpoint | Job perdido se processo reiniciar durante execução | PostgresSaver — retoma do nó interrompido |
| Sem governance | Nenhum registro de quais tarefas foram executadas | `declare_intent` → Action Journal |
| Sem memória | Cada request relearns tudo, sem contexto de sucessos anteriores | `store_memory` → ChromaDB |
| Nova instância por request | Overhead de inicialização a cada mensagem | Graph reutiliza estado via checkpointer |
| Sem visibilidade de retry | Falhas silenciosas no bus | Status no Journal: `pending→done/failed` |

## Invariantes a preservar na v2

1. **Interface de bus idêntica** — target="CoordinatorAgent" e RESPONSE para msg.source
2. **Formato de resposta compatível** — content = str(result), metadata com request_id
3. **max_retries=3 por padrão** — configurável via env COORDINATOR_MAX_RETRIES
4. **Web search como enrichment** — se WebSearchEngine disponível, enriquece antes de retry
5. **Não bloquear o bus** — processamento assíncrono, publicar RESPONSE mesmo em caso de falha

## Feature flag

```bash
COORDINATOR_VERSION=v1   # padrão em produção; usa run_coordinator_service.py (v1)
COORDINATOR_VERSION=v2   # usa coordinator_v2.py (LangGraph)
```

A variável é lida em `/home/homelab/myClaude/tools/start_coordinator.sh` (após modificação).

## Plano de cutover (passo 4.4)

1. Deploy `coordinator_v2.py` com `COORDINATOR_VERSION=v2` em ambiente paralelo
2. Observar 7 dias sem divergências entre v1 e v2 (ambos processam — v2 em modo shadow)
3. Mudar para `COORDINATOR_VERSION=v2` como único handler em produção
4. Manter `coordinator-agent.service` com v1 desabilitado (não removido) por 30 dias
5. Remover v1 após 30 dias de operação estável

## Rollback imediato

```bash
# Reverter em < 30s:
sudo systemctl set-environment COORDINATOR_VERSION=v1
sudo systemctl restart coordinator-agent.service
```

Ou via drop-in:
```bash
sudo systemctl edit coordinator-agent.service
# Adicionar/alterar: Environment="COORDINATOR_VERSION=v1"
sudo systemctl daemon-reload && sudo systemctl restart coordinator-agent.service
```
