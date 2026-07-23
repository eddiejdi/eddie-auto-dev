# Checklist KuCoin — Pay Fees with KCS + Lealdade (frota RPA4All)

**Data:** 2026-07-19  
**Objetivo:** ligar desconto de ~20% nas taxas spot e (opcional) entrar no nível K1 de lealdade, sem forçar K3/K4.

---

## 0. Contexto da sua frota

| Conta / sub | O que opera | USDT (aprox.) | Base (aprox.) |
|-------------|-------------|---------------|---------------|
| **Master TRADE** | SOL, DOGE, ETH residual, USDT-BRL | ~10 USDT | SOL ~1.39, DOGE ~2393, ETH ~0.033, BRL ~1024 |
| **sub:BTCAgressive** | BTC aggressive | ~15 USDT | BTC ~0.00134 |
| **sub:BTCConservative** | BTC conservative | ~15 USDT | BTC ~0.00055 |
| **sub:ETHAgressive** | ETH aggressive | ~2.4 USDT | ETH ~0.048 |
| **sub:ETHConservative** | ETH conservative | ~15 USDT | ETH ~0.008 |
| **Master MAIN** | pó (AKT/ETH) | — | irrelevante |

- Volume spot ~30d: **~$8k** → taxa estimada **~$6–10/mês** (taker ~0,1%).  
- Economia com KCS Pay **20%**: **~$1,5–2/mês**.  
- **KCS no snapshot atual: zero** (precisa comprar e distribuir).  
- Preço KCS de referência: **~$6,60**.

**Conclusão de alocação:** não maximize nível de lealdade; foque em **Pay Fees with KCS** + **1 KCS staked** (K1) se quiser o programa.

---

## 1. Quanto KCS comprar (recomendado)

### Pacote mínimo (recomendado agora)

| Destino | KCS | ≈ USDT | Para quê |
|---------|----:|-------:|----------|
| Master TRADE | **1,5** | ~10 | fees de SOL/DOGE/USDT-BRL + folga |
| BTCAgressive TRADE | **0,8** | ~5,3 | fees BTC aggressive |
| BTCConservative TRADE | **0,8** | ~5,3 | fees BTC conservative |
| ETHAgressive TRADE | **0,5** | ~3,3 | fees ETH (volume menor) |
| ETHConservative TRADE | **0,6** | ~4,0 | fees ETH conservative |
| **Master → KCS Staking** (opcional K1) | **1,0** | ~6,6 | mínimo do programa de lealdade |
| **Total** | **~5,2 KCS** | **~$35** | |

### Pacote enxuto (se quiser gastar menos)

| Destino | KCS | ≈ USDT |
|---------|----:|-------:|
| Master TRADE | 1,0 | ~6,6 |
| BTCAgressive TRADE | 0,5 | ~3,3 |
| BTCConservative TRADE | 0,5 | ~3,3 |
| ETHAgressive TRADE | 0,3 | ~2,0 |
| ETHConservative TRADE | 0,4 | ~2,6 |
| **Total (sem staking)** | **~2,7 KCS** | **~$18** |

**Regra de ouro:** cada conta que **executa ordem** precisa de KCS no **Trade** (ou Funding da mesma conta, conforme UI). Sem KCS na conta certa, a taxa volta a ser cobrada em USDT/base.

**Recarga:** quando o saldo KCS da conta cair abaixo de **~0,2 KCS**, reabasteça +0,5 KCS.

---

## 2. Checklist — Master (conta principal)

Faça logado como **master** em [kucoin.com](https://www.kucoin.com).

### 2.1 Comprar KCS

- [ ] Transferir **~35 USDT** (pacote mínimo) ou **~18 USDT** (enxuto) para **Trade** do master (se ainda não tiver).
- [ ] Spot: par **KCS/USDT** → market buy do total planejado.
- [ ] Confirmar saldo **KCS** em Assets → Trade (master).

### 2.2 Ativar “Pay Fees with KCS” (master)

**Web:**
- [ ] Avatar (canto superior direito) → **Account / Profile**.
- [ ] Ativar **Pay Fees with KCS** / **Use KCS to pay fees**.
- [ ] Alternativa na tela de trade: **Fee Discounts** (canto do painel) → marcar a opção.

**App:**
- [ ] Ícone pessoal → ativar **Pay Fees with KCS**.

- [ ] Fazer **1 trade mínimo** (ex.: converter 1 USDT em KCS ou micro BTC) e verificar se a fee saiu em **KCS** (histórico de fees / ledger).

### 2.3 (Opcional) Lealdade K1 — stake mínimo

- [ ] Earn / **KCS Staking** (ou KCS Center → Staking).
- [ ] Stake **≥ 1 KCS** (só o mínimo).
- [ ] Confirmar no painel **KCS Loyalty** nível **K1** após o próximo ciclo (~07:00 UTC+8 do dia seguinte).
- [ ] **Não** stake 10%+ do patrimônio só para K4.

---

## 3. Checklist — cada Sub-Account

KuCoin: master e sub **compartilham VIP/KYC**, mas **saldos e “pay with KCS” por conta** precisam estar corretos em cada sub que opera.

Para **cada** sub abaixo, repita:

### Subs ativas

| # | Sub-name | Agente | KCS alvo (mínimo) |
|---|----------|--------|-------------------|
| 1 | `BTCAgressive` | `crypto-agent@BTC_USDT_aggressive` | 0,5–0,8 |
| 2 | `BTCConservative` | `crypto-agent@BTC_USDT_conservative` | 0,5–0,8 |
| 3 | `ETHAgressive` | `crypto-agent@ETH_USDT_aggressive` | 0,3–0,5 |
| 4 | `ETHConservative` | `crypto-agent@ETH_USDT_conservative` | 0,4–0,6 |

### Passos por sub

- [ ] Master → **Account Overview → Sub-Account**.
- [ ] **Transfer** master → sub: enviar **KCS** (não só USDT) para a sub (conta **Trade** da sub).
- [ ] **Login na sub** (ou “Switch / Login as sub” se a UI permitir) **ou** gerenciar fee toggle se disponível no master por sub.
- [ ] Ativar **Pay Fees with KCS** no perfil **daquela sub** (mesmos passos do master).
- [ ] Confirmar: Assets da sub → Trade → **KCS ≥ alvo**.
- [ ] Após o próximo trade do agente, conferir no histórico se `feeCurrency` / ledger usa **KCS**.

> **Nota:** se a UI da sub não mostrar o toggle, a KuCoin às vezes herda do master; mesmo assim o **saldo KCS precisa existir na sub** que debita a taxa.

---

## 4. Contas que NÃO precisam de KCS agora

| Conta | Motivo |
|-------|--------|
| Master MAIN | Só residual; agentes usam TRADE |
| Shadow (se só simula / mesma conta master) | Se shadow for dry-run ou mesma TRADE master, não duplicar |
| SOL/DOGE no master | Já cobertos pelo KCS do **Master TRADE** |

---

## 5. Ordem de execução sugerida (15–20 min)

1. [ ] Comprar KCS no master (pacote mínimo ou enxuto).  
2. [ ] Ativar Pay Fees with KCS no **master**.  
3. [ ] Transferir KCS para as **4 subs** (tabela acima).  
4. [ ] Ativar Pay Fees with KCS em **cada sub**.  
5. [ ] (Opcional) Stake **1 KCS** no master para K1.  
6. [ ] Esperar 1 ciclo de trades dos agentes.  
7. [ ] Validar no histórico de fees: moeda = **KCS**, desconto ~20%.  
8. [ ] Anotar no Telegram/ops: “KCS fee ON master+subs YYYY-MM-DD”.

---

## 6. Validação técnica (homelab)

Depois de um dia de trades:

```sql
-- Fees com moeda KCS nos metadata (quando o agente grava fee_currency)
SELECT to_timestamp(timestamp) AS ts, symbol, profile, side,
       metadata->>'fee_currency' AS fee_ccy,
       metadata->>'fill_fee' AS fee
FROM btc.trades
WHERE dry_run = false
  AND timestamp > EXTRACT(EPOCH FROM NOW()) - 86400
ORDER BY timestamp DESC
LIMIT 30;
```

Ou no exporter / ledger KuCoin: procurar `feeCurrency = KCS`.

Saldos KCS (após o sync de balances passar a enxergar KCS):

```sql
SELECT account_type, currency, balance, synced_at
FROM btc.exchange_balance_snapshots
WHERE currency = 'KCS'
ORDER BY synced_at DESC
LIMIT 20;
```

---

## 7. Alertas / manutenção

| Sinal | Ação |
|-------|------|
| Trade com `feeCurrency=USDT` de novo | KCS esgotado ou toggle off → recarregar KCS |
| Saldo KCS sub &lt; 0,2 | Transferir +0,5 KCS do master |
| KCS price -30% em pouco tempo | Só reavaliar se “Pay with KCS” ainda vale (ainda costuma valer em volume estável) |
| Volume 30d &gt; $50k | Revisar se K2 (1–5% staked) começa a fazer sentido |

---

## 8. O que **não** fazer

- Não stakear 10%+ do portfólio só para K4.  
- Não deixar KCS só no **MAIN** se a ordem debita **TRADE**.  
- Não comprar KCS em volume grande “para o futuro” — recarregue sob demanda.  
- Não misturar: lealdade alta ≠ necessariamente menos fee que “Pay with KCS” ligado.

---

## 9. Resumo 30 segundos

1. Compre **~$20–35** de KCS.  
2. Ligue **Pay Fees with KCS** no master + 4 subs.  
3. Deixe **0,3–0,8 KCS por conta que opera**.  
4. Opcional: **1 KCS staked** = K1.  
5. Ignore “subir lealdade” além disso até o volume crescer.

---

*Documento operacional da frota crypto-agent / KuCoin. Atualizar quantidades se o capital ou volume mudar materialmente.*
