# ⚙️ Taxonomy Operations Guide

Operação diária do sistema de taxonomia.

---

## 1. Comandos principais

### Regenerar tudo

```bash
cd /workspace/eddie-auto-dev
python3 tools/catalog_taxonomy.py
```

Inclui: variables + tables + apis + graph + lifecycle + reports.

### Só tables e APIs (recomendado no dia a dia)

```bash
python3 tools/catalog_taxonomy.py --domain tables,apis
```

### Só grafo (catálogos já existem)

```bash
python3 tools/catalog_taxonomy.py --graph-only
```

### Só lifecycle

```bash
python3 tools/catalog_taxonomy.py --lifecycle-only
```

### Domínios isolados

```bash
python3 tools/catalog_variables.py
python3 tools/catalog_reporter.py --all

python3 tools/catalog_tables.py
python3 tools/catalog_apis.py

python3 tools/catalog_taxonomy_graph.py
python3 tools/catalog_taxonomy_lifecycle.py
```

### Updater (automação / timer)

```bash
python3 tools/catalog_updater.py --no-commit
python3 tools/catalog_updater.py --sync   # commit+push se configurado
```

---

## 2. Consultas úteis

### Tables

```bash
# status
python3 -c "
import json
from collections import Counter
c=json.load(open('.tables-catalog/catalog.json'))
print(c['metadata'].get('statusCounts'))
print(c['metadata'].get('ownerCounts'))
"

# listar unused
python3 -c "
import json
c=json.load(open('.tables-catalog/catalog.json'))
for cat,e in c['categories'].items():
  for fqn,d in e.items():
    if d.get('status')=='unused':
      print(fqn, d.get('owner'))
"

# uma table
python3 -c "
import json
c=json.load(open('.tables-catalog/catalog.json'))
print(json.dumps(c['categories']['trading']['btc.trades'], indent=2))
"
```

### APIs

```bash
# categories
python3 -c "
import json
c=json.load(open('.apis-catalog/catalog.json'))
print({k:len(v) for k,v in c['categories'].items()})
"

# com relatedTables
python3 -c "
import json
c=json.load(open('.apis-catalog/catalog.json'))
for cat,e in c['categories'].items():
  for k,d in e.items():
    if d.get('relatedTables'):
      print(k, '->', d['relatedTables'])
"

# orphans
python3 -c "
import json
c=json.load(open('.apis-catalog/catalog.json'))
print('orphanCount', c['metadata'].get('orphanCount'))
for cat,e in c['categories'].items():
  for k,d in e.items():
    if d.get('orphan'):
      print(k)
" | head
```

### Graph

```bash
# contagem por relation
python3 -c "
import json
from collections import Counter
g=json.load(open('.taxonomy-catalog/graph.json'))
print(Counter(e['relation'] for e in g['edges']))
print('strong', g.get('strongEdgeCount'))
"

# explicit links
python3 -c "
import json
g=json.load(open('.taxonomy-catalog/graph.json'))
for e in g['edges']:
  if e['relation']=='explicit':
    print(e['from'], '->', e['to'])
" | head -30

# domínio trading
python3 -c "
import json
g=json.load(open('.taxonomy-catalog/graph.json'))
print(g['domains'].get('trading'))
"
```

### Reports humanos

```bash
less .tables-catalog/CATALOG_REPORT.md
less .apis-catalog/CATALOG_REPORT.md
less .apis-catalog/SERVICE_ENDPOINTS.md
less .taxonomy-catalog/GRAPH_REPORT.md
less .taxonomy-catalog/ORPHANS.md
less .taxonomy-catalog/OWNERSHIP_GAPS.md
less docs/taxonomy/DOMAIN_MAP.md
```

---

## 3. Workflows comuns

### A) Criar endpoint novo que usa SQL

1. Escolher path/método sem colidir (consultar `.apis-catalog/catalog.json`).
2. Implementar rota.
3. Anotar:
   ```python
   # taxonomy: tables=btc.trades,clear.trades; owner=mt5_bridge
   @app.post("/order")
   ```
4. Regenerar:
   ```bash
   python3 tools/catalog_taxonomy.py --domain tables,apis
   ```
5. Commitar código + `.apis-catalog/` (+ grafo/lifecycle se gerados).
6. Pre-commit / CI validam anti-duplicata.

### B) Criar tabela nova

1. Escolher `schema.table` snake_case.
2. DDL com comentário:
   ```sql
   -- taxonomy: owner=marketing; status=active
   CREATE TABLE IF NOT EXISTS marketing.leads ( ... );
   ```
3. Linkar APIs/jobs que a usam (`tables=`).
4. `python3 tools/catalog_tables.py` (ou orquestrador).
5. Commitar SQL + `.tables-catalog/`.

### C) Reativar table `unused`

1. Achar quem deveria usar a table (código/job).
2. Anotar a API/job com `tables=schema.table`.
3. Regenerar → strong link → lifecycle volta `status=active`.

### D) Marcar API deprecated

```python
# taxonomy: status=deprecated
@app.get("/old")
```

ou OpenAPI:

```yaml
get:
  deprecated: true
```

### E) Commit bloqueado por duplicata

```
❌ ... é uma variação de 'FOO' ...
Commit bloqueado
```

**Ação:** reutilizar o nome canônico sugerido; não inventar variante.

---

## 4. Gates manuais

```bash
# staged (como o pre-commit)
python3 tools/hooks/variable_registry_validate.py --staged
python3 tools/hooks/table_registry_validate.py --staged
python3 tools/hooks/api_registry_validate.py --staged

# arquivo específico
python3 tools/hooks/api_registry_validate.py mt5_bridge/bridge_api.py
python3 tools/hooks/table_registry_validate.py clear_trading_agent/sql/clear_schema.sql
```

Códigos de saída:

| Exit | Significado |
|-----:|-------------|
| 0 | ok (pode haver WARNs de new/lint) |
| 1 | duplicate encontrado (bloqueia commit) |

---

## 5. CI

Workflows em `.github/workflows/`:

- `variable-registry-check.yml`
- `table-registry-check.yml`
- `api-registry-check.yml`

Disparam em PR para `main`, validam arquivos do diff contra os catálogos commitados.

---

## 6. Testes

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

## 7. Troubleshooting

| Sintoma | Causa provável | Ação |
|---------|----------------|------|
| Table marcada `unused` indevidamente | Falta anotação `tables=` na API | Anotar e regenerar |
| API `orphan=true` | Sem relatedTables/strong | Anotar tables ou aceitar se for UI/health-like |
| Gate false positive fuzzy | Nome parecido com existente | Renomear semanticamente ou reutilizar canônico |
| Owner `scripts` / team unassigned | Path genérico | Estender `OWNER_RULES` ou anotar `owner=` |
| Catalog não muda após anotação | Esqueceu regenerar | Rodar `catalog_taxonomy.py` |
| Pre-commit não roda gates | `core.hooksPath` | `git config core.hooksPath .githooks` |
| YAML variables “lixo” | Flatten de configs | Escopo variables (debt conhecido); não afeta tables/apis |
| `catalog_apis` varreu venv | skip quebrado | Path deve ser relativo; venv começa com `.venv` |

---

## 8. O que commitar

**Sempre com o código que muda o inventário:**

- `.tables-catalog/catalog.json` (+ reports se gerados)
- `.apis-catalog/catalog.json`
- `.variables-catalog/catalog.json` (se domain variables)
- `.taxonomy-catalog/*` (index, graph, orphans, lifecycle)

**Não commitar:** segredos reais (valores sensíveis já redigidos nos catálogos de variables).

---

## 9. Checklist de PR com taxonomia

- [ ] Nome canônico (sem variante de algo existente)
- [ ] Anotação `tables=` / `x-tables` se tocar SQL
- [ ] `owner`/`status` se não for óbvio pelo path
- [ ] `python3 tools/catalog_taxonomy.py --domain tables,apis`
- [ ] Reports/ORPHANS revisados se relevante
- [ ] Testes de taxonomy passam
- [ ] Pre-commit 10–12 verdes
