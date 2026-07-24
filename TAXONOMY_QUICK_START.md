# 🏷 Taxonomy System — Quick Start

Entrada rápida para a taxonomia unificada do homelab (**Variables + Tables + APIs**).

Documentação completa: [`docs/taxonomy/README.md`](./docs/taxonomy/README.md)

---

## Em 30 segundos

```bash
cd /workspace/eddie-auto-dev

# Regenerar inventários + grafo + lifecycle
python3 tools/catalog_taxonomy.py --domain tables,apis

# Ver resumo
less .tables-catalog/CATALOG_REPORT.md
less .apis-catalog/CATALOG_REPORT.md
less .taxonomy-catalog/ORPHANS.md
less docs/taxonomy/DOMAIN_MAP.md
```

---

## O que existe

| Domínio | Catálogo | Gate |
|---------|----------|------|
| Variables | `.variables-catalog/` | `tools/hooks/variable_registry_validate.py` |
| Tables | `.tables-catalog/` | `tools/hooks/table_registry_validate.py` |
| APIs | `.apis-catalog/` | `tools/hooks/api_registry_validate.py` |
| Graph + lifecycle | `.taxonomy-catalog/` | derivado |

**Números de referência (2026-07-24):** ~1998 vars · 63 tables · 174 APIs · 1266 edges no grafo.

---

## Anotar (obrigatório quando toca SQL)

```python
# taxonomy: tables=btc.trades,clear.trades; owner=mt5_bridge
@app.post("/order")
async def place_order(...):
    ...
```

```sql
-- taxonomy: owner=marketing; status=active
CREATE TABLE IF NOT EXISTS marketing.leads ( ... );
```

```yaml
get:
  x-tables: [btc.llm_calls]
  deprecated: true
```

Guia completo: [`docs/taxonomy/ANNOTATIONS.md`](./docs/taxonomy/ANNOTATIONS.md)

---

## Enforcement

| Onde | Efeito de duplicata |
|------|---------------------|
| PreToolUse (Claude/Cursor/Grok) | **deny** |
| pre-commit `[10–12/12]` | **bloqueia commit** |
| CI PR | **falha o check** |

`new` / `lint` = aviso (documente + regenere o catálogo).

Detalhes: [`docs/taxonomy/ENFORCEMENT.md`](./docs/taxonomy/ENFORCEMENT.md)

---

## Fluxo mínimo ao mudar código

1. Implemente variável / table / API.
2. Anote links (`tables=`) e owner se necessário.
3. `python3 tools/catalog_taxonomy.py --domain tables,apis`
4. Commit **código + catálogos**.
5. Pre-commit e CI validam anti-duplicata.

---

## Docs por tema

| Tema | Path |
|------|------|
| Overview | [docs/taxonomy/README.md](./docs/taxonomy/README.md) |
| Arquitetura | [docs/taxonomy/ARCHITECTURE.md](./docs/taxonomy/ARCHITECTURE.md) |
| Operação | [docs/taxonomy/OPERATIONS.md](./docs/taxonomy/OPERATIONS.md) |
| Tables | [docs/taxonomy/TABLES.md](./docs/taxonomy/TABLES.md) |
| APIs | [docs/taxonomy/APIS.md](./docs/taxonomy/APIS.md) |
| Graph | [docs/taxonomy/GRAPH.md](./docs/taxonomy/GRAPH.md) |
| Ownership / unused | [docs/taxonomy/OWNERSHIP.md](./docs/taxonomy/OWNERSHIP.md) |
| Domain map (mermaid) | [docs/taxonomy/DOMAIN_MAP.md](./docs/taxonomy/DOMAIN_MAP.md) |
| Variables (detalhe) | [docs/variables-taxonomy/README.md](./docs/variables-taxonomy/README.md) |
| Variables quick start | [VARIABLES_CATALOG_QUICK_START.md](./VARIABLES_CATALOG_QUICK_START.md) |

---

## Testes

```bash
python3 -m pytest tests/test_catalog_tables.py tests/test_catalog_apis.py \
  tests/test_catalog_taxonomy_graph.py tests/test_catalog_taxonomy_lifecycle.py \
  tests/test_taxonomy_meta.py tests/test_*_registry_validate.py -q
```
