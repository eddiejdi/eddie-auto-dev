# Skills Library

Indice das skills disponiveis no workspace.

## Skills
- `agent-customization`: criar/ajustar artefatos de customizacao Copilot.
- `testing-strategy`: estrategia de testes, fixtures e regressao.
- `security-hardening`: reforco de seguranca operacional e CI/CD.
- `homelab-deployment`: deploy e rollout seguro em homelab.
- `performance-profiling`: diagnostico de latencia, gargalos e desperdicio de token.
- `trading-analysis`: analise de estrategia, dados e risco no stack de trading.

## Como usar
- Escrever pedidos com gatilhos alinhados ao campo `description` da skill.
- Manter uma skill por fluxo especializado.
- Evitar duplicacao entre skills e instrucoes globais.

## Dependencias
- Nao ha dependencias ciclicas entre skills atuais.
- Todas dependem da governanca de frontmatter e linter.

## Validacao
- `/workspace/eddie-auto-dev/.venv/bin/python .github/hooks/lint-frontmatter.py`
