# Network Selfheal Suite — Variáveis

Suíte criada após a semana de incidentes 11–17/07/2026 (relatório na sessão
de 17/07): flaps crônicos do eth-wan, unit do ProtonVPN dessincronizada do
kernel e IoTs sumindo do WiFi sem detecção.

## ethwan-selfheal.service (`scripts/ethwan_selfheal`)

| Variável | Default | Propósito |
|---|---|---|
| `IFACE` | `eth-wan` | Interface WAN monitorada (USB RTL8153). |
| `CHECK_INTERVAL` | `30` | Intervalo de verificação do carrier (s). Mesmo nome já usado pelo dhcp-selfheal. |
| `LINK_DOWN_GRACE` | `20` | Segundos de link down antes da primeira ação (blips se resolvem sozinhos). |
| `BRINGUP_SCRIPT` | `/usr/local/bin/eth-wan-bringup.sh` | Script de bringup existente, usado como nível 2 da escada. |
| `USB_PORT` | `2-2` | Porta USB do adaptador para unbind/bind (nível 3, max 2/h). |
| `HEAL_COOLDOWN` | `120` | Cooldown mínimo entre quaisquer ações de heal (s). |
| `PROM_FILE` | `/var/lib/prometheus/node-exporter/ethwan_selfheal.prom` | Métricas textfile collector. |

## protonvpn-unit-selfheal.service (`scripts/protonvpn_unit_selfheal`)

| Variável | Default | Propósito |
|---|---|---|
| `UNIT` | `wg-quick@protonvpn.service` | Unit systemd reconciliada com o estado do kernel. |
| `WG_IFACE` | `protonvpn` | Interface WireGuard cujo handshake define "túnel vivo". |
| `WAN_IFACE` | `eth-wan` | Interface usada no teste de internet antes de um restart real. |
| `HANDSHAKE_MAX_AGE` | `600` | Idade máxima (s) do handshake para considerar o túnel saudável. |
| `STATE_DIR` | `/var/lib/protonvpn-unit-selfheal` | Contadores e rate limit (1 restart/h). |
| `PROM_FILE` | `.../protonvpn_unit_selfheal.prom` | Métricas textfile collector. |

## iot-presence-watchdog.service (`tools/homelab/iot_presence_watchdog.py`)

| Variável | Default | Propósito |
|---|---|---|
| `BYPASS_CONF` | `/etc/iot-vpn-bypass.conf` | Fonte dos MACs monitorados (mesma allowlist do bypass VPN). |
| `LEASES_FILE` | `/var/lib/misc/dnsmasq.leases` | Leases DHCP para presença. Mesmo nome já usado pelo dhcp-selfheal. |
| `STATE_FILE` | `/var/lib/iot-presence/state.json` | Estado de transições p/ alertar 1x por evento. |
| `PROM_FILE` | `.../iot_presence.prom` | Métricas por dispositivo (`iot_device_present{mac,ip}`). |
| `ABSENT_ALERT_MIN` | `30` | Minutos ausente antes do alerta Telegram (credenciais via `EnvironmentFile` `/etc/default/eddie-common` — `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`, já catalogadas). |

O watchdog de presença **não executa ação corretiva** — só observa e alerta.
