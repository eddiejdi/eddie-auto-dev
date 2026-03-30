---
name: codex-config-bridge
description: "Bridge agnóstico entre customizações do Copilot e Codex/Continue"
applies_to: ".codex/**, .continue/**, .vscode/settings.json"
---

# Codex Config Bridge

Reutiliza a infraestrutura de customização do Copilot para beneficiar **Codex**, **Continue** e outras extensões de IA.

## Objetivo
Unificar validação, guardrails e estrutura de personas entre múltiplas extensões IA no VS Code.

## Como reutilizar

### 1. Guardrails Compartilhados
```python
# tools/copilot_hooks/pre_tool_guardrails.py
# Já parametrizado — funciona para ANY extensão IA
# Não depende de Copilot específico

# Usar em .codex/hooks/ também
```

### 2. Schema de Personas
Copilot:
```yaml
---
description: "Use when: testing APIs"
---
```

Codex (`config.json`):
```json
{
  "agents": [
    {
      "id": "security-auditor",
      "description": "Use when: auditing code for security",
      "tools": ["read", "search", "web"]
    }
  ]
}
```

**Padrão comum**: `description` com trigger phrases

### 3. Validação Unificada
```python
# tools/validator_universal.py
def validate_customization(path: Path, format: str) -> list[str]:
    """Valida Copilot (YAML), Codex (JSON), Continue (TOML)."""
    if format == "yaml":
        return _validate_yaml_frontmatter(path)
    elif format == "json":
        return _validate_json_schema(path)
    elif format == "toml":
        return _validate_toml_schema(path)
```

## Benefícios

| Benefício | Como | Impacto |
|-----------|------|--------|
| **Code reuse** | Mesmo guardrails para Copilot + Codex | -50% duplicação |
| **Consistent UX** | Mesmos agentes, prompts, skills | Users não confundem |
| **Single validation** | Lint valida AMBAS extensões | Catch erros cedo |
| **Unified monitoring** | Hook log centralizado | Auditoria completa |
| **Easy switching** | User muda extensão, config persiste | Menos lock-in |

## Implementação (fases)

**Phase 1:** Extrair lógica agnóstica de `lint-frontmatter.py` → `validator_universal.py`

**Phase 2:** Criar `.codex/config.json` baseado em `.github/agents/` e `.github/prompts/`

**Phase 3:** Adaptar guardrails para ambas extensões

**Phase 4:** Documentar sinergia em `CODEX_INTEGRATION.md`

## Exemplo: Reutisar Agent em Codex

Copilot `security-auditor.agent.md`:
```yaml
---
description: "Use when: auditing code for security issues"
tools: [read, search, web]
---
# Security Auditor...
```

Gerar Codex config automaticamente:
```json
{
  "agents": [{
    "id": "security-auditor",
    "description": "Use when: auditing code for security issues",
    "tools": ["read", "search", "web"],
    "sourceFile": ".github/agents/security-auditor.agent.md"
  }]
}
```

**Tool:** `tools/sync_codex_from_copilot.py`
- Lê `.github/agents/`, `.github/prompts/`
- Gera `.codex/config.json`
- Rodar periodicamente ou em CI

## Próximos Passos
1. Criar `validator_universal.py` (agnóstico)
2. Criar `sync_codex_from_copilot.py` (auto-sync)
3. Criar `.codex/config.json` template
4. Documentar em `CODEX_INTEGRATION.md`
5. Atualizar `lint-instructions.yml` para validar ambos

---

**Status:** Skill para guiar implementação futura  
**Benefício ao Codex:** 📈 Muito alto (reutiliza toda infraestrutura)
