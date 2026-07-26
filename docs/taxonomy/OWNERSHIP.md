# 👤 Ownership & Lifecycle

Metadados de **dono**, **time** e **ciclo de vida** (tables + APIs).

Voltar: [README](./README.md) · [Annotations](./ANNOTATIONS.md) · [Graph](./GRAPH.md)

---

## Ownership

Cada table/endpoint recebe:

| Campo | Significado | Exemplo |
|-------|-------------|---------|
| `owner` | Serviço/módulo dono | `btc_trading_agent`, `mt5_bridge` |
| `team` | Time lógico | `trading`, `security`, `storage` |

### Resolução (ordem)

1. Anotação `taxonomy: owner=...; team=...`
2. `OWNER_RULES` por fragmento de path (`tools/taxonomy_meta.py`)
3. `SCHEMA_OWNERS` (`btc` → trading, `marketing` → growth)
4. Fallback: 1º segmento do path, `team=unassigned`

### Registry principal (OWNER_RULES)

| Path fragment | owner | team |
|---------------|-------|------|
| `btc_trading_agent` | btc_trading_agent | trading |
| `clear_trading_agent` | clear_trading_agent | trading |
| `mt5_bridge` | mt5_bridge | trading |
| `marketing` | marketing | growth |
| `secrets_agent` | secrets_agent | security |
| `nextcloud` / `ltfs` / `tape` / `storage_portal` | … | storage |
| `wiki` | wiki | knowledge |
| `cmdb` | cmdb | infra |
| `banking` / `belvo` | banking | finance |
| `x_agent` | x_agent | social |
| `agent_communication` / `agent_ipc` | agent_bus | platform |
| `operation_agent` | operation_agent | platform |
| `conube` | conube | ops |
| `huggingface` | huggingface | llm |
| `bn_acervo` | bn_acervo | content |
| `code_runner` | code_runner | platform |
| `grafana` / home setup | grafana / home_automation | observability / iot |
| `user_management` | user_management | identity |

**Incluir serviço novo:** edite `OWNER_RULES` em `tools/taxonomy_meta.py` e regenere.

### Gaps

Relatório: `.taxonomy-catalog/OWNERSHIP_GAPS.md`

- `tables_unassigned_team`
- `apis_unassigned_team`
- (unknown owner deve tender a 0)

---

## Lifecycle status

Valores: `active` | `deprecated` | `unused` | `experimental`

### Detecção no scan

| Fonte | Sinal |
|-------|--------|
| Comentário | `taxonomy: status=deprecated` |
| Python | `@deprecated`, `deprecated=True` |
| OpenAPI | `deprecated: true`, `x-status` |
| Default | `active` |

### Inferência pós-grafo (`unused`)

| Entidade | Critério | Efeito |
|----------|----------|--------|
| **Table** | zero strong links (`explicit`/`name_match`/`colocated`) | `status=unused` |
| **API** | sem `relatedTables` e sem strong | `orphan=true` (**não** muda status) |
| Health endpoints | `/health`, `/metrics`, … | nunca orphan |
| `deprecated` / `experimental` | — | **não** sobrescritos |

Se a table ganhar strong link depois, lifecycle restaura `active`.

### Artefatos

| Arquivo | Conteúdo |
|---------|----------|
| `.taxonomy-catalog/ORPHANS.md` | unused tables + orphan APIs |
| `.taxonomy-catalog/OWNERSHIP_GAPS.md` | gaps de owner/team |
| `.taxonomy-catalog/DOMAIN_MAP.md` | mermaid |
| `.taxonomy-catalog/lifecycle_summary.json` | contagens |
| `docs/taxonomy/DOMAIN_MAP.md` | cópia docs |

---

## Links explícitos API ↔ Table

Ver [ANNOTATIONS.md](./ANNOTATIONS.md).

Resumo:

```python
# taxonomy: tables=btc.trades,clear.trades; owner=mt5_bridge
@app.post("/order")
```

```yaml
get:
  x-tables: [btc.llm_calls]
```

Efeito: `relatedTables` + edge `explicit` + table active + API not orphan.

---

## Regenerar

```bash
python3 tools/catalog_taxonomy.py --domain tables,apis
python3 tools/catalog_taxonomy.py --lifecycle-only
```

Reports:

```bash
less .tables-catalog/CATALOG_REPORT.md   # Ownership + Lifecycle sections
less .apis-catalog/CATALOG_REPORT.md
less .taxonomy-catalog/ORPHANS.md
less .taxonomy-catalog/OWNERSHIP_GAPS.md
```

---

## Boas práticas

1. Todo endpoint que toca SQL deve ter `tables=` / `x-tables`.  
2. Preferir FQN `schema.table`.  
3. Owner deve mapear para um serviço real (não “misc” genérico).  
4. `unused` é um **sinal de higiene**, não exclusão física da table.  
5. Revisar `ORPHANS.md` periodicamente (ex.: sprint de taxonomia).
