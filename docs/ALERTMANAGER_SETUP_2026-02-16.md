# AlertManager Setup Progress — 16 de Fevereiro de 2026

**Timestamp:** 2026-02-16 13:50 UTC  
**Status:** ⏳ Em Andamento (Etapa 4/5)  
**Bloqueador:** AlertManager binary não instalado (requer compilação ou download manual)

---

## Resumo

Progresso na **integração completa de alertas** (stack Prometheus → AlertManager → Notificações):

| Componente | Status | Ação |
|------------|--------|------|
| 1️⃣ Prometheus Rules | ✅ OK | 4 regras carregadas (`/etc/prometheus/rules/homelab-alerts.yml`) |
| 2️⃣ Prometheus Config | ✅ OK | Alerting section adicionada (localhost:9093) |
| 3️⃣ Prometheus Service | ✅ OK | Reiniciado e ativo |
| 4️⃣ AlertManager Service | ⏳ PENDENTE | Binary não encontrado em `/usr/bin/alertmanager` |
| 5️⃣ Notificações | ⏳ PENDENTE | Webhook configurado mas AlertManager offline |

---

## Ações Completadas

### 1. Prometheus Rules (`/etc/prometheus/rules/homelab-alerts.yml`)

✅ **Arquivo criado e validado** com 4 regras:

```yaml
- DiskUsageHigh: Disco > 80% → warning (5m)
- DiskUsageCritical: Disco > 90% → critical (1m) 
- HighCPUUsage: CPU > 85% → warning (5m)
- HighMemoryUsage: RAM > 85% → warning (5m)
```

**Carregamento:** `curl http://localhost:9090/api/v1/rules` retorna 4 rules.

### 2. Prometheus Configuration

✅ **Arquivo `/etc/prometheus/prometheus.yml` atualizado:**

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    monitor: "homelab"

rule_files:
  - "/etc/prometheus/rules/*.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets: ["localhost:9093"]  # ← AlertManager endpoint

scrape_configs:
  # 7 exporters aqui (node, cadvisor, jira, review, etc)
```

**Status:** Prometheus ativo (`active`), sem erros de parsing YAML.

### 3. AlertManager Configuration

✅ **Arquivo `/etc/alertmanager/alertmanager.yml` criado:**

```yaml
global:
  resolve_timeout: 5m

route:
  receiver: "default"
  group_by: ["alertname", "instance"]
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h

receivers:
  - name: "default"
    webhook_configs:
      - url: "http://127.0.0.1:8503/alerts"
        send_resolved: true

inhibit_rules: []
```

**Nota:** Webhook aponta para Agents API local (Slack/Telegram integration futura).

### 4. AlertManager Service Unit

✅ **Arquivo `/etc/systemd/system/alertmanager.service` criado:**

```ini
[Unit]
Description=Prometheus AlertManager
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/alertmanager --config.file=/etc/alertmanager/alertmanager.yml \
  --storage.path=/var/lib/alertmanager
ExecReload=/bin/kill -HUP $MAINPID
KillMode=process
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Status:** Symlink criado, `sudo systemctl daemon-reload` executado.

---

## Problema Identificado

### ⚠️ AlertManager Binary Ausente

```bash
$ which alertmanager
(nada)

$ /usr/bin/alertmanager --version
(erro: arquivo não encontrado)
```

**Raiz:** `prometheus-alertmanager` package do Ubuntu contém apenas config/service, NÃO o binário.

**Solução Options:**

#### Opção A: Download Binário Go (Recomendado)
```bash
cd /tmp
wget https://github.com/prometheus/alertmanager/releases/download/v0.26.0/alertmanager-0.26.0.linux-amd64.tar.gz
tar xzf alertmanager-0.26.0.linux-amd64.tar.gz
sudo cp alertmanager-0.26.0.linux-amd64/alertmanager /usr/bin/
sudo cp alertmanager-0.26.0.linux-amd64/amtool /usr/bin/
sudo chmod +x /usr/bin/alertmanager /usr/bin/amtool
```

#### Opção B: Build Local (Se Go installed)
```bash
cd /tmp
git clone https://github.com/prometheus/alertmanager.git
cd alertmanager
make build
sudo cp ./alertmanager /usr/bin/
sudo cp ./amtool /usr/bin/
```

#### Opção C: Docker Sidecar (Alternativo)
```bash
docker run -d --name alertmanager \
  -p 9093:9093 \
  -v /etc/alertmanager:/etc/alertmanager \
  -v /var/lib/alertmanager:/alertmanager \
  prom/alertmanager
```

---

## Próximos Passos

### Imediato (5 minutos)

1. **SSH para homelab:**
   ```bash
   ssh homelab@192.168.15.2
   ```

2. **Download + install binário:**
   ```bash
   cd /tmp
   wget https://github.com/prometheus/alertmanager/releases/download/v0.26.0/alertmanager-0.26.0.linux-amd64.tar.gz
   tar xzf alertmanager-0.26.0.linux-amd64.tar.gz
   sudo cp alertmanager-0.26.0.linux-amd64/alertmanager /usr/bin/
   sudo chmod +x /usr/bin/alertmanager
   ```

3. **Start + verify:**
   ```bash
   sudo systemctl start alertmanager
   sudo systemctl is-active alertmanager
   curl http://localhost:9093/-/healthy
   ```

4. **Monitor:**
   ```bash
   sudo journalctl -u alertmanager -f
   ```

### Depois (Configuração)

1. **Test alert trigger:**
   ```bash
   curl -X POST http://localhost:9090/api/v1/admin/reload
   ```

2. **Check firing alerts:**
   ```bash
   curl http://localhost:9090/api/v1/alerts
   ```

3. **Verify webhook delivery:**
   ```bash
   sudo journalctl -u alertmanager | grep webhook
   ```

---

## Git Commit (Pendente)

Após completar setup, commitaremos:

```bash
cd /home/edenilson/eddie-auto-dev

git add docs/ALERTMANAGER_SETUP_2026-02-16.md

git commit -m "docs: Add AlertManager setup progress report

- Prometheus rules (4 alerts) ✅
- Prometheus config (alerting section) ✅
- AlertManager config files ✅
- Bloqueador: AlertManager binary missing (requer wget+install)
- Próxima: Download binário e ativar serviço"

git push origin feat/vpn-keepalive-watchdog
```

---

## Arquivos Criados/Modificados

| Arquivo | Status | Localização |
|---------|--------|-------------|
| `homelab-alerts.yml` | ✅ | `/etc/prometheus/rules/` |
| `prometheus.yml` | ✅ | `/etc/prometheus/` (com alerting) |
| `alertmanager.yml` | ✅ | `/etc/alertmanager/` |
| `alertmanager.service` | ✅ | `/etc/systemd/system/` |
| `ALERTMANAGER_SETUP_2026-02-16.md` | ✅ | `/docs/` (este arquivo) |

---

## Matriz de Responsabilidades

| Tarefa | Owner | Status | ETA |
|--------|-------|--------|-----|
| Download alertmanager binary | DevOps/Usuário | ⏳ | 5 min |
| Install /usr/bin permissions | DevOps | ⏳ | 2 min |
| systemctl start alertmanager | DevOps | ⏳ | 2 min |
| Verify 9093 listening | DevOps | ⏳ | 1 min |
| Test Prometheus → AlertManager | QA | ⏳ | 3 min |
| Document webhook integration | Eng | ⏳ | 10 min |

---

## Recomendações Futuras

1. **Slack Integration:** Adicionar `slack_configs` ao `alertmanager.yml`
2. **Email Alerts:** SMTP configuration para escalação crítica
3. **Dashboard:** Grafana panel mostrando alertas (histórico)
4. **PagerDuty:** Integração para oncall automation
5. **Auto-remediation:** Webhook trigger scripts de recovery

---

## Troubleshooting

### "Connection refused" em port 9093
→ AlertManager não iniciou; verificar `/var/log/alertmanager.log` ou `journalctl -u alertmanager`

### "alertmanager: command not found"
→ Binary não em `/usr/bin/`; fazer download e colocar lá com chmod +x

### "yaml: bad config"
→ Validar sintaxe: `amtool config routes` (requer binary)

### Alerts disparando mas ninguém recebendo
→ Webhook URL inválida; verificar `curl -X POST http://webhook-url` manualmente

---

**Documento gerado:** 2026-02-16 13:50 UTC  
**Próxima atualização esperada:** após instalação do binary
