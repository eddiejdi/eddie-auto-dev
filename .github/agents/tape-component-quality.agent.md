---
description: "Use when: validating tape stack readiness without requiring LTFS mount/format state, scoring every LTFS/FC component, and feeding Grafana with quality metrics"
tools: [execute/runInTerminal, execute/getTerminalOutput, execute/sendToTerminal, read/readFile, read/problems, edit/editFiles, edit/createFile, search/codebase, search/fileSearch]
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
- Rubrica de score: `100` quando todos os checks do componente passam; subtrair `25` por warning e `50` por falha.
- Mapeamento de status: `pass` para score `>= 90`, `degraded` para score `60-89`, `fail` para score `< 60`.

---

## 2. Componentes avaliados

| Componente | Categoria | Critico | O que valida |
|---|---|---|---|
| `fc_host0` / `fc_host7` | HBA | Sim | Estado do link, velocidade, targets, latencia e qualidade geral da porta |
| `device_nodes` | Device | Nao | Presenca de `/dev/sg*`, `/dev/st*`, `/dev/nst*` |
| `drive_transport` | Device | Sim | INQUIRY + Test Unit Ready (`sg_inq` + `sg_turs`); detecta FC instavel |
| `ltfs_stack` | Software | Sim | Binario patched via `LTFS_BIN` + `mkltfs`, `ltfsck`, `sg_inq`, `sg_turs` |
| `tape_access` | Orchestration | Sim | Integridade do gatekeeper `tools/tape-access` (busca em `/usr/local/tools/` tambem) |
| `ltfs_orchestrator_lock` | Orchestration | Sim | Lock stale em `/run/lock/ltfs-orchestrator.lock` (PID morto = deadlock silencioso) |
| `ltfs_service_unit` | Service | Nao | Estado da unit `ltfs-lto6.service` |
| `runtime_paths` | Filesystem | Nao | Mountpoint, work dir e export Samba (`LTFS_EXPORT_DIR`) |

**Score geral ponderado**: componentes marcados como `Critico=Sim` contribuem com peso 2× no aggregate.
Uma falha critica (score=0) reduz o overall abaixo de 60 mesmo com todos os checks nao-criticos passando.

---

## 3. Como executar

### Snapshot local
```bash
python3 tools/tape_component_quality_agent.py --json
```

Se `tools/tape_component_quality_agent.py` nao existir, tratar como erro fatal e nao sintetizar score.
Se algum CLI obrigatorio (`sg_inq`, `sg_turs`, `ltfs`, `mkltfs`, `ltfsck`) estiver ausente, marcar `ltfs_stack` como `fail` com remediacao explicita.

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

## 5. Variaveis de ambiente

| Variavel | Padrao | Descricao |
|---|---|---|
| `LTFS_BIN` | `/usr/local/ltfs-patched/bin/ltfs` | Caminho do binario LTFS patched |
| `LTFS_ORCH_LOCK` | `/run/lock/ltfs-orchestrator.lock` | Lock do orchestrador (verificado por PID stale) |
| `LTFS_EXPORT_DIR` | `/run/ltfs-export/lto6` | Diretorio de export Samba do LTFS |

---

## 6. Uso operacional

- Executar como preflight antes de qualquer tentativa de `mkltfs`, `ltfsck` ou mount LTFS; nao depende de LTFS ja montado.
- Se qualquer componente marcado como `Critico=Sim` tiver `status=fail`, bloquear operacoes destrutivas na fita.
- Se `ltfs_orchestrator_lock` retornar `fail`, remover o lock stale antes de qualquer `orchestrated-mount`.
- Usar em conjunto com `fc_hba_tester.py` para evidenciar quando o problema esta no link FC e nao na midia.

---

## 7. Arquivos principais

- **Core**: `tools/tape_component_quality_agent.py`
- **Testes**: `tests/test_tape_component_quality_agent.py`
- **Dashboard Grafana (import)**: `grafana/dashboards/tape-component-quality.json`
- **Dashboard Grafana (provisioning)**: `monitoring/grafana/provisioning/dashboards/tape-component-quality-v1.json`
- **Systemd (NAS)**: `systemd/tape-component-quality-exporter.service`
