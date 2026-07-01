# PandaPlus → Telegram Bridge

Detecta eventos da fechadura **PandaPlus** (DPs `unlock_request` e `alarm_lock`) via Tuya MQ e envia notificações para o Telegram, com fluxo opcional de aprovação remota usando `reply_unlock_request`.

## Eventos monitorados

| DP | Valor | Significado |
|----|-------|-------------|
| `unlock_request` | Integer > 0 | Alguém está pedindo abertura remota (countdown em segundos). |
| `alarm_lock` | `wrong_finger` / `wrong_password` / `wrong_card` / `wrong_face` / `key_in` | Tentativa falha de credencial — alguém na porta. |

Demais DPs (`battery_state`, contadores de uso, etc.) são ignorados.

## Modos de operação

| Modo | `PANDAPLUS_OBSERVE_ONLY` | Comportamento |
|------|--------------------------|----------------|
| Observação (padrão) | `1` | Envia notificação no Telegram com botão "📋 Ver detalhes". **NÃO** envia `reply_unlock_request` à fechadura. Recomendado por 24-48h até confirmar que eventos chegam. |
| Aprovação ativa | `0` | Mensagem com `✅ Aprovar` / `❌ Negar`. Decisão é roteada via HTTP local (porta 8590) para o endpoint `/reply`. |

## Variáveis de ambiente

| Variável | Obrigatória | Default | Descrição |
|----------|:-:|---------|-----------|
| `PANDAPLUS_DEVICE_ID` | ✅ | — | ID Tuya da fechadura (ex: `eb24b140cebde5a9dd7abw`). |
| `TELEGRAM_BOT_TOKEN` | ✅ | — | Token do bot Telegram. |
| `TELEGRAM_CHAT_ID` | ✅ | — | Chat ID para enviar notificações. |
| `PANDAPLUS_ALLOWED_USERS` | ❌ | `TELEGRAM_CHAT_ID` | Lista de `user_id` Telegram autorizados a aprovar (CSV). |
| `PANDAPLUS_OBSERVE_ONLY` | ❌ | `1` | `0` para habilitar fluxo de aprovação real. |
| `PANDAPLUS_HA_STORAGE` | ❌ | `/config/.storage/core.config_entries` | Caminho para o storage do HA (com tokens Tuya). |
| `PANDAPLUS_REPLY_HOST` | ❌ | `127.0.0.1` | Bind do HTTP listener. |
| `PANDAPLUS_REPLY_PORT` | ❌ | `8590` | Porta do HTTP listener. |
| `PANDAPLUS_REQUEST_TTL` | ❌ | `90` | TTL de cada pedido pendente (segundos). |
| `PANDAPLUS_TUYA_CLIENT_ID` | ❌ | `HA_3y9q4ak7g4ephrvke` | Client ID da integração HA (constante pública). |
| `DATABASE_URL` | ❌ | — | Postgres para auditoria (futuro). |

## Deploy no homelab

```bash
# 1. Diretório de trabalho com cópia do core.config_entries
sudo mkdir -p /var/lib/pandaplus-bridge
sudo chown homelab:homelab /var/lib/pandaplus-bridge

# 2. Arquivo de env (NUNCA versionar)
sudo tee /etc/default/pandaplus-bridge >/dev/null <<EOF
PANDAPLUS_DEVICE_ID=eb24b140cebde5a9dd7abw
TELEGRAM_BOT_TOKEN=...  # obter do Secrets Agent
TELEGRAM_CHAT_ID=948686300
PANDAPLUS_ALLOWED_USERS=948686300
PANDAPLUS_OBSERVE_ONLY=1
PANDAPLUS_HA_STORAGE=/var/lib/pandaplus-bridge/core.config_entries
EOF
sudo chmod 600 /etc/default/pandaplus-bridge

# 3. Instalar deps no venv do eddie-auto-dev
cd /home/homelab/eddie-auto-dev
./.venv/bin/pip install tuya-sharing aiohttp httpx

# 4. systemd
sudo cp systemd/pandaplus-telegram-bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pandaplus-telegram-bridge
sudo journalctl -u pandaplus-telegram-bridge -f
```

## Integração de callbacks (modo aprovação)

O bridge **não** consome `getUpdates` do Telegram (evita conflito com o bot principal). O fluxo:

```
Usuário aperta botão Telegram
        │
        ▼ callback_query (pdpls:approve:TOKEN)
eddie-telegram-bot.service (existente)
        │
        ▼ POST http://127.0.0.1:8590/reply  {token, decision, user_id}
pandaplus-telegram-bridge
        │
        ▼ tuya_sharing.Manager.customer_api.post(/commands)
PandaPlus Lock
```

Para ativar, adicione ao `telegram_bot.py` (no loop de updates, após `handle_message`):

```python
import httpx
# ...
elif callback := update.get("callback_query"):
    data = callback.get("data", "")
    if data.startswith("pdpls:"):
        _, decision, token = data.split(":", 2)
        user_id = callback["from"]["id"]
        async with httpx.AsyncClient(timeout=5) as cli:
            await cli.post(
                "http://127.0.0.1:8590/reply",
                json={"token": token, "decision": decision, "user_id": user_id},
            )
        await self.api._request(
            "answerCallbackQuery",
            callback_query_id=callback["id"],
            text="Processando...",
        )
```

## Testes

```bash
cd /workspace/eddie-auto-dev
.venv/bin/pytest tests/unit/test_pandaplus_bridge.py -v
```

## Limitações conhecidas

1. **Modelo PandaPlus é "unsupported"** no catálogo HA Tuya — eventos chegam via MQ mas não geram entidades HA. Bridge contorna isso indo direto na MQ.
2. **Renovação de token Tuya**: o SDK só renova quando faltam <60s para expirar. Se o bridge ficar offline mais do que `expire_time`, é preciso reiniciar e copiar `core.config_entries` novamente (o `ExecStartPre` do unit já faz isso).
3. **Battery-powered**: a fechadura só "fala" com a nuvem em eventos significativos. Não espere telemetria contínua.
4. **Sem campainha real**: PandaPlus não expõe DP de campainha — usamos `unlock_request` (pedido de abertura) e `alarm_lock` (tentativas falhas) como proxies.
