# Cloudflare Email Routing — Gmail SMTP para @rpa4all.com

**Atualizado:** 2026-03-13  
**Status:** ✅ Ativo  
**Domínio:** rpa4all.com  
**Provedor DNS:** Cloudflare  

## Visão Geral

O domínio `rpa4all.com` utiliza **Cloudflare Email Routing** para receber emails e encaminhá-los para contas Gmail. O envio de emails (SMTP) é feito pelo **docker-mailserver** self-hosted no homelab.

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Remetente  │────▶│ Cloudflare Email  │────▶│   Gmail     │
│  externo    │     │ Routing (MX)      │     │  Inbox      │
└─────────────┘     └──────────────────┘     └─────────────┘

┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Roundcube  │────▶│ docker-mailserver │────▶│ Destinatário│
│  Webmail    │     │ (Postfix:587)     │     │  externo    │
└─────────────┘     └──────────────────┘     └─────────────┘
```

## Registros DNS (Cloudflare)

### MX Records (Cloudflare Email Routing)
| Prioridade | Servidor | TTL |
|------------|----------|-----|
| 11 | `route3.mx.cloudflare.net` | Auto |
| 28 | `route1.mx.cloudflare.net` | Auto |
| 97 | `route2.mx.cloudflare.net` | Auto |

### SPF (TXT record em `rpa4all.com`)
```
v=spf1 include:_spf.mx.cloudflare.net mx a ~all
```

### DMARC (TXT record em `_dmarc.rpa4all.com`)
```
v=DMARC1; p=quarantine; rua=mailto:postmaster@rpa4all.com
```

### DKIM (TXT record em `mail._domainkey.rpa4all.com`)
```
v=DKIM1; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAq+PclOAH8AWC2d09H
Yt4ujTdL+35r7vz1SrLDAIP1Bs3pjKEbIOQA7unmJyJrCXxZIbVnXiIU+oicaovWjBT1jToPM8TVvGI
07tfw81/6hg56CYcmcIwxilO1D8tc5vzrvGKRgje9ulgzUb+3vHoRIr5//tbEknSR6exQJ4cScx4MI5i
ZuwWO/XpfZETbHKVb9uDTS6o+Seg+4X+nX7lq4JmhtiIVej8nqiMtUp+fOovkVXaI48aZf2pxdzgv/S
7/vDgcdKgiNlXD5N7146KC7jegR0pBP0iVIXn93/OKP7WIF20kyqy9b58tueyJcdhZWdWEGMll6kNKvr
Nu1lsJwIDAQAB
```

## Configuração no Cloudflare Dashboard

### Email Routing → Routing Rules
| Endereço @rpa4all.com | Destino (Gmail) | Tipo |
|------------------------|-----------------|------|
| `edenilson.teixeira@rpa4all.com` | Admin principal | Mailbox |
| `edenilson.paschoa@rpa4all.com` | Forward → Gmail | Forward |
| `postmaster@rpa4all.com` | → admin | Forward |
| Catch-all (*) | — | Drop ou Forward (configurar no dashboard) |

### Email Routing → Destination Addresses (verificados)
- `edenilson.teixeira@rpa4all.com` — admin principal ✅

## SMTP de Saída (docker-mailserver)

O envio de emails @rpa4all.com é feito pelo docker-mailserver local:

| Config | Valor |
|--------|-------|
| **Servidor SMTP** | `mail.rpa4all.com` |
| **Porta TLS** | 465 |
| **Porta STARTTLS** | 587 |
| **Autenticação** | Password (Dovecot) |
| **Hostname** | `mail.rpa4all.com` |
| **Compose** | `/mnt/raid1/docker-mailserver/docker-compose.yml` |
| **Config env** | `/mnt/raid1/docker-mailserver/mailserver.env` |
| **Contas** | `data/dms/config/postfix-accounts.cf` |
| **DKIM keys** | `data/dms/config/opendkim/keys/rpa4all.com/` |

### Acesso Webmail (Roundcube)
| Config | Valor |
|--------|-------|
| **URL pública** | `https://mail.rpa4all.com` |
| **Container** | `roundcube` (porta 9080) |
| **Cloudflare Tunnel** | `mail.rpa4all.com → localhost:9002` (nginx proxy) |

## Gmail SMTP (alternativo — para scripts/automação)

Para enviar emails via Gmail SMTP (usado em scripts de automação):

| Config | Valor |
|--------|-------|
| **Host** | `smtp.gmail.com` |
| **Porta** | 587 (STARTTLS) ou 465 (SSL) |
| **Usuário** | `edenilson.teixeira@rpa4all.com` (ou Gmail associado) |
| **Autenticação** | App Password (Google) |
| **App Password** | Gerar em: `myaccount.google.com/apppasswords` |

> ⚠️ **NUNCA** commitar App Passwords no repositório.
> Use o Secrets Agent: `tools/vault/secret_store.py`

## Grafana SMTP (não configurado)

O Grafana **não tem SMTP configurado** atualmente. Para habilitar alertas por email:

```bash
# Adicionar ao docker-compose.grafana.yml, seção environment do grafana:
- GF_SMTP_ENABLED=true
- GF_SMTP_HOST=smtp.gmail.com:587
- GF_SMTP_USER=edenilson.teixeira@rpa4all.com
- GF_SMTP_PASSWORD=<APP_PASSWORD>  # ← mover para secrets
- GF_SMTP_FROM_ADDRESS=grafana@rpa4all.com
- GF_SMTP_FROM_NAME=Grafana RPA4All
- GF_SMTP_STARTTLS_POLICY=MandatoryStartTLS
```

## Arquivos Relacionados no Workspace

| Arquivo | Descrição |
|---------|-----------|
| `site/deploy/cloudflared-rpa4all-ide.yml` | Config cloudflared (tunnel com regra mail) |
| `docker/docker-compose.docker-mailserver.yml` | Compose do mail server |
| `config/nginx-mail.conf` | Nginx reverse proxy para Roundcube |
| `docs/EMAIL_SERVER_SETUP.md` | Documentação detalhada do mail server |
| `grafana/email_server_dashboard.json` | Dashboard Grafana do email |
| `systemd/eddie-expurgo.service` | Serviço de limpeza Gmail |

## Manutenção

```bash
# Status dos containers de email
ssh homelab@192.168.15.2 "docker ps --filter name=mailserver --filter name=roundcube"

# Adicionar nova conta de email
ssh homelab@192.168.15.2 "cd /mnt/raid1/docker-mailserver && bash setup.sh account add user@rpa4all.com"

# Gerar/atualizar chave DKIM
ssh homelab@192.168.15.2 "cd /mnt/raid1/docker-mailserver && bash setup.sh dkim"

# Verificar logs SMTP
ssh homelab@192.168.15.2 "docker logs mailserver --tail 50"

# Testar envio SMTP
ssh homelab@192.168.15.2 "docker exec mailserver swaks --to test@gmail.com --from test@rpa4all.com --server localhost --port 25"
```
