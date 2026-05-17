# RPA4All Snapshot Monitoring

**Status:** ✅ Deployed (2026-05-03)  
**Architecture:** Watchdog + Prometheus + Grafana  
**Tags:** `rpa4all`, `monitoring`, `observability`, `prometheus`

---

## Overview

Novo sistema de observabilidade para RPA4All que coleta snapshots de eventos em tempo real, expõe via Prometheus, e visualiza em Grafana.

**Antes:** RPA4All rodava "cego" — sem alertas ou dashboards  
**Depois:** Visibilidade completa em produção

---

## Arquitetura

```
┌──────────────┐
│ RPA4All Core │  (disparando eventos)
└──────┬───────┘
       │
┌──────v────────────────┐
│ Snapshot Watchdog      │
│ (monitora fila)        │
└──────┬────────────────┘
       │
┌──────v──────────────┐
│ Snapshot Collector   │
│ (processa eventos)   │
└──────┬───────────────┘
       │
┌──────v──────────────┐
│ Prometheus Exporter  │
│ (:9100+X)            │
└──────┬───────────────┘
       │
┌──────v──────────────┐
│ Prometheus Scraper   │
│ (coleta métricas)    │
└──────┬───────────────┘
       │
┌──────v──────────────┐
│ Grafana Dashboard    │
│ (visualiza + alerta) │
└────────────────────┘
```

---

## Componentes

### 1. Watchdog Service

**Binário:** `/usr/local/bin/rpa4all-snapshot-watchdog`  
**Systemd:** `rpa4all-snapshot-watchdog.service`

#### Responsabilidades
- Monitorar fila de eventos RPA4All
- Detectar eventos anormais
- Trigger snapshots em intervalos regulares
- Health check do collector

#### Configuração
```ini
# /etc/rpa4all/snapshot-watchdog.conf
[watchdog]
rpa4all_socket = /var/run/rpa4all.sock
snapshot_interval = 300        # A cada 5 minutos
max_queue_depth = 1000         # Alert se fila > 1000
health_check_interval = 60     # A cada 1 minuto
```

---

### 2. Snapshot Collector

**Container:** `rpa4all-snapshot-collector`  
**Porta:** `9100` (Prometheus format)

#### Métricas Expostas
```
# HELP rpa4all_events_total Total RPA4All events processed
# TYPE rpa4all_events_total counter
rpa4all_events_total{type="workflow_start"} 1234
rpa4all_events_total{type="workflow_end"} 1230
rpa4all_events_total{type="activity_complete"} 5600
rpa4all_events_total{type="error"} 12

# HELP rpa4all_queue_depth Current event queue depth
# TYPE rpa4all_queue_depth gauge
rpa4all_queue_depth 42

# HELP rpa4all_workflow_duration_seconds Workflow execution time
# TYPE rpa4all_workflow_duration_seconds histogram
rpa4all_workflow_duration_seconds_bucket{le="10"} 100
rpa4all_workflow_duration_seconds_bucket{le="60"} 450
rpa4all_workflow_duration_seconds_bucket{le="300"} 1200

# HELP rpa4all_last_event_timestamp Last event timestamp
# TYPE rpa4all_last_event_timestamp gauge
rpa4all_last_event_timestamp 1714827300
```

#### Implementação
```python
# rpa4all_snapshot_collector.py
from prometheus_client import Counter, Gauge, Histogram, generate_latest

events_total = Counter('rpa4all_events_total', 'Total events', ['type'])
queue_depth = Gauge('rpa4all_queue_depth', 'Queue depth')
workflow_duration = Histogram('rpa4all_workflow_duration_seconds', 'Duration')

@app.route('/metrics', methods=['GET'])
def metrics():
    return generate_latest(), 200, {'Content-Type': 'text/plain; charset=utf-8'}
```

---

### 3. Prometheus Configuration

**File:** `/etc/prometheus/rpa4all_snapshot.yml`

```yaml
global:
  scrape_interval: 30s
  evaluation_interval: 30s

scrape_configs:
  - job_name: 'rpa4all-snapshot'
    static_configs:
      - targets: ['localhost:9100']
    metric_relabel_configs:
      - source_labels: [__name__]
        regex: 'rpa4all_.*'
        action: keep
```

---

### 4. Grafana Dashboard

**Dashboard ID:** `rpa4all-snapshot-monitor`  
**Panels:**
1. Events per second (gauge + trend)
2. Queue depth (time series)
3. Workflow duration (histogram)
4. Error rate (%)
5. Last event timestamp (stat)
6. Top error types (bar chart)

#### Alertas
```yaml
- name: "RPA4All Queue Full"
  condition: "rpa4all_queue_depth > 800"
  for: 5m
  severity: warning
  action: notify_slack, page_oncall

- name: "RPA4All Events Stalled"
  condition: "increase(rpa4all_events_total[5m]) == 0"
  for: 10m
  severity: critical
  action: page_oncall_immediately

- name: "Workflow Duration SLA Breach"
  condition: "rpa4all_workflow_duration_seconds{quantile=\"0.95\"} > 300"
  for: 10m
  severity: warning
```

---

## Deployment

### CI/CD Workflow
**File:** `.github/workflows/deploy-rpa4all-snapshot-monitor.yml`

```yaml
name: Deploy RPA4All Snapshot Monitor

on:
  push:
    paths:
      - 'rpa4all/snapshot-watchdog/**'
      - 'rpa4all/snapshot-collector/**'

jobs:
  deploy:
    runs-on: self-hosted
    steps:
      - uses: actions/checkout@v4
      - name: Build snapshot-collector Docker image
        run: docker build -t rpa4all-snapshot-collector:${{ github.sha }} .
      - name: Deploy to homelab
        run: |
          docker push $REGISTRY/rpa4all-snapshot-collector:${{ github.sha }}
          kubectl set image deployment/rpa4all-snapshot-collector \
            snapshot-collector=$REGISTRY/rpa4all-snapshot-collector:${{ github.sha }}
```

---

## Operações

### Verificar Status
```bash
# Watchdog rodando?
systemctl status rpa4all-snapshot-watchdog

# Collector saudável?
curl -s http://localhost:9100/metrics | grep rpa4all_queue_depth

# Prometheus scraping?
curl -s http://localhost:9090/api/v1/query?query=rpa4all_events_total

# Dashboard atualizado?
curl -s https://grafana.rpa4all.com/api/dashboards/uid/rpa4all-snapshot-monitor
```

### Debug
```bash
# Ver últimos snapshots coletados
kubectl logs -f deployment/rpa4all-snapshot-collector

# Check event queue
rpa4all-cli queue status --snapshot

# Force snapshot
rpa4all-cli snapshot force
```

---

## Troubleshooting

| Problema | Causa | Fix |
|----------|-------|-----|
| Métricas zeradas | Collector crashed | `systemctl restart rpa4all-snapshot-collector` |
| Queue full alert | Workflow lento | Investigar workflow específico |
| Prometheus scrape error | Network issue | Verificar firewall entre Prom e collector |
| Dashboard não atualiza | Grafana cache | Limpar cache: `curl -X DELETE $GRAFANA_URL/api/datasources/cache` |

---

## Próximos Passos

- [ ] Adicionar trace correlation (distribuído tracing)
- [ ] Implementar anomaly detection (ML-based alerting)
- [ ] Expandir para coletar activity logs
- [ ] Integrar com incident management (PagerDuty)
- [ ] Criar runbooks para alertas automáticas

---

**Última atualização:** 2026-05-03  
**Mantido por:** RPA4All, Infrastructure  
**Docs relacionadas:** Prometheus Setup, Grafana Dashboards, Alert Rules
