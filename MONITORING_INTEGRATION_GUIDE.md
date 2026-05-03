# RPA4All Snapshot — Monitoramento Grafana + Alertas Telegram

## Arquitetura

```
rpa4all-snapshot.service + health check
        ↓
rpa4all-snapshot-exporter.py (porta 9752)
        ↓
Prometheus (scrape :9752)
        ↓
Alert Rules (rpa4all-snapshot-alerts.yml)
        ↓
AlertManager + Telegram Receiver
        ↓
📱 Notificação Telegram + 📊 Grafana Dashboard
```

## Arquivos Necessários

1. **Exporter**: `/usr/local/bin/rpa4all-snapshot-exporter.py`
2. **Serviço Exporter**: `/etc/systemd/system/rpa4all-snapshot-exporter.service`
3. **Alertas**: `/etc/prometheus/rules/rpa4all-snapshot-alerts.yml`
4. **Config Prometheus**: Adicionar job scrape para :9752
5. **Template Telegram**: `/etc/prometheus/alertmanager_templates/rpa4all-snapshot.tmpl`

## Deployment Step-by-Step

### 1. Deploy Exporter

```bash
# SSH ao homelab
ssh homelab@192.168.15.2

# 1. Copiar exporter
sudo cp /tmp/rpa4all-snapshot-exporter.py /usr/local/bin/
sudo chmod +x /usr/local/bin/rpa4all-snapshot-exporter.py

# 2. Instalar dependência
pip install prometheus_client

# 3. Criar serviço
sudo tee /etc/systemd/system/rpa4all-snapshot-exporter.service > /dev/null << 'SERVICE'
[Unit]
Description=Prometheus Exporter for RPA4All Snapshot Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/rpa4all-snapshot-exporter.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=rpa4all-exporter

MemoryMax=256M
CPUQuota=50%

[Install]
WantedBy=multi-user.target
SERVICE

# 4. Ativar
sudo systemctl daemon-reload
sudo systemctl enable rpa4all-snapshot-exporter.service
sudo systemctl start rpa4all-snapshot-exporter.service

# 5. Verificar
sudo systemctl status rpa4all-snapshot-exporter.service
curl http://localhost:9752/metrics | grep rpa4all
```

### 2. Configurar Prometheus

Adicionar ao `/etc/prometheus/prometheus.yml` (na seção `scrape_configs`):

```yaml
  - job_name: 'rpa4all-snapshot'
    static_configs:
      - targets: ['localhost:9752']
    scrape_interval: 30s
    scrape_timeout: 10s
    metrics_path: '/metrics'
```

Depois:
```bash
sudo systemctl reload prometheus
curl http://localhost:9090/api/v1/query?query=rpa4all_snapshot_up
```

### 3. Adicionar Alert Rules

```bash
sudo cp /tmp/rpa4all-snapshot-alerts.yml /etc/prometheus/rules/

# Verificar sintaxe
sudo promtool check rules /etc/prometheus/rules/rpa4all-snapshot-alerts.yml

# Reload Prometheus
sudo systemctl reload prometheus

# Verificar alertas na UI
curl http://localhost:9090/api/v1/rules
```

### 4. Configurar Alertmanager para Telegram

Editar `/etc/prometheus/alertmanager.yml` (adicionar rota):

```yaml
routes:
  # Rota para RPA4All Snapshot
  - matchers:
      - alertname=~"RPA4AllSnapshot.*"
    receiver: 'telegram-rpa4all'
    group_by: ['alertname', 'severity']
    group_wait: 30s
    group_interval: 5m
    repeat_interval: 1h

receivers:
  - name: 'telegram-rpa4all'
    webhook_configs:
      - url: 'http://localhost:5001/alert'  # Telegram webhook receiver
        send_resolved: true
```

### 5. Template Telegram

```bash
sudo cp /tmp/rpa4all-snapshot-telegram-template.tmpl \
  /etc/prometheus/alertmanager_templates/

# Adicionar ao alertmanager.yml:
templates:
  - '/etc/prometheus/alertmanager_templates/*.tmpl'
```

### 6. Reload e Testar

```bash
sudo systemctl reload alertmanager
sudo systemctl reload prometheus

# Verificar status
sudo systemctl status alertmanager prometheus

# Logs
journalctl -u alertmanager -f
journalctl -u rpa4all-snapshot-exporter -f
```

## Métricas Disponíveis

```
rpa4all_snapshot_service_up                      # 0/1 serviço rodando
rpa4all_snapshot_lock_age_seconds                # Idade do lock file
rpa4all_snapshot_hung                            # 0/1 travado
rpa4all_snapshot_failed_total                    # Counter de falhas
rpa4all_snapshot_success_total                   # Counter de sucessos
rpa4all_snapshot_recovery_triggered_total        # Counter de recuperações
rpa4all_snapshot_backup_size_bytes               # Tamanho último backup
rpa4all_snapshot_last_run_timestamp              # Timestamp última execução
```

## Alertas Configurados

| Alerta | Condição | Ação |
|--------|----------|------|
| `RPA4AllSnapshotServiceDown` | Service not active 5min | ❌ CRÍTICO → Telegram |
| `RPA4AllSnapshotHung` | Lock age > 30min | ❌ CRÍTICO → Auto-restart + Telegram |
| `RPA4AllSnapshotLastRunTooOld` | Sem execução > 24h | ⚠️ WARNING → Telegram |
| `RPA4AllSnapshotFailureRate` | >3 falhas/hora | ⚠️ WARNING → Telegram |
| `RPA4AllBackupSizeUnusual` | Size > 500GB | ⚠️ WARNING → Telegram |
| `RPA4AllSnapshotRecoveryTriggered` | Recovery acionada | ℹ️ INFO → Telegram |

## Grafana Dashboard

Criar novo dashboard em http://grafana.rpa4all.com/d/rpa4all-snapshot com painéis:

1. **Status Card** — `rpa4all_snapshot_service_up` (vermelho/verde)
2. **Lock Age Gauge** — `rpa4all_snapshot_lock_age_seconds` (com alarme em 1800s)
3. **Success/Failure Counter** — `increase(rpa4all_snapshot_success_total[24h])` vs `failed_total`
4. **Backup Size Time Series** — `rpa4all_snapshot_backup_size_bytes`
5. **Last Run Timestamp** — `time() - rpa4all_snapshot_last_run_timestamp`
6. **Recent Alerts** — AlertManager alerts for RPA4All
7. **Recovery Events** — `increase(rpa4all_snapshot_recovery_triggered_total[24h])`

## Teste End-to-End

```bash
# Terminal 1: Monitorar logs exporter
journalctl -u rpa4all-snapshot-exporter -f

# Terminal 2: Forçar failure
systemctl stop rpa4all-snapshot.service

# Terminal 3: Aguardar alerta (5min) e verificar
curl http://localhost:9752/metrics | grep rpa4all_snapshot_hung

# Verificar Alertmanager
curl http://localhost:9093/api/v1/alerts

# Verificar Telegram (deve receber notificação em ~5min)
```

## Troubleshooting

### Exporter não está coletando métricas
```bash
curl http://localhost:9752/metrics | grep rpa4all
# Se vazio, verificar logs: journalctl -u rpa4all-snapshot-exporter -n 50
```

### Alertas não aparecem no Prometheus
```bash
# Validar syntax
promtool check rules /etc/prometheus/rules/rpa4all-snapshot-alerts.yml

# Recarregar
sudo systemctl reload prometheus

# Verificar UI
curl http://localhost:9090/api/v1/rules
```

### Notificações não chegam ao Telegram
```bash
# Verificar AlertManager status
sudo systemctl status alertmanager

# Verificar config
sudo promtool check config /etc/prometheus/alertmanager.yml

# Logs
journalctl -u alertmanager -n 100

# Testar webhook manualmente
curl -X POST http://localhost:9093/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '[{"labels":{"alertname":"TestAlert","severity":"critical"},"annotations":{"summary":"Test"}}]'
```

## Integração com Wiki

Documentar runbooks em:
- https://wiki.rpa4all.com/homelab/infrastructure/rpa4all-snapshot-troubleshooting
- https://wiki.rpa4all.com/homelab/infrastructure/prometheus-alerting

