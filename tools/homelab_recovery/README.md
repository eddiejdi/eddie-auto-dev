# Homelab Recovery Kit

Ferramentas para restaurar acesso ao homelab quando SSH está indisponível.

## Métodos de recovery (em ordem de prioridade)

| # | Método | Requisito | Script |
|---|--------|-----------|--------|
| 1 | Wake-on-LAN | Servidor desligado, WoL habilitado na BIOS | `recover.sh --wol` |
| 2 | Agents API (via tunnel) | cloudflared rodando, API up | `recover.sh --api` |
| 3 | Open WebUI code exec | Open WebUI rodando | `recover.sh --webui` |
| 4 | Telegram Bot command | Telegram bot rodando | `recover.sh --telegram` |
| 5 | GitHub Actions runner | Self-hosted runner online | Dispatch workflow |
| 6 | USB Recovery | Acesso físico ao servidor | `usb_recovery.sh` |

## Quick start

```bash
# Diagnóstico completo
./recover.sh --diagnose
```

## Agent RCA workflow (novo)

Este repositório agora inclui um fluxo leve para gerar RCA (Root Cause Analysis)
automático a partir de logs e disponibilizá-los para agents consumirem.

- Local de trabalho da fila: `/tmp/agent_queue`
- Arquivos gerados pelos RCAs: `/tmp/rca_EA-<NUM>.json`
- Acks criados pelos agents: `/tmp/agent_queue/rca_EA-<NUM>.ack`
- Arquivos consumidos movidos para: `/tmp/agent_queue/consumed/`

Scripts e serviços:

- Gerar RCAs e publicar no bus (local, ephemeral): `/tmp/generate_and_publish_rca.py`
- Coletar evidências via SSH e salvar snippets: `/tmp/collect_rca.sh`
- Consumidor simulado (processa e cria .ack): `/tmp/agent_consumer.py`
- Consumer em loop (systemd user): `/tmp/agent_consumer_loop.py` + `agent-consumer.service`
- API leve para agents (GET/ACK): `/tmp/simple_agent_api.py` + `agent-api.service` (user)

Endpoints HTTP disponíveis (localhost:8888):

- `GET /rcas` — lista RCAs em fila e consumidos
- `GET /rca/{ISSUE}` — retorna o conteúdo do `rca_{ISSUE}.json`
- `POST /rca/{ISSUE}/ack` — cria `rca_{ISSUE}.ack` e move o arquivo para `consumed`

Como usar (exemplo):

```bash
# listar
curl http://127.0.0.1:8888/rcas

# obter um rca
curl http://127.0.0.1:8888/rca/EA-42

# ack (agent):
curl -X POST http://127.0.0.1:8888/rca/EA-42/ack
```

Observações operacionais:

- O serviço `agent-api.service` foi criado como unit de usuário em
	`~/.config/systemd/user/agent-api.service`. Use `systemctl --user status agent-api.service`.
- Se preferir filas persistentes via Postgres, configure `DATABASE_URL` e use `tools/agent_ipc.py`.
- Arquivos consumidos são arquivados em `/tmp/rca_archives/` periodicamente pelo operador.

Se quiser, eu atualizo os agents existentes para consumir este endpoint ou publico os RCAs em Postgres; diga qual preferência.
# Homelab Recovery Kit

Ferramentas para restaurar acesso ao homelab quando SSH está indisponível.

## Métodos de recovery (em ordem de prioridade)

| # | Método | Requisito | Script |
# Homelab Recovery Kit

Ferramentas para restaurar acesso ao homelab quando SSH está
indisponível.

## Métodos de recovery (em ordem de prioridade)

| # | Método | Requisito | Script |
| --- | --- | --- | --- |
| 1 | Wake-on-LAN | Servidor desligado, WoL habilitado na BIOS | `recover.sh --wol` |
| 2 | Agents API (via tunnel) | `cloudflared` rodando, API disponível | `recover.sh --api` |
| 3 | Open WebUI code exec | Open WebUI rodando | `recover.sh --webui` |
| 4 | Telegram Bot command | Telegram bot rodando | `recover.sh --telegram` |
| 5 | GitHub Actions runner | Self-hosted runner online | Dispatch workflow |
| 6 | USB Recovery | Acesso físico ao servidor | `usb_recovery.sh` |

## Quick start

```bash
# Diagnóstico completo
./recover.sh --diagnose

# Tentar tudo automaticamente (não recomendado em produção sem revisão)
./recover.sh --auto

# Wake-on-LAN
./recover.sh --wol

# Executar comando via API tunnel (ex.: reiniciar sshd)
./recover.sh --api "sudo systemctl restart sshd"

# Monitorar até SSH voltar
./recover.sh --wait
```

## Configuração

Edite `config.env` com os dados do seu homelab (ex.: `SSH_USER`, `HOST`,
`CF_TUNNEL`). O script carrega este arquivo automaticamente.

## Prevenção

Para evitar perda de acesso SSH no futuro, considere as seguintes ações:

1. **Nunca** altere `/etc/ssh/sshd_config` remotamente sem um
 mecanismo de rollback automático (ex.: `at` ou `cron`).
2. Opcional: use `recover.sh --safeguard` para instalar um cron job de
 auto-restore do SSH.
3. Mantenha o tunnel `cloudflared` ativo como backup de acesso remoto.
4. Configure Wake-on-LAN na BIOS do servidor e verifique a
 conectividade da rede.
