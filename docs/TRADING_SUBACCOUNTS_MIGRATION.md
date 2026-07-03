# Migração dos perfis para subcontas KuCoin

Iniciada em 2026-07-03. Objetivo: cada perfil de trading opera na própria
subconta, com capital isolado.

## Subcontas (criadas pelo usuário) e mapeamento

| Subconta | UID (UI) | userId (API, para sub_transfer) | Perfil destino | Saldo inicial |
|---|---|---|---|---|
| BTCAgressive | 257506830 | 6a2fe102dc143e00017b48fe | `BTC_USDT_aggressive` | 100 USDT |
| BTCConservative | 257507456 | 6a2fe6f634e4a40001c3a385 | `BTC_USDT_conservative` | 50 USDT |
| ETHAgressive | 258149392 | 6a4849435769ca0001652fdf | `ETH_USDT_aggressive` (futuro) | 50 USDT |
| ETHConservative | 258149464 | 6a484a6d5769ca000165306d | `ETH_USDT_conservative` (futuro) | 50 USDT |

Transferências de 50 USDT executadas em 2026-07-03 via
`kucoin_api.sub_transfer()` (master TRADE → sub TRADE), order IDs no journal.
**Atenção:** o UID da interface não funciona no `sub-transfer` — usar o
`userId` interno de `GET /api/v2/sub/user`.

## Estado transitório (vigente)

- Master trade ficou com ~0,36 USDT + ~0,01 BTC: os agentes BTC (que ainda
  operam no master) **não conseguem abrir novas posições** (starvation), mas
  vendem as posições abertas normalmente (política positive-only).
- **Shadow não tem subconta** — decidir: criar `BTCShadow`, devolver USDT ao
  master, ou pausar o A/B test.

## Como o agente seleciona credenciais (já suportado)

`secrets_helper._iter_kucoin_secret_names()` respeita o env
`KUCOIN_SECRET_NAMES` (lista de secrets, checada antes do default
`kucoin/homelab`). Ou seja, por perfil basta o envfile apontar para o secret
da subconta.

## Passos restantes (bloqueado por ação do usuário)

1. **Usuário**: criar API key em cada subconta (KuCoin → API Management →
   subconta → permissões *General* + *Spot Trading*; mesma whitelist de IP do
   master) e fornecer key/secret/passphrase.
2. Gravar no Secrets Agent (sincroniza com Authentik), um por subconta:
   `kucoin/sub-btcagressive`, `kucoin/sub-btcconservative`,
   `kucoin/sub-ethagressive`, `kucoin/sub-ethconservative` — campos
   `api_key`, `api_secret`, `passphrase`.
3. Por perfil, no envfile (`/apps/crypto-trader/envfiles/<perfil>.env`):
   `KUCOIN_SECRET_NAMES=kucoin/sub-<subconta>`.
4. **Migrar posição aberta antes de trocar a chave**: vender a posição no
   master (ao atingir lucro mínimo) ou `sub_transfer` do BTC para a subconta;
   caso contrário o agente perde acesso à posição (BTC fica no master e a
   nova chave só enxerga a subconta).
5. Reiniciar o perfil migrado (um de cada vez), rodar
   `kucoin-postgres-sync` e conferir reconciliação (`position_diff`) e
   `_detect_external_deposits` (o saldo da subconta não deve ser tratado como
   depósito externo — validar no primeiro boot).
6. Repetir por perfil. ETH segue o plano de ativação
   (`TRADING_ETH_ACTIVATION_PLAN.md`) já nascendo na subconta.

## Observabilidade

- Snapshots por subconta ativos desde 2026-07-03 (`account_type="sub:<nome>"`
  em `btc.exchange_balance_snapshots`, a cada 15 min).
- Dashboard "Evolução Patrimonial por Conta" mostra uma linha por subconta
  automaticamente; relatório diário das 10h idem.
