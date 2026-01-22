
# Fly.io Runbook — DEPRECATED

This runbook previously described how to deploy and manage a Fly.io tunnel for
exposing homelab services to the internet. Fly.io has been removed from this
project: the `flyio-tunnel/` artifacts were deleted and the repository no
longer relies on Fly.io for external access.

If you previously used Fly.io for external exposure, update your operations to
one of the supported alternatives (examples):

- Cloudflare Tunnel (`cloudflared`) — lightweight, recommended for short-lived
  tunnels and zero-trust access.
- Tailscale or Tailscale SSH — peer-to-peer mesh networking when devices are
  reachable and trusted.
- Self-hosted reverse proxy on a public VM (not recommended unless required).

Operational notes:
- All Fly-specific scripts and configuration have been removed from this
  repository. Do not attempt to run `flyctl` or use `fly-tunnel.sh` from this
  repo.
- For validating external access now, prefer the model-server local endpoints
  (Ollama at `http://192.168.15.2:11434`) or set `VALIDATOR_URL` to your
  public tunnel URL before running validator tools.

See `docs/LESSONS_LEARNED_FLYIO_REMOVAL.md` for rationale, risks, and
recommended migration steps.
