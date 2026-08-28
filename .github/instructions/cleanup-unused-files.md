---
description: "Use when: revisando arquivos de projeto, limpando contexto acumulado, auditando memórias e instruções obsoletas"
applyTo: "**/.github/**,**/memories/**,**/*.md"
---

# Limpeza de Arquivos de Projeto Não Utilizados

**Status**: ✅ **REGRA GLOBAL** — Aplicável a manutenção de contexto

---

## Princípio

> **Arquivos não utilizados ativamente consomem tokens desnecessários em cada sessão.** Limpar regularmente é obrigação, não opcional.

---

## Regras Obrigatórias

- Antes de criar **novo** arquivo de instrução, memória ou skill: verificar se já existe equivalente com `file_search`.
- Arquivos `.md` de documentação gerados por tarefas anteriores e não mais referenciados devem ser removidos ou arquivados.
- Memories `/memories/repo/*.md` obsoletas devem ser deletadas — não apenas atualizadas para dizer "não usar mais".
- Arquivos `*.md.bak`, `*.md.old` e duplicatas em `.github/` devem ser removidos imediatamente.
- Skills e instructions com `description` idêntica ou redundante a outra existente devem ser consolidadas.

## Sinais de Limpeza Necessária

- Arquivo referenciado em instrução mas que não existe mais no workspace.
- Memory com data > 60 dias sem acesso recente ao tema.
- Instruction com `applyTo` que nunca é acionado por arquivos do projeto.
- Arquivos `.md` na raiz do workspace que não são README ou doc ativa.
