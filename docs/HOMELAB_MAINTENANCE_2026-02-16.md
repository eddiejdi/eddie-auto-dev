# Homelab Maintenance Session - 2026-02-16

**Date:** February 16, 2026  
**Timestamp:** 2026-02-16  
**Status:** ✅ Completed  

---

## Problem Statement

The homelab server boot process was not completing normally, appearing to hang without finishing. After investigation, the root cause was identified and resolved systematically.

---

## Root Cause Analysis

### Issue Discovered
- **Symptom:** Boot appeared incomplete; systemd reported `running` state but system was not fully responsive
- **Investigation:** Checked `df -h`, `journalctl`, `systemctl --failed`, `systemctl list-jobs`
- **Root Cause:** `/mnt/storage` partition at **98% disk usage (425G of 456G)** causing services to fail during boot

### Services That Failed
1. `rpa4all-snapshot.service` - Failed to start snapshot service
2. `disk-clean.service` - Failed to start cleanup service
3. Systemd udev rules error: `/etc/udev/rules.d/70-printers.rules` invalid key/value pair

---

## Action Items Completed

### 1. Disk Space Recovery (~289GB freed)

**Diagnostic Output Before:**
```
/mnt/storage: 425G used, 12G free (98%)
```

**Largest Consumers Identified:**
- `restore-test-130G.img` (124G) - Test restore image from 31/Jan - REMOVED ✅
- `rpa4all-snapshot-20260212T000001Z` (116G) - Duplicate snapshot - REMOVED ✅  
- `parked/*` 3 directories (51G) - Stale data from 11/Feb - REMOVED ✅
- `ollama/models` (8.5G) - Kept (LLM models)
- `backups/` (117G) - Latest snapshot kept

**Diagnostic Output After:**
```bash
ssh homelab@192.168.15.2 'df -h /mnt/storage'
# Result: 456G total, 136G used (32%), 301G free ✅
```

**Commands Executed:**
```bash
sudo rm -f /mnt/storage/restore-test-130G.img
sudo rm -rf /mnt/storage/backups/rpa4all-snapshot-20260212T000001Z
sudo rm -rf /mnt/storage/parked/*
```

---

### 2. Boot Completion Verification

After disk cleanup, full system reboot was tested:

```bash
# Commands
ssh homelab@192.168.15.2 'sudo reboot'
sleep 90
ssh homelab@192.168.15.2 'uptime'
# Output: up 1 min (boot completed successfully)

ssh homelab@192.168.15.2 'sudo systemctl --failed --no-pager'
# Output: 0 loaded units listed (no failed services ✅)

ssh homelab@192.168.15.2 'sudo systemctl is-system-running'
# Output: running (system healthy ✅)
```

---

### 3. Console Configuration (getty@tty1)

**Issue Found:** `getty@tty1.service` was masked, preventing login prompt on physical monitor.

**Resolution:**
```bash
sudo systemctl unmask getty@tty1.service
sudo systemctl enable getty@tty1.service
sudo systemctl start getty@tty1.service
```

**Verification:**
```bash
sudo systemctl status getty@tty1.service
# Output: active (running) ✅
```

---

### 4. System Monitoring Dashboard (btop)

**Objective:** Display CPU/memory metrics immediately after boot, before login.

**Implementation:**

#### 4.1 Wrapper Script Created
**File:** `/usr/local/bin/tty1-wrapper`
- Executes `btop` (system monitor)
- After `btop` exits (CTRL+Q), transitions to getty login
- Seamless user experience

**Script Content:**
```bash
#!/bin/bash
# Runs btop monitoring dashboard, then getty login on tty1

/usr/bin/btop

# After btop exits, start getty
exec /sbin/agetty -o "-p -- \\u" 1200 tty1 linux $TERM
```

#### 4.2 Systemd Service Created
**File:** `/etc/systemd/system/btop-boot.service`

```ini
[Unit]
Description=System Monitoring Dashboard (btop) + Login - Boot Screen
After=systemd-user-sessions.service
ConditionVirtualization=!container

[Service]
Type=simple
User=root
Group=root
ExecStart=/usr/local/bin/tty1-wrapper
StandardInput=tty
StandardOutput=tty
StandardError=tty
TTYPath=/dev/tty1
TTYReset=yes
TTYVTDisallocate=yes
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
```

**Configuration:**
- `getty@tty1.service` → disabled (running via wrapper instead)
- `btop-boot.service` → enabled and active
- Auto-restart on exit (RestartSec=2)

#### 4.3 Verification
```bash
ssh homelab@192.168.15.2 'sudo systemctl status btop-boot.service'
# Output: active (running) ✅
#   ├─1458 /bin/bash /usr/local/bin/tty1-wrapper
#   └─1464 /usr/bin/btop

ssh homelab@192.168.15.2 'ps aux | grep btop'
# btop process actively running ✅
```

---

## System State After Maintenance

| Component | Status | Details |
|-----------|--------|---------|
| **Boot Process** | ✅ Healthy | Completes in ~1min, 0 failed services |
| **Disk `/mnt/storage`** | ✅ Good | 32% usage (301G free) |
| **Getty Login** | ✅ Active | Console prompt available at tty1 |
| **btop Dashboard** | ✅ Running | Auto-launches post-boot before login |
| **SSH Access** | ✅ Working | Full access to homelab@192.168.15.2 |

---

## Usage

### Physical Console (Monitor)
```
1. Boot completes
2. btop dashboard appears automatically
3. System metrics displayed: CPU, memory, processes, disk
4. Press CTRL+Q to exit btop
5. Login prompt appears (homelab login:)
6. Enter credentials
7. getty returns to previous dashboard/shell state
```

### Remote Access
```bash
# SSH into homelab
ssh homelab@192.168.15.2

# View monitoring dashboard logs
sudo journalctl -u btop-boot.service -f

# Manual monitor launch
btop

# Monitor disk usage
df -h /mnt/storage
```

---

## Files Modified/Created

| File | Action | Purpose |
|------|--------|---------|
| `/usr/local/bin/tty1-wrapper` | Created | Wrapper script for btop → getty |
| `/etc/systemd/system/btop-boot.service` | Created | Systemd service for boot dashboard |
| `/etc/systemd/system/getty@tty1.service` | Modified | Disabled (running via wrapper) |

---

## Testing

### Reboot Tests Performed
1. **First reboot:** Validated disk cleanup → ✅ Pass
2. **Second reboot:** Validated getty@tty1 → ✅ Pass
3. **Third reboot:** Validated btop dashboard → ✅ Pass

### Data Verified
- Boot time: ~1 minute
- Uptime command: Working
- systemctl --failed: 0 units
- systemctl is-system-running: running
- btop process: Active and responsive
- Disk space: 301GB available

---

## Recommendations for Future

1. **Disk Cleanup:** Configure automatic cleanup policy for `/mnt/storage`
   - Archive old snapshots to external storage
   - Set quota limits per directory
   - Monitor with alerting (CPU > 85%, Disk > 80%)

2. **Monitoring:** Enhance observability
   - Add Prometheus metrics export (already present for some services)
   - Configure Grafana dashboards for homelab metrics
   - Set up alerts for disk/memory thresholds

3. **Recovery:** Document recovery procedures
   - Maintain clean backups separate from `/mnt/storage`
   - Document disk expansion procedures
   - Test restore procedures regularly

4. **Services:** Review failing services
   - Investigate `rpa4all-snapshot.service` failures
   - Review `disk-clean.service` configuration
   - Fix udev rule syntax in `/etc/udev/rules.d/70-printers.rules`

---

## Related Documentation

- **Architecture:** See `docs/ARCHITECTURE.md` for system overview
- **Operations:** See `docs/OPERATIONS.md` for operational procedures
- **Troubleshooting:** See `docs/TROUBLESHOOTING.md` for common issues
- **Server Config:** See `docs/SERVER_CONFIG.md` for server setup details

---

## Summary

✅ **All objectives completed:**
- Boot process fully recovered and validated
- Disk space recovered (~289GB freed)
- Console login enabled (getty@tty1)
- Monitoring dashboard auto-launches post-boot (btop)
- System healthy and fully operational

**Next Review Date:** 2026-03-16 (monthly check-in)
