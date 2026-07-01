---
description: "Use when: selecionando modo de raciocínio para uma tarefa, avaliando se análise profunda é necessária, decidindo profundidade de resposta"
applyTo: "**/*agent*,**/*task*,**/*llm*,**/*ollama*"
---

# Raciocínio Estendido — Usar Apenas Quando Necessário

**Status**: ✅ **REGRA GLOBAL** — Aplicável a toda seleção de modo de análise

---

## Princípio

> **Raciocínio estendido consome tokens significativamente maiores.** Deve ser ativado apenas para tarefas que genuinamente exigem análise multi-etapas complexa.

---

## Quando ATIVAR raciocínio estendido

- Diagnóstico de falha sistêmica com múltiplas causas raiz potenciais.
- Arquitetura de nova feature com trade-offs significativos.
- Debugging de race condition, deadlock ou problema de concorrência.
- Análise de segurança de código crítico (autenticação, criptografia).
- Refatoração que afeta múltiplos módulos interdependentes.

## Quando NÃO ATIVAR (modo padrão é suficiente)

- CRUD simples, edições de uma linha, renomeações.
- Busca e leitura de arquivos, pesquisa no workspace.
- Tarefas rotineiras: adicionar log, ajustar config, corrigir typo.
- Perguntas factuais sobre o codebase.
- Execução de comandos conhecidos (pytest, git status, etc.).

## Regra de Decisão

```
se tarefa == "rotineira ou pontual":
    usar modo padrão  # economiza tokens
elif tarefa == "análise complexa com trade-offs":
    ativar raciocínio estendido  # justificado
```
