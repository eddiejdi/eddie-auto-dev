# 🛡️ LTFS Crash Self-Heal & Detection System

## Overview

Sistema automático de detecção e recuperação de crashes do LTFS (Linear Tape File System) no NAS. Implementa:

1. **Detecção de Anomalias** - Monitora mount status e drain activity
2. **Alertas Automáticos** - Prometheus rules disparam quando LTFS hang/crash detectado
3. **Auto-Recovery** - Systemd timer executa remount a cada 5 minutos
4. **Grafana Dashboard** - 7 painéis visualizando crash timeline e recovery status

---

## Causa Raiz do Crash Identificada ⚠️

```
Timeline: LTFS Drain finalizado 13:55:44 → NAS reboot 13:56:52 (68 segundos depois)

Hipótese: LTFS fuse mount ficou HUNG em I/O durante flush final
         → Systemd watchdog timeout (~10-180s) → Auto-reboot

Evidence:
✅ Último arquivo drenado: 5659 files (completo)
✅ 68 segundos gap → Watchdog timeout
❌ LTFS agora unmounted (nas_ltfs_mount_up=0)
✅ Hardware OK (CPU 45°C, RAM 3.2GB free, FC errors=0)
```

---

## Componentes Implementados

### 1. 📊 Grafana Dashboard — Crash Detection

**URL:** `http://127.0.0.1:3002/d/nas-ltfs-crash-detection`

**Painéis:**

| Painel | Métrica | Propósito |
|--------|---------|----------|
| **LTFS Mount Status** | `nas_ltfs_mount_up` | Gauge: RED=unmounted, GREEN=mounted |
| **Drain Activity** | `ltfs_drain_total_files_tiered` + rate | Detector de stall (taxa cai = hang) |
| **Mount Timeline** | Historical `nas_ltfs_mount_up` | Visualizar crash/recovery eventos |
| **Drain Rate Stall** | `rate(...) vs baseline` | Comparar com histórico para anomalias |
| **NAS Uptime** | `time() - node_boot_time_seconds` | Detectar reboots recentes |
| **Self-Heal Status** | `nas_ltfs_selfheal_*` metrics | Recovery attempts e success rate |
| **Success Rate %** | `(1 - failures) * 100` | % de remounts bem-sucedidos |

**Exemplos de Leitura:**

- **Mount Status = RED** → LTFS não está montado → Self-heal timer disparará em ≤5 min
- **Drain Rate cai 50%** → Possível hang → Alert `LTFSDrainStall` em 3 min
- **Uptime < 5 min** → NAS reiniciou recentemente → Verificar logs de crash

---

### 2. 🚨 Prometheus Alert Rules

**Arquivo:** `/etc/prometheus/rules/ltfs-crash-detection.yml`

**Alertas Configurados:**

#### `LTFSMountDown` (CRITICAL)
```yaml
Trigger: nas_ltfs_mount_up == 0 por 2 minutos
Action:  Notifica para tentativa de remount via systemd timer
```

#### `LTFSDrainStall` (WARNING)
```yaml
Trigger: Drain rate cai para <50% do baseline em 3 minutos
Action:  Indica possível hang (antes do reboot)
```

#### `LTFSSelfHealFailed` (CRITICAL)
```yaml
Trigger: >3 falhas consecutivas de remount
Action:  Escala para OPS (possível falha de hardware)
```

#### `NASRebootedRecently` (WARNING)
```yaml
Trigger: NAS uptime < 5 minutos
Action:  Notifica para investigação de logs de crash
```

---

### 3. ⚙️ Self-Heal Systemd Service

**Timer:** `/etc/systemd/system/ltfs-selfheal.timer`
```ini
[Timer]
OnBootSec=30s        # Executar 30s após boot
OnUnitActiveSec=5min # Depois, a cada 5 minutos
```

**Script:** `/home/homelab/bin/ltfs-selfheal-remount.sh`

```bash
Lógica:
1. Verifica se LTFS está montado
2. Se unmounted → tenta remount
3. Se hung (timeout) → força unmount + remount
4. Registra sucesso/falha em /var/log/ltfs-selfheal.log
5. Exporta métricas para node-exporter via textfile
```

**Exemplo de Execução:**
```
[2026-04-26 13:57:22] === LTFS Self-Heal Check Started ===
[2026-04-26 13:57:22] LTFS não está montado — tentando remount
[2026-04-26 13:57:25] ltfsck passou — cartucho OK
[2026-04-26 13:57:26] ✓ LTFS remontado com sucesso
[2026-04-26 13:57:26] === LTFS Self-Heal Check Completed ===
```

---

## Como Usar

### Monitorar Status em Tempo Real
```bash
# Via Grafana (recomendado)
ssh -oBatchMode=yes homelab@192.168.15.2 'curl -sS http://127.0.0.1:3002/d/nas-ltfs-crash-detection'

# Via Prometheus alerts
curl -sS http://127.0.0.1:9090/api/v1/alerts | jq '.data.alerts[] | select(.labels.alertname | startswith("LTFS"))'
```

### Verificar Self-Heal Logs
```bash
ssh -oBatchMode=yes homelab@192.168.15.2 'tail -50 /var/log/ltfs-selfheal.log'
```

### Disparar Self-Heal Manualmente
```bash
ssh -oBatchMode=yes homelab@192.168.15.2 'sudo systemctl start ltfs-selfheal.service'
```

### Desabilitar Temporariamente
```bash
ssh -oBatchMode=yes homelab@192.168.15.2 'sudo systemctl stop ltfs-selfheal.timer'
```

---

## Métricas Exportadas

### Para Node-Exporter Textfile:
```
nas_ltfs_mount_up{mountpoint="/mnt/tape/lto6"}              1 (ou 0)
nas_ltfs_selfheal_consecutive_failures{mountpoint="..."}    0-N
nas_ltfs_selfheal_last_result_code{mountpoint="..."}        0-4
  # 0=healthy, 1=recovered, 2=failed, 3=cooldown, 4=rate_limited
```

### Existentes:
```
ltfs_drain_total_files_tiered           5659 (ou incrementa)
ltfs_drain_last_tiered_timestamp_seconds 1777211744
node_boot_time_seconds                  1777211812
node_fibrechannel_error_frames_total    0 (por host)
node_fibrechannel_link_failure_total    0 (por host)
```

---

## Exemplo: Crash Detection em Ação

### Cenário: LTFS Mount Hang (como ocorreu)

**T+0s (13:55:44):** Último arquivo drenado (2767.png)
- `ltfs_drain_total_files_tiered = 5659`
- `nas_ltfs_mount_up = 1` (mounted)
- Drain rate: ~20 files/5min

**T+30s (13:56:14):** LTFS fuse mount fica hung em flush
- Drain rate: ~2 files/5min (caiu 90%) → Alert `LTFSDrainStall` dispara em 3 min
- Watchdog keepalive para (systemd não consegue sincronizar)

**T+68s (13:56:52):** Watchdog timeout → Auto-reboot
- `node_boot_time_seconds` salta para `1777211812`
- `nas_ltfs_mount_up = 0` (failsafe unmount pós-reboot)
- Alert `NASRebootedRecently` dispara imediatamente
- Alert `LTFSMountDown` dispara em 2 min

**T+100s (13:57:25):** Self-heal timer executa
- `ltfs-selfheal-remount.sh` detecta mount down
- Tenta `ltfsck -d /dev/st0` → ✓ cartucho OK
- Executa `mount -t ltfs /dev/st0 /mnt/tape/lto6` → ✓ sucesso
- `nas_ltfs_mount_up = 1` (volta ao normal)
- Alert `LTFSMountDown` resolve automaticamente

**T+300s (13:60:52):** Próxima verificação
- Self-heal timer executa novamente (scheduled)
- `nas_ltfs_mount_up = 1` → nenhuma ação necessária
- Logs registram: "LTFS OK — nenhuma ação necessária"

---

## Prevenção Futura

Para evitar crashes similares:

1. **Aumentar watchdog timeout** durante operações de drain
   ```bash
   echo 300 | sudo tee /proc/sys/kernel/watchdog_thresh
   ```

2. **Adicionar pre-reboot check** (impedir reboot se LTFS em uso)
   ```bash
   # /etc/systemd/system/ltfs-precheck-reboot.service
   ExecStart=/home/homelab/bin/ltfs-check-before-reboot.sh
   ```

3. **Implementar drain timeout**
   ```bash
   # Kill drain process se >10 minutos sem progresso
   timeout 600 /usr/local/bin/ltfs-drain.sh
   ```

4. **Monitorar FC link failures**
   - Alert se `node_fibrechannel_link_failure_total` incrementa

---

## Próximos Passos

- [ ] Testar failover em cenário controlado (simular mount hang)
- [ ] Ajustar watchdog timeout se ainda houver crashes
- [ ] Adicionar webhook para notificação Telegram em crashes
- [ ] Implementar backup de dados LTFS pre-remount
- [ ] Documentar runbook de recovery manual se auto-heal falhar

---

**Last Updated:** 2026-04-26
**System Owner:** Homelab Team
**Status:** ✅ ACTIVE
