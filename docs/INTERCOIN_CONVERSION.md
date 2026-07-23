# Conversão Intermoedas (KuCoin) — Owner USDT_BRL

## Objetivo

Converter entre moedas da frota pelo **caminho de menor custo efetivo** (fee + spread + slip), sem substituir os agents `*_USDT` de swing.

## Owner

| Instância | Papel |
|-----------|--------|
| `crypto-agent@USDT_BRL_conservative` | **Owner** — processa fila, on-ramp BRL→USDT, multi-hop |
| `crypto-agent@USDT_BRL_aggressive` | Swing USDT-BRL apenas (`conversion.enabled=false`) |

## Observabilidade

| Item | Valor |
|------|--------|
| Exporter cons/aggr | portas **9115** / **9116** |
| Prometheus jobs | `crypto-exporter-usdt_brl_{conservative,aggressive}` |
| Grafana | Trading Agent Monitor → moeda `USDT-BRL` + row **Intermoedas / Conversão** |

## Config

`btc_trading_agent/config_USDT_BRL_conservative.json` → bloco `conversion`:

- `dry_run: false` (live BRL→USDT on-ramp no owner conservative; fila manual também)
- `max_route_cost_pct: 0.008` (80 bps — USDT-BRL costuma ~30–50 bps)
- `max_spread_bps: 50`
- `onramp_cooldown_seconds: 21600` + `onramp_balance_delta_pct: 5` — evita re-fila a cada ciclo
- `hubs: [USDT, BTC, ETH]`
- `allow_exotic_hubs: false` (bloqueia USD1/KCS como hub)
- `max_hops: 2`

## Fluxo

1. Enfileirar request (CLI ou on-ramp BRL)
2. Owner adquire `btc.conversion_lock`
3. `route_graph.find_best_route` escolhe menor score
4. `hop_executor.execute` (dry_run ou live)
5. Legs em `btc.conversion_legs`; status em `btc.conversion_requests`

## CLI

```bash
# Planejar (read-only, book público)
cd btc_trading_agent
python route_cli.py ETH BTC 0.05
python route_cli.py SOL BTC 1 --json

# Enfileirar para o owner
python tools/request_conversion.py --from ETH --to BTC --amount 0.01
python tools/request_conversion.py --from BRL --to USDT --amount 100
```

## Go-live

1. Confirmar scrape Prometheus e painéis Grafana com dry_run
2. Liberar só BRL↔USDT: `conversion.dry_run=false`, whitelist focada
3. Depois ETH↔BTC 1 hop
4. Dust sweep opcional

## Partial fill

Não há auto-unwind no MVP. Status `partial` + alerta; reconciliar manualmente e limpar dust via fila.

## Isolamento

Fills de conversão **não** devem alimentar `position_reconstruction` dos agents de swing (fonte em `conversion_*`, não em entries de strategy).
