# CMDB Baseline

- Generated at: `2026-07-12T19:59:08.025406+00:00`
- Site: `homelab-main`
- Hosts discovered: `1`
- Repo services discovered: `174`
- Critical services flagged for MVP: `69`
- Project: [eddie-auto-dev](https://github.com/eddiejdi/eddie-auto-dev)
- Owner: `edenilson.adm@gmail.com`

## Domain counts

- `identity`: 4
- `monitoring`: 17
- `network`: 16
- `operations`: 96
- `storage`: 32
- `trading`: 9

## Trading profile instances (`12`)

- `BTC_USDT_aggressive` → `BTC-USDT` / `aggressive` (live, metrics `:9095`) — `master TRADE (kucoin/homelab)`
- `BTC_USDT_conservative` → `BTC-USDT` / `conservative` (live, metrics `:9094`) — `master TRADE (kucoin/homelab)`
- `BTC_USDT_shadow` → `BTC-USDT` / `shadow` (live, metrics `:9099`) — `subconta (BTCAgressive)`
- `DOGE_USDT_aggressive` → `DOGE-USDT` / `aggressive` (live, metrics `:9114`) — `master TRADE (kucoin/homelab) — mesma conta do SOL`
- `DOGE_USDT_conservative` → `DOGE-USDT` / `conservative` (live, metrics `:9113`) — `master TRADE (kucoin/homelab) — mesma conta do SOL`
- `DOGE_USDT_shadow` → `DOGE-USDT` / `shadow` (live, metrics `:9112`) — `master TRADE (kucoin/homelab) — mesma conta do SOL`
- `ETH_USDT_aggressive` → `ETH-USDT` / `aggressive` (live, metrics `:9098`) — `subconta sub:ETHAgressive via KUCOIN_SECRET_NAMES`
- `ETH_USDT_conservative` → `ETH-USDT` / `conservative` (live, metrics `:9097`) — `subconta sub:ETHConservative ($50) via KUCOIN_SECRET_NAMES`
- `ETH_USDT_shadow` → `ETH-USDT` / `shadow` (live, metrics `:9096`) — `subconta (BTCAgressive)`
- `SOL_USDT_aggressive` → `SOL-USDT` / `aggressive` (live, metrics `:9106`) — `master TRADE (kucoin/homelab) — KuCoin não permite novas subcontas`
- `SOL_USDT_conservative` → `SOL-USDT` / `conservative` (live, metrics `:9104`) — `master TRADE (kucoin/homelab) — KuCoin não permite novas subcontas`
- `SOL_USDT_shadow` → `SOL-USDT` / `shadow` (live, metrics `:9108`) — `master TRADE (kucoin/homelab) — KuCoin não permite novas subcontas`

## NetBox seed candidates

- `homelab` -> role `compute-node`, platform `linux`, ip `192.168.15.2`

## MVP critical services

- `open-webui` (identity, compose) from `tools/authentik_management/configs/docker-compose.override.yml`
- `vaultwarden` (identity, compose) from `tools/vaultwarden/docker-compose.yml`
- `homelab-vault-backup.service` (identity, systemd) from `systemd/homelab-vault-backup.service`
- `homelab-vault-close.service` (identity, systemd) from `systemd/homelab-vault-close.service`
- `cadvisor` (monitoring, compose) from `docker/docker-compose-exporters.yml`
- `grafana` (monitoring, compose) from `tools/authentik_management/configs/docker-compose.override.yml`
- `node-exporter` (monitoring, compose) from `docker/docker-compose-exporters.yml`
- `postfix-exporter` (monitoring, compose) from `docker/docker-compose.simple-mail.yml`
- `prometheus` (monitoring, compose) from `docker/docker-compose.grafana.yml`
- `agent-network-exporter.service` (monitoring, systemd) from `tools/systemd/agent-network-exporter.service`
- `banking-metrics-exporter.service` (monitoring, systemd) from `systemd/banking-metrics-exporter.service`
- `eddie_central_extended_metrics.service` (monitoring, systemd) from `systemd/eddie_central_extended_metrics.service`
- `grafana-selfheal.service` (monitoring, systemd) from `systemd/grafana-selfheal.service`
- `job-monitor.service` (monitoring, systemd) from `systemd/job-monitor.service`
- `monitoring-containers-bootstrap.service` (monitoring, systemd) from `systemd/monitoring-containers-bootstrap.service`
- `monitoring-containers-bootstrap.timer` (monitoring, systemd) from `systemd/monitoring-containers-bootstrap.timer`
- `prometheus-selfheal.service` (monitoring, systemd) from `systemd/prometheus-selfheal.service`
- `rss-sentiment-exporter.service` (monitoring, systemd) from `systemd/rss-sentiment-exporter.service`
- `storj-exporter.service` (monitoring, systemd) from `deploy/storj-exporter.service`
- `tape-component-quality-exporter.service` (monitoring, systemd) from `systemd/tape-component-quality-exporter.service`
- `trading-selfheal-exporter.service` (monitoring, systemd) from `systemd/trading-selfheal-exporter.service`
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

## Serviços anotados manualmente

### `eddie-telegram-bot.service`
- Descrição: Chatbot Telegram do homelab Eddie com suporte a comandos de trading, AI, mídia e administração.
- Depende de: `eddie-postgres, ollama.service, specialized-agents-api.service`
- source: `deploy/cmdb/bootstrap/cmdb-agent-overrides.json`
- runtime_path: `/home/homelab/myClaude/telegram_bot.py`
- venv: `/home/homelab/myClaude/.venv`
- env_file: `/etc/default/eddie-common`
- commands: `{'trading': {'/relatorio': 'Relatório completo: planejamento AI por perfil (últimas 2h) + P&L 24h + posições abertas. Fonte: btc.ai_plans + btc.trades via psycopg2.', '/btc': 'Status resumido: preço KuCoin + métricas 7d (trades, win rate, PnL) + último trade.', '/trades [N]': 'Últimos N trades (default 5, max 20) com side, size, price, pnl e perfil.', '/performance': 'Estatísticas de sells nos últimos 7 dias: total, vencedores, win rate, PnL total e médio.', '/signal': 'Último sinal AI da btc.decisions: ação, confiança, preço, executado, motivo.', '/cotacao [par]': 'Cotação em tempo real via KuCoin API pública. Aceita: BTC, AKT, USDT-BRL, BTC/USDT. Resolve base → quotes [BRL, USDT, USDC].', '/trading [pergunta]': 'Interface de linguagem natural: roteado para cotacao/trades/performance/signal/status.'}, 'ai_chat': {'mensagem livre': 'Conversa com Ollama (phi4-mini) com contexto de sessão.', '/use [modelo]': 'Troca o modelo Ollama da sessão.', '/models': 'Lista modelos disponíveis no Ollama.', '/profiles': 'Lista perfis de AI configurados.', '/profile [nome]': 'Muda o perfil de AI da sessão.', '/clear': 'Limpa histórico da sessão.', '/ask [pergunta]': 'Pergunta direta ao AI sem contexto de sessão.', '/code [descrição]': 'Assistente de código.', '/agents': 'Lista agentes especializados disponíveis.', '/project': 'Informações do projeto atual.', '/run [cmd]': 'Executa comando via agente.'}, 'autodev': {'/autodev': 'Status do modo auto-desenvolvimento.', '/autodev_list': 'Lista tarefas de auto-dev pendentes.', '/autodev_test': 'Executa testes de auto-dev.', '/autodev_on': '(admin) Habilita auto-dev.', '/autodev_off': '(admin) Desabilita auto-dev.'}, 'media': {'/x [url]': 'Baixa texto e mídia de posts do Twitter/X e envia no Telegram.', '/photo': 'Envia foto.', '/doc': 'Envia documento.'}, 'system': {'/start': 'Mensagem de boas-vindas.', '/help': 'Lista todos os comandos disponíveis.', '/status': 'Status do bot e serviços do homelab.', '/id': 'Mostra chat_id e user_id.', '/me': 'Informações do usuário.'}, 'admin_only': {'/send': 'Envia mensagem para outro chat.', '/broadcast': 'Broadcast para todos os usuários.', '/ban /unban': 'Banir/desbanir usuário.', '/pin /unpin': 'Fixar/desafixar mensagem.', '/invite /title': 'Gerenciamento de grupo.'}, 'integrations_disabled': {'/calendar': 'Google Calendar (módulo não instalado).', '/gmail': 'Gmail (módulo não instalado).', '/onde /location': 'Localização (módulo não instalado).', '/casa /luzes': 'Home Assistant (módulo não instalado).', '/search': 'Busca web (módulo não instalado).'}}`
- token_management: `{'active_token_id': '1105143633', 'token_source': 'authentik/eddie/telegram_bot_token (local_vault via secrets agent)', 'apply_script': '/usr/local/bin/eddie-apply-telegram-token.sh', 'apply_script_repo': 'scripts/automation/eddie-apply-telegram-token.sh', 'rotation_script': '/home/homelab/telegram_botfather_rotate_selenium.py', 'rotation_script_repo': 'scripts/automation/telegram_botfather_rotate_selenium.py', 'rotation_runbook': 'docs/TELEGRAM_BOT_ROTATION_RUNBOOK.md', 'last_rotation': '2026-06-14', 'notes': 'Token canônico SEMPRE via secrets agent. Nunca hardcodado. Após rotação verificar getMe + Authentik.'}`
- fixes_applied: `['2026-06-13: psycopg2-binary instalado em /home/homelab/myClaude/.venv', '2026-06-13: DATABASE_URL adicionado ao /etc/default/eddie-common', '2026-06-13: get_trades/performance/signal migrados de TrainingDatabase para psycopg2 direto', '2026-06-13: get_quote implementado via KuCoin API pública (sem auth)', '2026-06-13: ROUND(double precision) corrigido para ROUND(expr::numeric) no SQL de posições', '2026-06-14: apply script reescrito — agora persiste token no Authentik via POST /secrets (commit 22f73963)', '2026-06-14: grep -hoP corrigido (sem -h prefixava filename: ao extrair SECRETS_AGENT_API_KEY) (commit 23dfedf9)', '2026-06-14: suporte a --token-file no apply script para evitar expansão bash prematura de {token_file}']`

### `grafana`
- Descrição: Grafana 12.4.0 via docker-compose.grafana.yml. Backend: PostgreSQL (eddie-postgres, db=grafana). Porta: 3002->3000. SSO via Authentik. URL: https://grafana.rpa4all.com
- Depende de: `eddie-postgres, homelab_monitoring network`
- source: `deploy/cmdb/bootstrap/cmdb-agent-overrides.json`
- compose_file: `/home/homelab/docker-compose.grafana.yml`

### `mnt-raid1.mount`
- Descrição: mergerfs union de /mnt/disk1 (sdb1) + /mnt/disk2 (sdc1) + /mnt/disk3 (sda1) em /mnt/raid1. Opção nonempty obrigatória — diretório contém nextcloud/ ao montar. Docker data-root: /mnt/disk1/docker. Ollama models: /mnt/raid1/ollama/models
- source: `deploy/cmdb/bootstrap/cmdb-agent-overrides.json`
- fix_applied: `2026-06-12: adicionado nonempty ao fstab; disk1/disk3 precisam estar montados antes`

### `eddie-apply-telegram-token.sh`
- Descrição: Script de aplicação de token Telegram: grava /etc/eddie/telegram.env, cria drop-ins systemd e persiste em Authentik via secrets agent.
- source: `deploy/cmdb/bootstrap/cmdb-agent-overrides.json`
- type: `script`
- path: `/usr/local/bin/eddie-apply-telegram-token.sh`
- repo: `scripts/automation/eddie-apply-telegram-token.sh`
- usage: `['eddie-apply-telegram-token.sh <TOKEN>', 'eddie-apply-telegram-token.sh --token-file <path>']`
- services_updated: `['eddie-telegram-bot', 'eddie-expurgo', 'eddie-calendar', 'homelab-dashboard', 'eddie-location']`
- authentik_paths: `['authentik/eddie/telegram_bot_token', 'shared/telegram_bot_token']`
- last_updated: `2026-06-14`
- commits: `['22f73963', '23dfedf9']`

### `telegram_botfather_rotate_selenium.py`
- Descrição: Script Selenium que rotaciona o token do bot Telegram via BotFather. Usa Chrome headless + Squid proxy + chromedriver146.
- source: `deploy/cmdb/bootstrap/cmdb-agent-overrides.json`
- type: `script`
- path: `/home/homelab/telegram_botfather_rotate_selenium.py`
- repo: `scripts/automation/telegram_botfather_rotate_selenium.py`
- bot_username: `Proj_Terminal_bot`
- chromedriver: `/home/homelab/.local/bin/chromedriver146`
- chrome_binary: `/opt/google/chrome/chrome`
- profile_archive: `/home/homelab/telegram_userdata_bundle.tar.gz`
- proxy: `http://localhost:3128 (Squid → ProtonVPN)`
- post_rotate_cmd: `/usr/local/bin/eddie-apply-telegram-token.sh --token-file {token_file}`
- runbook: `docs/TELEGRAM_BOT_ROTATION_RUNBOOK.md`
- features_added: `['--extra-chrome-arg (2026-06-14): permite passar proxy ao Chrome headless']`

### `wikijs`
- Descrição: Wiki.js v2 — documentação técnica do homelab. Docker: ghcr.io/requarks/wiki:2. DB: wikijs-db (postgres:15-alpine).
- source: `deploy/cmdb/bootstrap/cmdb-agent-overrides.json`
- type: `docker-compose`
- container: `wikijs`
- port_host: `3009`
- port_container: `3000`
- url: `http://192.168.15.2:3009`
- graphql: `http://192.168.15.2:3009/graphql`
- token_drop_in: `/etc/systemd/system/specialized-agents-api.service.d/wiki-token.conf`
- wiki_agent_port: `8503`
- known_pages: `{'incidents/telegram-token-rotation-2026-06-14': 'page_id 645 — incidente rotação token Telegram 2026-06-14', 'runbooks/telegram-bot-rotation': 'page_id 646 — runbook completo de rotação do bot'}`
- routing_issue_2026-06-14: `table 205 tinha rota stale br-db3b8fade1cf (linkdown) para 172.20.0.0/16 (wikijs network). Fix: ip route del stale + ip route add br-488839767b3b. Corrigir sempre que wikijs container for recriado.`

### `smart-ir-selfheal.service`
- Descrição: Watchdog do Smart IR NovaDigital no Home Assistant/Tuya Local.
- source: `/etc/systemd/system/smart-ir-selfheal.service`
- domain: `operations`
- candidate_system: `NetBox service model`
- status: `disabled`
- status_reason: `Desativado em 2026-06-14 por decisão operacional: não funciona e interfere nos outros dispositivos IoT.`
- disabled_at: `2026-06-14`
- target_device: `homelab`

### `crypto-agent@BTC_USDT_aggressive.service`
- Descrição: Trading agent BTC-USDT perfil aggressive (live) — master TRADE (kucoin/homelab).
- source: `scripts/cmdb/generate_cmdb_baseline.py`
- domain: `trading`
- symbol: `BTC-USDT`
- profile: `aggressive`
- config_file: `btc_trading_agent/config_BTC_USDT_aggressive.json`
- dry_run: `False`
- live_mode: `True`
- metrics_port: `9095`
- api_port: `None`
- kucoin_account: `master TRADE (kucoin/homelab)`
- systemd_instance: `BTC_USDT_aggressive`
- prometheus_job: `crypto-exporter-btc_usdt_aggressive`
- activate_script: `None`
- auto_generated: `True`

### `crypto-exporter@BTC_USDT_aggressive.service`
- Descrição: Trading exporter BTC-USDT perfil aggressive (live) — master TRADE (kucoin/homelab).
- source: `scripts/cmdb/generate_cmdb_baseline.py`
- domain: `trading`
- symbol: `BTC-USDT`
- profile: `aggressive`
- config_file: `btc_trading_agent/config_BTC_USDT_aggressive.json`
- dry_run: `False`
- live_mode: `True`
- metrics_port: `9095`
- api_port: `None`
- kucoin_account: `master TRADE (kucoin/homelab)`
- systemd_instance: `BTC_USDT_aggressive`
- prometheus_job: `crypto-exporter-btc_usdt_aggressive`
- activate_script: `None`
- auto_generated: `True`

### `crypto-agent@BTC_USDT_conservative.service`
- Descrição: Trading agent BTC-USDT perfil conservative (live) — master TRADE (kucoin/homelab).
- source: `scripts/cmdb/generate_cmdb_baseline.py`
- domain: `trading`
- symbol: `BTC-USDT`
- profile: `conservative`
- config_file: `btc_trading_agent/config_BTC_USDT_conservative.json`
- dry_run: `False`
- live_mode: `True`
- metrics_port: `9094`
- api_port: `None`
- kucoin_account: `master TRADE (kucoin/homelab)`
- systemd_instance: `BTC_USDT_conservative`
- prometheus_job: `crypto-exporter-btc_usdt_conservative`
- activate_script: `None`
- auto_generated: `True`

### `crypto-exporter@BTC_USDT_conservative.service`
- Descrição: Trading exporter BTC-USDT perfil conservative (live) — master TRADE (kucoin/homelab).
- source: `scripts/cmdb/generate_cmdb_baseline.py`
- domain: `trading`
- symbol: `BTC-USDT`
- profile: `conservative`
- config_file: `btc_trading_agent/config_BTC_USDT_conservative.json`
- dry_run: `False`
- live_mode: `True`
- metrics_port: `9094`
- api_port: `None`
- kucoin_account: `master TRADE (kucoin/homelab)`
- systemd_instance: `BTC_USDT_conservative`
- prometheus_job: `crypto-exporter-btc_usdt_conservative`
- activate_script: `None`
- auto_generated: `True`

### `crypto-agent@BTC_USDT_shadow.service`
- Descrição: Trading agent BTC-USDT perfil shadow (live) — subconta (BTCAgressive).
- source: `scripts/cmdb/generate_cmdb_baseline.py`
- domain: `trading`
- symbol: `BTC-USDT`
- profile: `shadow`
- config_file: `btc_trading_agent/config_BTC_USDT_shadow.json`
- dry_run: `False`
- live_mode: `True`
- metrics_port: `9099`
- api_port: `8516`
- kucoin_account: `subconta (BTCAgressive)`
- systemd_instance: `BTC_USDT_shadow`
- prometheus_job: `crypto-exporter-btc_usdt_shadow`
- activate_script: `None`
- auto_generated: `True`

### `crypto-exporter@BTC_USDT_shadow.service`
- Descrição: Trading exporter BTC-USDT perfil shadow (live) — subconta (BTCAgressive).
- source: `scripts/cmdb/generate_cmdb_baseline.py`
- domain: `trading`
- symbol: `BTC-USDT`
- profile: `shadow`
- config_file: `btc_trading_agent/config_BTC_USDT_shadow.json`
- dry_run: `False`
- live_mode: `True`
- metrics_port: `9099`
- api_port: `8516`
- kucoin_account: `subconta (BTCAgressive)`
- systemd_instance: `BTC_USDT_shadow`
- prometheus_job: `crypto-exporter-btc_usdt_shadow`
- activate_script: `None`
- auto_generated: `True`

### `crypto-agent@DOGE_USDT_aggressive.service`
- Descrição: Trading agent DOGE-USDT perfil aggressive (live) — master TRADE (kucoin/homelab) — mesma conta do SOL.
- source: `scripts/cmdb/generate_cmdb_baseline.py`
- domain: `trading`
- symbol: `DOGE-USDT`
- profile: `aggressive`
- config_file: `btc_trading_agent/config_DOGE_USDT_aggressive.json`
- dry_run: `False`
- live_mode: `True`
- metrics_port: `9114`
- api_port: `8524`
- kucoin_account: `master TRADE (kucoin/homelab) — mesma conta do SOL`
- systemd_instance: `DOGE_USDT_aggressive`
- prometheus_job: `crypto-exporter-doge_usdt_aggressive`
- activate_script: `scripts/activate_doge_trading_profiles.sh`
- auto_generated: `True`

### `crypto-exporter@DOGE_USDT_aggressive.service`
- Descrição: Trading exporter DOGE-USDT perfil aggressive (live) — master TRADE (kucoin/homelab) — mesma conta do SOL.
- source: `scripts/cmdb/generate_cmdb_baseline.py`
- domain: `trading`
- symbol: `DOGE-USDT`
- profile: `aggressive`
- config_file: `btc_trading_agent/config_DOGE_USDT_aggressive.json`
- dry_run: `False`
- live_mode: `True`
- metrics_port: `9114`
- api_port: `8524`
- kucoin_account: `master TRADE (kucoin/homelab) — mesma conta do SOL`
- systemd_instance: `DOGE_USDT_aggressive`
- prometheus_job: `crypto-exporter-doge_usdt_aggressive`
- activate_script: `scripts/activate_doge_trading_profiles.sh`
- auto_generated: `True`

### `crypto-agent@DOGE_USDT_conservative.service`
- Descrição: Trading agent DOGE-USDT perfil conservative (live) — master TRADE (kucoin/homelab) — mesma conta do SOL.
- source: `scripts/cmdb/generate_cmdb_baseline.py`
- domain: `trading`
- symbol: `DOGE-USDT`
- profile: `conservative`
- config_file: `btc_trading_agent/config_DOGE_USDT_conservative.json`
- dry_run: `False`
- live_mode: `True`
- metrics_port: `9113`
- api_port: `8523`
- kucoin_account: `master TRADE (kucoin/homelab) — mesma conta do SOL`
- systemd_instance: `DOGE_USDT_conservative`
- prometheus_job: `crypto-exporter-doge_usdt_conservative`
- activate_script: `scripts/activate_doge_trading_profiles.sh`
- auto_generated: `True`

### `crypto-exporter@DOGE_USDT_conservative.service`
- Descrição: Trading exporter DOGE-USDT perfil conservative (live) — master TRADE (kucoin/homelab) — mesma conta do SOL.
- source: `scripts/cmdb/generate_cmdb_baseline.py`
- domain: `trading`
- symbol: `DOGE-USDT`
- profile: `conservative`
- config_file: `btc_trading_agent/config_DOGE_USDT_conservative.json`
- dry_run: `False`
- live_mode: `True`
- metrics_port: `9113`
- api_port: `8523`
- kucoin_account: `master TRADE (kucoin/homelab) — mesma conta do SOL`
- systemd_instance: `DOGE_USDT_conservative`
- prometheus_job: `crypto-exporter-doge_usdt_conservative`
- activate_script: `scripts/activate_doge_trading_profiles.sh`
- auto_generated: `True`

### `crypto-agent@DOGE_USDT_shadow.service`
- Descrição: Trading agent DOGE-USDT perfil shadow (live) — master TRADE (kucoin/homelab) — mesma conta do SOL.
- source: `scripts/cmdb/generate_cmdb_baseline.py`
- domain: `trading`
- symbol: `DOGE-USDT`
- profile: `shadow`
- config_file: `btc_trading_agent/config_DOGE_USDT_shadow.json`
- dry_run: `False`
- live_mode: `True`
- metrics_port: `9112`
- api_port: `8522`
- kucoin_account: `master TRADE (kucoin/homelab) — mesma conta do SOL`
- systemd_instance: `DOGE_USDT_shadow`
- prometheus_job: `crypto-exporter-doge_usdt_shadow`
- activate_script: `scripts/activate_doge_trading_profiles.sh`
- auto_generated: `True`

### `crypto-exporter@DOGE_USDT_shadow.service`
- Descrição: Trading exporter DOGE-USDT perfil shadow (live) — master TRADE (kucoin/homelab) — mesma conta do SOL.
- source: `scripts/cmdb/generate_cmdb_baseline.py`
- domain: `trading`
- symbol: `DOGE-USDT`
- profile: `shadow`
- config_file: `btc_trading_agent/config_DOGE_USDT_shadow.json`
- dry_run: `False`
- live_mode: `True`
- metrics_port: `9112`
- api_port: `8522`
- kucoin_account: `master TRADE (kucoin/homelab) — mesma conta do SOL`
- systemd_instance: `DOGE_USDT_shadow`
- prometheus_job: `crypto-exporter-doge_usdt_shadow`
- activate_script: `scripts/activate_doge_trading_profiles.sh`
- auto_generated: `True`

### `crypto-agent@ETH_USDT_aggressive.service`
- Descrição: Trading agent ETH-USDT perfil aggressive (live) — subconta sub:ETHAgressive via KUCOIN_SECRET_NAMES.
- source: `scripts/cmdb/generate_cmdb_baseline.py`
- domain: `trading`
- symbol: `ETH-USDT`
- profile: `aggressive`
- config_file: `btc_trading_agent/config_ETH_USDT_aggressive.json`
- dry_run: `False`
- live_mode: `True`
- metrics_port: `9098`
- api_port: `None`
- kucoin_account: `subconta sub:ETHAgressive via KUCOIN_SECRET_NAMES`
- systemd_instance: `ETH_USDT_aggressive`
- prometheus_job: `crypto-exporter-eth_usdt_aggressive`
- activate_script: `None`
- auto_generated: `True`

### `crypto-exporter@ETH_USDT_aggressive.service`
- Descrição: Trading exporter ETH-USDT perfil aggressive (live) — subconta sub:ETHAgressive via KUCOIN_SECRET_NAMES.
- source: `scripts/cmdb/generate_cmdb_baseline.py`
- domain: `trading`
- symbol: `ETH-USDT`
- profile: `aggressive`
- config_file: `btc_trading_agent/config_ETH_USDT_aggressive.json`
- dry_run: `False`
- live_mode: `True`
- metrics_port: `9098`
- api_port: `None`
- kucoin_account: `subconta sub:ETHAgressive via KUCOIN_SECRET_NAMES`
- systemd_instance: `ETH_USDT_aggressive`
- prometheus_job: `crypto-exporter-eth_usdt_aggressive`
- activate_script: `None`
- auto_generated: `True`

### `crypto-agent@ETH_USDT_conservative.service`
- Descrição: Trading agent ETH-USDT perfil conservative (live) — subconta sub:ETHConservative ($50) via KUCOIN_SECRET_NAMES.
- source: `scripts/cmdb/generate_cmdb_baseline.py`
- domain: `trading`
- symbol: `ETH-USDT`
- profile: `conservative`
- config_file: `btc_trading_agent/config_ETH_USDT_conservative.json`
- dry_run: `False`
- live_mode: `True`
- metrics_port: `9097`
- api_port: `None`
- kucoin_account: `subconta sub:ETHConservative ($50) via KUCOIN_SECRET_NAMES`
- systemd_instance: `ETH_USDT_conservative`
- prometheus_job: `crypto-exporter-eth_usdt_conservative`
- activate_script: `None`
- auto_generated: `True`

### `crypto-exporter@ETH_USDT_conservative.service`
- Descrição: Trading exporter ETH-USDT perfil conservative (live) — subconta sub:ETHConservative ($50) via KUCOIN_SECRET_NAMES.
- source: `scripts/cmdb/generate_cmdb_baseline.py`
- domain: `trading`
- symbol: `ETH-USDT`
- profile: `conservative`
- config_file: `btc_trading_agent/config_ETH_USDT_conservative.json`
- dry_run: `False`
- live_mode: `True`
- metrics_port: `9097`
- api_port: `None`
- kucoin_account: `subconta sub:ETHConservative ($50) via KUCOIN_SECRET_NAMES`
- systemd_instance: `ETH_USDT_conservative`
- prometheus_job: `crypto-exporter-eth_usdt_conservative`
- activate_script: `None`
- auto_generated: `True`

### `crypto-agent@ETH_USDT_shadow.service`
- Descrição: Trading agent ETH-USDT perfil shadow (live) — subconta (BTCAgressive).
- source: `scripts/cmdb/generate_cmdb_baseline.py`
- domain: `trading`
- symbol: `ETH-USDT`
- profile: `shadow`
- config_file: `btc_trading_agent/config_ETH_USDT_shadow.json`
- dry_run: `False`
- live_mode: `True`
- metrics_port: `9096`
- api_port: `None`
- kucoin_account: `subconta (BTCAgressive)`
- systemd_instance: `ETH_USDT_shadow`
- prometheus_job: `crypto-exporter-eth_usdt_shadow`
- activate_script: `None`
- auto_generated: `True`

### `crypto-exporter@ETH_USDT_shadow.service`
- Descrição: Trading exporter ETH-USDT perfil shadow (live) — subconta (BTCAgressive).
- source: `scripts/cmdb/generate_cmdb_baseline.py`
- domain: `trading`
- symbol: `ETH-USDT`
- profile: `shadow`
- config_file: `btc_trading_agent/config_ETH_USDT_shadow.json`
- dry_run: `False`
- live_mode: `True`
- metrics_port: `9096`
- api_port: `None`
- kucoin_account: `subconta (BTCAgressive)`
- systemd_instance: `ETH_USDT_shadow`
- prometheus_job: `crypto-exporter-eth_usdt_shadow`
- activate_script: `None`
- auto_generated: `True`

### `crypto-agent@SOL_USDT_aggressive.service`
- Descrição: Trading agent SOL-USDT perfil aggressive (live) — master TRADE (kucoin/homelab) — KuCoin não permite novas subcontas.
- source: `scripts/cmdb/generate_cmdb_baseline.py`
- domain: `trading`
- symbol: `SOL-USDT`
- profile: `aggressive`
- config_file: `btc_trading_agent/config_SOL_USDT_aggressive.json`
- dry_run: `False`
- live_mode: `True`
- metrics_port: `9106`
- api_port: `8517`
- kucoin_account: `master TRADE (kucoin/homelab) — KuCoin não permite novas subcontas`
- systemd_instance: `SOL_USDT_aggressive`
- prometheus_job: `crypto-exporter-sol_usdt_aggressive`
- activate_script: `scripts/activate_sol_trading_profiles.sh`
- auto_generated: `True`

### `crypto-exporter@SOL_USDT_aggressive.service`
- Descrição: Trading exporter SOL-USDT perfil aggressive (live) — master TRADE (kucoin/homelab) — KuCoin não permite novas subcontas.
- source: `scripts/cmdb/generate_cmdb_baseline.py`
- domain: `trading`
- symbol: `SOL-USDT`
- profile: `aggressive`
- config_file: `btc_trading_agent/config_SOL_USDT_aggressive.json`
- dry_run: `False`
- live_mode: `True`
- metrics_port: `9106`
- api_port: `8517`
- kucoin_account: `master TRADE (kucoin/homelab) — KuCoin não permite novas subcontas`
- systemd_instance: `SOL_USDT_aggressive`
- prometheus_job: `crypto-exporter-sol_usdt_aggressive`
- activate_script: `scripts/activate_sol_trading_profiles.sh`
- auto_generated: `True`

### `crypto-agent@SOL_USDT_conservative.service`
- Descrição: Trading agent SOL-USDT perfil conservative (live) — master TRADE (kucoin/homelab) — KuCoin não permite novas subcontas.
- source: `scripts/cmdb/generate_cmdb_baseline.py`
- domain: `trading`
- symbol: `SOL-USDT`
- profile: `conservative`
- config_file: `btc_trading_agent/config_SOL_USDT_conservative.json`
- dry_run: `False`
- live_mode: `True`
- metrics_port: `9104`
- api_port: `8516`
- kucoin_account: `master TRADE (kucoin/homelab) — KuCoin não permite novas subcontas`
- systemd_instance: `SOL_USDT_conservative`
- prometheus_job: `crypto-exporter-sol_usdt_conservative`
- activate_script: `scripts/activate_sol_trading_profiles.sh`
- auto_generated: `True`

### `crypto-exporter@SOL_USDT_conservative.service`
- Descrição: Trading exporter SOL-USDT perfil conservative (live) — master TRADE (kucoin/homelab) — KuCoin não permite novas subcontas.
- source: `scripts/cmdb/generate_cmdb_baseline.py`
- domain: `trading`
- symbol: `SOL-USDT`
- profile: `conservative`
- config_file: `btc_trading_agent/config_SOL_USDT_conservative.json`
- dry_run: `False`
- live_mode: `True`
- metrics_port: `9104`
- api_port: `8516`
- kucoin_account: `master TRADE (kucoin/homelab) — KuCoin não permite novas subcontas`
- systemd_instance: `SOL_USDT_conservative`
- prometheus_job: `crypto-exporter-sol_usdt_conservative`
- activate_script: `scripts/activate_sol_trading_profiles.sh`
- auto_generated: `True`

### `crypto-agent@SOL_USDT_shadow.service`
- Descrição: Trading agent SOL-USDT perfil shadow (live) — master TRADE (kucoin/homelab) — KuCoin não permite novas subcontas.
- source: `scripts/cmdb/generate_cmdb_baseline.py`
- domain: `trading`
- symbol: `SOL-USDT`
- profile: `shadow`
- config_file: `btc_trading_agent/config_SOL_USDT_shadow.json`
- dry_run: `False`
- live_mode: `True`
- metrics_port: `9108`
- api_port: `8518`
- kucoin_account: `master TRADE (kucoin/homelab) — KuCoin não permite novas subcontas`
- systemd_instance: `SOL_USDT_shadow`
- prometheus_job: `crypto-exporter-sol_usdt_shadow`
- activate_script: `scripts/activate_sol_trading_profiles.sh`
- auto_generated: `True`

### `crypto-exporter@SOL_USDT_shadow.service`
- Descrição: Trading exporter SOL-USDT perfil shadow (live) — master TRADE (kucoin/homelab) — KuCoin não permite novas subcontas.
- source: `scripts/cmdb/generate_cmdb_baseline.py`
- domain: `trading`
- symbol: `SOL-USDT`
- profile: `shadow`
- config_file: `btc_trading_agent/config_SOL_USDT_shadow.json`
- dry_run: `False`
- live_mode: `True`
- metrics_port: `9108`
- api_port: `8518`
- kucoin_account: `master TRADE (kucoin/homelab) — KuCoin não permite novas subcontas`
- systemd_instance: `SOL_USDT_shadow`
- prometheus_job: `crypto-exporter-sol_usdt_shadow`
- activate_script: `scripts/activate_sol_trading_profiles.sh`
- auto_generated: `True`

