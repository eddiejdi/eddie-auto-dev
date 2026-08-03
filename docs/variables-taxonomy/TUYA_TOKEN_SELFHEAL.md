# Tuya Token Selfheal — Variáveis

Serviço: `tuya-token-selfheal.service` (+ `.timer`, a cada **5 min**) — script
`tools/homelab/tuya_token_selfheal.py`, instalado em
`/usr/local/bin/tuya_token_selfheal.py` no homelab (192.168.15.2).

Detecta access token Tuya prestes a expirar (ou já expirado) no Home
Assistant, **força refresh proativo** via API Tuya Sharing (o SDK do bridge
só renova com <60s), grava o token em `tuya_tokens_runtime.json` e injeta no
HA preferindo hot-apply (`tuya_token_inject.apply`), com fallback para
`homeassistant.restart` e `docker restart`. Métricas em
`/var/lib/prometheus/node-exporter/tuya_token_selfheal.prom` (dashboard
Grafana `tuya-token-selfheal`).

Complementa (não substitui) o **monitor** `tuya-token-renewer` — ver
[TUYA_TOKEN_RENEWER.md](TUYA_TOKEN_RENEWER.md): aquele job **não** renova e, desde
2026-07-30, manda Telegram **somente em erro** (não no aviso “perto de vencer”).

| Variável | Default | Propósito |
|---|---|---|
| `HA_CONTAINER` | `homeassistant` | Nome do container Docker do Home Assistant (mesma semântica do `tuya_token_renewer.py`). |
| `HA_URL` | `http://127.0.0.1:8123` | Base URL da API local do Home Assistant. |
| `HA_CONFIG_ENTRIES` | `/home/homelab/homeassistant/config/.storage/core.config_entries` | Caminho no host do storage de config entries do HA onde o `token_info` é injetado. |
| `BRIDGE_RUNTIME_TOKENS` | `/var/lib/pandaplus-bridge/tuya_tokens_runtime.json` | Token Tuya renovado (bridge ou selfheal) — fonte do heal. |
| `STATE_FILE` | `/var/lib/tuya-selfheal/state.json` | Estado persistente do selfheal (contadores e histórico de heals p/ rate limit). |
| `PROM_FILE` | `/var/lib/prometheus/node-exporter/tuya_token_selfheal.prom` | Saída textfile collector das métricas Prometheus. |
| `MAX_HEALS_24H` | `24` | Rate limit de heals por 24h — acima disso o problema é estrutural (reauth QR via `tuya_reauth_via_authentik.py`). |
| `HA_BOOT_WAIT_S` | `300` | Tempo máximo aguardando o HA subir após docker restart antes de declarar falha do heal. |
| `TUYA_SELFHEAL_HOT_WAIT_S` | `90` | Tempo máximo (s) aguardando entidades após hot-apply do token (distinto de `HA_BOOT_WAIT_S`, usado no docker restart). |
| `HEAL_SOFT_THRESHOLD_MIN` | `45` | Minutos restantes do access token do HA abaixo dos quais o selfheal renova proativamente e injeta. `0` = só com token já expirado. |
| `TUYA_CLIENT_ID` | `HA_3y9q4ak7g4ephrvke` | Client ID público da integração Tuya do HA core (refresh Sharing API). |
| `TUYA_SHARING_SITE` | `/home/homelab/myClaude/.venv/lib/python3.12/site-packages` | site-packages com `tuya_sharing` (venv do pandaplus-bridge). |
| `PARTIAL_DEGRADED_MIN_MISSING` | `5` | Nº mínimo de entidades faltando (nem 0 ativas, nem token perto de expirar) para considerar degradação parcial — abaixo disso é tratado como blip normal de 1-2 dispositivos offline. |
| `PARTIAL_DEGRADED_STREAK_THRESHOLD` | `3` | Checagens consecutivas (a cada 5 min) com degradação parcial sustentada antes de disparar reload da entry. Descoberto 2026-08-02: sem isso, um caso 72/82 ficou travado ~2h até o próximo refresh proativo coincidir e corrigir por acaso. |
