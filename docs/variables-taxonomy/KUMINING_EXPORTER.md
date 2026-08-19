# KuMining exporter — variáveis

Variáveis do `grafana/exporters/kumining_exporter.py` (cloud mining KuCoin:
rendimentos e custos via `btc.exchange_account_ledgers`).

| Variável | Default | Propósito |
|---|---|---|
| `KUMINING_INTERVAL` | `300` | Segundos entre scrapes do exporter. Usado também no unit systemd `kumining-exporter.service` via `Environment=`. |
| `DATABASE_URL` | — | DSN do Postgres (`btc` schema). Obrigatória; o exporter sai com erro se ausente. Vem do `EnvironmentFile=/apps/crypto-trader/envfiles/trading-database.env` em produção. |

## Por que existem

O exporter coleta os bizTypes de mineração que o `kucoin_postgres_sync.py`
já grava no ledger (Earnings, CLOUD_MINING_OTHER, Hash Power Fee, Electricity
Fee). O intervalo de 5min é suficiente porque o sync roda a cada 15min —
valores menores só repetem o mesmo snapshot. Porta `9130`, publicada no
Prometheus como job `kumining-exporter`.