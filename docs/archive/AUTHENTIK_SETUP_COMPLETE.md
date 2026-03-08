# 🔐 Authentik SSO - Setup Completo

**Data:** 7 de março de 2026  
**Status:** ✅ Configuração Finalizada  

---

## ✅ Etapas Concluídas

### 1. Grupos Criados no Authentik

| Grupo | Descrição |
|-------|-----------|
| `Grafana Admins` | Acesso Admin ao Grafana |
| `Grafana Users` | Acesso User/Viewer ao Grafana |
| `Nextcloud Admins` | Acesso Admin ao Nextcloud |
| `Nextcloud Users` | Acesso User ao Nextcloud |
| `OpenWebUI Admins` | Acesso Admin ao OpenWebUI |
| `OpenWebUI Users` | Acesso User ao OpenWebUI |

### 2. Usuários Configurados

#### 👤 **edenilson** (pk=7)
- **Email:** edenilson.paschoa@rpa4all.com
- **Status:** ✅ Ativo
- **Grupos:**
  - ✅ Grafana Admins → Admin no Grafana
  - ✅ Nextcloud Users → User no Nextcloud
  - ✅ OpenWebUI Users → User no OpenWebUI
- **Permissions:** Acesso completo Grafana, acesso básico Nextcloud/OpenWebUI

#### 👤 **homelab** (pk=8) [NOVO]
- **Email:** homelab@rpa4all.com
- **Senha:** `HomeLabService2026!` (⚠️ alterar em produção)
- **Status:** ✅ Ativo
- **Grupos:**
  - ✅ Grafana Admins → Admin no Grafana
  - ✅ Nextcloud Admins → Admin no Nextcloud
  - ✅ OpenWebUI Admins → Admin no OpenWebUI
- **Permissions:** Acesso admin em tudo

### 3. Scripts de Gerenciamento Criados

Localizados em: `/tools/authentik_management/`

- **authentik_user_manager.py** - Gerenciador de usuários via Python API
- **authentik_cli.sh** - CLI Bash para operações com Authentik
- **authentik_django_shell.sh** - Acesso direto via Django Shell
- **setup_groups_users.py** - Script de setup inicial

---

## 🚀 Configuração das Ferramentas

### 1️⃣ GRAFANA - OAuth2/Generic OAuth

**Arquivo:** `/home/homelab/docker-compose.yml` ou `.env`

```yaml
services:
  grafana:
    environment:
      # ─── OAuth2 - Authentik ─────────────────
      GF_AUTH_GENERIC_OAUTH_ENABLED: "true"
      GF_AUTH_GENERIC_OAUTH_ALLOW_SIGN_UP: "true"
      GF_AUTH_GENERIC_OAUTH_CLIENT_ID: "authentik-grafana"
      GF_AUTH_GENERIC_OAUTH_CLIENT_SECRET: "grafana-sso-secret-2026"
      GF_AUTH_GENERIC_OAUTH_SCOPES: "openid profile email groups"
      GF_AUTH_GENERIC_OAUTH_AUTH_URL: "https://auth.rpa4all.com/application/o/authorize/"
      GF_AUTH_GENERIC_OAUTH_TOKEN_URL: "https://auth.rpa4all.com/application/o/token/"
      GF_AUTH_GENERIC_OAUTH_API_URL: "https://auth.rpa4all.com/application/o/userinfo/"
      
      # ─── Role Mapping ────────────────────────
      GF_AUTH_GENERIC_OAUTH_ROLE_ATTRIBUTE_PATH: "groups[0]"
      GF_AUTH_GENERIC_OAUTH_ROLE_ATTRIBUTE_STRICT: "false"
      
      # ─── SSL ──────────────────────────────────
      GF_AUTH_GENERIC_OAUTH_INSECURE_SKIP_VERIFY: "true"
      
      # ─── Branding ─────────────────────────────
      GF_AUTH_GENERIC_OAUTH_NAME: "Authentik"
      GF_AUTH_GENERIC_OAUTH_ICON: "signin"
```

**Fluxo:**
```
1. Usuário clica "Authentik" no login do Grafana
2. Redireciona para: https://auth.rpa4all.com/application/o/authorize/
3. Usuário autentica no Authentik
4. Retorna com JWT token + grupos
5. Grafana lê grupos[0] e atribui role:
   - "Grafana Admins" → Admin
   - "Grafana Users" → Viewer
6. Usuário logado ✅
```

**Após aplicar:**
```bash
docker-compose restart grafana
# Testar: https://grafana.rpa4all.com → Login → Clique "Authentik"
```

---

### 2️⃣ NEXTCLOUD - OIDC (user_oidc v8.5.0)

**Arquivo:** `/var/www/html/config/config.php`

```php
'oidc_login_provider_url' => 'https://auth.rpa4all.com/application/o/nextcloud/',
'oidc_login_client_id' => 'authentik-nextcloud',
'oidc_login_client_secret' => 'nextcloud-sso-secret-2026',
'oidc_login_scopes' => 'openid profile email',
'oidc_login_button_text' => 'Log in with Authentik',
'oidc_login_hide_password_form' => false,  // Manter para fallback
'oidc_login_use_access_token_payload' => false,
'oidc_create_groups' => true,  // Criar grupos automaticamente
'oidc_login_default_group' => 'users',
'oidc_login_logout_url' => 'https://auth.rpa4all.com/application/o/token/revoke/',
```

**Setup:**
```bash
# 1. SSH no servidor
ssh homelab@192.168.15.2

# 2. Editar config.php
docker exec -it nextcloud sh
# Ou via arquivo:
nano /var/www/html/config/config.php

# 3. Ativar app user_oidc
# Via Admin → Apps → "user_oidc" → Enable
# Ou via CLI:
docker exec nextcloud php occ app:enable user_oidc

# 4. Reiniciar
docker-compose restart nextcloud
```

**Após aplicar:**
```
Testar: https://nextcloud.rpa4all.com → Clicar "Log in with Authentik"
```

---

### 3️⃣ OPENWEBUI - OIDC Configuration

**Arquivo:** `docker-compose.yml` ou `.env`

```yaml
services:
  open-webui:
    environment:
      # ─── OIDC ─────────────────────────────────
      WEBUI_AUTH_PROVIDER: "oidc"
      OIDC_PROVIDER_URL: "https://auth.rpa4all.com/application/o/openwebui/"
      OIDC_CLIENT_ID: "authentik-openwebui"
      OIDC_CLIENT_SECRET: "openwebui-sso-secret-2026"
      OIDC_SCOPES: "openid profile email"
      OIDC_AUTHORIZATION_ENDPOINT: "https://auth.rpa4all.com/application/o/authorize/"
      OIDC_TOKEN_ENDPOINT: "https://auth.rpa4all.com/application/o/token/"
      OIDC_USERINFO_ENDPOINT: "https://auth.rpa4all.com/application/o/userinfo/"
      
      # ─── Group-based Roles ─────────────────
      OIDC_GROUP_CLAIM: "groups"
      OIDC_ADMIN_GROUP: "OpenWebUI Admins"
      OIDC_USER_GROUP: "OpenWebUI Users"
      
      # ─── Behavior ──────────────────────────────
      OIDC_AUTO_CREATE_USER: "true"
      OIDC_AUTO_ADD_USER_TO_GROUP: "true"
```

**Setup:**
```bash
# Editar docker-compose.yml e adicionar as variáveis acima
docker-compose restart open-webui

# Testar: https://openwebui.rpa4all.com → Login → Botão "OIDC"
```

---

## 📋 Checklist de Verificação

### Grafana
- [ ] OAuth2 ativado em `Admin → Configuration → OAuth`
- [ ] Botão "Authentik" aparece no login
- [ ] Login com edenilson mostra role "Admin"
- [ ] Data source Grafana Admins mapeado para Admin
- [ ] Novo usuário via OIDC cria conta automaticamente

### Nextcloud
- [ ] user_oidc app instalado e ativado
- [ ] Login com "Log in with Authentik" funciona
- [ ] Primeiro login cria conta automaticamente
- [ ] Grupos do Authentik aparecem em Nextcloud
- [ ] edenilson recebe acesso básico de user

### OpenWebUI
- [ ] OIDC login disponível
- [ ] homelab é Admin automaticamente
- [ ] edenilson é User automaticamente
- [ ] Novo usuário via OIDC recebe role baseado em grupo

---

## 🔗 Links e Referências

| Recurso | URL/Comando |
|---------|-------------|
| **Authentik Admin Console** | https://auth.rpa4all.com/if/admin/ |
| **Grafana Dashboard** | https://grafana.rpa4all.com |
| **Nextcloud** | https://nextcloud.rpa4all.com |
| **OpenWebUI** | https://openwebui.rpa4all.com |
| **User Management Scripts** | `/tools/authentik_management/` |

---

## 🔐 Credenciais e Secrets

> ⚠️ **NUNCA commitar secrets em texto claro!**

| Secret | Local | Status |
|--------|-------|--------|
| `akadmin` password | vault:authentik-admin-password | ✅ Vault |
| `edenilson` password | vault:authentik-edenilson-password | ✅ Vault |
| `homelab` password | ⚠️ ALTERAR em produção | 🔴 Temporária |
| OAuth2 secrets | vault:authentik-{app}-client-secret | ✅ Vault |
| Grafana OAuth secret | vault:grafana-oauth-client-secret | ✅ Vault |
| Nextcloud OAuth secret | vault:nextcloud-oauth-client-secret | ✅ Vault |
| OpenWebUI OAuth secret | vault:openwebui-oauth-client-secret | ✅ Vault |

---

## 🐛 Troubleshooting

### Problema: "Invalid credentials" ao logar via OAuth

**Solução:**
```bash
# 1. Verificar Authentik user está ativo
docker exec authentik-server ak shell -c "from authentik.core.models import User; User.objects.filter(username='edenilson')"

# 2. Resetar senha Grafana se necessário
docker exec grafana grafana cli admin reset-admin-password NEWPASS

# 3. Limpar cookies do navegador e tentar novamente
```

### Problema: Grupos não aparecem em OIDC token

**Solução:**
1. Verificar em Authentik → Applications → [App] → Provider
2. Confirmar "groups" está em Scopes/Claims
3. Verificar Property Mappings tem "groups" incluído
4. Testar endpoint: `https://auth.rpa4all.com/application/o/[app]/userinfo/`

### Problema: HTTPS certificate error

**Solução:**
```bash
# Grafana:
GF_AUTH_GENERIC_OAUTH_INSECURE_SKIP_VERIFY=true  ✅

# Nextcloud:
'oidc_verify_ssl' => false,  # config.php

# OpenWebUI:
OIDC_VERIFY_SSL=false  # .env
```

> ⚠️ Para produção: Usar certificado válido (Let's Encrypt)

---

## 📈 Próximas Melhorias

- [ ] Implementar MFA (Multi-Factor Authentication) no Authentik
- [ ] Criar políticas de acesso por serviço (Access Policies)
- [ ] Setup Syslog centralizado para audit de logins
- [ ] Configurar backup automático de banco Authentik
- [ ] Monitorar falhas de login com alertas
- [ ] Implementar provisioning automático de apps

---

## 📞 Suporte

Para dúvidas ou problemas:
1. Consultar Authentik docs: https://goauthentik.io/docs/
2. Verificar logs: `docker logs authentik-server`
3. Acessar Authentik admin console e revisar Configuration

---

**Última atualização:** 2026-03-07  
**Próxima revisão:** Quando adicionar novo serviço ao SSO
