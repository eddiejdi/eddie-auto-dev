# Incidente 2026-08-10 — Login Grafana via Authentik falhando

## Resumo

Usuário não conseguia logar no **Grafana** pelo botão "Authentik" (SSO OAuth2/OIDC via
Authentik). Sintomas evoluíram durante o diagnóstico:

1. Na página de login do Authentik: **"Invalid password"** mesmo com senha correta.
2. Após reset de senha: **"Login failed / Sign up is disabled"** na tela do Grafana.

**Causa raiz final:** multiplas causas encadeadas (senha desatualizada no Authnentik +
config de sign-up do Grafana divergente + bind OAuth `auth_id` desatualizado).
No **após** também descobrimos e corrigimos o **approval-gateway em crash loop**, que
impedia o fluxo de aprovação via Telegram.

Visão do incidente em orquestrações: `intent-20260810-190413-fd641b`,
`intent-20260810-210530-fecbdf`, `intent-20260810-212204-b90f06`.

---

## 1. "Invalid password" mesmo com senha correta

### Diagnóstico

- Verificado que `auth.rpa4all.com` e `grafana.rpa4all.com` respondiam 200.
- Provider OAuth2 `authentik-grafana` no Authentik: `client_id`, `client_secret`
  (`grafana-sso-secret-2026`, igual no DB e no env do Grafana), redirect URI
  `https://grafana.rpa4all.com/login/generic_oauth` (strict), receptor, autorização
  `implicit-consent` — **tudo íntegro**.
- Token endpoint aceita o client (`invalid_grant`, não `invalid_client`) → credenciais
  OAuth corretas.
- Fluxo de autenticação: identification → password → MFA validation → login, estágios
  íntegros, sem policies bloqueando.
- Usuário `edenilson.paschoa` ativo, porém **último login no Authentik 2026-04-11**.
- Teste com senha errada retornou exatamente `Invalid password`; teste com senha
  resetada retornou `Successful authentication` via `InbuiltBackend`.

### Conclusão

O **hash de senha armazenado no Authentik** para o usuário estava desatualizado/divergente
da senha que o dono usava (coerente com último login em abril). **Não era bug no fluxo OAuth.**

### Correção

```bash
docker exec authentik-server ak shell -c "
from authentik.core.models import User
u = User.objects.get(username='edenilson.paschoa')
u.set_password('NOVA_SENHA')   # senha temporária; dono troca no perfil
u.save()
"
```

O dono deve trocar a senha temporária em `https://auth.rpa4all.com` → perfil → *Change password*.

---

## 2. "Login failed / Sign up is disabled" (Grafana)

Após reset da senha, o Authentik autenticava, mas o callback do Grafana falhava.

### Causas (3) e correções

1. **Sign-up OAuth desabilitado no deploy** — o compose
   `/home/homelab/monitoring/docker-compose.grafana.yml` tinha
   `GF_AUTH_GENERIC_OAUTH_ALLOW_SIGN_UP=false` (divergiu do repo canônico, que tem `true`).
   Alinhado para `true` (+ `GF_USERS_ALLOW_SIGN_UP=true`, `GF_USERS_AUTO_ASSIGN_ORG=true`)
   e container recriado:

   ```bash
   cd /home/homelab/monitoring
   docker compose -f docker-compose.grafana.yml up -d --no-deps grafana
   ```

2. **Bind OAuth `auth_id` desatualizado** — o `sub` emitido pelo Authentik mudou
   (bind antigo `80b173…` de 2026-08-09 → atual `7211d880…`). O Grafana não achava o
   `user_auth` e falhava com `unable to create user: user not found`. Alinhado:

   ```sql
   UPDATE user_auth SET auth_id='7211d88066bf25d5062454a2e8bb8a80bea6a228409f18002ac11e62a380dc1f'
   WHERE user_id=2;  -- edenilson.paschoa@rpa4all.com
   ```

3. **Role** — confirmado que o usuário pertence ao grupo `Grafana Admins` no Authentik
   e o scope `profile` entrega `groups`; logo
   `GF_AUTH_GENERIC_OAUTH_ROLE_ATTRIBUTE_PATH=contains(groups[*],'Grafana Admins') && 'Admin'`
   mapeia **Admin**.

---

## 3. Approval Gateway em crash loop (callback do Telegram sem botões)

Durante a aprovação do reset, o `approval-gateway.service` estava **failed** há ~2h:

```
ago 10 14:01:02 homelab systemd[1]: approval-gateway.service: Start request repeated too quickly.
```

### Causa

A unit referenciava `postgresql.service` (inexistente neste host — o PostgreSQL roda via
container `eddie-postgres.service`, porta 5433). O gateway conectava antes do container
estar pronto no boot, esgotava o `StartLimitBurst` e o systemd **desistia** de reiniciar.
Como o polling do bot é feito pelo `eddie-telegram-bot`, os botões ✅/❌ nunca chegavam ao usuario.

### Correção

Drop-in `/etc/systemd/system/approval-gateway.service.d/depend-postgres.conf` (versionado em
`systemd/approval-gateway.service.d/depend-postgres.conf`):

```ini
[Unit]
After=eddie-postgres.service
Requires=eddie-postgres.service
StartLimitBurst=20
StartLimitIntervalSec=300

[Service]
ExecStartPre=/bin/sh -c 'for i in $(seq 1 30); do pg_isready -h 192.168.15.2 -p 5433 -q && exit 0; sleep 2; done; exit 1'
```

Unit canônica `systemd/approval-gateway.service` também atualizada
(`After=… eddie-postgres.service` + `Requires=eddie-postgres.service`).

### Falha adicional: callbacks não eram roteados

O `telegram_bot.py` declarava `allowed_updates=["message","callback_query"]`, mas
**descartava** `callback_query`. Foi adicionado roteamento para
`approval_gateway.handle_telegram_callback_query()` (nova função pública no
`specialized_agents/approval_gateway.py`), que executa o `_on_callback` com o mesmo boot
de env do gateway. Sem isso, mesmo clicando "Aprovar" nada acontecia.

---

## 4. Token API do Authentik expirado (acompanhante)

- O token hardcoded em scripts (`ak-homelab-authentik-api-2026`) **não existe no DB** do
  Authentik e retorna `403 Token invalid/expired`. O `secrets_agent` também usava esse
  valor stale → backend `unavailable` (servindo cache).
- Criado token persistente novo via shell:

```bash
docker exec authentik-server ak shell -c "
from authentik.core.models import Token, User
t = Token.objects.create(
    identifier='homelab-api-2026',
    user=User.objects.get(username='akadmin'),
    expiring=False,
    intent='api',            # obrigatório para auth via Bearer (TokenIntents.INTENT_API)
    description='API token homelab',
)
print(t.key)
"
```

- `AUTHENTIK_TOKEN` atualizado em `/etc/systemd/system/secrets_agent.service.d/override.conf`
  → backend do secrets_agent voltou para `available`.
- **Entrada do vault `authentik/api_token` atualizada**: o `local_vault` do secrets_agent
  (em `/var/lib/eddie/secrets_agent/local_vault/`) guarda valores criptografados
  (XOR + HMAC com passphrase). A entrada foi re-gravada com o token novo usando a mesma
  rotina do `LocalVault.store()` → `homelab_secrets_get('authentik/api_token')` agora
  retorna o token válido.
- **Scripts des-hardcodados**: criados `tools/authentik_management/authentik_token.py` e
  `authentik_token.sh` que resolvem o token sem segredo no código — ordem:
  env `AUTHENTIK_TOKEN` → `/etc/systemd/system/secrets_agent.service.d/override.conf`
  (homelab, canônico) → secrets_agent `localhost:8088/secrets/authentik/api_token`.
  Todos os scripts que usavam `ak-homelab-authentik-api-2026` foram atualizados
  (`authentik_cli.sh`, `authentik_user_manager.py`, `setup_authentik_sso.py`,
  `configure_authentik_nextcloud_oidc.py`, `register_nextcloud_access_panel.py`,
  `fix_openwebui_oauth.py`, `restore_grafana_authentik_login.py`,
  `register_{ntopng,cmdb,mailu,wallpapers}_authentik.sh`,
  `register_mailu_authentik.py`, `specialized_agents/user_management.py`).

---

## 5. `authentik-ldap-outpost` unhealthy (acompanhante)

- Container estava `unhealthy` há horas: `403 Forbidden` ao buscar config no Authentik
  (`/api/v3/outposts/instances/`) e healthcheck do `/ldap ping` recusando conexão.
- Causa: o `AUTHENTIK_TOKEN` do container apontava para um token inexistente
  (`ak-outpost-25449a4e-…-key`), enquanto o token real do LDAP Outpost
  (`ak-outpost-4f9bdb8d-8a91-4c20-b6e2-507d02959b44-api`) existe e é válido no DB.
- Correção: recriado o container com o `AUTHENTIK_TOKEN` correto:

```bash
TOK=$(docker exec authentik-postgres psql -q -U authentik -d authentik -t -A \
  -c "SELECT key FROM authentik_core_token WHERE identifier='ak-outpost-4f9bdb8d-8a91-4c20-b6e2-507d02959b44-api';")
docker rm -f authentik-ldap-outpost
docker run -d --name authentik-ldap-outpost --restart unless-stopped \
  -p 389:3389 -p 636:6636 \
  -e AUTHENTIK_HOST=http://172.17.0.1:9000 -e AUTHENTIK_INSECURE=true \
  -e "AUTHENTIK_TOKEN=$TOK" ghcr.io/goauthentik/ldap:2024.12
```

- Resultado: container **healthy**, websocket conectado, LDAP (`3389`) e LDAPS (`6636`)
  e métricas (`9300`) de pé.

---

## 6. Datasource/dashboard Grafana do Authentik (pendência conhecida)

`grafana/provisioning/datasources/authentik-http.yaml` e
`grafana/authentik_admin_dashboard.json` ainda embutem o token antigo como valor do
header `Bearer` (datasource HTTP "authentik-http" e dashboards que consultam a API do
Authentik). **Não** será embutido o token novo no repo por política de secrets.
Deve migrar para `secureJsonData` + env no deploy.

---

## Arquivos alterados (commit)

| Arquivo | Mudança |
|---------|---------|
| `specialized_agents/approval_gateway.py` | `handle_telegram_callback_query()` entry-point |
| `telegram_bot.py` | roteamento de `callback_query` → approval_gateway |
| `systemd/approval-gateway.service` | dependência `eddie-postgres.service` |
| `systemd/approval-gateway.service.d/depend-postgres.conf` | novo drop-in (wait + burst) |
| `tools/authentik_management/authentik_token.py` | helper de resolução do token (novo) |
| `tools/authentik_management/authentik_token.sh` | helper de resolução do token (novo) |
| `tools/authentik_management/*.py` + `*.sh` | des-hardcode do token (env/override/secrets) |
| `scripts/misc/register_*_authentik.sh`, `scripts/automation/fix_openwebui_oauth.py`, `scripts/training/register_mailu_authentik.py`, `specialized_agents/user_management.py`, `tools/setup_authentik_sso.py` | des-hardcode do token |
| `docs/INCIDENTS/2026-08-10_GRAFANA_AUTHENTIK_LOGIN_AND_APPROVAL_GATEWAY.md` | este documento |

Deploy (homelab):
- `/home/homelab/monitoring/docker-compose.grafana.yml` (sign-up OAuth)
- `/etc/systemd/system/approval-gateway.service.d/depend-postgres.conf`
- `/home/homelab/myClaude/specialized_agents/approval_gateway.py`
- `/home/homelab/myClaude/telegram_bot.py`
- `/etc/systemd/system/secrets_agent.service.d/override.conf` (AUTHENTIK_TOKEN)
- container `authentik-ldap-outpost` recriado com token correto

## Pendências

- [x] Rotacionar senha temporária do usuário (dono define definitiva).
- [x] Approval gateway resiliente ao boot do Postgres.
- [x] Botões de aprovação do Telegram passam a funcionar.
- [x] Token API do Authentik válido + secrets_agent backend `available`.
- [x] Atualizar scripts que hardcodam `ak-homelab-authentik-api-2026` (helpers de resolução).
- [x] Investigar `authentik-ldap-outpost` unhealthy → container recriado com token correto.
- [x] Atualizar entrada no vault `authentik/api_token` (local_vault re-gravado).
- [ ] Migrar datasource/dashboard Grafana do Authentik para `secureJsonData` + env
      (hoje embutem o token antigo; não embutir o novo por política).