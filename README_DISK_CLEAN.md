# Disk Clean Agent

Purpose: safe, configurable disk cleanup script with dry-run and report modes.

Usage:
- Run a non-destructive report: `sudo /usr/local/bin/disk_clean.sh --report-only`
- Dry-run showing planned changes: `sudo /usr/local/bin/disk_clean.sh` (default dry-run)
- Execute cleanup (destructive): `sudo /usr/local/bin/disk_clean.sh --execute --apt --journal --tmp-days 7 --include-docker`

Installation on homelab (done): files copied to `/usr/local/bin/disk_clean.sh`, units in `/etc/systemd/system/` and logrotate in `/etc/logrotate.d/disk-clean`.

Scheduling:
- There is a provided timer `disk-clean.timer` (OnCalendar=weekly) which is **not enabled by default**. To enable scheduled destructive runs, run:

  sudo systemctl enable --now disk-clean.timer

Important:
- Always review the dry-run (`--report-only`) before enabling scheduled `--execute` runs, as `apt autoremove` and `docker system prune -a --volumes` can remove packages and images.
