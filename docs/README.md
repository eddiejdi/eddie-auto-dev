# 📚 Documentação Shared AI

> ⚠️ **Manutenção de conhecimento:** sempre que você adicionar ou modificar documentos:
> 1. Atualize o *RAG index* (ver `index_homelab_docs.py` ou API `/rag/index`).
> 2. Acrescente nomes nas listas de `KNOWLEDGE_SOURCES` se aplicável (consultar `specialized_agents/instructor_agent.py`).
> 3. Comente no `CHANGELOG.md` e `README.md` nas seções recentes para registrar as fontes atualizadas.
> 4. Não precisa perguntar manualmente — o roteiro acima serve como checklist.


## Documentos Disponíveis

| Arquivo | Descrição |
|---------|-----------|
| [INTEGRATION.md](INTEGRATION.md) | Integração Open WebUI, Telegram, WhatsApp |
| [MODELS.md](MODELS.md) | Configuração de modelos Ollama |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Arquitetura do sistema |
| [API.md](API.md) | Documentação de APIs |
| [SETUP.md](SETUP.md) | Guia de instalação |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Solução de problemas |
| [NEXTCLOUD_ACCESS_PANEL.md](NEXTCLOUD_ACCESS_PANEL.md) | Painel de criação de acesso ao Nextcloud via Authentik |
| [NAS_IDLE_POWER_SAVING_2026-07-05.md](NAS_IDLE_POWER_SAVING_2026-07-05.md) | Runbook dos ajustes de economia de energia em idle do NAS |
| [SOL_USDT_INSTALLATION.md](SOL_USDT_INSTALLATION.md) | Instalação e operação do trading agent SOL-USDT (3 perfis live) |
| [LESSONS_LEARNED_2026-02-02.md](LESSONS_LEARNED_2026-02-02.md) | Lições aprendidas (monitoramento e deploy) |

## Atualizações Recentes

### 09 de julho de 2026
- ✅ Hooks do Claude Code importados para Grok (`.grok/hooks/`, `hooks.json`, `scripts/install_grok_hooks.sh`)
- ✅ Instalação SOL-USDT documentada em `SOL_USDT_INSTALLATION.md`

### 05 de julho de 2026
- ✅ Economia de energia em idle do NAS documentada em `NAS_IDLE_POWER_SAVING_2026-07-05.md`
- ✅ Registrados ajustes de Ollama/GPU, HDD standby conservador, timer LTFS e comandos de reversão
- ✅ Validação operacional preservou TrueNAS, SMB e NFS ativos

### 29 de abril de 2026
- ✅ Remediação completa do cliente Pi-hole/DNS local documentada em `PIHOLE_CLIENT_DNS_REMEDIATION_2026-04-29.md`
- ✅ Página publicada na Wiki.js em `https://wiki.rpa4all.com/pt/troubleshooting/pihole-client-dns-remediation-2026-04-29`
- ✅ DNS IPv4 voltou a ser automático via DHCP com Pi-hole efetivo em `192.168.15.2`
- ✅ Reserva DHCP stale, ARP flux local e interferência do túnel `wg-panama` foram diagnosticados e corrigidos

### 02 de fevereiro de 2026
- ✅ Painéis Grafana corrigidos (datasource + validação Selenium)
- ✅ Pipeline de deploy multi-ambiente (dev/cer/prod)
- ✅ Runner self-hosted e retries de healthcheck

### 10 de janeiro de 2026
- ✅ Integração Open WebUI + Telegram + WhatsApp
- ✅ Modelos shared-assistant (sem censura) e shared-coder (restrito)
- ✅ WAHA instalado para API WhatsApp
- ✅ Sistema de perfis automáticos

## Links Úteis

- **Open WebUI:** http://192.168.15.2:3000
- **Ollama:** http://192.168.15.2:11434
- **WAHA Dashboard:** http://192.168.15.2:3001/dashboard
- **GitHub Agent:** http://localhost:8502

---
*Gerado automaticamente*
