# Prompts Library

Indice dos prompts especializados disponiveis.

## Prompts
- `generic.prompt.md`: tarefas gerais de engenharia.
- `testing-specialist.prompt.md`: foco em testes e cobertura.
- `security-auditor.prompt.md`: foco em risco e seguranca.
- `infrastructure-ops.prompt.md`: operacoes de infra e deploy.
- `trading-analyst.prompt.md`: analise de trading e diagnostico.
- `api-architect.prompt.md`: desenho e revisao de contratos FastAPI.

## Como escolher
- Se precisa restringir ferramentas e isolamento, prefira agent.
- Se precisa de orientacao de saida por persona, use prompt.

## Validacao
- `/workspace/eddie-auto-dev/.venv/bin/python .github/hooks/lint-frontmatter.py`
