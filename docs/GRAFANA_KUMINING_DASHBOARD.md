# Grafana KuMining Dashboard — Mineração

**Data:** 2026-08-08  
**Dashboard:** [btc-trading-monitor](https://grafana.rpa4all.com/d/btc-trading-monitor/btc-trading-monitor)  
**UID:** `btc-trading-monitor`  
**Folder:** Eddie Auto-Dev (uid: `fffxoniykngn4e`)

## Visão Geral

Seção de mineração KuMining adicionada ao dashboard principal de trading. Monitora saldos BTC em sub-contas de trading, ganhos de mineração e USDT disponível para transferência.

## Painéis Adicionados (IDs 300-308)

| ID | Tipo | Título | Descrição |
|----|------|--------|-----------|
| 300 | row | ⛏️ Mineração KuMining | Seção colapsável |
| 301 | stat | ₿ Saldo BTC (Main) | Saldo BTC total nas sub-contas de trading |
| 302 | stat | 📈 Ganhos BTC no Período | Delta de BTC no período selecionado |
| 303 | stat | 💰 Ganhos em USDT | Valor dos ganhos convertido em USDT |
| 304 | text | 📋 Contrato Ativo | Detalhes do contrato (10 TH, 7 dias) |
| 305 | timeseries | 📈 Saldo BTC ao Longo do Tempo | Evolução do saldo BTC |
| 306 | timeseries | ⛏️ Ganhos de Mineração por Snapshot | Ganhos diários por snapshot |
| 307 | stat | 💵 USDT Disponível (Main) | USDT disponível na conta main |
| 308 | text | 🚀 Ações Rápidas | Botões de transferência KuCoin |

## Fonte de Dados

- **PostgreSQL:** `btc-trading-pg` (uid)
- **Tabela:** `btc.exchange_balance_snapshots`
- **Colunas relevantes:**
  - `synced_at` — timestamp do snapshot
  - `account_type` — tipo da conta (`main`, `trade`, `sub:BTCAgressive`, `sub:BTCConservative`)
  - `currency` — moeda (`BTC`, `USDT`, etc.)
  - `balance` — saldo total
  - `available` — saldo disponível
  - `holds` — saldo em hold
  - `price_usdt` — preço em USDT

## Contas de Trading

| account_type | Uso |
|--------------|-----|
| `main` | Conta principal (USDT, BRL) |
| `trade` | Conta de trading |
| `sub:BTCAgressive` | Sub-conta BTC agressiva |
| `sub:BTCConservative` | Sub-conta BTC conservadora |
| `sub:ETHAgressive` | Sub-conta ETH agressiva |
| `sub:ETHConservative` | Sub-conta ETH conservadora |

**Importante:** O BTC está em `sub:BTCAgressive` e `sub:BTCConservative`, **não** em `main`.

## Queries dos Painéis

### Painel 301: Saldo BTC
```sql
WITH latest AS (
  SELECT account_type, balance
  FROM btc.exchange_balance_snapshots
  WHERE currency = 'BTC'
    AND account_type IN ('sub:BTCAgressive', 'sub:BTCConservative')
  ORDER BY synced_at DESC
  LIMIT 2
)
SELECT now() AS "time", SUM(balance) AS "Saldo BTC"
FROM latest
```

### Painel 302: Ganhos BTC no Período
```sql
WITH btc_snapshots AS (
  SELECT synced_at, SUM(balance) AS total_balance
  FROM btc.exchange_balance_snapshots
  WHERE currency = 'BTC'
    AND account_type IN ('sub:BTCAgressive', 'sub:BTCConservative')
  GROUP BY synced_at
),
period_ends AS (
  SELECT
    (ARRAY_AGG(total_balance ORDER BY synced_at DESC))[1] AS end_bal,
    (ARRAY_AGG(total_balance ORDER BY synced_at ASC))[1] AS start_bal
  FROM btc_snapshots
  WHERE synced_at BETWEEN $__timeFrom() AND $__timeTo()
)
SELECT now() AS "time", COALESCE(end_bal - start_bal, 0) AS "Ganhos BTC"
FROM period_ends
```

### Painel 303: Ganhos em USDT
```sql
WITH btc_snapshots AS (
  SELECT synced_at, SUM(balance) AS total_balance
  FROM btc.exchange_balance_snapshots
  WHERE currency = 'BTC'
    AND account_type IN ('sub:BTCAgressive', 'sub:BTCConservative')
  GROUP BY synced_at
),
btc_delta AS (
  SELECT
    (ARRAY_AGG(total_balance ORDER BY synced_at DESC))[1]
    - (ARRAY_AGG(total_balance ORDER BY synced_at ASC))[1] AS btc_earned
  FROM btc_snapshots
  WHERE synced_at BETWEEN $__timeFrom() AND $__timeTo()
),
btc_price AS (
  SELECT price_usdt
  FROM btc.exchange_balance_snapshots
  WHERE currency = 'BTC'
    AND account_type IN ('sub:BTCAgressive', 'sub:BTCConservative')
    AND price_usdt IS NOT NULL
  ORDER BY synced_at DESC
  LIMIT 1
)
SELECT now() AS "time", COALESCE(btc_earned * btc_price.price_usdt, 0) AS "Ganhos USDT"
FROM btc_delta, btc_price
```

### Painel 305: Saldo BTC ao Longo do Tempo
```sql
SELECT
  synced_at AS "time",
  SUM(balance) AS "Saldo BTC"
FROM btc.exchange_balance_snapshots
WHERE currency = 'BTC'
  AND account_type IN ('sub:BTCAgressive', 'sub:BTCConservative')
  AND synced_at BETWEEN $__timeFrom() AND $__timeTo()
GROUP BY synced_at
ORDER BY synced_at
```

### Painel 306: Ganhos de Mineração por Snapshot
```sql
WITH ordered AS (
  SELECT
    synced_at,
    SUM(balance) AS total_balance,
    LAG(SUM(balance)) OVER (ORDER BY synced_at) AS prev_balance
  FROM btc.exchange_balance_snapshots
  WHERE currency = 'BTC'
    AND account_type IN ('sub:BTCAgressive', 'sub:BTCConservative')
  GROUP BY synced_at
)
SELECT
  synced_at AS "time",
  COALESCE(total_balance - prev_balance, 0) AS "Ganhos BTC"
FROM ordered
WHERE synced_at BETWEEN $__timeFrom() AND $__timeTo()
  AND total_balance - COALESCE(prev_balance, total_balance) > 0
ORDER BY synced_at
```

### Painel 307: USDT Disponível
```sql
WITH latest AS (
  SELECT DISTINCT ON (account_type)
    account_type, available
  FROM btc.exchange_balance_snapshots
  WHERE currency = 'USDT'
    AND account_type = 'main'
  ORDER BY account_type, synced_at DESC
)
SELECT now() AS "time", available AS "USDT Disponível"
FROM latest
```

## Painel 103: Valor KuMining no Saldo Exchange R$

O painel **103 "💰 Saldo Exchange em R$ (total bruto)"** agora soma também o valor investido
em contratos KuMining (hashrate + energia) convertido para R$.

Fonte: `btc.exchange_account_ledgers`, saídas USDT com
`biz_type IN ('Cloud Mining Hash Power Fee', 'Cloud Mining Electricity Fee')`.

Taxa de conversão: mesma `brl_rate` usada no resto do painel (snapshot BRL → fallback trades USDT-BRL).

### Query KuMining (adicionada ao painel 103)
```sql
, kumining_cost AS (
  SELECT COALESCE(SUM(ABS(amount)), 0) AS usdt_cost
  FROM btc.exchange_account_ledgers
  WHERE currency = 'USDT'
    AND direction = 'out'
    AND biz_type IN ('Cloud Mining Hash Power Fee', 'Cloud Mining Electricity Fee')
)
```

O `usdt_cost` é somado ao total em R$ via `usdt_cost / brl_price_usdt`.

> **Nota:** o texto estático do painel 304 (~2.62 USDT) está **desatualizado** — o ledger mostra
> 2 compras de hash power (1.764 em 08/08 + 18.144 em 08/15 = 19.91 USDT) além das taxas de energia.

## Botões de Transferência (Painel 308)

O painel 308 é um painel de texto HTML com botões que abrem a KuCoin:

1. **Transferir para Conta de Trading** — USDT da conta main para trading
2. **Transferir BTC Mining → Trading** — BTC de mineração para trading

URLs de transferência:
- `https://www.kucoin.com/transfer/main/trade`
- `https://www.kucoin.com/transfer/main/trade?coin=BTC`

## Índices

A tabela `btc.exchange_balance_snapshots` possui índice:
```sql
CREATE INDEX idx_exchange_balance_snapshots_lookup 
ON btc.exchange_balance_snapshots 
USING btree (account_type, currency, synced_at DESC)
```

## Problemas Conhecidos e Correções

### 1. "No Data" nos painéis
**Causa:** Queries usando `account_type = 'main' AND currency = 'BTC'` — não existe BTC na conta main.

**Correção:** Alterar para `account_type IN ('sub:BTCAgressive', 'sub:BTCConservative')`.

### 2. "No Data" em painéis stat
**Causa:** Stat panels precisam de `format: time_series` com `now()` como coluna de tempo.

**Correção:** Alterar `format` de `table` para `time_series` e usar `SELECT now() AS "time", ...`.

### 3. Dashboard não atualiza no Grafana
**Causa:** Provisioning com `allowUiUpdates: false` e `updateIntervalSeconds: 30`.

**Correção:** Copiar arquivo para `/home/homelab/monitoring/grafana/provisioning/dashboards/` e reiniciar container.

## Deploy

```bash
# Copiar dashboard atualizado
cat grafana/dashboards/btc-trading-monitor.json | \
  ssh homelab@192.168.15.2 "sudo tee /home/homelab/monitoring/grafana/provisioning/dashboards/btc-trading-monitor.json > /dev/null"

# Reiniciar Grafana
ssh homelab@192.168.15.2 "docker restart grafana"

# Verificar
curl -s -u admin:Rpa_four_all! http://192.168.15.2:3002/api/dashboards/uid/btc-trading-monitor | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'panels={len(d[\"dashboard\"][\"panels\"])}')"
```

## Referências

- Dashboard JSON: `grafana/dashboards/btc-trading-monitor.json`
- Provisioning: `monitoring/grafana/provisioning/dashboards/`
- Export script: `monitoring/grafana/export_dashboard_to_provisioning.sh`
- Trading exporter: `btc_trading_agent/prometheus_exporter.py`
