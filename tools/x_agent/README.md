# X Agent — Eddie Auto-Dev

Serviço para interação completa com X.com (Twitter) via API v2.

## Funcionalidades

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/health` | GET | Health check |
| `/metrics` | GET | Métricas Prometheus |
| `/tweets` | POST | Postar tweet |
| `/tweets/{id}` | GET | Obter tweet |
| `/tweets/{id}` | DELETE | Deletar tweet |
| `/tweets/{id}/like` | POST/DELETE | Like/Unlike |
| `/tweets/{id}/retweet` | POST/DELETE | Retweet/Unretweet |
| `/tweets/{id}/bookmark` | POST | Salvar nos bookmarks |
| `/timeline/home` | GET | Timeline home |
| `/timeline/user/{username}` | GET | Tweets de um usuário |
| `/search` | GET/POST | Buscar tweets |
| `/mentions` | GET | Menções ao user autenticado |
| `/profile` | GET | Perfil do autenticado |
| `/profile/{username}` | GET | Perfil de usuário |
| `/users/{username}/follow` | POST/DELETE | Follow/Unfollow |
| `/users/{username}/followers` | GET | Seguidores |
| `/users/{username}/following` | GET | Seguindo |
| `/me/followers` | GET | Meus seguidores |
| `/me/following` | GET | Quem eu sigo |
| `/bookmarks` | GET | Meus bookmarks |

## Credenciais (Secrets Agent)

Todas armazenadas no Secrets Agent (porta 8088):

| Secret | Descrição |
|--------|-----------|
| `eddie/x_client_id` | OAuth 2.0 Client ID |
| `eddie/x_client_secret` | OAuth 2.0 Client Secret |
| `eddie/x_bearer_token` | Bearer Token (App-only) |
| `eddie/x_api_key` | Consumer Key (OAuth 1.0a) |
| `eddie/x_api_secret` | Consumer Secret (OAuth 1.0a) |
| `eddie/x_access_token` | Access Token (OAuth 1.0a) |
| `eddie/x_access_secret` | Access Token Secret (OAuth 1.0a) |

## Porta

- **API**: 8515
- **Prometheus Metrics**: 8002

## Deploy

```bash
# Instalar dependências
pip install httpx authlib fastapi uvicorn prometheus_client

# Executar
python tools/x_agent/x_agent.py

# Ou via systemd
sudo cp tools/x_agent/x-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now x-agent
```

## Limites da API (Free Tier)

- **Post tweets**: 1.500/mês
- **Read tweets**: Sem acesso a search (requer Basic $100/mês)
- **User lookup**: Limitado
- **Timeline**: Requer OAuth 2.0 user context

## Integração Open WebUI

Tool `homelab_x_agent` atribuída ao modelo `x-agent` no Open WebUI.
