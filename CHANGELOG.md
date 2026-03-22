# Changelog

## 2026-03-22

- Added NAS/LTO monitoring assets for `OMV + LTO-6`, including Grafana dashboard, LTFS flush metrics, NAS tape metrics, and local AI assessment panel.
- Adjusted Prometheus and Grafana alerting to remove stale targets, stop alerting on `Nextcloud` `noData`, and treat `FC abort` as a recent-event signal instead of a historical sticky counter.
- Recorded field lessons from the `LTO-6` recovery: `single-path` FC remained stable for LTFS writes, dual-path caused reservation conflicts during failover, and buffer-first disk staging remains the correct operating model.
- Documented the operational cleanup that resolved alert noise on `homelab`: stale swap image removal, large conversation database moved to `/mnt/raid1`, and obsolete snap revisions removed.
