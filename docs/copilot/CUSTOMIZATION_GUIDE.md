# Copilot Customization Guide

Guia central para customizacao do Copilot neste repositorio.

## Objetivo
Organizar instrucoes, prompts, skills, agents e hooks para aumentar previsibilidade, seguranca e reutilizacao.

## Mapa de artefatos
- Instrucoes: `.github/instructions/`
- Prompts: `.github/prompts/`
- Skills: `.github/skills/<nome>/SKILL.md`
- Agents: `.github/agents/`
- Hooks e validadores: `.github/hooks/`
- Workflow CI: `.github/workflows/lint-instructions.yml`
- Templates, checklists e exemplos: `assets/copilot/`
- Configuracoes locais de chat: `.vscode/settings.json` e `.vscode/extensions.json`

## Ordem recomendada de criacao
1. Definir frontmatter e validacao.
2. Criar frameworks (skill, prompt, agent).
3. Criar skills de dominio.
4. Criar prompts por persona.
5. Criar/ajustar agentes especializados.
6. Integrar hooks e CI.

## Regras de governanca
- Todo artefato com frontmatter valido.
- Description obrigatoria para discovery.
- Evitar `applyTo` amplo.
- Manter escopo claro entre prompt, skill e agent.

## Como criar novo artefato

### Opção 1: Usar o Creator Script (Recomendado)
```bash
python tools/create_copilot_artifact.py
```

Script interativo que:
- Guia você na escolha: skill vs agent vs prompt vs instruction
- Coleta informações e gera frontmatter automático
- Valida com `lint-frontmatter.py` antes de salvar
- Cria estrutura correta com example content

Veja: [CREATE_ARTIFACT.md](./CREATE_ARTIFACT.md)

### Opção 2: Manual (Templates)
1. Copie template de `assets/copilot/templates/`
2. Preencha frontmatter + conteúdo
3. Salve em local correto (`.github/skills/nome/SKILL.md`, etc)
4. Valide localmente com linter
5. Commit e push

Veja: [Template Index](./EXAMPLES.md#templatos)

## Fluxo de validacao
1. Executar linter local:
   - `python .github/hooks/lint-frontmatter.py`
2. Executar testes do linter:
   - `python -m unittest -q tests/hooks/test_lint_frontmatter.py`
3. Conferir workflow de CI no PR (GitHub Actions).

## Hooks ativos
- `pre-tooluse-guardrails.json`: bloqueio ou confirmacao de operacoes perigosas.
- `post-edit-validate.json`: validacao automatica de frontmatter apos edicoes em artefatos de customizacao.
- Scripts de suporte em `tools/copilot_hooks/`.

## Troubleshooting rapido
- Skill nao encontrada: revisar `description` e nome da pasta.
- Prompt nao dispara: descricao sem gatilho pratico.
- Conflito de contexto: applyTo sobreposto em instrucoes.
- Falha de parser: frontmatter com sintaxe invalida.
