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
| [CONUBE_SUPPORT_FLOW.md](CONUBE_SUPPORT_FLOW.md) | Fluxo de abertura de chamado na Conube |
| [HOMELAB_BTOP_GPU_DISKS_FIX_2026-03-18.md](HOMELAB_BTOP_GPU_DISKS_FIX_2026-03-18.md) | Runbook do fix do btop (GPU1 + discos + estabilidade) |
| [SETUP.md](SETUP.md) | Guia de instalação |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Solução de problemas |
| [LESSONS_LEARNED_2026-02-02.md](LESSONS_LEARNED_2026-02-02.md) | Lições aprendidas (monitoramento e deploy) |

## Atualizações Recentes

### 18 de março de 2026
- ✅ Runbook de correção do `btop` no homelab (GPU1 ausente, crash com 2 GPUs e inclusão de discos com progressbar)
- ✅ Workaround estável em `btop 1.3.0`: `show_gpu_info = "Auto"` com `gpu0 gpu1`
- ✅ Fluxo `POST /conube/support/open-ticket` documentado
- ✅ Exemplo de payload, cURL e interpretação de resposta (`Pendente` -> `Em análise`)

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
