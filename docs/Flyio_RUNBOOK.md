# Fly.io Tunnel Runbook (safe deploy)

Purpose: step-by-step, safe instructions to deploy the repository's Fly.io tunnel and verify services. This runbook replaces older Cloudflare instructions.

Prerequisites
- `flyctl` installed and authenticated (token or interactive login).
- Access to the repository directory containing `flyio-tunnel/`.
- Backups of critical secrets (Google OAuth JSON, WireGuard keys) saved to `/home/homelab/backups/`.

Quick deploy (recommended: review before running)

```bash
# (install flyctl if needed)
curl -L https://fly.io/install.sh | sh
export PATH="$HOME/.fly/bin:$PATH"

# authenticate (token or interactive)
~/.fly/bin/flyctl auth login

# run deploy from repo
cd ~/eddie-auto-dev/flyio-tunnel
~/.fly/bin/flyctl deploy

# verify
~/.fly/bin/flyctl apps list
~/.fly/bin/flyctl status -a <APP_NAME>
~/.fly/bin/flyctl logs -a <APP_NAME>
```

Validation checks
- Test HTTP endpoints exposed by the tunnel (replace URL from `fly-tunnel.sh url`):
  - `curl <TUNNEL_URL>/api/ollama`
  - `curl <TUNNEL_URL>/webui/`
- Use helper script: `./fly-tunnel.sh test` (in `flyio-tunnel/`).

Rollback / cleanup
- To remove the app: `~/.fly/bin/flyctl apps destroy <APP_NAME>` (use with caution).

Notes & safety
- This runbook **does not** modify local WireGuard interfaces directly — Fly.io app handles connectivity.
- Keep Google OAuth client secret and `WEBUI_URL` unchanged; restore from `/home/homelab/backups/critical-YYYYMMDD/` if needed.

Files to review in repo
- `flyio-tunnel/fly-tunnel.sh` — helper to start/stop/test the tunnel.
- `flyio-tunnel/fly.toml` — app configuration used by `flyctl deploy`.
- `CRITICAL_FLYIO_TUNNEL.md` — high-level architecture and validation checklist.

If you want, I can:
- (A) Run `~/.fly/bin/flyctl deploy` now (requires auth and your confirmation).
- (B) Produce a systemd unit that runs `fly-tunnel.sh start` on boot (you must confirm desired behavior).
