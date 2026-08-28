# Taxonomy Orphans & Unused

**Generated:** 2026-07-24T20:01:32.530300

Tables without strong API links are marked `status=unused`.
APIs without table links are flagged `orphan=true` (status unchanged).

---

## Unused tables (31)

- `btc.ai_plans` — owner=`btc_trading_agent` category=`trading`
- `btc.ai_trade_controls` — owner=`btc_trading_agent` category=`trading`
- `btc.ai_trade_windows` — owner=`btc_trading_agent` category=`trading`
- `btc.conversion_legs` — owner=`btc_trading_agent` category=`trading`
- `btc.conversion_lock` — owner=`btc_trading_agent` category=`trading`
- `btc.conversion_requests` — owner=`btc_trading_agent` category=`trading`
- `btc.decisions_track_record_hourly` — owner=`btc_trading_agent` category=`trading`
- `btc.exchange_account_ledgers` — owner=`btc_trading_agent` category=`trading`
- `btc.exchange_balance_snapshots` — owner=`btc_trading_agent` category=`trading`
- `btc.exchange_sync_state` — owner=`btc_trading_agent` category=`trading`
- `btc.learning_rewards` — owner=`btc_trading_agent` category=`trading`
- `btc.llm_shadow_results` — owner=`btc_trading_agent` category=`sentiment`
- `btc.market_states` — owner=`btc_trading_agent` category=`trading`
- `btc.news_sentiment` — owner=`grafana` category=`sentiment`
- `btc.profile_allocations` — owner=`btc_trading_agent` category=`trading`
- `btc.sentiment_calibration` — owner=`grafana` category=`sentiment`
- `clear.ai_trade_controls` — owner=`clear_trading_agent` category=`trading`
- `clear.ai_trade_windows` — owner=`clear_trading_agent` category=`trading`
- `clear.learning_rewards` — owner=`clear_trading_agent` category=`trading`
- `clear.tax_accumulated_losses` — owner=`clear_trading_agent` category=`general`
- `clear.tax_events` — owner=`clear_trading_agent` category=`general`
- `clear.tax_monthly_summary` — owner=`clear_trading_agent` category=`general`
- `public.content_queue` — owner=`content_automation` category=`content`
- `public.conversation_snapshots` — owner=`tools` category=`content`
- `public.conversations` — owner=`tools` category=`content`
- `public.home_command_queue` — owner=`grafana` category=`home`
- `public.home_device_history` — owner=`grafana` category=`home`
- `public.home_devices` — owner=`grafana` category=`home`
- `public.ollama_payload_log` — owner=`tools` category=`general`
- `public.schema_migrations` — owner=`platform` category=`governance`
- `public.user_management` — owner=`user_management` category=`identity`

## Orphan APIs (no table link) (112)

### acervo (3)

- `POST /dossier` — service=`specialized_agents/bn_acervo_agent`
- `POST /jobs` — service=`specialized_agents/bn_acervo_agent`
- `POST /story` — service=`specialized_agents/bn_acervo_agent`

### admin (1)

- `GET /admin/users` — service=`specialized_agents/nextcloud_agent`

### agents (4)

- `GET /tool-interceptor/stats` — service=`tools/proxy_tool_interceptor`
- `GET /tool-interceptor/tools` — service=`tools/proxy_tool_interceptor`
- `POST /penalize_and_retrain` — service=`tools/operation_agent`
- `POST /test` — service=`specialized_agents/agent_communication_bus`

### auth (2)

- `POST /api/v1/auths/signin` — service=`docs`
- `POST /session/test-login` — service=`specialized_agents/conube_agent`

### banking (3)

- `GET /billing/pending` — service=`specialized_agents/conube_agent`
- `GET /cofrinho` — service=`specialized_agents/banking`
- `POST /billing/pay-pending` — service=`specialized_agents/conube_agent`

### cmdb (3)

- `POST /apply/glpi` — service=`specialized_agents/cmdb_agent`
- `POST /apply/netbox` — service=`specialized_agents/cmdb_agent`
- `POST /run` — service=`specialized_agents/cmdb_agent`

### general (8)

- `POST /print` — service=`deploy`
- `POST /query` — service=`specialized_agents/api`
- `POST /recording/clear` — service=`specialized_agents/api`
- `POST /recording/pause` — service=`specialized_agents/api`
- `POST /recording/resume` — service=`specialized_agents/api`
- `POST /trading/converse` — service=`specialized_agents/api`
- `POST /users` — service=`specialized_agents/api`
- `POST /{agent_id}/activate` — service=`specialized_agents/api`

### llm (8)

- `GET /api/tags` — service=`docs`
- `GET /copilot/model-info` — service=`specialized_agents/copilot_routes`
- `GET /resources` — service=`specialized_agents/huggingface_inference_agent`
- `GET /v1/models` — service=`specialized_agents/copilot_routes`
- `POST /api/generate` — service=`docs`
- `POST /chat` — service=`specialized_agents/nextcloud_agent`
- `POST /image/generate` — service=`specialized_agents/huggingface_inference_agent`
- `POST /v1/chat/completions` — service=`specialized_agents/copilot_routes`

### meetings (5)

- `GET /api/jobs` — service=`tools/meeting_translator`
- `GET /api/jobs/{job_id}` — service=`tools/meeting_translator`
- `GET /jobs/{job_id}` — service=`specialized_agents/bn_acervo_agent`
- `POST /api/join` — service=`tools/meeting_translator`
- `POST /jobs/cancel-active` — service=`specialized_agents/bn_acervo_agent`

### monitoring (7)

- `GET /admin/logs` — service=`specialized_agents/nextcloud_agent`
- `GET /dashboard/operational-summary` — service=`specialized_agents/conube_agent`
- `GET /debug/communication/subscribers` — service=`specialized_agents/api`
- `GET /debug/logs` — service=`specialized_agents/bn_acervo_agent`
- `GET /reports/daily-summary` — service=`specialized_agents/conube_agent`
- `GET /reports/daily-summary/cached` — service=`specialized_agents/conube_agent`
- `POST /alerts` — service=`specialized_agents/api`

### ops (6)

- `GET /actions/run-remediation` — service=`specialized_agents/conube_agent`
- `POST /actions/run-remediation` — service=`specialized_agents/conube_agent`
- `POST /company/close-open-financial-periods` — service=`specialized_agents/conube_agent`
- `POST /company/close-overdue-balances` — service=`specialized_agents/conube_agent`
- `POST /tasks/remediate-client-pending` — service=`specialized_agents/conube_agent`
- `POST /tasks/remediate-pending-selenium` — service=`specialized_agents/conube_agent`

### platform (7)

- `GET /api/v1/functions` — service=`docs`
- `GET /api/v2/packages` — service=`site/code_runner_manager`
- `GET /api/v2/runtimes` — service=`site/code_runner_manager`
- `GET /index` — service=`specialized_agents/api`
- `GET /panel` — service=`specialized_agents/api`
- `POST /api/v1/functions` — service=`docs`
- `POST /api/v2/execute` — service=`site/code_runner_manager`

### secrets (7)

- `DELETE /secrets/local/{name}` — service=`tools/secrets_agent`
- `GET /audit/recent` — service=`tools/secrets_agent`
- `GET /secrets` — service=`tools/secrets_agent`
- `GET /secrets/local/{name}` — service=`tools/secrets_agent`
- `GET /secrets/{item_id}` — service=`tools/secrets_agent`
- `POST /bw/unlock` — service=`tools/secrets_agent`
- `POST /secrets` — service=`tools/secrets_agent`

### social (25)

- `DELETE /tweets/{tweet_id}` — service=`tools/x_agent`
- `DELETE /tweets/{tweet_id}/like` — service=`tools/x_agent`
- `DELETE /tweets/{tweet_id}/retweet` — service=`tools/x_agent`
- `DELETE /users/{username}/follow` — service=`tools/x_agent`
- `GET /bookmarks` — service=`tools/x_agent`
- `GET /me/followers` — service=`tools/x_agent`
- `GET /me/following` — service=`tools/x_agent`
- `GET /mentions` — service=`tools/x_agent`
- `GET /profile` — service=`tools/x_agent`
- `GET /profile/{username}` — service=`tools/x_agent`
- `GET /search` — service=`tools/x_agent`
- `GET /timeline/home` — service=`tools/x_agent`
- `GET /timeline/user/{username}` — service=`tools/x_agent`
- `GET /tweets/{tweet_id}` — service=`tools/x_agent`
- `GET /users/{username}/followers` — service=`tools/x_agent`
- `GET /users/{username}/following` — service=`tools/x_agent`
- `GET /video/download` — service=`tools/x_agent`
- `GET /video/info` — service=`tools/x_agent`
- `POST /search` — service=`tools/x_agent`
- `POST /tweets` — service=`tools/x_agent`
- `POST /tweets/{tweet_id}/bookmark` — service=`tools/x_agent`
- `POST /tweets/{tweet_id}/like` — service=`tools/x_agent`
- `POST /tweets/{tweet_id}/retweet` — service=`tools/x_agent`
- `POST /users/{username}/follow` — service=`tools/x_agent`
- `POST /video/download` — service=`tools/x_agent`

### storage (18)

- `GET /admin/storage-diagnostics` — service=`specialized_agents/nextcloud_agent`
- `GET /download/file/{filename}` — service=`tools/x_agent`
- `GET /files/download` — service=`specialized_agents/nextcloud_agent`
- `GET /files/list` — service=`specialized_agents/nextcloud_agent`
- `GET /media/resources` — service=`specialized_agents/api`
- `GET /share/list` — service=`specialized_agents/nextcloud_agent`
- `GET /tape/component-quality/report` — service=`specialized_agents/tape_routes`
- `GET /tape/hba-test/report` — service=`specialized_agents/tape_routes`
- `POST /files/list` — service=`specialized_agents/nextcloud_agent`
- `POST /files/mkdir` — service=`specialized_agents/nextcloud_agent`
- `POST /files/upload` — service=`specialized_agents/nextcloud_agent`
- `POST /media/image/generate` — service=`specialized_agents/api`
- `POST /occ` — service=`specialized_agents/nextcloud_agent`
- `POST /share/create` — service=`specialized_agents/nextcloud_agent`
- `POST /tape/component-quality` — service=`specialized_agents/tape_routes`
- `POST /tape/hba-test` — service=`specialized_agents/tape_routes`
- `POST /vpn/install` — service=`specialized_agents/nextcloud_agent`
- `POST /vpn/provision` — service=`specialized_agents/nextcloud_agent`

### trading (2)

- `GET /balance` — service=`specialized_agents/banking`
- `GET /symbol/{symbol}/tick` — service=`mt5_bridge/bridge_api`

### wiki (3)

- `POST /evolve` — service=`specialized_agents/wiki_agent`
- `POST /raw` — service=`specialized_agents/wiki_agent`
- `POST /refactor` — service=`specialized_agents/wiki_agent`


## How to fix

1. Add `# taxonomy: tables=schema.table` above the route
2. Or OpenAPI `x-tables: [schema.table]`
3. Re-run `python3 tools/catalog_taxonomy.py --domain tables,apis`
