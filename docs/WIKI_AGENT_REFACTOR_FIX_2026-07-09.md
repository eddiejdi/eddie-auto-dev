# Wiki Agent — Fix `__file__` em `wiki_refactor.py`

**Data:** 2026-07-09  
**Serviço:** `specialized-agents-api` (porta 8503)  
**Sintoma:** `POST /wiki/raw` retornava HTTP 500

---

## Causa raiz

Ao inicializar `WikiAgent`, o construtor de `WikiRefactorSkill` usava:

```python
Path(__file__).resolve().parents[1]
```

No homelab (`/home/homelab/myClaude/specialized_agents/`), o módulo é carregado em contexto onde `__file__` não existe, gerando:

```
NameError: name '__file__' is not defined
```

Isso impedia qualquer chamada a `/wiki/publish`, `/wiki/raw` e `/wiki/evolve`.

---

## Correção

Nova função `_resolve_repo_root()` em `specialized_agents/wiki_refactor.py`:

1. Usa `repo_root` explícito quando informado
2. Tenta `globals()["__file__"]` (seguro quando ausente)
3. Fallback para `WIKI_REFACTOR_REPO_ROOT` ou `EDDIE_REPO_ROOT`
4. Fallback para `/home/homelab/myClaude` ou `/home/homelab/eddie-auto-dev`
5. Último recurso: `Path.cwd()`

---

## Deploy no homelab

```bash
# 1. Copiar módulo corrigido
scp specialized_agents/wiki_refactor.py \
  homelab:/home/homelab/myClaude/specialized_agents/wiki_refactor.py

# 2. Reiniciar API
ssh homelab 'sudo systemctl restart specialized-agents-api'

# 3. Validar
curl -s http://192.168.15.2:8503/wiki/health
curl -s -X POST http://192.168.15.2:8503/wiki/raw \
  -H 'Content-Type: application/json' \
  -d '{"topic":"Smoke","raw_text":"# smoke test wiki agent","wiki_path":"operations/wiki-agent-smoke","tags":["test"],"locale":"pt","skip_ollama":true}'
```

Resposta esperada: `{"ok": true, "page_id": ..., "wiki_path": "operations/wiki-agent-smoke"}`

---

## Variáveis de ambiente (opcional)

| Variável | Uso |
|----------|-----|
| `WIKI_REFACTOR_REPO_ROOT` | Root do repo para scan de `docs/**/*.md` no refactor |
| `EDDIE_REPO_ROOT` | Alias do root do projeto |

Recomendado no systemd drop-in do homelab:

```ini
[Service]
Environment=WIKI_REFACTOR_REPO_ROOT=/home/homelab/myClaude
```

---

## Testes

```bash
.venv/bin/python -m pytest tests/test_wiki_refactor.py -q
```

---

## Diagnóstico complementar — timeout Wiki.js (09/07)

Após o fix do `__file__`, `/wiki/raw` passou a falhar com:

```
503 — Erro de conexão com Wiki.js: timed out
```

**Causa:** Wiki.js estava ocupado renderizando página (job `Rendering page ID 659` ~30s nos logs). O `wiki_client` usava timeout de **15s**, insuficiente durante jobs pesados.

**Evidências:**
- `docker logs wikijs` — jobs de render + rebuild page tree às 12:05–12:06 UTC
- GraphQL em `:3009` voltou a responder em ~4s após o job
- `/wiki/raw` validado: `{"ok":true,"page_id":660}` (smoke test)

**Mitigação aplicada:**
- `wiki_client.py` — timeout GraphQL aumentado de 15s → **45s**
- Recomendado no homelab: `WIKI_URL=http://127.0.0.1:3009/graphql` no systemd (evita round-trip pela interface externa)

---

## Referências

- `specialized_agents/wiki_refactor.py` — `_resolve_repo_root()`
- `specialized_agents/wiki_agent.py` — endpoints `/wiki/raw`, `/wiki/publish`
- `docs/WIKI_AGENT_COMPLETE_REFERENCE_2026-05-03.md` — contrato da API