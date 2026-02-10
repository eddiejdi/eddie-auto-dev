# PR: Fix Grafana production metrics — agent-network-exporter

## Resumo
Corrige falhas que deixaram o Grafana de produção sem dados.

Principais mudanças:
- Corrige query SQL que usava `LAG()` dentro de `AVG()` (substituída por CTE) para evitar erro de agregação no Postgres.
- Quando a tabela `conversations` estiver vazia, o exporter agora conta `conversation_id` distintos na tabela `messages` (últimas 6h) para métricas de conversas ativas.
- Reuso de `conversation_id` no `AgentConversationInterceptor` para agrupar mensagens do mesmo par source→target dentro de janela de 5 minutos.
- `specialized_agents.__init__` passou a usar lazy imports para evitar carregar `chromadb`/`grpc` na inicialização, reduzindo uso de memória e tempo de startup.
- `check_conversations.py` refatorado para uma versão leve que consulta Postgres diretamente via SQLAlchemy (evita importar módulos pesados para diagnósticos rápidos).

## Arquivos alterados
- `specialized_agents/agent_network_exporter.py` — SQL fix, active conversations fallback
- `specialized_agents/agent_interceptor.py` — conversation_id reuse logic
- `specialized_agents/__init__.py` — lazy imports
- `check_conversations.py` — lightweight diagnostic
- `tools/run_network_exporter.py` — safe import (aligned with lazy init)

## Testes locais realizados
- Verificado Postgres: existem mensagens (~466) e sample de conversation_ids.
- Reiniciado `agent-network-exporter.service` e confirmado `/metrics` expõe `agent_active_conversations`, `agent_connection_strength`, `agent_response_latency_seconds`.
- `check_conversations.py` executa rapidamente e imprime resumo das conversas.

## Plano de deploy seguro (test/stage → prod)
1. Criar branch `fix/grafana-exporter-metrics` (feito) e abrir PR para revisão.
2. Em ambiente de teste/staging (ou homelab):
   - Atualizar o código com a branch e instalar dependências (em venv):

```bash
# no host de staging
git fetch origin
git checkout -b fix/grafana-exporter-metrics origin/fix/grafana-exporter-metrics || git checkout fix/grafana-exporter-metrics
. .venv/bin/activate
pip install -r requirements.txt  # se necessário
   - Aplicar drop-ins systemd com `DATABASE_URL` se não estiver presente.
   - Reiniciar serviços: `systemctl restart agent-network-exporter.service specialized-agents-api.service`
   - Verificar `/metrics` (porta 9101) e logs:

```bash
curl -sS http://localhost:9101/metrics | head -40
journalctl -u agent-network-exporter.service -f
   - Validar dashboard Grafana em staging (ou forçar scrape no Prometheus) e checar painéis.

3. Rollout para produção (após validação em staging):
   - Abrir janela de deploy curta (1-2 min) e rodar steps similares em prod.
   - Se algo der errado, reverter rapidamente para a versão anterior com `systemctl restart <service>` apontando para o commit anterior ou usar `git checkout` na pasta de deploy.

## Rollback
- Se o exporter falhar ou Prometheus não receber métricas, reverter commit localmente em host e reiniciar o serviço:

```bash
# no host prod
cd /path/to/eddie-auto-dev
git checkout HEAD~1  # reverte o último commit no deploy
sudo systemctl restart agent-network-exporter.service
## Observações adicionais
- Recomendo aumentar `MemoryMax=` (systemd) para o exporter se o ambiente tiver memória suficiente, mas o ideal é manter lazy imports para reduzir footprint.
- Validar se Prometheus consegue fazer scrape (regras de firewall/iptables).

---

Por favor confirme se quer que eu:  
1) faça push da branch e abra o PR no GitHub automaticamente (requer `gh` CLI e credenciais), ou  
2) apenas deixar o branch e o arquivo `PR_DESCRIPTION.md` localmente (pronto para você abrir o PR manualmente).