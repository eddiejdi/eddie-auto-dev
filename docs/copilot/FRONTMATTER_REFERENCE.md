# Frontmatter Reference for Copilot Customization

Este documento define o padrao minimo de frontmatter YAML para arquivos de customizacao do Copilot neste repositorio.

## Objetivo
- Padronizar discovery de prompts, skills, agents e instructions.
- Evitar falhas silenciosas por YAML invalido.
- Reduzir conflitos de escopo com applyTo muito amplo.

## Regras Gerais
- Sempre usar bloco YAML no topo com delimitadores `---`.
- Usar espacos, nunca tabs.
- `description` e obrigatorio para discovery.
- Evitar `applyTo: "**"` salvo instrucao realmente global.
- `applyTo` deve ser especifico e sem sobreposicao desnecessaria.

## Modelos por Artefato

### Instruction (`.instructions.md`)
```yaml
---
description: "Use when: editing Python modules with I/O and database access"
applyTo: "**/*.py"
---
```

Campos:
- `description`: obrigatorio. Deve conter gatilhos claros em linguagem natural.
- `applyTo`: recomendado. Use glob restrito por dominio.

### Prompt (`.prompt.md`)
```yaml
---
description: "Use when: drafting production-safe deployment runbooks"
---
```

Campos:
- `description`: obrigatorio.
- `applyTo`: opcional. Use apenas quando o prompt for altamente contextual.

### Agent (`.agent.md`)
```yaml
---
description: "Use when: auditing security risks in pull requests"
tools: ["vscode", "search", "read", "edit", "execute", "agent"]
---
```

Campos:
- `description`: obrigatorio.
- `tools`: recomendado. Deve ser explicito e minimo necessario.

### Skill (`SKILL.md`)
```yaml
---
name: security-hardening
description: "Use when: hardening CI/CD, secrets handling, and SSH safety"
---
```

Campos:
- `name`: obrigatorio e deve corresponder ao nome da pasta.
- `description`: obrigatorio e orientado a gatilhos.

## Anti-patterns
- `applyTo: "**"` em arquivo especifico de dominio.
- Descricao generica como "General coding rules".
- YAML sem aspas quando ha `:` no valor.
- Tabs em vez de espacos.

## Checklist de Validacao
- Frontmatter inicia na linha 1.
- Bloco `---` fechado.
- YAML parseavel.
- `description` presente quando aplicavel.
- `applyTo` sem padroes excessivamente amplos.

## Convencao de Versionamento
- Atualize este documento quando novos campos forem adotados.
- Mantenha exemplos sincronizados com os artefatos reais em `.github/`.
