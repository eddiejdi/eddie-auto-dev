# 📧 Mailu Email Server + Webmail - Deployment Guide

## Visão Geral

**Mailu** é um servidor de email completo self-hosted com interface web. Este setup fornece:

- ✅ **SMTP** (Postfix) - Envio de emails
- ✅ **IMAP/POP3** (Dovecot) - Recebimento de emails  
- ✅ **Webmail** (Roundcube) - Interface web para acessar emails
- ✅ **Admin Panel** - Gerenciar usuários, domínios, quotas
- ✅ **Monitoramento** - Prometheus + Grafana
- ✅ **SSO Opcional** - Integração com Authentik

## Arquivos

```
docker-compose.mailu.yml    # Configuração Docker Compose
.env.mailu                  # Variáveis de ambiente
mailu_monitoring_dashboard.json  # Painel Grafana
MAILU_DEPLOYMENT.md         # Este arquivo
```

## Pré-requisitos

1. ✅ Docker + Docker Compose instalados
2. ✅ Rede `homelab_monitoring` criada:
   ```bash
   docker network create homelab_monitoring
   ```
3. ✅ Domínio configurado (ex: `mail.rpa4all.com`)
4. ✅ DNS MX records configurados:
   ```
   mail.rpa4all.com.  IN  MX  10  mail.rpa4all.com.
   mail.rpa4all.com.  IN  A   <seu-ip>
   ```

## Quick Start

### 1. Preparar Variáveis de Ambiente

```bash
# Copiar template
cp .env.mailu.example .env.mailu

# Gerar chaves seguras
python3 -c "import secrets; print('MAILU_SECRET_KEY=' + secrets.token_urlsafe(32))"
python3 -c "import secrets; print('MAILU_DB_PASSWORD=' + secrets.token_urlsafe(32))"
python3 -c "import secrets; print('MAILU_REDIS_PASSWORD=' + secrets.token_urlsafe(32))"

# Editar .env.mailu com valores gerados
nano .env.mailu
```

### 2. Criar Rede Homelab (se não existir)

```bash
docker network create homelab_monitoring
```

### 3. Deploy Mailu

```bash
# Iniciar serviços
docker-compose -f docker-compose.mailu.yml up -d

# Verificar status
docker-compose -f docker-compose.mailu.yml ps

# Ver logs
docker-compose -f docker-compose.mailu.yml logs -f
```

### 4. Acessar Admin Panel

```
URL: https://mail.rpa4all.com/admin/
Usuário: admin@mail.rpa4all.com
Senha: (será gerada automaticamente na primeira execução)
```

### 5. Acessar Webmail (Roundcube)

```
URL: https://mail.rpa4all.com/
```

## Configuração Pós-Deploy

### Criar Primeira Conta de Email

1. Acessar Admin Panel: `https://mail.rpa4all.com/admin/`
2. Menu: **Mail Domains** → **New Domain** 
3. Adicionar domínio (ex: `rpa4all.com`)
4. Menu: **Users** → **New User**
5. Criar usuário (ex: `edenilson@rpa4all.com`)

### Configurar SSL/TLS

Se usando **Let's Encrypt**:
- Mailu cuidará automaticamente
- Certifique-se que porta 80 esté acessível
- Certificates serão renovados automaticamente

Se usando **Certificados Manuais**:
```bash
# Copiar certs para volume
docker cp /caminho/do/cert.pem mailu-frontend:/certs/cert.pem
docker cp /caminho/do/key.pem mailu-frontend:/certs/key.pem

# Reiniciar frontend
docker-compose -f docker-compose.mailu.yml restart mailu-frontend
```

### Integrar com Authentik (Opcional)

1. Criar OAuth2 Client em Authentik:
   ```
   Name: Mailu
   Client ID: mailu-client
   Client Secret: (gerar)
   Redirect URI: https://mail.rpa4all.com/auth/oauth2/callback
   ```

2. Editar `.env.mailu`:
   ```env
   ENABLE_OAUTH2=true
   OAUTH2_PROVIDER_URL=https://auth.rpa4all.com
   OAUTH2_CLIENT_ID=mailu-client
   OAUTH2_CLIENT_SECRET=<seu_secret>
   ```

3. Reiniciar:
   ```bash
   docker-compose -f docker-compose.mailu.yml restart mailu-backend
   ```

## Monitoramento Prometheus

### Métricas Disponíveis

**Postfix Exporter** (porto 9307):
- `postfix_queue_size` - Tamanho da fila de emails
- `postfix_emails_sent_total` - Total de emails enviados
- `postfix_emails_received_total` - Total de emails recebidos
- `postfix_smtp_connections_total` - Conexões SMTP
- `postfix_rejects_total` - Emails rejeitados

**Sistema (Node Exporter)**:
- `node_disk_io_time_seconds_total` - I/O de disco
- `node_network_transmit_bytes_total` - Tráfego de rede

### Adicionar ao Prometheus

Editar `/etc/prometheus/prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'mailu-postfix'
    static_configs:
      - targets: ['localhost:9307']
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
        replacement: 'mailu-smtp'
```

Reiniciar Prometheus:
```bash
sudo systemctl restart prometheus
```

## Painel Grafana

Importar dashboard:

```bash
# Copiar arquivo JSON para Grafana
cp mailu_monitoring_dashboard.json /var/lib/grafana/dashboards/

# Ou via UI:
# 1. Grafana → Dashboards → Import
# 2. Selecionar arquivo JSON
# 3. Selecionar datasource "Prometheus"
```

**Panels Inclusos:**
- Fila de emails (Postfix Queue)
- Throughput (Sent/Received)
- Conexões SMTP
- Logins IMAP (Sucessos/Falhas)
- Armazenamento de caixas postais
- Taxa de bounce (24h)
- Top recipients
- Alertas e erros

## Backup & Restore

### Backup Automático

Editar crontab para backup diário:

```bash
crontab -e

# Adicionar linha:
0 2 * * * /usr/local/bin/mailu-backup.sh
```

Script de backup (`mailu-backup.sh`):

```bash
#!/bin/bash
BACKUP_DIR="/mnt/backups/mailu"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup do banco dados
docker exec mailu-db pg_dump -U mailu mailu | gzip > $BACKUP_DIR/mailu_db_$DATE.sql.gz

# Backup de dados de email
tar czf $BACKUP_DIR/mailu_data_$DATE.tar.gz /var/lib/docker/volumes/mailu_maildata/_data/

# Cleanup arquivos antigos (manter últimos 30 dias)
find $BACKUP_DIR -name "*.gz" -mtime +30 -delete
```

### Restore

```bash
# Restaurar banco de dados
gunzip < backup_db.sql.gz | docker exec -i mailu-db psql -U mailu -d mailu

# Restaurar dados de email
tar xzf backup_data.tar.gz -C /var/lib/docker/volumes/mailu_maildata/_data/
```

## Troubleshooting

### Emails não são recebidos
- [ ] Verificar DNS MX records
- [ ] Verificar firewall (porta 25 aberta)
- [ ] Ver logs: `docker logs mailu-postfix`
- [ ] SPF/DKIM/DMARC configurado?

### Webmail não carrega
- [ ] Verificar logs: `docker logs mailu-roundcube`
- [ ] Limpar cache: `docker exec mailu-redis redis-cli FLUSHALL`
- [ ] Restart: `docker-compose -f docker-compose.mailu.yml restart mailu-roundcube`

### SSL/TLS errors
- [ ] Verificar certificados: `docker exec mailu-frontend ls -la /certs/`
- [ ] Modo debug: `docker exec mailu-frontend nginx -T`
- [ ] Let's Encrypt: `docker logs mailu-frontend | grep letsencrypt`

### Performance issues
- [ ] Aumentar recursos: Editar `docker-compose.mailu.yml`
- [ ] Verificar uso de disco: `docker exec mailu-postfix df -h`
- [ ] Limpar fila: `docker exec mailu-postfix postsuper -d ALL deferred`

## Gerenciamento de Usuários

### Criar novo usuário

```bash
# Via API (requer token de admin)
curl -X POST https://mail.rpa4all.com/api/users \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@rpa4all.com",
    "password": "secure_password",
    "quota_mb": 5120
  }'
```

### Reset de Senha

```bash
# Via Admin Panel:
# 1. Users → Selecionar usuário
# 2. Change password
# OU via CLI:
docker exec mailu-backend flask mailu user-password user@rpa4all.com newpassword
```

## Segurança

- [ ] Mudar senhas padrão em `.env.mailu`
- [ ] Configurar SPF/DKIM/DMARC no Admin
- [ ] Habilitar 2FA no Admin Panel
- [ ] Configurar rate limiting (AUTH_RATELIMIT)
- [ ] Usar HTTPS/TLS obrigatório
- [ ] Backups criptografados
- [ ] Firewall: apenas portas necessárias abertas
- [ ] Logs centralizados (Loki)

## Integração com Sistema Existente

### Com Authentik (SSO)
✅ Suportado (veja secção "Integrar com Authentik")

### Com Grafana
✅ Dashboard incluído (mailu_monitoring_dashboard.json)

### Com Loki (Logs)
```yaml
# No docker-compose.mailu.yml, adicionar:
  mailu-journal:
    image: fluent/fluent-bit:latest
    volumes:
      - /var/log:/var/log:ro
    networks:
      - homelab_monitoring
    command: |
      -c /etc/fluent-bit/fluent-bit.conf
```

## Recursos Adicionais

- **Documentação Oficial**: https://mailu.io/
- **GitHub**: https://github.com/Mailu/Mailu
- **Community Forum**: https://github.com/Mailu/Mailu/discussions

## Roadmap

- [ ] Integração Authentik SSO completa
- [ ] Webmail alternativo (Sogo, Horde)
- [ ] Antivírus (ClamAV) integrado
- [ ] Backup automático com Restic
- [ ] Monitoramento de saúde com Evilginx2
- [ ] Failover / Alta Disponibilidade

---

**Última atualização:** Março 2026
**Versão Mailu:** 2.0+
**Testado em:** Linux (Ubuntu 22.04+), Docker 20.10+, Docker Compose 2.0+
