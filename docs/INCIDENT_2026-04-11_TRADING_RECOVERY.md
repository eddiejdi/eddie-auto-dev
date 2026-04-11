# Incident Report — Trading Recovery 2026-04-11

## Resumo Executivo

Sessão de diagnóstico e correção completa do sistema de trading BTC, cobrindo:
sincronização de trades, modelo de IA, saturação de GPU, e validação de dashboards Grafana.

**Data:** 11 de Abril de 2026  
**Duração:** ~4h  
**Impacto:** Agentes não compravam, dados inconsistentes, modelo de IA indisponível  
**Status:** ✅ RESOLVIDO — ambos agentes operando normalmente

---

## 1. Problemas Identificados

### 1.1 Orphan Trades (Gravidade: Alta)
- **Sintoma:** 197 trades do perfil aggressive e 18 do conservative sem `order_id` na tabela `btc.trades`.
- **Root Cause:** Função `_detect_external_deposits()` do `trading_agent.py` criava registros BUY "phantom" para cada depósito detectado, sem vincular a uma ordem real na KuCoin.
- **Impacto:** Posição calculada pelo agente divergia da posição real na exchange. O agente acreditava ter posições abertas que não existiam.

### 1.2 Modelo Ollama Ausente (Gravidade: Alta)
- **Sintoma:** Todas as chamadas de IA retornavam `[fallback]` em vez de análises reais.
- **Root Cause:** O modelo `trading-analyst` foi removido do Ollama (não aparecia em `ollama list`). Provavelmente deletado durante manutenção ou atualização.
- **Impacto:** AI trade windows marcadas como `[fallback]`, decisões baseadas apenas em indicadores técnicos sem análise LLM.

### 1.3 GPU1 Saturada (Gravidade: Média)
- **Sintoma:** GTX 1050 com 83% de uso VRAM (755MB de 2GB).
- **Root Cause:** Processo `real_workload.py` (PID 6506) rodando indefinidamente, consumindo GPU1.
- **Impacto:** Agente aggressive (que usa GPU1) não conseguia carregar modelo para inferência.

### 1.4 Testes Desatualizados (Gravidade: Baixa)
- **Sintoma:** 2 testes falhando em `test_grafana_dashboard_queries.py`.
- **Root Cause:** Assertions referenciavam padrões SQL (`$__timeFrom()`) que não correspondiam ao SQL real dos painéis Grafana (`$__unixEpochFrom()` e `LIMIT`).

---

## 2. Correções Aplicadas

### 2.1 Sync Reconciliation (kucoin_postgres_sync.py)
```
Commit: 8ef612f0 — fix(sync): reconciliação de orphan trades + 3-step sync + cleanup duplicatas
```

**Novas funções:**
| Função | Descrição |
|--------|-----------|
| `_match_orphan_to_fill()` | Match KuCoin fills com orphan trades (±120s, same side, size±20%) |
| `_reconcile_position_integrity()` | Valida posição net por profile vs balance na exchange |
| `_cleanup_duplicate_orphans()` | Marca duplicatas como `buy_reconciled`/`sell_reconciled` |

**Processo _sync_fills reformulado (3 steps):**
1. Match por `order_id` exato
2. Match de orphans por timestamp + side + size
3. Insert de novo registro se não há match

**Resultado:** 150 duplicatas limpas (234→84 restantes genuínos).

### 2.2 Modelo Ollama Recriado
```bash
ollama create trading-analyst -f ollama/Modelfile.trading-analyst
```
- Baseado em `qwen3:8b` com system prompt especializado em trading
- AI windows recuperaram de `[fallback]` para `[apply]`

### 2.3 GPU1 Liberada
```bash
kill -9 6506  # real_workload.py
```
- GPU1 liberada de 755MB/83% para 3MB/0%
- Ambos agentes reiniciados após liberação

### 2.4 GPU Selfheal Service
```
Commit: c993452d — feat(monitoring): GPU selfheal service + Grafana alert rules
```
- `ollama_gpu_selfheal.sh`: monitora VRAM, restart Ollama se >90%
- Systemd service: `ollama-gpu-selfheal.service`
- Alertas Grafana para GPU saturada

### 2.5 Dashboard + Testes Corrigidos
```
Commit: 21479d3a — fix(grafana): corrige testes do dashboard para match com SQL real
```
- Painéis 87-89: assert corrigido de `BETWEEN` para `LIMIT` + `ORDER BY`
- Painel 11: assert corrigido de `$__timeFrom` para `$__unixEpochFrom/To`

---

## 3. Medidas Preventivas

### 3.1 Contra Orphan Trades Futuros

| Medida | Status | Descrição |
|--------|--------|-----------|
| **3-step sync** | ✅ Implementado | Sempre tenta match antes de criar novo registro |
| **Orphan matching** | ✅ Implementado | Match por timestamp±120s + side + size±20% |
| **Reconciliation cron** | ✅ Ativo (`*/5 * * * *`) | Valida posição net vs exchange a cada 5 min |
| **validate_trades_sync.py** | ✅ Criado | Script de validação sob demanda |
| **Monitorar orphan_count** | ✅ No log do cron | Alertar se orphan_count crescer anormalmente |

**Recomendação futura:** Adicionar constraint no `trading_agent.py` para que `_detect_external_deposits()` nunca crie trades sem `order_id` válido, ou use um `source='external_deposit'` distinto.

### 3.2 Contra Perda de Modelo Ollama

| Medida | Status | Descrição |
|--------|--------|-----------|
| **Modelfile versionado** | ✅ `ollama/Modelfile.trading-analyst` | Permite recriar modelo a qualquer momento |
| **GPU selfheal service** | ✅ Deployado | Monitora e recupera Ollama automaticamente |
| **Grafana alerts** | ✅ Criados | Alerta se modelo indisponível por >5 min |
| **Healthcheck no cron** | 🔲 Recomendado | Adicionar `ollama show trading-analyst` no cron de sync |

**Recomendação:** Criar cron job que executa `ollama list | grep trading-analyst` a cada hora. Se não encontrar, recriar automaticamente via `ollama create`.

### 3.3 Contra Saturação de GPU

| Medida | Status | Descrição |
|--------|--------|-----------|
| **GPU selfheal** | ✅ `ollama-gpu-selfheal.service` | Mata processos que saturam VRAM |
| **Grafana dashboard** | ✅ Validado | Métricas VRAM/temp no dashboard |
| **Alert rules** | ✅ `grafana_gpu_alert_rules.yml` | Alertas para VRAM >80%, temp >85°C |
| **Bloquear real_workload.py** | 🔲 Recomendado | Adicionar guard clause ou rate limiter |

### 3.4 Contra Testes Desatualizados

| Medida | Status | Descrição |
|--------|--------|-----------|
| **Testes corrigidos** | ✅ | Assertions agora refletem SQL real do dashboard |
| **CI com pytest** | ✅ | Roda em todo push via GitHub Actions |
| **Dashboard JSON versionado** | ✅ | `grafana/btc_trading_dashboard_v3_prometheus.json` |

**Recomendação:** Quando editar painéis no Grafana UI, exportar JSON e atualizar o arquivo versionado imediatamente.

---

## 4. Estado Final do Sistema

### Posições Abertas (11/04 18:15)
| Perfil | Preço Compra | Tamanho | Sell Target | Status |
|--------|-------------|---------|-------------|--------|
| Aggressive | $73,365.15 | 0.000136 BTC | $73,952.07 | Guardrail ativo (-0.16% < 2.50%) |
| Conservative | $73,343.20 | 0.000136 BTC | $73,929.95 | Guardrail ativo |

### RAG Status
- **Regime:** RANGING (confiança 92-100%)
- **Bull/Bear/Flat:** 0% / 0-7.7% / 92-100%
- **Patterns:** 8-15 similares encontrados
- **Modelo:** `trading-analyst` (qwen3:8b) operando em GPU0

### Grafana Market RAG (9 painéis)
- 6 painéis Prometheus: ✅ dados fluindo
- 3 painéis PostgreSQL (ai_plans): ✅ 30 registros BTC-USDT desde 26/03
- Última análise: 11/04 18:14

---

## 5. Commits no GitHub

| Hash | Tipo | Descrição |
|------|------|-----------|
| `8ef612f0` | fix | Reconciliação de orphan trades + 3-step sync |
| `c993452d` | feat | GPU selfheal service + Grafana alert rules |
| `21479d3a` | fix | Testes do dashboard corrigidos para SQL real |
| `796001dc` | fix | Storj selfheal exporter + cert fix |
| `9ff216c8` | feat | FastAPI skeleton + flow preservation |

---

## 6. Lições Aprendidas

1. **Orphan trades são silenciosos** — O agente calculava posição errada sem log de erro. Sempre validar `order_id IS NOT NULL` em queries de posição.
2. **Modelos Ollama são voláteis** — Não persistem entre reinstalações. Manter `Modelfile` versionado e healthcheck ativo.
3. **GPU compartilhada precisa de guardrails** — Um processo batch pode saturar a GPU usada para inferência. Selfheal + alerts são obrigatórios.
4. **Testes de dashboard devem espelhar o SQL real** — Exportar JSON do Grafana e validar programaticamente.
5. **Cron de sync é o coração do sistema** — Deve ser monitorado, logado e ter fallback robusto.
