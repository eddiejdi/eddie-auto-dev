# 📊 Integração de Métricas - Grafana

**Status:** ✅ Implementado e Pronto

---

## 📋 O que foi implementado

### 1. ✅ Exportador Prometheus (`metrics_exporter.py`)
- Coleta métricas do sistema de fallback distribuído
- Registra: timeouts, splits, carga de agentes, recursos Docker
- Histórico in-memory para análise de tendências
- Interface de singleton thread-safe

### 2. ✅ API FastAPI (`metrics_api.py`)
- Endpoint `/metrics/prometheus` - formato para scraping Grafana
- Endpoint `/metrics/summary` - resumo em JSON
- Webhooks para eventos: `task_split`, `timeout`, `chunk_executed`, `docker_allocated`
- Health check integrado

### 3. ✅ Dashboard Grafana (`grafana_dashboards/distributed-fallback-dashboard.json`)
- 12 painéis visualizando:
  - 📊 Task Splits (fallback events)
  - ⏱️ Timeout Events (por agente/estágio)
  - ⚡ Latência de Execução (p95/p99)
  - 👥 Carga de Agentes (distribuição)
  - ✅ Taxa de Sucesso/Falha
  - 🐳 Alocação Docker (CPU/Memória)
  - 🔀 Merge & Deduplicação
  - 🚨 Violações de Profundidade

### 4. ✅ Integração em Código
- `agent_manager.py`: Registra splits e deduplicação
- `docker_orchestrator.py`: Registra alocação de recursos
- `base_agent.py`: Registra timeouts via métricas

---

## 🚀 Quick Start

### 1️⃣ Instalar Prometheus (se não tiver)

```bash
# Docker
docker run -d \
  --name prometheus \
  -p 9090:9090 \
  -v prometheus_data:/prometheus \
  -v /path/to/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus
```

**prometheus.yml:**
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'eddie-metrics'
    static_configs:
      - targets: ['localhost:8503']  # Porta da API
    metrics_path: '/metrics/prometheus'
```

### 2️⃣ Integrar com Grafana

```bash
# Setup automático
python3 setup_grafana_metrics.py \
  --grafana-url http://localhost:3000 \
  --prometheus-url http://localhost:9090 \
  --api-key seu_api_key_grafana
```

**Parâmetros opcionais:**
- `--grafana-url`: URL do Grafana (padrão: http://localhost:3000)
- `--prometheus-url`: URL do Prometheus (padrão: http://localhost:9090)
- `--api-key`: API key para autenticação
- `--dashboard`: Path customizado para JSON do dashboard

### 3️⃣ Verificar Integração

```bash
# Métricas em tempo real
curl http://localhost:8503/metrics/prometheus | head -20

# Resumo JSON
curl http://localhost:8503/metrics/summary | jq

# Health check
curl http://localhost:8503/metrics/health
```

---

## 📊 Métricas Disponíveis

### Task Distribution
| Métrica | Descrição | Type |
|---------|-----------|------|
| `task_split_total` | Total de vezes que tarefas foram divididas | Counter |
| `task_split_chunks_total` | Total de chunks criados | Counter |
| `timeout_events_total` | Total de timeouts (por agent/reason) | Counter |
| `fallback_depth_exceeded_total` | Tentativas de exceder max_fallback_depth | Counter |

### Execution Performance
| Métrica | Descrição | Type |
|---------|-----------|------|
| `task_execution_seconds` | Tempo de execução de tarefas (por stage) | Histogram |
| `chunk_execution_seconds` | Tempo individual de chunks (por agent) | Histogram |
| `task_success_total` | Tarefas bem-sucedidas (por stage) | Counter |
| `task_failure_total` | Tarefas falhadas (por reason) | Counter |

### Agent Load
| Métrica | Descrição | Type |
|---------|-----------|------|
| `agent_active_tasks` | Tarefas ativas por agente | Gauge |
| `agent_tasks_executed_total` | Total de tarefas executadas | Counter |

### Docker Resources
| Métrica | Descrição | Type |
|---------|-----------|------|
| `docker_container_cpu_limit` | Limite de CPU em milicores | Gauge |
| `docker_container_memory_limit_bytes` | Limite de memória em bytes | Gauge |
| `docker_elastic_adjustment_total` | Ajustes de recursos (por tipo) | Counter |

### Code Quality
| Métrica | Descrição | Type |
|---------|-----------|------|
| `merge_deduplication_total` | Duplicatas removidas no merge | Counter |
| `merge_chunks_combined_total` | Chunks combinados com sucesso | Counter |

---

## 🎨 Painéis do Dashboard

### Painel 1: Task Splits 📊
- Mostra eventos de fallback ao longo do tempo
- Indica quando e com que frequência o sistema divide tarefas
- Use para: Entender padrões de timeout

### Painel 2: Timeout Events ⏱️
- Timeouts por agente e estágio
- Identifica agentes problemáticos
- Use para: Detectar bottlenecks

### Painel 3: Execution Latency ⚡
- Percentis 95 e 99 de tempo de execução
- Mostra distribuição de latência por stage
- Use para: Otimizar timeouts

### Painel 4: Agent Load 👥
- Carga em tempo real de cada agente
- Visualiza balanceamento
- Use para: Garantir distribuição justa

### Painel 5: Success/Failure Rate ✅
- Taxa de sucesso/falha das tarefas
- Identifica problemas de confiabilidade
- Use para: Monitorar saúde geral

### Painel 6: Docker CPU 🐳
- Alocação de CPU por container
- Valida elasticidade de recursos
- Use para: Confirmar limites dinâmicos

### Painel 7: Docker Memory 💾
- Alocação de memória por container
- Tracks reservas e limites
- Use para: Prevenir OOM

### Painel 8: Merge & Dedup 🔀
- Duplicatas removidas
- Chunks combinados
- Use para: Avaliar qualidade do merge

---

## 🔗 Integração com Sistema Existente

O sistema de métricas integra-se com a infraestrutura existente:

### Fluxo de Dados
```
Agent Task Execution
        ↓
Communication Bus (log_task_start/end)
        ↓
MetricsCollector (record_*)
        ↓
Prometheus Scrape (:8503/metrics/prometheus)
        ↓
Grafana Dashboard (visualização)
```

### Conexão com Streamlit
O dashboard Streamlit existente pode incluir widget que aponta para Grafana:

```python
import streamlit as st

st.markdown(
    f'<iframe src="http://localhost:3000/d/eddie-distributed-fallback" width="100%" height="800"></iframe>',
    unsafe_allow_html=True
)
```

---

## 🚨 Alertas Configurados

Três regras de alerta são criadas automaticamente:

### Alert 1: High Timeout Events ⚠️
- **Condição:** `increase(timeout_events_total[5m]) > 10`
- **Severidade:** warning
- **Ação:** Revisar logs de agentes problemáticos

### Alert 2: Fallback Depth Exceeded 🚨
- **Condição:** `increase(fallback_depth_exceeded_total[5m]) > 0`
- **Severidade:** critical
- **Ação:** Investigar recursão infinita / config max_fallback_depth

### Alert 3: High Failure Rate ⚠️
- **Condição:** `rate(task_failure_total[5m]) > 0.1` (>10%)
- **Severidade:** warning
- **Ação:** Revisar código / requisitos de tarefas

---

## 📐 Exemplos de Queries PromQL

### Sucesso/Falha Últimas 24h
```promql
rate(task_success_total[24h])
rate(task_failure_total[24h])
```

### Carga média de agentes
```promql
avg(agent_active_tasks)
```

### Latência p99 por stage
```promql
histogram_quantile(0.99, rate(task_execution_seconds_bucket[5m]))
```

### Eficiência de merge
```promql
(merge_chunks_combined_total - merge_deduplication_total) / merge_chunks_combined_total
```

### Taxa de splits
```promql
rate(task_split_total[1h])
```

---

## 🔧 Configuração Avançada

### Custom Prometheus Scrape
Se não usar `setup_grafana_metrics.py`, configure manualmente:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'eddie-fallback'
    scrape_interval: 30s
    scrape_timeout: 10s
    static_configs:
      - targets: ['${HOMELAB_HOST}:8503']
    metrics_path: '/metrics/prometheus'
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
```

### Retention Policy
Grafana retém dados conforme configuração do Prometheus:

```yaml
# prometheus.yml
global:
  evaluation_interval: 15s
  external_labels:
    monitor: 'eddie-metrics'

# Dados armazenados por 15 dias
storage:
  retention:
    time: 15d
    size: 50GB
```

---

## 🐛 Troubleshooting

### Sem dados em Grafana

```bash
# 1. Verificar se métricas estão sendo coletadas
curl http://localhost:8503/metrics/prometheus | grep task_split

# 2. Verificar se Prometheus está fazendo scrape
curl http://localhost:9090/api/v1/query?query=task_split_total

# 3. Ver targets do Prometheus
curl http://localhost:9090/api/v1/targets
```

### Dashboard não aparece

```bash
# Listar dashboards
curl -H "Authorization: Bearer $API_KEY" \
  http://localhost:3000/api/search?type=dash-db

# Recriar dashboard
python3 setup_grafana_metrics.py --dashboard /path/to/custom.json
```

### Alertas não funcionam

```bash
# Ver estado dos alertas
curl -H "Authorization: Bearer $API_KEY" \
  http://localhost:3000/api/v1/rules

# Verificar notificação
curl -H "Authorization: Bearer $API_KEY" \
  http://localhost:3000/api/alert-notifications
```

---

## 📈 Métricas de Sucesso

Monitore estes indicadores:

| Indicador | Meta | Como Ler |
|-----------|------|---------|
| Taxa de Sucesso | > 95% | `task_success_total / (task_success_total + task_failure_total)` |
| Latência p99 | < 60s | Painel "Execution Latency" |
| Timeouts/hora | < 5 | Painel "Timeout Events" |
| Eficiência de Merge | > 90% | `(chunks - duplicatas) / chunks` |
| Balanceamento | < 2x diferença | Painel "Agent Active Tasks" |

---

## 🔐 Segurança

### API Key Grafana
```bash
# Gerar nova API key (UI Grafana)
Admin → API Keys → Create new API token

# Usar em script
export GRAFANA_API_KEY="seu_token_aqui"
python3 setup_grafana_metrics.py --api-key $GRAFANA_API_KEY
```

### CORS em Produção
Se Grafana está em host diferente:

```javascript
// Habilitar CORS na API FastAPI
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://${HOMELAB_HOST}:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 📚 Referências

- [Prometheus Docs](https://prometheus.io/docs)
- [Grafana Docs](https://grafana.com/docs)
- [PromQL Guide](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Alerting](https://grafana.com/docs/grafana/latest/alerting/)

---

## 🎯 Próximos Passos

1. **Deploy em Produção**
   - Configurar Prometheus com storage persistente
   - Usar API key com permissões limitadas
   - Habilitar HTTPS no Grafana

2. **Alertas Avançados**
   - Integrar com Slack/PagerDuty
   - Criar runbooks automáticos
   - Implementar escalation policies

3. **Machine Learning**
   - Detecção de anomalias
   - Previsão de timeouts
   - Otimização automática de parâmetros

4. **Dashboards Adicionais**
   - Análise de features (por requisito)
   - Comparação de performance (linguagens)
   - ROI de fallback system

---

**✅ Sistema de Métricas Pronto para Uso!**

Acesse: `http://localhost:3000/d/eddie-distributed-fallback`
