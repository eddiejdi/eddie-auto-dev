Cloudflare Named Tunnel (persistent)
===================================

Overview
--------
This document explains how to create a persistent Cloudflare "named" Tunnel and deploy it to the homelab host (${HOMELAB_HOST}).

Prerequisites
-------------
- `cloudflared` installed locally (https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation)
- SSH access to the homelab host as `homelab` user (or another user with sudo)
- A Cloudflare account / zone if you plan to use a custom hostname (optional for quick tunnels)

Quick steps
-----------
1. Locally: authenticate `cloudflared login` (opens browser) and create a named tunnel:

```bash
./tools/tunnels/cloudflare_named_setup.sh --name eddie-homelab
```

2. After the script creates the tunnel it will write a sample config `cloudflared-eddie-homelab-config.yml` and print the credentials file path (in `~/.cloudflared`).

3. Copy artifacts to homelab and deploy service (automated):

```bash
./tools/tunnels/deploy_named_tunnel_via_ssh.sh \
  --host ${HOMELAB_HOST} --user homelab \
  --tunnel eddie-homelab \
  --creds ~/.cloudflared/<credentials-file>.json \
  --config ./cloudflared-eddie-homelab-config.yml
```

4. On homelab the unit `cloudflared-named@eddie-homelab.service` will be enabled and started.

Notes and DNS
-------------
- If you want a stable hostname like `webui.example.com` you must add a CNAME/DNS record for that hostname pointing to `yourtunnelid.cfargotunnel.com` or use `cloudflared tunnel route dns` to map a hostname to your tunnel. See Cloudflare docs.
- Keep the credentials file and `/etc/cloudflared/config.yml` secure (root-only).

If you want me to (A) run these steps locally for you or (B) deploy automatically to homelab, provide Cloudflare account access or run `cloudflared login` locally and then tell me where the credentials file is.
