# Skill Framework

Este framework padroniza criacao e manutencao de skills no repositorio.

## Quando usar Skill
- Fluxo multi-etapa com regras e checklists.
- Tarefa recorrente que precisa de contexto especializado.
- Processo com risco operacional que exige padrao consistente.

## Estrutura obrigatoria
- Caminho: `.github/skills/<nome>/SKILL.md`
- Frontmatter minimo:

```yaml
---
name: <nome-da-skill>
description: "Use when: <gatilhos claros para descoberta>"
---
```

## Estrutura recomendada do corpo
1. Objetivo
2. Quando usar
3. Quando nao usar
4. Entradas esperadas
5. Passo a passo
6. Validacao
7. Falhas comuns
8. Exemplos

## Convencoes
- `name` igual ao nome da pasta.
- `description` com termos que o usuario realmente escreve.
- Evitar dependencias ciclicas entre skills.
- Referenciar arquivos reais do workspace.

## Anti-patterns
- Skill com conteudo generico sem workflow.
- Description vaga sem gatilhos.
- Copiar regras globais de instrucoes sem especializacao.

## Checklist de aceite
- Frontmatter valido.
- Discovery por description testavel.
- Passos claros e validaveis.
- Pelo menos um exemplo realista.
