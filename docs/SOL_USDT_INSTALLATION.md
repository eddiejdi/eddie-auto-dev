# Instalação SOL-USDT — Trading Agent

**Data:** 2026-07-09  
**Ambiente:** Homelab (`192.168.15.2`)  
**Status:** Live (conservative + aggressive)  
**Banco:** PostgreSQL `btc_trading` porta `5433` — SQLite proibido

---

## Visão geral

SOL-USDT opera com **três perfis** independentes na conta master TRADE da KuCoin (`kucoin/homelab`). KuCoin não permite novas subcontas; todos os perfis compartilham a mesma conta, com configs e portas separadas.

| Perfil | Config | Métricas | API | Job Prometheus |
|--------|--------|:--------:|:---:|----------------|
| **shadow** | `config_SOL_USDT_shadow.json` | 9108 | 8518 | `crypto-exporter-sol_usdt_shadow` |
| **conservative** | `config_SOL_USDT_conservative.json` | 9104 | 8516 | `crypto-exporter-sol_usdt_conservative` |
| **aggressive** | `config_SOL_USDT_aggressive.json` | 9106 | 8517 | `crypto-exporter-sol_usdt_aggressive` |

**Capital alvo:** ~US$ 50 por perfil live (recomendado ~US$ 150 USDT total na TRADE master).

**Política de saída:** `guardrails_positive_only_sells: true` — o agente não vende no prejuízo.

---

## Arquivos no repositório

```
btc_trading_agent/
  config_SOL_USDT_shadow.json
  config_SOL_USDT_conservative.json
  config_SOL_USDT_aggressive.json
  SOL_USDT_shadow.env.example
  SOL_USDT_conservative.env.example
  SOL_USDT_aggressive.env.example

scripts/
  activate_sol_trading_profiles.sh   # ativação rápida no homelab
  deploy_btc_trading_profiles.sh       # deploy completo (BTC+ETH+SOL)

monitoring/prometheus.yml            # jobs SOL (portas 9104/9106/9108)

systemd/crypto-agent@.service        # template das instâncias
```

---

## Pré-requisitos

1. **Homelab** com runtime em `/apps/crypto-trader/trading/`
2. **Usuário de serviço** `btc-trading` e envfiles em `/apps/crypto-trader/envfiles/`
3. **Secrets** KuCoin via `secrets_agent` (default `kucoin/homelab`)
4. **Saldo USDT** na TRADE master (~US$ 150 para os 3 perfis)
5. **Candles** — `candle-collector.service` já inclui `SOL-USDT` na lista de símbolos
6. **PostgreSQL** acessível em `127.0.0.1:5433` (schema `btc`)

---

## Instalação automática (CI/CD)

O workflow `.github/workflows/deploy-btc-trading-profiles.yml` dispara quando arquivos SOL mudam:

```yaml
paths:
  - 'btc_trading_agent/config_SOL_USDT_*.json'
```

No merge em `main`, o deploy:

1. Sincroniza código e configs para `/apps/crypto-trader/trading/`
2. Reinicia `crypto-agent@SOL_USDT_{shadow,conservative,aggressive}`
3. Reinicia `crypto-exporter@SOL_USDT_{shadow,conservative,aggressive}`
4. Atualiza `prometheus.yml` e recarrega Prometheus

---

## Instalação manual no homelab

### Opção A — script dedicado SOL

No homelab, após `git pull`:

```bash
cd /home/homelab/eddie-auto-dev   # ou caminho do clone
sudo bash scripts/activate_sol_trading_profiles.sh
```

O script:

- Cria envfiles em `/apps/crypto-trader/envfiles/SOL_USDT_*.env`
- Copia os 3 configs para `/apps/crypto-trader/trading/btc_trading_agent/`
- Atualiza `/home/homelab/monitoring/prometheus.yml` (se jobs SOL existirem no repo)
- Habilita e reinicia agent + exporter de cada perfil

### Opção B — deploy completo de perfis

```bash
sudo bash scripts/deploy_btc_trading_profiles.sh
```

Inclui BTC, ETH e SOL; use quando houver mudanças no runtime compartilhado (`trading_agent.py`, mixins, etc.).

### Envfiles gerados

Exemplo `SOL_USDT_conservative.env`:

```bash
TRADING_TELEGRAM_CHAT_ID=-1004434951297
METRICS_PORT=9104
BTC_ENGINE_API_PORT=8516
```

Templates: `btc_trading_agent/SOL_USDT_*.env.example`

---

## Verificação pós-instalação

### Serviços systemd

```bash
for p in shadow conservative aggressive; do
  systemctl is-active "crypto-agent@SOL_USDT_${p}.service"
  systemctl is-active "crypto-exporter@SOL_USDT_${p}.service"
done
```

### Métricas Prometheus

```bash
curl -s http://127.0.0.1:9104/metrics | grep -E 'btc_trading_open_position|btc_price' | head -5
curl -s http://127.0.0.1:9106/metrics | grep btc_trading_open_position | head -3
```

### Posição aberta (PostgreSQL)

```bash
PGPASSWORD=eddie_memory_2026 psql -h 127.0.0.1 -U postgres -p 5433 -d btc_trading -c \
  "SELECT profile, symbol, side, quantity, price, executed_at
   FROM btc.trades
   WHERE symbol = 'SOL-USDT' AND side = 'buy'
   ORDER BY executed_at DESC LIMIT 10;"
```

### Grafana

- Dashboard: **Trading Agent Monitor** (`btc-trading-monitor`)
- Variável `coin` / `profile`: selecionar `SOL-USDT` + `conservative` ou `aggressive`
- URL externa: https://grafana.rpa4all.com

### Logs do agente

```bash
journalctl -u 'crypto-agent@SOL_USDT_conservative.service' -f --no-pager -n 50
```

---

## Parâmetros principais (conservative)

| Parâmetro | Valor | Notas |
|-----------|-------|-------|
| `dry_run` | `false` | Live desde 2026-07-08 |
| `take_profit_pct` | 2% | TP ~US$ 78,90 a partir de entrada ~US$ 77,66 |
| `trailing_stop` | +1% ativação | Venda dinâmica acima do TP mínimo |
| `guardrails_positive_only_sells` | `true` | Bloqueia venda no prejuízo |
| `max_position_pct` | 0.6 | Até 60% do saldo alocado |
| `min_trade_amount` | US$ 10 | Tamanho mínimo por ordem |

Detalhes em `_sol_live_notes` dentro de cada `config_SOL_USDT_*.json`.

---

## Troubleshooting

| Sintoma | Causa provável | Ação |
|---------|----------------|------|
| Serviço `inactive` | Config ausente ou envfile errado | Rodar `activate_sol_trading_profiles.sh` |
| Grafana sem dados SOL | Prometheus sem scrape | Conferir jobs `crypto-exporter-sol_usdt_*` em `prometheus.yml` |
| Plano IA sem posição | State em memória defasado | Corrigido em PR #214 — `_resolve_db_open_position()` usa PostgreSQL |
| Venda não executa | Guardrail positive-only | Preço abaixo da entrada; aguardar TP/trailing |
| `ENOSPC` / disco cheio | Logs ou staging | Ver `journalctl` e `df -h /` no homelab |

---

## Referências

- [MULTI_COIN_TRADING_INFRASTRUCTURE.md](MULTI_COIN_TRADING_INFRASTRUCTURE.md) — arquitetura geral multi-moeda
- `scripts/activate_sol_trading_profiles.sh` — ativação one-shot
- `scripts/deploy_btc_trading_profiles.sh` — deploy unificado
- `monitoring/prometheus.yml` — scrape targets SOL