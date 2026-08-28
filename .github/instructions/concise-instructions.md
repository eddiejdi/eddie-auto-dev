---
description: "Use when: escrevendo ou revisando instruções de projeto, copilot-instructions.md, instruction files, prompts de sistema"
applyTo: "**/.github/**,**/instructions/**,**/*.instructions.md,**/copilot-instructions*"
---

# Instruções de Projeto Concisas e Focadas

**Status**: ✅ **REGRA GLOBAL** — Aplicável a criação e manutenção de instruções

---

## Princípio

> **Instruções de projeto são para contexto geral e diretrizes principais.** Instruções específicas de tarefa pertencem ao próprio chat, não ao arquivo global.

---

## Regras Obrigatórias

- Cada instruction file deve ter **um único propósito** — sem misturar domínios.
- Máximo **1 arquivo `.md`** criado/modificado por tarefa de instrução.
- **Proibido** duplicar regras que já existem em `copilot-instructions.md` — referenciar, não repetir.
- `applyTo` deve ser **específico** — nunca usar `**`, `**/*` ou `*` sem qualificador adicional.
- `description` deve conter gatilhos reais de uso ("Use when: ...") — não descrições genéricas.
- Após criar/editar instrução, rodar o linter: `.venv/bin/python .github/hooks/lint-frontmatter.py`.

## O que pertence aqui vs. no chat

| Vai na instrução global | Fica no chat |
|---|---|
| Padrões de código do projeto | Requisito específico de uma feature |
| Convenções de naming | Debugging pontual |
| Regras de arquitetura | Configuração de uma única tarefa |
| Guardrails de segurança | Ajustes de estilo para um arquivo |
