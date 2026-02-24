**Painel Grafana — BTC Trading Agent Monitor**

Este diretório contém um JSON de dashboard pronto para importação no Grafana: `btc_trading_dashboard.json`.

Pré-requisitos:
- Grafana com acesso ao banco Postgres usado pelo agente (datasource nomeado `Postgres`).
- O datasource Postgres deve apontar para: host `localhost:5433`, db `btc_trading` e credenciais adequadas.

Importar via UI:
1. Abra Grafana → + (Create) → Import.
2. Cole o conteúdo de `btc_trading_dashboard.json` ou escolha o arquivo para upload.
3. Ao importar, selecione o `Postgres` como datasource.

Importar via API (exemplo):
```bash
# Ajuste GRAFANA_URL e API_KEY
GRAFANA_URL="http://localhost:3000"
API_KEY="<YOUR_GRAFANA_API_KEY>"
curl -s -X POST ${GRAFANA_URL}/api/dashboards/db \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d @btc_trading_dashboard.json
```

Notas:
- As queries do dashboard usam macros do Grafana (`$__timeFilter`) e esperam que as colunas timestamp existam (`created_at`, `date`). Se os nomes de colunas forem diferentes, ajuste as queries no JSON.
- O painel inclui:
  - `BTC Price (close)` — série histórica do preço importado.
  - `Recent Trades` — tabela com trades (side, price, size, dry_run).
  - `Cumulative PnL` — cálculo estimado considerando taxa de 0.1% (ajuste conforme sua corretora).
  - `Agent Position (BTC)` — posição acumulada calculada a partir dos trades.
  - `Signals per Minute` — contagem de decisões por minuto.
  - `RAG Update History` — tabela com registros armazenados em `btc.update_history`.

Se quiser, eu posso:
- Ajustar as queries para o schema exato do seu DB.
- Criar um script que importe automaticamente o dashboard via API usando a URL e a API key do Grafana no homelab.
# Agent Neural Network Dashboard

Dashboard Grafana com visualização de rede neural mostrando a comunicação entre agents em tempo real.

## 🎯 Features

- **Mapa Neural Interativo**: Visualização de grafo mostrando todos os agents e suas conexões
- **Métricas em Tempo Real**: Taxa de mensagens, latência, força das conexões
- **Análise de Comunicação**: Identificação de padrões e gargalos
- **Multi-datasource**: Combina Prometheus (métricas) e PostgreSQL (topologia)

## 📊 Painéis Incluídos

1. **Agent Neural Network Map** - Grafo interativo com nodes e edges
2. **Message Flow Rate** - Taxa de mensagens por segundo entre agents
3. **Connection Strength Matrix** - Matriz de força das conexões (0-1)
4. **Active Agents** - Pizza chart com agents ativos
5. **Message Types Distribution** - Distribuição de tipos de mensagem
6. **Active Conversations** - Gauge de conversas ativas

## 🚀 Deploy

```bash
chmod +x deploy_neural_network_grafana.sh
./deploy_neural_network_grafana.sh
## 🔧 Componentes

### Agent Network Exporter

Exporta métricas Prometheus sobre comunicação entre agents:

- **Porta**: 9101
- **Métricas**:
  - `agent_messages_total` - Total de mensagens entre agents
  - `agent_active_count` - Agents ativos
  - `agent_response_latency_seconds` - Latência de resposta
  - `agent_connection_strength` - Força da conexão (0-1)
  - `agent_message_type_total` - Mensagens por tipo
  - `agent_errors_total` - Erros por agent
  - `agent_active_conversations` - Conversas ativas

### Database Schema

Utiliza as tabelas do interceptor:

```sql
messages (
  id, timestamp, source, target, type, content, metadata
)

conversations (
  id, started_at, ended_at, phase, participants, status
)
## 📈 Visualizações

### Node Graph

O painel principal usa o plugin `nodeGraph` do Grafana com:

- **Nodes**: Representam agents (coloridos por grupo)
  - `language` - Agents de linguagem (Python, JS, Go, etc.)
  - `coordinator` - Coordenador
  - `director` - Diretor
  - `interface` - Interfaces (Telegram, etc.)
  - `llm` - LLM clients

- **Edges**: Representam comunicação (espessura = volume)
  - Coloridos por tipo de mensagem
  - Tooltip mostra última interação

### Layout Algorithm

Usa algoritmo `force-directed` para posicionamento automático:
- Attraction: 1 (atração entre nodes conectados)
- Repulsion: 10 (repulsão entre nodes não conectados)

## 🔍 Queries

### Nodes Query

```sql
SELECT DISTINCT
  source as id,
  source as label,
  CASE WHEN source LIKE '%python%' THEN 'language'
       WHEN source LIKE '%coordinator%' THEN 'coordinator'
       ... END as "group",
  COUNT(*) as message_count
FROM messages
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY source
### Edges Query

```sql
SELECT 
  source as "from",
  target as "to",
  COUNT(*) as weight,
  MAX(timestamp) as last_interaction
FROM messages
WHERE timestamp > NOW() - INTERVAL '24 hours'
  AND target != 'all'
GROUP BY source, target
## 🛠️ Troubleshooting

### Métricas não aparecem

```bash
# Verificar se exporter está rodando
ssh homelab@${HOMELAB_HOST} 'sudo systemctl status agent-network-exporter'

# Testar endpoint
curl http://${HOMELAB_HOST}:9101/metrics
### Dashboard vazio

```bash
# Verificar se há dados no PostgreSQL
ssh homelab@${HOMELAB_HOST} 'docker exec eddie-postgres psql -U postgres -c "SELECT COUNT(*) FROM messages;"'
### Nodes não aparecem

- Verifique se o datasource PostgreSQL está configurado corretamente
- Confirme que há mensagens nas últimas 24h
- Verifique logs: `journalctl -u agent-network-exporter -f`

## 📚 Referências

- [Grafana Node Graph](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/node-graph/)
- [Prometheus Python Client](https://github.com/prometheus/client_python)
- [PostgreSQL Grafana Datasource](https://grafana.com/docs/grafana/latest/datasources/postgres/)

## 🔐 Credenciais

Armazenadas no Bitwarden:
- Item: "Eddie PostgreSQL - Agent Memory (Homelab)"
- Grafana: admin/admin (padrão)
