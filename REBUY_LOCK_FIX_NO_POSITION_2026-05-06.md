# Fix: REBUY Lock — Sem Posição = Entrada Livre

**Data:** 2026-05-06  
**Arquivo:** `/apps/crypto-trader/trading/btc_trading_agent/trading_agent.py`  
**Backup:** `trading_agent.py.bak_rebuy_20260506_080457`  
**Serviços reiniciados:** `crypto-agent@BTC_USDT_conservative`, `crypto-agent@BTC_USDT_aggressive`

---

## Problema identificado

Os agentes BTC-USDT (conservative e aggressive) ficaram **36+ horas sem executar nenhum trade** mesmo com variação de preço de +2% no período (BTC: $80,602 → $82,449).

### Causa raiz

O `rebuy_lock` bloqueava **toda e qualquer compra** enquanto o preço estivesse acima do preço da última entrada vendida, independente de haver posição aberta ou não:

```
🔒 REBUY blocked: preço $82,257.35 >= entrada da última venda $78,487.95
🔒 REBUY blocked: preço $82,289.95 >= entrada da última venda $79,538.85
```

| Agente | Preço atual | Último preço de entrada | Gap |
|---|---|---|---|
| conservative | ~$82,200 | $78,487.95 | +4.7% |
| aggressive | ~$82,200 | $79,538.85 | +3.3% |

O BTC subiu de forma unidirecional após as vendas em 04/05, sem oferecer pullback. O lock estava impedindo o agente de reentrar em um mercado em alta.

---

## Regra anterior (comportamento incorreto)

```python
# Bloqueava BUY independente de haver posição
if last_sell > 0 and price >= last_sell:
    # 🔒 REBUY blocked — sempre
```

## Nova regra (comportamento correto)

```python
# REBUY lock: só aplica se há posição aberta.
# Sem posição = entrada livre sempre.
# O agente DEVE ter sempre 1 posição alocada.
has_position = float(self.state.position) > 0
if has_position and last_sell > 0 and price >= last_sell:
    # 🔒 REBUY blocked (posição aberta) — protege contra DCA no topo
else:
    # 🔓 Sem posição = entrada livre
```

---

## Lógica de negócio documentada

**Princípio:** O agente **SEMPRE deve ter 1 posição alocada**, comprando pelo menor valor estatístico possível e vendendo pelo maior valor estatístico.

| Situação | Comportamento |
|---|---|
| **Sem posição + BUY signal** | ✅ Entrar livremente (próxima janela válida) |
| **Com posição + BUY (DCA) + preço ≥ última entrada** | 🔒 Bloqueado — aguarda desconto |
| **Com posição + BUY (DCA) + preço < última entrada** | ✅ DCA permitido |
| **Com posição + SELL signal** | Guardrail de PnL mínimo aplica normalmente |

---

## Segundo filtro ativo (informação)

Após o fix do REBUY lock, o agente passou a gerar BUY signals corretamente, mas ainda há um segundo filtro:

```
🔒 BUY blocked (AI target): preço $82,432.85 > alvo $80,844.60 (+1.96%)
     ranging:lower_20611_aggr_34%
```

O **AI target** é calculado pelo RAG como o percentil inferior (P34) dos últimos N snapshots de preço. Em regime RANGING, o agente só entra próximo ao "fundo estatístico" do range.

**Preço estimado de entrada (05/06 08:10):**
- buy_target RAG: **$80,779 – $80,845**
- Mínimo 7 dias: $80,813
- Preço atual: $82,432

O target **sobe gradualmente** conforme novos preços entram no histórico. Se o BTC consolidar acima de $82K, o target alcança esse nível em ~6-8h.

---

## Diagnóstico adicional: Bug `applied_min_sell_pnl_pct`

Todos os agentes emitem periodicamente:
```
WARNING: AI trade controls generation failed: 'RegimeAdjustment' object has no attribute 'applied_min_sell_pnl_pct'
```

**Impacto:** Os parâmetros de AI controls (`OLLAMA_TRADE_PARAMS_MODE=apply`) não são aplicados nesses ciclos.  
**Status:** Não bloqueante para execução de trades. Fix pendente no objeto `RegimeAdjustment`.

---

## Validação

```bash
# Verificar status dos serviços
systemctl is-active crypto-agent@BTC_USDT_conservative.service
systemctl is-active crypto-agent@BTC_USDT_aggressive.service

# Verificar novo comportamento nos logs
journalctl -u "crypto-agent@BTC_USDT_conservative.service" -f | grep -E "BUY|REBUY|blocked|livre"

# Confirmar último trade no DB
PGPASSWORD=eddie_memory_2026 psql -h localhost -p 5433 -U postgres -d btc_trading \
  -c "SELECT id, side, profile, price, to_timestamp(timestamp) FROM btc.trades ORDER BY timestamp DESC LIMIT 5;"
```
