# Taxonomy Ownership Gaps

**Generated:** 2026-07-24T20:01:32.530738

## tables_unknown_owner (0)


## tables_unassigned_team (11)

- `public.conversation_snapshots`
- `public.conversations`
- `public.email_sends`
- `public.messages`
- `public.ollama_payload_log`
- `public.open_positions`
- `public.sent_applications`
- `public.sent_drafts`
- `public.training_samples`
- `whatsapp.messages`
- `whatsapp.sessions`

## apis_unknown_owner (0)


## apis_unassigned_team (23)

- `GET /api/quick/{action}`
- `GET /api/status`
- `GET /api/tags`
- `GET /api/v1/functions`
- `GET /api/v1/models`
- `GET /api/v1/models/{id}`
- `GET /callback`
- `GET /copilot/model-info`
- `GET /login/github`
- `GET /logout`
- `GET /portal`
- `GET /tool-interceptor/stats`
- `GET /tool-interceptor/tools`
- `GET /v1/models`
- `POST /api/chat`
- `POST /api/generate`
- `POST /api/v1/auths/signin`
- `POST /api/v1/functions`
- `POST /api/v1/rag/index`
- `POST /login/token`
- `POST /portal/notify`
- `POST /print`
- `POST /v1/chat/completions`

Fix: edit `OWNER_RULES` in `tools/taxonomy_meta.py` or add `taxonomy: owner=...; team=...` annotations.
