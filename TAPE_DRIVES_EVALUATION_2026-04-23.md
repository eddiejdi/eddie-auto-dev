# Tape Drives Evaluation Report - 2026-04-23

## Executive Summary

✅ **Drive 2 (HUJ5485704)**: FULLY OPERATIONAL & HEALTHY  
❌ **Drive 1 (HUJ5485716)**: OFFLINE - FC LINK DOWN (fixable)

---

## Drive 2: HP Ultrium 6-SCSI (sg1) - HEALTHY ✅

### Device Information
```
Serial Number:    HUJ5485704
Device:           /dev/sg1 (/dev/nst1 for tape operations)
Model:            HP Ultrium 6-SCSI
Firmware:         J5SW
Interface:        Fibre Channel via QLogic port 1 (PCI 01:00.1)
```

### Health Status
```
Drive Status:       ONLINE
Position:           BOT (Beginning Of Tape)
Density:            0x5a (LTO-6)
Soft Errors:        0

Tape Alerts:        ALL = 0
  ✓ No read/write errors
  ✓ No media issues
  ✓ No cleaning required
  ✓ No mechanical failures
  ✓ No interface errors
  ✓ All systems nominal
```

### Assessment
**✅ OPERATIONAL** - Drive 2 is fully functional and ready for backup operations.

---

## Drive 1: HP Ultrium 6-SCSI (sg0) - OFFLINE ❌

### Issue
```
Device Files:       /dev/sg0, /dev/nst0 - NOT FOUND
Serial Number:      HUJ5485716
Status:             Not detected after system boot
Connectivity:       Fibre Channel via QLogic port 0 (PCI 01:00.0)
```

### Root Cause
The FC HBA Port 0 has BusMaster functionality disabled while Port 1 is enabled. This prevents the drive from being detected on the SCSI bus.

```
QLogic HBA Status:
  Port 0 (01:00.0): BusMaster=DISABLED  ← Connected to Drive 1 [OFFLINE]
  Port 1 (01:00.1): BusMaster=ENABLED   ← Connected to Drive 2 [ONLINE ✓]
```

This matches a known infrastructure issue where Port 0 generates Fibre Channel Loop Initialization Primitives (LIPs) that disrupt device detection.

### Solution

**Option 1: Unbind Problematic Port (Quick Fix)**
```bash
ssh homelab@192.168.15.4
sudo sh -c 'echo "0000:01:00.0" > /sys/bus/pci/drivers/qla2xxx/unbind'
sudo sh -c 'echo "- - -" > /sys/class/scsi_host/host0/scan'
# Verify: ls -la /dev/sg0
```

**Option 2: Rescan SCSI Bus (Alternative)**
```bash
sudo sh -c 'echo "- - -" > /sys/class/scsi_host/host*/scan'
```

**Option 3: Full FC Driver Reload (Requires Downtime)**
```bash
sudo modprobe -r qla2xxx
sudo modprobe qla2xxx
```

**Recommended**: Option 1 (unbind port 0) - Fastest, lowest impact.

---

## Session Actions

### ✅ Completed
1. Waited for 192.168.15.4 boot (after user-initiated reboot)
2. Added `homelab` user to `tape` group for device access
3. Diagnosed Drive 2: All systems healthy
4. Diagnosed Drive 1: Identified root cause (disabled HBA port)
5. Documented solutions for Drive 1 restoration

### 🔄 Pending (Requires Root)
1. Unbind HBA port 0 to restore Drive 1 detection
2. Verify both drives visible: `ls -la /dev/sg*`
3. Run full status check on both drives
4. Validate LTFS mount capability
5. Test Bacula backup operations

---

## Technical Details

### Fibre Channel Configuration
```
Hardware:          QLogic QLE2562 Dual-Port 8Gb FC HBA
Location:          PCI Bus 01, Slot 00, Function 0/1
Topology:          Fibre Channel Arbitrated Loop (FC-AL)

Port 0 (01:00.0):
  - IRQ: 16
  - Status: I/O+, Mem+, BusMaster-
  - Connected to: Drive 1 (HUJ5485716)
  - Issue: BusMaster disabled → device not detected

Port 1 (01:00.1):
  - IRQ: 17
  - Status: I/O+, Mem+, BusMaster+
  - Connected to: Drive 2 (HUJ5485704)
  - Status: ✓ WORKING
```

### User Access
```
Previous State:    homelab user: NOT in tape group
Fix Applied:       usermod -aG tape homelab
New Groups:        tape(26), openmediavault-admin, authentik-users, Grafana, OpenWebUI, Nextcloud
Result:            ✓ Can now access tape devices /dev/sg* and /dev/nst*
```

---

## Recommendations

### Immediate
1. **Restore Drive 1**: Apply Option 1 solution (unbind port 0)
2. **Verify Both**: Run diagnostics on both drives post-fix
3. **Document FC Issues**: Consider disabling problematic port permanently if issues persist

### Long-term
1. Monitor FC port 0 for LIP generation after fix
2. Consider replacing FC HBA if port 0 continues to cause issues
3. Implement automated FC health monitoring
4. Update backup/archival procedures to account for Drive 1 occasional outages

### Related Memory Files
- `/memories/repo/ltfs-fc-instability-2026-04-22.md` - Complete FC LIP diagnostics
- `/memories/repo/lto-tape-knowledge.md` - LTO-6 technical reference
- `/memories/repo/ltfs-tape-recovery.md` - Tape recovery procedures

---

## Summary Table

| Aspect | Drive 1 (sg0) | Drive 2 (sg1) |
|--------|---------------|---------------|
| **Serial** | HUJ5485716 | HUJ5485704 |
| **Model** | HP Ultrium 6-SCSI | HP Ultrium 6-SCSI |
| **Firmware** | J5SW | J5SW |
| **Detection** | ❌ OFFLINE | ✅ ONLINE |
| **Health** | N/A (offline) | ✅ ALL PASS |
| **Tape Alerts** | N/A | 0 (no issues) |
| **HBA Port** | 01:00.0 (BusMaster-) | 01:00.1 (BusMaster+) |
| **Root Cause** | FC port disabled | N/A |
| **Fix Status** | Documented, ready | N/A |

---

**Report Generated**: 2026-04-23  
**System**: 192.168.15.4 (Tape Server)  
**Evaluator**: Infrastructure Agent  
**Next Step**: Apply Drive 1 restoration (requires root access)
