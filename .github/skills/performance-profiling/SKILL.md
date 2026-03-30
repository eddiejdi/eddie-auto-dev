---
name: performance-profiling
description: "Use when: profiling slow code paths, optimizing GPU-first routing, and reducing latency or token waste"
---

# Performance Profiling

## Objetivo
Diagnosticar gargalos de execucao e desperdicio de recurso em codigo e fluxos LLM.

## Quando usar
- Codigo lento ou com I/O excessivo.
- Ajustes de roteamento LLM e GPU-first.
- Analise de latencia, throughput e custo de token.

## Workflow
1. Definir metrica alvo.
2. Identificar caminho critico.
3. Medir antes da mudanca.
4. Aplicar otimização minima.
5. Medir depois e comparar.

## Regras obrigatorias
- Nao otimizar sem baseline.
- Priorizar gargalo real antes de micro-otimizacao.
- Separar ganho de latencia, custo e complexidade.

## Validacao
- Metricas antes/depois.
- Regressao funcional ausente.
- Trade-offs documentados.

## Exemplo
Pedido: "reduza latencia no fluxo Ollama GPU0->GPU1".
