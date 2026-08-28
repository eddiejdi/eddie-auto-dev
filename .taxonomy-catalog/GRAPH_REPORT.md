# Taxonomy Cross-Domain Graph

**Generated:** 2026-07-24T20:01:32.515556

**Nodes:** variables=1998, tables=63, apis=174, domains=30

**Edges:** 1266 (strong entity links ≈ 290)

**Relation types:** colocated, domain_affinity, explicit, in_domain, name_match, schema_hint

---

## Domains

| Domain | Variables | Tables | APIs |
|--------|----------:|-------:|-----:|
| acervo | 0 | 0 | 3 |
| admin | 0 | 0 | 1 |
| agents | 4 | 0 | 9 |
| auth | 0 | 0 | 9 |
| banking | 1 | 0 | 3 |
| cmdb | 7 | 0 | 3 |
| content | 0 | 5 | 0 |
| database | 48 | 0 | 0 |
| general | 0 | 5 | 9 |
| governance | 0 | 2 | 0 |
| health | 0 | 0 | 14 |
| home | 0 | 3 | 0 |
| identity | 0 | 1 | 0 |
| infra | 5 | 0 | 8 |
| integrations | 14 | 0 | 0 |
| ipc | 0 | 1 | 0 |
| llm | 425 | 0 | 12 |
| marketing | 0 | 5 | 2 |
| meetings | 0 | 0 | 5 |
| monitoring | 21 | 0 | 8 |
| ops | 0 | 0 | 6 |
| platform | 0 | 0 | 7 |
| portal | 0 | 4 | 0 |
| secrets | 125 | 0 | 7 |
| sentiment | 0 | 5 | 0 |
| services | 1235 | 0 | 0 |
| social | 48 | 0 | 25 |
| storage | 16 | 0 | 30 |
| trading | 43 | 32 | 10 |
| wiki | 6 | 0 | 3 |

## Top linked entities

- `domain:llm` (degree=112)
- `domain:secrets` (degree=107)
- `domain:trading` (degree=85)
- `domain:social` (degree=73)
- `domain:services` (degree=50)
- `domain:database` (degree=49)
- `domain:storage` (degree=46)
- `api:GET /marketing/leads/stats` (degree=40)
- `api:GET /history/deals` (degree=37)
- `api:GET /account` (degree=36)
- `api:GET /symbol/{symbol}/rates` (degree=36)
- `api:GET /orders` (degree=35)
- `api:GET /positions` (degree=35)
- `api:GET /balance` (degree=33)
- `api:GET /symbol/{symbol}/tick` (degree=33)
- `table:public.open_positions` (degree=31)
- `domain:monitoring` (degree=29)
- `variable:BTC_ENGINE_API_PORT` (degree=25)
- `table:whatsapp.sessions` (degree=25)
- `table:whatsapp.messages` (degree=24)

## High-confidence entity links (sample)

- `api:POST /storage/portal/tokens` —[explicit]→ `table:public.api_tokens` (annotation=public.api_tokens)
- `api:POST /storage/portal/tokens` —[explicit]→ `table:public.portal_users` (annotation=public.portal_users)
- `api:POST /storage/portal/tokens` —[explicit]→ `table:public.contracts` (annotation=public.contracts)
- `api:GET /account` —[explicit]→ `table:clear.performance_stats` (annotation=clear.performance_stats)
- `api:GET /account` —[explicit]→ `table:btc.performance_stats` (annotation=btc.performance_stats)
- `api:GET /account` —[explicit]→ `table:clear.trades` (annotation=clear.trades)
- `api:GET /history/deals` —[explicit]→ `table:clear.trades` (annotation=clear.trades)
- `api:GET /history/deals` —[explicit]→ `table:btc.trades` (annotation=btc.trades)
- `api:GET /history/deals` —[explicit]→ `table:clear.decisions` (annotation=clear.decisions)
- `api:GET /history/deals` —[explicit]→ `table:btc.decisions` (annotation=btc.decisions)
- `api:GET /marketing/leads/stats` —[explicit]→ `table:marketing.leads` (annotation=marketing.leads)
- `api:GET /marketing/leads/stats` —[explicit]→ `table:marketing.daily_metrics` (annotation=marketing.daily_metrics)
- `api:GET /orders` —[explicit]→ `table:clear.trades` (annotation=clear.trades)
- `api:GET /orders` —[explicit]→ `table:btc.trades` (annotation=btc.trades)
- `api:GET /positions` —[explicit]→ `table:clear.trades` (annotation=clear.trades)
- `api:GET /positions` —[explicit]→ `table:btc.trades` (annotation=btc.trades)
- `api:GET /symbol/{symbol}/rates` —[explicit]→ `table:clear.candles` (annotation=clear.candles)
- `api:GET /symbol/{symbol}/rates` —[explicit]→ `table:btc.candles` (annotation=btc.candles)
- `api:GET /symbol/{symbol}/rates` —[explicit]→ `table:clear.market_states` (annotation=clear.market_states)
- `api:POST /marketing/leads` —[explicit]→ `table:marketing.leads` (annotation=marketing.leads)
- `api:POST /marketing/leads` —[explicit]→ `table:marketing.daily_metrics` (annotation=marketing.daily_metrics)
- `api:POST /marketing/leads` —[explicit]→ `table:marketing.email_log` (annotation=marketing.email_log)
- `api:POST /order` —[explicit]→ `table:clear.trades` (annotation=clear.trades)
- `api:POST /order` —[explicit]→ `table:btc.trades` (annotation=btc.trades)
- `api:GET /marketing/health` —[explicit]→ `table:marketing.leads` (annotation=marketing.leads)
- `api:GET /marketing/health` —[explicit]→ `table:marketing.daily_metrics` (annotation=marketing.daily_metrics)
- `api:GET /storage/portal/bootstrap` —[explicit]→ `table:public.contracts` (annotation=public.contracts)
- `api:GET /storage/portal/bootstrap` —[explicit]→ `table:public.portal_users` (annotation=public.portal_users)
- `api:GET /storage/portal/bootstrap` —[explicit]→ `table:public.api_tokens` (annotation=public.api_tokens)
- `api:GET /storage/portal/files` —[explicit]→ `table:public.contracts` (annotation=public.contracts)
- `api:PATCH /storage/portal/users/{user_id}` —[explicit]→ `table:public.portal_users` (annotation=public.portal_users)
- `api:PATCH /storage/portal/users/{user_id}` —[explicit]→ `table:public.contracts` (annotation=public.contracts)
- `api:POST /storage/contracts/finalize` —[explicit]→ `table:public.contracts` (annotation=public.contracts)
- `api:POST /storage/contracts/finalize` —[explicit]→ `table:public.portal_users` (annotation=public.portal_users)
- `api:POST /storage/contracts/finalize` —[explicit]→ `table:public.payments` (annotation=public.payments)
- `api:POST /storage/portal/files/upload` —[explicit]→ `table:public.payments` (annotation=public.payments)
- `api:POST /storage/portal/files/upload` —[explicit]→ `table:public.contract` (annotation=public.contract)
- `api:POST /storage/portal/payments` —[explicit]→ `table:public.payments` (annotation=public.payments)
- `api:POST /storage/portal/payments` —[explicit]→ `table:public.contracts` (annotation=public.contracts)
- `api:POST /storage/portal/payments` —[explicit]→ `table:public.portal_users` (annotation=public.portal_users)
- `api:POST /storage/portal/subusers` —[explicit]→ `table:public.portal_users` (annotation=public.portal_users)
- `api:POST /storage/portal/subusers` —[explicit]→ `table:public.contracts` (annotation=public.contracts)
- `api:POST /storage/request-access` —[explicit]→ `table:public.contracts` (annotation=public.contracts)
- `api:POST /storage/request-access` —[explicit]→ `table:public.portal_users` (annotation=public.portal_users)
- `api:GET /api/v1/models` —[explicit]→ `table:btc.llm_calls` (annotation=btc.llm_calls)
- `api:GET /api/v1/models` —[explicit]→ `table:btc.llm_log_config` (annotation=btc.llm_log_config)
- `api:GET /api/v1/models/{id}` —[explicit]→ `table:btc.llm_calls` (annotation=btc.llm_calls)
- `api:POST /api/v1/rag/index` —[explicit]→ `table:btc.training_samples` (annotation=btc.training_samples)
- `api:GET /messages` —[explicit]→ `table:public.agent_ipc` (annotation=public.agent_ipc)
- `api:GET /stats` —[explicit]→ `table:public.agent_ipc` (annotation=public.agent_ipc)
