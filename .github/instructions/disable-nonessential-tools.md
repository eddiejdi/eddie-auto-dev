---
description: "Use when: decidindo quais ferramentas ativar para uma tarefa, avaliando necessidade de busca web, conectores MCP e ferramentas externas"
applyTo: "**/*agent*,**/*tool*,**/*mcp*,**/*connector*"
---

# Ferramentas e Conectores — Ativar Apenas Quando Necessários

**Status**: ✅ **REGRA GLOBAL** — Aplicável a toda execução de tarefa

---

## Princípio

> **Ferramentas ativas consomem tokens em cada turno, mesmo quando não usadas.** Desative o que não é necessário para a conversa atual.

---

## Hierarquia de Ferramentas (do mais para o menos econômico)

```
1. Workspace local (grep_search, read_file, file_search) ← SEMPRE preferir
2. Ferramentas de terminal (run_in_terminal)              ← Quando local insuficiente
3. GPU local Ollama (GPU0 → GPU1)                        ← Para LLM calls
4. MCP Homelab (bus, secrets, db)                        ← Apenas se tarefa exige
5. Busca web / fetch_webpage                             ← Apenas quando indispensável
6. APIs cloud externas                                   ← Último recurso com aprovação
```

## Quando DESATIVAR ferramentas

| Ferramenta | Desativar quando |
|---|---|
| `fetch_webpage` / busca web | Tarefa é 100% baseada no workspace local |
| `mcp_homelab_*` | Tarefa não envolve homelab (é puramente de código local) |
| `mcp_telegram_*` | Nenhuma interação com Telegram necessária |
| `semantic_search` repetida | Já retornou contexto suficiente em chamada anterior |
| GPU1 / fallback cloud | GPU0 respondeu com sucesso |

## Regras de Aplicação

- **Skill primeiro, exploração depois**: invocar skill correspondente antes de explorar código.
- Não chamar `semantic_search` em paralelo com outras buscas — é sequencial.
- `fetch_webpage` proibido para URLs geradas/inventadas — apenas URLs fornecidas pelo usuário.
- MCP tools somente quando o contexto local (`/memories/repo/`) não resolve.
- Após usar ferramenta externa, avaliar se resultado deve ir para `memories/repo/` para evitar re-consulta futura.
