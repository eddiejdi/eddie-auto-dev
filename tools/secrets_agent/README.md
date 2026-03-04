# Secrets Agent v2.0 — Auto-Unlock Bitwarden

Gateway unificado para secrets com **auto-login, auto-unlock e cache de sessão** do Bitwarden. Nunca solicita senha interativamente.

## Funcionalidades

- **Auto-unlock BW** — usa `BW_MASTER_PASSWORD` ou arquivo de senha (`BW_PASSWORD_FILE`)
- **Auto-login BW** — via API key (`BW_CLIENTID`/`BW_CLIENTSECRET`) ou email+password
- **Cache de sessão** — persiste sessão BW em disco, sobrevive a restarts
- **Retry automático** — reautentica se sessão expira durante uso
- **Fallback gracioso** — secrets locais (SQLite) funcionam mesmo sem BW
- `GET /secrets` — lista itens do BW + secrets locais
- `GET /secrets/{item_id}` — retorna valor (requer `X-API-KEY`)
- `GET /secrets/local/{name}` — busca secret local por nome/field
- `POST /secrets` — armazena secret no SQLite local
- `GET /bw/status` — diagnóstico da sessão BW
- `POST /bw/unlock` — força re-unlock (requer `X-API-KEY`)
- `GET /health` — health check com status BW
- `GET /metrics` — métricas Prometheus

## Instalação rápida (homelab)

```bash
# 1. Configurar master password (RECOMENDADO — arquivo seguro)
sudo mkdir -p /var/lib/eddie/secrets_agent
echo 'SUA_MASTER_PASSWORD' | sudo tee /var/lib/eddie/secrets_agent/.bw_master_password
sudo chmod 600 /var/lib/eddie/secrets_agent/.bw_master_password

# 2. Garantir BW logado (uma única vez)
bw login  # ou: bw login --apikey (com BW_CLIENTID/BW_CLIENTSECRET)

# 3. Instalar serviço
chmod +x tools/secrets_agent/install.sh
sudo tools/secrets_agent/install.sh

# 4. Verificar
curl http://127.0.0.1:8088/bw/status
curl http://127.0.0.1:8088/health
```

## Configuração (env vars)

| Variável | Default | Descrição |
|----------|---------|-----------|
| `SECRETS_AGENT_API_KEY` | `please-set-a-strong-key` | Chave de autenticação da API |
| `SECRETS_AGENT_DATA` | `/var/lib/eddie/secrets_agent` | Diretório de dados |
| `SECRETS_AGENT_PORT` | `8088` | Porta da API |
| `SECRETS_AGENT_PROM_PORT` | `8009` | Porta métricas Prometheus |
| `BW_PASSWORD_FILE` | `{DATA}/. bw_master_password` | Arquivo com master password (mais seguro) |
| `BW_MASTER_PASSWORD` | — | Master password via env var (alternativa) |
| `BW_CLIENTID` | — | Client ID para API key login |
| `BW_CLIENTSECRET` | — | Client Secret para API key login |
| `BW_EMAIL` | — | Email para login com password |
| `BW_STATUS_TTL` | `60` | TTL (segundos) do cache de status BW |
| `BW_CMD_TIMEOUT` | `30` | Timeout (segundos) para comandos `bw` |

## Fluxo de autenticação

```
Startup / Requisição com BW
           │
           ▼
    ┌─ BW_SESSION válida? ─── sim ──▶ USAR
    │       │ não
    │       ▼
    │  ┌─ bw status ──────────────────────────────┐
    │  │                                           │
    │  ├─ unlocked ──▶ OK (usar)                   │
    │  │                                           │
    │  ├─ locked ──▶ auto-unlock                   │
    │  │    └─ BW_MASTER_PASSWORD / BW_PASSWORD_FILE│
    │  │    └─ salva sessão em cache                │
    │  │                                           │
    │  ├─ unauthenticated ──▶ auto-login           │
    │  │    ├─ API key (BW_CLIENTID)               │
    │  │    └─ Email + password                    │
    │  │    └─ depois auto-unlock                  │
    │  │                                           │
    │  └─ unknown ──▶ tenta unlock direto          │
    │                                              │
    └────── falhou? ──▶ secrets locais OK           │
                       ▶ BW indisponível           │
                                                   │
    Retry automático se sessão expira mid-request   │
    ────────────────────────────────────────────────┘
```

## Segurança

- Todas as requisições autenticadas via `X-API-KEY`
- Auditoria em SQLite (`/var/lib/eddie/secrets_agent/audit.db`)
- Rate-limiting por IP (5 falhas em 60s dispara alerta de leak)
- Arquivo de senha com `chmod 600`
- Master password nunca aparece em logs
