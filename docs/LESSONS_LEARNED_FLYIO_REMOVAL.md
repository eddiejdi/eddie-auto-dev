# Lessons Learned — Removing Fly.io Tunnel

Summary
- The Fly.io tunnel (`flyio-tunnel/`) was removed from the repository.
- Reasons: ongoing cost, operational complexity, rollout fragility, and better
  alternatives (Cloudflare Tunnel / Tailscale) for the project's needs.

What went wrong / risks observed
- Cost unpredictability: Fly.io's non-free tiers and egress/storage can accrue.
- Operational complexity: WireGuard, Caddy reverse-proxy, and Fly machines
  added several points of failure and maintenance burden.
- Secrets exposure risk: deployment required careful secret handling (OAuth
  credentials, WireGuard keys) — automation increased risk of accidental leaks.
- Testing gap: not enough automated E2E tests guarding tunnel changes before
  deploy.

What we learned
- Prefer providers that minimize running VM footprint for occasional public
  exposure; Cloudflare Tunnel or Tailscale often suffice.
- Keep public exposure orthogonal to core app logic — services should be
  reachable locally for dev/test and the tunnel managed separately.
- Automate safety: make scripts idempotent, dry-run by default, and require
  explicit confirmations or env flags to perform destructive actions.
- Document rollback and provide health checks as first-class artifacts.

Actions taken
- Removed `flyio-tunnel/` artifacts and disabled Fly-specific scripts.
- Updated runbooks and homelab docs to indicate removal and alternatives.
- Added `VALIDATOR_URL`-aware behavior to validation tools to avoid hardcoded
  Fly URLs.

Recommendations
- For external exposure, prefer `cloudflared` (Cloudflare Tunnel) for most
  users; only use full VM-based proxies if you need specific control or
  geographical hosting.
- Add CI checks that detect public-tunnel changes and require manual review.
- Rotate secrets and audit access (Bitwarden / simple_vault) after removal.

Contact
- If you want, I can: (A) fully remove the empty `flyio-tunnel/` directory, (B)
  implement a Cloudflare Tunnel installer and systemd unit, or (C) prepare a PR
  with the changes to merge.
