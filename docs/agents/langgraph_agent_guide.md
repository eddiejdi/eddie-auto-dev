# Guia: Novos Agentes com LangGraph + Governança

Este guia cobre como criar, testar e operar novos agentes do homelab usando o
framework LangGraph integrado à camada de governança (Action Journal, Approval
Gateway, Shared Memory).

## Arquitetura do grafo base

```
START → declare_intent → [low: execute] [medium/high: await_approval]
                                │
                         await_approval ──(rejected)──→ reject → END
                                │
                             (approved)
                                │
                            execute → store_memory → complete_intent → END
```

Cada nó é executado e checkpointado no PostgreSQL. Se o processo morrer em
qualquer ponto, `agent.resume(thread_id)` retoma do último nó completo.

## Criando um agente novo

### 1. Subclasse mínima

```python
# specialized_agents/meu_agente.py
from specialized_agents.langgraph_base import AgentState, HomelabAgent

class MeuAgente(HomelabAgent):
    AGENT_ID    = "meu_agente"        # único no homelab
    ACTION_TYPE = "minha_acao"        # tipo registrado no Action Journal
    RISK_LEVEL  = "low"               # low | medium | high | critical

    def _describe_work(self, state: AgentState) -> str:
        return f"Processar {state.get('target', '?')}"

    def _execute_work(self, state: AgentState) -> dict:
        # faz o trabalho; nunca lança exceção — retorna erro no dict
        try:
            resultado = _faz_algo(state["target"])
            return {
                "outcome":     f"ok: {resultado}",
                "memory_fact": f"meu_agente processou {state['target']}: {resultado}",
            }
        except Exception as exc:
            raise  # HomelabAgent captura e registra no Journal automaticamente
```

### 2. Risk level dinâmico

Se o risco depende dos dados, calcule antes de `agent.run()`:

```python
agent = MeuAgente()
agent.RISK_LEVEL = "medium" if tamanho > LIMITE else "low"
result = agent.run(target="foo")
```

### 3. Acessando `extra` na execução

Passe dados arbitrários via `extra`:

```python
result = agent.run(
    target="servidor-abc",
    extra={"porta": 8080, "dry_run": True},
)
# Em _execute_work:
porta = state["extra"]["porta"]
```

## Flow de aprovação (risk ≥ medium)

1. `agent.run()` registra intent no DB com `status=pending` e retorna imediatamente
2. O `approval-gateway.service` detecta o intent pendente e envia botão no Telegram
3. Operador aperta ✅ ou ❌
4. Gateway faz UPDATE na tabela `agent_actions`
5. Agendador (ou outro processo) chama `agent.resume(thread_id)`:

```python
# No runner ou systemd timer:
result = agent.resume(thread_id=saved_thread_id)
if result["status"] == "done":
    print(result["outcome"])
```

### Verificar se está aguardando aprovação

```python
result = agent.run(target="x")
if result.get("approval") == "pending":
    thread_id = result["thread_id"]
    # salvar thread_id para uso no resume
```

## Checkpoint e recuperação

O checkpointer usa `PostgresSaver.from_conn_string()` (psycopg3) para persistir
estado após cada nó. Sempre chame `agent.close()` ao encerrar para liberar a conexão.

```python
from specialized_agents.ltfs_log_rotation_agent import LtfsLogRotationAgent

agent = LtfsLogRotationAgent()
try:
    result = agent.run(target="teste")
    thread_id = result["thread_id"]
finally:
    agent.close()  # libera PostgresSaver e conexão psycopg3

# Em nova instância Python (simula restart após kill):
agent2 = LtfsLogRotationAgent()
try:
    result2 = agent2.resume(thread_id=thread_id)
    # Retoma do último nó checkpointado
finally:
    agent2.close()
```

> **Nota**: `PostgresSaver(conn)` com conexão psycopg3 manual não persiste
> checkpoints. Use sempre `from_conn_string` via `_get_checkpointer()` interno.

## Time-travel debug

```python
history = agent.get_history(thread_id)
for step in history:
    print(f"step={step['step']} next={step['next']}")
    print(f"  status={step['values'].get('status')}")
    print(f"  approval={step['values'].get('approval')}")
```

Saída típica (fluxo low-risk):
```
step=4 next=[]
  status=done
  approval=not_required
step=3 next=['complete_intent']
  status=done
  approval=not_required
step=2 next=['store_memory']
  ...
```

## Deploy como systemd service

### One-shot (timer)

```ini
# systemd/meu-agente.service
[Unit]
Description=Meu Agente LangGraph

[Service]
Type=oneshot
User=homelab
WorkingDirectory=/home/homelab/myClaude
EnvironmentFile=/etc/default/eddie-common
ExecStart=/usr/bin/python3 -m specialized_agents.meu_agente
StandardOutput=journal
StandardError=journal
SyslogIdentifier=meu-agente
```

```ini
# systemd/meu-agente.timer
[Unit]
Description=Meu Agente — executa a cada 6h

[Timer]
OnBootSec=10min
OnUnitActiveSec=6h
Unit=meu-agente.service

[Install]
WantedBy=timers.target
```

### Daemon long-running

Para agentes que fazem loop:

```python
def main():
    agent = MeuAgente()
    while True:
        result = agent.run(target=_proximo_alvo())
        if result.get("approval") == "pending":
            _salvar_thread_id(result["thread_id"])
        time.sleep(300)
```

## Padrões e convenções

| Atributo       | Convenção                                    |
|----------------|----------------------------------------------|
| `AGENT_ID`     | snake_case, único; ex: `ltfs_log_rotation`   |
| `ACTION_TYPE`  | verbo_substantivo; ex: `ltfs_rotate_logs`    |
| `RISK_LEVEL`   | `low` para read-only; `medium` para writes   |
| `memory_fact`  | Começar com `{AGENT_ID}: ` para filtragem    |
| `outcome`      | Texto humano, ≤ 2000 chars                   |

## Regras de segurança

- **BTC trading (`crypto-agent@*`) está fora de escopo** — nunca usar LangGraph nesses serviços sem `dry_run=True` e autorização explícita do operador.
- Credenciais só via `EnvironmentFile=/etc/default/eddie-common` nos serviços systemd.
- Agentes não devem hardcodar `DATABASE_URL` nem tokens; sempre ler do ambiente.
- `_execute_work` pode lançar exceções livremente — `HomelabAgent` captura e registra no Journal com `status=failed`.

## Dependências

```
langgraph                     # pip install --break-system-packages
langchain-anthropic            # só se usar ChatAnthropic diretamente
langgraph-checkpoint-postgres  # PostgresSaver
psycopg2-binary                # já instalado no homelab
chromadb                       # já instalado (shared memory)
```

Verifique com:
```bash
python3 -c 'from langgraph.graph import StateGraph; from langgraph.checkpoint.postgres import PostgresSaver; print("ok")'
```

## Troubleshooting

**`psycopg2.errors.UndefinedTable: relation "checkpoints" does not exist`**
→ `PostgresSaver.setup()` cria as tabelas na primeira inicialização. Confirme que `DATABASE_URL` aponta para o DB correto.

**Intent fica em `pending` mas approval-gateway não envia mensagem**
→ Verificar `systemctl status approval-gateway.service`; pode haver conflito com `eddie-telegram-bot.service` (dois long-polls no mesmo bot).

**`AttributeError: module 'langgraph' has no attribute '__version__'`**
→ Normal; o pacote não expõe `__version__`. Importar `from langgraph.graph import StateGraph` para verificar.

**`TypeError: Invalid connection type: psycopg2.extensions.connection`**
→ `PostgresSaver` requer psycopg3 (`import psycopg`), não psycopg2. Use `from_conn_string()` — `HomelabAgent` faz isso automaticamente.

**`CREATE INDEX CONCURRENTLY cannot run inside a transaction block`**
→ Ocorre se chamar `PostgresSaver.setup()` em conexão com autocommit=False. `from_conn_string` gerencia isso internamente.

**Agent retorna `status=running, approval=pending` sem parar**
→ `INTERRUPT_ON_APPROVAL=True` (padrão). O grafo retorna ao final do stream e o processo sai. Use `resume(thread_id)` quando a aprovação chegar.
