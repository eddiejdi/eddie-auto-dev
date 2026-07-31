# Smart Life / Tuya via Home Assistant

Runbook da integracao Smart Life/Tuya no homelab. Estado validado em 2026-04-24;
atualização de cenas locais e reauth em **2026-07-27/28**.

## Runbooks de cenas (preferir LAN / `tuya_local`)

| Cena | Doc |
|------|-----|
| Quarto — ciclo fita/spot pelo interruptor | [CENA_QUARTO_TUYA_LOCAL.md](CENA_QUARTO_TUYA_LOCAL.md) |
| Suite — botão do ventilador ↔ lâmpada (relé mini) | [CENA_SUITE_LUZ_TUYA_LOCAL.md](CENA_SUITE_LUZ_TUYA_LOCAL.md) |

**Política operacional (jul/2026):** cenas críticas de luz/ventilador devem usar
entidades `tuya_local` (LAN). A integração cloud `tuya` permanece para sync/self-heal
de `local_key` e dispositivos ainda não migrados; sessão Sharing morre com erro
**1010** e deixa entidades cloud `unavailable` — sintomas típicos: latência alta
ou “funciona às vezes”.

Self-heal e monitor:

- `tools/homelab/tuya_token_selfheal.py` + `tuya-token-selfheal.timer` — renovação proativa + injeção no HA ([vars](variables-taxonomy/TUYA_TOKEN_SELFHEAL.md))
- `tools/homelab/tuya_token_renewer.py` + `tuya-token-renewer.timer` — **monitor** de saúde (não renova); Telegram **somente em erro** ([política](variables-taxonomy/TUYA_TOKEN_RENEWER.md))
- `tools/homelab/tuya_local_key_selfheal.py` + `tuya-local-key-selfheal.timer`
- Reauth QR: `tools/homelab/tuya_reauth_via_authentik.py` / artefatos `artifacts/tuya_reauth_qr_*.png`

**Telegram (renewer, 2026-07-30):** avisos do tipo “⏰ Tuya perto de vencer… ~31 min”
com entidades ativas **não** são enviados. Só falha de entry/HA, 0 entidades
ativas ou token **já expirado**. Janela “perto de vencer” fica só no journal;
o selfheal cobre a renovação.

## Arquitetura

- O Home Assistant roda no container Docker `homeassistant` no host `homelab`.
- O acesso local esta em `http://192.168.15.2:8123`.
- A integracao usada e a Tuya nativa do Home Assistant, autenticada pelo fluxo QR code do app Smart Life/Tuya.
- A VM Home Assistant OS/KVM e o fluxo Zigbee foram descartados para este escopo.

## Estado Atual

- Container `homeassistant`: healthy.
- HTTP local do Home Assistant: `200`.
- Integracao Tuya: 1 config entry ativa.
- Config entry atual: `01KPZQ62H7MSSFEAJAZBCAP3CE`.
- Entidades Tuya registradas: 53.
- Tokens Tuya de curta duracao ficam gerenciados pelo proprio Home Assistant em `.storage`; nao duplicar esses tokens em documentacao.

## Secrets

Os valores sensiveis foram armazenados no Secrets Agent local e espelhados no Authentik. Nao colocar valores em texto claro neste repositorio.

Secrets Agent local vault:

| Nome | Campo | Uso |
|---|---|---|
| `shared/home_assistant_url` | `password` | Compatibilidade com resolvers legados |
| `shared/home_assistant_url` | `url` | URL do Home Assistant |
| `shared/home_assistant_user` | `username` | Usuario local do Home Assistant |
| `shared/home_assistant_password` | `password` | Senha local do Home Assistant |
| `shared/smartlife_tuya_account` | `username` | Conta/titulo da integracao Smart Life/Tuya |
| `shared/smartlife_tuya_account` | `endpoint` | Endpoint Tuya selecionado pelo Home Assistant |
| `shared/smartlife_tuya_account` | `user_code` | User code Tuya usado no pareamento |
| `shared/smartlife_tuya_account` | `ha_config_entry_id` | Config entry da integracao no Home Assistant |

Mirror no Authentik:

| Authentik `client_id` | Origem |
|---|---|
| `secret-homeassistant-url-password` | `shared/home_assistant_url#password` |
| `secret-homeassistant-url` | `shared/home_assistant_url#url` |
| `secret-homeassistant-user` | `shared/home_assistant_user#username` |
| `secret-homeassistant-password` | `shared/home_assistant_password#password` |
| `secret-smartlife-tuya-username` | `shared/smartlife_tuya_account#username` |
| `secret-smartlife-tuya-endpoint` | `shared/smartlife_tuya_account#endpoint` |
| `secret-smartlife-tuya-user-code` | `shared/smartlife_tuya_account#user_code` |
| `secret-smartlife-tuya-ha-entry-id` | `shared/smartlife_tuya_account#ha_config_entry_id` |

Observacao: Authentik 2024.12 nao expoe um vault generico para secrets. O mirror usa providers OAuth2 "secret-holder", um por campo, armazenando o valor em `client_secret` por causa do limite de 255 caracteres. O Secrets Agent local continua sendo o fallback operacional.

## Operacao

Validar Home Assistant:

```bash
ssh homelab 'docker inspect -f "{{.State.Health.Status}}" homeassistant'
ssh homelab 'curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8123/'
```

Validar Tuya sem imprimir secrets:

```bash
ssh homelab 'sudo docker exec homeassistant python3 -c "import json,pathlib; cfg=json.loads(pathlib.Path(\"/config/.storage/core.config_entries\").read_text()); entries=[e for e in cfg[\"data\"][\"entries\"] if e.get(\"domain\")==\"tuya\"]; reg=json.loads(pathlib.Path(\"/config/.storage/core.entity_registry\").read_text()); print(\"tuya_entries\",len(entries)); print(\"tuya_entities\", sum(1 for e in reg[\"data\"][\"entities\"] if e.get(\"platform\")==\"tuya\"))"'
```

Reespelhar secrets do Secrets Agent local para Authentik:

```bash
scp tools/homelab/store_smartlife_secrets_authentik.py homelab:/tmp/store_smartlife_secrets_authentik.py
ssh homelab 'sudo python3 /tmp/store_smartlife_secrets_authentik.py'
```

## Recuperacao Tuya

Use este fluxo quando os dispositivos aparecem offline e o log indicar falha de autenticacao Tuya.

1. Gere backup da configuracao do Home Assistant antes de editar `.storage`.
2. Se a UI ficar presa em reauth antigo, remova a config entry Tuya obsoleta de `/home/homelab/homeassistant/config/.storage/core.config_entries` com o Home Assistant parado.
3. Suba o Home Assistant novamente.
4. Na UI, adicione a integracao `Tuya` do zero.
5. No app Smart Life/Tuya, use o fluxo de QR code atual e finalize a autorizacao antes de clicar em continuar no Home Assistant.
6. Valide `tuya_entries` e `tuya_entities` pelos comandos acima.

Backups relevantes desta recuperacao:

- `/home/homelab/backups/smartlife/homeassistant_before_tuya_entry_reset_.tar.gz`
- `/home/homelab/backups/smartlife/homeassistant_config_before_smartlife_focus_20260424_0851.tar.gz`
