# Self-Healing Configuration — Painel Shared Auto Dev Central

## 📊 Gauges Adicionados

O painel **shared-auto-dev-central** ![
  
](image.png)contém **5 gauges** que monitoram e acionam auto-recuperação:

### **Serviços (Jira + Crypto Agents)**

#### **1. 🔧 Self-Healing Status (Stall > 300s)**
- **Localização**: Topo-esquerda (gridPos: 0,0)
- **Métricas monitoradas**:
  - Contagem de restarts nos últimos 5 minutos
  - Detecção de serviços travados (stall > 300s)
- **Status visual**:
  - ✅ **Verde**: Todos os serviços saudáveis
  - ⚠️ **Laranja**: Detectado stall, selfhealing acionado
  - 🔴 **Vermelho**: Múltiplos restarts ou limite excedido

#### **2. 📊 Service Stall History (5m)**
- **Localização**: Topo-direita (gridPos: 12,0)
- **Mostra**:
  - Histórico de travamentos por serviço dos últimos 5 minutos
  - Contagem de eventos de stall
  - Status: OK → HEALING → CRITICAL

### **Ollama (NEW) - Congelamento Específico**

#### **3. 🧊 Ollama Frozen Detection**
- **Localização**: Segunda linha-esquerda
- **Condições de congelamento**:
  - Sem requisições por > 60s E GPU < 5% por > 180s
  - OU > 50 goroutines presos (deadlock)
- **Status visual**:
  - ✅ **Verde**: Ollama respondendo normalmente
  - 🔴 **Vermelho**: FROZEN - auto-restart acionado

#### **4. ⏱️ Ollama Frozen Duration**
- **Localização**: Segunda linha-centro
- **Mostra**: Tempo (segundos) desde último request bem-sucedido
- **Thresholds**:
  - 🟢 **0-60s**: Fresh (verde)
  - 🟡 **60-180s**: WARNING (laranja)
  - 🔴 **> 180s**: CRITICAL - restart automático (vermelho)

#### **5. 🔄 Ollama Auto-Restarts (1h)**
- **Localização**: Segunda linha-direita
- **Mostra**: Contador de auto-restarts no último 1 hora
- **Thresholds**:
  - 🟢 **0 restarts**: STABLE (verde)
  - 🟡 **1-2 restarts**: UNSTABLE (laranja)
  - 🔴 **≥ 3 restarts**: CRITICAL - limite atingido (vermelho)

---

## 🚀 Fluxo do Self-Healing Automático

### Serviços (Jira + Crypto Agents)
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
│ Log: /var/log/shared-selfheal.log                                 │
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

### Ollama (Novo Fluxo de Congelamento)
```
┌─────────────────────────────────────────────────────────────────┐
│ 1️⃣  DETECÇÃO DE CONGELAMENTO                                   │
│ Condições:                                                        │
│ • Sem requisições  > 60s AND GPU utilização < 5% por > 180s    │
│ • OU goroutines presos > 50 (deadlock detectado)                │
│ • Intervalo check: 15s (mais agressivo que serviços)            │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2️⃣  VALIDAÇÃO (2 minutos confirmados)                           │
│ Se ambas condições verdadeiras por 2 min → ativa alert           │
│ Alert: "OllamaFrozen" (severity: critical)                      │
│ Métrica: ollama_frozen_duration_seconds > 180                    │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3️⃣  AUTO-RESTART OLLAMA                                         │
│ systemctl restart ollama (via SSH ao homelab)                   │
│ Cooldown: 60s (aguardar modelo recarregar)                      │
│ Log: /var/log/ollama-selfheal.log                                │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4️⃣  VERIFICAÇÃO PÓS-RESTART                                     │
│ Testar: curl http://192.168.15.2:11434/api/tags                │
│ Se 200 OK → ollama_up = 1, reset ollama_frozen_duration        │
│ Se falha → iniciar nova tentativa (max 3/hora)                  │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5️⃣  POLÍTICAS OLLAMA                                            │
│ Max restarts/hora: 3 (com cooldown 60s)                         │
│ Se 3 restarts consecutivos falham → escalate para admin         │
│ Alert: "SelfHealingExhausted" (severity: warning)               │
│ Alert: "ConsecutiveFailures" (severity: critical)               │
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

### Teste 1: Simular Travamento de Serviço
```bash
# No homelab, pausar um processo
systemctl stop crypto-agent@BTC_USDT.service

# Aguardar 5+ minutos para gauge ficar laranja
# Selfhealing deve reiniciar automaticamente dentro de 2-4 minutos
systemctl status crypto-agent@BTC_USDT.service
```

### Teste 2: Simular Congelamento do Ollama (NEW)
```bash
# Opção 1: Pausar o processo Ollama
ssh homelab@192.168.15.2 "ps aux | grep '[/]usr/local/bin/ollama serve' | awk '{print \$2}' | xargs kill -STOP"

# Aguardar 3-4 minutos
# Gauge "Ollama Frozen Duration" deve passar de verde → laranja → vermelho
# Script de monitoramento deve dispalar restart

# Opção 2: Simular travamento na GPU
ssh homelab@192.168.15.2 "pkill -STOP ollama"
sleep 200  # Aguardar 180+ segundos

# Ver status do gauge em tempo real
curl -s http://localhost:9090/api/v1/query?query=ollama_up | jq

# Opção 3: Testar o script de detecção diretamente
bash tools/selfheal/ollama_frozen_monitor.sh --test
```

### Teste 3: Verificar Logs
```bash
# Ver tentativas de selfhealing (serviços)
tail -f /var/log/shared-selfheal.log

# Ver tentativas de ollama frozen detection
tail -f /var/log/ollama-selfheal.log

# Ver alertas Prometheus
curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.labels.service=="ollama") | {alertname, severity, labels}'
```

### Teste 4: Verificar Métricas do Ollama
```bash
# Listar todas as métricas do Ollama
curl -s http://localhost:9090/api/v1/query?query=ollama_up | jq

# Ver duração do congelamento
curl -s 'http://localhost:9090/api/v1/query?query=ollama_frozen_duration_seconds' | jq

# Ver contador de restarts
curl -s 'http://localhost:9090/api/v1/query?query=increase(ollama_selfheal_restarts_total%5B1h%5D)' | jq

# Ver GPU utilization
curl -s 'http://localhost:9090/api/v1/query?query=ollama_gpu_utilization_percent' | jq
```

### Teste 5: Monitorar em Tempo Real
```bash
# Abrir dashboard ao vivo
open "https://grafana.rpa4all.com/d/shared-central/shared-auto-dev-e28094-central?orgId=1&refresh=5s"

# OU monitorar pelo terminal
watch -n 5 'curl -s http://localhost:9090/api/v1/query?query=ollama_frozen_duration_seconds | jq ".data.result[0].value"'
```

---

## 🧊 Setup do Ollama Monitoring

### 1. Instalação do Metrics Exporter
```bash
# Copiar script para /usr/local/bin
cp tools/selfheal/ollama_metrics_exporter.sh /usr/local/bin/
chmod +x /usr/local/bin/ollama_metrics_exporter.sh

# Criar systemd service
sudo bash -c 'cat > /etc/systemd/system/ollama-metrics-exporter.service << EOF
[Unit]
Description=Ollama Prometheus Metrics Exporter
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/ollama_metrics_exporter.sh --daemon 15
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

Environment="OLLAMA_HOST=http://192.168.15.2:11434"

[Install]
WantedBy=multi-user.target
EOF
'

# Habilitar e iniciar
sudo systemctl daemon-reload
sudo systemctl enable ollama-metrics-exporter.service
sudo systemctl start ollama-metrics-exporter.service
```

### 2. Instalação do Frozen Monitor (Daemon)
```bash
# Copiar script para /usr/local/bin
cp tools/selfheal/ollama_frozen_monitor.sh /usr/local/bin/
chmod +x /usr/local/bin/ollama_frozen_monitor.sh

# Criar systemd service
sudo bash -c 'cat > /etc/systemd/system/ollama-frozen-monitor.service << EOF
[Unit]
Description=Ollama Frozen Detection & Auto-Recovery
After=network-online.target ollama.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/ollama_frozen_monitor.sh 180 15 3 60
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

Environment="OLLAMA_HOST=http://192.168.15.2:11434"
Environment="OLLAMA_SERVICE=ollama"

# Permissão para reiniciar Ollama via SSH
AmbientCapabilities=CAP_SYS_ADMIN

[Install]
WantedBy=multi-user.target
EOF
'

# Habilitar e iniciar
sudo systemctl daemon-reload
sudo systemctl enable ollama-frozen-monitor.service
sudo systemctl start ollama-frozen-monitor.service

# Verificar status
sudo systemctl status ollama-frozen-monitor.service
```

### 3. Configurar Prometheus para Coletar Métricas do Ollama

Adicionar ao `monitoring/prometheus.yml`:
```yaml
scrape_configs:
  - job_name: 'ollama'
    scrape_interval: 15s
    static_configs:
      - targets: ['192.168.15.2:11434']  # API do Ollama
  
  # Textfile collector (para métricas exportadas pelo daemon)
  - job_name: 'node-exporter'
    scrape_interval: 15s
    static_configs:
      - targets: ['192.168.15.2:9100']  # Node exporter customizado
```

### 4. Carregar Regras de Alertas do Ollama
```bash
# Prometheus já carrega de monitoring/prometheus/selfhealing_rules.yml
# Verificar se a regra de group "ollama_selfhealing" está ativa:

curl -s http://localhost:9090/api/v1/rules | jq '.data.groups[] | select(.name=="ollama_selfhealing") | .rules[]'
```

---

## 🚨 Alertas do Ollama (Grupo: ollama_selfhealing)

| Alerta | Condição | Ação | Severidade |
|--------|----------|------|-----------|
| **OllamaFrozen** | Sem requisições > 60s AND GPU < 5% por > 180s | Restart automático | **CRITICAL** |
| **OllamaSlowResponse** | p95 latência > 30s por 3 min | Notificação | WARNING |
| **OllamaMemoryPressure** | Memória > 95% | Notificação | WARNING |
| **OllamaGPUOverheat** | Temp GPU > 85°C | Throttle | WARNING |
| **SelfHealingExhausted** | > 3 restarts/hora | Notificação admin | WARNING |
| **ConsecutiveFailures** | > 2 falhas em série | Escalação | **CRITICAL** |

---

## 📊 Métricas Disponíveis (Ollama)

```
ollama_up                           — Status (1=up, 0=down)
ollama_frozen_duration_seconds      — Tempo sem requisições
ollama_last_request_timestamp       — Unix timestamp última requisição
ollama_models_loaded                — Contagem de modelos carregados
ollama_models_total_size_bytes      — Tamanho total dos modelos
ollama_models_active                — Modelos ativamente processando
ollama_vram_used_bytes              — VRAM em uso
ollama_gpu_utilization_percent      — Utilização GPU (0-100)
ollama_gpu_memory_used_bytes        — Memória GPU usada
ollama_gpu_memory_total_bytes       — Memória GPU total
ollama_gpu_temperature_celsius      — Temperatura GPU
ollama_selfheal_restarts_total      — Contador de restarts automáticos
```

---

## 📝 Notas de Implementação

**Arquivos principais**:
- [grafana/dashboards/shared-auto-dev-central.json](grafana/dashboards/shared-auto-dev-central.json) — Dashboard com 5 gauges
- [monitoring/prometheus/selfhealing_rules.yml](monitoring/prometheus/selfhealing_rules.yml) — Regras (serviços + Ollama)
- [tools/selfheal/ollama_frozen_monitor.sh](tools/selfheal/ollama_frozen_monitor.sh) — Daemon de detecção/recuperação
- [tools/selfheal/ollama_metrics_exporter.sh](tools/selfheal/ollama_metrics_exporter.sh) — Exportador de métricas
- [tools/selfheal/selfhealing_restart.sh](tools/selfheal/selfhealing_restart.sh) — Executor de restart (serviços)

**Checklist pós-instalação**:
- [ ] Prometheus recarregou `selfhealing_rules.yml`
- [ ] Ollama metrics exporter está rodando e exportando
- [ ] Ollama frozen monitor está rodando
- [ ] Dashboard mostra 5 gauges sem erros
- [ ] Teste 1: simular stall de serviço → auto-restart
- [ ] Teste 2: simular congelamento Ollama → auto-restart
- [ ] Logs sendo escritos em `/var/log/ollama-selfheal.log`
- [ ] Alertas disparando corretamente em Prometheus

O sistema está **pronto para monitorar e recuperar automaticamente** travamentos de Ollama!

