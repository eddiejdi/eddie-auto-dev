# 📡 APIs Taxonomy

Catálogo de **endpoints HTTP** (FastAPI / Flask / OpenAPI).

Voltar ao índice: [README](./README.md) · [Architecture](./ARCHITECTURE.md) · [Annotations](./ANNOTATIONS.md)

---

## Snapshot

| Métrica | Valor típico |
|---------|--------------|
| Endpoints | 174 |
| Serviços | 25 |
| general (residual) | ~9 |
| deprecated | 1 |
| com `relatedTables` | ~26 |
| orphan | ~112 (exclui health) |

Fonte: `.apis-catalog/catalog.json` → `metadata`.

---

## Geração

```bash
python3 tools/catalog_apis.py
# ou
python3 tools/catalog_taxonomy.py --domain apis
```

**Saídas:**

| Arquivo | Conteúdo |
|---------|----------|
| `.apis-catalog/catalog.json` | Fonte de verdade do gate |
| `.apis-catalog/CATALOG_REPORT.md` | Por categoria + ownership + status |
| `.apis-catalog/SERVICE_ENDPOINTS.md` | Por serviço |
| `.apis-catalog/catalog.csv` | Export |
| `.apis-catalog/schema.json` | JSON Schema |

---

## Fontes

| Source | Captura |
|--------|---------|
| FastAPI/Starlette | `@app.get`, `@router.post`, … + `APIRouter(prefix=…)` |
| Flask | `@app.route(..., methods=[...])` |
| OpenAPI | `docs/openapi.yaml`, `openapi*.yaml/json` |

**Ignorados:** tests, venvs, `catalog_apis.py` (self), caches.

---

## Chave canônica

```
METHOD /path
```

Normalização:

- `/secrets/{name:path}` → `/secrets/{name}`
- trailing `/` removida (exceto `/`)
- params Flask/Express → `{name}`

Exemplos: `GET /health`, `POST /order`, `GET /tool-interceptor/stats`.

---

## Categorias (path + service hint)

| Category | Sinais |
|----------|--------|
| health | /health, /metrics, /status, /ready |
| auth | /auth, /login, /token, /session, /logout |
| secrets | /secret, /vault, /bw/, /authentik, /audit/recent |
| trading | /order, /position, /trade, /symbol, mt5_bridge |
| agents | /agent, /evoke, /messages, tool-interceptor |
| storage | /storage, /tape, /nextcloud, /share, portal |
| social | /tweet, /follow, /bookmark, x_agent |
| llm | /model, /rag, /chat, /generate, huggingface |
| marketing | /lead, /campaign, /diagnostico |
| banking | /bank, /billing, /cofrinho, /balance |
| meetings | /api/jobs, /api/join |
| infra | /api/hosts, ssh |
| platform | code_runner, /api/v2/* |
| ops | /actions, remediation, conube |
| monitoring | /alert, /dashboard, /reports |
| wiki, cmdb, acervo, admin | hints de path/serviço |
| general | fallback residual |

Service hints: `SERVICE_CATEGORY_HINTS` em `tools/catalog_apis.py`.

---

## Campos da entry

| Campo | Descrição |
|-------|-----------|
| `operationKey` | `METHOD /path` |
| `method`, `path` | HTTP |
| `source` | fastapi \| flask \| openapi |
| `service` | pacote/arquivo inferido |
| `category` | semântica |
| `sensitive` | auth/secrets |
| `status` | active \| deprecated \| experimental \| unused |
| `owner` / `team` | ownership |
| `relatedTables` | FQNs via anotação / `x-tables` |
| `orphan` | true se sem link de table (lifecycle) |
| `summary`, `operationId`, `tags` | OpenAPI quando houver |
| `locations[]` | file, line, service |

---

## Gate

```bash
python3 tools/hooks/api_registry_validate.py --staged
python3 tools/hooks/api_registry_validate.py path/to/routes.py
```

| Status | Efeito |
|--------|--------|
| ok | silencioso |
| duplicate (fuzzy, mesmo method) | **bloqueia** |
| lint | aviso |
| new | aviso |

Métodos diferentes no **mesmo path** (`GET` vs `POST`) **não** são duplicata.

Ver [ENFORCEMENT.md](./ENFORCEMENT.md).

---

## Ownership, status e links a tables

```python
# taxonomy: tables=btc.trades,clear.trades; owner=mt5_bridge
@app.post("/order")
async def place_order(...): ...
```

```yaml
get:
  x-tables: [btc.llm_calls]
  deprecated: true
```

- `relatedTables` no catálogo da API  
- aresta `explicit` no grafo (peso 1.0)  
- table deixa de ser `unused`; API deixa de ser `orphan`

Guia: [ANNOTATIONS.md](./ANNOTATIONS.md) · [OWNERSHIP.md](./OWNERSHIP.md)

---

## Ao criar um endpoint

1. Conferir catálogo (path/método)  
2. Prefixo coerente com o serviço  
3. Anotar `tables=` se lê/escreve SQL  
4. Regenerar catálogo  
5. Commitar código + `.apis-catalog/` (+ taxonomy se gerado)

---

## Consultas

```bash
less .apis-catalog/SERVICE_ENDPOINTS.md

# por owner
python3 -c "
import json
c=json.load(open('.apis-catalog/catalog.json'))
for o,n in sorted(c['metadata']['ownerCounts'].items(), key=lambda x:-x[1]):
  print(f'{n:3} {o}')
"

# linked
python3 -c "
import json
c=json.load(open('.apis-catalog/catalog.json'))
for cat,e in c['categories'].items():
  for k,d in e.items():
    if d.get('relatedTables'):
      print(k, d['relatedTables'])
"
```
