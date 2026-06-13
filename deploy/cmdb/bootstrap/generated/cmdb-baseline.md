# CMDB Baseline

- Generated at: `2026-06-13T14:58:54.679765+00:00`
- Site: `homelab-main`
- Hosts discovered: `1`
- Repo services discovered: `145`
- Critical services flagged for MVP: `59`
- Project: [eddie-auto-dev](https://github.com/eddiejdi/eddie-auto-dev)
- Owner: `edenilson.adm@gmail.com`

## Domain counts

- `identity`: 7
- `monitoring`: 13
- `network`: 16
- `operations`: 83
- `storage`: 23
- `trading`: 3

## NetBox seed candidates

- `homelab` -> role `compute-node`, platform `linux`, ip `192.168.15.2`

## MVP critical services

- `nextcloud` (identity, compose) from `forks/rpa4all-nextcloud-authentik/docker-compose.yml`
- `nextcloud-db` (identity, compose) from `forks/rpa4all-nextcloud-authentik/docker-compose.yml`
- `nextcloud-redis` (identity, compose) from `forks/rpa4all-nextcloud-authentik/docker-compose.yml`
- `open-webui` (identity, compose) from `tools/authentik_management/configs/docker-compose.override.yml`
- `vaultwarden` (identity, compose) from `tools/vaultwarden/docker-compose.yml`
- `homelab-vault-backup.service` (identity, systemd) from `systemd/homelab-vault-backup.service`
- `homelab-vault-close.service` (identity, systemd) from `systemd/homelab-vault-close.service`
- `cadvisor` (monitoring, compose) from `docker/docker-compose-exporters.yml`
- `grafana` (monitoring, compose) from `tools/authentik_management/configs/docker-compose.override.yml`
- `node-exporter` (monitoring, compose) from `docker/docker-compose-exporters.yml`
- `postfix-exporter` (monitoring, compose) from `docker/docker-compose.simple-mail.yml`
- `agent-network-exporter.service` (monitoring, systemd) from `tools/systemd/agent-network-exporter.service`
- `banking-metrics-exporter.service` (monitoring, systemd) from `systemd/banking-metrics-exporter.service`
- `eddie_central_extended_metrics.service` (monitoring, systemd) from `systemd/eddie_central_extended_metrics.service`
- `grafana-selfheal.service` (monitoring, systemd) from `systemd/grafana-selfheal.service`
- `job-monitor.service` (monitoring, systemd) from `systemd/job-monitor.service`
- `monitoring-containers-bootstrap.service` (monitoring, systemd) from `systemd/monitoring-containers-bootstrap.service`
- `rss-sentiment-exporter.service` (monitoring, systemd) from `systemd/rss-sentiment-exporter.service`
- `storj-exporter.service` (monitoring, systemd) from `deploy/storj-exporter.service`
- `tape-component-quality-exporter.service` (monitoring, systemd) from `systemd/tape-component-quality-exporter.service`
- `proxy` (network, compose) from `deploy/cmdb/docker-compose.yml`
- `cloudflared-named@.service` (network, systemd) from `tools/tunnels/cloudflared-named@.service`
- `cloudflared.service` (network, systemd) from `tools/tunnels/cloudflared/cloudflared.service`
- `dhcp-selfheal.service` (network, systemd) from `systemd/dhcp-selfheal.service`
- `homelab-lan-gateway.service` (network, systemd) from `deploy/vpn/homelab-lan-gateway.service`
- `iot-vpn-bypass-watchdog.service` (network, systemd) from `systemd/iot-vpn-bypass-watchdog.service`
- `iot-vpn-bypass-watchdog.timer` (network, systemd) from `systemd/iot-vpn-bypass-watchdog.timer`
- `ipv6-proxy.service` (network, systemd) from `systemd/ipv6-proxy.service`
- `localtunnel@.service` (network, systemd) from `tools/tunnels/localtunnel@.service`
- `pihole-ipv6-dns-fix.service` (network, systemd) from `systemd/pihole-ipv6-dns-fix.service`
- `protonvpn-boot-selfheal.service` (network, systemd) from `systemd/protonvpn-boot-selfheal.service`
- `protonvpn-routing-watchdog-fix.service` (network, systemd) from `deploy/vpn/protonvpn-routing-watchdog-fix.service`
- `protonvpn-routing-watchdog.service` (network, systemd) from `deploy/vpn/protonvpn-routing-watchdog.service`
- `rpa4all-ddns-server.service` (network, systemd) from `deploy/vpn/rpa4all-ddns-server.service`
- `rpa4all-vpn-ddns.service` (network, systemd) from `deploy/vpn-deb/rpa4all-vpn/usr/share/rpa4all-vpn/rpa4all-vpn-ddns.service`
- `wireguard-nat.service` (network, systemd) from `deploy/vpn/wireguard-nat.service`
- `disk-clean.service` (storage, systemd) from `systemd/disk-clean.service`
- `disk-clean.timer` (storage, systemd) from `systemd/disk-clean.timer`
- `disk-spindown.service` (storage, systemd) from `tools/homelab/disk-spindown.service`
- `homelab-disk-backup.service` (storage, systemd) from `tools/backup/homelab-disk-backup.service`

## Serviços anotados manualmente

### `eddie-telegram-bot.service`
- Descrição: Chatbot Telegram do homelab Eddie. Comandos: /relatorio (AI plan + P&L 24h), /btc (status BTC), /trades, /performance, /signal, /cotacao, /trading. Ollama model: phi4-mini. Fonte: /home/homelab/myClaude/telegram_bot.py + btc_trading_agent/telegram_trading.py
- Depende de: `eddie-postgres, ollama.service, specialized-agents-api.service`
- runtime_path: `/home/homelab/myClaude/telegram_bot.py`

### `grafana`
- Descrição: Grafana 12.4.0 via docker-compose.grafana.yml. Backend: PostgreSQL (eddie-postgres, db=grafana). Porta: 3002->3000. SSO via Authentik. URL: https://grafana.rpa4all.com
- Depende de: `eddie-postgres, homelab_monitoring network`
- compose_file: `/home/homelab/docker-compose.grafana.yml`

### `mnt-raid1.mount`
- Descrição: mergerfs union de /mnt/disk1 (sdb1) + /mnt/disk2 (sdc1) + /mnt/disk3 (sda1) em /mnt/raid1. Opção nonempty obrigatória — diretório contém nextcloud/ ao montar. Docker data-root: /mnt/disk1/docker. Ollama models: /mnt/raid1/ollama/models
- fix_applied: `2026-06-12: adicionado nonempty ao fstab; disk1/disk3 precisam estar montados antes`

