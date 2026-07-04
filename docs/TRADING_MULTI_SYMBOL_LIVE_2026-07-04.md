# Trading multi-símbolo em produção — BTC + ETH live em subcontas

Consolidação das mudanças de 2026-07-03/04 (PRs #190 a #203). Continuação de
`TRADING_AGENT_REVIEW_2026-07-03.md`; detalhes operacionais em
`TRADING_SUBACCOUNTS_MIGRATION.md` e `TRADING_ETH_ACTIVATION_PLAN.md`.

## 1. Estado final da frota (2026-07-04)

| Perfil | Modo | Conta KuCoin | Capital inicial | Exporter | Credencial |
|---|---|---|---|---|---|
| BTC_USDT_conservative | LIVE | sub:BTCConservative | $50 + posição BTC | 9094 | `kucoin/sub-btcconservative` |
| BTC_USDT_aggressive | LIVE | sub:BTCAgressive | $100 | 9095 | `kucoin/sub-btcagressive` |
| BTC_USDT_shadow | LIVE | master (A/B test) | ~$10 compartilhado | 9099 | `kucoin/homelab` |
| ETH_USDT_conservative | LIVE | sub:ETHConservative | $50 | 9097 | `kucoin/sub-ethconservative` |
| ETH_USDT_aggressive | LIVE | sub:ETHAgressive | $50 | 9098 | `kucoin/sub-ethagressive` |
| ETH_USDT_shadow | LIVE | master (A/B test) | ~$10 compartilhado | 9096 | `kucoin/homelab` |

Todos com guardrails **positive-only** (nunca vender no prejuízo; mínimo 0,3%
líquido nos conservative/aggressive, 1% nos shadow), `max_daily_loss`,
circuit breaker e rebuy guard. `dry_run=false` em 6/6 por ordem do usuário
(2026-07-04 — a Fase B de validação dry do ETH foi encurtada; risco ETH
limitado aos $100 das subcontas).

## 2. Telegram (PRs #190, #192, #193)

- **Grupo exclusivo "BTC Trade Agent"** — chat `-1004434951297` (o ID inicial
  `-5517772551` migrou no upgrade para supergrupo). Recebe: notificações de
  ordem (🟢/🔴), alertas do agente e o relatório diário. Envfiles:
  `TRADING_TELEGRAM_CHAT_ID`; report: chat fixado no `ExecStart` via
  `/usr/bin/env` (EnvironmentFile do eddie-common sobrepõe `Environment=`).
- **Relatório diário de balanço às 10:00 BRT** (`trading-daily-report.timer`,
  versionado): balanço por conta (main/trade/subcontas, USDT e R$), token
  canônico de `/etc/default/eddie-common` (o `.env` do myClaude causava
  `InvalidToken` silencioso **todo dia** desde sempre), `num_predict=4096`
  (modelos reasoning gastavam o orçamento no `<think>` e truncavam a
  mensagem), balanço anexado deterministicamente se o LLM omitir.

## 3. Subcontas e credenciais (PRs #196, #197)

- 4 subcontas criadas pelo usuário e fundeadas com 50 USDT cada via
  `kucoin_api.sub_transfer()` (novo). **Armadilha**: o endpoint
  `/api/v2/accounts/sub-transfer` exige o `userId` interno de
  `/api/v2/sub/user`, não o UID da interface ("User not found").
- Posição aberta do conservative (0.00015964 BTC) transferida ANTES da troca
  de chave; restaurada 1:1 no restart sem falso depósito externo.
- Credenciais por subconta no Secrets Agent (`kucoin/sub-*`: api_key,
  api_secret, passphrase) com sync no Authentik; seleção por perfil via
  `KUCOIN_SECRET_NAMES` no envfile (mecanismo que já existia no
  secrets_helper).
- **Passphrases recuperadas do Bitwarden do usuário** por automação: a conta
  usa verificação de novo dispositivo por e-mail (não é 2FA; `--method/--code`
  não funcionam) → pexpect no prompt `Enter OTP` + leitura do código via
  token Gmail do homelab (`myClaude/gmail_data/token.json`). Fluxo registrado
  na memória `feedback-bw-gmail-otp-flow`.
- **Bug latente corrigido no secrets agent** (PR #197): o search da API de
  providers do Authentik só indexa `name`; buscar por `client_id` retornava 0
  e todo UPDATE de secret caía em CREATE → `400 already exists` silencioso
  (vault local OK, Authentik desatualizado). Corrigido em get/fields/upsert/
  delete.
- `DATABASE_URL` removido do drop-in `crypto-agent@` (resolvido via
  `shared/database_url` no Authentik). `TELEGRAM_BOT_TOKEN` inline no drop-in
  e credenciais master nos envfiles seguem como candidatos a limpeza.

## 4. ETH: da Fase A ao live (PRs #199–#203)

Linha do tempo (2026-07-03 23h → 2026-07-04 08h):

1. **Fase A**: `ETH_USDT_shadow` dry (config força `dry_run=true` mesmo com
   `--live` do template), exporter 9096, scrape job. Em ~10h de simulação:
   19 compras dry, 12 entradas, avg $1.755,76 — guardrails segurando as
   vendas abaixo de 1% e o rebuy guard exigindo -1% para DCA (comportamento
   correto; "não negociou" era só invisibilidade do dry no dashboard, que
   filtra `dry_run=false`).
2. **Notícias por moeda** (PR #200): as 9 queries de `btc.news_sentiment` no
   agente eram `coin IN ('BTC','GENERAL')` fixo; agora derivam da moeda do
   símbolo (`_news_coin`), e o ranking de fontes confiáveis compara o preço
   do próprio símbolo (era `BTC-USDT` hardcoded). A coleta RSS já era
   multi-moeda.
3. **Exporter multi-símbolo** (PR #201): `_fetch_exchange_balances` usava
   `get_balance("BTC")` fixo — no agente ETH misturava saldo BTC do master
   com preço do ETH (unrealized fantasma de ~$9). Agora usa a moeda-base.
4. **Live** (PRs #202, #203): conservative primeiro (primeira ordem real em
   ~30s: BUY $10 @ $1.757,55, order `6a48e90c...`), depois aggressive e flip
   do shadow — frota 6/6 em modo real.

## 5. Infra corrigida no caminho

- `kucoin-postgres-sync.timer` morto desde o boot pós-queda de 2026-07-02
  (`OnUnitActiveSec` não re-arma) → `OnCalendar=*:00/15` (PR #194); units
  versionadas. Snapshots de saldo voltaram a ~96/dia; subcontas aparecem como
  `account_type="sub:<nome>"`.
- Painel "Evolução Patrimonial por Conta" em formato longo (time/metric/
  value): linha por conta dinâmica — main, trade, cada `sub:*`, BTC, USDT e
  Total.
- Advisory lock em `_ensure_schema` (deadlock quando os perfis reiniciam
  juntos) — PR #184, validado em produção nos restarts em massa.

## 6. Riscos aceitos e pendências

1. **Fase B do ETH encurtada** por decisão do usuário — validação virou
   observação em produção com capital limitado ($100 ETH).
2. **Shadows dividem ~$10 no master** — starvation frequente; opção: criar
   subs BTCShadow/ETHShadow.
3. **Credenciais master inline nos envfiles** (fallback não usado) e
   `TELEGRAM_BOT_TOKEN` no drop-in — limpeza pendente.
4. **APIs de subconta com IP Irrestrito** — restringir ao IP de saída do
   homelab; opcionalmente regenerar as chaves que passaram pelo chat.
5. **Modularização do trading_agent.py** (plano na seção 2 do
   `TRADING_ETH_ACTIVATION_PLAN.md`) — aprovada, não iniciada.
6. Falha pré-existente em `test_rss_sentiment_exporter::test_gpu1_timeout_usa_gpu0`
   (fallback GPU) — não relacionada às mudanças; investigar.
7. Sync detectou 38 *orphan trades* e *position mismatch* de 0,0015 BTC no
   master — reconciliação futura.
