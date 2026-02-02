# 🚀 Quick Start - Métricas e Monitoramento Distribuído

**Tudo já está implementado e pronto para usar!**

## 📊 O que você tem agora

### 1. Coleta Automática de Métricas
- ✅ Task splits e fallbacks
- ✅ Timeouts por agente
- ✅ Latência de execução (p95/p99)
- ✅ Carga de agentes
- ✅ Alocação Docker (CPU/Memória)
- ✅ Qualidade de merge (deduplicação)

### 2. Dashboard Grafana
- 11 painéis interativos
- Auto-refresh a cada 30s
- Alertas configurados
- Histórico de 6 horas (expansível)

### 3. Três Alertas Críticos
- ⚠️ High Timeout Events (>10/5min)
- 🚨 Fallback Depth Exceeded
- ⚠️ High Failure Rate (>10%)

---

## ⚡ Quick Setup (2 min)

### Passo 1: Instalar Prometheus (escolha uma)

**Opção A: Docker (recomendado)**
```bash
docker run -d \
  --name prometheus \
  -p 9090:9090 \
  -v prometheus_data:/prometheus \
  prom/prometheus:latest \
  --config.file=/etc/prometheus/prometheus.yml
```

**Opção B: Binário local**
```bash
wget https://github.com/prometheus/prometheus/releases/download/v2.40.0/prometheus-2.40.0.linux-amd64.tar.gz
tar xvfz prometheus-*.tar.gz
cd prometheus-*
./prometheus --config.file=prometheus.yml
```

### Passo 2: Setup Automático
```bash
# Com API key (recomendado)
python3 setup_grafana_metrics.py \
  --grafana-url http://localhost:3000 \
  --prometheus-url http://localhost:9090 \
  --api-key seu_api_key_aqui

# Ou sem API key
python3 setup_grafana_metrics.py
```

### Passo 3: Verificar Integração
```bash
# Métricas em tempo real
curl http://localhost:8503/metrics/prometheus | head -10

# Resumo JSON
curl http://localhost:8503/metrics/summary | jq

# Health check
curl http://localhost:8503/metrics/health
```

---

## 🎯 URLs de Acesso

| Serviço | URL |
|---------|-----|
| **Grafana Dashboard** | http://localhost:3000/d/eddie-distributed-fallback |
| **Prometheus Targets** | http://localhost:9090/targets |
| **API Métricas** | http://localhost:8503/metrics/prometheus |
| **Resumo JSON** | http://localhost:8503/metrics/summary |

---

## 📈 Primeiros Passos em Grafana

1. **Acesse:** http://localhost:3000
2. **Login:** admin / admin (padrão)
3. **Vá para:** Dashboards → eddie-distributed-fallback
4. **Explore:** Clique nos painéis para drilldown

### Widgets Principais
- **Task Splits**: Veja quando o fallback foi acionado
- **Timeout Events**: Identifique agentes problemáticos
- **Execution Latency**: Valide se p99 < 60s
- **Agent Load**: Confirme balanceamento
- **Success/Failure**: Monitor confiabilidade

---

## 🔍 Exemplos de PromQL

Copie/cole no Prometheus Explorer (`http://localhost:9090/graph`):

### Taxa de Sucesso Últimas 24h
```promql
rate(task_success_total[24h])
```

### Timeouts por Agente
```promql
increase(timeout_events_total{reason="execution"}[1h])
```

### Latência p99
```promql
histogram_quantile(0.99, rate(task_execution_seconds_bucket[5m]))
```

### Carga Média de Agentes
```promql
avg(agent_active_tasks)
```

### Eficiência de Merge
```promql
(merge_chunks_combined_total - merge_deduplication_total) / merge_chunks_combined_total
```

---

## 🚨 Alertas Ativos

Todos já estão configurados:

| Alerta | Condição | Severidade |
|--------|----------|-----------|
| High Timeouts | >10 em 5min | ⚠️ warning |
| Depth Exceeded | Qualquer ocorrência | 🚨 critical |
| High Failures | >10% em 5min | ⚠️ warning |

**Para configurar notificações:**
1. Acesse Grafana → Alerting → Notification channels
2. Crie canal (Slack, PagerDuty, Email, etc)
3. Associe aos alertas

---

## 🔧 Troubleshooting

### "Sem dados em Grafana?"
```bash
# Verificar se métricas estão sendo coletadas
curl http://localhost:8503/metrics/prometheus | grep task_split

# Verificar status do Prometheus
curl http://localhost:9090/api/v1/targets
```

### "Prometheus não encontra a API?"
```bash
# Verificar conectividade
curl http://localhost:8503/metrics/health

# Ver config do Prometheus
cat /etc/prometheus/prometheus.yml | grep eddie
```

### "Dashboard vazio?"
```bash
# Esperar 1-2 minutos de execução (primeiro scrape)
# Depois F5 para refresh
# Verificar que data picker está correto (últimas 6h)
```

---

## 📊 Métricas Disponíveis

### Task Distribution (Counter)
- `task_split_total` - Total de splits
- `task_split_chunks_total` - Total de chunks criados
- `timeout_events_total` - Total de timeouts (por agent/reason)

### Execution (Histogram + Counter)
- `task_execution_seconds` - Latência por stage
- `task_success_total` / `task_failure_total` - Taxa de sucesso

### Agents (Gauge + Counter)
- `agent_active_tasks` - Tarefas ativas agora
- `agent_tasks_executed_total` - Total executado (por agent)

### Docker (Gauge + Counter)
- `docker_container_cpu_limit` - CPU em milicores
- `docker_container_memory_limit_bytes` - Memória em bytes

### Quality (Counter)
- `merge_deduplication_total` - Duplicatas removidas
- `merge_chunks_combined_total` - Chunks combinados

---

## 🎓 Próximos Passos

### Semana 1
- ✅ Setup básico
- ✅ Validar coleta de dados
- [ ] Ajustar timeouts baseado em latência observada

### Semana 2
- [ ] Criar dashboards customizados por linguagem
- [ ] Setup notificações (Slack/Email)
- [ ] Backup do Prometheus

### Mês 1
- [ ] ML para detecção de anomalias
- [ ] Otimização automática de parâmetros
- [ ] Dashboard de ROI do fallback system

---

## 📚 Documentação Completa

Para detalhes avançados, arquitetura, e troubleshooting:

👉 [GRAFANA_METRICS_INTEGRATION.md](GRAFANA_METRICS_INTEGRATION.md)

---

## ✅ Validação

Checklist para confirmar tudo está funcionando:

- [ ] Prometheus rodando em http://localhost:9090
- [ ] Grafana rodando em http://localhost:3000
- [ ] API respondendo em http://localhost:8503/metrics/health
- [ ] Dashboard visível em Grafana
- [ ] Painéis com dados (esperar 2-3 min após restart)
- [ ] PromQL queries funcionando
- [ ] Alertas visíveis em Grafana → Alerting

---

**🎉 Pronto! Seu sistema de monitoramento está ativo!**

Execute uma requisição no seu servidor e veja as métricas aparecerem em tempo real no Grafana.
