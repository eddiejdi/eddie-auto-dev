# Runbook — Rotação de Token do Bot Telegram

> Bot: `@Proj_Terminal_bot`  
> Script: `/home/homelab/telegram_botfather_rotate_selenium.py`  
> Apply script: `/usr/local/bin/eddie-apply-telegram-token.sh`  
> Token canônico: Authentik via secrets agent `authentik/eddie/telegram_bot_token`

---

## Quando Rotar

- Token retorna 401 Unauthorized na API Telegram
- Rotação preventiva (a cada 90 dias ou por política de segurança)
- Após suspeita de vazamento

---

## Pré-requisitos

| Componente | Caminho | Observação |
|---|---|---|
| Script de rotação | `/home/homelab/telegram_botfather_rotate_selenium.py` | Repo: `scripts/automation/` |
| Apply script | `/usr/local/bin/eddie-apply-telegram-token.sh` | Repo: `scripts/automation/` |
| ChromeDriver | `/home/homelab/.local/bin/chromedriver146` | Chrome 146; chromedriver 148 do PATH é incompatível |
| Chrome | `/opt/google/chrome/chrome` | |
| Python venv | `/home/homelab/myClaude/venv/bin/python3` | |
| Profile bundle | `/home/homelab/telegram_userdata_bundle.tar.gz` | Sessão logada no Telegram Web |
| Xvfb | systemd ou `Xvfb :99 -screen 0 1280x1024x24 &` | Chrome headless ainda precisa de DISPLAY |
| Squid proxy | `localhost:3128` | Para rotear Telegram Web pelo ProtonVPN |

---

## Procedimento

### Passo 1 — Matar Chrome órfão

```bash
ssh homelab@192.168.15.2
kill $(pgrep -f "telegram-rotate-selenium-run") 2>/dev/null || true
```

Sempre executar antes de qualquer tentativa. Chrome da sessão anterior segura
lock do profile dir e impede `_wait_until_logged_in`.

### Passo 2 — Verificar Xvfb

```bash
systemctl status xvfb 2>/dev/null || pgrep Xvfb || echo "Xvfb não está rodando"
# Se necessário:
Xvfb :99 -screen 0 1280x1024x24 &
```

### Passo 3 — Rodar rotação em background

```bash
export DISPLAY=:99
nohup /home/homelab/myClaude/venv/bin/python3 \
  /home/homelab/telegram_botfather_rotate_selenium.py \
  --bot-username Proj_Terminal_bot \
  --profile-dir /home/homelab/.cache/telegram-rotate-selenium-run \
  --profile-archive /home/homelab/telegram_userdata_bundle.tar.gz \
  --profile-archive-clean \
  --headless \
  --timeout-seconds 180 \
  --chrome-binary /opt/google/chrome/chrome \
  --chromedriver-path /home/homelab/.local/bin/chromedriver146 \
  --output-token-file /tmp/new_tg_token \
  --extra-chrome-arg --proxy-server=http://localhost:3128 \
  --post-rotate-cmd '/usr/local/bin/eddie-apply-telegram-token.sh --token-file {token_file}' \
> /tmp/telegram-rotate.log 2>&1 &
echo "PID: $!"
```

### Passo 4 — Monitorar

```bash
tail -f /tmp/telegram-rotate.log
```

Aguardar uma das mensagens:
- `Token rotacionado com sucesso` — prosseguir para verificação
- `TimeoutException` / `ElementNotFound` — ver seção de troubleshooting

### Passo 5 — Verificar

```bash
# Token novo está no arquivo?
cat /tmp/new_tg_token

# Token válido na API Telegram?
TOKEN=$(cat /tmp/new_tg_token)
curl -s "https://api.telegram.org/bot${TOKEN}/getMe" | python3 -m json.tool

# Token no Authentik bate com o novo?
API_KEY=$(grep -hoP 'SECRETS_AGENT_API_KEY=\K\S+' \
  /etc/systemd/system/secrets-agent.service.d/override.conf)
curl -s "http://localhost:8088/secrets/authentik/eddie/telegram_bot_token?field=password" \
  -H "x-api-key: $API_KEY"
```

O token em Authentik deve ser idêntico ao de `/tmp/new_tg_token`.

### Passo 6 — Sincronização manual (se necessário)

Se o apply script falhou silenciosamente (checar log), rodar manualmente:

```bash
/usr/local/bin/eddie-apply-telegram-token.sh --token-file /tmp/new_tg_token
```

Saída esperada:
```
[1/2] Systemd drop-ins aplicados.
[2/2] Persistindo token no Authentik...
  OK authentik/eddie/telegram_bot_token#password
  OK authentik/eddie/telegram_bot_token#token
  OK shared/telegram_bot_token#password
  OK shared/telegram_bot_token#token
Token aplicado e persistido no Authentik com sucesso.
```

---

## Troubleshooting

### TimeoutException (118s ao carregar Telegram Web)

Causa: Chrome não está usando o proxy Squid para rotear via ProtonVPN.

Verificar:
```bash
grep -i proxy /tmp/telegram-rotate.log
```

Fix: confirmar que `--extra-chrome-arg --proxy-server=http://localhost:3128` está
presente no comando. Verificar se o Squid está rodando:
```bash
systemctl status squid
curl -sx http://localhost:3128 https://web.telegram.org/ -o /dev/null -w "%{http_code}"
```

---

### ElementNotFound / seletores errados

Causa provável: versão desatualizada do script no homelab (sem sync com o repo).

```bash
# No dev:
scp scripts/automation/telegram_botfather_rotate_selenium.py \
  homelab:/home/homelab/telegram_botfather_rotate_selenium.py
```

---

### Token rotacionado mas bot com 401

Causa: apply script falhou ao persistir no Authentik.

Diagnóstico:
```bash
grep -i "FALHA\|Error\|error" /tmp/telegram-rotate.log
```

Fix:
```bash
/usr/local/bin/eddie-apply-telegram-token.sh --token-file /tmp/new_tg_token
```

---

### "Operation not permitted" ao matar Chrome

`pkill -9 chrome` falha para processos de outros usuários (ex.: kiosk, root).
Usar `pgrep -f telegram-rotate-selenium-run` para matar apenas os do usuário
`homelab`.

---

### SECRETS_AGENT_API_KEY vazia ou com path no início

Causa: `grep -oP` (sem `-h`) com múltiplos arquivos prefixava o resultado com
`filename:`.

```bash
# Diagnóstico:
grep -oP 'SECRETS_AGENT_API_KEY=\K\S+' \
  /etc/systemd/system/secrets-agent.service.d/override.conf \
  2>/dev/null
# Saída ERRADA: /etc/systemd/system/...:188bbf4c...

# Correto:
grep -hoP 'SECRETS_AGENT_API_KEY=\K\S+' \
  /etc/systemd/system/secrets-agent.service.d/override.conf \
  2>/dev/null
# Saída CORRETA: 188bbf4c...
```

O apply script atual (repo) já usa `-h`. Garantir que o homelab tem a versão
atualizada.

---

### DISPLAY vazio (Chrome não inicia)

```bash
export DISPLAY=:99
# ou garantir que Xvfb está ativo antes de rodar
```

---

## Apply Script — Referência Rápida

Script: `/usr/local/bin/eddie-apply-telegram-token.sh`  
Repo: `scripts/automation/eddie-apply-telegram-token.sh`

**Uso:**
```bash
# Token direto:
eddie-apply-telegram-token.sh "1234567890:AAH..."

# Token em arquivo (usar com {token_file} do script de rotação):
eddie-apply-telegram-token.sh --token-file /tmp/new_tg_token
```

**O que faz:**
1. Escreve `/etc/eddie/telegram.env` com `TELEGRAM_BOT_TOKEN=<TOKEN>`
2. Cria drop-ins em `/etc/systemd/system/<service>.service.d/override.conf`
   para: `eddie-telegram-bot`, `eddie-expurgo`, `eddie-calendar`,
   `homelab-dashboard`, `eddie-location`
3. Recarrega e habilita os serviços
4. Chama `POST http://localhost:8088/secrets` para persistir em Authentik em
   dois paths: `authentik/eddie/telegram_bot_token` e `shared/telegram_bot_token`

**Secrets agent — API key:**
```bash
grep -hoP 'SECRETS_AGENT_API_KEY=\K\S+' \
  /etc/systemd/system/secrets-agent.service.d/override.conf
```

---

## Armadilhas Conhecidas

| # | Armadilha | Fix |
|---|---|---|
| 1 | Chrome órfão segura lock do profile dir | `kill $(pgrep -f telegram-rotate-selenium-run)` antes de qualquer rotação |
| 2 | Seletores CSS errados na versão antiga do homelab | Sempre sincronizar do repo antes de rodar |
| 3 | ChromeDriver 148 incompatível com Chrome 146 | Sempre usar `--chromedriver-path /home/homelab/.local/bin/chromedriver146` |
| 4 | Profile sem sessão válida após reboot | Sempre passar `--profile-archive` + `--profile-archive-clean` |
| 5 | `post_rotate_cmd` não configurado | Sempre passar `--post-rotate-cmd` explicitamente |
| 6 | Apply script original não salvava no Authentik | Apply script reescrito (commit `22f73963`); deploy no homelab obrigatório |
| 7 | `grep -oP` prefixava filename em saída multi-arquivo | Usar `grep -hoP`; corrigido em commit `23dfedf9` |
| 8 | Token em `/etc/default/eddie-common` pode divergir do Authentik | Após rotação, verificar com `getMe` E checar secrets agent |
| 9 | `$(cat {token_file})` expande prematuramente no bash | Usar `--token-file {token_file}` no post-rotate-cmd |
| 10 | DISPLAY vazio — Chrome não inicia em headless | `export DISPLAY=:99` antes de qualquer chamada |
| 11 | Telegram Web timeout sem proxy | Passar `--extra-chrome-arg --proxy-server=http://localhost:3128` |
