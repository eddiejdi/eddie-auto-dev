---
description: "Use when: carregando contexto de projeto, decidindo quais arquivos incluir, gerenciando janela de contexto do agente"
applyTo: "**/*agent*,**/*context*,**/*memory*,**/*tool*,**/*task*"
---

# Eficiência via RAG — Carregar Apenas o Contexto Relevante

**Status**: ✅ **REGRA GLOBAL** — Aplicável a todas as interações

---

## Princípio

> **Projetos usam RAG (Retrieval-Augmented Generation).** O agente deve carregar na janela de contexto APENAS o conteúdo diretamente relevante para a tarefa atual.

---

## Regras Obrigatórias

- **NUNCA** carregue arquivos inteiros se apenas uma seção é necessária — use `read_file` com `startLine`/`endLine`.
- **NUNCA** cole logs completos no chat. Salve em `/tmp/<nome>.log` e referencie o caminho.
- **Prefira** buscas direcionadas (`grep_search`, `semantic_search`, `file_search`) antes de abrir arquivos.
- Ao usar `semantic_search`, uma única chamada deve ser suficiente — se retornar o workspace completo, você tem contexto suficiente.
- Leituras paralelas de arquivos independentes são permitidas; leituras em cadeia especulativas são proibidas.

## Gatilho de Violação

- Respostas lentas ou repetitivas após ~30 turnos → compactar imediatamente com `/compact`.
- Pastes > 5k chars no chat → **PROIBIDO**. Redirecionar para arquivo.
