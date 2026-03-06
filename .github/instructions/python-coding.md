---
applyTo: "**/*.py"
---

# Regras de código Python — Eddie Auto-Dev

## Estilo obrigatório
1. **Type hints** em TODAS as funções e variáveis de módulo. Use `from __future__ import annotations` quando necessário.
2. **Docstrings em PT-BR** para funções/classes públicas (Google style).
3. **async/await** para operações I/O-bound (HTTP, DB, filesystem, SSH).
4. **f-strings** — nunca `.format()` ou `%` para interpolação.
5. **pathlib.Path** em vez de `os.path`.
6. **try/except específico** — nunca bare `except:` ou `except Exception:` sem logging.
7. **Logging estruturado** — `logger.info/warning/error` com contexto, nunca `print()` em produção.
8. **Constantes UPPER_CASE** no topo do módulo. Sem magic numbers/strings.
9. **Funções pequenas** — max ~50 linhas.
10. **Imports organizados**: stdlib → third-party → local (isort compatible).

## Padrões do projeto
- **Message bus** para inter-agent: `from specialized_agents.agent_communication_bus import get_communication_bus, MessageType`
- **RAG**: `RAGManagerFactory.get_manager(language)` ou `RAGManagerFactory.global_search(...)`
- **IPC cross-process**: `from tools import agent_ipc` (requer `DATABASE_URL`)
- **Logging pattern**: `log_request`, `log_response`, `log_task_start`, `log_task_end` para metadata consistente
- **Secrets**: nunca commit. Usar `tools/vault/secret_store.py`
