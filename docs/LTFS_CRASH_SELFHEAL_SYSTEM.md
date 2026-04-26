# LTFS Crash Self-Heal & Detection System

## Overview

Sistema automático de detecção e recuperação de crashes do LTFS (Linear Tape File System) no NAS. Implementa:

1. **Flush periódico** — `sync_type=time,sync_time=300`: LTFS escreve índice na fita a cada 5 min, liberando buffer de RAM continuamente (correção da causa raiz do crash de 2026-04-26).
2. **Detecção de Anomalias** — Monitora mount status, I/O responsiveness e drain activity.
3. **Alertas Automáticos** — Prometheus rules disparam em caso de hang, stale mount ou falha de recovery.
4. **Auto-Recovery** — Systemd timer executa self-heal a cada 5 min, cobrindo 3 cenários de falha.
5. **Grafana Dashboard** — 7 painéis visualizando crash timeline e recovery status.

---

## Causa Raiz e Correção

### Incidente: 2026-04-26 13:55:44 → 13:56:52 (68 segundos)

```
Timeline:
  13:55:44 → Último drain (5659 files, completo)
  13:55:44 → LTFS inicia flush do índice em sync_type=unmount
  13:56:52 → Fuse mount HUNG → Watchdog timeout → Auto-reboot

Causa: -o sync_type=unmount acumulou todo o estado em RAM.
       No unmount, o flush único e massivo travou o fuse layer por 68s.
       O watchdog interpretou como travamento e reiniciou a NAS.
```

### Correção aplicada (2026-04-26)

`-o sync_type=unmount` substituído por `-o sync_type=time -o sync_time=300` em:
- `tmp/ltfs-fc-stable-start` (wrapper do ltfs-lto6.service)
- `tmp/ltfs-retry.sh`

Com `sync_type=time`, o LTFS faz flushes menores a cada 5 minutos. O buffer de RAM é liberado continuamente e o unmount vira uma operação leve, eliminando o risco de flush massivo.

---

## Componentes

### 1. Grafana Dashboard — Crash Detection

**URL:** `http://127.0.0.1:3002/d/nas-ltfs-crash-detection`

| Painel | Métrica | Propósito |
|--------|---------|-----------|
| **LTFS Mount Status** | `nas_ltfs_mount_up` | Gauge: RED=down, GREEN=ok |
| **I/O Hung** | `nas_ltfs_io_hung` | 1 quando I/O não respondeu em 15s |
| **Drain Activity** | `ltfs_drain_total_files_tiered` + rate | Detector de stall |
| **Mount Timeline** | Historical `nas_ltfs_mount_up` | Crash/recovery visualization |
| **NAS Uptime** | `time() - node_boot_time_seconds` | Detectar reboots |
| **Self-Heal Status** | `nas_ltfs_selfheal_*` | Recovery attempts e result codes |
| **Success Rate %** | Derived from consecutive failures | % de remounts bem-sucedidos |

---

### 2. Prometheus Alert Rules

**Arquivo:** `/etc/prometheus/rules/ltfs-selfheal-rules.yml`  
**Repositório:** `monitoring/prometheus/ltfs-selfheal-rules.yml`

| Alert | Severidade | Trigger | Observação |
|-------|-----------|---------|------------|
| **LTFSMountDown** | CRITICAL | `nas_ltfs_mount_up == 0` por 2 min | Same as before |
| **LTFSIOHung** | CRITICAL | `nas_ltfs_io_hung == 1` imediato | **NOVO** — hang mid-sync detectado |
| **LTFSSelfHealFailed** | CRITICAL | `consecutive_failures >= 3` por 1 min | Escalar para intervenção manual |
| **LTFSDrainStall** | WARNING | `rate(drain[10m]) == 0` por **10 min** | Era 3 min — ajustado para evitar false positives durante os flushes periódicos de 300s |
| **NASRebootedRecently** | WARNING | uptime < 5 min | Imediato |

> **Por que `LTFSDrainStall` mudou de 3 min para 10 min?**  
> Com `sync_type=time`, o LTFS escreve o índice na fita a cada 300s. Esse flush bloqueia o drain por até ~90s. Com threshold de 3 min, o alert dispararia a cada ciclo de sync. Com 10 min, só alerta em stalls reais.

---

### 3. Self-Heal Systemd Service

**Timer:** `/etc/systemd/system/ltfs-selfheal.timer`  
**Script:** `/home/homelab/bin/ltfs-selfheal-remount.sh`  
**Repositório:** `tools/ltfs-selfheal-remount.sh`  
**Schedule:** 30s após boot, depois a cada 5 min

#### Cenários cobertos (novo — sync_type=time)

| Caso | Detecção | Ação |
|------|---------|------|
| **Mount down** | `findmnt` falha + sem processo | `systemctl start ltfs-lto6` (até 3 tentativas) |
| **Stale fuse mount** | `findmnt` ok + processo morto | `fusermount -u -z` → restart |
| **Hang mid-sync** | `findmnt` ok + processo vivo + `timeout 15 ls` trava | SIGTERM → espera 60s (sync em andamento) → SIGKILL → `fusermount -u -z` → restart |
| **Saudável** | `findmnt` ok + I/O responde em 15s | Sem ação — registra métricas |

> **Por que SIGTERM antes de SIGKILL no hang?**  
> Com `sync_type=time`, o LTFS pode estar no meio de escrever o índice na fita (operação levando 30-90s). SIGTERM dá até 60s para o processo finalizar o sync limpo. SIGKILL só é usado se o processo não encerrar nesse período — evita corrupção de índice.

**Exemplo de log — hang mid-sync:**
```
[2026-04-26 14:02:01] === LTFS Self-Heal (sync_type=time) ===
[2026-04-26 14:02:01] LTFS montado. Verificando I/O (timeout 15s)...
[2026-04-26 14:02:16] AVISO: I/O travado — LTFS pid=3821 ativo há 287s (sync hang)
[2026-04-26 14:02:16] SIGTERM → LTFS pid=3821 (aguardando 60s para sync finalizar)...
[2026-04-26 14:02:44] LTFS encerrou após 28s (sync concluído normalmente)
[2026-04-26 14:02:46] Tentativa 1/3 — iniciando ltfs-lto6.service...
[2026-04-26 14:03:10] ✓ LTFS remontado (tentativa 1, 24s)
```

---

## Métricas Exportadas

Arquivo: `/var/lib/node_exporter/textfile_collector/ltfs_selfheal.prom` (na NAS)

```
nas_ltfs_mount_up{mountpoint="/mnt/tape/lto6"}                1 ou 0
nas_ltfs_io_hung{mountpoint="/mnt/tape/lto6"}                 1 quando I/O não responde em 15s
nas_ltfs_selfheal_consecutive_failures{mountpoint="..."}      0-N
nas_ltfs_selfheal_last_result_code{mountpoint="..."}
  # 0 = healthy (sem ação)
  # 1 = recovered (estava desmontado, remontou OK)
  # 2 = failed (retries esgotados)
  # 5 = stale fuse mount recovered
  # 6 = hung mid-sync recovered
```

Métricas da NAS (node-exporter):
```
ltfs_drain_total_files_tiered           contador incremental
node_boot_time_seconds                  timestamp do último boot
node_fibrechannel_error_frames_total    erros FC por host
node_fibrechannel_link_failure_total    falhas de link FC
```

---

## Como Usar

### Monitorar em tempo real
```bash
# Dashboard Grafana
open http://127.0.0.1:3002/d/nas-ltfs-crash-detection

# Alerts ativos no Prometheus
curl -sS http://127.0.0.1:9090/api/v1/alerts | jq '.data.alerts[] | select(.labels.category=="ltfs")'

# Logs do self-heal
ssh homelab@192.168.15.2 'tail -50 /var/log/ltfs-selfheal.log'
```

### Disparar self-heal manualmente
```bash
ssh homelab@192.168.15.2 'sudo systemctl start ltfs-selfheal.service'
```

### Verificar sync_type ativo na NAS
```bash
ssh root@192.168.15.4 'cat /proc/$(pgrep -f "ltfs /mnt")/cmdline | tr "\0" "\n" | grep sync'
# Esperado: sync_type=time e sync_time=300
```

### Desabilitar self-heal temporariamente
```bash
ssh homelab@192.168.15.2 'sudo systemctl stop ltfs-selfheal.timer'
```

---

## Deploy / Atualização

```bash
# Self-heal script
scp tools/ltfs-selfheal-remount.sh homelab@192.168.15.2:/home/homelab/bin/ltfs-selfheal-remount.sh
ssh homelab@192.168.15.2 'chmod +x /home/homelab/bin/ltfs-selfheal-remount.sh'

# Alert rules Prometheus
scp monitoring/prometheus/ltfs-selfheal-rules.yml homelab@192.168.15.2:/etc/prometheus/rules/ltfs-selfheal-rules.yml
ssh homelab@192.168.15.2 'curl -sX POST http://localhost:9090/-/reload'

# ltfs-fc-stable-start (fix sync_type)
scp tmp/ltfs-fc-stable-start root@192.168.15.4:/usr/local/sbin/ltfs-fc-stable-start
ssh root@192.168.15.4 'chmod +x /usr/local/sbin/ltfs-fc-stable-start && systemctl restart ltfs-lto6'
```

---

**Last Updated:** 2026-04-26  
**Status:** ✅ ACTIVE — sync_type=time operacional
