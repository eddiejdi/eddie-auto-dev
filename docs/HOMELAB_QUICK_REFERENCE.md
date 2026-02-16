# Homelab Quick Reference - Boot & Monitoring

## Physical Console Access

### After Boot
Monitor automatically displays:
1. **btop Dashboard** (CPU, memory, processes)
2. Press `CTRL+Q` to exit
3. **Login Prompt** appears

### Keyboard Shortcuts (btop)
- `q` or `CTRL+C`: Quit
- `M`: Sort by memory
- `P`: Sort by CPU
- `T`: Sort by process time
- ↑/↓: Navigate processes
- `K`: Kill process (requires confirmation)

### USB Console Access
```bash
# If physical keyboard/monitor not available
ssh homelab@192.168.15.2

# View live dashboard logs
sudo journalctl -u btop-boot.service -f

# Check service status
sudo systemctl status btop-boot.service
```

---

## Disk Management

### Check Space
```bash
# Remote check
ssh homelab@192.168.15.2 'df -h /mnt/storage'

# Expected output:
# /dev/mapper/... 456G 136G 301G 32% /mnt/storage
```

### Identify Large Files
```bash
ssh homelab@192.168.15.2 'sudo du -sh /mnt/storage/* | sort -h'

# Top consumers to monitor:
# - /mnt/storage/backups/        (snapshots)
# - /mnt/storage/ollama/         (LLM models)  
# - /mnt/storage/parked/         (stale data - can be removed)
```

### Cleanup Procedures
```bash
# Remove stale parked data
ssh homelab@192.168.15.2 'sudo rm -rf /mnt/storage/parked/*'

# Archive old snapshots (if needed)
# First backup to external storage, then:
ssh homelab@192.168.15.2 'sudo rm -rf /mnt/storage/backups/rpa4all-snapshot-OLDDATE'
```

---

## Service Management

### Boot Dashboard Service
```bash
# Status
sudo systemctl status btop-boot.service

# Restart (if needed)
sudo systemctl restart btop-boot.service

# View logs
sudo journalctl -u btop-boot.service -n 50

# Disable (back to standard getty login)
sudo systemctl disable btop-boot.service
sudo systemctl enable getty@tty1.service
sudo systemctl start getty@tty1.service
```

### Full System Boot
```bash
# Reboot
ssh homelab@192.168.15.2 'sudo reboot'

# Wait ~90 seconds
sleep 90

# Verify boot completed
ssh homelab@192.168.15.2 'uptime'
ssh homelab@192.168.15.2 'sudo systemctl --failed'
ssh homelab@192.168.15.2 'sudo systemctl is-system-running'
```

---

## System Health Checks

### Quick Health Verification
```bash
#!/bin/bash
# Homelab health check script

echo "=== Boot Status ==="
ssh homelab@192.168.15.2 'uptime'

echo "=== Failed Services ==="
ssh homelab@192.168.15.2 'sudo systemctl --failed --no-pager'

echo "=== System State ==="
ssh homelab@192.168.15.2 'sudo systemctl is-system-running'

echo "=== Disk Usage ==="
ssh homelab@192.168.15.2 'df -h / | tail -1'
ssh homelab@192.168.15.2 'df -h /mnt/storage | tail -1'

echo "=== Load Average ==="
ssh homelab@192.168.15.2 'uptime | awk -F"load average:" '"'"'{print $2}'"'"''

echo "=== btop Service ==="
ssh homelab@192.168.15.2 'sudo systemctl status btop-boot.service --no-pager | head -5'
```

---

## SSH Access

### Connection
```bash
# Standard connection
ssh homelab@192.168.15.2

# With port forwarding (if needed)
ssh -L 8080:localhost:8080 homelab@192.168.15.2

# From any machine with SSH key
ssh -i ~/.ssh/id_rsa homelab@192.168.15.2
```

### Credentials
- **User:** homelab
- **Host:** 192.168.15.2
- **Auth:** SSH key-based (no password required)

---

## Related Information

**Last Updated:** 2026-02-16

**Documentation Files:**
- Full details: `docs/HOMELAB_MAINTENANCE_2026-02-16.md`
- Architecture: `docs/ARCHITECTURE.md`
- Operations: `docs/OPERATIONS.md`
- Troubleshooting: `docs/TROUBLESHOOTING.md`

**Key Services:**
- **btop-boot.service:** Monitoring dashboard + login (port: tty1)
- **getty@tty1.service:** Linux console login (managed by wrapper)

**Monitoring Tools Available:**
- `btop` - Enhanced system monitor (default on boot)
- `htop` - Process monitor
- `glances` - Multi-purpose system monitor
- `journalctl` - System logs

---

## Emergency Procedures

### System Unresponsive
```bash
# Try SSH access first
ssh homelab@192.168.15.2 'sudo systemctl is-system-running'

# If timeouts, try reboot
ssh homelab@192.168.15.2 'sudo reboot'

# If no response, hardware power cycle may be needed
```

### Disk Full Emergency
```bash
# Identify largest files
sudo du -sh /mnt/storage/* | sort -hr

# Emergency cleanup (backup first!)
sudo rm -rf /mnt/storage/parked/*

# Check recovery
df -h /mnt/storage
```

### Service Stuck
```bash
# Restart single service
sudo systemctl restart btop-boot.service

# Check status
sudo systemctl status btop-boot.service

# View recent errors
sudo journalctl -u btop-boot.service -e
```

---

## Version History

| Date | Change | Status |
|------|--------|--------|
| 2026-02-16 | Initial setup - btop boot dashboard + disk recovery | ✅ Complete |
| TBD | Monitor threshold alerts | Planned |
| TBD | Automated cleanup policies | Planned |
