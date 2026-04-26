# 📊 NAS Monitoring & LTFS Self-Heal Setup

Complete guide to monitoring infrastructure for NAS (192.168.15.4) with automatic crash detection and recovery.

## 🚀 Quick Start

### Access Points
| Service | URL | Purpose |
|---------|-----|---------|
| **Grafana** | http://127.0.0.1:3002 | Dashboards & visualization |
| **Prometheus** | http://127.0.0.1:9090 | Metrics storage & queries |
| **NAS Node Exporter** | http://192.168.15.4:9100 | Hardware metrics |

### Dashboards Available
1. **NAS Monitoring Stable** - Baseline CPU/RAM/Disk/IO/Network metrics
2. **LTFS Crash Detection** - Crash timeline, self-heal status, recovery tracking

---

## 📋 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     NAS (192.168.15.4)                      │
│  ┌───────────────┐  ┌──────────────┐  ┌───────────────┐    │
│  │ node-exporter │  │ LTFS Mount   │  │ LTO6 Drives   │    │
│  │ :9100         │  │ /mnt/tape    │  │ (fc_host0,7)  │    │
│  └───────┬───────┘  └──────┬───────┘  └───────────────┘    │
│          │                  │                                │
│          └──────┬───────────┘                                │
│                 │ Textfile metrics                           │
│          ┌──────▼──────────────┐                             │
│          │ /var/lib/prometheus │                             │
│          │ - ltfs_drain.prom   │                             │
│          │ - lto6.prom         │                             │
│          │ - lto6_selfheal.prom│                             │
│          └────────┬────────────┘                             │
└────────────────────┼──────────────────────────────────────────┘
                     │ HTTP :9100/metrics
                     │
        ┌────────────▼────────────┐
        │  Prometheus (127.0.0.1) │
        │  :9090                  │
        │  - Scrapes every 15s    │
        │  - Alert rules active   │
        └────────────┬────────────┘
                     │ Query/Alerts
                     │
        ┌────────────▼────────────┐
        │  Grafana (127.0.0.1)    │
        │  :3002                  │
        │  - 2 Dashboards         │
        │  - Real-time metrics    │
        └─────────────────────────┘
```

---

## 🛡️ LTFS Crash Detection System

### Problem Statement
NAS suffered LTFS mount hang during drain operation:
- **13:55:44** - Last file drained (5659 files completed)
- **13:56:52** - NAS rebooted (68 seconds later)
- **Root cause** - LTFS fuse mount stuck in I/O flush
- **Trigger** - Watchdog timeout forced reboot

### Solution: Auto-Recovery
✅ Systemd timer executes every 5 minutes
✅ Detects mount hang/unmounted state
✅ Automatically remounts with fsck validation
✅ Logs all operations for audit trail
✅ Prometheus alerts on failures
✅ Grafana dashboard visualizes timeline

---

## 📊 Grafana Dashboards

### Dashboard 1: NAS Monitoring Stable
**URL**: http://127.0.0.1:3002/d/nas-monitoring-stable

6 panels showing baseline metrics:
- **NAS Status** (Gauge) - UP/DOWN indicator
- **CPU Usage** (%) - 5-min rolling average
- **Memory Usage** (GB) - Available/Total
- **Disk Space** (GB) - Free space by filesystem
- **Disk I/O** (ops/sec) - Read/Write operations
- **Network Throughput** (Mbps) - RX/TX traffic

Query range: Last 6 hours (configurable)

### Dashboard 2: LTFS Crash Detection & Self-Heal
**URL**: http://127.0.0.1:3002/d/nas-ltfs-crash-detection

7 panels for crash diagnostics:

#### Panel 1: LTFS Mount Status (Gauge)
```promql
nas_ltfs_mount_up{mountpoint="/mnt/tape/lto6"}
```
- RED (0) = UNMOUNTED → Self-heal timer triggers
- GREEN (1) = MOUNTED → Healthy state

#### Panel 2: Drain Activity Timeline
```promql
ltfs_drain_total_files_tiered
rate(ltfs_drain_total_files_tiered[5m]) * 300
```
- Files drained (cumulative)
- Drain rate (files per 5 minutes)
- Anomaly: Rate drop = hang indicator

#### Panel 3: Mount Timeline (Step-Line)
```promql
nas_ltfs_mount_up{mountpoint="/mnt/tape/lto6"}
```
- Visualization of mount up/down events
- Crash timestamp + recovery timestamp
- Interval gap = problem window

#### Panel 4: Drain Rate Stall Detection (Bar Chart)
```promql
rate(ltfs_drain_total_files_tiered[5m]) * 300
avg_over_time(rate(ltfs_drain_total_files_tiered[5m]) * 300[1h])
```
- Current rate vs 1h baseline
- Threshold: Rate < 50% baseline = WARNING
- Indicates hang before watchdog timeout

#### Panel 5: NAS Uptime
```promql
time() - node_boot_time_seconds{job="nas-node-exporter"}
```
- Seconds since last boot
- Alert if < 300 seconds (recent reboot)

#### Panel 6: Self-Heal Recovery Status
```promql
nas_ltfs_selfheal_consecutive_failures{mountpoint="/mnt/tape/lto6"}
nas_ltfs_selfheal_last_result_code{mountpoint="/mnt/tape/lto6"}
```
- Failure count (0 = healthy)
- Result code: 0=healthy, 1=recovered, 2=failed, 3=cooldown, 4=rate_limited

#### Panel 7: Self-Heal Success Rate %
```promql
(1 - nas_ltfs_selfheal_consecutive_failures{mountpoint="/mnt/tape/lto6"}) * 100
```
- Percentage of successful remount attempts
- Target: 100%

---

## 🚨 Prometheus Alerts

Alert file: `/etc/prometheus/rules/ltfs-crash-detection.yml`

### Alert 1: LTFSMountDown
```yaml
Severity: CRITICAL
Trigger: nas_ltfs_mount_up == 0 for 2 minutes
Action: Notify operators, self-heal timer attempts remount
```
**When it fires:**
- LTFS mount is not available
- Node-exporter reports 0
- Likely crash or stuck process

**What to do:**
1. Check Grafana timeline (when did it go down?)
2. Check self-heal logs: `tail -50 /var/log/ltfs-selfheal.log`
3. If persistent, check tape cartridge physically

### Alert 2: LTFSDrainStall
```yaml
Severity: WARNING
Trigger: Drain rate < 50% baseline for 3 minutes
Action: Notify operators (likely hang in progress)
```
**When it fires:**
- Drain process slowed significantly
- Usually precedes watchdog timeout
- **Early warning system**

**What to do:**
1. Check if any tape/backup processes are hung
2. Monitor dashboard - watch for mount status going RED
3. May need manual intervention soon

### Alert 3: LTFSSelfHealFailed
```yaml
Severity: CRITICAL
Trigger: >3 consecutive recovery failures
Action: Escalate to operations team
```
**When it fires:**
- Auto-recovery failed multiple times
- Possible hardware failure (tape drive, FC connection)
- Manual intervention required

**What to do:**
1. Check NAS console for tape drive errors
2. Verify FC card link status
3. Check dmesg for scsi/tape errors

### Alert 4: NASRebootedRecently
```yaml
Severity: WARNING
Trigger: Uptime < 5 minutes
Action: Notify operators to investigate crash
```
**When it fires:**
- NAS rebooted unexpectedly
- Check what caused reboot

**What to do:**
1. Review system logs: `journalctl --boot=-1 -n 100`
2. Check for kernel panic messages
3. Review previous drain activity timeline

---

## ⚙️ Self-Heal Service

### Installation
Systemd service automatically installed on NAS via:
- `/etc/systemd/system/ltfs-selfheal.timer` - Periodic scheduler
- `/etc/systemd/system/ltfs-selfheal.service` - Recovery executor
- `/home/homelab/bin/ltfs-selfheal-remount.sh` - Detection script

### Schedule
```ini
[Timer]
OnBootSec=30s          # First run 30s after NAS boot
OnUnitActiveSec=5min   # Then every 5 minutes
```

### Monitoring Service Status
```bash
# Check if timer is active
sudo systemctl status ltfs-selfheal.timer

# View recent logs
sudo journalctl -u ltfs-selfheal.service -n 50

# Manually trigger (test)
sudo systemctl start ltfs-selfheal.service

# Temporarily disable (if needed)
sudo systemctl stop ltfs-selfheal.timer
```

### Log File
Location: `/var/log/ltfs-selfheal.log`

Example output:
```
[2026-04-26 13:57:22] === LTFS Self-Heal Check Started ===
[2026-04-26 13:57:22] LTFS não está montado — tentando remount
[2026-04-26 13:57:25] ltfsck passou — cartucho OK
[2026-04-26 13:57:26] ✓ LTFS remontado com sucesso
[2026-04-26 13:57:26] === LTFS Self-Heal Check Completed ===
```

---

## 📈 Metrics Reference

### NAS System Metrics
| Metric | Type | Description | Query |
|--------|------|-------------|-------|
| `up` | Gauge | NAS online | `up{job="nas-node-exporter"}` |
| `node_cpu_seconds_total` | Counter | CPU time | `rate(...[5m])` |
| `node_memory_MemAvailable_bytes` | Gauge | Free RAM | `... / 1024 / 1024 / 1024` (GB) |
| `node_filesystem_avail_bytes` | Gauge | Disk free | `... / 1024 / 1024 / 1024` (GB) |
| `node_disk_reads_completed_total` | Counter | Read ops | `rate(...[5m])` |
| `node_disk_writes_completed_total` | Counter | Write ops | `rate(...[5m])` |
| `node_network_receive_bytes_total` | Counter | RX traffic | `rate(...[5m]) * 8 / 1000000` (Mbps) |
| `node_network_transmit_bytes_total` | Counter | TX traffic | `rate(...[5m]) * 8 / 1000000` (Mbps) |
| `node_boot_time_seconds` | Gauge | Last boot timestamp | For uptime calc |

### LTFS Specific Metrics
| Metric | Type | Source | Description |
|--------|------|--------|-------------|
| `nas_ltfs_mount_up` | Gauge | textfile_exporter | 1=mounted, 0=unmounted |
| `ltfs_drain_total_files_tiered` | Gauge | textfile_exporter | Cumulative files drained |
| `ltfs_drain_last_tiered_timestamp_seconds` | Gauge | textfile_exporter | Unix timestamp of last drain |
| `nas_ltfs_selfheal_consecutive_failures` | Gauge | textfile_exporter | Recovery attempt failures |
| `nas_ltfs_selfheal_last_result_code` | Gauge | textfile_exporter | 0=healthy, 1=recovered, 2=failed |
| `node_fibrechannel_error_frames_total` | Counter | node-exporter | FC errors per host |
| `node_fibrechannel_link_failure_total` | Counter | node-exporter | FC link failures |

---

## 🔧 Troubleshooting

### LTFS Mount Not Recovering
```bash
# 1. Check if script is running
ps aux | grep ltfs-selfheal

# 2. Check logs
tail -100 /var/log/ltfs-selfheal.log

# 3. Manually test recovery
sudo /home/homelab/bin/ltfs-selfheal-remount.sh

# 4. Check tape device status
mt -f /dev/st0 status

# 5. Check LTFS fsck result
sudo ltfsck -d /dev/st0 -v
```

### Prometheus Not Scraping NAS
```bash
# 1. Check target status
curl -s http://127.0.0.1:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="nas-node-exporter")'

# 2. Check last error
# Look for .lastError field in response above

# 3. Verify NAS is reachable
ping -c 3 192.168.15.4
curl -s http://192.168.15.4:9100/metrics | head -20
```

### Alert Rules Not Firing
```bash
# 1. Check rules are loaded
curl -s http://127.0.0.1:9090/api/v1/rules | jq '.data.groups[] | select(.name=="ltfs-crash-detection")'

# 2. Check alert state
curl -s http://127.0.0.1:9090/api/v1/alerts | jq '.data.alerts[] | select(.labels.alertname | contains("LTFS"))'

# 3. Validate rules syntax
sudo promtool check rules /etc/prometheus/rules/ltfs-crash-detection.yml
```

### Grafana Dashboard Blank
```bash
# 1. Check if Prometheus datasource is connected
# In Grafana: Configuration → Data Sources → Prometheus → Test

# 2. Check query results directly
curl -s 'http://127.0.0.1:9090/api/v1/query?query=nas_ltfs_mount_up'

# 3. Check if NAS has exported metrics recently
curl -s http://192.168.15.4:9100/metrics | grep ltfs
```

---

## 📝 Documentation Files

- **[LTFS_CRASH_SELFHEAL_SYSTEM.md](./LTFS_CRASH_SELFHEAL_SYSTEM.md)** - Deep dive technical documentation
- **[MONITORING_SETUP.md](./MONITORING_SETUP.md)** - This file (operational guide)
- **Dashboard JSON** - `/workspace/eddie-auto-dev/dashboards/nas-ltfs-selfheal-crash-detection.json`

---

## 🔗 Related Pages

- [GitHub PR #154](https://github.com/eddiejdi/eddie-auto-dev/pull/154) - Self-heal system implementation
- [Homelab Infrastructure](./../../docs/) - Complete infrastructure documentation
- [NAS Configuration](./../../docs/) - NAS specific setup

---

**Last Updated**: 2026-04-26  
**Status**: ✅ Production Ready  
**Owner**: Homelab Team
