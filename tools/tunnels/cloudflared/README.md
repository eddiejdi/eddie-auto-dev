Cloudflare Tunnel (cloudflared) - setup rápido
=============================================

Objetivo: expor serviços do homelab (ex.: `192.168.15.2:8503`) sob um subdomínio seu (ex.: `homelab.rpa4all.com`) via Cloudflare Tunnel, sem mexer no roteador.

Pré-requisitos:
- Conta Cloudflare com o domínio adicionado (você precisará delegar nameservers para o Cloudflare).
- `cloudflared` instalado no homelab.

Passos resumidos:

1) No Cloudflare
   - Adicione o domínio (se ainda não estiver).
   - Na seção "Zero Trust / Access / Tunnels" crie um novo Tunnel.
   - Baixe o arquivo `credentials` (ou copie o `tunnel secret`), ou execute `cloudflared tunnel login` no host para autenticar.

2) No homelab (192.168.15.2)
   - Instale `cloudflared`:
     ```bash
     # Debian/Ubuntu example
     curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
     sudo dpkg -i cloudflared.deb
     ```
   - Autentique e crie tunnel (ex.):
     ```bash
     cloudflared tunnel login
     cloudflared tunnel create homelab-tunnel
     ```
   - Crie um arquivo de configuração `config.yml` (ex.: `/etc/cloudflared/config.yml`) com ingress rules apontando para seu serviço:
     ```yaml
     tunnel: <TUNNEL-UUID>
     credentials-file: /home/<user>/.cloudflared/<TUNNEL-UUID>.json
     ingress:
       - hostname: homelab.rpa4all.com
         service: http://192.168.15.2:8503
       - service: http_status:404
     ```
   - Registre a rota DNS no Cloudflare (via UI: adicionar CNAME que aponta para `tunnel.cloudflare.com` conforme instruções do painel para esse tunnel). Normalmente o painel cria a entrada automaticamente ao mapear um `hostname` para o tunnel.

3) Executar como serviço systemd
   - Use o unit file `cloudflared.service` e coloque `config.yml` no `/etc/cloudflared`.
   - Habilite e inicie:
     ```bash
     sudo systemctl enable --now cloudflared@homelab-tunnel.service
     ```

Observações:
- Se não quiser delegar nameservers do domínio inteiro para Cloudflare, crie apenas um subdomínio e faça um CNAME apontando para o hostname que o Cloudflare fornecer (consulte o painel Cloudflare -> Tunnels -> Routes para instruções de CNAME).
- Alternativa sem mudar DNS: usar Fly.io ou um túnel público (ngrok/localtunnel), mas mapping para seu próprio domínio requer configurações/pagamento.

Se quiser, eu crio os arquivos de serviço e um exemplo de `config.yml` neste repositório para você ajustar. Quer que eu adicione esses arquivos agora? 
