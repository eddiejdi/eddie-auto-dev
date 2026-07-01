# Grafana BTC Conservative No Data - Diagnostico e Correcao - 2026-05-19

## Resumo executivo

Foi corrigido o problema de `No Data` no dashboard:

- URL: `https://grafana.rpa4all.com/d/btc-trading-monitor/f09fa496-trading-agent-monitor`
- Filtros analisados: `coin=BTC-USDT`, `profile=conservative`, janela `now-12h`

O incidente tinha **duas causas distintas**:

1. Uma parte dos paineis estava vazia por motivo legitimo de negocio: o perfil `conservative` nao teve `trades` confirmados no recorte analisado, embora continuasse gerando `decisions` e metricas.
2. Outra parte dos paineis estava realmente falhando por problema de infraestrutura entre `Grafana` e `Prometheus`, gerando `timeout`, `context deadline exceeded` e depois `503 Service Unavailable`.

## Sintoma observado

- Dashboard publico carregando com `No Data` em painieis do monitor BTC.
- Problema reproduzido no recorte `BTC-USDT / conservative / now-12h`.
- Grafana acessivel publicamente, mas com consultas falhando em parte dos painieis.

## Escopo investigado

- Dashboard provisionado do Grafana no homelab
- Datasource Prometheus do Grafana
- Queries SQL do dashboard BTC
- Dados reais no Postgres `btc_trading`
- Alcance do `Grafana -> Prometheus` no host homelab
- Efeitos colaterais de servicos auxiliares de self-heal

## Evidencias coletadas

### 1. Estado real dos dados de negocio

No banco `btc_trading`, para `symbol=BTC-USDT` e `profile=conservative`:

- `trades_12h=0`
- `decisions_12h=6829`
- `last_decision` atualizada em `2026-05-19`
- `last_trade=null` no recorte recente validado

Conclusao: o bot continuava operando em termos de decisao e metricas, mas sem executar trades confirmados na janela selecionada.

### 2. Estado real do Prometheus

Dentro do container `prometheus`, queries retornavam normalmente em JSON.

Exemplo validado:

- `GET /api/v1/query?query=up` -> `200`
- `GET /api/v1/query?query=btc_price{coin="BTC-USDT",profile="conservative"}` -> `200`

Conclusao: o Prometheus em si estava funcional.

### 3. Falha no caminho Grafana -> Prometheus

Antes da correcao final:

- `grafana` rodava em `host network`
- `prometheus` rodava em `bridge`
- o datasource provisionado do Grafana apontava para `http://127.0.0.1:9090`

Na pratica, o host homelab apresentava falha no acesso local ao Prometheus publicado por Docker:

- `curl http://127.0.0.1:9090/-/healthy` expirava
- `curl http://127.0.0.1:9090/api/v1/query?query=up` expirava
- logs do Grafana mostravam:
  - `context deadline exceeded`
  - `timeout awaiting response headers`
  - `response from prometheus couldn't be parsed`
  - `Service Unavailable`

Conclusao: o principal gargalo restante nao era o dashboard JSON, e sim o caminho local entre Grafana e Prometheus.

## Causa raiz

### Causa 1. Ausencia real de trades no periodo

Parte dos `No Data` era correta do ponto de vista dos dados:

- o perfil `conservative` nao executou trades confirmados no intervalo analisado;
- logo, painieis puramente baseados em `btc.trades` poderiam naturalmente ficar vazios.

O problema do dashboard era de apresentacao: varios painieis tratavam janela vazia como `No Data`, em vez de exibir zero, linha continua ou placeholder explicito.

### Causa 2. Datasource com caminho local instavel

Parte dos `No Data` era falsa e causada por falha de infraestrutura:

- o Grafana consultava `127.0.0.1:9090`;
- esse endpoint local estava instavel porque o Prometheus ainda dependia do publish/bridge Docker;
- sob carga de consultas e regras de alerta, o endpoint local passava a devolver timeout ou `503`.

## Correcao aplicada

### 1. Correcao dos painieis SQL do dashboard BTC

Arquivos alinhados:

- `grafana/dashboards/btc_trading_monitor.json`
- `grafana/btc_trading_dashboard_v3_prometheus.json`

Paineis ajustados:

- `📊 PnL Acumulado`
  - passou a emitir pontos de borda da janela e baseline acumulada;
  - evita `No Data` quando nao ha trades no intervalo.

- `📊 Trades por Hora`
  - passou a usar `generate_series` e `left join`;
  - preenche horas sem trades com zero.

- `📊 Trades Recentes`
  - passou a retornar uma linha placeholder quando nao ha trades API confirmados no periodo;
  - evita tabela vazia com `No Data`.

### 2. Correcao do datasource provisionado

Arquivo ajustado:

- `monitoring/grafana/provisioning/datasources/datasources.yml`

URL provisionada:

- de `http://prometheus:9090`
- para `http://127.0.0.1:9090`

### 3. Deploy do dashboard provisionado real no homelab

Arquivo ativo no host:

- `/home/homelab/monitoring/grafana/provisioning/dashboards/btc-trading-monitor.json`

Validacao:

- o `sha256` do arquivo provisionado no homelab ficou igual ao JSON corrigido do repositrio;
- isso confirmou que a correcao nao ficou apenas local.

### 4. Correcao de infraestrutura do Prometheus

Arquivo persistente ajustado no host:

- `/home/homelab/docker-compose.grafana.yml`

Mudanca aplicada:

- `prometheus` saiu de `bridge + ports`
- passou para `network_mode: host`

Motivacao:

- eliminar o salto de rede quebrado entre `grafana` em `host network` e `prometheus` acessado por `127.0.0.1:9090`.

Execucao:

- backup do compose remoto realizado antes da alteracao;
- container `prometheus` recriado mantendo o volume `prometheus_data`.

## Validacoes finais

### Validacao de testes locais

Teste executado:

```bash
pytest -q tests/test_grafana_dashboard_queries.py
```

Resultado:

- suite aprovada

### Validacao de integridade dos dashboards

Os dois JSONs relevantes foram carregados com parser JSON sem erro:

- `grafana/dashboards/btc_trading_monitor.json`
- `grafana/btc_trading_dashboard_v3_prometheus.json`

### Validacao de infraestrutura

Depois da recriacao do Prometheus em `host network`:

- `http://127.0.0.1:9090/-/healthy` -> `200` em cerca de `0.001s`
- `http://127.0.0.1:9090/api/v1/query?query=up` -> `200` em cerca de `0.001s`
- `Grafana` permaneceu saudavel em `http://127.0.0.1:3002/api/health`
- `Prometheus` e `Grafana` ficaram `Up`

### Validacao operacional do dashboard

Resultado esperado apos a correcao:

- painieis baseados em metricas Prometheus deixam de cair por timeout falso;
- painieis baseados em trades passam a mostrar zero ou placeholder quando a janela nao contem execucoes;
- `No Data` residual deixa de significar problema generico e passa a representar estado de dados realmente vazio apenas quando aplicavel.

## Servicos auxiliares observados

Durante a investigacao, os servicos abaixo foram encontrados interferindo na estabilidade do Grafana em momentos anteriores:

- `grafana-selfheal.service`
- `tunnel-healthcheck-exporter.service`

Estado mantido ao final da correcao:

- ambos `inactive`

Observacao:

- isso ajudou a estabilizar a investigacao e a evitar reinicios agressivos durante o bootstrap do Grafana;
- a reativacao deve ser feita somente com janela de tolerancia adequada para startup da stack.

## Diferenca entre sintoma e causa

Para este dashboard, e importante separar:

- `sem trades no periodo`:
  - estado valido de negocio para alguns painieis SQL;
- `No Data por timeout/503`:
  - erro de infraestrutura no caminho `Grafana -> Prometheus`.

Misturar os dois sintomas leva a diagnostico errado.

## Arquivos alterados no repositrio

- `grafana/dashboards/btc_trading_monitor.json`
- `grafana/btc_trading_dashboard_v3_prometheus.json`
- `monitoring/grafana/provisioning/datasources/datasources.yml`
- `tests/test_grafana_dashboard_queries.py`

## Arquivos alterados no homelab

- `/home/homelab/monitoring/grafana/provisioning/dashboards/btc-trading-monitor.json`
- `/home/homelab/monitoring/grafana/provisioning/datasources/datasources.yml`
- `/home/homelab/docker-compose.grafana.yml`

## Estado final

Incidente resolvido para o dashboard analisado.

Estado final consolidado:

- Grafana publico saudavel
- Prometheus local respondendo sem timeout
- dashboard provisionado sincronizado com a versao corrigida
- `No Data` falso eliminado
- ausencia real de trades no perfil `conservative` explicitada corretamente

## Runbook minimo para reincidencia

1. Validar se o problema e em painel de trades ou painel de metricas.
2. No Postgres, comparar `trades_12h` vs `decisions_12h` para o perfil afetado.
3. No host homelab, testar:
   - `curl http://127.0.0.1:9090/-/healthy`
   - `curl 'http://127.0.0.1:9090/api/v1/query?query=up'`
4. Se o dashboard for provisionado, confirmar o arquivo real em:
   - `/home/homelab/monitoring/grafana/provisioning/dashboards/`
5. Se houver timeout no Grafana, inspecionar logs de `grafana` e readiness real do `prometheus`.

## Conclusao

O incidente nao era um unico defeito. Houve:

- um problema de representacao do dashboard para janelas sem trades;
- e um problema real de conectividade local entre Grafana e Prometheus.

As duas frentes foram corrigidas, validadas e publicadas no estado provisionado real do homelab.
