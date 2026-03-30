---
name: testing-strategy
description: "Use when: adding tests, improving pytest coverage, creating fixtures, and validating regressions"
---

# Testing Strategy

## Objetivo
Padronizar criacao de testes com foco em cobertura, isolamento e regressao.

## Quando usar
- Nova feature precisa de testes unitarios.
- Correcao de bug exige teste de nao regressao.
- Reestruturar fixtures e mocks.

## Entradas esperadas
- Modulo alterado.
- Comportamento esperado.
- Dependencias externas que devem ser mockadas.

## Workflow
1. Definir cenarios de sucesso, erro e borda.
2. Criar testes por comportamento, nao por implementacao.
3. Mockar I/O externo (DB, HTTP, APIs, filesystem).
4. Validar com suite local e revisar falhas.

## Regras obrigatorias
- Evitar chamadas reais em servicos externos.
- Priorizar testes deterministas.
- Adicionar cobertura para caminho de erro relevante.

## Validacao
- Comando base: `pytest -q`
- Para escopo especifico, executar apenas o arquivo de testes alterado.

## Falhas comuns
- Teste acoplado ao estado global.
- Fixture com efeitos colaterais.
- Cobertura insuficiente para casos de erro.

## Exemplo de uso
Pedido: "corrigi parser de contrato, gere testes".
Saida esperada: testes cobrindo parser valido, entrada invalida e campos ausentes.
