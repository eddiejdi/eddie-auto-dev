Alternative: Use Cloudflare Tunnel (cloudflared)

If you use Cloudflare, cloudflared can expose the homelab Open WebUI securely without opening ports on your home network.

Homelab side (run on 192.168.15.2):
1. Install cloudflared and authenticate with your Cloudflare account.
2. Create a named tunnel:
   cloudflared tunnel create openwebui
3. Configure `config.yml` for the tunnel (example):

   tunnel: <TUNNEL_ID>
   credentials-file: /root/.cloudflared/<TUNNEL_ID>.json
   ingress:
     - hostname: openwebui.rpa4al.com
       service: http://127.0.0.1:3000
     - service: http_status:404

4. Run as a service: `sudo cloudflared service install` (it will create a systemd unit).

Public config (Cloudflare DNS):
- Create a CNAME (or the tunnel integration will add route) `openwebui` -> managed by Cloudflare.

Notes:
- This avoids needing to configure an SSH tunnel; Cloudflare handles TLS and exposure.
- Ensure you adjust headers or use the Cloudflare dashboard Worker to rewrite/remove `X-Frame-Options` header if needed.
- You can still run Nginx in front of the domain to add a CSP header limiting frame-ancestors if you want to force embedding only on rpa4al.com.
