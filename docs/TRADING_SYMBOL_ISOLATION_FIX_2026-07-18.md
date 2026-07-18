# Fix: Isolamento multi-moeda RAG/Janela IA + Grafana (2026-07-18)

## Resumo

Incidente e correção de **contaminação cruzada entre moedas** (BTC/ETH/SOL/DOGE/USDT-BRL) nos arquivos de estado do Market RAG e da janela operacional de IA, com impacto em:

1. **Métricas Prometheus / Grafana** (alvos e janelas de uma moeda aparecendo em outra)
2. **Runtime de trading** (gates de BUY/janela lendo estado compartilhado por *profile* apenas)
3. **Painel ROI do modelo** (preço/label hardcoded em BTC)

Adicionalmente, no perfil **aggressive** foi ativado um **teste de autoridade plena da IA** nos trade controls (`ai_trade_controls` com blend 1.0).

---

## Sintomas observados

### Grafana (`btc-trading-monitor`, coin=DOGE-USDT)

- Card de preço DOGE com valor de outra moeda (ex.: ~$74 ≈ SOL)
- Alvos IA misturados: buy target $64k (BTC), entry $5.13 (USDT-BRL)
- Painel ROI: `Posicao por Trades: 2392 BTC` (era DOGE da conta trade, mal rotulado)
- Painel 99 (posições) correto: DOGE aggressive 13x + conservative 5x; shadow flat

### AI Plan

- Texto `Preço mín. p/ desbloquear SELL: N/A (sem posição aberta)` no **shadow** (correto — flat)
- Confusão visual porque o filtro multi-profile no Grafana lista posições de cons+aggr no mesmo painel

### Prometheus (antes do fix)

```
btc_rag_ai_buy_target{coin="DOGE-USDT",profile="shadow"}   → 64071   # BTC
btc_trade_window_entry_low{coin="DOGE-USDT",profile="aggressive"} → 5.13  # USDT-BRL
```

---

## Causa raiz

Todos os `crypto-agent@*` e `crypto-exporter@*` usam o mesmo `WorkingDirectory`:

`/apps/crypto-trader/trading/btc_trading_agent`

Arquivos **somente por profile** eram sobrescritos pela última moeda a recalibrar/escrever:

| Arquivo legado | Problema |
|----------------|----------|
| `data/market_rag/regime_adjustments_{profile}.json` | Último writer vence entre BTC/ETH/SOL/DOGE |
| `data/market_rag/trade_window_{profile}.json` | Janela IA de uma moeda lida por todas |
| `data/market_rag/index.pkl` | Índice vetorial legado multi-moeda (já havia `index_{symbol}.pkl`) |

O exporter lia esses paths **sem validar `symbol`**, exportando o estado da última moeda com o label da instância atual.

### Impacto em runtime (sim, afetava perfis)

| Componente | Impacto |
|------------|---------|
| Exporter / Grafana | Alto — métricas cruzadas |
| Janela BUY (`_get_fresh_ai_trade_window`) | Médio/Alto — se `symbol` no JSON batia com outra moeda, janela era rejeitada (perda de gate); se ausente/legado, risco de aplicar preço errado |
| Buy target em memória | Médio no restart — load do JSON compartilhado até recalibrar (~5 min) |
| Posições / trades / PnL DB | Não — filtrados por `symbol+profile` |
| Painel 99 | Não — SQL por `$coin` |

---

## Correção de código

### 1. Isolamento de arquivos por `symbol + profile`

- `market_rag.py` → `regime_adjustments_{SYMBOL}_{profile}.json`
- `trading_agent.py` → `trade_window_{SYMBOL}_{profile}.json`
- `prometheus_exporter.py` → lê paths isolados; **rejeita** legado se `symbol` no JSON ≠ moeda da instância

### 2. Aggressive: AI trade controls com autoridade plena (teste)

Bloco `ai_trade_controls` nos `config_*_aggressive.json`:

- `apply_blend_* = 1.0` (applied ≈ suggested)
- floors/ceilings alargados
- `test_label: aggressive_ai_authority_2026-07-18`
- Policy configurável em `MarketRAG._resolve_ai_trade_control_policy()`
- Conservative/shadow **sem** o bloco (blend histórico 35%/50%)

### 3. Grafana `btc-trading-monitor`

- ROI: preço live de `btc.market_states WHERE symbol='$coin'` (não mais snapshot global)
- Label de posição: `{{{base_asset}}}` em vez de `BTC`
- Legendas `BTC Price` → `Preço $coin`

### 4. Testes

- `tests/test_ollama_trade_controls.py`: nome de arquivo isolado + blend 1.0 aggressive + default policy

---

## Saneamento em produção (homelab)

1. Deploy de `market_rag.py`, `trading_agent.py`, `prometheus_exporter.py`
2. Restart de todos `crypto-agent@*` e `crypto-exporter@*`
3. Validação de coerência de escala por moeda nos JSONs isolados
4. Quarentena dos legados:

```
/apps/crypto-trader/trading/btc_trading_agent/data/market_rag/legacy_quarantine_20260718_092020/
```

Conteúdo: `regime_adjustments_{aggressive,conservative,shadow}.json`, `trade_window_{...}.json`, `index.pkl`

5. Smoke: DOGE rejeita janela BTC; Prometheus `PROM_SCALE_PASS`

### Verificação pós-fix (Prometheus)

| Moeda | buy_target | window_low |
|-------|------------|------------|
| DOGE | ~0.07 | ~0.07 |
| BTC | ~64090 | ~64080 |
| ETH | ~1843 | ~1839–1846 |
| SOL | ~74.8 | ~74.6–74.7 |

---

## Layout canônico de arquivos RAG

```
data/market_rag/
  index_{SYMBOL}.pkl
  regime_adjustments_{SYMBOL}_{profile}.json
  trade_window_{SYMBOL}_{profile}.json
  legacy_quarantine_YYYYMMDD_HHMMSS/   # somente histórico
```

**Não recriar** paths só-profile.

---

## Monitoramento aggressive (16,5 min)

- Serviços OK; 0 trades no período
- Após AI authority: `suggested == applied` (ex.: conf 0.65)
- Gargalos remanescentes: `sell_guardrail_min_pnl` (posições underwater) e `low_confidence` pós-subida de conf pela IA

---

## Rollback

### Código

Reverter o PR / redeploy da versão anterior.

### Arquivos de estado (não recomendado)

```bash
sudo mv /apps/crypto-trader/trading/btc_trading_agent/data/market_rag/legacy_quarantine_20260718_092020/* \
  /apps/crypto-trader/trading/btc_trading_agent/data/market_rag/
sudo systemctl restart 'crypto-agent@*' 'crypto-exporter@*'
```

Isso **reintroduz contaminação**.

---

## Checklist operacional

- [ ] Paths isolados existem por coin+profile em produção
- [ ] Pasta `legacy_quarantine_*` presente; raiz sem `trade_window_aggressive.json` etc.
- [ ] Prometheus: buy_target/window na escala da moeda
- [ ] Grafana DOGE: preço ~0.07, sem alvos $64k/$5.13
- [ ] Aggressive: logs `AI trade controls [apply]` com applied≈suggested
- [ ] Conservative/shadow: sem `ai_trade_controls` no config (blend legado)

---

## Referências

- Dashboard: `grafana/dashboards/btc-trading-monitor.json` (uid `btc-trading-monitor`)
- Isolamento anterior do index: branch histórica `fix/market-rag-symbol-isolation`
- Skill trading: `.claude/commands/trading.md` (Postgres only, multi-coin)
