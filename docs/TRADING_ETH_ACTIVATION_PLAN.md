# Plano de Ativação — Negociação ETH-USDT

> **STATUS 2026-07-04: EXECUTADO (acelerado).** Fase A rodou ~10h; o usuário
> autorizou live direto (Fase B encurtada). Frota 6/6 em modo real — ver
> `TRADING_MULTI_SYMBOL_LIVE_2026-07-04.md`. A modularização (seção 2)
> continua pendente e válida.

Planejado em 2026-07-03 a pedido do usuário. Pré-requisito: modularização mínima
do `trading_agent.py` (seção 2), porque ativar um segundo símbolo multiplica o
custo de manutenção do monolito.

## 0. Decisões já tomadas (contexto)

- **Política de saída (definida 2026-07-03)**: nunca realizar prejuízo — o piso
  de venda é o lucro mínimo acima dos custos. Implementação vigente:
  `guardrails_positive_only_sells: true` + `guardrails_min_sell_pnl_pct: 0.003`
  (0,3% ≥ taxa round-trip de 0,2% + margem). `auto_stop_loss` permanece
  **desabilitado por design** (o `stop_loss_pct: 0.03` da config é ignorado).
  A mesma política se aplica ao ETH.
- Shadow live no BTC é intencional (A/B test MACD vs baseline).
- Mensagens de trading vão para o grupo Telegram "BTC Trade Agent"
  (`-1004434951297`) — avaliar renomear para "Trade Agent" ao incluir ETH.

## 1. O que já é multi-símbolo (verificado no código)

| Componente | Status |
|---|---|
| `trading_agent.py` | `--config config_<PAR>_<perfil>.json` define `symbol`; `DEFAULT_SYMBOL` é só fallback |
| `crypto-agent@.service` | template `%I` → `COIN_CONFIG_FILE=config_%I.json` + `envfiles/%I.env` — instância nova = config + envfile |
| Schema `btc.*` | tabelas têm coluna `symbol` (o nome do schema é legado, não limita) |
| Dashboard | variável `$coin` já lista ETH-USDT; queries filtram por `coin` |
| MCP trading_* | parâmetro `symbol` em todas as tools |
| KuCoin API | endpoints por símbolo; `get_price_fast("ETH-USDT")` funciona hoje |

## 2. Pré-requisito: modularização do trading_agent.py (aprovada 2026-07-03)

5.857 linhas hoje. Extrações em ordem de risco crescente, uma por PR, com a
suíte de regressão passando em cada passo e sem mudança de comportamento:

1. **`ai_planner.py`** — `_generate_ai_plan`, `_parse_ai_plan_controls`,
   `_sanitize_ai_plan`, `_build_fallback_ai_plan`, `_save_ai_plan`,
   `_cleanup_garbage_plans` (~900 linhas; só depende de db/ollama/estado).
2. **`ai_controls.py`** — `_generate_ai_trade_controls/_window`, parsers e
   saves correspondentes (~700 linhas).
3. **`market_context.py`** — `_analyze_signal_context`, `_get_buy_*`,
   `_get_sell_*`, profit-guard (~600 linhas).
4. O núcleo (`_run_loop`, `_execute_trade`, `_check_can_trade`) fica em
   `trading_agent.py` (~2.000 linhas ao final).

Critério de aceite por etapa: `pytest tests/test_btc_*` verde + 24h de shadow
sem divergência de decisão vs baseline (comparar `btc.decisions`).

## 3. Fases de ativação do ETH

### Fase A — Shadow/dry (sem dinheiro; ~30 min de trabalho)
1. `config_ETH_USDT_shadow.json`: clonar do shadow BTC com
   `symbol: "ETH-USDT"`, `dry_run: true`, `min_trade_amount: 10`,
   guardrails idênticos (positive-only sells).
2. `envfiles/ETH_USDT_shadow.env`: `TRADING_TELEGRAM_CHAT_ID=-1004434951297`.
3. `systemctl enable --now crypto-agent@ETH_USDT_shadow` (dry — não requer
   aprovação de trading real).
4. Exporter: `crypto-exporter@ETH_USDT_shadow` na porta **9096** + scrape job
   `servidor: homelab, coin: ETH-USDT` no prometheus.yml.
5. Validar: decisões em `btc.decisions symbol='ETH-USDT'`, candles ETH
   coletados, dashboard com `$coin=ETH-USDT` populando.

### Fase B — Validação (1–2 semanas)
- Win rate shadow ≥ 60% e PnL simulado positivo líquido de taxas.
- Volatilidade ETH ≈ 1,5–2× BTC: revisar `max_volatility` (0.08→0.12?) e
  `dca_valley_bounce_pct`.
- Conferir se o modelo `trading-analyst` gera planos coerentes para ETH
  (prompts usam o símbolo da config — sem hardcode de BTC detectado, mas
  validar saída real).

### Fase C — Live conservador (requer aprovação explícita + revisão)
1. Gate da política de deploy: regressão completa + confirmação do usuário.
2. `config_ETH_USDT_conservative.json`: `dry_run: false`,
   `min_trade_amount: 10`, alocação inicial pequena (ex.: 15% do capital
   trade — hoje ~$84 dos ~$560), `max_positions` reduzido (ex.: 4).
3. Capital: decidir origem — conta trade compartilhada com BTC (mais simples;
   `_get_active_symbol_profiles` já rateia exposição entre perfis live) ou
   subconta dedicada (isolamento melhor; exige credencial da subconta no
   secrets agent e testes do fluxo de transferência).
4. Ativar e acompanhar 48h com relatório diário incluindo ETH (o script
   é por-símbolo: adicionar loop de símbolos no `trading_daily_report.py`).

### Fase D — Perfil aggressive ETH (opcional, após 30 dias de histórico)

## 4. Riscos e mitigação

- **Capital compartilhado**: BTC e ETH disputam o mesmo saldo trade — o rateio
  por perfil existe, mas foi testado só com 1 símbolo; Fase A/B valida com
  dry antes de arriscar.
- **GPU/Ollama**: cada perfil novo adiciona chamadas ao trading-analyst;
  monitorar latência do coordinator (11437) com 4+ perfis.
- **Schema**: `btc.candles` é UNIQUE(timestamp, symbol, ktype) — ok; volume de
  candles dobra (~2× storage, hoje irrelevante).
- **Exporter/Prometheus**: nunca reutilizar porta de outro perfil (lição:
  séries duplicadas silenciosas).

## 5. Estimativa

| Fase | Esforço | Dependência |
|---|---|---|
| Modularização 1 (ai_planner) | 1 sessão | — |
| Fase A shadow ETH | 30 min | nenhuma (pode preceder a modularização) |
| Fase B validação | 1–2 semanas corridas | Fase A |
| Fase C live | 1 sessão + aprovação | Fase B + política de deploy |
