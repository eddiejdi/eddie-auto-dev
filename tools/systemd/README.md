# systemd helpers

`install_env_for_unit.sh` — helper to create `/etc/default/<unit>` from
`tools/simple_vault/secrets/*.gpg` using `tools/simple_vault/export_env.sh`.

Example:

```bash
# generate /etc/default/shared-calendar and restart the service
sudo tools/systemd/install_env_for_unit.sh shared-calendar.service
Systemd unit snippet example (drop-in) to make systemd read the file:

Create `/etc/systemd/system/shared-calendar.service.d/override.conf` with:

[Service]
EnvironmentFile=/etc/default/shared-calendar
Then `systemctl daemon-reload` and `systemctl restart shared-calendar.service`.
