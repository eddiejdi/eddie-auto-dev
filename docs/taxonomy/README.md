# 🏷 Homelab Taxonomy System

Documentação completa da taxonomia unificada do repositório **Shared Auto-Dev / eddie-auto-dev**.

> **Última atualização:** 2026-07-24  
> **Versão do índice:** 1.1.0 (`.taxonomy-catalog/index.json`)

---

## O que é

Sistema de **inventário + enforcement + grafo** para três domínios do homelab:

| Domínio | O que cataloga | Chave canônica |
|---------|----------------|----------------|
| **Variables** | Variáveis de ambiente / config | `UPPER_SNAKE_CASE` |
| **Tables** | Tabelas SQL / DDL embutido | `schema.table` |
| **APIs** | Endpoints HTTP (FastAPI/Flask/OpenAPI) | `METHOD /path` |

Sobre esses inventários existem:

- **Gates anti-duplicata** (PreToolUse + pre-commit + CI)
- **Ownership** (`owner`, `team`) e **lifecycle** (`active` / `deprecated` / `experimental` / `unused`)
- **Grafo cruzado** variables ↔ tables ↔ APIs
- **Orphans / gaps** acionáveis para higiene contínua

---

## Índice da documentação

| Doc | Conteúdo |
|-----|----------|
| **[README.md](./README.md)** (este) | Visão geral, números, mapa rápido |
| **[ARCHITECTURE.md](./ARCHITECTURE.md)** | Arquitetura, fluxos, artefatos, schemas |
| **[OPERATIONS.md](./OPERATIONS.md)** | Comandos do dia a dia, regenerar, troubleshooting |
| **[ANNOTATIONS.md](./ANNOTATIONS.md)** | Como anotar código/SQL/OpenAPI |
| **[ENFORCEMENT.md](./ENFORCEMENT.md)** | Hooks, pre-commit, CI, regras de gate |
| **[TABLES.md](./TABLES.md)** | Domínio Tables em detalhe |
| **[APIS.md](./APIS.md)** | Domínio APIs em detalhe |
| **[GRAPH.md](./GRAPH.md)** | Grafo cruzado e relações |
| **[OWNERSHIP.md](./OWNERSHIP.md)** | Owner, team, unused, orphans |
| **[DOMAIN_MAP.md](./DOMAIN_MAP.md)** | Diagrama Mermaid dos hubs (gerado) |
| **[Variables taxonomy](../variables-taxonomy/README.md)** | Domínio Variables (legado expandido) |
| **[Quick start (raiz)](../../TAXONOMY_QUICK_START.md)** | Entrada executiva de 2 minutos |

---

## Snapshot atual (gerado)

| Métrica | Valor |
|---------|------:|
| Variables (catálogo) | ~1998 |
| Tables | **63** (5 schemas) |
| Tables active / unused | **32** / **31** |
| API endpoints | **174** (25 serviços) |
| APIs deprecated | **1** |
| APIs com `relatedTables` | **26** |
| APIs orphan | **112** |
| Graph edges | **1266** (strong ≈ **290**) |
| Explicit API↔table | **105** |
| Owners desconhecidos (tables/apis) | **0** / **0** |

> Números mudam a cada `python3 tools/catalog_taxonomy.py`. Fonte de verdade: os `catalog.json` e `lifecycle_summary.json`.

---

## Mapa mental

```
                    ┌──────────────────────────┐
                    │  tools/catalog_taxonomy  │
                    │       (orquestrador)     │
                    └────────────┬─────────────┘
           ┌─────────────────────┼─────────────────────┐
           ▼                     ▼                     ▼
   catalog_variables      catalog_tables         catalog_apis
           │                     │                     │
           ▼                     ▼                     ▼
  .variables-catalog/   .tables-catalog/      .apis-catalog/
           │                     │                     │
           └─────────────────────┼─────────────────────┘
                                 ▼
                    catalog_taxonomy_graph
                                 │
                                 ▼
                    .taxonomy-catalog/graph.json
                                 │
                                 ▼
                 catalog_taxonomy_lifecycle
                    unused · orphans · gaps · domain map
                                 │
           ┌─────────────────────┼─────────────────────┐
           ▼                     ▼                     ▼
   PreToolUse hooks        pre-commit [10-12]      GitHub CI
```

---

## Comando único

```bash
cd /workspace/eddie-auto-dev

# Inventário completo + grafo + lifecycle
python3 tools/catalog_taxonomy.py

# Só tables + apis (mais rápido no dia a dia)
python3 tools/catalog_taxonomy.py --domain tables,apis
```

---

## Fluxo do desenvolvedor / agente

1. **Antes de criar** variável, tabela ou endpoint: consultar o catálogo do domínio.
2. **Preferir reutilizar** o nome canônico (o gate bloqueia duplicatas “quase iguais”).
3. **Se for novo de verdade:**
   - anotar purpose / `tables=` / `owner` quando aplicável ([ANNOTATIONS.md](./ANNOTATIONS.md));
   - regenerar o domínio;
   - commitar o `catalog.json` junto com o código.
4. **Após merge:** lifecycle reclassifica tables sem link strong como `unused` e lista APIs orphan.

---

## Ferramentas (código)

| Path | Função |
|------|--------|
| `tools/catalog_taxonomy.py` | Orquestrador (domains + graph + lifecycle) |
| `tools/catalog_variables.py` | Scanner de variáveis |
| `tools/catalog_tables.py` | Scanner de tabelas |
| `tools/catalog_apis.py` | Scanner de APIs |
| `tools/catalog_taxonomy_graph.py` | Grafo cruzado |
| `tools/catalog_taxonomy_lifecycle.py` | unused / orphans / gaps / domain map |
| `tools/taxonomy_meta.py` | Ownership, status, parse de anotações |
| `tools/catalog_reporter.py` | Reports do domínio variables |
| `tools/catalog_updater.py` | Automação (timer/commit) — chama orquestrador |
| `tools/hooks/variable_registry_validate.py` | Gate variables |
| `tools/hooks/table_registry_validate.py` | Gate tables |
| `tools/hooks/api_registry_validate.py` | Gate APIs |

---

## Artefatos gerados

```
.variables-catalog/
  catalog.json | catalog.csv | CATALOG_REPORT.md | SERVICE_VARIABLES.md | schema.json

.tables-catalog/
  catalog.json | catalog.csv | CATALOG_REPORT.md | schema.json

.apis-catalog/
  catalog.json | catalog.csv | CATALOG_REPORT.md | SERVICE_ENDPOINTS.md | schema.json

.taxonomy-catalog/
  index.json              # índice unificado
  graph.json              # grafo completo
  links.csv               # arestas
  GRAPH_REPORT.md
  ORPHANS.md              # unused tables + orphan APIs
  OWNERSHIP_GAPS.md
  DOMAIN_MAP.md           # mermaid
  lifecycle_summary.json
```

---

## Testes

```bash
python3 -m pytest \
  tests/test_catalog_variables.py \
  tests/test_catalog_tables.py \
  tests/test_catalog_apis.py \
  tests/test_catalog_taxonomy_graph.py \
  tests/test_catalog_taxonomy_lifecycle.py \
  tests/test_taxonomy_meta.py \
  tests/test_variable_registry_validate.py \
  tests/test_table_registry_validate.py \
  tests/test_api_registry_validate.py \
  -q
```

---

## Histórico

| Data | Mudança |
|------|---------|
| 2026-06-21 | Catálogo de variáveis (inicial) |
| 2026-07-14 | Enforcement de variáveis (hook + pre-commit + CI) |
| 2026-07-24 | Escopo **Tables** + **APIs** |
| 2026-07-24 | Grafo cruzado, categorias API refinadas, `sensitive`/`status` |
| 2026-07-24 | Ownership, anotações `x-tables`, lifecycle `unused` |
| 2026-07-24 | Orphans, ownership gaps, domain map, backfill de links críticos |
| 2026-07-24 | Documentação consolidada (`docs/taxonomy/*` + `TAXONOMY_QUICK_START.md`) |

---

## Próximos passos sugeridos

1. Reduzir **unused tables** anotando APIs/jobs que as usam.
2. Reduzir **orphan APIs** com `taxonomy: tables=...` ou `x-tables`.
3. Publicar `DOMAIN_MAP.md` / `ORPHANS.md` na Wiki.js.
4. Dashboard Grafana a partir de `lifecycle_summary.json`.
