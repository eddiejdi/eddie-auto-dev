Guia rápido: Expor Open WebUI (SSH + Nginx)

Resumo
-----
Objetivo: expor o Open WebUI que roda no homelab (192.168.15.2:3000) para a Internet e permitir que `https://rpa4al.com` embeda via iframe.

Arquitetura recomendada
----------------------
1) Homelab (192.168.15.2): roda Open WebUI em localhost:3000. Executa um systemd unit que cria um túnel SSH reverso para o servidor público (mapeia public:127.0.0.1:13300 → homelab:127.0.0.1:3000).
2) Public server (público com DNS): Nginx serve `openwebui.rpa4al.com` e proxy_pass para `http://127.0.0.1:13300/`. TLS via certbot.

Passos (detalhados)
-------------------
1) No homelab (execute como usuário homelab):
   - Copie `site/deploy/setup_homelab_tunnel_local.sh` para o homelab e execute:
     sudo bash setup_homelab_tunnel_local.sh deploy@rpa4al.com
   - O script:
     * Gera (se necessário) chave SSH em ~/.ssh/id_ed25519
     * Copia a chave pública para o servidor público com ssh-copy-id
     * Cria /etc/systemd/system/openwebui-ssh-tunnel.service e habilita o serviço
   - Confira: sudo systemctl status openwebui-ssh-tunnel

2) No servidor público:
   - Copie `site/deploy/openwebui-nginx.conf` para /etc/nginx/sites-available/openwebui.conf e altere server_name para `openwebui.rpa4al.com`.
   - Ative a configuração: sudo ln -s /etc/nginx/sites-available/openwebui.conf /etc/nginx/sites-enabled/
   - Teste e recarregue: sudo nginx -t && sudo systemctl reload nginx
   - Obtenha TLS: sudo certbot --nginx -d openwebui.rpa4al.com

3) Verificação:
   - No public server: curl -I https://openwebui.rpa4al.com/ (deve retornar 200 e cabeçalhos sem `X-Frame-Options: DENY` e com CSP `frame-ancestors` adequado).
   - No site server: atualize `site/openwebui-config.json` com "https://openwebui.rpa4al.com/" e recarregue a aba "Open WebUI".

Notas de segurança
------------------
- O túnel SSH usa chaves sem passphrase para reinício automático. Proteja a chave privada (permissões corretas) e considere usar sessões restritas no servidor remoto.
- O Nginx remove `X-Frame-Options` e define CSP com `frame-ancestors` somente para os domínios permitidos.

Dicas e troubleshooting
----------------------
- Se o túnel falhar: veja `journalctl -u openwebui-ssh-tunnel -n 200` no homelab.
- No public server, verifique se o processo sshd permite port-forwarding (PermitOpen/AllowTcpForwarding).
- Se usar um provedor com NAT, preferir Cloudflare Tunnel (veja site/deploy/cloudflared_tunnel.md).
