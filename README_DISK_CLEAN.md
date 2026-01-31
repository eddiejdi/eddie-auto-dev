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

Telegram notifications:
- The script will attempt to send a summary to Telegram when `/etc/eddie/telegram.env` exists and contains `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
- Ensure `/etc/eddie/telegram.env` is readable by root (it is read as root when run by the service). If you get `{"ok":false,"error_code":404,"description":"Not Found"}` the bot token or chat id is invalid; test manually with:

  sudo bash -c 'source /etc/eddie/telegram.env && curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" -d chat_id="${TELEGRAM_CHAT_ID}" -d text="test message"'

- Notifications are optional; if you prefer no notifications, remove or restrict `/etc/eddie/telegram.env`.

## 🔐 Managing secrets (Vault)

This project stores sensitive values encrypted in the local repository vault: `tools/simple_vault/secrets/` (this directory is ignored by git). Use the helper scripts to add and deploy secrets safely.

Save a secret (example: Telegram bot token):

  printf '%s' '<token>' | tools/simple_vault/add_secret.sh telegram_bot_token

Decrypt and deploy to the homelab (example):

  tools/simple_vault/decrypt_secret.sh tools/simple_vault/secrets/telegram_bot_token.gpg | sudo tee /etc/eddie/telegram.env >/dev/null
  sudo chown root:root /etc/eddie/telegram.env && sudo chmod 600 /etc/eddie/telegram.env

See `docs/SECRETS.md` for full guidance and best practices.
