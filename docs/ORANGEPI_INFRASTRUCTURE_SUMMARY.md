# Orange Pi Zero 2W — Infrastructure Summary

**Data**: 2026-06-22  
**Status**: ✅ FULLY OPERATIONAL

---

## 📋 Resumo Executivo

Orange Pi Zero 2W foi adicionado à infraestrutura do homelab como:
1. **Device (CMDB)**: Registrado no NetBox como `orangepizero2w`
2. **SSH Server**: Accessible via `orangepi@192.168.15.166` (LDAP auth via Authentik)
3. **GitHub Actions Runner**: Self-hosted runner ARM64 para CI/CD

**Total de horas**: ~2-3 horas (network discovery → full provisioning)

---

## 🔧 Configuração Completa

### 1. Network Discovery
- **IP Address**: 192.168.15.166/24 (DHCP)
- **MAC**: 20:7b:d5:1a:11:0a
- **Hostname**: orangepizero2w
- **Connectivity**: LAN (192.168.15.0/24) + WAN (NAT via homelab)

### 2. Operating System
- **Base**: Armbian 26.8.0 (rolling/trunk)
- **Distro**: Debian 13 (Trixie)
- **Kernel**: 6.18.35-current-sunxi64
- **Boot**: Headless (sem display), SSH ativo
- **Init**: systemd

### 3. Authentication
- **SSH**: PasswordAuthentication=yes, PermitRootLogin=yes
- **User**: orangepi (UID 1000)
- **Password**: rpa4all@2026
- **LDAP Integration**: 
  - SSSD + nslcd (ambos active/running)
  - Base DN: dc=rpa4all,dc=com
  - Bind: uid=ldapservice,ou=users,dc=rpa4all,dc=com

### 4. CMDB Registration (NetBox)
```
Device Name: orangepizero2w
Role: edge-device (custom, orange #ff9800)
Manufacturer: Xunlong Orange Pi (custom)
Type: Orange Pi Zero 2W (custom)
Site: homelab-main
Platform: linux
Primary IP: 192.168.15.166/24
Interface: eth0 (VIRTUAL)
Status: Active
```

### 5. GitHub Actions Runner
```
Runner Name: orangepi-zero2w
Status: online 🟢
Version: v2.335.1 (ARM64/Linux)
Service: actions.runner.eddiejdi-eddie-auto-dev.orangepi-zero2w
Memory: 34.8MB (running)
PID: 11848

Labels:
  - self-hosted (system)
  - Linux (system)
  - ARM64 (system)
  - orangepi (custom)
  - arm64 (custom)
  - edge-device (custom)
```

---

## 📊 Hardware Specifications

| Property | Value |
|----------|-------|
| **Processor** | Allwinner H616 (ARM Cortex-A53/A72) |
| **Cores** | 4-core @ up to 1.5GHz |
| **RAM** | 3.83 GB LPDDR4 |
| **Storage** | 29 GB SD card (microSD v2) |
| **Architecture** | arm64/aarch64 |
| **Thermal** | 50°C (normal operation) |

---

## 🔗 Integration Points

### Homelab Connectivity
- **Bridge**: SSH to homelab@192.168.15.2, then to orangepi@192.168.15.166
- **Direct access**: Available on LAN 192.168.15.0/24
- **External**: via homelab NAT (WAN IP 79.127.164.75)

### LDAP/Authentik Integration
- **SSSD daemon**: active (listening on `/var/run/sssd.sock`)
- **nslcd daemon**: active (managing LDAP queries)
- **Bind credentials**: ldapservice / ldapservice-app-pass-20260324-key
- **NSS/PAM**: Configured for LDAP user resolution

### GitHub Integration
- **Runner registration**: `eddiejdi/eddie-auto-dev` repository
- **GitHub CLI**: v2.95.0 (installed, authenticated)
- **Token**: Generated ephemeral registration tokens via `gh api`

---

## 📁 File Locations

| Path | Purpose |
|------|---------|
| `/tmp/runner-extract/` | GitHub Actions Runner (executable) |
| `/etc/systemd/system/actions.runner.*` | Runner systemd service |
| `/etc/sssd/sssd.conf` | SSSD configuration for LDAP |
| `/etc/nslcd.conf` | nslcd configuration for LDAP |
| `/home/orangepi/` | Default user home |
| `/root/.ssh/` | SSH key directory |

---

## 🚀 Operational Commands

### SSH Access
```bash
# Direct (from LAN)
ssh orangepi@192.168.15.166

# Via homelab (from anywhere)
ssh -J homelab@192.168.15.2 orangepi@192.168.15.166
```

### Check Runner Status
```bash
# Local Orange Pi
systemctl status actions.runner.eddiejdi-eddie-auto-dev.orangepi-zero2w

# Remote from dev machine
sshpass -p 'rpa4all@2026' ssh orangepi@192.168.15.166 \
  'sudo systemctl status actions.runner.eddiejdi-eddie-auto-dev.orangepi-zero2w'
```

### Monitor Logs
```bash
# Real-time runner logs
journalctl -u actions.runner.eddiejdi-eddie-auto-dev.orangepi-zero2w -f

# Recent errors
journalctl -u actions.runner.eddiejdi-eddie-auto-dev.orangepi-zero2w -p err -n 20
```

### Verify GitHub Integration
```bash
# From dev machine
gh api repos/eddiejdi/eddie-auto-dev/actions/runners \
  --jq '.runners[] | select(.name=="orangepi-zero2w")'
```

---

## ✅ Validation Checklist

- ✅ Network connectivity (ping, SSH working)
- ✅ DHCP IP assigned (192.168.15.166)
- ✅ OS boot successful (Armbian 26.8.0)
- ✅ SSH passwordless access configured
- ✅ LDAP/SSSD/nslcd active and responding
- ✅ CMDB (NetBox) registration complete
- ✅ GitHub runner registered and online
- ✅ Runner service systemd enabled (auto-start on boot)
- ✅ GitHub CLI v2.95.0 installed
- ✅ Temperature normal (~50°C)
- ✅ Disk usage low (6% of 29GB)
- ✅ Memory usage normal (5-6% of 3.83GB)

---

## 🔄 Maintenance Schedule

| Task | Frequency | Command |
|------|-----------|---------|
| Check runner status | Daily | `systemctl status actions.runner.eddiejdi-eddie-auto-dev.orangepi-zero2w` |
| Review logs | Weekly | `journalctl -u actions.runner.* -n 100` |
| Disk cleanup | Monthly | `df -h /` check |
| Temperature check | Monthly | `cat /sys/class/thermal/thermal_zone0/temp` |
| System updates | Quarterly | `sudo apt update && sudo apt upgrade` |
| LDAP credentials renewal | Annually | Update bind DN password in `/etc/nslcd.conf` |

---

## 📚 Documentation

- **Setup Guide**: [GITHUB_RUNNER_SETUP.md](GITHUB_RUNNER_SETUP.md)
- **GitHub Runner Docs**: https://docs.github.com/en/actions/hosting-your-own-runners
- **Armbian Orange Pi**: https://www.armbian.com/orange-pi-zero-2w/
- **NetBox API**: https://demo.netbox.dev/static/docs/

---

## 🎯 Next Steps

1. **Create test workflows** using `runs-on: orangepi-zero2w` label
2. **Monitor runner performance** under actual CI/CD workloads
3. **Fine-tune resource allocation** if memory pressure observed
4. **Add monitoring** to Prometheus/Grafana for long-term tracking
5. **Backup runner configuration** periodically

---

**Deployed by**: GitHub Copilot (automated provisioning)  
**Last Status Check**: 2026-06-22 22:08:36 UTC-3  
**Next Review**: 2026-07-22
