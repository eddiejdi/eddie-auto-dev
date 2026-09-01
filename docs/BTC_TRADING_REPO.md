# Agente BTC Trading — repositório separado

O agente não é mais um subprojeto exclusivo do auto-dev.

| O quê | Onde |
| --- | --- |
| Repositório | https://github.com/eddiejdi/homelab-btc-trading |
| Checkout local | `/workspace/homelab-btc-trading` |
| Código do agente | `/workspace/homelab-btc-trading/btc_trading_agent` |
| Runtime no homelab | `/apps/crypto-trader/trading/btc_trading_agent` |

`eddie-auto-dev/btc_trading_agent` é um **symlink** para
`../homelab-btc-trading/btc_trading_agent`. A cópia in-tree foi removida.

Após clonar só o auto-dev:

```bash
scripts/ensure_btc_trading_checkout.sh
```
