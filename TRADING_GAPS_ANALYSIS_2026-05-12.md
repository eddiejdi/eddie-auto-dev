# 📊 ANÁLISE DETALHADA DE GAPS NA NEGOCIAÇÃO
## Trading Agent - BTC-USDT & USDT-BRL
**Data da análise**: 12 de maio de 2026  
**Status**: ⚠️ GAPS SIGNIFICATIVOS IDENTIFICADOS

---

## 📈 RESUMO EXECUTIVO

### Dados Coletados
| Métrica | BTC-USDT | USDT-BRL | Status |
|---------|----------|----------|--------|
| **Total de Trades** | 1,652 | 6 | ⚠️ |
| **BUYs** | 838 | 6 | ✓ |
| **SELLs** | 584 | 0 | ❌ CRÍTICO |
| **Período** | Jan-Mai 2026 | Abr-Mai 2026 | — |
| **Win Rate** | 57.71% | — | ✓ |
| **Total PnL** | +3.4279 USDT | — | ✓ |

---

## 🔍 GAPS TEMPORAIS - ANÁLISE CRÍTICA

### 1. BTC-USDT: Distribuição de Gaps

| Classificação | Quantidade | % do Total | Significado |
|---------------|-----------|-----------|------------|
| **Gaps > 5 min** | 775 | 47% | Pausas normais |
| **Gaps > 30 min** | 275 | 17% | ⚠️ Pausas longas |
| **Gaps > 1 hora** | 192 | 12% | ⚠️ CRÍTICO |
| **Gaps > 6 horas** | ~80 | 5% | ❌ Muito longo |
| **Gaps > 24 horas** | ~30 | 2% | ❌ MUITO CRÍTICO |

**Conclusão**: 192 gaps > 1 hora = **11.6% do tempo sem negociação**

---

### 2. TOP 10 Maiores Gaps Detectados

| Rank | Duração | Data/Hora | Período |
|------|---------|-----------|---------|
| 🔴 1️⃣ | **1,278h 19min** (53.3 dias) | 2026-01-02 18:16 | **INICIAL - Startup** |
| 🟠 2️⃣ | **89h 58min** (3.7 dias) | 2026-03-28 13:23 | ? |
| 🟠 3️⃣ | **79h 45min** (3.3 dias) | 2026-04-23 17:13 | ? |
| 🟠 4️⃣ | **78h 28min** (3.3 dias) | 2026-04-18 20:39 | ? |
| 🟡 5️⃣ | **67h 53min** (2.8 dias) | 2026-02-27 23:49 | ? |
| 🟡 6️⃣ | **67h 50min** (2.8 dias) | 2026-03-06 14:32 | ? |
| 🟡 7️⃣ | **63h 37min** (2.6 dias) | 2026-04-01 07:13 | ? |
| 🟡 8️⃣ | **50h 02min** (2.1 dias) | 2026-05-07 15:24 | **RECENTE** ⚠️ |
| 🟡 9️⃣ | **47h 48min** (2.0 dias) | 2026-04-29 12:49 | **RECENTE** ⚠️ |
| 🟡 🔟 | **42h 23min** (1.8 dias) | 2026-05-04 17:51 | **RECENTE** ⚠️ |

**Padrão observado**: Gaps longos ocorrem principalmente em:
- 🔴 Início do sistema (jan-02)
- 🟠 Períodos intermediários (fev-mar-abr)
- 🟡 **PRESENTE** - Últimos 10 dias com gaps > 42h

---

### 3. USDT-BRL: Situação Crítica

| Métrica | Valor | Status |
|---------|-------|--------|
| Total Trades | 6 | ⚠️ |
| BUYs | 6 | ⚠️ |
| **SELLs** | **0** | ❌ CRÍTICO |
| Gaps > 5 min | 3 | — |
| Gaps > 1 hora | 1 | — |
| **Max Gap** | **32,879 min** (22.8 dias) | ❌ EXTREMO |

**Análise**: 
- ❌ 6 BUYs abertos, **NENHUM SELL** executado
- ❌ Posição presa sem saída
- ⚠️ Comportamento de "fire-and-forget"

---

## 📊 ANÁLISE DE PERFORMANCE

### Win Rate por Side (BTC-USDT)
```
BUY  (838 ops):  Avg PnL% = +0.0761%  | Total: +$?
SELL (584 ops):  Avg PnL% = +0.0761%  | Total: +$3.4279
```

### Distribuição de PnL
- **Min PnL%**: -14.8143% (Trade com grande loss)
- **Max PnL%**: +3.9222% (Trade com ótimo ganho)
- **Avg PnL%**: +0.0761% (Muito conservador)
- **Amplitude**: 18.74% (Alto desvio)

---

## ⚠️ QUESTÕES CRÍTICAS IDENTIFICADAS

### 🔴 Problema 1: USDT-BRL Preso
**Severidade**: CRÍTICA  
**Descrição**: 6 BUYs abertos sem nenhum SELL  
**Impacto**: Posição presa, sem liquidez  
**Detalhes**:
- conservative profile: 2 BUYs (net: 4.67 USDT) + 0 SELLs
- aggressive profile: 3 BUYs (net: 6.82 USDT) + 0 SELLs
- exchange_sync profile: 1 BUY (net: 9.48 USDT) + 0 SELLs
- **Total: 6 BUYs | 0 SELLs | Net USDT: 20.97 USDT aberto**

**Investigação necessária**:
- [ ] Verificar reason de bloqueio de SELLs em USDT-BRL
- [ ] Analisar guardrail configuration (min_sell_pnl_pct muito alto?)
- [ ] Confirmar se é dry-run ou live (presumido: LIVE)

### � Problema 1: USDT-BRL Preso
**Severidade**: CRÍTICA  
**Descrição**: 6 BUYs abertos sem nenhum SELL  
**Impacto**: Posição presa, sem liquidez  
**Detalhes**:
- conservative profile: 2 BUYs (net: 4.67 USDT) + 0 SELLs
- aggressive profile: 3 BUYs (net: 6.82 USDT) + 0 SELLs
- exchange_sync profile: 1 BUY (net: 9.48 USDT) + 0 SELLs
- **Total: 6 BUYs | 0 SELLs | Net USDT: 20.97 USDT aberto**

**Investigação necessária**:
- [ ] Verificar reason de bloqueio de SELLs em USDT-BRL
- [ ] Analisar guardrail configuration (min_sell_pnl_pct muito alto?)
- [ ] Confirmar se é dry-run ou live (presumido: LIVE)

### 🔴 Problema 2: Trades em Reconciliation Presos por 8 Dias
**Severidade**: CRÍTICA  
**Descrição**: 3 trades em status `reconciliation` desde 6-7 de abril  
**Impacto**: Dados de negociação inconsistentes, possível perda de posição  
**Detalhes**:
- ID 1353: 2026-04-06 00:26 | price: 69209.65 | size: 0 | **PRESO 36+ dias**
- ID 1354: 2026-04-06 00:26 | price: 66362 | size: 0 | **PRESO 36+ dias**
- ID 1374: 2026-04-07 20:23 | price: 68986.2 | size: 0.00007208 | **PRESO 35+ dias**

**Padrão observado**: 
- Reconciliation ficaram presas por ~8 dias
- Em 2026-04-14, 3 trades "filled" apareceram (IDs 1504-1506)
- Possível: agent tentou reconciliar e criou novos registros em vez de atualizar os antigos

**Investigação necessária**:
- [ ] Analisar lógica de reconciliation no `trading_agent.py`
- [ ] Verificar se há erro na UPDATE vs INSERT
- [ ] Limpar trades em reconciliation não resolvidas

### � Problema 3: Gaps > 1 Hora (192 ocorrências)
**Severidade**: ALTA  
**Descrição**: 11.6% do tempo com pausas > 1h  
**Impacto**: Perda de oportunidades de trading  
**Possível causa**: Aguardando reconciliação de trades travados?

### 🟡 Problema 4: Gaps Recentes (Últimos 10 dias)
**Severidade**: MÉDIA-ALTA  
**Descrição**: Padrão consistente de gaps > 40h  
**Impacto**: Atividade reduzida nos últimos dias  
**Possibilidade**: Sistema foi desativado ou reconfigurado em ~2026-04-28

### 🟡 Problema 5: Cobertura de Candles Incompleta
**Status**: ⏳ PENDENTE (query não completou)  
**Descrição**: Possível falta de candles correspondentes aos trades  
**Impacto**: Dados incompletos para análise técnica

---

## 🔧 RECOMENDAÇÕES

### 1. Imediato (CRÍTICO)
- [ ] **Resolva trades em reconciliation** (IDs 1353, 1354, 1374):
  - Status: PRESO desde 2026-04-06/07 (~36 dias)
  - Ação: UPDATE status = 'executed' ou DELETE se irrelevantes
  - Script: `btc_trading_agent/scripts/fix_reconciliation_trades.py`

- [ ] **Investigue USDT-BRL** (6 BUYs, 0 SELLs, 20.97 USDT aberto):
  - Força SELL ou aguarda nova oportunidade?
  - Verificar guardrail de min_sell_pnl_pct em config_USDT_BRL_*.json
  - Confirmar se agente USDT-BRL ainda está ativo

- [ ] **Verifique gap de 50h em 2026-05-07** às 15:24:
  - Qual evento causou essa pausa?
  - Agent foi parado/reiniciado?
  - Logs: `/var/log/journal/crypto-agent@USDT_BRL*` e `/var/log/journal/crypto-agent@BTC_USDT*`

### 2. Curto Prazo (SEMANA)
- [ ] Revisar lógica de bloqueio de SELL em ambos símbolos
- [ ] Confirmar se gaps longos são esperados (dry-run?)
- [ ] Validar cobertura de candles (reexecutar query)
- [ ] Comparar com logs do systemd do crypto-agent

### 3. Médio Prazo (MÊS)
- [ ] Implementar alertas para gaps > 1h
- [ ] Adicionar retry automático para SELLs bloqueados
- [ ] Melhorar logging para rastreabilidade de gaps
- [ ] Considerar dashboard de "trading activity" em tempo real

---

## 📝 CONCLUSÃO

✅ **Performance é positiva** (57.71% WR, +3.4279 PnL)  
✅ **Todos os 1658 trades BTC-USDT em LIVE** (não dry-run)  
⚠️ **MAS há GAPS SIGNIFICATIVOS** (192 > 1h, 11.6% do tempo inativo)  
⚠️ **3 trades presos em reconciliation por 36+ dias** (desde 2026-04-06)  
❌ **CRÍTICO**: USDT-BRL preso com 6 BUYs, 0 SELLs, 20.97 USDT aberto  

🔍 **Requer investigação urgente** dos gaps, reconciliation travada e bloqueio de SELLs em USDT-BRL.

---

## 📌 Dados Brutos Coletados

```
TRADES POR SYMBOL E LADO (executed status):
  BTC-USDT: 1652 total | 838 BUYs | 584 SELLs
  USDT-BRL: 6 total   | 6 BUYs   | 0 SELLs  ❌

DISTRIBUIÇÃO DE STATUS:
  executed      : 1658 trades ✅
  filled        : 3 trades (IDs 1504-1506, 2026-04-14)
  reconciliation: 3 trades (IDs 1353-1354-1374, desde 2026-04-06/07) ⚠️

BTC-USDT MODE:
  live (dry_run=false): 1658 trades ✅
  dry_run (dry_run=true): 0 trades

USDT-BRL POSIÇÕES ABERTAS:
  conservative  : 2 BUYs → net: 4.67 USDT
  aggressive    : 3 BUYs → net: 6.82 USDT
  exchange_sync : 1 BUY  → net: 9.48 USDT
  TOTAL: 6 BUYs, 0 SELLs → net: 20.97 USDT ABERTO

HISTÓRICO TEMPORAL:
  Período: 2026-01-02 18:16:15 → 2026-05-08 19:27:22 (~4 meses e 6 dias)
  
GAPS CRÍTICOS:
  BTC-USDT:
    - Gaps > 5 min : 775 occurrências (47%)
    - Gaps > 1 hora: 192 occurrências (11.6%)
    - Max gap     : 1278h 19min (53.3 dias) - início do sistema
  
  USDT-BRL:
    - Gaps > 5 min : 3 occorrências
    - Gaps > 1 hora: 1 occorrência
    - Max gap      : 32879 min (22.8 dias)

TRADES PRESOS EM RECONCILIATION (IDs 1353-1354-1374):
  1353: 2026-04-06 00:26:35 | reconcile | price: 69209.65 | size: 0
  1354: 2026-04-06 00:26:38 | reconcile | price: 66362   | size: 0
  1374: 2026-04-07 20:23:38 | reconcile | price: 68986.2 | size: 7.208e-05
```
