# 📧 Mailu Email Server - Setup Rápido

Seu homelab agora tem um **servidor de email completo** com webmail integrado!

## 📦 Arquivos Criados

```
📁 Raiz do projeto:
├── docker-compose.mailu.yml          ← Docker Compose (7 serviços)
├── .env.mailu                        ← Variáveis de configuração
├── deploy_mailu.py                   ← Script de deployment automático
├── MAILU_DEPLOYMENT.md               ← Documentação completa

📁 grafana/:
└── mailu_monitoring_dashboard.json   ← Dashboard Grafana (8 panels)
```

## 🚀 Quick Start (5 minutos)

### Opção 1: Automático (Recomendado)
```bash
# Fazer script executável
chmod +x deploy_mailu.py

# Executar deployment interativo
python3 deploy_mailu.py

# Ou não-interativo
python3 deploy_mailu.py --non-interactive \
  --domain mail.rpa4all.com \
  --admin-email admin@mail.rpa4all.com
```

### Opção 2: Manual
```bash
# 1. Editar configuração
nano .env.mailu

# 2. Gerar chaves seguras
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"

# 3. Criar rede (se não existe)
docker network create homelab_monitoring

# 4. Deploy
docker-compose -f docker-compose.mailu.yml up -d

# 5. Verificar status
docker-compose -f docker-compose.mailu.yml ps
```

## 🌐 Acessos

| Serviço | URL | Usuário | Senha |
|---------|-----|---------|-------|
| **Admin Panel** | `https://mail.rpa4all.com/admin/` | `admin@mail.rpa4all.com` | Na primeira execução |
| **Webmail** | `https://mail.rpa4all.com/` | Criar usuários no admin | Sua senha |
| **Grafana** | `http://192.168.15.2:3002/` | Via OAuth Authentik | - |

## 📊 Monitoramento

### Dashboard Grafana (8 Panels)
✅ **Criado e pronto para importar:**

```bash
# Via CLI - Copiar arquivo JSON
cp grafana/mailu_monitoring_dashboard.json \
   /var/lib/grafana/dashboards/

# Via Web - Grafana → Dashboards → Import
# Arquivos → Selecionar mailu_monitoring_dashboard.json
```

**Panels:**
1. 📧 Fila de Emails (Gauge)
2. 📈 Throughput (Sent/Received)
3. 🔗 Conexões SMTP
4. 👤 Logins IMAP (Success/Failed)
5. 💾 Armazenamento Mailbox (Pie)
6. ⚠️ Taxa de Bounce (24h)
7. 📋 Top 10 Recipients
8. 🚨 Alertas & Erros (Logs)

### Métricas Prometheus

**Disponíveis automaticamente:**
- `postfix_queue_size`
- `postfix_emails_sent_total`
- `postfix_emails_received_total`
- `postfix_smtp_connections_total`
- `imap_logins_success_total`
- `imap_logins_failed_total`

**Porta:** `9307` (postfix-exporter)

## 🔧 Serviços Docker

| Serviço | Imagem | Função |
|---------|--------|--------|
| **mailu-db** | postgres:15 | Banco de dados PostgreSQL |
| **mailu-redis** | redis:7 | Cache Redis |
| **mailu-backend** | mailu/admin:2.0 | API e Admin Panel |
| **mailu-frontend** | mailu/nginx:2.0 | Proxy reverso (HTTP/SMTP/IMAP) |
| **mailu-postfix** | mailu/postfix:2.0 | Servidor SMTP |
| **mailu-dovecot** | mailu/dovecot:2.0 | Servidor IMAP/POP3 |
| **mailu-roundcube** | mailu/roundcube:2.0 | Webmail em PHP |
| **postfix-exporter** | boynux/postfix-exporter | Métricas Prometheus |

## 📍 Integração com Infraestrutura Existente

### ✅ Com Authentik (SSO)
Comentado no `.env.mailu`. Para ativar:

```env
ENABLE_OAUTH2=true
OAUTH2_PROVIDER_URL=https://auth.rpa4all.com
OAUTH2_CLIENT_ID=mailu-client
OAUTH2_CLIENT_SECRET=your_oauth2_secret
```

Depois: `docker-compose -f docker-compose.mailu.yml restart mailu-backend`

### ✅ Com Grafana
Dashboard Mailu incluso na pasta `grafana/`. 
Import como dashboard normal.

### ✅ Com Prometheus
Prometheus scrapeará automaticamente em:
- http://postfix-exporter:9307/metrics

Adicionar a jobs.yml do Prometheus (opcional):
```yaml
- job_name: 'mailu-postfix'
  static_configs:
    - targets: ['localhost:9307']
```

### ✅ Com Loki (Logs Centralizados)
Logs disponíveis via `docker logs mailu-*`.
Para enviar a Loki, configure fluent-bit (veja MAILU_DEPLOYMENT.md).

## 🔐 Segurança

⚠️ **Obrigatório Após Deploy:**

1. **Mudar senhas padrão** no `.env.mailu`
2. **Configurar DNS MX records**
   ```
   mail.rpa4all.com.  IN  MX  10  mail.rpa4all.com.
   ```
3. **Adicionar SPF/DKIM/DMARC** via Admin Panel
4. **Habilitar 2FA** no Admin Panel
5. **Firewall**: Liberar apenas portas necessárias (25, 143, 587, 993)

## 📚 Documentação Detalhada

```bash
# Abrir documentação completa
cat MAILU_DEPLOYMENT.md
```

Cobre:
- ✅ Instalação passo-a-passo
- ✅ Configuração SSL/TLS
- ✅ Backup & Restore
- ✅ Troubleshooting
- ✅ Gerenciamento de usuários
- ✅ Integração com terceiros
- ✅ Performance tuning
- ✅ Segurança & DKIM

## 🆘 Troubleshooting Rápido

### Ver logs
```bash
docker-compose -f docker-compose.mailu.yml logs -f [serviço]
# Serviços: mailu-postfix, mailu-dovecot, mailu-roundcube, mailu-backend, etc.
```

### Restart rápido
```bash
docker-compose -f docker-compose.mailu.yml restart
```

### Parar serviços
```bash
docker-compose -f docker-compose.mailu.yml down
```

### Status de containers
```bash
docker ps | grep mailu
docker stats mailu-*
```

## 📊 Próximos Passos Recomendados

1. **Deploy** (python3 deploy_mailu.py)
2. **Criar domínio** no Admin (rpa4all.com)
3. **Criar usuários** de teste
4. **Testar webmail** (Roundcube)
5. **Configurar DNS** (MX records)
6. **Importar dashboard** Grafana
7. **Backup** (cron job automático)
8. **(Opcional) SSO** com Authentik

## 🎯 Funcionalidades Futuras

- [ ] ClamAV antivirus integrado
- [ ] Autenticação SMS 2FA
- [ ] Dovecot Exporter para métricas IMAP
- [ ] Backup com Restic automático
- [ ] Sogo webmail alternativo
- [ ] Rate limiting por IP
- [ ] Alertas automáticos (Telegram)

## 📞 Suporte

- **Docs Mailu**: https://mailu.io/
- **GitHub**: https://github.com/Mailu/Mailu
- **Issues**: https://github.com/Mailu/Mailu/issues

---

**Status:** ✅ Pronto para Deploy  
**Data:** Março 2026  
**Versão:** Mailu 2.0+  
**Ambiente Suportado:** Linux (Ubuntu 22.04+), Docker 20.10+
