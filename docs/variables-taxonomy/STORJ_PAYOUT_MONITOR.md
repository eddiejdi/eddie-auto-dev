# Storj Payout Monitor — Variáveis

Serviço: `storj-payout-monitor.service` (+ `.timer`, a cada **30 min**) —
script `tools/homelab/storj_payout_monitor.py`, instalado em
`/usr/local/bin/storj_payout_monitor.py` no homelab (192.168.15.2).

Inclui também `tools/homelab/storj_withdraw.py` (`/usr/local/bin/storj_withdraw.py`)
— ferramenta de **uso manual apenas** (nunca chamada por systemd), que lê o
plano de retirada em `--dry-run`; ver `docs/storj-withdrawal-runbook.md`.

Detecta quando o saldo "disposed" (liberado, cumulativo) do payout Storj
aumenta — a Storj retém pagamentos por ~2 períodos antes de liberá-los como
saldo gasto na carteira do nó — e dispara alerta via Telegram. Somente
leitura: não tem acesso a nenhuma chave privada nem move fundos. Métricas em
`/var/lib/prometheus/node-exporter/storj_payout_monitor.prom`.

| Variável | Default | Propósito |
|---|---|---|
| `STORJ_API_BASE` | `http://127.0.0.1:14002/api` | Base URL da API local do storagenode (held-history/paystubs). |
| `STORJ_WALLET_ADDRESS` | `0x4787E8bA11d9D32f8A51336a1844e663105a7d24` | Endereço da carteira de payout do nó (zkSync-era), configurado no container via `WALLET=`. |
| `ZKSYNC_EXPLORER_BASE` | `https://block-explorer-api.mainnet.zksync.io` | Block explorer público do zkSync-era usado para ler saldo STORJ on-chain (somente leitura). |
| `COINGECKO_PRICE_URL` | `https://api.coingecko.com/api/v3/simple/price?ids=storj&vs_currencies=usd` | Endpoint público para preço STORJ/USD (usado só para enriquecer o texto do alerta). |
| `STORJ_PAYOUT_STATE_FILE` | `/var/lib/storj-payout-monitor/state.json` | Estado persistente (último disposed_total/saldo/contador de alertas) para não re-alertar o mesmo delta. |
| `PROM_FILE` | `/var/lib/prometheus/node-exporter/storj_payout_monitor.prom` | Saída textfile collector das métricas Prometheus. |
| `STORJ_ALERT_THRESHOLD_USD` | `20` | Delta mínimo (USD) de saldo recém-liberado para disparar alerta Telegram. |
| `STORJ_PAYOUT_HTTP_TIMEOUT` | `15` | Timeout (s) das chamadas HTTP feitas pelo monitor. |
| `SECRETS_AGENT_API_KEY` | (via `EnvironmentFile=-/etc/crypto-agent/secrets-api.env`) | Chave de API do secrets agent local — reaproveitada do mesmo arquivo já usado pelo trading agent (só a API key, nada de segredo específico de trading). |
| `SECRETS_AGENT_URL` | `http://127.0.0.1:8088` | Base URL do secrets agent local. |
| `KUCOIN_API_DIR` | (auto-detectado: `/apps/crypto-trader/trading/btc_trading_agent`, `/apps/crypto-trader/btc_trading_agent`, `/home/homelab/myClaude/btc_trading_agent`, nessa ordem) | Diretório onde `storj_withdraw.py` (uso manual) encontra `kucoin_api.py` para reaproveitar autenticação — o script roda standalone em `/usr/local/bin`, fora do checkout do repo, então o caminho não pode ser derivado de `__file__`. |
