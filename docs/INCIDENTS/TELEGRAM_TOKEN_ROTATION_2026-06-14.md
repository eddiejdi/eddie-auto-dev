# Incidente — Rotação de Token Telegram com falha silenciosa no Authentik — 2026-06-14

> Diagnóstico e correção da pipeline de rotação automática do token do bot
> `@Proj_Terminal_bot`, cobrindo três falhas encadeadas: Authentik nunca
> atualizado, `--token-file` com expansão bash prematura, e `grep` prefixando
> filename em saída multi-arquivo.

---

## Resumo Executivo

Em 2026-06-14 o bot Telegram retornava 401 Unauthorized apesar de o serviço
`eddie-telegram-bot` estar ativo. A investigação revelou que:

1. O script `eddie-apply-telegram-token.sh` nunca persistia o token no Authentik
   — apenas escrevia drop-ins do systemd. O Authentik continuava com o token
   antigo (inválido) indefinidamente.
2. O script de rotação Selenium usava `"$(cat {token_file})"` no
   `--post-rotate-cmd`, mas o bash expandia `$(cat ...)` **antes** do Python
   substituir `{token_file}`, causando `cat: {token_file}: No such file or
   directory`.
3. O `grep -oP` com múltiplos arquivos no apply script prefixava o resultado
   com `filename:`, tornando `SECRETS_AGENT_API_KEY` inválida (caminho do
   arquivo + valor) — o POST ao secrets agent retornava 401.

A rotação anterior (sessão anterior ao incidente) foi bem-sucedida pelo Chrome
Selenium mas o apply script falhou silenciosamente na etapa do Authentik.
Token correto ficou em `/etc/default/eddie-common`; o Authentik ficou com token
desatualizado. O bot funcionava porque o serviço lia de `/etc/default/eddie-common`.

Correções aplicadas:
- `eddie-apply-telegram-token.sh`: adicionada persistência no Authentik via
  secrets agent
- `eddie-apply-telegram-token.sh`: suporte a `--token-file <path>` para evitar
  expansão bash prematura
- `eddie-apply-telegram-token.sh`: `grep -hoP` para suprimir prefix de filename
- `telegram_botfather_rotate_selenium.py`: adicionado `--extra-chrome-arg` para
  passar proxy Squid ao Chrome

---

## Estado Encontrado

### Sintomas iniciais

- Bot Telegram retornava 401 Unauthorized em todas as chamadas à API
- `systemctl status eddie-telegram-bot` mostrava serviço **ativo**
- Token em Authentik (`authentik/eddie/telegram_bot_token`): `AAG5BrfOsGbV...`
  → API retornava `{"ok": false, "error_code": 401, "description": "Unauthorized"}`

### Divergência de tokens

| Local | Token | Status |
|---|---|---|
| Authentik (secrets agent MCP) | `AAG5BrfOsGbV88BFztljR7fH5ekmszFnulA` | **Inválido** |
| `/etc/default/eddie-common` | `AAH0otoMp3ng8-y6of8uEPquozFjUqPCd5E` | **Válido** |
| `/etc/eddie/telegram.env` | `AAG5BrfOsGbV...` (antigo) | **Inválido** |

O serviço lia de `/etc/default/eddie-common` via drop-in de configuração
alternativo, por isso funcionava. Código que buscava o token do Authentik
recebia o token antigo e falhava.

---

## Causas Raiz

### Causa 1 — Apply script nunca atualizava o Authentik

O `eddie-apply-telegram-token.sh` original:
```bash
# Escrevia apenas /etc/eddie/telegram.env + drop-ins systemd
# Nunca chamava o secrets agent
```

Toda rotação bem-sucedida pelo Selenium resultava em token aplicado nos serviços
mas **não persistido no Authentik**. A cada rotação a divergência crescia.

### Causa 2 — Expansão bash prematura no post-rotate-cmd

O comando de rotação usava:
```bash
--post-rotate-cmd "eddie-apply-telegram-token.sh \"$(cat {token_file})\""
```

O bash executava `$(cat {token_file})` **antes** do Python substituir
`{token_file}` pelo caminho real, resultando em:
```
cat: {token_file}: No such file or directory
```
O post-rotate-cmd era ignorado silenciosamente.

### Causa 3 — grep prefixava filename em saída multi-arquivo

```bash
SECRETS_AGENT_API_KEY=$(
  grep -oP 'SECRETS_AGENT_API_KEY=\K\S+' \
    /etc/systemd/system/secrets-agent.service.d/override.conf \
    /etc/systemd/system/secrets_agent.service.d/override.conf \
    2>/dev/null | head -1
)
```

Com múltiplos arquivos, `grep` prefixava `filename:match`. O resultado era:
```
/etc/systemd/system/secrets-agent.service.d/override.conf:188bbf4c1b43...
```

Em vez de `188bbf4c1b43...`. O POST ao secrets agent retornava 401.

---

## Linha do Tempo

| Hora | Evento |
|---|---|
| Sessão anterior | Rotação Selenium bem-sucedida; token salvo em `eddie-common` mas apply falhou silenciosamente no Authentik |
| 2026-06-14 | Investigação: bot funcionava, mas Authentik retornava token inválido |
| 2026-06-14 | Descoberta: `grep -oP` sem `-h` prefixava filename |
| 2026-06-14 | Fix aplicado: `grep -hoP` + suporte `--token-file` + persistência Authentik |
| 2026-06-14 | Token sincronizado manualmente: secrets agent atualizado com token válido |
| 2026-06-14 | Commits `22f73963` (apply script rewrite) e `23dfedf9` (grep -h fix) |

---

## Correções Aplicadas

### 1. Persistência no Authentik (commit `22f73963`)

```bash
# Adicionado ao final de eddie-apply-telegram-token.sh
_store() {
  local name="$1" field="$2"
  http_code=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${SECRETS_AGENT_URL}/secrets" \
    -H "Content-Type: application/json" \
    -H "x-api-key: ${SECRETS_AGENT_API_KEY}" \
    -d "{\"name\":\"${name}\",\"value\":\"${TOKEN}\",\"field\":\"${field}\"}")
  [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ] || return 1
}
_store "authentik/eddie/telegram_bot_token" "password"
_store "authentik/eddie/telegram_bot_token" "token"
_store "shared/telegram_bot_token"          "password"
_store "shared/telegram_bot_token"          "token"
```

### 2. Suporte a `--token-file` (commit `22f73963`)

```bash
if [ "${1:-}" = "--token-file" ]; then
  TOKEN="$(cat "$2")"
elif [ "$#" -eq 1 ] && [ -n "${1:-}" ]; then
  TOKEN="$1"
fi
```

Permite usar no `--post-rotate-cmd`:
```
/usr/local/bin/eddie-apply-telegram-token.sh --token-file {token_file}
```
O Python substitui `{token_file}` antes da execução; o bash só lê o arquivo
depois que o path é real.

### 3. grep -h para suprimir prefix de filename (commit `23dfedf9`)

```bash
# Antes:
grep -oP 'SECRETS_AGENT_API_KEY=\K\S+' file1 file2 | head -1
# Saída: /path/to/file1:188bbf4c...  ← ERRADO

# Depois:
grep -hoP 'SECRETS_AGENT_API_KEY=\K\S+' file1 file2 | head -1
# Saída: 188bbf4c...  ← CORRETO
```

### 4. --extra-chrome-arg no script de rotação

```bash
--extra-chrome-arg --proxy-server=http://localhost:3128
```

Sem o proxy Squid, o Chrome headless tentava carregar `web.telegram.org`
diretamente, o que causava timeout (118s). Com o proxy, o tráfego passa pelo
ProtonVPN.

---

## Verificação

```bash
# Confirmar token no secrets agent
curl -s http://localhost:8088/secrets/authentik/eddie/telegram_bot_token?field=password \
  -H "x-api-key: $(grep -hoP 'SECRETS_AGENT_API_KEY=\K\S+' \
    /etc/systemd/system/secrets-agent.service.d/override.conf)"

# Confirmar token válido na API Telegram
TOKEN=$(cat /etc/default/eddie-common | grep TELEGRAM | cut -d= -f2)
curl -s "https://api.telegram.org/bot${TOKEN}/getMe" | python3 -m json.tool
```

---

## Regras Estabelecidas

1. **Sempre buscar token do Authentik** via `authentik/eddie/telegram_bot_token`
   — nunca hardcodado ou de arquivo local.
2. **Após qualquer rotação**, verificar com `getMe` que o token persiste no
   Authentik, não apenas em `/etc/default/eddie-common`.
3. **`grep` com múltiplos arquivos** sempre usar `-h` para suprimir prefix de
   filename quando só o valor importa.
4. **`--post-rotate-cmd`** nunca usar `$(cat {token_file})` — usar
   `--token-file {token_file}` para que o Python faça a substituição antes.
