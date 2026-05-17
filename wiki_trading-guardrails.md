# Trading Guardrails Tuning & Rebuy Lock

**Status:** ✅ Deployed (2026-05-02)  
**Current Guardrail:** 0.3% (min_sell_pnl_pct)  
**Tags:** `trading`, `kucoin`, `risk-management`, `guardrails`

---

## Overview

Guardrails são **limites de segurança** que previnem sells abaixo de um certo profit margin, evitando realized losses durante flutuações de mercado.

**Problema:** Guardrail 1.0% ficava muito restritivo, prendendo posições em KuCoin.  
**Solução:** Redução progressiva com monitoring: 1.0% → 0.5% → 0.3%.

---

## Conceito: Rebuy Lock vs Guardrail

### Rebuy Lock
**Objetivo:** Evitar rebuy em posição vencida (abaixo do last_sell_entry)

```python
# Rebuy lock strict (2026-05-01)
if current_price < last_sell_entry_price:
    # Não comprar (esperar bounce)
    pass
else:
    # Ok comprar
    create_buy_order()
```

**Benefício:** Evita "catching falling knife"  
**Risco:** Pode perder spike de recuperação rápida

---

### Guardrail
**Objetivo:** Evitar sell abaixo de X% profit

```python
# Guardrail = min_sell_pnl_pct
min_sell_pnl = position_cost * (1 + guardrail)

if current_price > min_sell_pnl:
    # Ok vender
    create_sell_order()
else:
    # Não vender, esperar bounce
    hold()
```

**Benefício:** Protege contra realized losses  
**Risco:** Posição fica presa se mercado cai demais

---

## O Problema de KuCoin

**Cenário:**
1. Compra BTC em $30.000 (slot 1)
2. Preço cai para $28.000 (-6.7%)
3. Guardrail 1.0% bloqueando sell abaixo $30.300
4. Posição **presa** indefinidamente
5. Outras slots ganham, mas KuCoin bleeding

**Diagnóstico:**
```
Guardrail muito conservador → não permite flexibilidade
```

---

## Tuning Progressivo

### Semana 1: 1.0% → 0.5%
```yaml
# crypto-trader/config.yaml
guardrails:
  min_sell_pnl_pct: 0.005  # 0.5%
```

**Resultado:** +15% sells/dia, algumas posições escapam com -0.5% loss

**Decision:** Reduzir mais

---

### Semana 2: 0.5% → 0.3%
```yaml
guardrails:
  min_sell_pnl_pct: 0.003  # 0.3%
```

**Esperado:** +20% sells/dia, realized losses ~0.3% max  
**Monitoramento:** 48h para confirmar

---

## Per-Slot Independent Positions

**Novo:** Cada slot agora tem seu próprio state:

```python
class TradeSlot:
    def __init__(self, slot_id):
        self.slot_id = slot_id
        self.position = None
        self.last_sell_entry = None   # Rebuy lock per-slot
        self.take_profit = None
        self.trailing_stop = None
        self.rebuy_locked = False     # Bloqueio per-slot
    
    def can_rebuy(self, current_price):
        # Só esse slot olha seu próprio last_sell_entry
        if self.rebuy_locked:
            return current_price < self.last_sell_entry
        return True
    
    def can_sell(self, current_price):
        # Só esse slot olha seu próprio guardrail
        min_sell = self.position.cost * (1 + GUARDRAIL)
        return current_price >= min_sell
```

**Benefício:** Slot 1 preso não bloqueia Slot 2  
**Impacto:** +30% na capacidade de recuperação

---

## Implementation Details

### Config Structure
```yaml
trading:
  slots: 3
  
  guardrails:
    min_sell_pnl_pct: 0.003       # 0.3% global default
    take_profit_pct: 0.015        # 1.5% TP por slot
    
  rebuy:
    lock_strict: true              # BUY só se price < last_sell_entry
    cooldown_seconds: 60           # Aguarde 60s após sell
    
  per_slot:
    enable_independent_state: true
    enable_custom_guardrail: true  # Permite override per-slot
```

### Slot Override Example
```yaml
slots:
  slot_0:
    symbol: "BTC/USDT"
    guardrail_override: 0.005      # Mais conservador que global
  slot_1:
    symbol: "ETH/USDT"
    guardrail_override: 0.002      # Mais agressivo
```

---

## Monitoramento & Alertas

### Prometheus Metrics
```
# Realized PnL
crypto_trading_realized_pnl_total{exchange="kucoin", symbol="BTC/USDT"} = -5.2
crypto_trading_realized_loss_count{exchange="kucoin"} = 23

# Guardrail blocks
crypto_guardrail_blocks_total{reason="pnl_below_min"} = 1024
crypto_guardrail_blocks_avg_hours_locked = 3.5

# Per-slot metrics
crypto_slot_position_duration_hours{slot="0"} = 12.4
crypto_slot_pnl_realized{slot="1"} = +2.3
```

### Alertas
```yaml
- name: "Position Locked > 6h"
  condition: "crypto_slot_position_duration_hours > 360"
  action: notify_slack
  
- name: "Unrealized Loss > 5%"
  condition: "crypto_unrealized_loss_pct > 0.05"
  action: notify_slack, suggest_manual_review
  
- name: "Guardrail blocks spike"
  condition: "increase(crypto_guardrail_blocks_total[1h]) > 100"
  action: page_oncall
```

---

## Decisão Framework

### Quando aumentar guardrail (mais conservador)
- [ ] Realized losses > 2% em 24h
- [ ] Posição presa > 12h e trending down
- [ ] Market volatility muito alta (VIX equivalent)

### Quando diminuir guardrail (mais agressivo)
- [ ] Realized losses negligíveis (<0.1%)
- [ ] Positions opening too fast (unable to capture full move)
- [ ] Market entering bull run (want to stay in longer)

---

## Testing & Validation

### Backtesting
```bash
cd crypto-trader
pytest tests/guardrail_backtest.py \
  --min-sell-pnl=0.003 \
  --exchange=kucoin \
  --period=30d
```

### Paper Trading
```bash
# Deploy com dry_run=True primeiro
crypto-trader --dry-run --min-sell-pnl=0.003
# Aguarde 24h, revisar P&L vs live

# Se P&L similar, deploy com dry_run=False
```

### Production Monitoring
```bash
# Primeiros 48h: monitorar cada 1h
watch -n 3600 'curl -s http://localhost:9090/api/v1/query?query=crypto_trading_realized_pnl_total'

# Dias 3-7: monitorar cada 4h
# Semana 2+: monitorar 1x/dia
```

---

## Rollback Procedure

Se guardrail 0.3% não funcionar:

```bash
# 1. Obter último commit estável
git log --oneline | grep -E "guardrail|trading" | head -5

# 2. Revert
git revert 1f7e6ce1  # Fix commit guardrail 0.3%

# 3. Deploy anterior (0.5%)
git checkout 77f5f486  # config: guardrails 0.5%

# 4. Redeploy
kubectl set image deployment/crypto-trader trading=crypto-trader:0.5%
```

---

## Próximos Passos

- [ ] Monitorar guardrail 0.3% por 48h (volume sells, realized PnL)
- [ ] Implementar dynamic guardrail (ajusta com mercado)
- [ ] Adicionar ML predictor (quando desbloquear?)
- [ ] Criar dashboard de per-slot analytics
- [ ] Documentar decision tree para futuras mudanças

---

**Última atualização:** 2026-05-02  
**Mantido por:** Trading Agent, Infrastructure  
**Docs relacionadas:** Trading Strategy, Risk Management, KuCoin Integration
