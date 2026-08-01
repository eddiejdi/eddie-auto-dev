# Tuya Token Renewer (monitor) — Variáveis e política Telegram

Serviço: `tuya-token-renewer.service` (+ `.timer`) — script
`tools/homelab/tuya_token_renewer.py`, instalado em
`/usr/local/bin/tuya_token_renewer.py` no homelab (192.168.15.2).

**Não renova o token.** É um *monitor* de saúde da config entry Tuya no Home
Assistant: lê `token_info` no storage, consulta estados das entidades e
alerta só quando há **erro real**. A renovação proativa fica a cargo do
[`tuya-token-selfheal`](TUYA_TOKEN_SELFHEAL.md) (timer ~5 min, soft threshold 45 min).

| Item | Valor operacional |
|---|---|
| Unit | `tuya-token-renewer.service` / `.timer` |
| Repo unit | `systemd/tuya-token-renewer.service` (+ timer) |
| ExecStart | `/usr/local/bin/tuya_token_renewer.py` |
| Intervalo em produção (jul/2026) | `OnUnitActiveSec=30min` (timer no host; o `.timer` versionado no repo pode diferir — preferir o do homelab) |
| Secrets | via Secrets Agent (`SECRETS_AGENT_URL` + `SECRETS_AGENT_API_KEY` no drop-in da unit) |

## Política Telegram (2026-07-30)

**Somente enviar mensagem em caso de erro.** Aviso de “token perto de vencer”
com entidades saudáveis **não** vai para o Telegram — só para o journal.

| Condição | Exit | Telegram |
|---|---|---|
| Config entry ausente / docker exec falhou | `2` | ✅ `⚠️ Tuya com falha no Home Assistant` |
| API do HA ilegível (após retries; HA “starting” é silenciado) | `2` | ✅ `⚠️ Tuya monitor sem leitura do HA` |
| `0/N` entidades ativas (após retries de flapping) | `2` | ✅ `⚠️ Tuya sem entidades ativas…` |
| Token **já expirado** (`remaining_min ≤ 0`) e HA ainda reporta entidades | `2` | ✅ `🔴 Tuya expirado no Home Assistant` |
| Token na janela de aviso (`remaining < TUYA_TOKEN_WARN_MINUTES`) e HA saudável | `0` | ❌ só `WARNING` no journal |
| Tudo OK (entidades ativas, token com margem) | `0` | ❌ silêncio |

### Por que não alertar “perto de vencer”

O access token Tuya dura ~2 h. Com timer a cada 30 min e limiar 45 min, o
monitor disparava Telegram **quase a cada ciclo** com texto do tipo:

```text
⏰ Tuya perto de vencer no Home Assistant
Token expira em ~31 min.
HA: 82/82 entidades ativas | 13 desabilitadas | 4 scenes ignoradas
```

Isso é ruído: o selfheal já renova proativamente abaixo de
`HEAL_SOFT_THRESHOLD_MIN` (default 45). Telegram fica reservado a falha de
disponibilidade ou token **vencido** (reauth QR).

## Variáveis de ambiente

| Variável | Default | Propósito |
|---|---|---|
| `SECRETS_AGENT_URL` | `http://192.168.15.2:8088` | Base do Secrets Agent. |
| `SECRETS_AGENT_API_KEY` | *(obrigatório — drop-in da unit)* | Auth no Secrets Agent. **Nunca** versionar em git. |
| `HA_CONTAINER` | `homeassistant` | Container Docker do HA (leitura de `.storage` via `docker exec`). |
| `TUYA_ZERO_ACTIVE_RETRIES` | `3` | Releituras se a API HA devolver 0 entidades ativas (anti-flap). |
| `TUYA_ZERO_ACTIVE_RETRY_SLEEP_S` | `20` | Sleep entre releituras de 0 ativas. |
| `TUYA_TOKEN_WARN_MINUTES` | `45` | Limiar **somente de log** para “perto de vencer”. Não dispara Telegram. |

Secrets lidos pelo script (não são env da unit):

| Secret | Campo | Uso |
|---|---|---|
| `eddie/tuya_ha/entry_id` | default | Config entry Tuya no HA |
| `eddie/tuya_ha/ha_url` | default | URL do HA (links nos alertas) |
| `authentik/eddie/home_assistant_token` | default | Bearer da API HA |
| `authentik/eddie/telegram_bot_token` | `token` | Bot (opcional; sem ele, só log) |
| `authentik/eddie/telegram_chat_id` | `chat_id` | Chat destino |

Drop-in de produção: `SuccessExitStatus=2` em
`tuya-token-renewer.service.d/20-monitor-alert-not-system-failure.conf` —
exit `2` (alerta de domínio) **não** marca a unit como *failed* no systemd.

## Deploy

```bash
# Do workspace
scp tools/homelab/tuya_token_renewer.py homelab@192.168.15.2:/tmp/tuya_token_renewer.py
ssh homelab@192.168.15.2 'sudo install -m 755 /tmp/tuya_token_renewer.py /usr/local/bin/tuya_token_renewer.py'

# Rodar uma vez e conferir journal (não deve haver send Telegram em HA saudável)
ssh homelab@192.168.15.2 'sudo systemctl start tuya-token-renewer.service && journalctl -u tuya-token-renewer.service -n 20 --no-pager'
```

Log esperado com token na janela de aviso e entidades OK:

```text
INFO Tuya token expira em ~17 min | HA: 82/82 entidades ativas | …
WARNING Token expira em ~17 min (limiar log 45 min); sem Telegram (somente erros)
```

## Relação com outros jobs Tuya

| Job | Papel | Telegram |
|---|---|---|
| `tuya-token-renewer` | Monitor de saúde / disponibilidade | **Só erro** (esta política) |
| `tuya-token-selfheal` | Refresh + injeção de token no HA | Métricas Prometheus; não é este monitor |
| `tuya-local-key-selfheal` | Sync `local_key` cloud → `tuya_local` | Fora do escopo deste doc |
| `ha-tuya-mq-watchdog` | MQTT Tuya sharing | Fora do escopo deste doc |

Ver também: [SMARTLIFE_TUYA_INTEGRATION.md](../SMARTLIFE_TUYA_INTEGRATION.md),
[TUYA_TOKEN_SELFHEAL.md](TUYA_TOKEN_SELFHEAL.md).

## Histórico

| Data | Mudança |
|---|---|
| 2026-07-30 | Telegram do aviso “perto de vencer” removido; documentada política *errors-only*. Produção atualizada em `/usr/local/bin/tuya_token_renewer.py`. |
