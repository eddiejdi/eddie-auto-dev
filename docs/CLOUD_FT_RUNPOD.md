# Cloud FT / RunPod — movido

Este documento e o pipeline de treino cloud foram extraídos do monorepo.

## Fonte canônica

- **Código e fluxo:** https://github.com/eddiejdi/homelab-cloud-ft  
- **Dashboard Grafana:** https://github.com/eddiejdi/homelab-grafana-dashboards/blob/main/dashboards/infrastructure/cloud-ft-runpod.json  
- **Painel:** https://grafana.rpa4all.com/d/cloud-ft-runpod/cloud-ft-runpod?orgId=1&refresh=30s  

## Homelab

```bash
cd /home/homelab/homelab-cloud-ft
sudo systemctl status cloud-ft-orchestrator cloud-ft-exporter
python3 -m cloud_ft.orchestrator --once
```

State/metrics: `/var/lib/eddie/cloud_ft/`  
Resultados: `/home/homelab/finetune/cloud-results/`
