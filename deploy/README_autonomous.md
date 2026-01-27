# Production deployment instructions for Autonomous Remediator

1. Secure the env file

- Copy `production_autonomous.env` to the production host, e.g.:

  scp deploy/production_autonomous.env user@prod:/tmp/
  sudo mv /tmp/production_autonomous.env /etc/autonomous_remediator.env
  sudo chown root:root /etc/autonomous_remediator.env
  sudo chmod 600 /etc/autonomous_remediator.env

2. Edit secrets

- Open `/etc/autonomous_remediator.env` and fill in:
  - `DATABASE_URL` (optional) for DB IPC fallback
  - `TUNNEL_API_TOKEN` (required to run tunnel provider CLI non-interactively)
  - `GITHUB_TOKEN` (if you plan to run the test suite remotely)
  - `AUTONOMOUS_MODE=1` only after you confirm you want the agent to execute actions

3. Enable and reload systemd service

  sudo systemctl daemon-reload
  sudo systemctl restart autonomous_remediator.service
  sudo journalctl -u autonomous_remediator.service -f

  5. Toggle Autonomous Mode safely

  - A helper script is available to flip `AUTONOMOUS_MODE` in the env file with a backup:

    ./tools/toggle_autonomous_mode.sh on|off [--apply] [env-file]

  Examples:

    # Dry-run change (edit /etc file required by admin):
    ./tools/toggle_autonomous_mode.sh on /tmp/autonomous_remediator.env

    # Apply and restart service (requires sudo):
    sudo ./tools/toggle_autonomous_mode.sh on --apply /etc/autonomous_remediator.env

  Use caution enabling `on` — verify `TUNNEL_API_TOKEN` and other secrets are correctly set before applying.

  8. Running CoordinatorAgent locally

  - Quick start (uses project's virtualenv if present):

    ./tools/start_coordinator.sh

  - Or run the service in background and view logs:

    nohup ./tools/start_coordinator.sh > /tmp/coordinator.log 2>&1 &
    tail -f /tmp/coordinator.log

  - A systemd unit file template is available at `systemd/coordinator.service` for production use; copy it to `/etc/systemd/system/` and enable it.

  9. Invoking the Diretor model/agent

  - Use the helper to publish a request to the `DIRETOR` target so the Director model (Open WebUI) or any listener can respond:

    ./tools/invoke_director.py "Por favor, autorize a ativacao do modo autonomo e liste checagens finais."


4. To replicate Open WebUI in production (dry-run first):

  # Dry-run (use your tunnel provider/app name)
  TUNNEL_APP_NAME=homelab-tunnel-sparkling-sun-3565 \
  TUNNEL_API_TOKEN=xxx \
  OAUTH_SESSION_TOKEN_ENCRYPTION_KEY=yyy \
  ./tools/replicate_openwebui_prod.sh

  # Execute for real (use your tunnel provider/app name)
  TUNNEL_APP_NAME=homelab-tunnel-sparkling-sun-3565 \
  TUNNEL_API_TOKEN=xxx \
  OAUTH_SESSION_TOKEN_ENCRYPTION_KEY=yyy \
  ./tools/replicate_openwebui_prod.sh --yes

5. Monitoring and verification

- Watch remediator logs on the prod host:
  sudo journalctl -u autonomous_remediator.service -f
- Check Open WebUI in production after deploy and confirm `/health` returns 200.

6. Rollback

- If the deployment causes issues, rollback via your tunnel provider's release mechanism or restore the previous image from your container registry.
