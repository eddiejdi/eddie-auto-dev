# 🔍 RPA4All Snapshot — Stack Completo de Monitoramento

## 📦 O Que Foi Criado

### 1️⃣ Watchdog System (Auto-Healing)
- ✅ Service com timeout 30min
- ✅ Health check a cada 5min
- ✅ Auto-recovery em caso de travamento
- ✅ Logs estruturados

**Arquivos**:
- `rpa4all-snapshot.service` — Service principal
- `rpa4all-snapshot-recovery.service` — Retry automático
- `rpa4all-snapshot-health.service` — Health check
- `rpa4all-snapshot-health.timer` — Timer periódico
- `rpa4all-snapshot-health.sh` — Script de detecção

### 2️⃣ Prometheus Exporter (Métricas)
- ✅ 8 métricas em tempo real
- ✅ Porta 9752
- ✅ Systemd service
- ✅ Restart automático

**Arquivo**:
- `rpa4all-snapshot-exporter.py`
- `rpa4all-snapshot-exporter.service`

### 3️⃣ Alert Rules (Prometheus)
- ✅ 6 alertas pré-configurados
- ✅ Severidade crítica/warning/info
- ✅ Integração com AlertManager
- ✅ Templates Telegram

**Arquivo**:
- `rpa4all-snapshot-alerts.yml`
- `rpa4all-snapshot-telegram-template.tmpl`

### 4️⃣ Guias de Deploy
- ✅ Passo-a-passo completo
- ✅ Troubleshooting
- ✅ Testes E2E
- ✅ Integração com Grafana

## 📊 Dashboard Recomendado

Criar em http://grafana.rpa4all.com/d/rpa4all-snapshot com:

```
┌─────────────────────────────────────────────┐
│  🟢 RPA4All Snapshot — Status               │
├─────────────────────────────────────────────┤
│                                             │
│ Status: 🟢 UP      Last Run: 2h ago        │
│                                             │
│ ┌─────────────────────────────────────────┐ │
│ │ Lock Age: 0s [━━━━━━━━━━━━━━━━━━━━━━]  │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ Success: 156  Failures: 2  Recoveries: 1   │
│                                             │
│ Backup Size: 387GB (↗ 5% último mês)       │
│                                             │
│ Alerts: 0 active                            │
│                                             │
└─────────────────────────────────────────────┘
```

## 📱 Alertas no Telegram

```
🔴 ALERTA RPA4All Snapshot
───────────────────────────
Alerta: RPA4AllSnapshotHung
Severidade: CRITICAL

⏸️ RPA4All Snapshot HUNG (Travado)

Descrição: Lock file com idade 35min...
Ação: Health check vai reiniciar automaticamente em ~5 minutos

Tempo: 2026-05-03 17:32:15

[Abrir Grafana](link)
```

## 🚀 Quick Start

### Requisitos
- SSH acesso ao homelab (homelab@192.168.15.2)
- Prometheus já rodando
- AlertManager já rodando
- Telegram bot já configurado

### Deploy em 3 Passos

**1. Copiar Watchdog**
```bash
ssh homelab@192.168.15.2 "bash -s" < <(cat /tmp/DEPLOYMENT_GUIDE.md | grep -A 100 "# SSH ao homelab")
```

**2. Deploy Exporter + Alertas**
```bash
ssh homelab@192.168.15.2 "bash -s" < <(cat /tmp/MONITORING_INTEGRATION_GUIDE.md | grep -A 200 "# SSH ao homelab")
```

**3. Criar Dashboard Grafana**
- Abrir http://grafana.rpa4all.com/d/new
- Add panels com as queries em MONITORING_INTEGRATION_GUIDE.md

## 📈 Métricas Disponíveis

```prometheus
# ┌─ Status do Serviço
rpa4all_snapshot_service_up                   # 0=down, 1=up
rpa4all_snapshot_hung                         # 0=ok, 1=hung

# ┌─ Timings
rpa4all_snapshot_lock_age_seconds             # Idade do lock (segundos)
rpa4all_snapshot_last_run_timestamp           # Unix timestamp último sucesso
rpa4all_snapshot_last_run_duration_seconds    # Duração última execução

# ┌─ Contadores
rpa4all_snapshot_failed_total                 # Total de falhas (counter)
rpa4all_snapshot_success_total                # Total de sucessos (counter)
rpa4all_snapshot_recovery_triggered_total     # Auto-recoveries (counter)

# ┌─ Tamanho
rpa4all_snapshot_backup_size_bytes            # Bytes do último backup
```

## 🎯 Alertas

| # | Nome | Condição | Severidade | Ação |
|---|------|----------|-----------|------|
| 1 | ServiceDown | Service not active 5min | 🔴 CRITICAL | Telegram |
| 2 | Hung | Lock age > 1800s | 🔴 CRITICAL | Auto-restart + Telegram |
| 3 | LastRunTooOld | Sem execução > 24h | 🟡 WARNING | Telegram |
| 4 | FailureRate | >3 falhas/hora | 🟡 WARNING | Telegram |
| 5 | SizeUnusual | Backup > 500GB | 🟡 WARNING | Telegram |
| 6 | RecoveryTriggered | Auto-recovery acionada | ℹ️ INFO | Telegram |

## 📚 Documentação

- **Deployment**: `DEPLOYMENT_GUIDE.md` (watchdog + health check)
- **Monitoring**: `MONITORING_INTEGRATION_GUIDE.md` (Prometheus + Grafana)
- **Comparison**: `COMPARISON.md` (por que watchdog é melhor)
- **Troubleshooting**: Ver seção "Troubleshooting" em MONITORING_INTEGRATION_GUIDE.md

## ✅ Checklist de Deploy

- [ ] Watchdog systemd services criados
- [ ] Health check script rodando
- [ ] Exporter rodando na porta 9752
- [ ] Prometheus scrapeando :9752
- [ ] Alert rules carregadas
- [ ] AlertManager com rota para Telegram
- [ ] Template Telegram configurado
- [ ] Dashboard Grafana criado
- [ ] Teste E2E: Forçar failure e confirmar alerta Telegram

## 🔧 Troubleshooting Rápido

```bash
# Checar exporter
curl http://homelab:9752/metrics | grep rpa4all

# Checar alertas no Prometheus
curl http://homelab:9090/api/v1/rules | jq '.data.groups[] | select(.name=="rpa4all_snapshot_alerts")'

# Checar AlertManager
curl http://homelab:9093/api/v1/alerts | jq '.[] | select(.labels.alertname | contains("RPA4All"))'

# Logs
ssh homelab@192.168.15.2 "journalctl -u rpa4all-snapshot-exporter -f"
ssh homelab@192.168.15.2 "journalctl -u rpa4all-snapshot-health -f"
```

## 📞 Suporte

Documentação completa em `/memories/session/rpa4all-agent-logs-investigation-2026-05-03.md`

Guias em `/tmp/`:
- `DEPLOYMENT_GUIDE.md`
- `MONITORING_INTEGRATION_GUIDE.md`
- `COMPARISON.md`
