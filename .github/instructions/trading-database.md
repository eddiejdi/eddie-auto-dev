---
applyTo: "**/*trading*,**/*btc*,**/*exporter*,**/*coin*,**/btc_query*,**/config.json"
---

# Regras de Trading & Banco de Dados — Shared Auto-Dev

## ⛔ BANCO DE DADOS — REGRA CRÍTICA (NÃO NEGOCIÁVEL)
- **SOMENTE PostgreSQL** (`psycopg2`) — porta `5433`, database `btc_trading`, schema `btc`
- **NUNCA SQLite** — `data/trading_agent.db` está OBSOLETO
- DSN: `postgresql://postgres:shared_memory_2026@localhost:5433/btc_trading`
- `conn.autocommit = True` (OBRIGATÓRIO — evita `InFailedSqlTransaction`)
- `cursor.execute("SET search_path TO btc, public")` após conectar
- Placeholders: `%s` (nunca `?`)
- **TODAS** as queries filtram por `AND symbol=%s` — sem exceção
- `dry_run` é `bool` (True/False), nunca int (1/0)
- Referência funcional: `btc_query.py`

## Multi-Posição (desde 2026-03-03)
- Acumula até `max_positions` (default 3) entradas BUY antes de vender
- Preço médio ponderado: `new_avg = (old*old_entry + new*new_price) / total`
- SELL liquida toda posição contra preço médio
- Config: `max_positions`, `max_position_pct`, `min_confidence`, `min_trade_interval`, `max_daily_trades`, `max_daily_loss`
- Métricas Prometheus: `btc_trading_open_position_count`, `btc_trading_avg_entry_price`

## Multi-Coin (6 moedas)
Portas: BTC(:9092/:8511), ETH(:9098/:8512), XRP(:9094/:8513), SOL(:9095/:8514), DOGE(:9096/:8515), ADA(:9097/:8516).

## Regras Exporter
- `/set-live` é **GET** (não POST)
- Cada exporter usa seu `CONFIG_PATH` via env `COIN_CONFIG_FILE`

## Regras Grafana
1. **UM arquivo JSON por dashboard** — títulos duplicados bloqueiam silenciosamente
2. Expressões Prometheus: `{job="$coin_job"}` — nunca hardcoded
3. Editar APENAS o JSON no disco (UI sobrescrita a cada 30s)
4. Verificar: `sudo docker logs grafana --since 60s 2>&1 | grep "not unique\|no database write"`
5. Dashboard ativo: `btc_trading_dashboard_v3_prometheus.json`
