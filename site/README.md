Eddie — Site de Currículo (rpa4al.com)

Arquivos:
- `index.html` — Página principal com navegação por abas e embed do Open WebUI em `/openwebui/`.
- `styles.css` — Estilos modernos e responsivos.
- `script.js` — Lógica de navegação por abas e lazy-load do iframe.

Deploy recomendado (Nginx)
--------------------------
A forma mais direta para permitir o embed do Open WebUI é configurar um proxy reverso que exponha o app em `/openwebui/` no mesmo domínio, ou definir `site/openwebui-config.json` com a URL pública do seu servidor Open WebUI (ex.: `https://openwebui.rpa4al.com/`).

Exemplo de snippet Nginx (proxy local para `localhost:3000`):

```
server {
  listen 80;
  server_name rpa4al.com;

  root /var/www/rpa4al/site; # ajustar conforme caminho
  index index.html;

  location / {
    try_files $uri $uri/ =404;
  }

  # Proxy para OpenWebUI (porta 3000)
  location /openwebui/ {
    proxy_pass http://127.0.0.1:3000/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_hide_header X-Frame-Options; # remover header que pode bloquear iframe
    add_header X-Frame-Options "SAMEORIGIN" always;
  }
}
```

Observações e alternativas:
- Se você já tem um servidor público do Open WebUI, coloque a URL em `site/openwebui-config.json` (ex.: `{"openwebui_url":"https://openwebui.rpa4al.com/"}`). O site usará essa URL preferencialmente.
- Se você prefere o proxy local, mantenha a rota `/openwebui/` apontando para `localhost:3000` no Nginx; o site tentará usar `/openwebui/` como fallback.
- Se o Open WebUI servir `X-Frame-Options: DENY`, o proxy precisa remover/alterar esse header.

Próximos passos que posso fazer por você:
- Atualizar `openwebui-config.json` com a URL do seu servidor público, ou gerar o `deploy.sh` (Nginx + systemd) e abrir PR com tudo configurado.
- Testar a integração se você me fornecer the URL do servidor ou instruções de acesso.

Expose Open WebUI externally
---------------------------
Recommended approaches to expose the Open WebUI running on your homelab (192.168.15.2):

1) SSH reverse tunnel (recommended if you control a public server)
   - On homelab create an SSH reverse tunnel to the public server and run `systemd` unit (`site/deploy/openwebui-ssh-tunnel.service`).
   - On the public server run the Nginx config `site/deploy/openwebui-nginx.conf` (create a DNS CNAME `openwebui.rpa4al.com` to point here).
   - This approach is simple, requires only SSH and Nginx, and works even with NAT.

2) Cloudflare Tunnel (cloudflared)
   - Use `cloudflared` on the homelab to create a tunnel and map the hostname `openwebui.rpa4al.com` to `http://127.0.0.1:3000` on the homelab.
   - See `site/deploy/cloudflared_tunnel.md` for the config and notes.

Security & embedding notes
- The proxy must remove `X-Frame-Options` (or set an allow list) and set a `Content-Security-Policy` with `frame-ancestors` that allows embedding from your main domain (`https://rpa4al.com`). Example header added in the Nginx snippet.
- Use TLS (Let's Encrypt) on the public server and force HTTPS to avoid mixed-content issues when embedding.

Testing
- After deploy: curl -I https://openwebui.rpa4al.com/ and check `Content-Security-Policy` and `X-Frame-Options` headers.
- On the site server, ensure `site/openwebui-config.json` points to `https://openwebui.rpa4al.com/` then open the site and check the iframe loads.
