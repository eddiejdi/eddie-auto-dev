# 📚 Documentação Eddie AI

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
| [LESSONS_LEARNED_2026-02-02.md](LESSONS_LEARNED_2026-02-02.md) | Lições aprendidas (monitoramento e deploy) |
| [HOMELAB_AGENT.md](HOMELAB_AGENT.md) | Agente Homelab (execução remota SSH) |
| [WEATHER_AGENT.md](#) | Weather Agent (via copilot-instructions) |

## Atualizações Recentes

### 23 de fevereiro de 2026
- ✅ Weather Agent: monitoramento meteorológico via Open-Meteo API a cada 15 min
- ✅ Tabela `weather_readings` no Postgres com 17 variáveis ambientais
- ✅ Rotas FastAPI `/weather/*` (current, latest, history, summary, collect)
- ✅ Serviço systemd `eddie-weather-agent.service`
- ✅ 15 testes unitários

### 02 de fevereiro de 2026
- ✅ Painéis Grafana corrigidos (datasource + validação Selenium)
- ✅ Pipeline de deploy multi-ambiente (dev/cer/prod)
- ✅ Runner self-hosted e retries de healthcheck

### 10 de janeiro de 2026
- ✅ Integração Open WebUI + Telegram + WhatsApp
- ✅ Modelos eddie-assistant (sem censura) e eddie-coder (restrito)
- ✅ WAHA instalado para API WhatsApp
- ✅ Sistema de perfis automáticos

## Links Úteis

- **Open WebUI:** http://192.168.15.2:3000
- **Ollama:** http://192.168.15.2:11434
- **WAHA Dashboard:** http://192.168.15.2:3001/dashboard
- **GitHub Agent:** http://localhost:8502

---
*Gerado automaticamente*
