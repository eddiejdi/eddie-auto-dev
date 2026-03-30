# Prompt Templates

Guia para criar prompts reutilizaveis em `.github/prompts/`.

## Quando usar Prompt
- Tarefa unica e focada por persona.
- Entrada textual com objetivo claro.
- Nao precisa de isolamento de ferramenta como em agent.

## Frontmatter minimo
```yaml
---
description: "Use when: <tipo de pedido e contexto>"
---
```

## Template base
```md
---
description: "Use when: <gatilho>"
---

# <Nome do prompt>

## Objetivo
<resultado esperado>

## Entrada esperada
- <item>

## Saida esperada
- <item>

## Regras
- <regra>
```

## Convencoes
- Um prompt por objetivo principal.
- Nome orientado ao dominio: `testing-specialist.prompt.md`.
- Linguagem direta, sem ambiguidade.

## Checklist de aceite
- Description descoberta por linguagem natural.
- Prompt produz saida verificavel.
- Nao conflita com outra persona no mesmo contexto.
