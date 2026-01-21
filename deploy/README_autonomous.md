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
  - `FLY_API_TOKEN` (required to run `flyctl` non-interactively)
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

  Use caution enabling `on` — verify `FLY_API_TOKEN` and other secrets are correctly set before applying.

4. To replicate Open WebUI in production (dry-run first):

  # Dry-run
  FLY_APP_PROD=homelab-tunnel-sparkling-sun-3565 \
  FLY_API_TOKEN=xxx \
  OAUTH_SESSION_TOKEN_ENCRYPTION_KEY=yyy \
  ./tools/replicate_openwebui_prod.sh

  # Execute for real
  FLY_APP_PROD=homelab-tunnel-sparkling-sun-3565 \
  FLY_API_TOKEN=xxx \
  OAUTH_SESSION_TOKEN_ENCRYPTION_KEY=yyy \
  ./tools/replicate_openwebui_prod.sh --yes

5. Monitoring and verification

- Watch remediator logs on the prod host:
  sudo journalctl -u autonomous_remediator.service -f
- Check Open WebUI in production after deploy and confirm `/health` returns 200.

6. Rollback

- If the deployment causes issues, you can rollback via Fly's releases or restore previous image.
