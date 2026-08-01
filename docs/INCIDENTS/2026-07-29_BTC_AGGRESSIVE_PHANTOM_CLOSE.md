# Incidente — Phantom-close de posições no BTC Trading Agent (profile aggressive)

| Campo | Valor |
|-------|--------|
| Data | 2026-07-29 |
| Severidade | Alta (trading com dinheiro real, bloqueio de novas entradas) |
| Área | BTC Trading Agent — KuCoin (profile aggressive, subconta BTCAgressive) |
| Status | **Resolvido** |
| Runbook | [reference_trading_agent_location.md] (memória) — 192.168.15.2:/apps/crypto-trader |

## Sintoma

Usuário reportou "Agente(s) parado(s): BTC USDT aggressive". Ao investigar,
o agente estava na verdade rodando, mas com **20 posições abertas há dias
sem sinal de venda** e sem novas entradas, apesar da IA sinalizar regime
`RANGING` normalmente. Um restart do serviço fez as 20 posições **desaparecerem**
do banco (contagem foi para zero), levantando suspeita de perda de dados.

## Causa raiz

`get_balance()` em `kucoin_api.py` consulta saldo via
`GET /api/v1/accounts`, que retorna **apenas o saldo da conta MASTER** da
KuCoin. O profile `aggressive` opera fisicamente na **subconta
`BTCAgressive`** (KuCoin tem limite de subcontas, então múltiplos pares/
profiles compartilham a mesma subconta por moeda).

No bootstrap do agente (`trading_agent.py`), o guardrail de
"phantom accumulation" compara o saldo real na exchange com as posições
abertas no PostgreSQL:

```python
real_balance = get_balance(base_currency)   # só via conta MASTER
if real_balance < _MIN_TRADEABLE:
    # fecha todas as posições abertas no DB — "balance_zero_on_restore"
```

Como `get_balance()` nunca olha subcontas, o agente via **saldo master ≈ 0**
mesmo com **0.00300063 BTC (~$186) reais na subconta `BTCAgressive`**, e
concluía (erroneamente) que as 20 posições no DB eram "fantasma", fechando
todas a cada restart. Isso não só apagava o histórico de posição como
**bloqueava novas compras**: o cálculo de risco via 100% do capital
"alocado" (mesmo sem saldo real disponível) e recusava novos BUYs.

O script `kucoin_postgres_sync.py` já tinha a lógica correta
(`get_sub_account_balances()` agregando master + subcontas) para seu
próprio check de integridade — mas o bootstrap do `trading_agent.py`
usava um caminho de código diferente e desatualizado.

### Achado colateral: processo duplicado

Durante a investigação, um restart em `crypto-agent@aggressive.service`
(nome de unit legado, sem símbolo — não faz parte do `deploy_profiles.sh`
oficial) criou um **segundo processo concorrente** operando na mesma
config/subconta que `crypto-agent@BTC_USDT_aggressive.service` (o processo
de produção real, ativo desde 2026-07-28). Nenhum trade duplicado ou
corrupção de dados ocorreu na janela de ~25 min de operação simultânea
(regime `RANGING`, sem sinais de entrada), mas o unit legado foi parado
para eliminar o risco.

## Correção

1. **`kucoin_api.py`**: nova função `get_balance_with_subaccounts(currency)`
   que agrega saldo da conta master + todas as subcontas (`trade` type),
   reaproveitando `get_sub_account_balances()` já validado no sync script.
2. **`trading_agent.py`**: bootstrap do guardrail de phantom-close agora
   chama `get_balance_with_subaccounts(base_currency)` em vez de
   `get_balance(base_currency)`.
3. Backup dos arquivos originais: `*.bak.gapfix_20260729_103229`
   (repo `/apps/crypto-trader` não é git — ver Prevenção).
4. Posições fechadas incorretamente (`closed_reason=balance_zero_on_restore`)
   restauradas para `status=open` via correção manual no PostgreSQL.
5. Unit legado `crypto-agent@aggressive.service` parado; apenas as
   instâncias oficiais `crypto-agent@BTC_USDT_{profile}.service`
   permanecem ativas.
6. Fix validado em produção nos três profiles (`aggressive`,
   `conservative`, `shadow`) — nenhum disparou phantom-close nos
   restarts pós-fix; saldo agregado corretamente reportado
   (ex: exchange=0.00277313 BTC vs master-only=0.00000149 BTC).

## Validação pós-fix

Métrica do exporter Prometheus (`crypto-exporter@BTC_USDT_aggressive`,
porta 9095 — mesma fonte usada pelo dashboard Grafana
`btc-trading-monitor.json`) confere com o estado interno do agente:

```
btc_trading_open_position_btc{profile="aggressive"}   0.00046427
btc_trading_open_position_usdt{profile="aggressive"}  29.97
btc_trading_open_position_raw_entries{profile="aggressive"} 2
```

Esse valor é o mesmo reportado antes do incidente — confirma que
nenhum dado de posição real foi perdido; o bug era de bookkeeping
(campo `status` no Postgres), não de execução de ordens. Dashboards
não mostram diferença visível porque o exporter sempre consultou o
estado ao vivo (nunca ficou com cache stale) e nenhuma operação de
mercado ocorreu durante o incidente (regime `RANGING`).

## Prevenção

- Qualquer checagem de saldo usada para decisões de guardrail/segurança
  deve usar `get_balance_with_subaccounts()`, nunca `get_balance()` puro,
  em contas com múltiplos profiles/subcontas compartilhadas.
- `kucoin_postgres_sync.py` detecta `Position mismatch` a cada 15 min mas
  **não corrige automaticamente** — considerar ação corretiva automática
  ou alerta Telegram quando `position_diff` persistir por N ciclos.
- Usar sempre os nomes de unit oficiais do `deploy_profiles.sh`
  (`crypto-agent@{SYMBOL}_{profile}.service`); units legados sem símbolo
  (`crypto-agent@aggressive.service`) não devem ser reiniciados — considerar
  removê-los do `crypto-agent@.service` template ou adicionar guard.
- `/apps/crypto-trader` não está sob controle de versão git — mudanças em
  produção dependem de backups `.bak.*` manuais. Recomenda-se inicializar
  git no diretório para rastreabilidade (fora do escopo deste incidente).
