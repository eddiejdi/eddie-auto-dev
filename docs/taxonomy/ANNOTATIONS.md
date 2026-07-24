# ✏️ Taxonomy Annotations Reference

Como declarar metadados e links no código-fonte.  
Parser: `tools/taxonomy_meta.py`.

---

## 1. Formato principal

Comentário (Python `#`, SQL `--`, ou linha em description OpenAPI):

```text
taxonomy: key=value; key2=value2
```

### Chaves suportadas

| Key | Valores | Aplica-se a |
|-----|---------|-------------|
| `tables` / `table` | FQNs ou nomes bare, CSV | API (link → tables) |
| `status` | `active` \| `deprecated` \| `experimental` \| `unused` | API, Table |
| `owner` | id do serviço/módulo | API, Table |
| `team` | time lógico | API, Table |

### Exemplos

```python
# taxonomy: tables=btc.trades,clear.trades; owner=mt5_bridge; status=active
@app.post("/order")
async def place_order(...):
    ...
```

```python
# taxonomy: status=deprecated
@app.get("/legacy")
def legacy():
    ...
```

```sql
-- taxonomy: owner=marketing; team=growth; status=active
CREATE TABLE IF NOT EXISTS marketing.leads (
    id SERIAL PRIMARY KEY,
    email TEXT NOT NULL
);
```

---

## 2. Atalhos

### Tables shorthand

```python
# tables: marketing.leads, marketing.daily_metrics
@router.get("/leads/stats")
```

```python
# table=btc.candles
@app.get("/symbol/{symbol}/rates")
```

### Status via marcadores de código

| Marcador | Status inferido |
|----------|-----------------|
| `@deprecated` | deprecated |
| `deprecated=True` | deprecated |
| `taxonomy: status=deprecated` | deprecated |
| `@experimental` | experimental |
| `taxonomy: status=experimental` | experimental |

> Marcadores genéricos tipo “WIP” no meio do arquivo **não** disparam experimental (evita falso positivo).

---

## 3. OpenAPI / Swagger

```yaml
paths:
  /api/v1/models:
    get:
      summary: List models
      x-tables:
        - btc.llm_calls
        - btc.llm_log_config
      # ou singular:
      # x-table: btc.llm_calls
      responses:
        "200":
          description: OK

  /api/v1/functions:
    get:
      summary: List functions
      deprecated: true
      x-status: deprecated
```

Extensões reconhecidas:

| Extensão | Uso |
|----------|-----|
| `x-tables` | lista de FQNs |
| `x-table` | um FQN |
| `x-db-tables` / `x-db-table` | aliases |
| `x-status` / `x-lifecycle` | status explícito |
| `deprecated: true` | status deprecated |

Descriptions/summaries também são varridas por `taxonomy: …`.

---

## 4. Resolução de nomes de tabela

| Entrada | Resolução |
|---------|-----------|
| `btc.trades` | FQN exato |
| `trades` | se só existir um `*.trades` no catálogo → esse FQN; se ambíguo, mantém bare |
| nome inexistente | guardado como soft ref (evidence no grafo) |

Preferir **sempre FQN** (`schema.table`) em anotações novas.

---

## 5. Onde colocar o comentário

O scanner olha uma **janela de contexto** ao redor do decorator / `CREATE TABLE` (~250–400 chars antes e depois).

**Bom:**
```python
# taxonomy: tables=public.agent_ipc
@router.get("/messages")
async def communication_messages(...):
```

**Ruim (longe demais):**
```python
# taxonomy: tables=public.agent_ipc
# ... 80 linhas ...
@router.get("/messages")
```

Para OpenAPI, coloque `x-tables` no mesmo operation object do método HTTP.

---

## 6. Seeds já aplicados no repo (referência)

| Local | Anotação |
|-------|----------|
| `mt5_bridge/bridge_api.py` | order, positions, orders, account, rates, history/deals |
| `marketing/lead_capture_api.py` | POST/GET leads |
| `storage_portal_api.py` | portal tokens/users/payments/contracts |
| `specialized_agents/agent_communication_bus.py` | messages, publish/send |
| `tools/operation_agent/evoke_handler.py` | evoke → agent_actions |
| `docs/openapi.yaml` | models, rag/index, functions deprecated |
| `marketing/db_migrate.py` | leads owner |
| `tools/migrations/001_agent_governance.sql` | agent_actions owner |

Use-os como templates.

---

## 7. Efeito no pipeline

```
anotação no código
    → catalog_apis / catalog_tables grava relatedTables / owner / status
    → graph cria edge relation=explicit weight=1.0
    → lifecycle: table deixa de ser unused; API deixa de ser orphan
    → reports ORPHANS / CATALOG atualizados
```

Sem regenerar o catálogo, **nada muda** nos JSON/gates.

```bash
python3 tools/catalog_taxonomy.py --domain tables,apis
```

---

## 8. Anti-padrões

| Evitar | Por quê |
|--------|---------|
| Variantes de nome (`API_TOKEN` vs `APITOKEN`) | gate **deny** |
| `tables=trades` ambíguo (btc+clear) | link fraco/errado |
| Esquecer regenerar catálogo | CI/local usam JSON velho |
| Marcar `unused` na mão no JSON | lifecycle sobrescreve; anote links |
| Colocar segredos em annotations | só metadados de nome/status/owner |

---

## 9. Snippets copy-paste

### FastAPI trading

```python
# taxonomy: tables=btc.trades,clear.trades; owner=mt5_bridge
@app.post("/order")
async def place_order(...):
    ...
```

### FastAPI marketing

```python
# taxonomy: tables=marketing.leads,marketing.daily_metrics; owner=marketing
@router.post("/leads")
async def capture_lead(...):
    ...
```

### SQL

```sql
-- taxonomy: owner=btc_trading_agent; team=trading; status=active
CREATE TABLE IF NOT EXISTS btc.new_feature (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### OpenAPI

```yaml
/api/v1/example:
  get:
    summary: Example
    x-tables: [btc.trades]
    responses:
      "200":
        description: OK
```
