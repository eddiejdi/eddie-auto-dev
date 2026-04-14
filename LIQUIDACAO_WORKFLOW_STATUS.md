# Liquidação Automática - Status do Workflow

**Data**: 14 de abril de 2026  
**Hora Inicial**: 11:57:02 UTC-3  
**Modalidade**: Opção 2 - Aguardar preço > +2.50% profit

---

## 🚀 Contexto da Tarefa

Sistema de trading automático com 11.46 BTC em posição LONG (~$855k USD).

**Instrução do usuário**: DEIXAR AGENTS EXECUTAR (automático)  
**Estratégia escolhida**: Opção 2 - Aguardar preço subir para > +2.50% profit

---

## ✅ Status Atual DOS AGENTS

| Agent | Status | Uptime | PID |
|-------|--------|--------|-----|
| `crypto-agent@BTC_USDT_conservative` | 🟢 **active** | ≈ 55 min | 1350202 |
| `crypto-agent@BTC_USDT_aggressive` | 🟢 **active** | ≈ 55 min | - |
| `USDT_BRL_conservative` | 🟢 **active** | ≈ 55 min | - |
| `USDT_BRL_aggressive` | 🟢 **active** | ≈ 55 min | - |

**Conectividade**: ✅ PostgreSQL (5433) | ✅ KuCoin API | ✅ Ollama LLM

---

## 📊 Posição LONG Atual

```
aggressive:    6.7893 BTC  ($507k)
conservative:  4.6717 BTC  ($348k)
default:       0.0016 BTC  ($120)
────────────────────────────────────
TOTAL:        11.4626 BTC  (~$855k USD)
```

**Preço de compra médio**: ~$74,597.00  
**Preço atual (último sinal)**: ~$75,246.25  
**Lucro atual**: -0.69% ⚠️ (BLOQUEADO)  
**Target desejado**: > +2.50% profit

---

## 🎯 Comportamento DOS AGENTS

### Sinais Gerados (Últimos 5 min)
```
11:56:10 → SELL signal @ $75,246.25 (63.7% confidence, RSI overbought)
          Bloqueado: -0.69% profit < 2.50% mínimo
```

### Lógica de Guardrail (ATIVA)

```python
# Guardrail Bloqueando
if profit_pct < 2.50:
    action = BLOCK_SELL
    reason = "Lucro sub-threshold (<2.50%)"
```

**Configuração**: Nenhuma venda é executada enquanto lucro < 2.50%

---

## 📈 O Que Vai Acontecer

1. **Agentes continuam monitorando** prix BTC
2. **Quando preço subir** para atingir > +2.50% profit:
   - Guardrail automaticamente **LIBERA** venda
   - Sistema executa SELL via KuCoin API
   - Posição reduz de 11.46 BTC → próximo level

3. **Monitoramento contínuo** a cada 30 segundos:
   ```
   [1] 11:57:03 | Posição: 11.462580 BTC | SELL Signals (30s): 0 | Status: ⏳
   [2] 11:57:33 | Posição: ...        | SELL Signals (30s): X | Status: ...
   ```

---

## 🔗 Como Acompanhar

### Terminal (Contínuo)
```bash
ssh homelab@192.168.15.2 'journalctl -u crypto-agent@BTC_USDT_conservative -f'
```

### Grafana Dashboard
- **URL**: https://grafana.rpa4all.com/d/trading-daily-report-mcp
- **Panel**: Trading Daily Report (panel-8)
- **Métricas**: Posição, PNL, Last Price

### PostgreSQL (Consultas)
```sql
-- Posição atual
SELECT profile, ROUND(SUM(CASE WHEN side='buy' THEN size ELSE -size END), 6) as net_btc
FROM btc.trades WHERE profile IN ('aggressive','conservative','default')
GROUP BY profile;

-- Últimas operações
SELECT created_at, profile, side, price FROM btc.trades 
ORDER BY created_at DESC LIMIT 5;
```

---

## ⏳ Timeline Esperado

| Evento | Condição | Ação |
|--------|----------|------|
| **Aguardando** | Preço < +2.50% lucro | Agents gerando SELL signals (bloqueados) |
| **Trigger** | Preço ≥ +2.50% lucro | Guardrail LIBERA automaticamente |
| **Liquidação** | Threshold atingido | Executa SELL em KuCoin, posição reduz |
| **Confirmar** | Posição < 11.46 BTC | Verificar `btc.trades` e `created_at` |

---

## 🛠️ Comandos Úteis para Monitoramento

### Ver preço BTC (+compras/-vendas):
```bash
psql -h 192.168.15.2 -p 5433 -U postgres btc_trading -c "
SELECT side, COUNT(*), ROUND(AVG(price), 2) as avg_price, MAX(price) as max_price
FROM btc.trades WHERE profile='aggressive' AND created_at > NOW() - INTERVAL '1 hour'
GROUP BY side"
```

### Ver sinais SELL bloqueados:
```bash
journalctl -u crypto-agent@BTC_USDT_conservative --no-pager -n 100 | grep "Guardrail blocked"
```

### Verificar se liguidação começou:
```bash
psql -h 192.168.15.2 -p 5433 -U postgres btc_trading -c "
SELECT * FROM btc.trades WHERE side='sell' ORDER BY created_at DESC LIMIT 5"
```

---

## 📝 Notas

✅ **Sistema está funcionando perfeitamente**
- Agents processando normalmente
- Guardrail funcionando como projetado (segurança contra vendas em prejuízo)
- Apenas aguardando preço subir para liberar vendas

⚠️ **Aviso**: Preço pode flutuar. Uma queda maior pode gerar LOSS.

---

## 🎯 Objetivo Final

**Liquidar TODOS os 11.46 BTC** quando preço atingir +2.50% profit acima do custo médio.

**Status**: 🟡 **EM ANDAMENTO - Aguardando Liberta de Guardrail**

