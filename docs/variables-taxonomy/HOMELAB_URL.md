# HOMELAB_URL

## Propósito
URL base do Communication Bus do homelab (`bus_*` no `scripts/homelab_mcp_server.py`) — endpoint HTTP usado pelas ferramentas `bus_health`, `bus_get_messages`, `bus_publish`, `bus_record_result`, `bus_search_by_agent`.

## Escopo
- **Consumidor principal**: `scripts/homelab_mcp_server.py` (default `http://192.168.15.2:8503` se não setada).
- **Novo consumidor (2026-07-29)**: drop-in systemd `systemd/eddie-whatsapp-bot.service.d/env.conf` — o bot do WhatsApp importa `homelab_mcp_server.py` em processo (`scripts/misc/mcp_tool_bridge.py`) pra dar tool-calling ao modelo `shared-homelab`; sem essa var, as ferramentas `bus_*` resolvem o default (`192.168.15.2:8503`), que já é correto já que o bot roda no próprio host homelab — mas é setada explicitamente para não depender do default do módulo.
- **Valor típico**: `http://localhost:8503` quando o consumidor roda no próprio host homelab (192.168.15.2); `http://192.168.15.2:8503` quando roda remoto.

## Não confundir com
- `HOMELAB_USER` — usuário SSH do host homelab, variável não relacionada (nome parecido, propósito diferente).

## Relacionadas
- [[API_BASE_URL]], [[SECRETS_AGENT_URL]], [[DATABASE_URL]]
