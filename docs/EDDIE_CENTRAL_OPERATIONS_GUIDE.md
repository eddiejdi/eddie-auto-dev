# Shared Central — Guia de Operações [24/02/2026]

**Última atualização:** 24 de fevereiro de 2026  
**Status:** ✅ Production Ready  
**Dashboard:** http://192.168.15.2:3002/d/shared-central

---

## ⚡ Quick Reference

### Status do Dashboard
```bash
# Validação completa (local)
cd /home/edenilson/shared-auto-dev
GRAFANA_URL="http://192.168.15.2:3002" \
GRAFANA_USER="admin" \
GRAFANA_PASS="GrafanaEddie2026" \
python3 validate_all_panels.py
```

**Esperado:** ✅ 100% — Painéis com dados: 22/22

---

### Verificar Exporters
```bash
# FASE 1 (porta 9105)
curl -s http://192.168.15.2:9105/metrics | grep -E "agent_count|message_rate"

# FASE 3 (porta 9106)
curl -s http://192.168.15.2:9106/metrics | grep -E "conversations_total|copilot"
```

---

### Reiniciar Serviços
```bash
# Exporter FASE 1
ssh homelab@192.168.15.2 "sudo systemctl restart shared-central-metrics"

# Exporter FASE 3
ssh homelab@192.168.15.2 "sudo systemctl restart shared_central_extended_metrics"

# Grafana
ssh homelab@192.168.15.2 "sudo systemctl restart grafana-server"
# OU via Docker
ssh homelab@192.168.15.2 "docker restart grafana"
```

---

### Verificar Logs
```bash
# Exporter FASE 1
ssh homelab@192.168.15.2 "journalctl -u shared-central-metrics -f"

# Exporter FASE 3
ssh homelab@192.168.15.2 "sudo journalctl -u shared_central_extended_metrics -f"

# Grafana
ssh homelab@192.168.15.2 "docker logs -f grafana"
```

---

## 📊 Painéis Ativos

### Infraestrutura (12 painéis)
| ID | Nome | Métrica | Status |
|----|------|---------|--------|
| 1 | CPU Usage | `node_cpu_seconds_total` | ✅ |
| 2 | Memória | `node_memory_MemAvailable` | ✅ |
| 3 | Disco / | `node_filesystem_free` | ✅ |
| 4 | Uptime | Uptime em segundos | ✅ |
| 5 | Targets UP | Prometheus targets | ✅ |
| 6 | RAM Total | `node_memory_MemTotal` | ✅ |
| 7-12 | Gráficos históricos | Timeseries | ✅ |

### Shared Agents (4 painéis)
| ID | Nome | Métrica | Status |
|----|------|---------|--------|
| 402 | Agentes Ativos | `agent_count_total` (9105) | ✅ |
| 403 | Taxa Mensagens | `message_rate_total` (9105) | ✅ |
| 404 | Containers Ativos | `cadvisor_containers_running` | ✅ |
| 407 | WhatsApp Accuracy | Gauge customizado | ✅ |

### Communication Bus (9 painéis)
| ID | Nome | Métrica | Status |
|----|------|---------|--------|
| 13 | Total Mensagens | `messages_total` (9106) | ✅ |
| 14 | Conversas | `conversations_total` (9106) | ✅ |
| 15 | Decisões Memória | `agent_decisions_total` (9106) | ✅ |
| 16 | IPC Pendentes | `ipc_pending_requests` (9106) | ✅ |
| 26 | Confiança Média | `agent_decision_confidence` (9106) | ✅ |
| 27 | Feedback Médio | `agent_decision_feedback` (9106) | ✅ |
| 17-21+ | ~~Gráficos históricos~~ | ~~Removidos~~ | 🗑️ |

### Qualidade (2 painéis)
| ID | Nome | Métrica | Status |
|----|------|---------|--------|
| 26 | Confiança Média | Avg decisões | ✅ |
| 27 | Feedback Médio | Avg feedback | ✅ |

---

## 🔧 Troubleshooting Comum

### Painel Sem Dados
**Sintoma:** Valor zerado ou "No data"

**Passos de investigação:**
1. Verificar se exporter está rodando
   ```bash
   curl -s http://192.168.15.2:9105/metrics | head -20
   curl -s http://192.168.15.2:9106/metrics | head -20
   ```

2. Testar métrica no Prometheus
   ```bash
   curl -s "http://192.168.15.2:9090/api/v1/query?query=agent_count_total"
   ```

3. Verificar query no Grafana
   - Abrir painel → Edit → Queries
   - Verificar sintaxe PromQL

4. Checar PostgreSQL se for exporter estendido
   ```bash
   ssh homelab@192.168.15.2 "psql postgresql://postgress:shared_memory_2026@localhost:5432/postgres -c 'SELECT COUNT(*) FROM agent_communication_messages;'"
   ```

---

### Exporter Offline
**Sintoma:** Porta 9105 ou 9106 não responde

**Solução:**
```bash
# Verificar status
ssh homelab@192.168.15.2 "sudo systemctl status shared-central-metrics"
ssh homelab@192.168.15.2 "sudo systemctl status shared_central_extended_metrics"

# Reiniciar
ssh homelab@192.168.15.2 "sudo systemctl restart shared-central-metrics"
ssh homelab@192.168.15.2 "sudo systemctl restart shared_central_extended_metrics"

# Ver logs
ssh homelab@192.168.15.2 "sudo journalctl -u shared_central_extended_metrics -n 50"
```

---

### Dashboard Não Atualiza
**Sintoma:** Valores congelados nos painéis

**Solução:**
1. Verificar refresh rate do dashboard (default: 30s)
2. Limpar cache do navegador (Ctrl+Shift+R)
3. Reiniciar Grafana
   ```bash
   ssh homelab@192.168.15.2 "docker restart grafana"
   ```
4. Verificar Prometheus scraping
   ```bash
   curl -s http://192.168.15.2:9090/targets | grep shared
   ```

---

## 📈 Métricas de Saúde

### Dashboard
```
Taxa sucesso:     100% ✅
Painéis válidos:  22/22 ✅
Painéis offline:  0 ✅
Querys errors:    0 ✅
Response time:    <100ms ✅
```

### Exporters
```
FASE 1 (9105):    ✅ Active, 30s scrape interval
FASE 3 (9106):    ✅ Active, 30s scrape interval
Database conn:    ✅ PostgreSQL conectado
Fallback data:    ✅ Mock values disponíveis
```

### Prometheus
```
Targets UP:       10+
Scrape duration:  <2s
TSDB size:        ~2GB
Query performance: <100ms
```

---

## 🗄️ Arquivos Críticos

### Configuração
```
/etc/systemd/system/shared-central-metrics.service
/etc/systemd/system/shared_central_extended_metrics.service
/etc/prometheus/prometheus.yml
/var/lib/grafana/provisioning/dashboards/shared-central.json
```

### Código
```
/home/edenilson/shared-auto-dev/shared_central_missing_metrics.py
/home/edenilson/shared-auto-dev/shared_central_extended_metrics.py
/home/edenilson/shared-auto-dev/validate_all_panels.py
```

### Backup
```
/tmp/shared-central-clean.json  (Dashboard current)
/home/homelab/backups/         (Backups diários)
```

---

## 🔐 Credenciais

| Serviço | URL | User | Password | Armazenado |
|---------|-----|------|----------|-----------|
| Grafana Local | 192.168.15.2:3002 | admin | GrafanaEddie2026 | Secrets Agent |
| Prometheus | 192.168.15.2:9090 | - | (sem auth) | - |
| PostgreSQL | localhost:5432 | postgres | shared_memory_2026 | Env var |

---

## 📅 Manutenção Planejada

### Semanal
- [x] Validar dashboard (script: `validate_all_panels.py`)
- [ ] Verificar espaço em disco
- [ ] Revisar logs Grafana/Prometheus

### Mensal
- [ ] Atualizar documentação
- [ ] Arquivar backups antigos
- [ ] Analisar performance

### Trimestral
- [ ] Upgrade Grafana
- [ ] Upgrade Prometheus
- [ ] Rebuild venvs

---

## 🚀 Deployment

### Fazer Push de Mudanças
```bash
cd /home/edenilson/shared-auto-dev
git add -A
git commit -m "chore: [descrição]"
git push origin main
```

### Deploy no Homelab
```bash
# Copiar exporter
scp shared_central_extended_metrics.py homelab@192.168.15.2:/home/homelab/shared-auto-dev/

# Copiar systemd service
scp shared_central_extended_metrics.service homelab@192.168.15.2:/tmp/
ssh homelab@192.168.15.2 "sudo cp /tmp/shared_central_extended_metrics.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl restart shared_central_extended_metrics"

# Deploy dashboard
scp shared-central-clean.json homelab@192.168.15.2:/tmp/
ssh homelab@192.168.15.2 "docker cp /tmp/shared-central-clean.json grafana:/etc/grafana/provisioning/dashboards/shared-central.json && docker restart grafana"
```

---

## 📞 Suporte

**Repositório:** eddiejdi/shared-auto-dev  
**Dashboard Cloud:** grafana.rpa4all.com/d/shared-central  
**Dashboard Local:** http://192.168.15.2:3002/d/shared-central  
**Documentação:** /home/edenilson/shared-auto-dev/docs/

**Para problemas:**
1. Verificar logs via `journalctl`
2. Consultar documentação em `docs/`
3. Rodar validação com `validate_all_panels.py`

---

**Última atualização:** 24/02/2026 15:30 UTC  
**Próxima revisão:** 03/03/2026  
**Status:** ✅ Ready for production
