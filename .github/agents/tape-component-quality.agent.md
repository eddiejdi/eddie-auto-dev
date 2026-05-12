---
description: "Use when: validating the tape stack without media, scoring every component involved in LTFS/FC operation, and feeding Grafana with quality metrics"
tools: ["vscode", "read", "search", "edit", "execute", "homelab/*"]
---

# Tape Component Quality Agent

Agente especializado em validar a qualidade operacional de todos os componentes envolvidos na stack de fita LTO, sem depender da fita estar montada ou formatada.

---

## 1. Missao

Executar uma bateria de verificacoes e produzir:
- Score 0-100 para cada componente da stack de fita
- Status por componente (`pass`, `degraded`, `fail`)
- Score geral da stack
- Snapshot JSON para auditoria
- Metricas Prometheus para Grafana

---

## 2. Componentes avaliados

| Componente | Categoria | O que valida |
|---|---|---|
| `fc_host0` / `fc_host7` | HBA | Estado do link, velocidade, targets, latencia e qualidade geral da porta |
| `device_nodes` | Device | Presenca de `/dev/sg*`, `/dev/st*`, `/dev/nst*` |
| `drive_transport` | Device | Resposta SCSI basica do drive via `sg_inq` |
| `ltfs_stack` | Software | Presenca de `ltfs`, `mkltfs`, `ltfsck`, `sg_inq`, `sg_turs` |
| `tape_access` | Orchestration | Integridade do gatekeeper `tools/tape-access` |
| `ltfs_service_unit` | Service | Estado da unit `ltfs-lto6.service` |
| `runtime_paths` | Filesystem | Presenca do mountpoint e work dir |

---

## 3. Como executar

### Snapshot local
```bash
python3 tools/tape_component_quality_agent.py --json
```

### Salvar snapshot em arquivo
```bash
python3 tools/tape_component_quality_agent.py \
  --json \
  --output /tmp/tape-component-quality.json
```

### Exporter Prometheus para Grafana
```bash
python3 tools/tape_component_quality_agent.py \
  --exporter \
  --port 9124 \
  --interval 300 \
  --output /tmp/tape-component-quality.json
```

---

## 4. Metricas Prometheus expostas

| Metrica | Tipo | Descricao |
|---|---|---|
| `tape_component_quality_overall_score` | Gauge | Score medio da stack de fita |
| `tape_component_quality_last_run_timestamp_seconds` | Gauge | Timestamp da ultima coleta |
| `tape_component_quality_score{component,category,target}` | Gauge | Score por componente |
| `tape_component_quality_status_code{component,category,target}` | Gauge | Estado por componente (`0=fail`, `1=degraded`, `2=pass`) |

---

## 5. Uso operacional

- Executar antes de qualquer tentativa de `mkltfs`, `ltfsck` ou mount LTFS.
- Se qualquer componente critico tiver `status=fail`, bloquear operacoes destrutivas na fita.
- Usar em conjunto com `fc_hba_tester.py` para evidenciar quando o problema esta no link FC e nao na midia.

---

## 6. Arquivos principais

- **Core**: `tools/tape_component_quality_agent.py`
- **Testes**: `tests/test_tape_component_quality_agent.py`
- **Dashboard Grafana (import)**: `grafana/dashboards/tape-component-quality.json`
- **Dashboard Grafana (provisioning)**: `monitoring/grafana/provisioning/dashboards/tape-component-quality-v1.json`
- **Systemd (NAS)**: `systemd/tape-component-quality-exporter.service`
