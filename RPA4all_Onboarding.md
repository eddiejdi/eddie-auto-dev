---
Subject: Bem-vindo à RPA4All! Seu Onboarding Completo
From: IT & Automação <it@rpa4all.com>
To: [Novo Colaborador]
---

# Bem-vindo(a) à equipe RPA4All!

Estamos muito felizes em ter você a bordo. Nossa missão na **RPA4All** (Robotic Process Automation) é transformar e otimizar processos através da automação inteligente. Abaixo você encontrará o guia completo da nossa infraestrutura e todos os acessos essenciais.

---

## 1. Portais Externos e SSO (Authentik)
Todos os acessos são gerenciados via Single Sign-On com **Authentik**. Faça login no portal SSO com suas credenciais provisórias.

| Serviço | URL |
|---------|-----|
| Portal SSO (Authentik) | https://auth.rpa4all.com |
| Nextcloud (Arquivos & Docs) | https://nextcloud.rpa4all.com |
| Grafana (Monitoramento) | https://grafana.rpa4all.com |
| OpenWebUI (Interface de IA) | https://openwebui.rpa4all.com |
| Site Institucional | https://www.rpa4all.com |
| IDE Web | https://ide.rpa4all.com |
| Wiki.js (Documentação) | https://wiki.rpa4all.com |
| Jira (Gestão de Projetos) | https://rpa4all.atlassian.net |

---

## 2. VPN (WireGuard + Cloudflare Tunnel)
Para acesso remoto à infraestrutura interna:
- **Endpoint:** `vpn.rpa4all.com`
- **Porta:** `51822` (UDP / TCP Tunnel)
- **Configuração:** `/etc/wireguard/rpa4all.conf`
- **Script de Conexão:** `connect-homelab-vpn.sh`
- *Chaves e credenciais distribuídos via Simple Vault.*

---

## 3. Email Corporativo (@rpa4all.com)
Seu email corporativo roda em servidor próprio (Postfix + Dovecot):
- **SMTP:** `mail.rpa4all.com` — porta 587 (TLS)
- **IMAP:** `mail.rpa4all.com` — porta 993 (TLS)
- **Webmail (Roundcube):** Acesse via navegador no portal de email
- *Credenciais serão enviadas separadamente pelo Simple Vault.*

---

## 4. IA e Homelab ("Eddie")
Nosso Homelab possui um cluster multi-GPU com modelos Open Source locais via **Ollama**:
- **GPU0 (RTX 2060):** `http://192.168.15.2:11434`
- **GPU1 (GTX 1050):** `http://192.168.15.2:11435`
- **API de Agentes (FastAPI):** `http://localhost:8503`
- **Code Runner:** `http://localhost:2000`
- **Communication Bus:** Toda comunicação inter-agentes passa pelo barramento central.

---

## 5. Bots e Integrações de Chat
| Canal | Detalhes |
|-------|----------|
| Telegram Bot | Gerenciado via systemd (`eddie-telegram-bot.service`). Token no Vault. |
| WhatsApp (WAHA) | API HTTP em `http://192.168.15.2:3001` |

---

## 6. Dashboards e Monitoramento

| Dashboard | URL Interna | Descrição |
|-----------|-------------|-----------|
| Streamlit (Conversation Monitor) | `http://localhost:8501` | Monitoramento de agentes |
| Streamlit (Dev Dashboard) | `http://localhost:8502` | GitHub Agent e Testes |
| Grafana | `http://192.168.15.2:3002` | Métricas e alertas |
| OpenSearch Dashboards | `http://192.168.15.2:5601` | Logs centralizados |
| Pi-hole DNS | Docker container local | Filtragem DNS e ad-block |

---

## 7. Banco de Dados (PostgreSQL)
- **Host:** `192.168.15.2`
- **Porta:** `5433`
- **Schema principal:** `btc`
- *Credenciais no Vault. Sempre usar `conn.autocommit = True` e placeholders `%s`.*

---

## 8. Wiki e Documentação (Confluence, Draw.io, .md)
Documentação segue o modelo **Docs-as-Code**:
- **Wiki.js (On-Premise):** [https://wiki.rpa4all.com](https://wiki.rpa4all.com) — Wiki interno com SSO Authentik
- **Confluence:** [https://rpa4all.atlassian.net/wiki](https://rpa4all.atlassian.net/wiki) — Space `'ED'`
- **Jira:** https://rpa4all.atlassian.net — tickets e workflows
- **Draw.io:** Diagramas `.drawio` commitados no repositório
- **Markdown:** RFCs, ADRs e tutoriais em `.md` processados pelo **ConfluenceAgent**
- Pipeline automática converte e publica no Confluence a cada push.

---

## 9. Repositório e Código
- **GitHub:** https://github.com/eddiejdi/shared-auto-dev
- **Local:** `/home/edenilson/eddie-auto-dev`
- **Branch principal:** `master`
- **CI/CD:** GitHub Agent integrado via MCP

---

## 10. Inventário Completo de Serviços

| Categoria | Serviço | Endereço | Porta |
|-----------|---------|----------|-------|
| SSO | Authentik | auth.rpa4all.com | HTTPS |
| Cloud | Nextcloud | nextcloud.rpa4all.com | HTTPS |
| Monitor | Grafana | grafana.rpa4all.com | HTTPS |
| IA UI | OpenWebUI | openwebui.rpa4all.com | HTTPS |
| LLM | Ollama GPU0 | 192.168.15.2 | 11434 |
| LLM | Ollama GPU1 | 192.168.15.2 | 11435 |
| API | Specialized Agents | localhost | 8503 |
| API | Code Runner | localhost | 2000 |
| Dashboard | Streamlit 1 | localhost | 8501 |
| Dashboard | Streamlit 2 | localhost | 8502 |
| Chat | Telegram Bot | via Telegram | — |
| Chat | WhatsApp WAHA | 192.168.15.2 | 3001 |
| Email | Mail Server | mail.rpa4all.com | 587/993 |
| Logs | OpenSearch | 192.168.15.2 | 9200 |
| Logs | OpenSearch Dash. | 192.168.15.2 | 5601 |
| DNS | Pi-hole | Docker | 53 |
| PM | Jira | rpa4all.atlassian.net | HTTPS |
| Docs | Wiki.js | wiki.rpa4all.com | HTTPS |
| Docs | Confluence | [rpa4all.atlassian.net/wiki](https://rpa4all.atlassian.net/wiki) | HTTPS |
| DB | PostgreSQL | 192.168.15.2 | 5433 |
| VPN | WireGuard | vpn.rpa4all.com | 51822 |
| Web | Site Público | www.rpa4all.com | HTTPS |
| IDE | IDE Web | ide.rpa4all.com | HTTPS |

---

Dúvidas? Mande mensagem no canal interno com a tag `@it-support` ou entre em contato via Telegram Bot.

**Equipe de Infraestrutura & Operações — RPA4All**

