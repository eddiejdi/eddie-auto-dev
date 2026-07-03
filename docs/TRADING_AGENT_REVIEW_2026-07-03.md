# Revisão do Trading Agent BTC — 2026-07-03

Revisão completa do agente de trading em produção (BTC-USDT, perfis `conservative`,
`aggressive` e `shadow` no homelab) solicitada em 2026-07-03: gaps, padronização,
melhorias e solução de problemas. Inclui a revisão do dashboard Grafana
`btc-trading-monitor`. PRs resultantes: #183, #184, #185, #186, #187, #188.

## 1. Estado encontrado

| Item | Valor |
|---|---|
| Serviços | `crypto-agent@BTC_USDT_{conservative,aggressive,shadow}` ativos em 192.168.15.2 |
| Código | `/apps/crypto-trader/trading/btc_trading_agent/` |
| PnL total | conservative −4,57 USDT (WR 76,8%) · aggressive −4,21 USDT (WR 62,5%) |
| Config | `dry_run: false`, `live_mode: true` (dinheiro real) |
| Testes | 78 regressivos verdes antes do deploy |

## 2. Problemas encontrados e corrigidos

### 2.1 MCP de trading quebrado (PR #183)
Todas as tools `trading_*` do MCP homelab falhavam com
`NameError: TRADING_DATABASE_URL is not defined` — o bloco de trading em
`scripts/homelab_mcp_server.py` (+416 linhas, não commitado) usava a variável sem
defini-la. Fix: `TRADING_DATABASE_URL = os.environ.get(...)` no topo do módulo.
Vale a partir do próximo start do servidor MCP.

### 2.2 "OrangePi" não existe — 192.168.15.3 é o homelab (PR #183)
`192.168.15.3` é o segundo IP da própria máquina homelab (interface `eth-wan`;
`eth-onboard` = 192.168.15.2). Os 3 scrape jobs `crypto-exporter-orangepi-*` no
Prometheus coletavam os **mesmos exporters** já cobertos pelos jobs
`servidor: homelab` (via 172.17.0.1), duplicando toda série com label falso.
Removidos de `monitoring/prometheus.yml`; opção `orangepi` removida do dropdown
do dashboard. Prometheus recarregado via `docker kill -s HUP`.

### 2.3 Trabalho não commitado parcialmente deployado (PR #183)
O working tree tinha features à frente da produção (coluna `servidor` em
`btc.trades`/`btc.decisions`, contexto de performance 7d nos prompts LLM,
`statement_timeout` no exporter), com `training_db.py` **já deployado sem commit**.
Tudo commitado, mesclado em `main` e deployado pelo workflow oficial
`deploy-btc-trading-profiles` (dispatch com `--ref main`).

### 2.4 Starvation de capital logando a cada 5s (PR #183)
46× "Trade amount too small: ~$9" em 24h no conservative — alocação restante do
perfil abaixo de `min_trade_amount: $10`, re-logado a cada poll. Throttle de 1/h
com mensagem explicando a causa (`trading_agent.py`, `_execute_trade`).

### 2.5 Deadlock na migração de schema (PR #184)
O deploy reinicia os 3 perfis juntos; cada agente roda `PROFILE_MIGRATION_SQL`
em `_ensure_schema()` no startup, e os `ALTER TABLE` concorrentes causaram
`psycopg2.errors.DeadlockDetected` no aggressive (auto-recuperado via systemd
restart). Fix: `pg_advisory_xact_lock(hashtext('btc_ensure_schema'))` serializa
a migração (`training_db.py`).

### 2.6 Hooks do Claude Code com path relativo (PR #183)
Os hooks em `.claude/settings.json` (`python3 tools/copilot_hooks/...`) rodam a
partir do cwd do shell da sessão; quando o cwd mudou para um subdiretório, todo
tool call passou a ser bloqueado (deadlock circular — nem o `cd` de volta era
permitido). Fix: `python3 "$CLAUDE_PROJECT_DIR"/tools/...` em todos os hooks.

## 3. Dashboard Grafana `btc-trading-monitor`

### 3.1 Diagnóstico (avaliação viva de ~90 queries)
- **"No Data"**: causa histórica era o filtro `instance=~"$servidor"` (o label
  `instance` vale `btc_usdt_conservative`, nunca `homelab`); migrado para
  `servidor=~` e deployado no PR #183. Avaliação com variáveis substituídas
  confirmou 67/68 painéis com dados.
- **Valores duvidosos**: a seção "Sessão do Agente" duplicava o cabeçalho com
  `max()` sem filtro de perfil/moeda — Win Rate mostrava o melhor perfil, PnL o
  menos negativo, Posição BTC o máximo em vez da soma.
- **Layout quebrado**: gauges do Market RAG com `gridPos` acima do próprio row
  header; stat de 16×16 no meio do log.

### 3.2 Reestruturação (PR #185)
- Removidos 7 stats duplicados + gráfico de preço duplicado + 4 row headers órfãos.
- **Visível ao abrir** (24 painéis, antes ~70): cabeçalho por perfil → Preço/PnL →
  Real vs Previsão IA → Decisões & Trades → Performance & Patrimônio.
- **Rows colapsáveis** (38 painéis): Risk Management, Indicadores Técnicos,
  Market RAG, News Sentiment & Sinais Leading, Saúde do Agente. A query pesada do
  "Ranking por Fonte" só executa se a seção for expandida.

### 3.3 Painel "Disponível para Saque (R$)" (PR #186)
A taxa BRL era buscada apenas nas linhas da conta `trade` (que não têm BRL),
caindo no fallback `COALESCE(..., 1)`: o painel exibia **US$ 516,57 rotulado como
R$** quando o correto era **R$ 2.787,88** (subestimava ~5,3×). Fix: taxa do
snapshot completo, soma main+trade, renomeado para
"💸 Saldo Exchange em R$ (main+trade)".

**Importante:** subcontas KuCoin **não são sincronizadas** —
`btc.exchange_balance_snapshots` só tem `main` e `trade` da conta master.

### 3.4 Painel "Evolução Patrimonial" (PRs #187, #188)
Antes: série única de equity de `btc.exchange_snapshots` (só conta trade).
Agora, a partir de `btc.exchange_balance_snapshots` (~15 min): **Conta Main**,
**Conta Trade**, **BTC (em USDT)** e **USDT** (tracejadas) e **Total** (destacada).

## 4. Descobertas operacionais

- **`grafana-dashboard-sync.timer` (horário, DB→arquivos)** pode sobrescrever
  silenciosamente qualquer deploy de dashboard feito na janela do tick — foi o
  que aconteceu com o primeiro deploy da reestruturação (sobrescrito 14 s depois).
  Mitigação ao deployar manualmente: conferir `systemctl list-timers
  grafana-dashboard-sync.timer` e deployar logo após o tick; o provisioning do
  Grafana recarrega a cada 30 s e, uma vez ingerido, o sync passa a exportar a
  versão nova.
- Dashboard provisionado de
  `/home/homelab/monitoring/grafana/provisioning/dashboards/btc-trading-monitor.json`
  (provider `eddie-dashboards`, `updateIntervalSeconds: 30`); Grafana na porta
  3002 (container `grafana`).
- Timeouts intermitentes da API KuCoin (~8/24h, orderbook/trades) tolerados pelo
  agente, sem impacto.
- Shadow reiniciou 2× em 2026-07-02 porque o Postgres não estava pronto no boot
  pós-queda de energia; o retry do systemd resolveu.

## 5. Pendências — resolução (atualizado no fim de 2026-07-03)

1. **Stop loss** — decisão do usuário: *"deve ser o mínimo de lucro acima dos
   custos (positivo)"* → nunca realizar prejuízo. Já era o comportamento
   vigente (`guardrails_positive_only_sells` + `min_sell_pnl_pct 0.3%` >
   taxas 0.2%); `auto_stop_loss` fica **desabilitado por design**.
2. **Credencial do DB** — movida para o Secrets Agent/Authentik
   (`shared/database_url`, field `url`; item `secret-shared-database-url-url`
   no Authentik). Linha `Environment=DATABASE_URL=` removida do drop-in
   `crypto-agent@.service.d/common.conf` (host e repo); o agente resolve via
   `secrets_helper.get_database_url()` (testado ponta-a-ponta). Vale a partir
   do próximo restart dos agentes. **Ainda inline no drop-in**:
   `TELEGRAM_BOT_TOKEN` — candidato à mesma migração.
3. **Subcontas KuCoin** — implementado: `get_sub_account_balances()` em
   `kucoin_api.py` + snapshot com `account_type="sub:<nome>"` no
   `kucoin_postgres_sync`. Subconta **sub:BTCAgressive** detectada e já
   aparece no gráfico patrimonial (formato longo, linhas dinâmicas por conta),
   no total e no relatório diário.
4. **Snapshots esparsos** — root cause: `kucoin-postgres-sync.timer` morto
   desde o boot de 2026-07-02 (`OnUnitActiveSec` não re-armou); corrigido com
   `OnCalendar=*:00/15` (PR #194) e units versionadas.
5. **Modularização** — aprovada; plano faseado em
   `docs/TRADING_ETH_ACTIVATION_PLAN.md` (seção 2), junto com o plano de
   ativação de ETH-USDT (shadow → validação → live).
