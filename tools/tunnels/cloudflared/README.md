Cloudflare Tunnel (cloudflared) - setup rápido
=============================================

Objetivo: expor serviços do homelab (ex.: `${HOMELAB_HOST}:8503`) sob um subdomínio seu (ex.: `homelab.rpa4all.com`) via Cloudflare Tunnel, sem mexer no roteador.

Pré-requisitos:
- Conta Cloudflare com o domínio adicionado (você precisará delegar nameservers para o Cloudflare).
- `cloudflared` instalado no homelab.

Passos resumidos:

1) No Cloudflare
   - Adicione o domínio (se ainda não estiver).
   - Na seção "Zero Trust / Access / Tunnels" crie um novo Tunnel.
   - Baixe o arquivo `credentials` (ou copie o `tunnel secret`), ou execute `cloudflared tunnel login` no host para autenticar.

2) No homelab (${HOMELAB_HOST})
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
         service: http://${HOMELAB_HOST}:8503
       - service: http_status:404
     ```
   - Registre a rota DNS no Cloudflare (via UI: adicionar CNAME que aponta para `tunnel.cloudflare.com` conforme instruções do painel para esse tunnel). Normalmente o painel cria a entrada automaticamente ao mapear um `hostname` para o tunnel.

3) Executar como serviço systemd
   - Use o unit file `cloudflared.service` e coloque `config.yml` no `/etc/cloudflared`.
   - Habilite e inicie:
     ```bash
     sudo systemctl enable --now cloudflared@homelab-tunnel.service
     ```

Se quiser, eu posso:
- Gerar o `config.yml` final (substituindo `<TUNNEL-UUID>`) se você me fornecer o Tunnel ID/credentials path.
- Gerar e enviar um comando pronto para atualizar o `PUBLIC_TUNNEL_URL` como secret do GitHub (precisa de permissão/`--apply`).

Exemplo de ação rápida (no homelab):

```bash
# autenticar
cloudflared tunnel login
# criar tunnel (nome exemplo)
cloudflared tunnel create homelab-tunnel
# listar para obter UUID
cloudflared tunnel list
# mapear DNS (no Cloudflare painel ou usar o comando abaixo)
cloudflared tunnel route dns <TUNNEL-UUID> homelab.rpa4all.com
# copiar exemplo e ajustar
sudo mkdir -p /etc/cloudflared
sudo cp tools/tunnels/cloudflared/config.homelab.yml.example /etc/cloudflared/config.yml
# ajustar /etc/cloudflared/config.yml: substituir <TUNNEL-UUID> e o caminho do credentials-file
# mover credenciais (exemplo)
sudo mv ~/.cloudflared/<TUNNEL-UUID>.json /etc/cloudflared/
sudo chown root:root /etc/cloudflared/<TUNNEL-UUID>.json
# habilitar o serviço
sudo cp tools/tunnels/cloudflared/cloudflared.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared@homelab-tunnel.service
Se quiser que eu gere o `config.yml` já preenchido (para você transferir ao host) envie o `TUNNEL-UUID` ou confirme que quer que eu gere um comando pronto para executar no homelab.

Observações:
- Se não quiser delegar nameservers do domínio inteiro para Cloudflare, crie apenas um subdomínio e faça um CNAME apontando para o hostname que o Cloudflare fornecer (consulte o painel Cloudflare -> Tunnels -> Routes para instruções de CNAME).
- Alternativa sem mudar DNS: usar Fly.io ou um túnel público (ngrok/localtunnel), mas mapping para seu próprio domínio requer configurações/pagamento.

Se quiser, eu crio os arquivos de serviço e um exemplo de `config.yml` neste repositório para você ajustar. Quer que eu adicione esses arquivos agora? 
