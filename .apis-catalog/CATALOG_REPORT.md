# APIs Catalog Report
**Generated:** 2026-07-24T20:01:28.940347
**Total Endpoints:** 174
**Services:** 25
**Sensitive Endpoints:** 17
**Source Files:** 32
---

## Summary by Category

### acervo (3)

- `POST /dossier` ✓ [active] owner=`bn_acervo` — service=`specialized_agents/bn_acervo_agent` source=`fastapi`
- `POST /jobs` ✓ [active] owner=`bn_acervo` — service=`specialized_agents/bn_acervo_agent` source=`fastapi`
- `POST /story` ✓ [active] owner=`bn_acervo` — service=`specialized_agents/bn_acervo_agent` source=`fastapi`

### admin (1)

- `GET /admin/users` ✓ [active] owner=`nextcloud` — service=`specialized_agents/nextcloud_agent` source=`fastapi`

### agents (9)

- `GET /messages` ✓ [active] owner=`agent_bus` — service=`specialized_agents/agent_communication_bus` source=`fastapi` tables=public.agent_ipc
- `GET /stats` ✓ [active] owner=`agent_bus` — service=`specialized_agents/agent_communication_bus` source=`fastapi` tables=public.agent_ipc
- `GET /tool-interceptor/stats` ✓ [active] owner=`tools` — service=`tools/proxy_tool_interceptor` source=`fastapi`
- `GET /tool-interceptor/tools` ✓ [active] owner=`tools` — service=`tools/proxy_tool_interceptor` source=`fastapi`
- `POST /evoke` ✓ [active] owner=`operation_agent` — service=`tools/operation_agent` source=`fastapi` tables=public.agent_actions
- `POST /penalize_and_retrain` ✓ [active] owner=`operation_agent` — service=`tools/operation_agent` source=`fastapi`
- `POST /publish` ✓ [active] owner=`agent_bus` — service=`specialized_agents/agent_communication_bus` source=`fastapi` tables=public.agent_ipc
- `POST /send` ✓ [active] owner=`agent_bus` — service=`specialized_agents/agent_communication_bus` source=`fastapi` tables=public.agent_ipc
- `POST /test` ✓ [active] owner=`agent_bus` — service=`specialized_agents/agent_communication_bus` source=`fastapi`

### auth (9)

- `DELETE /sessions/{session_id}` 🔒 [active] owner=`code_runner` — service=`site/code_runner_manager` source=`fastapi`
- `GET /callback` 🔒 [active] owner=`scripts` — service=`scripts/misc` source=`flask`
- `GET /login/github` 🔒 [active] owner=`scripts` — service=`scripts/misc` source=`flask`
- `GET /logout` 🔒 [active] owner=`scripts` — service=`scripts/misc` source=`flask`
- `GET /sessions` 🔒 [active] owner=`code_runner` — service=`site/code_runner_manager` source=`fastapi`
- `POST /api/v1/auths/signin` 🔒 [active] owner=`docs` — service=`docs` source=`openapi`
- `POST /login/token` 🔒 [active] owner=`scripts` — service=`scripts/misc` source=`flask`
- `POST /session/test-login` 🔒 [active] owner=`conube` — service=`specialized_agents/conube_agent` source=`fastapi`
- `POST /storage/portal/tokens` 🔒 [active] owner=`storage_portal` — service=`storage_portal_api` source=`fastapi` tables=public.api_tokens,public.portal_users,public.contracts

### banking (3)

- `GET /billing/pending` ✓ [active] owner=`conube` — service=`specialized_agents/conube_agent` source=`fastapi`
- `GET /cofrinho` ✓ [active] owner=`banking` — service=`specialized_agents/banking` source=`fastapi`
- `POST /billing/pay-pending` ✓ [active] owner=`conube` — service=`specialized_agents/conube_agent` source=`fastapi`

### cmdb (3)

- `POST /apply/glpi` ✓ [active] owner=`cmdb` — service=`specialized_agents/cmdb_agent` source=`fastapi`
- `POST /apply/netbox` ✓ [active] owner=`cmdb` — service=`specialized_agents/cmdb_agent` source=`fastapi`
- `POST /run` ✓ [active] owner=`cmdb` — service=`specialized_agents/cmdb_agent` source=`fastapi`

### general (9)

- `POST /api/execute` ✓ [active] owner=`ssh_agent` — service=`scripts/misc` source=`flask`
- `POST /print` ✓ [active] owner=`deploy` — service=`deploy` source=`flask`
- `POST /query` ✓ [active] owner=`api_server` — service=`specialized_agents/api` source=`fastapi`
- `POST /recording/clear` ✓ [active] owner=`api_server` — service=`specialized_agents/api` source=`fastapi`
- `POST /recording/pause` ✓ [active] owner=`api_server` — service=`specialized_agents/api` source=`fastapi`
- `POST /recording/resume` ✓ [active] owner=`api_server` — service=`specialized_agents/api` source=`fastapi`
- `POST /trading/converse` ✓ [active] owner=`api_server` — service=`specialized_agents/api` source=`fastapi`
- `POST /users` ✓ [active] owner=`api_server` — service=`specialized_agents/api` source=`fastapi`
- `POST /{agent_id}/activate` ✓ [active] owner=`api_server` — service=`specialized_agents/api` source=`fastapi`

### health (14)

- `GET /admin/status` ✓ [active] owner=`nextcloud` — service=`specialized_agents/nextcloud_agent` source=`fastapi`
- `GET /api/health` ✓ [active] owner=`ssh_agent` — service=`scripts/misc` source=`flask`
- `GET /api/status` ✓ [active] owner=`scripts` — service=`scripts/misc` source=`flask`
- `GET /authentik/status` 🔒 [active] owner=`secrets_agent` — service=`tools/secrets_agent` source=`fastapi`
- `GET /bw/status` ✓ [active] owner=`secrets_agent` — service=`tools/secrets_agent` source=`fastapi`
- `GET /health` ✓ [active] owner=`storage_portal` — service=`storage_portal_api` source=`fastapi`
- `GET /marketing/health` ✓ [active] owner=`marketing` — service=`marketing/lead_capture_api` source=`fastapi` tables=marketing.leads,marketing.daily_metrics
- `GET /metrics` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`
- `GET /status` ✓ [active] owner=`api_server` — service=`specialized_agents/api` source=`fastapi`
- `GET /tape/component-quality/status` ✓ [active] owner=`tape` — service=`specialized_agents/tape_routes` source=`fastapi`
- `GET /tape/hba-test/status` ✓ [active] owner=`tape` — service=`specialized_agents/tape_routes` source=`fastapi`
- `GET /tape/health` ✓ [active] owner=`tape` — service=`specialized_agents/tape_routes` source=`fastapi`
- `GET /{agent_id}/health` ✓ [active] owner=`api_server` — service=`specialized_agents/api` source=`fastapi`
- `HEAD /health` ✓ [active] owner=`api_server` — service=`specialized_agents/api` source=`fastapi`

### infra (8)

- `DELETE /api/hosts/{name}` ✓ [active] owner=`ssh_agent` — service=`scripts/misc` source=`flask`
- `GET /api/hosts` ✓ [active] owner=`ssh_agent` — service=`scripts/misc` source=`flask`
- `GET /api/info/{name}` ✓ [active] owner=`ssh_agent` — service=`scripts/misc` source=`flask`
- `GET /api/quick/{action}` ✓ [active] owner=`scripts` — service=`scripts/misc` source=`flask`
- `GET /api/test/{name}` ✓ [active] owner=`ssh_agent` — service=`scripts/misc` source=`flask`
- `POST /api/connect/{name}` ✓ [active] owner=`ssh_agent` — service=`scripts/misc` source=`flask`
- `POST /api/disconnect/{name}` ✓ [active] owner=`ssh_agent` — service=`scripts/misc` source=`flask`
- `POST /api/hosts` ✓ [active] owner=`ssh_agent` — service=`scripts/misc` source=`flask`

### llm (12)

- `GET /api/tags` ✓ [active] owner=`docs` — service=`docs` source=`openapi`
- `GET /api/v1/models` ✓ [active] owner=`docs` — service=`docs` source=`openapi` tables=btc.llm_calls,btc.llm_log_config
- `GET /api/v1/models/{id}` ✓ [active] owner=`docs` — service=`docs` source=`openapi` tables=btc.llm_calls
- `GET /copilot/model-info` ✓ [active] owner=`specialized_agents` — service=`specialized_agents/copilot_routes` source=`fastapi`
- `GET /resources` ✓ [active] owner=`huggingface` — service=`specialized_agents/huggingface_inference_agent` source=`fastapi`
- `GET /v1/models` ✓ [active] owner=`specialized_agents` — service=`specialized_agents/copilot_routes` source=`fastapi`
- `POST /api/chat` ✓ [active] owner=`tools` — service=`tools/proxy_tool_interceptor` source=`fastapi`
- `POST /api/generate` ✓ [active] owner=`docs` — service=`docs` source=`openapi`
- `POST /api/v1/rag/index` ✓ [active] owner=`docs` — service=`docs` source=`openapi` tables=btc.training_samples
- `POST /chat` ✓ [active] owner=`nextcloud` — service=`specialized_agents/nextcloud_agent` source=`fastapi`
- `POST /image/generate` ✓ [active] owner=`huggingface` — service=`specialized_agents/huggingface_inference_agent` source=`fastapi`
- `POST /v1/chat/completions` ✓ [active] owner=`specialized_agents` — service=`specialized_agents/copilot_routes` source=`fastapi`

### marketing (2)

- `GET /` ✓ [active] owner=`marketing` — service=`marketing/app` source=`fastapi`
- `GET /diagnostico` ✓ [active] owner=`marketing` — service=`marketing/app` source=`fastapi`

### meetings (5)

- `GET /api/jobs` ✓ [active] owner=`meeting_translator` — service=`tools/meeting_translator` source=`fastapi`
- `GET /api/jobs/{job_id}` ✓ [active] owner=`meeting_translator` — service=`tools/meeting_translator` source=`fastapi`
- `GET /jobs/{job_id}` ✓ [active] owner=`bn_acervo` — service=`specialized_agents/bn_acervo_agent` source=`fastapi`
- `POST /api/join` ✓ [active] owner=`meeting_translator` — service=`tools/meeting_translator` source=`fastapi`
- `POST /jobs/cancel-active` ✓ [active] owner=`bn_acervo` — service=`specialized_agents/bn_acervo_agent` source=`fastapi`

### monitoring (8)

- `GET /admin/logs` ✓ [active] owner=`nextcloud` — service=`specialized_agents/nextcloud_agent` source=`fastapi`
- `GET /api/learning-metrics` ✓ [active] owner=`grafana` — service=`scripts/training` source=`flask`
- `GET /dashboard/operational-summary` ✓ [active] owner=`conube` — service=`specialized_agents/conube_agent` source=`fastapi`
- `GET /debug/communication/subscribers` ✓ [active] owner=`api_server` — service=`specialized_agents/api` source=`fastapi`
- `GET /debug/logs` ✓ [active] owner=`bn_acervo` — service=`specialized_agents/bn_acervo_agent` source=`fastapi`
- `GET /reports/daily-summary` ✓ [active] owner=`conube` — service=`specialized_agents/conube_agent` source=`fastapi`
- `GET /reports/daily-summary/cached` ✓ [active] owner=`conube` — service=`specialized_agents/conube_agent` source=`fastapi`
- `POST /alerts` ✓ [active] owner=`api_server` — service=`specialized_agents/api` source=`fastapi`

### ops (6)

- `GET /actions/run-remediation` ✓ [active] owner=`conube` — service=`specialized_agents/conube_agent` source=`fastapi`
- `POST /actions/run-remediation` ✓ [active] owner=`conube` — service=`specialized_agents/conube_agent` source=`fastapi`
- `POST /company/close-open-financial-periods` ✓ [active] owner=`conube` — service=`specialized_agents/conube_agent` source=`fastapi`
- `POST /company/close-overdue-balances` ✓ [active] owner=`conube` — service=`specialized_agents/conube_agent` source=`fastapi`
- `POST /tasks/remediate-client-pending` ✓ [active] owner=`conube` — service=`specialized_agents/conube_agent` source=`fastapi`
- `POST /tasks/remediate-pending-selenium` ✓ [active] owner=`conube` — service=`specialized_agents/conube_agent` source=`fastapi`

### platform (7)

- `GET /api/v1/functions` ✓ [deprecated] owner=`docs` — service=`docs` source=`openapi`
- `GET /api/v2/packages` ✓ [active] owner=`code_runner` — service=`site/code_runner_manager` source=`fastapi`
- `GET /api/v2/runtimes` ✓ [active] owner=`code_runner` — service=`site/code_runner_manager` source=`fastapi`
- `GET /index` ✓ [active] owner=`api_server` — service=`specialized_agents/api` source=`fastapi`
- `GET /panel` ✓ [active] owner=`api_server` — service=`specialized_agents/api` source=`fastapi`
- `POST /api/v1/functions` ✓ [active] owner=`docs` — service=`docs` source=`openapi`
- `POST /api/v2/execute` ✓ [active] owner=`code_runner` — service=`site/code_runner_manager` source=`fastapi`

### secrets (7)

- `DELETE /secrets/local/{name}` 🔒 [active] owner=`secrets_agent` — service=`tools/secrets_agent` source=`fastapi`
- `GET /audit/recent` 🔒 [active] owner=`secrets_agent` — service=`tools/secrets_agent` source=`fastapi`
- `GET /secrets` 🔒 [active] owner=`secrets_agent` — service=`tools/secrets_agent` source=`fastapi`
- `GET /secrets/local/{name}` 🔒 [active] owner=`secrets_agent` — service=`tools/secrets_agent` source=`fastapi`
- `GET /secrets/{item_id}` 🔒 [active] owner=`secrets_agent` — service=`tools/secrets_agent` source=`fastapi`
- `POST /bw/unlock` 🔒 [active] owner=`secrets_agent` — service=`tools/secrets_agent` source=`fastapi`
- `POST /secrets` 🔒 [active] owner=`secrets_agent` — service=`tools/secrets_agent` source=`fastapi`

### social (25)

- `DELETE /tweets/{tweet_id}` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`
- `DELETE /tweets/{tweet_id}/like` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`
- `DELETE /tweets/{tweet_id}/retweet` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`
- `DELETE /users/{username}/follow` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`
- `GET /bookmarks` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`
- `GET /me/followers` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`
- `GET /me/following` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`
- `GET /mentions` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`
- `GET /profile` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`
- `GET /profile/{username}` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`
- `GET /search` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`
- `GET /timeline/home` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`
- `GET /timeline/user/{username}` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`
- `GET /tweets/{tweet_id}` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`
- `GET /users/{username}/followers` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`
- `GET /users/{username}/following` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`
- `GET /video/download` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`
- `GET /video/info` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`
- `POST /search` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`
- `POST /tweets` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`
- `POST /tweets/{tweet_id}/bookmark` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`
- `POST /tweets/{tweet_id}/like` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`
- `POST /tweets/{tweet_id}/retweet` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`
- `POST /users/{username}/follow` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`
- `POST /video/download` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`

### storage (30)

- `GET /admin/storage-diagnostics` ✓ [active] owner=`nextcloud` — service=`specialized_agents/nextcloud_agent` source=`fastapi`
- `GET /download/file/{filename}` ✓ [active] owner=`x_agent` — service=`tools/x_agent` source=`fastapi`
- `GET /files/download` ✓ [active] owner=`nextcloud` — service=`specialized_agents/nextcloud_agent` source=`fastapi`
- `GET /files/list` ✓ [active] owner=`nextcloud` — service=`specialized_agents/nextcloud_agent` source=`fastapi`
- `GET /media/resources` ✓ [active] owner=`api_server` — service=`specialized_agents/api` source=`fastapi`
- `GET /portal` ✓ [active] owner=`scripts` — service=`scripts/misc` source=`flask`
- `GET /share/list` ✓ [active] owner=`nextcloud` — service=`specialized_agents/nextcloud_agent` source=`fastapi`
- `GET /storage` ✓ [active] owner=`marketing` — service=`marketing/app` source=`fastapi`
- `GET /storage/portal/bootstrap` ✓ [active] owner=`storage_portal` — service=`storage_portal_api` source=`fastapi` tables=public.contracts,public.portal_users,public.api_tokens
- `GET /storage/portal/files` ✓ [active] owner=`storage_portal` — service=`storage_portal_api` source=`fastapi` tables=public.contracts
- `GET /tape/component-quality/report` ✓ [active] owner=`tape` — service=`specialized_agents/tape_routes` source=`fastapi`
- `GET /tape/hba-test/report` ✓ [active] owner=`tape` — service=`specialized_agents/tape_routes` source=`fastapi`
- `PATCH /storage/portal/users/{user_id}` ✓ [active] owner=`storage_portal` — service=`storage_portal_api` source=`fastapi` tables=public.portal_users,public.contracts
- `POST /files/list` ✓ [active] owner=`nextcloud` — service=`specialized_agents/nextcloud_agent` source=`fastapi`
- `POST /files/mkdir` ✓ [active] owner=`nextcloud` — service=`specialized_agents/nextcloud_agent` source=`fastapi`
- `POST /files/upload` ✓ [active] owner=`nextcloud` — service=`specialized_agents/nextcloud_agent` source=`fastapi`
- `POST /media/image/generate` ✓ [active] owner=`api_server` — service=`specialized_agents/api` source=`fastapi`
- `POST /occ` ✓ [active] owner=`nextcloud` — service=`specialized_agents/nextcloud_agent` source=`fastapi`
- `POST /portal/notify` ✓ [active] owner=`scripts` — service=`scripts/misc` source=`flask`
- `POST /share/create` ✓ [active] owner=`nextcloud` — service=`specialized_agents/nextcloud_agent` source=`fastapi`
- `POST /storage/contracts/finalize` ✓ [active] owner=`storage_portal` — service=`storage_portal_api` source=`fastapi` tables=public.contracts,public.portal_users,public.payments
- `POST /storage/portal/files/folder` ✓ [active] owner=`storage_portal` — service=`storage_portal_api` source=`fastapi`
- `POST /storage/portal/files/upload` ✓ [active] owner=`storage_portal` — service=`storage_portal_api` source=`fastapi` tables=public.payments,public.contract
- `POST /storage/portal/payments` ✓ [active] owner=`storage_portal` — service=`storage_portal_api` source=`fastapi` tables=public.payments,public.contracts,public.portal_users
- `POST /storage/portal/subusers` ✓ [active] owner=`storage_portal` — service=`storage_portal_api` source=`fastapi` tables=public.portal_users,public.contracts
- `POST /storage/request-access` ✓ [active] owner=`storage_portal` — service=`storage_portal_api` source=`fastapi` tables=public.contracts,public.portal_users
- `POST /tape/component-quality` ✓ [active] owner=`tape` — service=`specialized_agents/tape_routes` source=`fastapi`
- `POST /tape/hba-test` ✓ [active] owner=`tape` — service=`specialized_agents/tape_routes` source=`fastapi`
- `POST /vpn/install` ✓ [active] owner=`nextcloud` — service=`specialized_agents/nextcloud_agent` source=`fastapi`
- `POST /vpn/provision` ✓ [active] owner=`nextcloud` — service=`specialized_agents/nextcloud_agent` source=`fastapi`

### trading (10)

- `GET /account` ✓ [active] owner=`mt5_bridge` — service=`mt5_bridge/bridge_api` source=`fastapi` tables=clear.performance_stats,btc.performance_stats,clear.trades
- `GET /balance` ✓ [active] owner=`banking` — service=`specialized_agents/banking` source=`fastapi`
- `GET /history/deals` ✓ [active] owner=`mt5_bridge` — service=`mt5_bridge/bridge_api` source=`fastapi` tables=clear.trades,btc.trades,clear.decisions,btc.decisions
- `GET /marketing/leads/stats` ✓ [active] owner=`marketing` — service=`marketing/lead_capture_api` source=`fastapi` tables=marketing.leads,marketing.daily_metrics
- `GET /orders` ✓ [active] owner=`mt5_bridge` — service=`mt5_bridge/bridge_api` source=`fastapi` tables=clear.trades,btc.trades
- `GET /positions` ✓ [active] owner=`mt5_bridge` — service=`mt5_bridge/bridge_api` source=`fastapi` tables=clear.trades,btc.trades
- `GET /symbol/{symbol}/rates` ✓ [active] owner=`mt5_bridge` — service=`mt5_bridge/bridge_api` source=`fastapi` tables=clear.candles,btc.candles,clear.market_states
- `GET /symbol/{symbol}/tick` ✓ [active] owner=`mt5_bridge` — service=`mt5_bridge/bridge_api` source=`fastapi`
- `POST /marketing/leads` ✓ [active] owner=`marketing` — service=`marketing/lead_capture_api` source=`fastapi` tables=marketing.leads,marketing.daily_metrics,marketing.email_log
- `POST /order` ✓ [active] owner=`mt5_bridge` — service=`mt5_bridge/bridge_api` source=`fastapi` tables=clear.trades,btc.trades

### wiki (3)

- `POST /evolve` ✓ [active] owner=`wiki` — service=`specialized_agents/wiki_agent` source=`fastapi`
- `POST /raw` ✓ [active] owner=`wiki` — service=`specialized_agents/wiki_agent` source=`fastapi`
- `POST /refactor` ✓ [active] owner=`wiki` — service=`specialized_agents/wiki_agent` source=`fastapi`

## Ownership

- `x_agent`: 27 endpoints
- `api_server`: 16 endpoints
- `nextcloud`: 15 endpoints
- `conube`: 12 endpoints
- `storage_portal`: 11 endpoints
- `ssh_agent`: 9 endpoints
- `secrets_agent`: 9 endpoints
- `scripts`: 8 endpoints
- `docs`: 8 endpoints
- `mt5_bridge`: 7 endpoints
- `tape`: 7 endpoints
- `marketing`: 6 endpoints
- `bn_acervo`: 6 endpoints
- `code_runner`: 5 endpoints
- `agent_bus`: 5 endpoints
- `meeting_translator`: 3 endpoints
- `specialized_agents`: 3 endpoints
- `tools`: 3 endpoints
- `cmdb`: 3 endpoints
- `wiki`: 3 endpoints
- `banking`: 2 endpoints
- `huggingface`: 2 endpoints
- `operation_agent`: 2 endpoints
- `grafana`: 1 endpoints
- `deploy`: 1 endpoints

## Lifecycle status

- `active`: 173
- `deprecated`: 1
