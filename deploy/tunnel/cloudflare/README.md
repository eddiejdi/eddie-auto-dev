Migração para Cloudflare Tunnel (cloudflared)

Este guia descreve passo-a-passo como migrar o túnel do serviço atual para o Cloudflare Tunnel (`cloudflared`). Inclui comandos, configuração de systemd, DNS e verificação.

Pré-requisitos
- Conta Cloudflare com permissão para gerenciar DNS/Cloudflare Tunnel (zonas e contas)
- Acesso SSH ao host que fará o terminador do túnel (homelab ou VM)
- `curl` / `wget` / `sudo`

Instalação (Debian/Ubuntu exemplo)

```bash
# baixar pacote mais recente (amd64)
curl -L -o cloudflared.deb \
  "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb"
sudo dpkg -i cloudflared.deb
sudo mv /usr/local/bin/cloudflared /usr/bin/cloudflared || true
cloudflared --version
```

Autenticar e criar tunnel

```bash
# Abre o browser e autentica sua conta Cloudflare
cloudflared tunnel login

# Cria um túnel nomeado; retorne o TUNNEL_ID
cloudflared tunnel create my-eddie-tunnel

# O comando acima gera um arquivo de credenciais em ~/.cloudflared/
```

Configuração `config.yml` (exemplo)

Coloque o arquivo em `/etc/cloudflared/config.yml` (ou `~/.cloudflared/config.yml` se preferir por usuário):

```yaml
tunnel: <TUNNEL_ID>
credentials-file: /home/<user>/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: eddie.example.com
    service: http://localhost:8501
  - service: http_status:404

# optional: metrics
metrics: 127.0.0.1:8081
```

Registrar serviço systemd (exemplo `/etc/systemd/system/cloudflared-tunnel.service`)

```ini
[Unit]
Description=cloudflared Tunnel for Eddie
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/cloudflared tunnel run --config /etc/cloudflared/config.yml --name my-eddie-tunnel
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Configurar DNS (opções)
- Adicione um CNAME `eddie.example.com` apontando para `<tunnel-name>.cfargotunnel.com` ou configure via Dashboard -> Zero Trust -> Tunnels -> Routes.

Fluxo de migração (resumo)
1. Pare/backup do túnel atual (Fly / outro). Documente configurações e regras de firewall.
2. Instale `cloudflared` no host que ficará como endpoint do túnel.
3. `cloudflared tunnel login` e `cloudflared tunnel create`.
4. Crie `/etc/cloudflared/config.yml` com `ingress` apontando para `localhost` portas dos serviços (p.ex. Streamlit 8501, API 8503).
5. Crie e habilite o unit systemd:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now cloudflared-tunnel.service
   ```
6. Configure DNS (CNAME ou registros via dashboard).
7. Teste acesso externo e validação de headers/health check.
8. Quando estiver estável, retire o túnel antigo.

Verificação e troubleshooting
- Logs: `sudo journalctl -u cloudflared-tunnel -f`
- Estado: `cloudflared tunnel list` e `cloudflared tunnel run --config ...` manualmente para testes.
- Se houver problemas de DNS, aguarde TTL e verifique `dig +short eddie.example.com`.

Segurança
- Proteja credenciais em `/etc/cloudflared` com permissões apropriadas.
- Use regras de firewall para permitir apenas conexões de saída necessárias.

Notas finais
- Este documento serve como referência para migrar serviços que hoje usam uma VM sempre-on (ex: Fly Machine) para um túnel outbound pela Cloudflare, removendo a necessidade de manter uma VM pública dedicada, reduzindo custos contínuos.
