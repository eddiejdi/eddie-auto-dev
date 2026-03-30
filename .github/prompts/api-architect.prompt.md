---
description: "Use when: designing or reviewing FastAPI endpoints, API contracts, service boundaries, and request-validation flows"
---

# API Architect Prompt

## Objetivo
Desenhar e revisar interfaces de API com clareza de contrato, validacao e baixo acoplamento.

## Entrada esperada
- Requisito funcional.
- Endpoint ou modulo alvo.
- Restricoes de compatibilidade.

## Saida esperada
- Proposta de contrato ou ajuste.
- Impacto em handlers, schemas e validacao.
- Riscos de compatibilidade e testes sugeridos.

## Regras
- Separar contrato externo de implementacao interna.
- Priorizar schemas claros e erros previsiveis.
- Minimizar breaking changes desnecessarios.
