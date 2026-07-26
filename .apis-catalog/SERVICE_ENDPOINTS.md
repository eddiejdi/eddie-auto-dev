# API Endpoints by Service

## deploy (1)

- `POST /print`

## docs (8)

- `GET /api/tags`
- `GET /api/v1/functions`
- `GET /api/v1/models`
- `GET /api/v1/models/{id}`
- `POST /api/generate`
- `POST /api/v1/auths/signin`
- `POST /api/v1/functions`
- `POST /api/v1/rag/index`

## marketing/app (3)

- `GET /`
- `GET /diagnostico`
- `GET /storage`

## marketing/lead_capture_api (3)

- `GET /marketing/health`
- `GET /marketing/leads/stats`
- `POST /marketing/leads`

## mt5_bridge/bridge_api (7)

- `GET /account`
- `GET /history/deals`
- `GET /orders`
- `GET /positions`
- `GET /symbol/{symbol}/rates`
- `GET /symbol/{symbol}/tick`
- `POST /order`

## scripts/misc (17)

- `DELETE /api/hosts/{name}`
- `GET /api/health`
- `GET /api/hosts`
- `GET /api/info/{name}`
- `GET /api/quick/{action}`
- `GET /api/status`
- `GET /api/test/{name}`
- `GET /callback`
- `GET /login/github`
- `GET /logout`
- `GET /portal`
- `POST /api/connect/{name}`
- `POST /api/disconnect/{name}`
- `POST /api/execute`
- `POST /api/hosts`
- `POST /login/token`
- `POST /portal/notify`

## scripts/training (1)

- `GET /api/learning-metrics`

## site/code_runner_manager (5)

- `DELETE /sessions/{session_id}`
- `GET /api/v2/packages`
- `GET /api/v2/runtimes`
- `GET /sessions`
- `POST /api/v2/execute`

## specialized_agents/agent_communication_bus (5)

- `GET /messages`
- `GET /stats`
- `POST /publish`
- `POST /send`
- `POST /test`

## specialized_agents/api (16)

- `GET /debug/communication/subscribers`
- `GET /index`
- `GET /media/resources`
- `GET /panel`
- `GET /status`
- `GET /{agent_id}/health`
- `HEAD /health`
- `POST /alerts`
- `POST /media/image/generate`
- `POST /query`
- `POST /recording/clear`
- `POST /recording/pause`
- `POST /recording/resume`
- `POST /trading/converse`
- `POST /users`
- `POST /{agent_id}/activate`

## specialized_agents/banking (2)

- `GET /balance`
- `GET /cofrinho`

## specialized_agents/bn_acervo_agent (6)

- `GET /debug/logs`
- `GET /jobs/{job_id}`
- `POST /dossier`
- `POST /jobs`
- `POST /jobs/cancel-active`
- `POST /story`

## specialized_agents/cmdb_agent (3)

- `POST /apply/glpi`
- `POST /apply/netbox`
- `POST /run`

## specialized_agents/conube_agent (12)

- `GET /actions/run-remediation`
- `GET /billing/pending`
- `GET /dashboard/operational-summary`
- `GET /reports/daily-summary`
- `GET /reports/daily-summary/cached`
- `POST /actions/run-remediation`
- `POST /billing/pay-pending`
- `POST /company/close-open-financial-periods`
- `POST /company/close-overdue-balances`
- `POST /session/test-login`
- `POST /tasks/remediate-client-pending`
- `POST /tasks/remediate-pending-selenium`

## specialized_agents/copilot_routes (3)

- `GET /copilot/model-info`
- `GET /v1/models`
- `POST /v1/chat/completions`

## specialized_agents/huggingface_inference_agent (2)

- `GET /resources`
- `POST /image/generate`

## specialized_agents/nextcloud_agent (15)

- `GET /admin/logs`
- `GET /admin/status`
- `GET /admin/storage-diagnostics`
- `GET /admin/users`
- `GET /files/download`
- `GET /files/list`
- `GET /share/list`
- `POST /chat`
- `POST /files/list`
- `POST /files/mkdir`
- `POST /files/upload`
- `POST /occ`
- `POST /share/create`
- `POST /vpn/install`
- `POST /vpn/provision`

## specialized_agents/tape_routes (7)

- `GET /tape/component-quality/report`
- `GET /tape/component-quality/status`
- `GET /tape/hba-test/report`
- `GET /tape/hba-test/status`
- `GET /tape/health`
- `POST /tape/component-quality`
- `POST /tape/hba-test`

## specialized_agents/wiki_agent (3)

- `POST /evolve`
- `POST /raw`
- `POST /refactor`

## storage_portal_api (11)

- `GET /health`
- `GET /storage/portal/bootstrap`
- `GET /storage/portal/files`
- `PATCH /storage/portal/users/{user_id}`
- `POST /storage/contracts/finalize`
- `POST /storage/portal/files/folder`
- `POST /storage/portal/files/upload`
- `POST /storage/portal/payments`
- `POST /storage/portal/subusers`
- `POST /storage/portal/tokens`
- `POST /storage/request-access`

## tools/meeting_translator (3)

- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `POST /api/join`

## tools/operation_agent (2)

- `POST /evoke`
- `POST /penalize_and_retrain`

## tools/proxy_tool_interceptor (3)

- `GET /tool-interceptor/stats`
- `GET /tool-interceptor/tools`
- `POST /api/chat`

## tools/secrets_agent (9)

- `DELETE /secrets/local/{name}`
- `GET /audit/recent`
- `GET /authentik/status`
- `GET /bw/status`
- `GET /secrets`
- `GET /secrets/local/{name}`
- `GET /secrets/{item_id}`
- `POST /bw/unlock`
- `POST /secrets`

## tools/x_agent (27)

- `DELETE /tweets/{tweet_id}`
- `DELETE /tweets/{tweet_id}/like`
- `DELETE /tweets/{tweet_id}/retweet`
- `DELETE /users/{username}/follow`
- `GET /bookmarks`
- `GET /download/file/{filename}`
- `GET /me/followers`
- `GET /me/following`
- `GET /mentions`
- `GET /metrics`
- `GET /profile`
- `GET /profile/{username}`
- `GET /search`
- `GET /timeline/home`
- `GET /timeline/user/{username}`
- `GET /tweets/{tweet_id}`
- `GET /users/{username}/followers`
- `GET /users/{username}/following`
- `GET /video/download`
- `GET /video/info`
- `POST /search`
- `POST /tweets`
- `POST /tweets/{tweet_id}/bookmark`
- `POST /tweets/{tweet_id}/like`
- `POST /tweets/{tweet_id}/retweet`
- `POST /users/{username}/follow`
- `POST /video/download`

