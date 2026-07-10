# Instalação DOGE-USDT — Trading Agent

**Data:** 2026-07-10  
**Ambiente:** Homelab (`192.168.15.2`)  
**Status:** Live (shadow + conservative + aggressive)  
**Banco:** PostgreSQL `btc_trading` porta `5433` — SQLite proibido

---

## Visão geral

DOGE-USDT segue o **mesmo padrão triplo de perfis** introduzido com SOL-USDT: três instâncias systemd independentes na conta master TRADE da KuCoin (`kucoin/homelab`). BTC e ETH continuam em subcontas dedicadas; SOL e DOGE compartilham a TRADE master.

| Perfil | Config | Métricas | API | Job Prometheus |
|--------|--------|:--------:|:---:|----------------|
| **shadow** | `config_DOGE_USDT_shadow.json` | 9112 | 8522 | `crypto-exporter-doge_usdt_shadow` |
| **conservative** | `config_DOGE_USDT_conservative.json` | 9113 | 8523 | `crypto-exporter-doge_usdt_conservative` |
| **aggressive** | `config_DOGE_USDT_aggressive.json` | 9114 | 8524 | `crypto-exporter-doge_usdt_aggressive` |

**Capital alvo:** ~US$ 50 por perfil (recomendado ~US$ 150 USDT alocados ao DOGE na TRADE master).

**Pool compartilhado TRADE master:** SOL e DOGE operam na mesma conta. Com ambos em live, planeje **~US$ 300 USDT** de margem operacional (US$ 150 × 2 moedas), além de saldo livre para fees e slippage.

**Política de saída:** `guardrails_positive_only_sells: true` — o agente não vende no prejuízo.

---

## Histórico de inclusão (2026-07-10)

| Etapa | Ação |
|-------|------|
| 1. Análise | Mapeado fluxo de inclusão da SOL (configs, envfiles, prometheus, deploy, CI) |
| 2. Scaffold | Clonados `config_SOL_USDT_*.json` → `config_DOGE_USDT_*.json` com `symbol: DOGE-USDT` |
| 3. Dry run | Primeira ativação com `dry_run: true`, `live_mode: false` |
| 4. Infra | Portas 9112–9114 alocadas; jobs Prometheus; serviços em `deploy_btc_trading_profiles.sh` |
| 5. Integrações | Relatório diário, Trading Analyst (conversa), workflow CI/CD |
| 6. Homelab | `activate_doge_trading_profiles.sh` executado em `192.168.15.2` |
| 7. Live | Usuário autorizou live; configs atualizados e serviços reiniciados |

Commits na branch `feat/trading-agent-telegram-conversation`:

- `feat(trading): add DOGE-USDT profiles (dry_run) on master TRADE account`
- `feat(trading): enable DOGE-USDT live trading on master TRADE account`

---

## Arquivos no repositório

```
btc_trading_agent/
  config_DOGE_USDT_shadow.json
  config_DOGE_USDT_conservative.json
  config_DOGE_USDT_aggressive.json
  DOGE_USDT_shadow.env.example
  DOGE_USDT_conservative.env.example
  DOGE_USDT_aggressive.env.example
  trading_conversation.py          # SYMBOLS inclui DOGE-USDT

scripts/
  activate_doge_trading_profiles.sh  # ativação rápida no homelab
  deploy_btc_trading_profiles.sh     # deploy completo (BTC+ETH+SOL+DOGE)
  trading_daily_report.py            # SYMBOLS inclui DOGE-USDT

monitoring/prometheus.yml            # jobs DOGE (portas 9112/9113/9114)

.github/workflows/
  deploy-btc-trading-profiles.yml    # CI: paths + verificação de serviços DOGE

systemd/crypto-agent@.service        # template das instâncias (%I → config_%I.json)
```

---

## Diferenças em relação a BTC/ETH/SOL

| Aspecto | BTC / ETH | SOL | DOGE |
|---------|-----------|-----|------|
| Conta KuCoin | Subcontas (`KUCOIN_SECRET_NAMES`) | TRADE master | TRADE master (igual SOL) |
| Base de parâmetros | Otimizador / ETH clone | ETH clone | **SOL clone** |
| Portas métricas | 9096–9108 (ETH/SOL) | 9104/9106/9108 | **9112/9113/9114** |
| Relatório diário | Sim | Sim | Sim (desde 2026-07-10) |
| Trading Analyst | Sim | Sim | Sim (desde 2026-07-10) |
| Candles | Sim | Sim | Já na frota de 6 moedas |

DOGE **não** usa `KUCOIN_SECRET_NAMES` no envfile — o default `kucoin/homelab` do `secrets_helper` é suficiente.

---

## Pré-requisitos

1. **Homelab** com runtime em `/apps/crypto-trader/trading/`
2. **Usuário de serviço** `btc-trading` e envfiles em `/apps/crypto-trader/envfiles/`
3. **Secrets** KuCoin via `secrets_agent` (default `kucoin/homelab`)
4. **Saldo USDT** na TRADE master (~US$ 150 para DOGE; ~US$ 300 se SOL+DOGE live)
5. **Candles** — `candle-collector.service` já inclui `DOGE-USDT` em `SYMBOLS`
6. **PostgreSQL** acessível em `127.0.0.1:5433` (schema `btc`)
7. **SOL ativo** (opcional) — mesma conta; monitorar exposição agregada

---

## Instalação automática (CI/CD)

O workflow `.github/workflows/deploy-btc-trading-profiles.yml` dispara quando arquivos DOGE mudam:

```yaml
paths:
  - 'btc_trading_agent/config_DOGE_USDT_*.json'
  - 'scripts/activate_doge_trading_profiles.sh'
```

No merge em `main`, o runner self-hosted no homelab:

1. Sincroniza código e configs para `/apps/crypto-trader/trading/`
2. Reinicia `crypto-agent@DOGE_USDT_{shadow,conservative,aggressive}`
3. Reinicia `crypto-exporter@DOGE_USDT_{shadow,conservative,aggressive}`
4. Chama `ensure_doge_trading_profiles()` no deploy script
5. Verifica serviços ativos e scrape targets Prometheus (`crypto-exporter-doge_usdt_*`)

---

## Instalação manual no homelab

### Opção A — script dedicado DOGE

Após sync dos arquivos do repositório:

```bash
sudo bash scripts/activate_doge_trading_profiles.sh
```

O script:

- Cria envfiles em `/apps/crypto-trader/envfiles/DOGE_USDT_*.env`
- Copia os 3 configs para `/apps/crypto-trader/trading/btc_trading_agent/`
- Atualiza `/home/homelab/monitoring/prometheus.yml` (se jobs DOGE existirem no repo)
- Habilita e reinicia agent + exporter de cada perfil

### Opção B — deploy completo de perfis

```bash
sudo bash scripts/deploy_btc_trading_profiles.sh
```

Inclui BTC, ETH, SOL e DOGE; use quando houver mudanças no runtime compartilhado (`trading_agent.py`, mixins, `llm.py`, etc.).

### Envfiles gerados

Exemplo `DOGE_USDT_conservative.env`:

```bash
TRADING_TELEGRAM_CHAT_ID=-1004434951297
METRICS_PORT=9113
BTC_ENGINE_API_PORT=8523
```

Templates: `btc_trading_agent/DOGE_USDT_*.env.example`

---

## Ativação live (pós dry run)

Para sair de simulação e operar com ordens reais, em cada `config_DOGE_USDT_*.json`:

```json
"dry_run": false,
"live_mode": true
```

Depois, no homelab:

```bash
sudo systemctl restart \
  crypto-agent@DOGE_USDT_shadow \
  crypto-agent@DOGE_USDT_conservative \
  crypto-agent@DOGE_USDT_aggressive \
  crypto-exporter@DOGE_USDT_shadow \
  crypto-exporter@DOGE_USDT_conservative \
  crypto-exporter@DOGE_USDT_aggressive
```

Confirme nos logs:

```bash
journalctl -u crypto-agent@DOGE_USDT_conservative.service -n 20 --no-pager | grep -E "LIVE|dry_run"
```

Saída esperada: `Mode: 🔴 LIVE TRADING`.

---

## Verificação pós-instalação

### Serviços systemd

```bash
for p in shadow conservative aggressive; do
  systemctl is-active "crypto-agent@DOGE_USDT_${p}.service"
  systemctl is-active "crypto-exporter@DOGE_USDT_${p}.service"
done
```

### Métricas Prometheus (host)

```bash
curl -s http://127.0.0.1:9113/metrics | grep -E 'btc_price|btc_trading_open_position' | head -5
curl -s http://127.0.0.1:9114/metrics | grep btc_price | head -3
```

### Scrape targets (Prometheus em Docker)

O container `prometheus` monta `/home/homelab/monitoring/prometheus.yml`. Após alteração do arquivo, pode ser necessário:

```bash
sudo docker restart prometheus
# aguardar ~60s (TSDB grande no boot)
sudo docker exec prometheus wget -qO- http://127.0.0.1:9090/api/v1/targets | \
  python3 -c "import json,sys; d=json.load(sys.stdin); \
  jobs=['crypto-exporter-doge_usdt_shadow','crypto-exporter-doge_usdt_conservative','crypto-exporter-doge_usdt_aggressive']; \
  by={t['labels'].get('job'):t.get('health') for t in d['data']['activeTargets']}; \
  [print(f'{j}:{by.get(j)}') for j in jobs]"
```

### Posição aberta (PostgreSQL)

```bash
PGPASSWORD=eddie_memory_2026 psql -h 127.0.0.1 -U postgres -p 5433 -d btc_trading -c \
  "SELECT profile, symbol, side, quantity, price, executed_at
   FROM btc.trades
   WHERE symbol = 'DOGE-USDT' AND side = 'buy'
   ORDER BY executed_at DESC LIMIT 10;"
```

### Grafana

- Dashboard: **Trading Agent Monitor** (`btc-trading-monitor`)
- Variável `coin`: `DOGE-USDT` já está no dropdown da frota de 6 moedas
- URL externa: https://grafana.rpa4all.com

### Relatório diário e Trading Analyst

- `scripts/trading_daily_report.py` — seção DOGE-USDT (ícone `Ð`)
- `btc_trading_agent/trading_conversation.py` — `TRADING_CONVERSATION_SYMBOLS` default inclui `DOGE-USDT`

### Logs do agente

```bash
journalctl -u 'crypto-agent@DOGE_USDT_conservative.service' -f --no-pager -n 50
```

---

## Parâmetros principais (conservative)

Clonados de `config_SOL_USDT_conservative.json`; metadados em `_doge_live_notes`.

| Parâmetro | Valor | Notas |
|-----------|-------|-------|
| `dry_run` | `false` | Live desde 2026-07-10 |
| `live_mode` | `true` | Ordens reais na KuCoin |
| `take_profit_pct` | 2% | Igual SOL conservative |
| `trailing_stop` | +1% ativação | Venda dinâmica acima do TP mínimo |
| `guardrails_positive_only_sells` | `true` | Bloqueia venda no prejuízo |
| `max_position_pct` | 0.6 | Até 60% do saldo alocado ao perfil |
| `min_trade_amount` | US$ 10 | Tamanho mínimo por ordem |

Perfil **aggressive**: `min_confidence` 0.55, `take_profit_pct` 1.5%, `max_position_pct` 1.0 (igual SOL aggressive).

Perfil **shadow**: notificações desabilitadas; usado para observação/simulação de estratégia sem alertas.

---

## Mapa de portas (frota TRADE master)

Evitar conflito ao adicionar novas moedas na mesma conta:

| Moeda | shadow | conservative | aggressive |
|-------|:------:|:------------:|:----------:|
| SOL | 9108 / 8518 | 9104 / 8516 | 9106 / 8517 |
| **DOGE** | **9112 / 8522** | **9113 / 8523** | **9114 / 8524** |
| Próxima moeda sugerida | 9115 / 8525 | 9116 / 8526 | 9117 / 8527 |

---

## Troubleshooting

| Sintoma | Causa provável | Ação |
|---------|----------------|------|
| Serviço `inactive` | Config ausente ou envfile errado | Rodar `activate_doge_trading_profiles.sh` |
| Grafana sem dados DOGE | Prometheus sem scrape | Conferir jobs `crypto-exporter-doge_usdt_*`; `docker restart prometheus` |
| Log ainda mostra `dry_run=True` | Config não sincronizado | Copiar JSONs para `/apps/crypto-trader/trading/btc_trading_agent/` e reiniciar |
| Venda não executa | Guardrail positive-only | Preço abaixo da entrada; aguardar TP/trailing |
| Saldo insuficiente | Pool TRADE compartilhado SOL+DOGE | Aumentar USDT na TRADE master ou reduzir `max_position_pct` |
| Prometheus API 503 após restart | TSDB grande no boot | Aguardar 1–2 min; verificar `docker logs prometheus` |

---

## Checklist para incluir nova moeda (replicar fluxo DOGE)

1. Clonar configs de referência (ex.: SOL) → `config_{COIN}_USDT_{profile}.json`
2. Definir `symbol`, conta (subconta vs TRADE master), `dry_run`/`live_mode`
3. Alocar 3 pares de portas (métricas + API) sem conflito
4. Criar `activate_{coin}_trading_profiles.sh` + `*.env.example`
5. Adicionar jobs em `monitoring/prometheus.yml`
6. Registrar em `AGENT_SERVICES` / `EXPORTER_SERVICES` + `ensure_*()` no deploy
7. Atualizar workflow CI (paths + verificação)
8. Atualizar `trading_daily_report.py` e `trading_conversation.py` se reportável
9. Adicionar testes em `tests/test_deploy_btc_trading_profiles_script.py`
10. Documentar em `docs/{COIN}_USDT_INSTALLATION.md`

---

## Referências

- [SOL_USDT_INSTALLATION.md](SOL_USDT_INSTALLATION.md) — modelo de referência (mesma conta TRADE)
- [MULTI_COIN_TRADING_INFRASTRUCTURE.md](MULTI_COIN_TRADING_INFRASTRUCTURE.md) — arquitetura geral multi-moeda
- `scripts/activate_doge_trading_profiles.sh` — ativação one-shot
- `scripts/deploy_btc_trading_profiles.sh` — deploy unificado
- `monitoring/prometheus.yml` — scrape targets DOGE