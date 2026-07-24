# 🕸 Taxonomy Graph (Tables ↔ APIs ↔ Variables)

Grafo cruzado entre os três domínios.

Voltar: [README](./README.md) · [Architecture](./ARCHITECTURE.md) · [Ownership](./OWNERSHIP.md)

---

## Geração

```bash
# Via orquestrador (padrão após scanners)
python3 tools/catalog_taxonomy.py --domain tables,apis

# Só grafo
python3 tools/catalog_taxonomy.py --graph-only
python3 tools/catalog_taxonomy_graph.py
```

---

## Artefatos

| Arquivo | Conteúdo |
|---------|----------|
| `.taxonomy-catalog/graph.json` | Grafo (meta + edges) |
| `.taxonomy-catalog/links.csv` | Arestas CSV |
| `.taxonomy-catalog/GRAPH_REPORT.md` | Resumo + top linked + strong sample |
| `.taxonomy-catalog/index.json` | Índice + meta do grafo |
| `docs/taxonomy/DOMAIN_MAP.md` | Mermaid dos hubs (gerado no lifecycle) |

---

## Tipos de relação

| Relation | Peso | Significado |
|----------|-----:|-------------|
| `in_domain` | 0.4–0.5 | Entidade → hub `domain:<name>` |
| `domain_affinity` | 0.55 | Table e API no mesmo domínio (cap 8/table) |
| `schema_hint` | 0.65 | Var de config ↔ tables do schema |
| `name_match` | 0.8–0.9 | Token do path ≈ nome da table |
| `colocated` | 0.85 | Mesmo pacote/módulo de origem |
| `explicit` | **1.0** | Anotação / OpenAPI `x-tables` |

**Strong** (usadas no lifecycle): `explicit`, `name_match`, `colocated` com weight ≥ 0.8.

Co-location **não** usa pastas monorepo genéricas sozinhas (`tools/`, `specialized_agents/`, …) — só `a/b` (pacote/módulo).

---

## Modelo mental

```
 variable ──in_domain──▶ domain:trading ◀──in_domain── api
      │                       ▲                         │
      └──schema_hint──▶ table ┴── explicit / name_match / colocated / domain_affinity
```

---

## Consultas

```bash
# relations
python3 -c "
import json
from collections import Counter
g=json.load(open('.taxonomy-catalog/graph.json'))
print('edges', g['edgeCount'], 'strong', g.get('strongEdgeCount'))
print(Counter(e['relation'] for e in g['edges']))
"

# explicit only
python3 -c "
import json
g=json.load(open('.taxonomy-catalog/graph.json'))
for e in g['edges']:
  if e['relation']=='explicit':
    f,t=e['from'],e['to']
    print(f\"{f['type']}:{f['id']} -> {t['type']}:{t['id']}\")
" | head -40

# domínio
python3 -c "
import json
g=json.load(open('.taxonomy-catalog/graph.json'))
print(json.dumps(g['domains'].get('trading'), indent=2))
"
```

---

## Domain map (wiki-friendly)

Diagrama Mermaid gerado no lifecycle:

- [DOMAIN_MAP.md](./DOMAIN_MAP.md)
- `.taxonomy-catalog/DOMAIN_MAP.md`

Publicável na Wiki.js como página de arquitetura.

---

## Manutenção

O grafo é **100% derivado**. Não editar `graph.json` à mão.

```bash
python3 tools/catalog_taxonomy.py
```

Após anotar `tables=` / `x-tables`, as arestas `explicit` aparecem e o lifecycle reclassifica unused/orphan.
