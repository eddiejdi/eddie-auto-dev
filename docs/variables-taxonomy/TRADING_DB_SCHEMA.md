# Migração de schema do trading — variáveis

Variáveis de `btc_trading_agent/training_db.py` que controlam a migração de
schema executada no start de cada `crypto-agent@*`.

| Variável | Default | Propósito |
|---|---|---|
| `BTC_SCHEMA_LOCK_TIMEOUT` | `5s` | `SET LOCAL lock_timeout` da transação de migração. Sem ele, o `ALTER TABLE` entra na fila atrás das transações dos agentes que já estão negociando e o par DDL×DML fecha ciclo de deadlock. Falhar rápido e repetir é melhor que segurar `AccessExclusiveLock`. Aceita qualquer literal de intervalo do Postgres. |
| `BTC_SCHEMA_MAX_ATTEMPTS` | `5` | Tentativas de `_ensure_schema()` antes de propagar o erro. Só repete em `DeadlockDetected`/`LockNotAvailable`; qualquer outra exceção sobe na primeira. Backoff 1s→2s→4s→8s. |

## Por que existem

Incidente de 2026-07-25 (deploy run 30177183701): dois agentes que subiram com
1s de diferença morreram com `psycopg2.errors.DeadlockDetected` em
`_ensure_schema()`. 5 ocorrências em 24h, 12 das 14 instâncias atingidas em
algum momento — sempre em deploy.

`PROFILE_MIGRATION_SQL` rodava **a cada start**: 13 `ALTER TABLE`
(`AccessExclusiveLock` em `btc.trades`, `btc.decisions`, `btc.ai_plans`) mais
`UPDATE ... WHERE profile IS NULL` varrendo a tabela inteira. Enquanto isso, os
outros 13 agentes negociavam nessas mesmas tabelas.

O `pg_advisory_xact_lock('btc_ensure_schema')` que já existia serializa os
agentes **entre si**, mas não protege contra as transações de quem já está
rodando. Daí o ciclo DDL×DML.

## A correção principal não é uma variável

É o skip: `_profile_migration_applied()` consulta `information_schema.columns`
e pula `PROFILE_MIGRATION_SQL` quando o schema já está no estado final. No caso
comum — todo restart depois do primeiro — não há DDL nenhum, então não há
`AccessExclusiveLock` a disputar. As duas variáveis acima cobrem o caso em que
a migração é de fato necessária.

`PROFILE_MIGRATION_COLUMNS` declara o estado final esperado (tabela, coluna,
default). `tests/test_training_db_schema_migration.py` falha se ela divergir do
SQL — sem isso, um `ALTER TABLE` novo passaria a ser pulado silenciosamente.
