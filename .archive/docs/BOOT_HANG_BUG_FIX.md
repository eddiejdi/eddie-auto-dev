# Boot Hanging Bug — Review Service Fix
**Date:** 2026-02-14  
**Issue:** Boot taking excessive time, systemd hanging at multi-user.target  
**Root Cause:** `review-service.service` unable to start → infinite restart loop → blocking boot chain  

---

## Problem Analysis

### Symptoms
- Boot appears to hang/freeze after ~10-15s
- `systemd-analyze time` shows 48.5s boot time (expected after firmware tuning)
- `systemctl is-system-running` eventually returns "running" but with delay
- `systemd-analyze critical-chain` shows `graphical.target` waiting for `review-service.service`

### Root Cause
```
Boot Chain:
graphical.target 
  → review-service.service (FAILING)
    → specialized-agents-api.service 
      → network.target
```

When `review-service.service` fails to start:
1. It enters `auto-restart` loop (RestartSec=10)
2. Each restart attempt fails immediately
3. systemd waits for service to stabilize before continuing critical chain
4. Result: Boot appears hung for 30-60+ seconds while systemd retries

### Error Message
```
ModuleNotFoundError: No module named 'paramiko'
File "/home/homelab/eddie-auto-dev/specialized_agents/remote_orchestrator.py", line 14, in <module>
    import paramiko
```

### Why Did This Happen?
The `review-service.service` unit file used `/usr/bin/python3` (system Python) but:
- `paramiko` was only installed in the **virtualenv** at `/home/homelab/eddie-auto-dev/.venv`
- System Python didn't have access to venv packages
- Service failed on first import, never recovered until fixed

---

## Solution Applied

### Change Made
```diff
- ExecStart=/usr/bin/python3 /home/homelab/eddie-auto-dev/specialized_agents/review_service.py
+ ExecStart=/home/homelab/eddie-auto-dev/.venv/bin/python3 /home/homelab/eddie-auto-dev/specialized_agents/review_service.py
```

### Why This Works
- `/home/homelab/eddie-auto-dev/.venv/bin/python3` is the **venv Python interpreter**
- It has access to all packages installed in the virtualenv (paramiko, cryptography, etc.)
- Service now starts successfully on first attempt
- No infinite restart loop
- Boot completes normally

### Impact
- **Before:** Boot hung until systemd timeout (~30-60s) due to review-service restart loop
- **After:** Boot completes at normal speed (~48s), all services start successfully
- **Restart chain:** No longer critical path blocker

---

## Installation

On the homelab server (192.168.15.2):

```bash
# 1. Apply the corrected service file
sudo cp /home/homelab/eddie-auto-dev/tools/systemd/review-service.service \
       /etc/systemd/system/review-service.service

# 2. Reload systemd configuration
sudo systemctl daemon-reload

# 3. Restart the service
sudo systemctl restart review-service.service

# 4. Verify it's running
systemctl status review-service.service

# 5. Optional: Reboot to verify full boot flow
sudo systemctl reboot
```

### Drop-in Override
If you prefer to keep the current `/etc/systemd/system/review-service.service` and override just the ExecStart:

```bash
mkdir -p /etc/systemd/system/review-service.service.d/

cat > /etc/systemd/system/review-service.service.d/override-execstart.conf << 'EOF'
[Service]
ExecStart=
ExecStart=/home/homelab/eddie-auto-dev/.venv/bin/python3 /home/homelab/eddie-auto-dev/specialized_agents/review_service.py
EOF

sudo systemctl daemon-reload
sudo systemctl restart review-service.service
```

---

## Verification

### Boot Time Should Return to Normal
```bash
ssh homelab@192.168.15.2 systemd-analyze time
# Expected: ~48s (same as firmware-only optimization baseline)

systemd-analyze critical-chain
# Expected: graphical.target depends on cloudflared@dev, NOT review-service
```

### Service Should Start Successfully
```bash
systemctl status review-service.service
# Expected: Active: active (running)
# No error messages in logs
```

### Logs Should Be Clean
```bash
journalctl -u review-service.service -n 20
# Expected: No "ModuleNotFoundError" entries
# Only normal startup logs
```

---

## Lessons Learned

1. ✅ **Always use virtualenv Python in systemd units** — Never hardcode `/usr/bin/python3` if dependencies are in venv
2. ✅ **Monitor boot hang issues** — Check `systemd-analyze critical-chain` for service failures in boot path
3. ✅ **Restart loops block boot** — A service with `Restart=always` can inadvertently delay entire boot if in critical chain
4. ✅ **Use drop-in `.d/` directories** — For system service overrides to avoid tracking in git

---

## Related Files
- [tools/systemd/review-service.service](../tools/systemd/review-service.service) — Corrected template
- [BOOT_OPTIMIZATION.md](../BOOT_OPTIMIZATION.md) — Boot performance tuning (firmware/loader focus)
- Issue/PR: (link to issue if available)
