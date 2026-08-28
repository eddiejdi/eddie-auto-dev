# Hooks Library

Hooks de workspace para guardrails e validacao automatica do Copilot.

## Arquivos
- `pre-tooluse-guardrails.json`: bloqueia ou pede confirmacao para comandos de alto risco.
- `post-edit-validate.json`: roda validacao de frontmatter apos edicoes em artefatos de customizacao.

## Scripts
- `tools/copilot_hooks/pre_tool_guardrails.py`
- `tools/copilot_hooks/post_edit_validate.py`

## Eventos usados
- `PreToolUse`
- `PostToolUse`

## Validacao
- Conferir logs no canal `GitHub Copilot Chat Hooks`.
- Rodar testes em `tests/copilot_hooks/`.
