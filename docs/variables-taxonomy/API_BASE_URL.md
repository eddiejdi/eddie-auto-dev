# API_BASE_URL

## Propósito
URL base do backend "API Estou Aqui" (Express/Sequelize) — endpoint HTTP usado pelas ferramentas `api_*` em `scripts/homelab_mcp_server.py` (`api_health`, `api_auth_login`, `api_events_list`, `api_events_get`, `api_events_create`, `api_checkins_create`).

## Escopo
- **Consumidor principal**: `scripts/homelab_mcp_server.py` (default `http://192.168.15.2:3000` se não setada).
- **Novo consumidor (2026-07-29)**: drop-in systemd `systemd/eddie-whatsapp-bot.service.d/env.conf` — mesmo motivo de [[HOMELAB_URL]]: o bot do WhatsApp importa `homelab_mcp_server.py` em processo via `scripts/misc/mcp_tool_bridge.py`.
- **Valor típico**: `http://localhost:3000` quando o consumidor roda no próprio host homelab.

## Relacionadas
- [[HOMELAB_URL]], [[SECRETS_AGENT_URL]], [[DATABASE_URL]]
