# 🔧 Fix: Gauges sem Dados — Eddie Central

> **Quick Start:** Solução para 2 métricas críticas faltando no dashboard

---

## ⚡ Deploy Rápido (TL;DR)

```bash
# 1. Deploy automatizado no homelab
./deploy_missing_metrics.sh

# 2. Configurar Prometheus (manual)
ssh homelab@192.168.15.2
sudo nano /etc/prometheus/prometheus.yml
# Adicionar job (ver output do script)
sudo systemctl reload prometheus

# 3. Validar
python3 validate_eddie_central_api.py
```

**Resultado:** 7/20 → 9/20 gauges válidos (35% → 45%) ✅

---

## 📁 Arquivos

| Arquivo | Descrição |
|---------|-----------|
| `eddie_central_missing_metrics.py` | ⭐ Exporter de métricas (porta 9102) |
| `deploy_missing_metrics.sh` | 🚀 Deploy automatizado |
| `SOLUCAO_GAUGES_SEM_DADOS.md` | 📖 Documentação completa |
| `validate_eddie_central_api.py` | 🧪 Script de validação |

---

## 🎯 Problema → Solução

| Gauge | Query | Status Antes | Status Depois |
|-------|-------|--------------|---------------|
| Agentes Ativos | `agent_count_total` | ❌ SEM DADOS | ✅ OK |
| Taxa de Mensagens | `message_rate_total` | ❌ SEM DADOS | ✅ OK |

---

## 📊 Teste Local

```bash
# Terminal 1
python3 eddie_central_missing_metrics.py

# Terminal 2
curl http://localhost:9102/metrics | grep agent_count
# agent_count_total 5.0

curl http://localhost:9102/metrics | grep message_rate
# message_rate_total 8.3
```

---

## 📞 Links

- **Dashboard:** https://grafana.rpa4all.com/d/eddie-central/
- **Doc Completa:** [SOLUCAO_GAUGES_SEM_DADOS.md](SOLUCAO_GAUGES_SEM_DADOS.md)
- **Relatório Validação:** [VALIDATION_EDDIE_CENTRAL_REPORT.md](VALIDATION_EDDIE_CENTRAL_REPORT.md)
- **Plano Correção:** [CORRECTION_PLAN_EDDIE_CENTRAL.md](CORRECTION_PLAN_EDDIE_CENTRAL.md)

---

**Status:** ✅ Pronto para deploy  
**Próximo passo:** Adicionar 11 queries faltantes (ver CORRECTION_PLAN)
