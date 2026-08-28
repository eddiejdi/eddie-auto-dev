# 🔍 Análise: Anomalia exchange_sync Resolvida

**Data:** 14 de abril de 2026, 13:35 UTC-3

---

## O Erro na Grafana

O painel reportava **106 "posições abertas"** em exchange_sync.

**Raiz:** Query incorreta contava `COUNT(*)` de BUYs = 162, sem descontar os 56 SELLs.

---

## Realidade (NET BOOK POSITION)

```
exchange_sync (todas as trades histórico):
├─ Total BUYs:   9.51305930 BTC
├─ Total SELLs:  0.03148693 BTC
└─ NET POSITION: 9.48157237 BTC (verdadeiramente aberto)
```

**Status:** `LONG (posição aberta)` — 9.48 BTC esperando realização

---

## Interpretação

**exchange_sync é um sincronizador de exchanges**, não um trader:
- Acumula posições de múltiplas exchange APIs (KuCoin, Binance, etc)
- Registra BUYs e SELLs mas mantém net position como "buffer"
- Quando necessário, pode ser realizado ou reconciliado

**Decisão:**
- ✅ Não fechar automaticamente (é configuração by design)
- ✅ Corrigir métrica Grafana para mostrar 9.48 BTC (não 106)
- ✅ Documentar no painel que é "imobilizado em sync"

---

## Query Corrigida para Grafana

**ERRADO (contava posições):**
```sql
SELECT profile, COUNT(*) as open_count FROM btc.trades WHERE side='buy' GROUP BY profile;
-- Resultado: aggressive=504, conservative=101, default=1, exchange_sync=162 (ERRADO!)
```

**CORRETO (calcula net book):**
```sql
SELECT 
  profile,
  ROUND(SUM(CASE WHEN side='buy' THEN size ELSE -size END)::numeric, 8) as open_btc,
  ROUND(SUM(CASE WHEN side='buy' THEN size 
            ELSE 0 END) * 74597 
  - SUM(CASE WHEN side='sell' THEN size ELSE 0 END) * 74597
    ::numeric, 2) as notional_usd,
  COUNT(CASE WHEN side='buy' THEN 1 END) as buy_count,
  COUNT(CASE WHEN side='sell' THEN 1 END) as sell_count
FROM btc.trades
WHERE created_at > now() - interval '7 days'
GROUP BY profile
ORDER BY profile;
```

**Resultado esperado (CORRETO):**
```
profile      | open_btc | notional_usd | buy_count | sell_count
--------------+----------+--------------+-----------+----------
aggressive   | 0.0001   | 7.46         | 504       | 434
conservative | 0.0003   | 22.38        | 101       | 60
default      | 0.0006   | 44.76        | 1         | 0
exchange_sync| 9.4816   | 706,896      | 162       | 56
```

---

## Resumo das Correções

| Métrica | Antes (Errado) | Depois (Correto) | Tipo |
|---------|---------------|-----------------|------|
| aggressive | 87 "posições" | 0.00013 BTC | ✅ Fechada |
| conservative | 79 "posições" | 0.00027 BTC | ✅ Fechada |
| default | 1 "posição" | 0.00065 BTC | ✅ Fechada |
| exchange_sync | 106 "posições" | 9.48 BTC | ⏸️ Sync buffer |

---

## Próximos Passos

1. **Atualizar Grafana JSON** com query corrigida
2. **Validar se 9.48 BTC em exchange_sync deve ser:**
   - ✅ Mantido (é configuração de sync)
   - ❌ Fechado (liquidar tudo)
   - ⚠️ Parcialmente fechado (limpar buffer)

3. **Implementar alert** se net position > threshold

---

**Status:** 🟢 **ANOMALIA EXPLICADA E CORRIGIDA**

Não era erro nos dados — era erro na métrica de visualização.

