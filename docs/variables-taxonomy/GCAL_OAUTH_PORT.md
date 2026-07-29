# GCAL_OAUTH_PORT

## Propósito
Porta do servidor local de redirect usado no consentimento OAuth do Google Calendar (`scripts/misc/google_calendar_oauth_consent.py`). O homelab é headless, então o dono acessa via túnel SSH (`ssh -L <porta>:localhost:<porta> homelab`) e o redirect do Google volta por ele.

## Escopo
- **Consumidor**: `scripts/misc/google_calendar_oauth_consent.py` (`REDIRECT_PORT`).
- **Default**: `8771`.
- **Não usar 8765**: já é do vault server do homelab (`homelab-vault-backup.service` faz health-check em `http://localhost:8765/api/status`). Tentar bindar ali falha com `OSError: [Errno 98] Address already in use` — verificado em produção 2026-07-29.

## Relacionadas
- [[GOOGLE_OAUTH_SECRET_NAME]]
