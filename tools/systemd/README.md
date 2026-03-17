# systemd helpers

`install_env_for_unit.sh` — helper to create `/etc/default/<unit>` from
`tools/simple_vault/secrets/*.gpg` using `tools/simple_vault/export_env.sh`.

`install_specialized_agents_api_secrets.sh` — instala um drop-in para
`specialized-agents-api.service` com `SECRETS_AGENT_URL`,
`SECRETS_AGENT_API_KEY` e `CONUBE_SECRET_NAME`.

Example:

```bash
# generate /etc/default/shared-calendar and restart the service
sudo tools/systemd/install_env_for_unit.sh shared-calendar.service
Systemd unit snippet example (drop-in) to make systemd read the file:

Create `/etc/systemd/system/shared-calendar.service.d/override.conf` with:

[Service]
EnvironmentFile=/etc/default/shared-calendar
Then `systemctl daemon-reload` and `systemctl restart shared-calendar.service`.

Para o agente da Conube via Agent Secrets:

```bash
SECRETS_AGENT_API_KEY=... \
SECRETS_AGENT_URL=http://192.168.15.2:8088 \
CONUBE_SECRET_NAME=conube/rpa4all \
sudo tools/systemd/install_specialized_agents_api_secrets.sh
```
