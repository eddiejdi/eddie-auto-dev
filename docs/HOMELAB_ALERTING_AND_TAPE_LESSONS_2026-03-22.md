# Homelab Alerting And Tape Lessons 2026-03-22

## Scope

This note captures what changed operationally on `2026-03-22` while restoring tape writes, cleaning alert noise, and reducing disk pressure on `homelab`.

## What Was Corrected

- `Grafana` alerting stopped paging on stale or non-actionable signals.
- The `NAS OMV + LTO` dashboard gained real tape and buffer observability.
- A local assessment agent using `Ollama` now summarizes drive and NAS health into an HTML panel.
- Root disk pressure on `homelab` was reduced enough to clear active storage alerts.

## Monitoring Lessons

### Nextcloud health

- `Nextcloud` public endpoint alerts were firing because the rule treated `noData` as failure.
- The public site was healthy while the metric series `nextcloud_probe_up` was absent.
- Operational rule: a missing probe series is not the same as a service outage.
- Corrective action: `noDataState` and `execErrState` for those rules were moved to `OK`.

### NAS exporter health

- `NAS Node Exporter Down` became sticky even when `up{job="nas-node-exporter"} = 1`.
- The alert should not stay critical only because the evaluator temporarily had no fresh sample.
- Corrective action: `noDataState` and `execErrState` were moved to `OK`.

### Fibre Channel alerts

- Alerting on the raw `24h` abort count made the warning effectively permanent after a single incident cluster.
- Operationally, the actionable question is whether aborts are still happening now.
- Corrective action: the alert was changed to compare the current `24h` counter with its `1h offset`, which approximates "new aborts in the last hour".

### Trading targets

- `Prometheus Target Down` was still watching obsolete jobs:
  - `autocoinbot-exporter`
  - `conube-exporter`
- The live exporters were already `crypto-exporter-btc_usdt_aggressive` on `9095` and `crypto-exporter-btc_usdt_conservative` on `9094`.
- Corrective action: dead jobs were removed from scrape and alert expressions.

### Disk thresholds

- With the host role growing, `75%` for root warning became too noisy.
- `85%` remains the meaningful critical threshold.
- Corrective action: root warning now starts at `80%`.

## Tape Lessons

### Single path vs dual path

- `LTFS` format and mount could succeed under dual-path FC.
- Real writes later failed with transport disruption and reservation conflicts.
- The stable production behavior came only after forcing `single-path`.
- Operational rule: for this host and drive, use `single-path` for production writes until dual-path is revalidated in a separate maintenance window.

### Buffer-first is correct

- Directly treating tape like a normal low-latency filesystem increases operational risk.
- The working model is:
  - write to disk cache first
  - expose the logical mount from cache
  - let the controlled flush move data to tape
- This model kept the `Nextcloud` backup safe even while FC and LTFS were being repaired.

### Monitoring the tape path

- The useful metrics for day-2 operations were:
  - `nas_ltfs_mount_up`
  - `nas_ltfs_read_only`
  - `nas_ltfs_write_timeout_events_24h`
  - `nas_fc_abort_events_24h`
  - tape used/available bytes
  - buffer occupancy and flush throughput
- The AI assessment panel is only a summary layer; the Prometheus metrics remain the source of truth.

## Disk Hygiene Lessons

- A stale `/swap.img` of `32G` existed while the real configured swap was `/swapfile`.
- Removing the orphaned swap image was low-risk and recovered significant root capacity.
- A large operational database was also moved off root:
  - from `/home/homelab/eddie-auto-dev/agent_data/interceptor_data/conversations.db`
  - to `/mnt/raid1/eddie-auto-dev-agent-data/conversations.db`
  - with a symlink left in place
- Old disabled `snap` revisions were also removed.

## Result

Final operating state after remediation:
- root filesystem dropped to roughly `77%`
- active Grafana alert queue dropped to `0`
- tape path remained usable in `single-path`
- Nextcloud stayed publicly available through `Cloudflare`

## Files That Became Operational Sources Of Truth

- `monitoring/prometheus.yml`
- `monitoring/grafana/provisioning/alerting/rules.yml`
- `grafana/dashboards/nas-rpa4all-omv.json`
- `tools/homelab/ltfs_cache_flush.py`
- `tools/homelab/nas_ai_assessor.py`
- `tools/nas/export_lto6_metrics.sh`
- `docs/NAS_OMV_LTO_ARCHITECTURE.md`
- `docs/LTO6_FC_TROUBLESHOOTING_RUNBOOK.md`
