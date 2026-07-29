# GOOGLE_OAUTH_SECRET_NAME

## Propósito
Nome do secret no Authentik (via Secrets Agent `:8088`) que guarda o OAuth client do Google tipo **Desktop/Installed** — campos `client_id` e `client_secret`. Usado pela integração de Google Calendar do bot do WhatsApp para montar o client config OAuth em runtime, em vez de depender do `credentials.json` solto em `scripts/misc/calendar_data/`.

## Escopo
- **Consumidor**: `scripts/misc/google_calendar_integration.py` (`GOOGLE_OAUTH_SECRET`).
- **Default**: `google/oauth_client_installed` — entrada que já existe no Authentik (`authentik/google/oauth_client_installed#client_id` / `#client_secret`).
- **Atenção**: em 2026-07-29 a entrada existia mas os campos estavam **vazios** — entrada existir ≠ ter valor. Popular via `scripts/import_bw_secret_to_authentik.sh` (importa do Bitwarden) ou POST direto no Secrets Agent.

## Fluxo completo
1. `_client_config_from_vault()` busca `client_id`/`client_secret` do Authentik.
2. Se o cofre não tiver os valores, cai no `CREDENTIALS_FILE` (compatibilidade com instalações antigas).
3. O `token.pickle` (token de usuário pós-consentimento OAuth) continua local — é derivado, renovável e por-máquina; o que é segredo de longo prazo (client) fica no Authentik.

## Relacionadas
- [[SECRETS_AGENT_URL]], [[HOMELAB_URL]]
