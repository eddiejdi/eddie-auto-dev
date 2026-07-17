# Tuya Token Selfheal — Variáveis

Serviço: `tuya-token-selfheal.service` (+ `.timer`, a cada 15 min) — script
`tools/homelab/tuya_token_selfheal.py`, instalado em
`/usr/local/bin/tuya_token_selfheal.py` no homelab (192.168.15.2).

Detecta o refresh token Tuya morto no Home Assistant (0 entidades ativas +
token expirado) e injeta o token vivo do pandaplus-bridge, reiniciando o
container do HA. Métricas em
`/var/lib/prometheus/node-exporter/tuya_token_selfheal.prom` (dashboard
Grafana `tuya-token-selfheal`).

| Variável | Default | Propósito |
|---|---|---|
| `HA_CONTAINER` | `homeassistant` | Nome do container Docker do Home Assistant (mesma semântica do `tuya_token_renewer.py`). |
| `HA_CONFIG_ENTRIES` | `/home/homelab/homeassistant/config/.storage/core.config_entries` | Caminho no host do storage de config entries do HA onde o `token_info` é injetado. |
| `BRIDGE_RUNTIME_TOKENS` | `/var/lib/pandaplus-bridge/tuya_tokens_runtime.json` | Token Tuya renovado persistido pelo pandaplus-bridge (fonte do heal). |
| `STATE_FILE` | `/var/lib/tuya-selfheal/state.json` | Estado persistente do selfheal (contadores e histórico de heals p/ rate limit). |
| `PROM_FILE` | `/var/lib/prometheus/node-exporter/tuya_token_selfheal.prom` | Saída textfile collector das métricas Prometheus. |
| `MAX_HEALS_24H` | `3` | Rate limit de heals por 24h — acima disso o problema é estrutural (reauth QR via `tuya_reauth_via_authentik.py`). |
| `HA_BOOT_WAIT_S` | `300` | Tempo máximo aguardando o HA subir após o restart antes de declarar falha do heal. |
