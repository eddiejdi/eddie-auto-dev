# CMDB Baseline

- Generated at: `2026-07-08T11:50:31.480312+00:00`
- Site: `homelab-main`
- Hosts discovered: `1`
- Repo services discovered: `162`
- Critical services flagged for MVP: `162`
- Project: [eddie-auto-dev](https://github.com/eddiejdi/eddie-auto-dev)
- Owner: `edenilson.adm@gmail.com`

## Domain counts

- `monitoring`: 162

## NetBox seed candidates

- `homelab` -> role `compute-node`, platform `linux`, ip `192.168.15.2`

## MVP critical services

- `cadvisor` (monitoring, compose) from `docker/docker-compose-exporters.yml`
- `glpi` (monitoring, compose) from `deploy/cmdb/docker-compose.yml`
- `glpi-db` (monitoring, compose) from `deploy/cmdb/docker-compose.yml`
- `grafana` (monitoring, compose) from `tools/authentik_management/configs/docker-compose.override.yml`
- `mail-db` (monitoring, compose) from `docker/docker-compose.simple-mail.yml`
- `mail-server` (monitoring, compose) from `docker/docker-compose.simple-mail.yml`
- `mailu-backend` (monitoring, compose) from `docker/docker-compose.mailu.yml`
- `mailu-db` (monitoring, compose) from `docker/docker-compose.mailu.yml`
- `mailu-dovecot` (monitoring, compose) from `docker/docker-compose.mailu.yml`
- `mailu-frontend` (monitoring, compose) from `docker/docker-compose.mailu.yml`
- `mailu-postfix` (monitoring, compose) from `docker/docker-compose.mailu.yml`
- `mailu-redis` (monitoring, compose) from `docker/docker-compose.mailu.yml`
- `mailu-roundcube` (monitoring, compose) from `docker/docker-compose.mailu.yml`
- `netbox` (monitoring, compose) from `deploy/cmdb/docker-compose.yml`
- `netbox-postgres` (monitoring, compose) from `deploy/cmdb/docker-compose.yml`
- `netbox-redis` (monitoring, compose) from `deploy/cmdb/docker-compose.yml`
- `netbox-redis-cache` (monitoring, compose) from `deploy/cmdb/docker-compose.yml`
- `netbox-worker` (monitoring, compose) from `deploy/cmdb/docker-compose.yml`
- `nginx` (monitoring, compose) from `docker/docker-compose.simple-mail.yml`
- `node-exporter` (monitoring, compose) from `docker/docker-compose-exporters.yml`
- `ntopng` (monitoring, compose) from `docker/docker-compose.ntopng.yml`
- `ntopng-redis` (monitoring, compose) from `docker/docker-compose.ntopng.yml`
- `open-webui` (monitoring, compose) from `tools/authentik_management/configs/docker-compose.override.yml`
- `opensearch-dashboards` (monitoring, compose) from `docker/docker-compose.opensearch.yml`
- `opensearch-node1` (monitoring, compose) from `docker/docker-compose.opensearch.yml`
- `postfix-exporter` (monitoring, compose) from `docker/docker-compose.simple-mail.yml`
- `postgres` (monitoring, compose) from `docker/docker-compose.email-simple.yml`
- `printshare` (monitoring, compose) from `deploy/printshare/docker-compose.yml`
- `prometheus` (monitoring, compose) from `docker/docker-compose.grafana.yml`
- `proxy` (monitoring, compose) from `deploy/cmdb/docker-compose.yml`
- `roundcube` (monitoring, compose) from `docker/docker-compose.simple-mail.yml`
- `vaultwarden` (monitoring, compose) from `tools/vaultwarden/docker-compose.yml`
- `wikijs` (monitoring, compose) from `docker/docker-compose.wikijs.yml`
- `wikijs-db` (monitoring, compose) from `docker/docker-compose.wikijs.yml`
- `agent-network-exporter.service` (monitoring, systemd) from `tools/systemd/agent-network-exporter.service`
- `akash-sweep.service` (monitoring, systemd) from `systemd/akash-sweep.service`
- `akash-sweep.timer` (monitoring, systemd) from `systemd/akash-sweep.timer`
- `approval-gateway.service` (monitoring, systemd) from `systemd/approval-gateway.service`
- `auto_validate.service` (monitoring, systemd) from `deploy/auto_validate.service`
- `autonomous_remediator.service` (monitoring, systemd) from `tools/systemd/autonomous_remediator.service`

## Serviços anotados manualmente

### `eddie-telegram-bot.service`
- Descrição: Chatbot Telegram do homelab Eddie com suporte a comandos de trading, AI, mídia e administração.
- Depende de: `eddie-postgres, ollama.service, specialized-agents-api.service`
- runtime_path: `/home/homelab/myClaude/telegram_bot.py`
- venv: `/home/homelab/myClaude/.venv`
- env_file: `/etc/default/eddie-common`
- commands: `{'trading': {'/relatorio': 'Relatório completo: planejamento AI por perfil (últimas 2h) + P&L 24h + posições abertas. Fonte: btc.ai_plans + btc.trades via psycopg2.', '/btc': 'Status resumido: preço KuCoin + métricas 7d (trades, win rate, PnL) + último trade.', '/trades [N]': 'Últimos N trades (default 5, max 20) com side, size, price, pnl e perfil.', '/performance': 'Estatísticas de sells nos últimos 7 dias: total, vencedores, win rate, PnL total e médio.', '/signal': 'Último sinal AI da btc.decisions: ação, confiança, preço, executado, motivo.', '/cotacao [par]': 'Cotação em tempo real via KuCoin API pública. Aceita: BTC, AKT, USDT-BRL, BTC/USDT. Resolve base → quotes [BRL, USDT, USDC].', '/trading [pergunta]': 'Interface de linguagem natural: roteado para cotacao/trades/performance/signal/status.'}, 'ai_chat': {'mensagem livre': 'Conversa com Ollama (phi4-mini) com contexto de sessão.', '/use [modelo]': 'Troca o modelo Ollama da sessão.', '/models': 'Lista modelos disponíveis no Ollama.', '/profiles': 'Lista perfis de AI configurados.', '/profile [nome]': 'Muda o perfil de AI da sessão.', '/clear': 'Limpa histórico da sessão.', '/ask [pergunta]': 'Pergunta direta ao AI sem contexto de sessão.', '/code [descrição]': 'Assistente de código.', '/agents': 'Lista agentes especializados disponíveis.', '/project': 'Informações do projeto atual.', '/run [cmd]': 'Executa comando via agente.'}, 'autodev': {'/autodev': 'Status do modo auto-desenvolvimento.', '/autodev_list': 'Lista tarefas de auto-dev pendentes.', '/autodev_test': 'Executa testes de auto-dev.', '/autodev_on': '(admin) Habilita auto-dev.', '/autodev_off': '(admin) Desabilita auto-dev.'}, 'media': {'/x [url]': 'Baixa texto e mídia de posts do Twitter/X e envia no Telegram.', '/photo': 'Envia foto.', '/doc': 'Envia documento.'}, 'system': {'/start': 'Mensagem de boas-vindas.', '/help': 'Lista todos os comandos disponíveis.', '/status': 'Status do bot e serviços do homelab.', '/id': 'Mostra chat_id e user_id.', '/me': 'Informações do usuário.'}, 'admin_only': {'/send': 'Envia mensagem para outro chat.', '/broadcast': 'Broadcast para todos os usuários.', '/ban /unban': 'Banir/desbanir usuário.', '/pin /unpin': 'Fixar/desafixar mensagem.', '/invite /title': 'Gerenciamento de grupo.'}, 'integrations_disabled': {'/calendar': 'Google Calendar (módulo não instalado).', '/gmail': 'Gmail (módulo não instalado).', '/onde /location': 'Localização (módulo não instalado).', '/casa /luzes': 'Home Assistant (módulo não instalado).', '/search': 'Busca web (módulo não instalado).'}}`
- token_management: `{'active_token_id': '1105143633', 'token_source': 'authentik/eddie/telegram_bot_token (local_vault via secrets agent)', 'apply_script': '/usr/local/bin/eddie-apply-telegram-token.sh', 'apply_script_repo': 'scripts/automation/eddie-apply-telegram-token.sh', 'rotation_script': '/home/homelab/telegram_botfather_rotate_selenium.py', 'rotation_script_repo': 'scripts/automation/telegram_botfather_rotate_selenium.py', 'rotation_runbook': 'docs/TELEGRAM_BOT_ROTATION_RUNBOOK.md', 'last_rotation': '2026-06-14', 'notes': 'Token canônico SEMPRE via secrets agent. Nunca hardcodado. Após rotação verificar getMe + Authentik.'}`
- fixes_applied: `['2026-06-13: psycopg2-binary instalado em /home/homelab/myClaude/.venv', '2026-06-13: DATABASE_URL adicionado ao /etc/default/eddie-common', '2026-06-13: get_trades/performance/signal migrados de TrainingDatabase para psycopg2 direto', '2026-06-13: get_quote implementado via KuCoin API pública (sem auth)', '2026-06-13: ROUND(double precision) corrigido para ROUND(expr::numeric) no SQL de posições', '2026-06-14: apply script reescrito — agora persiste token no Authentik via POST /secrets (commit 22f73963)', '2026-06-14: grep -hoP corrigido (sem -h prefixava filename: ao extrair SECRETS_AGENT_API_KEY) (commit 23dfedf9)', '2026-06-14: suporte a --token-file no apply script para evitar expansão bash prematura de {token_file}']`

### `grafana`
- Descrição: Grafana 12.4.0 via docker-compose.grafana.yml. Backend: PostgreSQL (eddie-postgres, db=grafana). Porta: 3002->3000. SSO via Authentik. URL: https://grafana.rpa4all.com
- Depende de: `eddie-postgres, homelab_monitoring network`
- compose_file: `/home/homelab/docker-compose.grafana.yml`

### `mnt-raid1.mount`
- Descrição: mergerfs union de /mnt/disk1 (sdb1) + /mnt/disk2 (sdc1) + /mnt/disk3 (sda1) em /mnt/raid1. Opção nonempty obrigatória — diretório contém nextcloud/ ao montar. Docker data-root: /mnt/disk1/docker. Ollama models: /mnt/raid1/ollama/models
- fix_applied: `2026-06-12: adicionado nonempty ao fstab; disk1/disk3 precisam estar montados antes`

### `eddie-apply-telegram-token.sh`
- Descrição: Script de aplicação de token Telegram: grava /etc/eddie/telegram.env, cria drop-ins systemd e persiste em Authentik via secrets agent.
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

