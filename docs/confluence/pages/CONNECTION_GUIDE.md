# Guia de Conexão — Eddie Homelab

> **Última atualização:** 2026-02-19  
> **Autor:** Agent dev_local (Copilot)  
> **Ambiente:** Homelab — Ubuntu 24.04, Kernel 6.8.0-100

---

## Sumário

1. [Visão Geral da Infraestrutura](#1-visão-geral-da-infraestrutura)
2. [Ollama — LLM Inference](#2-ollama--llm-inference)
3. [OpenWebUI — Interface Web e API OpenAI-compatible](#3-openwebui--interface-web-e-api-openai-compatible)
4. [CLINE (VS Code) — Integração com Ollama](#4-cline-vs-code--integração-com-ollama)
5. [PostgreSQL](#5-postgresql)
6. [Agents API (FastAPI)](#6-agents-api-fastapi)
7. [Secrets Agent](#7-secrets-agent)
8. [Grafana — Dashboards e Monitoramento](#8-grafana--dashboards-e-monitoramento)
9. [Estou Aqui — App Social](#9-estou-aqui--app-social)
10. [Cloudflare Tunnel — Acesso Público](#10-cloudflare-tunnel--acesso-público)
11. [SSH e VPN](#11-ssh-e-vpn)
12. [Mapa de Portas](#12-mapa-de-portas)
13. [Modelos Disponíveis](#13-modelos-disponíveis)
14. [Exemplos de Uso](#14-exemplos-de-uso)

---

## 1. Visão Geral da Infraestrutura

```
Internet → Cloudflare Tunnel (ID: 8169b9cd)
    ├─ openwebui.rpa4all.com → Nginx :3000 → Docker OpenWebUI :8002
    ├─ homelab.rpa4all.com   → FastAPI Agents :8503
    ├─ grafana.rpa4all.com   → Docker Grafana :3001
    ├─ estouaqui.rpa4all.com → Estou Aqui :3456
    ├─ api.rpa4all.com       → Agents/Code Runner :8081
    ├─ ide.rpa4all.com       → IDE :8081
    ├─ www.rpa4all.com       → Landing Page (Nginx :8090)
    ├─ ssh.rpa4all.com       → SSH :22
    └─ vpn.rpa4all.com       → WireGuard :51821

LAN (192.168.15.2)
    ├─ :11434  → Ollama (sem auth, acesso direto)
    ├─ :5432   → PostgreSQL (Docker, auth md5)
    ├─ :3000   → Nginx proxy → OpenWebUI
    ├─ :3001   → Grafana (Docker)
    ├─ :3456   → Estou Aqui API
    ├─ :8002   → OpenWebUI (Docker, loopback)
    ├─ :8088   → Secrets Agent (loopback)
    ├─ :8090   → Landing Page (loopback)
    ├─ :8503   → Agents API (FastAPI)
    └─ :8081   → Agents/Code Runner
```

**Hardware:** CPU Haswell (AVX2), 31 GiB RAM, sem GPU. Inferência 100% em CPU.

---

## 2. Ollama — LLM Inference

### Acesso LAN (recomendado para baixa latência)

| Campo | Valor |
|-------|-------|
| **URL** | `http://192.168.15.2:11434` |
| **Autenticação** | Nenhuma |
| **Firewall** | Porta 11434/tcp aberta (ufw ALLOW) |
| **Bind** | `0.0.0.0:11434` (acessível de toda a LAN) |

### Endpoints

| Endpoint | Descrição | Formato |
|----------|-----------|---------|
| `GET /api/tags` | Listar modelos disponíveis | JSON |
| `POST /api/chat` | Chat (formato Ollama nativo) | Streaming JSON |
| `POST /api/generate` | Completion simples | Streaming JSON |
| `POST /api/embeddings` | Gerar embeddings | JSON |
| `POST /v1/chat/completions` | Chat (formato OpenAI-compatible) | JSON |
| `POST /v1/completions` | Completion (formato OpenAI-compatible) | JSON |

### Exemplo — Chat via API nativa

```bash
curl http://192.168.15.2:11434/api/chat \
  -d '{
    "model": "eddie-assistant",
    "messages": [{"role": "user", "content": "Olá, como você está?"}],
    "stream": false
  }'
```

### Exemplo — Chat via formato OpenAI

```bash
curl http://192.168.15.2:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5-coder:7b",
    "messages": [{"role": "user", "content": "Explique recursão em Python"}]
  }'
```

### Exemplo — Embeddings

```bash
curl http://192.168.15.2:11434/api/embeddings \
  -d '{"model": "nomic-embed-text", "prompt": "texto para vetorizar"}'
```

---

## 3. OpenWebUI — Interface Web e API OpenAI-compatible

### Acesso Público (HTTPS via Cloudflare Tunnel)

| Campo | Valor |
|-------|-------|
| **URL** | `https://openwebui.rpa4all.com` |
| **Versão** | 0.7.2 |
| **Email admin** | `edenilson.adm@gmail.com` |
| **Senha admin** | *(armazenada no Secrets Agent como `eddie/webui_admin_password`)* |

### Acesso LAN

| Campo | Valor |
|-------|-------|
| **URL** | `http://192.168.15.2:3000` |
| **Roteamento** | Nginx `:3000` → proxy_pass `http://127.0.0.1:8002` (Docker) |

### Autenticação — Obter Token JWT

```bash
# Via URL pública
TOKEN=$(curl -s https://openwebui.rpa4all.com/api/v1/auths/signin \
  -H 'Content-Type: application/json' \
  -d '{"email":"edenilson.adm@gmail.com","password":"<senha>"}' | jq -r .token)

# Via LAN
TOKEN=$(curl -s http://192.168.15.2:3000/api/v1/auths/signin \
  -H 'Content-Type: application/json' \
  -d '{"email":"edenilson.adm@gmail.com","password":"<senha>"}' | jq -r .token)
```

### Endpoint principal — Chat Completions (OpenAI-compatible)

```bash
curl https://openwebui.rpa4all.com/api/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "eddie-assistant",
    "messages": [{"role": "user", "content": "Olá"}]
  }'
```

### Listar modelos disponíveis

```bash
curl https://openwebui.rpa4all.com/api/models \
  -H "Authorization: Bearer $TOKEN"
```

---

## 4. CLINE (VS Code) — Integração com Ollama

> O CLINE se conecta diretamente ao Ollama via LAN. **Não use URLs públicas.**

### Configuração

| Campo | Valor |
|-------|-------|
| **API Provider** | `Ollama` |
| **Custom base URL** | `http://192.168.15.2:11434` |
| **Ollama API Key** | *(vazio)* |
| **Model** | `eddie-coder` (recomendado) ou `qwen2.5-coder:7b` |
| **Context Window** | `8192` |
| **Request Timeout** | `120000` (120 segundos — modelos grandes demoram ~18s) |

### Modelos recomendados para CLINE

| Modelo | Uso | Velocidade |
|--------|-----|------------|
| `eddie-coder` | Geração/edição de código (melhor qualidade) | ~18s |
| `qwen2.5-coder:7b` | Código com boa relação qualidade/velocidade | ~5s |
| `qwen2.5-coder:1.5b` | Ultra-rápido, tarefas simples | ~2s |

### Troubleshooting CLINE

- **"Unable to fetch models"**: Verifique que a URL é `http://192.168.15.2:11434` (sem porta 3000, sem HTTPS)
- **Timeout**: Aumente Request Timeout para `120000` ms
- **"Does not support MCP"**: Normal para Ollama — MCP requer modelos comerciais (Claude, GPT)

---

## 5. PostgreSQL

### Eddie Postgres (banco principal)

| Campo | Valor |
|-------|-------|
| **Host (LAN)** | `192.168.15.2` |
| **Porta** | `5432` |
| **Usuário** | `postgres` |
| **Senha** | *(armazenada no Secrets Agent como `eddie/database_url`)* |
| **Auth** | `md5` |
| **Versão** | PostgreSQL 15.15 (Alpine) |
| **Container** | `eddie-postgres` |
| **Bind** | `0.0.0.0:5432` (acessível de toda a LAN) |

```bash
# Connection string
postgresql://postgress:<senha>@192.168.15.2:5432/postgres

# Dentro de containers Docker, usar hostname:
postgresql://postgress:<senha>@eddie-postgres:5432/postgres
```

### OpenWebUI Postgres (banco separado)

| Campo | Valor |
|-------|-------|
| **Container** | `openwebui-postgres` |
| **Usuário** | `openwebui` |
| **Senha** | `OpenWebUI@2026` |
| **Banco** | `openwebui` |
| **Acesso** | Apenas via rede Docker interna |

---

## 6. Agents API (FastAPI)

### Acesso Público

| Campo | Valor |
|-------|-------|
| **URL** | `https://homelab.rpa4all.com` |
| **Health** | `GET /health` |
| **Status** | `healthy` |
| **Porta interna** | `8503` |

### Acesso LAN

```bash
curl http://192.168.15.2:8503/health
```

### Endpoints principais

| Endpoint | Descrição |
|----------|-----------|
| `GET /health` | Status do sistema |
| `POST /communication/publish` | Publicar no Communication Bus |
| `GET /bus/stream` | SSE — eventos em tempo real |
| `GET /communication/messages` | Polling de mensagens |
| `POST /distributed/route-task` | Rotear tarefa para agente |
| `POST /distributed/record-result` | Registrar resultado |
| `GET /distributed/precision-dashboard` | Dashboard de precisão |
| `GET /interceptor/ws/conversations` | WebSocket — conversas |

---

## 7. Secrets Agent

| Campo | Valor |
|-------|-------|
| **URL** | `http://localhost:8088` (somente loopback) |
| **Autenticação** | Header `X-API-KEY` |
| **Serviço** | `secrets-agent.service` (systemd, Restart=always) |

### Endpoints

| Endpoint | Descrição |
|----------|-----------|
| `GET /secrets` | Listar todos os secrets |
| `GET /secrets/local/{name}?field={field}` | Obter secret local |
| `POST /secrets` | Criar/atualizar secret |
| `GET /metrics` | Métricas Prometheus |

### Uso via Python

```python
from tools.secrets_agent_client import get_secrets_agent_client

client = get_secrets_agent_client()
token = client.get_local_secret("eddie/telegram_bot_token", "password")
db_url = client.get_local_secret("eddie/database_url", "url")
client.close()
```

> **IMPORTANTE:** O Secrets Agent é a **única** fonte de credenciais autorizada. Nunca usar `bw` CLI, variáveis de ambiente ou arquivos locais.

---

## 8. Grafana — Dashboards e Monitoramento

| Campo | Valor |
|-------|-------|
| **URL pública** | `https://grafana.rpa4all.com` |
| **URL LAN** | `http://192.168.15.2:3001` |
| **Container** | Docker, porta `3001` |
| **Datasource** | `eddie-postgres:5432` (hostname Docker) |

---

## 9. Estou Aqui — App Social

| Campo | Valor |
|-------|-------|
| **URL pública** | `https://estouaqui.rpa4all.com` |
| **Porta interna** | `3456` |
| **Tech stack** | Flutter web + Node.js/Express API + PostgreSQL |
| **Repo** | `eddiejdi/estou-aqui` |

---

## 10. Cloudflare Tunnel — Acesso Público

**Tunnel ID:** `8169b9cd-a798-4610-b3a6-ed7218f6685d`  
**Serviço:** `cloudflared-rpa4all.service` (systemd, active)  
**Config:** `/etc/cloudflared/config.yml`

### Roteamento completo

| Hostname | Serviço interno | Descrição |
|----------|-----------------|-----------|
| `openwebui.rpa4all.com` | `http://127.0.0.1:3000` | OpenWebUI (via Nginx) |
| `www.rpa4all.com` | `http://127.0.0.1:8090` | Landing page |
| `rpa4all.com` | `http://127.0.0.1:8090` | Landing page (naked domain) |
| `homelab.rpa4all.com` | `http://127.0.0.1:8503` | Agents API |
| `grafana.rpa4all.com` | `http://127.0.0.1:3001` | Grafana |
| `estouaqui.rpa4all.com` | `http://127.0.0.1:3456` | Estou Aqui |
| `api.rpa4all.com/agents-api/*` | `http://127.0.0.1:8081` | Agents API (runner) |
| `api.rpa4all.com/code-runner/*` | `http://127.0.0.1:8081` | Code Runner |
| `ide.rpa4all.com` | `http://127.0.0.1:8081` | IDE remota |
| `ssh.rpa4all.com` | `ssh://127.0.0.1:22` | SSH via tunnel |
| `vpn.rpa4all.com` | `tcp://127.0.0.1:51821` | WireGuard VPN |
| `*` (catch-all) | `http_status:404` | Fallback |

---

## 11. SSH e VPN

### SSH direto (LAN)

```bash
ssh homelab@192.168.15.2
```

### SSH via Cloudflare Tunnel (externo)

```bash
# Requer cloudflared instalado localmente
# ~/.ssh/config:
Host homelab-tunnel
    HostName ssh.rpa4all.com
    User homelab
    ProxyCommand cloudflared access ssh --hostname %h

ssh homelab-tunnel
```

### WireGuard VPN

| Campo | Valor |
|-------|-------|
| **Endpoint** | `vpn.rpa4all.com:51821` (via Cloudflare Tunnel) |
| **Porta interna** | `51821` |

---

## 12. Mapa de Portas

| Porta | Serviço | Bind | Acesso |
|-------|---------|------|--------|
| `22` | SSH | `0.0.0.0` | LAN + Tunnel |
| `3000` | Nginx → OpenWebUI | `0.0.0.0` | LAN + Tunnel |
| `3001` | Grafana (Docker) | `0.0.0.0` | LAN + Tunnel |
| `3456` | Estou Aqui | — | LAN + Tunnel |
| `5432` | Eddie Postgres (Docker) | `0.0.0.0` | LAN |
| `8002` | OpenWebUI (Docker) | `127.0.0.1` | Loopback only |
| `8081` | Agents/Code Runner | — | Tunnel |
| `8088` | Secrets Agent | `127.0.0.1` | Loopback only |
| `8090` | Nginx Landing Page | `127.0.0.1` | Loopback → Tunnel |
| `8503` | Agents API (FastAPI) | — | LAN + Tunnel |
| `11434` | Ollama | `0.0.0.0` | LAN (firewall open) |
| `51821` | WireGuard | — | Tunnel |

---

## 13. Modelos Disponíveis

| Modelo | Parâmetros | Família | Tipo | Tempo médio |
|--------|-----------|---------|------|-------------|
| `eddie-assistant` | 7.6B | Qwen2 | Chat geral | ~25s |
| `eddie-coder` | 7.6B | Qwen2 | Geração de código | ~18s |
| `eddie-whatsapp` | 7.6B | Qwen2 | Interação WhatsApp | ~73s |
| `qwen2.5-coder:7b` | 7.6B | Qwen2 | Código (base) | ~5s |
| `llama3.2:3b` | 3.2B | Llama | Chat rápido | ~3s |
| `qwen2.5-coder:1.5b` | 1.5B | Qwen2 | Código ultra-rápido | ~2s |
| `nomic-embed-text` | 137M | Nomic-BERT | Embeddings only | <1s |
| `deepseek-v3.1:671b-cloud` | 671B | DeepSeek2 | Stub (cloud) | N/A |

> **Nota:** Todos os modelos rodam em CPU (Haswell AVX2, 31 GiB RAM). Modelos `eddie-*` são customizados via Modelfile com system prompts específicos.

---

## 14. Exemplos de Uso

### Python — Ollama via requests

```python
import requests

resp = requests.post("http://192.168.15.2:11434/v1/chat/completions", json={
    "model": "eddie-coder",
    "messages": [{"role": "user", "content": "Crie uma função Python de fibonacci"}]
})
print(resp.json()["choices"][0]["message"]["content"])
```

### Python — OpenWebUI via requests

```python
import requests

# Autenticar
auth = requests.post("https://openwebui.rpa4all.com/api/v1/auths/signin", json={
    "email": "edenilson.adm@gmail.com",
    "password": "<senha>"
})
token = auth.json()["token"]

# Chat
resp = requests.post("https://openwebui.rpa4all.com/api/chat/completions",
    headers={"Authorization": f"Bearer {token}"},
    json={"model": "eddie-assistant", "messages": [{"role": "user", "content": "Olá"}]}
)
print(resp.json()["choices"][0]["message"]["content"])
```

### JavaScript/Node.js — Ollama

```javascript
const resp = await fetch("http://192.168.15.2:11434/v1/chat/completions", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    model: "qwen2.5-coder:7b",
    messages: [{ role: "user", content: "Explique async/await" }]
  })
});
const data = await resp.json();
console.log(data.choices[0].message.content);
```

### cURL — Embeddings

```bash
curl http://192.168.15.2:11434/api/embeddings \
  -d '{"model":"nomic-embed-text","prompt":"texto para vetorizar"}'
```

---

> **Segurança:** Credenciais referenciadas neste documento devem ser obtidas exclusivamente via Secrets Agent (porta 8088). Nunca hardcodar senhas ou tokens.
