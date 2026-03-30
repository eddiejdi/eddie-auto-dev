# Agent Framework

Padrao para criacao de agentes em `.github/agents/`.

## Quando usar Agent
- Precisa de conjunto de tools restrito.
- Precisa de comportamento especializado por dominio.
- Precisa de isolamento de contexto por subagente.

## Frontmatter minimo
```yaml
---
description: "Use when: <gatilho por dominio>"
tools: ["vscode", "read", "search"]
---
```

## Estrutura recomendada
1. Escopo do agente
2. Regras obrigatorias
3. Fluxo padrao
4. Ferramentas permitidas
5. Limites e proibicoes
6. Validacao final

## Convencoes
- Ferramentas minimas necessarias.
- Sem sobreposicao ampla com agentes existentes.
- Description com gatilhos claros e concretos.

## Escolha Agent vs Prompt
- Use agent quando precisa governar ferramentas e fluxo.
- Use prompt quando precisa apenas orientar uma resposta focada.

## Checklist de aceite
- Frontmatter valido.
- Tools coerentes com o dominio.
- Escopo claro sem conflito com agente orquestrador.
