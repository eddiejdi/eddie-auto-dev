---
name: agent-customization
description: "Use when: creating or fixing .instructions.md, .prompt.md, .agent.md, SKILL.md, frontmatter, applyTo, and tool restrictions"
---

# Agent Customization

## Objetivo
Criar e manter artefatos de customizacao com discovery consistente e baixo risco de conflito.

## Quando usar
- Criar nova instruction, prompt, agent ou skill.
- Ajustar frontmatter, description, applyTo e tools.
- Corrigir artefato que nao esta sendo acionado.

## Quando nao usar
- Bug de runtime da aplicacao.
- Configuracao de infraestrutura fora de customizacao Copilot.

## Workflow
1. Escolher o primitive correto (instruction, prompt, skill, agent).
2. Definir frontmatter minimo valido.
3. Escrever description com gatilhos reais de usuario.
4. Aplicar escopo especifico em applyTo quando necessario.
5. Validar com linter e revisar conflitos.

## Validacao
- Rodar: `/workspace/eddie-auto-dev/.venv/bin/python .github/hooks/lint-frontmatter.py`
- Garantir description presente e clara.
- Evitar applyTo amplo (`**`, `**/*`, `*`).

## Falhas comuns
- Description generica demais.
- Nome de skill diferente do nome da pasta.
- applyTo sobreposto com outra instruction.

## Exemplo de uso
Pedido: "crie um prompt para auditoria de seguranca em PR".
Saida esperada: novo `.prompt.md` com description gatilhavel e regras de saida objetivas.
