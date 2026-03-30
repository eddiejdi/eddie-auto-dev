---
name: trading-analysis
description: "Use when: analyzing trading models, PostgreSQL trading data, risk signals, and diagnostics for BTC or multi-coin flows"
---

# Trading Analysis

## Objetivo
Apoiar diagnostico tecnico e operacional do stack de trading com foco em risco e consistencia dos dados.

## Quando usar
- Analise de comportamento de estrategia.
- Revisao de pipelines de dados de trading.
- Investigacao de risco, sinal ou degradacao operacional.

## Workflow
1. Confirmar ativo, periodo e fonte de dados.
2. Separar dado observado de inferencia.
3. Validar consistencia no Postgres e no codigo.
4. Propor acoes priorizadas por risco.

## Regras obrigatorias
- Usar PostgreSQL, nunca SQLite, para fluxos de trading.
- Filtrar consultas por simbolo quando aplicavel.
- Tratar diagnostico e recomendacao como coisas separadas.

## Validacao
- Evidencia do dado consultado.
- Hipotese testavel.
- Impacto esperado da acao sugerida.

## Exemplo
Pedido: "investigue queda de performance da estrategia BTC nas ultimas 24h".
