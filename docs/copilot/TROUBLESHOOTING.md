# Troubleshooting

## Skill nao encontrada
- Revisar `description` da skill.
- Confirmar se `name` bate com o nome da pasta.
- Rodar o linter de frontmatter.

## Prompt nao aparece ou nao dispara
- Confirmar que o arquivo termina com `.prompt.md`.
- Melhorar `description` com gatilhos mais concretos.

## Agent com comportamento inesperado
- Revisar `tools` permitidas.
- Verificar sobreposicao de escopo com outro agente.
- Conferir o arquivo [ .github/agents/README.md ](.github/agents/README.md).

## Hook nao executa
- Confirmar local em `.github/hooks/*.json`.
- Confirmar `type: "command"`.
- Verificar logs em `GitHub Copilot Chat Hooks`.
- Garantir que o script chamado existe e e executavel no ambiente.

## Lint acusa falso positivo
- Confirmar se o arquivo realmente pertence a um tipo validado.
- Revisar os glob patterns em [ .github/hooks/lint-frontmatter.py ](.github/hooks/lint-frontmatter.py).

## Parent repository discovery
- Se abrir subpastas em monorepo, habilitar `chat.useCustomizationsInParentRepositories`.
