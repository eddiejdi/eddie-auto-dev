# Integração RCA — Eddie Auto-Dev

Este documento é a versão para Confluence (Markdown pronta para colar) da integração RCA implantada no homelab.

**Resumo**
- Objetivo: permitir que agentes consumam RCAs (Root Cause Analysis) via uma API HTTP leve e executem remediações (modo `AUTONOMOUS_MODE` controlado).
- Ambiente: homelab (192.168.15.2)
- Serviços: `agent-api`, `agent-consumer-loop`, `operations-agent` (autônomo)

**Arquitetura**
- `simple_agent_api.py` (porta 8888) — expõe `/rcas`, `/rca/{issue}`, `/rca/{issue}/ack`.
- `agent_consumer_loop.py` — move RCAs para `consumed/` e escreve ACKs locais.
- `operations_agent.py` — consome via `agent_api_client.fetch_pending()`, executa `_run_actions()` (dry-run por padrão) e `ack_rca()`.
- `agent_api_client.py` — cliente HTTP; requer `AGENT_API_URL` + `ALLOW_AGENT_API=1`.

**Endpoints**
- `GET /rcas` → lista RCAs (queued/consumed)
- `GET /rca/{issue}` → detalhes
- `POST /rca/{issue}/ack` → marcar como consumido via API

**Fluxo de dados (resumo)**
1. Gerar JSON RCA (ex.: `rca_EA-XXXX.json`) em `/tmp/agent_queue/`
2. `agent-api` serve a fila via HTTP
3. `operations-agent` consulta `fetch_pending()` e recebe RCAs queued
4. `operations-agent` executa `_run_actions()` e envia `ack_rca()`
5. `agent-consumer-loop` move arquivos locais para `consumed/` e cria `.ack`

**Comandos úteis**
```bash
# Ver logs do operations agent
ssh homelab@192.168.15.2 'journalctl --user -u operations-agent -f'

# Ver fila via API
curl -s http://127.0.0.1:8888/rcas | jq .

# Criar RCA de teste
cat > /tmp/agent_queue/rca_EA-TEST.json <<EOF
{"issue":"EA-TEST","summary":"Teste","priority":"Low"}
EOF
```

**Configuração do serviço `operations-agent`**
- Variáveis do serviço (`~/.config/systemd/user/operations-agent.service`):
  - `AGENT_API_URL=http://127.0.0.1:8888`
  - `ALLOW_AGENT_API=1`
  - `DATABASE_URL=postgresql://postgres:eddie_memory_2026@localhost:5432/postgres`
  - `OPS_AGENT_POLL=10`
  - `AUTONOMOUS_MODE=0` (padrão: dry-run)

**Como documentar no Confluence**
1. Crie uma nova página no espaço desejado.
2. Cole este conteúdo (Markdown) no editor (Confluence Cloud permite colar Markdown via editor ou usar macro de import).
3. Anexe o arquivo de diagrama `diagrams/RCA_flow.drawio` (criado neste repo) e insira-o como um Gliffy/diagrama draw.io na página.

**Referências**
- `tools/homelab_recovery/simple_agent_api.py`
- `tools/homelab_recovery/agent_consumer_loop.py`
- `tools/operations_agent.py`
- `tools/agent_api_client.py`

---

*Gerado automaticamente — use como base e ajuste o texto no Confluence conforme padrões internos.*
