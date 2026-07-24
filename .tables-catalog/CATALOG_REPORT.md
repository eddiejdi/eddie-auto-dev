# Tables Catalog Report
**Generated:** 2026-07-24T20:01:27.497400
**Total Tables:** 63
**Schemas:** 5
**Sensitive Tables:** 4
**Source Files:** 38
---

## Summary by Category

### content (5)

- `public.content_queue` ✓ [unused] owner=`content_automation` — 14 cols, source=`python-ddl`
- `public.conversation_snapshots` ✓ [unused] owner=`tools` — 7 cols, source=`python-ddl`
- `public.conversations` ✓ [unused] owner=`tools` — 8 cols, source=`python-ddl`
- `public.messages` ✓ [active] owner=`tools` — 8 cols, source=`python-ddl`
- `whatsapp.messages` ✓ [active] owner=`scripts` — 7 cols, source=`python-ddl`

### general (8)

- `clear.tax_accumulated_losses` ✓ [unused] owner=`clear_trading_agent` — 4 cols, source=`sql`
- `clear.tax_events` ✓ [unused] owner=`clear_trading_agent` — 15 cols, source=`sql`
- `clear.tax_monthly_summary` ✓ [unused] owner=`clear_trading_agent` — 13 cols, source=`sql`
- `public.email_sends` ✓ [active] owner=`scripts` — 8 cols, source=`python-ddl`
- `public.ollama_payload_log` ✓ [unused] owner=`tools` — 5 cols, source=`python-ddl`
- `public.sent_applications` ✓ [active] owner=`scripts` — 6 cols, source=`python-ddl`
- `public.sent_drafts` ✓ [active] owner=`scripts` — 6 cols, source=`python-ddl`
- `whatsapp.sessions` ✓ [active] owner=`scripts` — 3 cols, source=`python-ddl`

### governance (2)

- `public.agent_actions` ✓ [active] owner=`platform` — 17 cols, source=`sql`
- `public.schema_migrations` ✓ [unused] owner=`platform` — 3 cols, source=`sql`

### home (3)

- `public.home_command_queue` ✓ [unused] owner=`grafana` — 8 cols, source=`python-ddl`
- `public.home_device_history` ✓ [unused] owner=`grafana` — 8 cols, source=`python-ddl`
- `public.home_devices` ✓ [unused] owner=`grafana` — 12 cols, source=`python-ddl`

### identity (1)

- `public.user_management` 🔒 [unused] owner=`user_management` — 13 cols, source=`python-ddl`

### ipc (1)

- `public.agent_ipc` ✓ [active] owner=`agent_bus` — 9 cols, source=`python-ddl`

### marketing (5)

- `marketing.campaigns` ✓ [active] owner=`marketing` — 7 cols, source=`python-ddl`
- `marketing.daily_metrics` ✓ [active] owner=`marketing` — 10 cols, source=`python-ddl`
- `marketing.email_log` ✓ [active] owner=`marketing` — 6 cols, source=`python-ddl`
- `marketing.leads` ✓ [active] owner=`marketing` — 16 cols, source=`python-ddl`
- `marketing.x_posts_log` ✓ [active] owner=`marketing` — 6 cols, source=`python-ddl`

### portal (4)

- `public.api_tokens` 🔒 [active] owner=`storage_portal` — 7 cols, source=`python-ddl`
- `public.contracts` 🔒 [active] owner=`storage_portal` — 31 cols, source=`python-ddl`
- `public.payments` ✓ [active] owner=`storage_portal` — 8 cols, source=`python-ddl`
- `public.portal_users` 🔒 [active] owner=`storage_portal` — 15 cols, source=`python-ddl`

### sentiment (5)

- `btc.llm_shadow_results` ✓ [unused] owner=`btc_trading_agent` — 11 cols, source=`python-ddl`
- `btc.news_sentiment` ✓ [unused] owner=`grafana` — 11 cols, source=`sql`
- `btc.sentiment_calibration` ✓ [unused] owner=`grafana` — 12 cols, source=`python-ddl`
- `btc.training_samples` ✓ [active] owner=`grafana` — 18 cols, source=`python-ddl`
- `public.training_samples` ✓ [active] owner=`scripts` — 13 cols, source=`python-ddl`

### trading (29)

- `btc.ai_plans` ✓ [unused] owner=`btc_trading_agent` — 9 cols, source=`python-ddl`
- `btc.ai_trade_controls` ✓ [unused] owner=`btc_trading_agent` — 18 cols, source=`python-ddl`
- `btc.ai_trade_windows` ✓ [unused] owner=`btc_trading_agent` — 19 cols, source=`python-ddl`
- `btc.candles` ✓ [active] owner=`btc_trading_agent` — 9 cols, source=`python-ddl`
- `btc.conversion_legs` ✓ [unused] owner=`btc_trading_agent` — 11 cols, source=`python-ddl`
- `btc.conversion_lock` ✓ [unused] owner=`btc_trading_agent` — 3 cols, source=`python-ddl`
- `btc.conversion_requests` ✓ [unused] owner=`btc_trading_agent` — 13 cols, source=`python-ddl`
- `btc.decisions` ✓ [active] owner=`btc_trading_agent` — 10 cols, source=`python-ddl`
- `btc.decisions_track_record_hourly` ✓ [unused] owner=`btc_trading_agent` — 8 cols, source=`python-ddl`
- `btc.exchange_account_ledgers` ✓ [unused] owner=`btc_trading_agent` — 12 cols, source=`python-ddl`
- `btc.exchange_balance_snapshots` ✓ [unused] owner=`btc_trading_agent` — 9 cols, source=`python-ddl`
- `btc.exchange_sync_state` ✓ [unused] owner=`btc_trading_agent` — 5 cols, source=`python-ddl`
- `btc.learning_rewards` ✓ [unused] owner=`btc_trading_agent` — 8 cols, source=`python-ddl`
- `btc.learning_rewards_retro` ✓ [active] owner=`btc_trading_agent` — 10 cols, source=`python-ddl`
- `btc.llm_calls` ✓ [active] owner=`btc_trading_agent` — 15 cols, source=`python-ddl`
- `btc.llm_log_config` ✓ [active] owner=`btc_trading_agent` — 10 cols, source=`python-ddl`
- `btc.market_states` ✓ [unused] owner=`btc_trading_agent` — 14 cols, source=`python-ddl`
- `btc.performance_stats` ✓ [active] owner=`btc_trading_agent` — 12 cols, source=`python-ddl`
- `btc.profile_allocations` ✓ [unused] owner=`btc_trading_agent` — 6 cols, source=`python-ddl`
- `btc.trades` ✓ [active] owner=`btc_trading_agent` — 14 cols, source=`python-ddl`
- `clear.ai_trade_controls` ✓ [unused] owner=`clear_trading_agent` — 11 cols, source=`sql`
- `clear.ai_trade_windows` ✓ [unused] owner=`clear_trading_agent` — 10 cols, source=`sql`
- `clear.candles` ✓ [active] owner=`clear_trading_agent` — 9 cols, source=`sql`
- `clear.decisions` ✓ [active] owner=`clear_trading_agent` — 11 cols, source=`sql`
- `clear.learning_rewards` ✓ [unused] owner=`clear_trading_agent` — 6 cols, source=`sql`
- `clear.market_states` ✓ [active] owner=`clear_trading_agent` — 12 cols, source=`sql`
- `clear.performance_stats` ✓ [active] owner=`clear_trading_agent` — 10 cols, source=`sql`
- `clear.trades` ✓ [active] owner=`clear_trading_agent` — 15 cols, source=`sql`
- `public.open_positions` ✓ [active] owner=`scripts` — 9 cols, source=`python-ddl`

## Ownership

- `btc_trading_agent`: 21 tables
- `clear_trading_agent`: 11 tables
- `scripts`: 7 tables
- `grafana`: 6 tables
- `marketing`: 5 tables
- `storage_portal`: 4 tables
- `tools`: 4 tables
- `platform`: 2 tables
- `agent_bus`: 1 tables
- `content_automation`: 1 tables
- `user_management`: 1 tables

## Lifecycle status

- `active`: 32
- `unused`: 31
