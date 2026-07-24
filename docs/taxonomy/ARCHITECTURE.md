# 🏗 Taxonomy Architecture

Arquitetura do sistema de taxonomia do homelab.

---

## 1. Princípios

1. **Catálogos derivados** — `catalog.json` é gerado por scanners; não editar à mão (exceto em emergência).
2. **Chaves canônicas estáveis** — gates e grafo dependem de nomes normalizados.
3. **Enforcement em camadas** — IDE/agente → git local → CI.
4. **Anotações explícitas vencem heurística** — `taxonomy: tables=...` / OpenAPI `x-tables` geram arestas `explicit` (peso 1.0).
5. **Lifecycle é pós-grafo** — `unused` só após links strong serem calculados.

---

## 2. Pipeline

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  Sources    │   │  Sources    │   │  Sources    │
│  .env/code  │   │  SQL/DDL    │   │  routes/OAS │
└──────┬──────┘   └──────┬──────┘   └──────┬──────┘
       │                 │                 │
       ▼                 ▼                 ▼
 catalog_variables  catalog_tables    catalog_apis
       │                 │                 │
       ▼                 ▼                 ▼
 .variables-catalog .tables-catalog  .apis-catalog
       │                 │                 │
       └────────────┬────┴────────┬────────┘
                    ▼             │
         catalog_taxonomy_graph   │
                    │             │
                    ▼             │
         .taxonomy-catalog/       │
           graph.json             │
                    │             │
                    ▼             │
      catalog_taxonomy_lifecycle  │
         unused · orphan · gaps   │
                    │             │
                    ▼             ▼
              reports + index.json
```

Orquestrador: `tools/catalog_taxonomy.py`.

| Flag | Efeito |
|------|--------|
| (default) | todos os domains + graph + lifecycle |
| `--domain tables,apis` | subset de domains |
| `--graph-only` | só grafo (+ lifecycle, salvo `--no-lifecycle`) |
| `--lifecycle-only` | só lifecycle sobre artefatos existentes |
| `--no-graph` | só scanners |
| `--no-lifecycle` | pula unused/orphans |
| `--no-reports` | só JSON, sem MD/CSV |

---

## 3. Domínios

### 3.1 Variables

| Item | Detalhe |
|------|---------|
| Scanner | `tools/catalog_variables.py` |
| Output | `.variables-catalog/` |
| Docs | [variables-taxonomy/README.md](../variables-taxonomy/README.md) |
| Gate | `variable_registry_validate.py` |
| Fontes | `.env*`, docker-compose, systemd, `*config*.py`/`*settings*.py`, YAML |
| Categorias | trading, authentication, database, infrastructure, integrations, monitoring, services (default) |
| Observação | YAML flatten gera ruído histórico (~76% do catálogo legado); gates usam o JSON como está |

### 3.2 Tables

| Item | Detalhe |
|------|---------|
| Scanner | `tools/catalog_tables.py` |
| Output | `.tables-catalog/` |
| Docs | [TABLES.md](./TABLES.md) |
| Gate | `table_registry_validate.py` |
| Fontes | `*.sql`, Python com `CREATE TABLE` |
| Chave | `schema.table` lowercase |
| Schemas | `btc`, `clear`, `marketing`, `public`, `whatsapp`, … |
| Metadados | columns, PK/FK, indexes, locations, category, sensitive, owner, team, status, relatedApis |

Resolução de schema:

1. Qualificador no DDL (`btc.trades`)
2. `SCHEMA = "btc"` no mesmo arquivo Python
3. `SET search_path TO …` em SQL
4. Hint por path (`btc_trading_agent/` → `btc`)
5. Fallback `public`

### 3.3 APIs

| Item | Detalhe |
|------|---------|
| Scanner | `tools/catalog_apis.py` |
| Output | `.apis-catalog/` |
| Docs | [APIS.md](./APIS.md) |
| Gate | `api_registry_validate.py` |
| Fontes | FastAPI/Flask decorators, OpenAPI YAML/JSON |
| Chave | `METHOD /path` com path params normalizados (`{name:path}` → `{name}`) |
| Metadados | service, category, sensitive, owner, team, status, relatedTables, orphan, locations |

Categorização:

1. Regex no path (`API_CATEGORIES`)
2. Service hints (`SERVICE_CATEGORY_HINTS`)
3. Fallback `general` (hoje residual, ~9 endpoints)

---

## 4. Camada transversal

### 4.1 `taxonomy_meta.py`

Responsável por:

- `OWNER_RULES` / `SCHEMA_OWNERS`
- parse de anotações `taxonomy: key=value`
- shorthand `tables: …`
- status a partir de texto / OpenAPI
- `x-tables` / `x-table` / `x-status`
- resolução de refs bare → FQN quando unívoco

### 4.2 Graph (`catalog_taxonomy_graph.py`)

Nós lógicos: variable | table | api | domain

| Relation | Peso | Origem |
|----------|-----:|--------|
| `in_domain` | 0.4–0.5 | membership em hub de domínio |
| `domain_affinity` | 0.55 | mesmo domínio (cap 8 APIs/tabela) |
| `schema_hint` | 0.65 | var config ↔ schema de table |
| `name_match` | 0.8–0.9 | token do path = nome da table |
| `colocated` | 0.85 | mesmo pacote/módulo (sem top-level genérico) |
| `explicit` | **1.0** | anotação / OpenAPI |

**Strong links** (lifecycle): `explicit`, `name_match`, `colocated` com weight ≥ 0.8.

### 4.3 Lifecycle (`catalog_taxonomy_lifecycle.py`)

| Regra | Ação |
|-------|------|
| Table sem strong link | `status=unused` + `lifecycleReason` |
| Table com strong link e estava unused | volta para `active` |
| status `deprecated`/`experimental` | **não** sobrescreve |
| API sem relatedTables e sem strong | `orphan=true` |
| API health | nunca orphan |

Saídas: `ORPHANS.md`, `OWNERSHIP_GAPS.md`, `DOMAIN_MAP.md`, `lifecycle_summary.json`, refresh dos CATALOG_REPORT.

---

## 5. Modelo de dados (resumo)

### Table entry

```json
{
  "name": "trades",
  "schema": "btc",
  "fqn": "btc.trades",
  "source": "python-ddl",
  "columns": [{"name": "id", "type": "SERIAL", "nullable": true, "primaryKey": true}],
  "primaryKey": ["id"],
  "foreignKeys": [],
  "indexes": [],
  "locations": [{"file": "btc_trading_agent/training_db.py", "line": 225}],
  "category": "trading",
  "sensitive": false,
  "sensitiveColumns": [],
  "status": "active",
  "owner": "btc_trading_agent",
  "team": "trading",
  "relatedApis": ["POST /order", "GET /positions"]
}
```

### API entry

```json
{
  "operationKey": "POST /order",
  "method": "POST",
  "path": "/order",
  "source": "fastapi",
  "service": "mt5_bridge/bridge_api",
  "summary": "",
  "category": "trading",
  "sensitive": false,
  "status": "active",
  "owner": "mt5_bridge",
  "team": "trading",
  "relatedTables": ["btc.trades", "clear.trades"],
  "orphan": false,
  "locations": [{"file": "mt5_bridge/bridge_api.py", "line": 349, "service": "mt5_bridge/bridge_api"}]
}
```

### Graph edge

```json
{
  "from": {"type": "api", "id": "POST /order"},
  "to": {"type": "table", "id": "btc.trades"},
  "relation": "explicit",
  "weight": 1.0,
  "evidence": "annotation=btc.trades"
}
```

Schemas JSON formais: `.tables-catalog/schema.json`, `.apis-catalog/schema.json`, `.variables-catalog/schema.json`.

---

## 6. Enforcement architecture

```
Agente (Claude/Cursor/Grok)
  └─ PreToolUse → variable | table | api registry_validate
        duplicate → deny
        new/lint  → warn

git commit
  └─ .githooks/pre-commit
        [10/12] variables --staged
        [11/12] tables --staged
        [12/12] apis --staged
        duplicate → exit 1

Pull Request
  └─ GitHub Actions
        variable-registry-check.yml
        table-registry-check.yml
        api-registry-check.yml
```

Detalhes: [ENFORCEMENT.md](./ENFORCEMENT.md).

---

## 7. O que não faz (ainda)

- Não consulta Postgres live (só DDL no repo)
- Não gera OpenAPI a partir do código (só lê specs existentes)
- Não bloqueia commit por `new` ou `unused` (só por **duplicate**)
- Não publica Wiki.js automaticamente (artefatos MD prontos para sync manual/agente)
- Variables scanner ainda tem debt de ruído YAML (documentado no domínio variables)

---

## 8. Extensão

| Quer… | Faça… |
|-------|--------|
| Novo owner/team | `OWNER_RULES` em `taxonomy_meta.py` |
| Nova categoria de API | `API_CATEGORIES` / `SERVICE_CATEGORY_HINTS` em `catalog_apis.py` |
| Nova categoria de table | `TABLE_CATEGORIES` em `catalog_tables.py` |
| Novo tipo de relação no grafo | `catalog_taxonomy_graph.py` + docs GRAPH |
| Novo domain (ex: queues) | scanner + catalog dir + gate + wire no orquestrador |
