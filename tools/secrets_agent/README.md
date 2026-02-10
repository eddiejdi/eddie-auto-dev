# Secrets Agent

Pequeno serviço para exposição controlada de segredos do Bitwarden, auditoria e métricas.

Funcionalidades:
- `GET /secrets` — lista `id` e `title` dos itens do Bitwarden (requer `bw` e sessão desbloqueada)
- `GET /secrets/{item_id}` — retorna a senha/valor (requer header `X-API-KEY`)
- `GET /audit/recent` — lista auditoria recente
- métricas Prometheus em `/metrics` (ou via exportador em `SECRETS_AGENT_PROM_PORT`)

Instalação rápida (homelab):

```bash
# ajustar se necessário
export SECRETS_AGENT_API_KEY="valor-secreto-muito-forte"
sudo mkdir -p /etc/systemd/system/secrets_agent.service.d
echo -e "[Service]\nEnvironment=SECRETS_AGENT_API_KEY=${SECRETS_AGENT_API_KEY}" | sudo tee /etc/systemd/system/secrets_agent.service.d/override.conf
chmod +x tools/secrets_agent/install.sh
sudo tools/secrets_agent/install.sh
```

Requisitos:
- `bw` CLI com sessão desbloqueada (`BW_SESSION`)
- Python packages: `fastapi`, `uvicorn`, `prometheus_client`

Segurança e auditoria:
- Todas as requisições são registradas em `/var/lib/eddie/secrets_agent/audit.db` (SQLite).
- Acesso não autorizado incrementa contadores e dispara alertas de leak quando há muitas falhas.

Observação importante: Exibir senhas em painéis é sensível — o agente exige `X-API-KEY` e grava auditoria de acessos. Garanta que o Grafana não esteja publicamente acessível.
