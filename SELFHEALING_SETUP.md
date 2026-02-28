# Self-Healing Configuration — Painel Eddie Auto Dev Central

## 📊 Gauge Adicionado: "Self-Healing Status"

O painel **eddie-auto-dev-central** agora contém dois gauges no topo que monitoram e acionam auto-recuperação automática:

### **1. 🔧 Self-Healing Status (Stall > 300s)**
- **Localização**: Topo-esquerda (gridPos: 0,0)
- **Métricas monitoradas**:
  - Contagem de restarts nos últimos 5 minutos
  - Detecção de serviços travados (stall > 300s)
- **Status visual**:
  - ✅ **Verde**: Todos os serviços saudáveis
  - ⚠️ **Laranja**: Detectado stall, selfhealing acionado
  - 🔴 **Vermelho**: Múltiplos restarts ou limite excedido

### **2. 📊 Service Stall History (5m)**
- **Localização**: Topo-direita (gridPos: 12,0)
- **Mostra**:
  - Histórico de travamentos por serviço dos últimos 5 minutos
  - Contagem de eventos de stall
  - Status: OK → HEALING → CRITICAL

---

## 🚀 Fluxo do Self-Healing Automático

```
┌─────────────────────────────────────────────────────────────────┐
│ 1️⃣  DETECÇÃO                                                      │
│ Prometheus detecta: (time() - process_start_time_seconds) > 300s│
│ Intervalo: 30s                                                    │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2️⃣  VALIDAÇÃO (2 minutos)                                        │
│ Se stall > 300s por 2 minutos consecutivos → ativa alerta        │
│ Alert: "ServiceStalled" (severity: critical)                     │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3️⃣  AÇÃO (Self-Healing)                                          │
│ systemctl restart <serviço>  (via webhook ou daemon)             │
│ Cooldown: 60s (evita restart em cascata)                         │
│ Log: /var/log/eddie-selfheal.log                                 │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4️⃣  MONITORAMENTO                                                │
│ selfhealing_restarts_total ++ (métrica Prometheus)               │
│ consecutive_failures++ si falhar (métrica local)                 │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5️⃣  POLÍTICAS                                                    │
│ Max restarts/hora: 3 (evita loop infinito)                       │
│ Se > 2 falhas consecutivas → escalate (alerta manual)            │
└─────────────────────────────────────────────────────────────────┘
```

---

## ⚙️ Integração com Prometheus

### Regras de Alerta (`monitoring/prometheus/selfhealing_rules.yml`)

```yaml
# Detecta travamento e dispara ação
alert: ServiceStalled
expr: (time() - process_start_time_seconds) > 300 
      and rate(process_runtime_go_goroutines[1m]) < 0.1
for: 2m
action: selfheal
```

### Métricas Exportadas
- `selfhealing_restarts_total` — total de restarts disparados
- `selfhealing_consecutive_failures` — contador de falhas em série
- `selfhealing:service_health:ratio` — saúde agregada (0-1)
- `selfhealing:stall_duration:seconds` — duração do travamento por serviço

---

## 🔌 Instalação do Webhook (Executor de Selfhealing)

Para executar os restarts automáticos, configure um servidor que escute os alertas do Prometheus:

### Opção 1: Alertmanager Webhook (Recomendado)
```bash
# Editar /etc/alertmanager/alertmanager.yml
route:
  receiver: selfheal_webhook
receivers:
  - name: selfheal_webhook
    webhook_configs:
      - url: http://localhost:5000/selfheal/trigger
        send_resolved: true
        headers:
          Authorization: "Bearer YOUR_SECRET_TOKEN"
```

### Opção 2: Daemon Local
```bash
# Copiar script para systemd
cp tools/selfheal/selfhealing_restart.sh /usr/local/bin/
chmod +x /usr/local/bin/selfhealing_restart.sh

# Criar systemd timer para verificações periódicas
sudo bash -c 'cat > /etc/systemd/system/selfhealing-check.timer << EOF
[Unit]
Description=Self-Healing Service Monitor
After=network-online.target

[Timer]
OnBootSec=30s
OnUnitActiveSec=30s
AccuracySec=1s

[Install]
WantedBy=timers.target
EOF
'

sudo systemctl enable --now selfhealing-check.timer
```

---

## 📋 Serviços Monitorados

Atualmente configurados para selfhealing:
- **jira-worker.service** — RPA/Jira integration
- **crypto-agent@BTC_USDT.service** — Trading agent BTC
- **crypto-agent@ETH_USDT.service** — Trading agent ETH
- **crypto-agent@XRP_USDT.service** — Trading agent XRP
- **crypto-agent@SOL_USDT.service** — Trading agent SOL
- **crypto-agent@DOGE_USDT.service** — Trading agent DOGE
- **crypto-agent@ADA_USDT.service** — Trading agent ADA

---

## 🎯 Cenários de Teste

### Teste 1: Simular Travamento
```bash
# No homelab, pausar um processo
systemctl stop crypto-agent@BTC_USDT.service

# Aguardar 5+ minutos para gauge ficar laranja
# Selfhealing deve reiniciar automaticamente dentro de 2-4 minutos
systemctl status crypto-agent@BTC_USDT.service
```

### Teste 2: Verificar Logs
```bash
# Ver tentativas de selfhealing
tail -f /var/log/eddie-selfheal.log

# Ver alertas Prometheus
curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | {alertname, severity, labels}'
```

### Teste 3: Verificar Métricas
```bash
# Contar restarts no Prometheus
curl -s 'http://localhost:9090/api/v1/query?query=increase(selfhealing_restarts_total%5B1h%5D)' | jq
```

---

## 🚨 Alertas Escalados

| Alerta | Condição | Ação |
|--------|----------|------|
| `ServiceStalled` | stall > 300s por 2m | Restart automático |
| `SelfHealingExhausted` | > 3 restarts/hora | Notificação para admin |
| `ConsecutiveFailures` | > 2 falhas em série | Escalata manual (Diretor) |

---

## 📝 Notas de Implementação

- **Arquivo dashboard**: `grafana/dashboards/eddie-auto-dev-central.json`
- **Arquivo de regras**: `monitoring/prometheus/selfhealing_rules.yml`
- **Script de restart**: `tools/selfheal/selfhealing_restart.sh`
- **Configuração Prometheus**: `monitoring/prometheus.yml` (atualizado com `rule_files`)

O gauge está **pronto para uso** — basta garantir que:
1. Prometheus está scrapeando as métricas `selfhealing_*` 
2. Alertmanager está configurado com o webhook (ou usar o daemon local)
3. systemctl tem permissões para restart (sudoers para o daemon)
