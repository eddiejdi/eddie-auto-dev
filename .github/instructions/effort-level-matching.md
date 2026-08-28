---
description: "Use when: calibrando profundidade de resposta, respondendo perguntas rotineiras, escolhendo verbosidade de análise"
applyTo: "**/*agent*,**/*task*,**/*llm*"
---

# Nível de Esforço Proporcional à Tarefa

**Status**: ✅ **REGRA GLOBAL** — Aplicável a toda geração de resposta

---

## Princípio

> **Nível de esforço maior = mais tokens. Calibre o esforço ao real requisito da tarefa.** Tarefas rotineiras não exigem as respostas mais detalhadas.

---

## Escala de Esforço

| Nível | Quando usar | Comportamento esperado |
|-------|-------------|------------------------|
| **Mínimo** | Verificações simples, confirmações, `git status`, leitura de arquivo | Resposta em 1-3 frases, sem elaboração |
| **Baixo** | Correções pontuais, ajustes de config, typos, adição de log | Implementar diretamente, confirmar brevemente |
| **Médio** | Features novas simples, refatorações locais, testes unitários | Solução completa com contexto mínimo necessário |
| **Alto** | Arquitetura nova, diagnóstico sistêmico, trade-offs de design | Análise detalhada com alternativas consideradas |

## Regras de Aplicação

- **Padrão é baixo** — escale para cima apenas quando justificado.
- Confirmar ação realizada em 1-3 frases — sem introduções, conclusões ou summaries desnecessários.
- Se o usuário pedir "verifique X", responder com o resultado, não com uma explicação de como verificar.
- Respostas com mais de 3 parágrafos para tarefa simples = desperdício de tokens.

## Anti-Padrões Proibidos

- "Aqui está o resultado:", "Vou agora...", "Com base na análise..." → remover sempre.
- Explicar o que foi feito em vez de simplesmente fazer.
- Gerar alternativas não solicitadas para tarefas com resposta única clara.
