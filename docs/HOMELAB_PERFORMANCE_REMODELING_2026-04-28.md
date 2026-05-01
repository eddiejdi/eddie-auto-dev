# Homelab Performance Remodeling - 2026-04-28

## Objective

Increase resilience and throughput of the converged `homelab` host (`192.168.15.2`) without breaking the current security model:

- proxy remains the default outbound path
- VPN remains part of the protection plane
- direct egress is treated as an exception
- critical infra must not compete equally with kiosk, desktop, and AI/UI workloads

## Current Architecture Findings

The host is heavily converged. It runs, on the same node:

- edge services: `nginx`, `cloudflared`, `squid`, `dnsmasq`, `dnsproxy`, `ssh`
- security services: `Authentik`, VPN daemons, DNS
- observability: `Prometheus`, `Grafana`, exporters
- application stack: `Nextcloud`, `OpenWebUI`, `Wiki.js`, mail, Home Assistant
- AI workloads: `ollama`, `llm-optimizer`, trading agents
- local UX stack: kiosk, remote XFCE, WebKit-based dashboards

This design works, but only if priority and resource isolation are explicit.

## Root Causes Identified

### 1. Proxy path was manually forced on the notebook

The notebook had hard-coded proxy settings in shell and desktop environment, which made every download go through `192.168.15.2:3128`.

### 2. Squid was under-dimensioned

Original `squid` profile:

- `workers 1`
- `1024` open files
- no resource priority
- no explicit separation from non-critical workloads

### 3. Critical infra shared CPU with heavy workloads

High load sources observed on the host:

- `ollama` runners
- WebKit kiosk/dashboard processes
- multiple long-running agents/exporters
- database and monitoring workloads

### 4. System health was noisy

`nas-ai-assessor.service` was failing because it referenced a missing script:

- `/home/homelab/eddie-auto-dev/tools/homelab/nas_ai_assessor.py`

## Changes Applied

### Notebook

- removed hard-coded proxy exports from:
  - `~/.profile`
  - `~/.config/environment.d/90-network-proxy.conf`
- set GNOME proxy mode to `auto`
- kept PAC/WPAD discovery via:
  - `http://192.168.15.2/wpad.dat`

### Squid on `homelab`

Updated `/etc/squid/squid.conf`:

- removed obsolete `dns_v4_first`
- set `workers 4`
- set `max_filedescriptors 65535`
- kept `cache deny all` because the dominant traffic is HTTPS `CONNECT`
- preserved LAN-only access model

Added systemd resource override:

- `/etc/systemd/system/squid.service.d/override-resources.conf`
  - `LimitNOFILE=65535`
  - `TasksMax=8192`

### Critical service prioritization

Added high-priority overrides for:

- `squid`
- `nginx`
- `cloudflared-rpa4all`
- `homelab-lan-dhcp`
- `dnsproxy-doh`
- `ssh`

Policy applied:

- reserved CPU affinity near the system cores
- high `CPUWeight`
- negative `Nice`
- reduced `OOMScoreAdjust`

### Non-critical UI demotion

Added low-priority overrides for:

- `kiosk-dashboard`
- `workstation-xfce`
- `homelab-dashboard`
- `btop-boot`
- `cpu-monitor`

Policy applied:

- CPU affinity moved away from critical cores
- low `CPUWeight`
- positive `Nice`
- idle I/O scheduling

### System health cleanup

Disabled broken timer:

- `nas-ai-assessor.timer`

Reset failed state for the missing script service.

## Validation

### Squid

Validated after restart:

- active with `4` workers
- `Max open files = 65535`
- listener backlog increased

### Service priority

Validated live:

- critical services gained high scheduling priority
- kiosk/workstation services gained low scheduling priority

### Proxy throughput

The proxy no longer fails due to trivial sizing issues.
External route quality is still a factor, but the proxy is no longer the first bottleneck.

## Remaining Structural Recommendations

### Short term

1. Keep PAC/WPAD as the default desktop path.
2. Use explicit CLI wrappers for PAC-aware tools instead of global static proxy exports.
3. Keep direct egress only for audited exceptions.

### Medium term

1. Move kiosk and remote desktop UX to a separate node or VM.
2. Move AI inference workloads to a compute-focused node or dedicated slice.
3. Bind internal-only databases and APIs to loopback unless exposure is required.
4. Add Docker resource policies for high-memory/high-CPU containers.

### Long term

Split the homelab into at least three operational planes:

1. Edge/Security Plane
   - `nginx`, `cloudflared`, `squid`, DNS, DHCP, VPN, Auth
2. Application/Data Plane
   - `Nextcloud`, mail, Wiki.js, storage APIs, databases
3. Compute/UI Plane
   - `ollama`, dashboards, kiosk, remote workstation, non-critical AI agents

This is the cleanest path to improve both security posture and performance predictability.

## Operational Conclusion

The best-performance architecture for this environment is not "no proxy".
It is:

- proxy automatic by policy
- proxy sized correctly
- critical infra protected by scheduler priority
- non-critical UX and AI workloads prevented from starving edge services
- exceptions handled explicitly, not by globally bypassing the protection stack
