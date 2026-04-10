# GitHub Actions Runner Recovery - 10 Apr 2026

## Problem

GitHub Actions runners on homelab were **offline** and unable to connect to GitHub, with errors:
```
Runner connect error: The HTTP request timed out after 00:01:40
```

## Root Cause

**NordVPN kill-switch on homelab was blocking ALL outbound traffic to GitHub's IP range** (140.82.112.0/20).

When DNS resolved `api.github.com` to 140.82.112.5, the connection would timeout because:
- NordVPN kill-switch was active (default security mode)
- No exception/allowlist configured for GitHub
- All traffic outside the VPN tunnel was blocked

## Solution Applied

Added GitHub to NordVPN allowlist to permit port 443 outbound (HTTPS):

```bash
# Connected via SSH to homelab
nordvpn allowlist add port 443
nordvpn allowlist add subnet 140.82.112.0/20
```

This allows:
- Port 443 connections (HTTPS) to bypass the VPN tunnel's kill-switch
- Direct communication with GitHub API and Actions broker endpoints
- Runner services can now reach `broker.actions.githubusercontent.com:443`

## Verification

- ✅ `curl https://api.github.com` — now connects
- ✅ `curl -I https://broker.actions.githubusercontent.com` — HTTP/2 404 (expected)
- ✅ GitHub API shows runner "homelab" as **ONLINE**
- ✅ Runner logs show `√ Connected to GitHub` and `Listening for Jobs`

## Runner Status After Fix

### eddie-auto-dev repo:
- **Runner "homelab" (id 22):** ✅ ONLINE (currently busy)
- Runner "eddie" (id 21): ❌ OFFLINE (ghost runner, can be deleted)
- Runner "nas-lto6" (id 23): ❌ OFFLINE (inactive)

### estou-aqui repo:
- **Runner "homelab-estou-aqui" (id 21):** ✅ ONLINE

## Files Modified

- No code files modified
- NordVPN configuration changed on homelab directly (not in git)

## Impact

- GitHub Actions workflows can now execute on the homelab runner
- Self-hosted runner is operational and can pick up jobs from both repositories
- No architecture changes required
- No impact on existing VPN routing rules

## Cleanup (Optional)

If the ghost runner "eddie" (id 21) in eddie-auto-dev is not needed:
```bash
gh api repos/eddiejdi/eddie-auto-dev/actions/runners/21 -X DELETE
```
