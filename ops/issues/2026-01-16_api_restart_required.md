# Issue: API não recarrega automaticamente após deploy

**Data:** 2026-01-16
**Severidade:** Média
**Status:** Aberto
**Reportado por:** Diretor (via Copilot)

## Problema

Após commit de novos endpoints (ex: `/bpm/templates`), a API em produção retornou 404 porque o uvicorn não foi reiniciado automaticamente.

## Causa Raiz

O deploy local via git pull não reinicia o serviço `specialized-agents-api`. Os novos endpoints só ficam disponíveis após restart manual.

## Impacto

- Usuários recebem 404 em endpoints recém-adicionados
- Tempo de downtime até detecção manual do problema

## Solução Proposta

### Opção 1: Systemd Reload Automático
```bash
# Adicionar ao deploy script
sudo systemctl restart specialized-agents-api
```

### Opção 2: Uvicorn com --reload (Dev only)
```bash
uvicorn specialized_agents.api:app --reload --host 0.0.0.0 --port 8503
```

### Opção 3: Webhook de Deploy
- GitHub Action envia webhook para servidor local
- Servidor executa restart automaticamente

## Ação Imediata Tomada

- API reiniciada manualmente
- Novo túnel criado: `https://settle-optimize-discharge-cross.trycloudflare.com`

## Tarefas para Operações

- [ ] Implementar auto-restart no deploy script
- [ ] Adicionar health check que valida endpoints esperados
- [ ] Configurar monitoramento de endpoints críticos

---

# Issue: Alto consumo de tokens Copilot vs Baixo uso do servidor local

**Severidade:** Alta (custo)
**Status:** Em análise

## Observação

Usuário reporta que tokens do GitHub Copilot estão sendo consumidos em excesso enquanto o servidor local (Ollama em 192.168.15.2:11434) está subutilizado.

## Diagnóstico Anterior

- CPU servidor: 80% idle
- RAM: 5.9GB disponível
- Ollama: 11 modelos carregados
- ChromaDB: Operacional

## Regras já implementadas

Ver `.github/copilot-instructions.md`:
- Regra 0.1: Economia de tokens
- Preferir processamento local

## Ações Recomendadas

1. **Auditar** quais operações estão usando Copilot vs Ollama local
2. **Implementar** logging de uso por provider
3. **Otimizar** roteamento: tarefas simples → modelo local pequeno
4. **Cache** de respostas frequentes no RAG local

## Métricas a Coletar

- Tokens Copilot consumidos por sessão
- Requests para Ollama local por sessão
- Tempo de resposta por provider
- Taxa de cache hit no RAG
