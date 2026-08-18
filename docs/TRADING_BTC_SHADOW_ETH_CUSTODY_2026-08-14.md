# BTC shadow — tombamento da custódia ETH conservative

**Data:** 2026-08-14  
**Wiki:** `/trading/btc-shadow-eth-conservative-custody`  
**Intent:** `intent-20260814-140220-d5a5a0` (aprovado @Eddiejdi, done 14:05 UTC)

Sem conta KuCoin nova. Sem sell. O lote ETH **3794** ficou na subconta.

## Por que

O BTC shadow via `equity=$0` no `buy_max_exposure`: o JSON tinha `kucoin_subaccount_name=BTCAgressive` e o envfile `KUCOIN_SECRET_NAMES=kucoin/sub-btcagressive` (a mesma key do aggressive). `_read_subaccount_spot_balances` chama `/sub-accounts` com key de subconta → lista vazia → cap $0.

Não havia secret `kucoin/sub-btcshadow`. A pior carteira **dedicada** reutilizável era a do ETH conservative (`kucoin/sub-ethconservative`). USDT-BRL conservative tem pior PnL, mas a key é `kucoin/homelab` (master) — não doável.

## O que mudou (prod)

| Item | Antes | Depois |
| --- | --- | --- |
| `/apps/crypto-trader/envfiles/BTC_USDT_shadow.env` | `kucoin/sub-btcagressive` | **`kucoin/sub-ethconservative`** |
| `config_BTC_USDT_shadow.json` | `kucoin_subaccount_name=BTCAgressive` | **chave removida** |
| `crypto-agent@BTC_USDT_shadow` | PID 2569676 | **1791881** |
| Credencial no boot | sub-btcagressive | **`kucoin/sub-ethconservative`** (`6a48569a…8b5f`) |
| `crypto-agent@ETH_USDT_conservative` | active/enabled | **inactive + disabled** (depois do restart do shadow) |

Ordem: config → restart **só** shadow → conferir `USDT=$30` → **então** stop+disable ETH conservative.

Intacto: BTC conservative/aggressive, ETH aggressive, ETH shadow.

## Estado da carteira

- USDT livre ~**$30** (RAG do shadow no boot).
- ETH **3794** 0,007657 @ $1.957 (27/07) — órfão; o BTC shadow **não** gere ETH.
- Sem posição BTC no restore (`Last trade was sell — no open position`).

## Comprou BTC depois do tombamento?

**Não** (checagem ~14:48 UTC).

| Desde 14:03 UTC | Valor |
| --- | --- |
| Fills BTC-USDT shadow | **0** |
| Decisões BUY | **0** |
| HOLD / SELL (não executado) | 337 / 26 |
| `buy_max_exposure` / `equity=$0` | **0** |

Último fill shadow BTC continua **07/08** (3852, já closed). O modelo só HOLD/SELL; alvo de compra da IA (~$62.1k) está abaixo do spot (~$62.7k). O bug de equity=0 **não** é o bloqueio atual.

## Relacionado

- [Slots fantasma e shared-balance](https://wiki.rpa4all.com/pt/trading/trading-btc-phantom-and-shared-balance)
- SQL 3889/3891 → `matched_sell` (3897/3896); 3907 segue aberto no aggressive.
