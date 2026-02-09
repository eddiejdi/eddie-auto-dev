# RCA Integration Summary — 2026-02-09

## Objetivo
Implementar infraestrutura completa de **Root Cause Analysis (RCA)** autônoma no homelab, permitindo que agentes consumam e processem RCAs via API HTTP leve.

---

## Arquitetura Implantada

### Componentes

1. **simple_agent_api.py** (port 8888)
   - Servidor HTTP stdlib
   - Endpoints:
     - `GET /rcas` → lista todos RCAs (queued + consumed)
     - `GET /rca/{issue}` → detalhes de um RCA específico
     - `POST /rca/{issue}/ack` → marca RCA como consumido
   - Serve arquivos de `/tmp/agent_queue`

2. **agent_consumer_loop.py**
   - Poll loop a cada 5 segundos
   - Procura padrão `rca_EA-*.json` em `/tmp/agent_queue`
   - Move para `/tmp/agent_queue/consumed/` após processar
   - Cria arquivo `.ack` com timestamp e processor

3. **operations_agent.py** (NEW)
   - Consume RCAs via `agent_api_client.fetch_pending()`
   - Executa `_run_actions()` para remediar (dry-run por padrão)
   - Chama `agent_api_client.ack_rca()` após processar
   - Dual-mode: bus-backed + DB-backed IPC

4. **agent_api_client.py**
   - Cliente Python para API
   - Métodos: `fetch_pending()`, `get_rca()`, `ack_rca()`
   - Controle: `AGENT_API_URL` + `ALLOW_AGENT_API=1`

### Serviços Systemd

| Service | Type | Port | Purpose |
|---------|------|------|---------|
| `agent-api.service` | user | 8888 | Serve RCAs via HTTP |
| `agent-consumer-loop.service` | user | - | Move files para consumed/ |
| `operations-agent.service` | user | - | **Consome RCAs autonomamente** |

---

## Validação Completa ✅

### Testes Realizados

1. **API serving**
   ```bash
   curl http://127.0.0.1:8888/rcas
   # Retorna JSON com status "queued" ou "consumed"
   ```

2. **Consumer processing**
   - Criado `rca_EA-TEST001.json` → consumido em ~5s
   - ACK criado: `{"issue": "EA-TEST001", "consumed_at": 1770665571.2281072, "processor": "agent-consumer-loop"}`

3. **agent_api_client**
   ```python
   from tools import agent_api_client
   rcas = agent_api_client.fetch_pending()  # ✅ Retorna lista
   detail = agent_api_client.get_rca('EA-TEST003')  # ✅ Retorna detalhes
   ok = agent_api_client.ack_rca('EA-TEST003')  # ✅ True
   ```

4. **OperationsAgent autônomo**
   ```
   [OperationsAgent] Starting API poll loop
   [OperationsAgent] Ready
   [OperationsAgent] API RCA available: EA-TEST001
   [OperationsAgent] ack EA-TEST001: True
   [OperationsAgent] API RCA available: EA-TEST002
   [OperationsAgent] ack EA-TEST002: True
   [OperationsAgent] API RCA available: EA-TEST003
   [OperationsAgent] ack EA-TEST003: True
   ```

### Status Final
- ✅ 3 RCAs de teste criados (EA-TEST001, EA-TEST002, EA-TEST003)
- ✅ Todos consumidos pelo OperationsAgent
- ✅ Status final: `EA-TEST001 -> consumed`, `EA-TEST002 -> consumed`, `EA-TEST003 -> consumed`
- ✅ Fila: vazia (nenhum .json pendente)

---

## Configuração de Ambiente

### operations-agent.service
```ini
Environment="AGENT_API_URL=http://127.0.0.1:8888"
Environment="ALLOW_AGENT_API=1"
Environment="DATABASE_URL=postgresql://postgres:eddie_memory_2026@localhost:5432/postgres"
Environment="OPS_AGENT_POLL=10"
Environment="AUTONOMOUS_MODE=0"  # dry-run (não executa ações destrutivas)
```

### Outros serviços (coordinator, specialized-agents-api, diretor)
Configurados com drop-ins em `/etc/systemd/system/{service}.service.d/rca_api.conf`:
```ini
Environment="AGENT_API_URL=http://127.0.0.1:8888"
Environment="ALLOW_AGENT_API=1"
```

**Nota**: Estes serviços NÃO executam operations_agent diretamente. O OperationsAgent é um processo separado para desacoplar responsabilidades.

---

## Pipeline Completo

```mermaid
graph LR
    A[Log Scan] --> B[Generate RCA JSON]
    B --> C[/tmp/agent_queue/rca_EA-XXX.json]
    C --> D[agent-api.service]
    C --> E[agent-consumer-loop.service]
    D --> F[operations-agent.service]
    F -->|fetch_pending| D
    F -->|process| G[_run_actions]
    F -->|ack_rca| D
    E -->|move| H[/tmp/agent_queue/consumed/]
```

---

## Próximos Passos

### 1. Gerar RCAs Reais
Usar `generate_and_publish_rca.py` para criar RCAs de erros reais do homelab:
- EA-42: Redis overcommit_memory warning
- EA-43: io_uring compatibility check
- EA-44: PostgreSQL permission denied (password auth)
- EA-45: Grafana provisioning permission denied
- EA-46: Backup space warnings

### 2. Ativar Modo Autônomo
Após validação com RCAs reais, mudar `AUTONOMOUS_MODE=1` em `operations-agent.service` para permitir ações destrutivas.

### 3. Monitoramento
- **Logs**: `journalctl --user -u operations-agent -f`
- **API**: `watch -n 5 'curl -s http://127.0.0.1:8888/rcas | jq .'`
- **Queue**: `watch -n 5 'ls -lh /tmp/agent_queue/'`

### 4. GitHub Actions Integration
Adicionar step no workflow `deploy-to-homelab.yml` para instalar `operations-agent.service` quando `INSTALL_RCA_SERVICES=1`.

---

## Commits Relacionados

- **198cc5d**: Bitwarden migration tools
- **fd9fb8c**: OperationsAgent systemd service (este deploy)

---

## Referências

- [tools/homelab_recovery/](../../tools/homelab_recovery/) — Scripts RCA
- [tools/operations_agent.py](../../tools/operations_agent.py) — Agente autônomo
- [tools/agent_api_client.py](../../tools/agent_api_client.py) — Cliente API
- [docs/AGENT_MEMORY.md](../../docs/AGENT_MEMORY.md) — Memória de agentes

---

**Data**: 2026-02-09  
**Status**: ✅ Integração completa e validada  
**Ambiente**: homelab (192.168.15.2)
