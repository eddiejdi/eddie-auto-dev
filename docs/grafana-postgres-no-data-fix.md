# Grafana PostgreSQL Plugin - No Data Fix

## Problema

Painéis Grafana com datasource PostgreSQL retornavam "No data" ou silenciosamente falhavam.

**Sintomas observados**:
- `/api/ds/query` (postgres) → **500 silencioso**
- `/api/datasources/proxy/uid/<uid>/query` → **502 Bad Gateway**
- Health check do datasource → **OK** (conexão com DB funcionava)
- Datasource Prometheus (mesma rota `/api/ds/query`) → **200 OK**
- Ambos os datasources postgres falhavam (btc-trading-pg + Eddie Bus)

## Causa Raiz

**Campo `database` no nível superior do YAML de provisioning, em vez de dentro de `jsonData`.**

```yaml
# ERRADO (causa 500 silencioso)
datasources:
  - name: BTC Trading PostgreSQL
    url: 172.17.0.1:5433
    user: postgres
    database: btc_trading        # ← ESTE CAMPO NÃO É LIDO PELO PLUGIN
    jsonData:
      postgresVersion: 1500
      sslmode: disable

# CORRETO
datasources:
  - name: BTC Trading PostgreSQL
    url: 172.17.0.1:5433
    user: postgres
    jsonData:
      database: btc_trading      # ← AQUI É ONDE O PLUGIN PROCURA
      postgresVersion: 1500
      sslmode: disable
```

### Por que o health check passa mas queries falham?

O health check do Grafana usa uma rota de conexão separada que lê `database` do nível superior. A query engine usa `jsonData.database`. Quando `database` está no nível errado, a query engine não encontra o nome do banco → 500.

## Diagnóstico

1. **Health check OK** → Conexão TCP com DB funciona
2. **Prometheus funciona na mesma rota** → Não é bug de auth nem de rede
3. **Ambos postgres datasources falham** → Não é bug de query específica
4. **`/api/datasources/proxy` retorna 502** → Proxy HTTP não consegue falar com protocolo binário Postgres (esperado para datasource tipo postgres com `access=proxy`)
5. **`database` no nível superior** → Confirmado via API: campo estava no lugar errado

## Correção

**Arquivo**: `monitoring/grafana/provisioning/datasources/datasources.yml`

Mudanças aplicadas:
- `database` movido de nível superior para dentro de `jsonData`
- `readOnly: true` removido do btc-trading-pg (permite edição via API)
- Password mantido como `${GF_DATABASE_PASSWORD}` (variável de ambiente do docker-compose)

## Deploy

```bash
# 1. Copiar arquivo corrigido para o homelab
# 2. Reiniciar container Grafana
docker restart grafana

# 3. Validar
curl -u "admin:<password>" -X POST -H "Content-Type: application/json" \
  "https://grafana.rpa4all.com/api/ds/query" \
  -d '{"queries":[{"refId":"A","datasourceId":855,"rawSql":"SELECT 1","format":1}],"from":"now-1d","to":"now"}'
# Deve retornar 200 com dados
```

## Lições Aprendidas

1. **Grafana provisioned datasources são read-only** — não é possível editar via API. Alterações requerem editar o YAML e reiniciar o container.
2. **`database` em PostgreSQL datasource DEVE estar em `jsonData`** — health check não valida isso.
3. **`$GF_DATABASE_PASSWORD` funciona em provisioning YAML** — Grafana resolve variáveis de ambiente do container.
4. **Restart do container não resolve bugs de config** — o YAML é relido no restart, mas se o YAML está errado, o bug persiste.
5. **Plugin Grafana-PostgreSQL pode falhar silenciosamente** — 500 sem mensagem de erro detalhada. O endpoint `/api/datasources/proxy` dá 502 que é mais informativo.

## Referências

- [GitHub Issue #65105](https://github.com/grafana/grafana/issues/65105) — "Provisioned datasource's database field is missing"
- [GitHub Issue #112418](https://github.com/grafana/grafana/issues/112418) — "Datasource: Postgres connection broken in 12.2.0"
- [Grafana Provisioning Docs](https://grafana.com/docs/grafana/latest/administration/provisioning/#data-sources)
