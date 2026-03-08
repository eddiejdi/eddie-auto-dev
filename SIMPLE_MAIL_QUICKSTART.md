# Email Server Simplificado - Guia Rápido

> **Status**: Solução alternativa devido a problemas de acesso ao Docker Hub para Mailu

## 🚀 Quick Start (2 minutos)

### Opção 1: Deployment Automático

```bash
chmod +x deploy_simple_mail.py
python3 deploy_simple_mail.py
```

O script irá:
1. ✓ Verificar pré-requisitos (Docker, Docker Compose)
2. ✓ Criar rede Docker necessária
3. ✓ Pedir domínio e email admin
4. ✓ Gerar senhas seguras
5. ✓ Iniciar containers
6. ✓ Aguardar services ficarem prontos

### Opção 2: Deployment Manual

```bash
# 1. Copiar arquivo de configuração
cp .env.mailu .env.simple-mail

# 2. Editar configuração
nano .env.simple-mail

# 3. Iniciar containers
docker-compose -f docker-compose.simple-mail.yml up -d

# 4. Verificar status
docker-compose -f docker-compose.simple-mail.yml ps
```

## 📋 Arquivos Criados

| Arquivo | Função |
|---------|--------|
| `docker-compose.simple-mail.yml` | Definição dos 5 containers (PostgreSQL, Postfix, Dovecot, Roundcube, Nginx) |
| `nginx-mail.conf` | Configuração Nginx (proxy reverso + SSL/TLS) |
| `deploy_simple_mail.py` | Script de automação Python |
| `.env.simple-mail` | Variáveis de ambiente (geradas automaticamente) |

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────┐
│           Users / Clients                    │
├─────────────────────────────────────────────┤
│ HTTPS (443) | HTTP (80) | SMTP (25/587)     │
├─────────────────────────────────────────────┤
│         Nginx Reverse Proxy                  │
│    (SSL/TLS + Rate Limiting)                 │
├─────────────────────────────────────────────┤
│                                              │
│  ┌───────────────┐  ┌──────────────────┐   │
│  │  Roundcube    │  │  Postfix/Dovecot │   │
│  │  (Webmail)    │  │  (SMTP/IMAP)     │   │
│  └───────────────┘  └──────────────────┘   │
│         │                    │               │
│         └────────┬───────────┘               │
│                  │                           │
│            PostgreSQL (DB)                   │
│            Redis (Cache)                     │
└─────────────────────────────────────────────┘
```

## 🔧 Configuração Pós-Deploy

### Acessar Roundcube
```
URL: https://mail.rpa4all.com/
Protocolo: IMAP
Servidor: mail-server (interno)
Porto: 143 (IMAP) ou 993 (IMAPS)
```

### Criar Primeiro Usuário Email

#### Via Roundcube (GUI):
1. Acessar: https://mail.rpa4all.com/
2. Criar novo usuário através do admin panel
3. Definir email: edenilson@mail.rpa4all.com
4. Definir senha segura

#### Via CLI (direto no container):
```bash
# Conectar ao container Postfix/Dovecot
docker exec -it mail-server bash

# Criar usuário via dovecot
doveadm user add -p password edenilson@mail.rpa4all.com
```

### Verificar Containers

```bash
# Status
docker-compose -f docker-compose.simple-mail.yml ps

# Logs
docker-compose -f docker-compose.simple-mail.yml logs -f

# Específico
docker-compose -f docker-compose.simple-mail.yml logs -f mail-server
```

## 🔐 Segurança

### SSL/TLS Obrigatório
```bash
# If você já tem certificado Let's Encrypt:
sudo certbot certonly --standalone -d mail.rpa4all.com

# Ou manual (30 dias):
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 30 -nodes
```

### Rate Limiting
Nginx está configurado com:
- Login: 5 req/s
- Geral: 50 req/s

## 📊 Monitoramento

### Prometheus Metrics
```
URL: http://postfix-exporter:9307/metrics

Métricas disponíveis:
- postfix_queue_size
- postfix_emails_sent_total
- postfix_emails_received_total
- dovecot_imap_logins_total
```

### Grafana Integration
1. Adicionar Prometheus datasource
2. Importar dashboard: `grafana/mailu_monitoring_dashboard.json`

## 🔗 Integração Authentik

A aplicação **já está registrada** em Authentik:

```
UUID: 7eaa61b5-00e7-4ad8-88ef-5e86c5991f65
Nome: Mailu Email Server
URL: https://mail.rpa4all.com
Acesso: https://auth.rpa4all.com/if/user/#/library
```

### Ativar SSO (Opcional)

```bash
# 1. Obter OAuth2 provider details
curl https://auth.rpa4all.com/api/v3/oauth2/authorization_codes/

# 2. Configurar Roundcube para LDAP/OAuth
# Editar: docker exec -it roundcube bash
#         vi /var/www/html/config/config.inc.php

# 3. Setar LDAP host:
#    $config['ldap_public'] = array(
#        'host' => 'auth.rpa4all.com',
#        'base_dn' => 'dc=rpa4all,dc=com'
#    );
```

## 🐛 Troubleshooting

### Problema: Containers não iniciam
```bash
# Verificar Docker daemon
systemctl status docker

# Verificar logs
docker-compose -f docker-compose.simple-mail.yml logs

# Limpar e recomeçar
docker-compose -f docker-compose.simple-mail.yml down -v
docker-compose -f docker-compose.simple-mail.yml up -d
```

### Problema: Roundcube acessa PostgreSQL mas não conecta ao Postfix
```bash
# Verificar conectividade entre containers
docker exec -it roundcube ping mail-server
docker exec -it roundcube telnet mail-server 143

# Verificar Postfix status
docker exec -it mail-server postfix status
```

### Problema: SSL não funciona
```bash
# Verificar certificado
openssl s_client -connect mail.rpa4all.com:443

# Renovar Let's Encrypt
docker exec -it mail-nginx certbot renew

# Ou usar certificado auto-assinado (teste):
openssl req -x509 -newkey rsa:2048 -keyout /tmp/key.pem \
  -out /tmp/cert.pem -days 365 -nodes
```

### Problema: Emails não podem ser enviados
```bash
# Verificar MX records
nslookup -type=MX mail.rpa4all.com

# Verificar Postfix queue
docker exec -it mail-server mailq

# Logs
docker exec -it mail-server tail -f /var/log/mail.log
```

## 📧 Portas e Protocolos

| Porto | Protocolo | Função | TLS |
|-------|-----------|--------|-----|
| 25 | SMTP | Receber email externo | Optional |
| 587 | SMTP-Submission | Enviar email (clientes) | Required |
| 143 | IMAP | Standard IMAP | Optional |
| 993 | IMAPS | Secure IMAP | Required |
| 110 | POP3 | POP3 acesso | Optional |
| 995 | POP3S | Secure POP3 | Required |
| 80 | HTTP | Roundcube web | Redireciona para 443 |
| 443 | HTTPS | Roundcube web SSL | Required |

## 🛑 Parar Servidores

```bash
# Parar containers (mantém dados)
docker-compose -f docker-compose.simple-mail.yml down

# Remover tudo (inclui dados!)
docker-compose -f docker-compose.simple-mail.yml down -v
```

## 📝 Notas

1. **Backup de dados**: Os volumes `mail_db_data`, `mail_data`, e `roundcube_data` contêm dados persistentes
2. **DNS MX**: Configure registros MX apontando para seu servidor
3. **Reverse DNS (PTR)**: Importante para reputação de email
4. **DKIM/SPF**: Configure via Postfix para melhor entrega
5. **Firewall**: Abra portas 25, 143, 587, 993, 110, 995, 80, 443

## 🔄 Alternativa: Usar Mailu Original

Se quiser voltar a usar Mailu (quando acesso ao Docker Hub for restaurado):

```bash
python3 deploy_mailu.py
# ou
docker-compose -f docker-compose.mailu.yml up -d
```

---

**Última atualização**: 2026-03-07
**Versão**: 1.0 (Simplified)
**Status**: Pronto para deployment
