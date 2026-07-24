# 🗄 Tables Taxonomy

Catálogo de **tabelas de banco** (PostgreSQL e DDL embutido em Python).

Voltar ao índice: [README](./README.md) · [Architecture](./ARCHITECTURE.md) · [Annotations](./ANNOTATIONS.md)

---

## Snapshot

| Métrica | Valor típico |
|---------|--------------|
| Total tables | 63 |
| Schemas | 5 (`btc`, `clear`, `marketing`, `public`, `whatsapp`, …) |
| Active / unused | ~32 / ~31 (pós-lifecycle) |
| Owners | btc_trading_agent, clear_trading_agent, marketing, storage_portal, … |

Fonte: `.tables-catalog/catalog.json` → `metadata`.

---

## Geração

```bash
python3 tools/catalog_tables.py
# ou
python3 tools/catalog_taxonomy.py --domain tables
```

**Saídas:**

| Arquivo | Conteúdo |
|---------|----------|
| `.tables-catalog/catalog.json` | Fonte de verdade do gate |
| `.tables-catalog/CATALOG_REPORT.md` | Resumo + ownership + status |
| `.tables-catalog/catalog.csv` | Export planilha |
| `.tables-catalog/schema.json` | JSON Schema |

---

## Fontes escaneadas

| Source | Captura |
|--------|---------|
| `*.sql` | `CREATE TABLE`, `CREATE INDEX`, FKs, `search_path` |
| `*.py` com DDL | `CREATE TABLE IF NOT EXISTS`, incl. `{SCHEMA}.table` |

**Ignorados:** `tests/`, venvs, `node_modules/`, caches, artefatos grandes.

Parser de body usa **parênteses balanceados** (suporta `NUMERIC(18,4)`).

---

## Chave canônica

```
schema.table   # lowercase
```

Exemplos: `btc.trades`, `clear.decisions`, `marketing.leads`, `public.agent_actions`.

### Resolução de schema

1. Qualificador no DDL  
2. `SCHEMA = "..."` no Python  
3. `SET search_path TO …`  
4. Hint de path (`btc_trading_agent` → `btc`, `clear_trading_agent` → `clear`, `marketing` → `marketing`)  
5. Fallback `public`

---

## Categorias

| Category | Exemplos de nome |
|----------|------------------|
| trading | trade, candle, decision, exchange_*, conversion, llm_call, … |
| sentiment | news_sentiment, training_sample, llm_shadow, … |
| marketing | lead, campaign, email_log, x_posts, … |
| governance | agent_action, schema_migration |
| ipc | agent_ipc |
| portal | contract, portal_user, api_token, payment |
| content | content_queue, conversation, message |
| home | home_device* |
| identity | user_management |
| general | fallback |

---

## Campos da entry

| Campo | Descrição |
|-------|-----------|
| `fqn`, `schema`, `name` | identidade |
| `source` | `sql` \| `python-ddl` \| `index-ref` |
| `columns[]` | name, type, nullable, primaryKey |
| `primaryKey`, `foreignKeys`, `indexes` | constraints |
| `locations[]` | file + line |
| `category` | semântica |
| `sensitive` / `sensitiveColumns` | colunas password/token/secret/… |
| `status` | active \| deprecated \| experimental \| **unused** |
| `owner` / `team` | ownership |
| `relatedApis` | preenchido via grafo quando APIs apontam para a table |
| `lifecycleReason` | por que ficou unused (se aplicável) |

---

## Gate

```bash
python3 tools/hooks/table_registry_validate.py --staged
python3 tools/hooks/table_registry_validate.py path/to/file.sql
```

| Status | Efeito |
|--------|--------|
| ok | silencioso |
| duplicate (fuzzy) | **bloqueia** |
| lint | aviso |
| new | aviso → documentar + rescanear |

Ver [ENFORCEMENT.md](./ENFORCEMENT.md).

---

## Lifecycle `unused`

Table **sem** aresta strong no grafo (`explicit` / `name_match` / `colocated`) → `status=unused`.

Isso **não** apaga a table do catálogo; sinaliza “sem link API/código detectado”.

Reativar: anotar API/job com `tables=schema.table` e regenerar.

Lista: `.taxonomy-catalog/ORPHANS.md`.

---

## Ao criar uma table

1. FQN snake_case sem colidir com existentes  
2. Comentário `-- taxonomy: owner=...; status=active`  
3. Anotar APIs/jobs consumidores  
4. `python3 tools/catalog_tables.py` (ou orquestrador)  
5. Commitar DDL + `.tables-catalog/`

Templates: [ANNOTATIONS.md](./ANNOTATIONS.md).

---

## Consultas rápidas

```bash
# report
less .tables-catalog/CATALOG_REPORT.md

# CSV
column -t -s, .tables-catalog/catalog.csv | less -S

# por owner
python3 -c "
import json
c=json.load(open('.tables-catalog/catalog.json'))
for o,n in sorted(c['metadata']['ownerCounts'].items(), key=lambda x:-x[1]):
  print(f'{n:3} {o}')
"
```
