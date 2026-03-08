# 📧 Mailu + Authentik Integration - User Library Access

## ✅ Status: REGISTRADO NA BIBLIOTECA USER

Mailu foi registrado com sucesso como uma aplicação no Authentik e agora aparece na biblioteca de usuários.

---

## 🔗 Acessar Mailu via Authentik

### 1️⃣ **URL da Biblioteca de Usuários**
```
https://auth.rpa4all.com/if/user/#/library
```

### 2️⃣ **Quem Vê?**
- ✅ Membros do grupo: **Email Admins**
- ✅ Membros do grupo: **Email Users**
- ✅ Administradores do Authentik
- ✅ Usuários com permissão padrão (sem restrições)

### 3️⃣ **Como Acessar**

**Passo 1:** Ir para a biblioteca
```
https://auth.rpa4all.com/if/user/#/library
```

**Passo 2:** Procurar por "Mailu Email Server"
```
📧 Mailu Email Server
   "Servidor de email com Roundcube Webmail"
```

**Passo 3:** Clicar no atalho
- ✅ Se você está logado no Authentik
- ✅ Será redirecionado automaticamente para https://mail.rpa4all.com/

**Passo 4:** Login no Webmail (Roundcube)
- Use suas **credenciais de email** (não Authentik)
- Exemplo: `edenilson@rpa4all.com`

---

## 📱 Acessos Diretos (sem vir pela Biblioteca)

| Serviço | URL | Uso |
|---------|-----|-----|
| **Webmail** | https://mail.rpa4all.com/ | Ler/enviar emails |
| **Admin Panel** | https://mail.rpa4all.com/admin/ | Gerenciar usuários, domínios |
| **Biblioteca Authentik** | https://auth.rpa4all.com/if/user/#/library | Launcher de apps |

---

## 🔐 Integração Authentik + Mailu (Detalhes Técnicos)

### Aplicação Registrada

```json
{
  "pk": "7eaa61b5-00e7-4ad8-88ef-5e86c5991f65",
  "name": "Mailu Email Server",
  "slug": "mailu-email",
  "meta_launch_url": "https://mail.rpa4all.com",
  "meta_description": "Servidor de email com Roundcube Webmail"
}
```

### Grupos Associados

| Grupo | UUID | Permissão |
|-------|------|-----------|
| Email Admins | f7672051-f2cb-4190-bb45-3eccef52cdb5 | Admin + Webmail |
| Email Users | ec28d843-42bc-41da-aad9-941fc2020a7f | Webmail apenas |

### Para Ativar SSO Opcional

Se quiser que usuários façam login no Mailu **usando Authentik** (sem digitar senha de email):

**Editar `.env.mailu`:**
```env
ENABLE_OAUTH2=true
OAUTH2_PROVIDER_URL=https://auth.rpa4all.com
OAUTH2_CLIENT_ID=mailu-oauth2-client
OAUTH2_CLIENT_SECRET=your_oauth2_secret_here
```

**Reiniciar:**
```bash
docker-compose -f docker-compose.mailu.yml restart mailu-backend
```

---

## 🚀 Deploy Status

| Componente | Status | Ação |
|-----------|--------|------|
| Authentik Application | ✅ Registrada | - |
| Biblioteca de Usuários | ✅ Configurada | - |
| Mailu Containers | ⏳ Pendente | `python3 deploy_mailu.py` |
| Grafana Dashboard | ✅ Pronto | Importar JSON |

---

## 📋 Checklist de Deployment

- [x] Registrar aplicação no Authentik
- [x] Configurar visibilidade na biblioteca
- [ ] Deploy Mailu containers
- [ ] Criar primeiro domínio de email (rpa4all.com)
- [ ] Criar usuários de teste
- [ ] Testar acesso webmail
- [ ] Configurar DNS MX records
- [ ] Importar dashboard Grafana
- [ ] (Opcional) Ativar SSO com Authentik

---

## 🎯 Próximas Ações

### 1. Deploy Mailu
```bash
python3 deploy_mailu.py
```

**O script vai:**
- Criar uma rede Docker
- Iniciar 7 containers (Postfix, Dovecot, Roundcube, PostgreSQL, Redis, Admin, Exporter)
- Gerar certificados SSL automáticos
- Exibir URLs de acesso

### 2. Criar Domínio de Email
Após deploy:
1. Ir para: https://mail.rpa4all.com/admin/
2. Menu: **Mail Domains** → **New Domain**
3. Adicionar: `rpa4all.com`

### 3. Criar Usuários
1. Menu: **Users** → **New User**
2. Criar usuários como:
   - edenilson@rpa4all.com
   - support@rpa4all.com
   - etc.

### 4. Configurar DNS
Adicionar record MX:
```dns
mail.rpa4all.com.  IN  MX  10  mail.rpa4all.com.
mail.rpa4all.com.  IN  A   <seu-ip>
```

### 5. Testar Acesso via Biblioteca
1. Abrir: https://auth.rpa4all.com/if/user/#/library
2. Localizar: "Mailu Email Server"
3. Clicar
4. Login com email criado na etapa 3

---

## 📊 Monitoramento

O dashboard Grafana para Mailu está pronto para importar:

```bash
# Copiar JSON para Grafana
cp grafana/mailu_monitoring_dashboard.json \
   /var/lib/grafana/dashboards/
```

**Ou via UI:**
- Grafana → Dashboards → Import
- Selecionar arquivo JSON
- Escolher datasource "Prometheus"

**Panels** (8 total):
1. 📧 Fila de emails
2. 📈 Throughput (sent/received)
3. 🔗 Conexões SMTP
4. 👤 Logins IMAP
5. 💾 Storage mailbox
6. ⚠️ Taxa bounce (24h)
7. 📋 Top recipients
8. 🚨 Alertas/erros

---

## 💡 Troubleshooting

### "Mailu não aparece na Biblioteca"
- Verifique se você está no grupo: Email Admins ou Email Users
- Teste com admin do Authentik (sempre vê todas as apps)
- Limpe cache do navegador (Ctrl+Shift+Del)

### "Erro ao tentar acessar desde Biblioteca"
- Verifique se `docker-compose.mailu.yml` está rodando
- Comandos:
  ```bash
  docker-compose -f docker-compose.mailu.yml ps
  docker-compose -f docker-compose.mailu.yml logs -f mailu-frontend
  ```

### "Web page not available (HTTPS error)"
- Aguarde 2-3 min para Let's Encrypt gerar certificado
- Ou verifique porta 80 aberta para ACME

### "Login no Roundcube não funciona"
- Usuário criado no Admin Panel?
- Domínio de email criado?
- Tentou com: `user@dominio.com` (não só `user`)?

---

## 📚 Referências Rápidas

| Recurso | Link |
|---------|------|
| Documentação Mailu | https://mailu.io/ |
| GitHub Mailu | https://github.com/Mailu/Mailu |
| Authentik Docs | https://goauthentik.io/ |
| Docker Compose Mailu | `/home/edenilson/shared-auto-dev/docker-compose.mailu.yml` |
| Deploy Script | `/home/edenilson/shared-auto-dev/deploy_mailu.py` |
| Deployment Guide | `/home/edenilson/shared-auto-dev/MAILU_DEPLOYMENT.md` |

---

## 🎉 Integração Completa!

```
┌─────────────────────────────────────────────┐
│  Authentik (Biblioteca)                     │
│  https://auth.rpa4all.com/if/user/#/library│
│                    ↓                        │
│        Clica em "Mailu Email Server"       │
│                    ↓                        │
│          Redirecionado para                │
│     https://mail.rpa4all.com/              │
│                    ↓                        │
│  Roundcube Webmail (Login com email)       │
│          Ler/Enviar Emails                 │
└─────────────────────────────────────────────┘
```

---

**Status:** ✅ **REGISTRADO**  
**Data:** Março 7, 2026  
**Próximo:** `python3 deploy_mailu.py`
