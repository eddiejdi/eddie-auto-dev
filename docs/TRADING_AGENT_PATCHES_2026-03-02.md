# Trading Agent — Patches & Melhorias (2026-03-02)

Registro das correções aplicadas ao BTC Trading Agent em 2 de março de 2026.

**Arquivo principal:** `/home/homelab/myClaude/btc_trading_agent/trading_agent.py`  
**Config:** `/home/homelab/myClaude/btc_trading_agent/config.json`  
**Service:** `btc-trading-agent.service` (systemd)  
**Backups:** `trading_agent.py.bak.20260302_*` (no mesmo diretório)

---

## 1. Dust Position Fix (loop de SELL infinito)

**Problema:** Posição de poeira (0.00000099 BTC = $0.068) causava loop infinito de tentativas de venda. O take-profit disparava a cada 5s, mas a KuCoin rejeitava a ordem por ser menor que o mínimo de $0.10 USDT. O agente nunca saía do loop.

**Solução:** Adicionada constante `MIN_EXCHANGE_ORDER_USDT = 0.10` (linha 63) e check de dust na função `_execute_trade` (bloco SELL, ~linha 509):

```python
MIN_EXCHANGE_ORDER_USDT = 0.10  # Minimum order value on KuCoin

# Dentro de _execute_trade, SELL block:
order_value_usdt = size * price
if order_value_usdt < MIN_EXCHANGE_ORDER_USDT:
    logger.warning(
        f"🧹 Dust position detected: {size:.8f} BTC = "
        f"USD {order_value_usdt:.4f} < min USD {MIN_EXCHANGE_ORDER_USDT}. "
        f"Clearing position (too small to sell)."
    )
    self.state.position = 0
    self.state.entry_price = 0
    return False
```

**Comportamento:** Posições menores que $0.10 são zeradas internamente sem chamar a exchange, quebrando o loop.

**Log esperado:** `🧹 Dust position detected: 0.00000099 BTC = USD 0.0682 < min USD 0.1. Clearing position`

---

## 2. Sell-at-Loss Protection (vendas com prejuízo por sinal normal)

**Problema:** O agente vendia com prejuízo sempre que um sinal SELL aparecia, sem verificar se o preço estava abaixo do preço de entrada. Nos trades de 2026-03-02 (17h-20h UTC), 3 vendas consecutivas com prejuízo:

| Trade | BUY | SELL | PnL | Intervalo |
|-------|-----|------|-----|-----------|
| 2874→2875 | $68,907 | $68,870 | -$0.025 (-0.25%) | ~5 min |
| 2872→2873 | $69,021 | $68,715 | -$0.064 (-0.64%) | ~5 min |
| 2870→2871 | $68,821 | $68,821 | -$0.020 (-0.20%) | ~5 min |

**Causa raiz:** Na função `_calculate_trade_size` (SELL), o fluxo quando `pnl <= 0` caía direto no `return self.state.position` sem nenhum check. Apenas `pnl > 0` tinha tratamento.

**Solução:** Adicionado check de `pnl <= 0` na `_calculate_trade_size` (~linha 433), antes do check de net profit:

```python
# PROTEÇÃO: Não vender com prejuízo por sinal normal
# Auto SL/TP (force=True) bypass este check via early return acima
if pnl <= 0:
    logger.info(
        f"🛡️ SELL blocked: price ${price:,.2f} below entry ${self.state.entry_price:,.2f} "
        f"(PnL: ${pnl:.4f}, net: ${net_profit:.4f}). Waiting for SL/TP auto-exit."
    )
    return 0
```

**Fluxo após patch:**
- Sinal SELL normal + `pnl <= 0` → **bloqueado** (retorna 0, posição mantida)
- Sinal SELL normal + `pnl > 0` → permitido (com check de net profit mínimo)
- Auto Stop-Loss (`force=True`, `pnl <= -2.5%`) → **permitido** (bypass via early return)
- Auto Take-Profit (`force=True`, `pnl >= +2.5%`) → **permitido** (bypass via early return)

**Log esperado:** `🛡️ SELL blocked: price $68,870.75 below entry $68,907.55 (PnL: $-0.0053, net: $-0.0253). Waiting for SL/TP auto-exit.`

---

## 3. Grafana — Panel "Disponível" (saldo USDT livre)

**Dashboard:** `btc_trading_dashboard_v3_prometheus.json` (UID: `btc-trading-monitor`)  
**Panel ID:** 73  
**Posição:** Primeira linha (x=3, y=0, w=3, h=4), entre "Preço BTC" e "PnL Total"

**Query Prometheus:**
```promql
btc_trading_equity_usdt{coin="$coin"} - btc_trading_open_position_usdt{coin="$coin"}
```

**Configuração:**
- Tipo: stat
- Unidade: `currencyUSD` (2 decimais)
- Thresholds: vermelho (<$10), laranja ($10-$50), verde (>$50)
- Filtro: variável `$coin` do dashboard (BTC-USDT, ETH-USDT, etc.)

**Layout ajustado:** Primeira linha reorganizada — todos os 8 panels com w=3 para totalizar 24 colunas.

---

## 4. Grafana — Panels de Log Rolante

Adicionados 3 panels na seção inferior do dashboard:

| ID | Tipo | Título | Datasource | Posição |
|----|------|--------|------------|---------|
| 70 | row | 📋 Agent Log (Rolling) | — | y=49 |
| 71 | table | 📋 Decisões Recentes (Log Rolante) | BTC Trading PostgreSQL | x=0, y=50, w=16, h=10 |
| 72 | table | 📊 Trades Recentes | BTC Trading PostgreSQL | x=16, y=50, w=8, h=10 |

**Panel 71 — Decisões:** Query SQL na tabela `btc.decisions`, últimas 200 decisões, com cores por ação (BUY=verde, SELL=vermelho, HOLD=azul), gauge de confiança.

**Panel 72 — Trades:** Query SQL na tabela `btc.trades`, últimos trades LIVE, com cores de PnL (positivo=verde, negativo=vermelho).

---

## Configuração Atual do Agente

```json
{
    "dry_run": false,
    "symbol": "BTC-USDT",
    "poll_interval": 5,
    "min_trade_interval": 300,
    "min_confidence": 0.55,
    "min_trade_amount": 10,
    "max_position_pct": 0.2,
    "stop_loss_pct": 0.025,
    "take_profit_pct": 0.035,
    "auto_stop_loss": { "enabled": true, "pct": 0.025 },
    "auto_take_profit": { "enabled": true, "pct": 0.025 },
    "min_net_profit": { "usd": 0.5, "pct": 0.015 },
    "trailing_stop": { "enabled": true, "activation_pct": 0.015, "trail_pct": 0.008 },
    "strategy.mode": "scalping"
}
```

## Estatísticas (até 2026-03-02 20:28 UTC)

| Métrica | Valor |
|---------|-------|
| Total trades (LIVE sells) | 44 |
| Wins / Losses | 22 / 22 (50%) |
| PnL total | -$0.3251 |
| USDT disponível | ~$54.57 |
| Posição atual | Nenhuma (last trade foi SELL) |

---

## Rollback

Cada patch tem backup datado no homelab:
```bash
ls /home/homelab/myClaude/btc_trading_agent/trading_agent.py.bak.*
```

Para reverter, restaurar o backup mais recente antes do patch desejado:
```bash
ssh homelab "cp /home/homelab/myClaude/btc_trading_agent/trading_agent.py.bak.20260302_HHMMSS \
    /home/homelab/myClaude/btc_trading_agent/trading_agent.py && \
    sudo systemctl restart btc-trading-agent"
```

## Recovery (Postgres-safe)

Um helper Postgres-safe foi adicionado ao repositório: `btc_trading_agent_recovery_postgres.sh`.
Use este script quando o agente estiver conectado a PostgreSQL (recomendado) — ele fará um `pg_dump` de backup,
marcará trades `open` antigos como `force_closed` e fornecerá (opcional) um comando seguro para reiniciar o serviço.

Exemplo (somente backup + DB fix):
```bash
./btc_trading_agent_recovery_postgres.sh --database-url "postgresql://postgres:pass@172.17.0.2:5432/btc_trading"
```

Para executar e reiniciar automaticamente (use com cautela):
```bash
./btc_trading_agent_recovery_postgres.sh --database-url "postgresql://..." --force-restart
```

NOTA: O antigo `btc_trading_agent_recovery.sh` usava SQLite e é considerado obsoleto para ambientes
que já usam PostgreSQL; prefira o script Postgres-safe acima.

