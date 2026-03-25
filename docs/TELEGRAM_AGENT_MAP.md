# Telegram Agent Map (Fonte da Verdade)

Este documento concentra os caminhos reais para localizar e operar o ecossistema Telegram neste workspace.

## 1) Onde fica o Agent Telegram principal

| Papel | Arquivo oficial | Observação |
|---|---|---|
| Bot Telegram principal | `scripts/misc/telegram_bot.py` | Entrada principal de comandos e integração com agentes |
| Listener via bus | `tools/telegram_listener.py` | Fluxo Telegram ↔ bus (legado/auxiliar) |
| Alertas Alertmanager → Telegram | `tools/alerting/alertmanager_telegram_webhook.py` | Webhook que recebe alertas e envia mensagens ao Telegram |
| Config do Alertmanager para Telegram | `tools/alerting/alertmanager_telegram.yml` | Rotas e receivers de notificação |
| Deploy da integração Alertmanager/Telegram | `scripts/deployment/deploy_alertmanager_telegram.sh` | Instala webhook + config no homelab |
| Secrets Telegram | `tools/secrets_loader.py` | Leitura de `shared/telegram_bot_token` e `shared/telegram_chat_id` |

## 2) Serviços systemd relacionados

| Serviço | Arquivo no repo | Função |
|---|---|---|
| `eddie-telegram-bot` | `systemd/eddie-telegram-bot.service` | Serviço do bot Telegram |
| `alertmanager-telegram-webhook` | (criado pelo deploy) | Webhook de alertas para Telegram |
| `job-monitor` | `systemd/job-monitor.service` | Monitor contínuo com opção de notificação Telegram |

## 3) Fluxo de alertas Telegram (monitoramento)

1. Prometheus/Grafana disparam alerta.
2. Alertmanager roteia para webhook `http://localhost:5000/alerts`.
3. `tools/alerting/alertmanager_telegram_webhook.py` saneia e envia para o chat Telegram.

## 4) Saneamento aplicado nos alertas

No webhook de alertas foram adicionados:

- filtro de severidade (`ALERT_ALLOWED_SEVERITIES`)
- opção para ignorar resolvidos (`ALERT_SEND_RESOLVED=false` por padrão)
- deduplicação temporal (`ALERT_DEDUP_WINDOW_SECONDS`)
- sanitização de conteúdo para `parse_mode=HTML`
- batching/limite de notificações por payload

Também foi ajustado `tools/alerting/alertmanager_telegram.yml` para reduzir ruído:

- evita rota duplicada (`continue: false` em self-healing)
- `send_resolved: false` nos receivers Telegram

## 5) Comandos rápidos para encontrar e validar

```bash
# localizar componentes Telegram oficiais
rg -n "telegram_bot.py|alertmanager_telegram|telegram_listener|shared-telegram-bot" scripts tools systemd docs

# validar sintaxe do webhook
python3 -m py_compile tools/alerting/alertmanager_telegram_webhook.py

# validar serviço do bot (host alvo)
sudo systemctl status eddie-telegram-bot

# logs do webhook (host alvo)
sudo journalctl -u alertmanager-telegram-webhook -f
```

## 6) Importante sobre duplicatas no workspace

Há cópias de árvore em `main-copy/`, `trading-work/` e `trading-deploy/`.
Use como referência principal os arquivos na raiz deste repositório (fora dessas cópias), salvo quando estiver operando explicitamente nesses ambientes clonados.
