# Agents Library

Guia rapido para escolha de agentes no workspace.

## Agentes disponiveis
- `agent_dev_local.agent.md`: orquestrador geral e agente padrao.
- `wiki_rpa4all.agent.md`: integracao com Wiki.js.
- `testing-specialist.agent.md`: foco em testes e regressao.
- `security-auditor.agent.md`: foco em seguranca.
- `infrastructure-ops.agent.md`: foco em homelab e deploy.
- `trading-analyst.agent.md`: foco em trading e risco.
- `api-architect.agent.md`: foco em FastAPI e contratos.

## Como escolher
- Use `agent_dev_local` quando o trabalho cruza multiplos dominios.
- Use agentes especializados quando o escopo for claro e repetitivo.
- Use prompt quando quiser apenas orientar a resposta, sem governar ferramentas.

## Validacao
- Revisar frontmatter, description e tools.
- Rodar o linter de frontmatter apos criar ou ajustar agentes.
