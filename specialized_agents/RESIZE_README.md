# Fallback de resize e distribuição de tarefas

## Objetivo
Quando uma solicitação demora demais e o agente não responde, o sistema divide a tarefa em partes menores e distribui para múltiplos agentes, combinando os resultados.

## Como funciona
1. O agente inicia a geração normalmente.
2. Se ultrapassar o `split_timeout`, dispara o fallback distribuído.
3. O `AgentManager` divide a solicitação em chunks e executa subtarefas em paralelo.
4. O resultado é combinado em um único bloco de código.

## Regras de distribuição
- Se houver `requirements.features`, cada feature vira um chunk.
- Caso contrário, a descrição é dividida por sentenças e agrupada.
- O agente que sofreu timeout é excluído da redistribuição.

## Parâmetros atuais
Os parâmetros estão centralizados em `TASK_SPLIT_CONFIG`:
- `split_timeout_seconds`: 30s (timeout de geração inicial)
- `max_workers`: 6 (número máximo de agentes em paralelo)
- `timeout_per_subtask_seconds`: 40s (timeout por subtask)
- `exclude_origin_agent`: evita reatribuir ao agente que sofreu timeout
- `generate_only_subtasks`: subtasks geram código sem testes/Docker

## Principais pontos de ajuste
- Aumentar `max_workers` para maior paralelismo.
- Reduzir `split_timeout_seconds` para fallback mais rápido.
- Reduzir `timeout_per_subtask_seconds` para evitar subtasks longas.
- Desativar `generate_only_subtasks` se precisar rodar testes no chunk.

## Elasticidade Docker
A elasticidade de consumo por container é controlada por `DOCKER_RESOURCE_CONFIG` e usa flags como:
- `--cpus`, `--memory`, `--memory-reservation`, `--memory-swap`

## Arquivos relacionados
- specialized_agents/base_agent.py
- specialized_agents/agent_manager.py
- specialized_agents/docker_orchestrator.py
- specialized_agents/config.py
