# NO_PROXY

## Propósito
Lista de domínios/IPs que devem fazer bypass do proxy HTTP/HTTPS Squid (192.168.15.2:3128).

## Escopo
- **Arquivo de configuração**: `~/.config/homelab/proxy.sh`
- **Ativação**: `source ~/.config/homelab/proxy.sh && homelab_proxy_on`
- **Padrão**: Desativado (direto/PAC)

## Conteúdo
- Loopback e redes locais: `localhost,127.0.0.0/8,::1,192.168.0.0/16,10.0.0.0/8,172.16.0.0/12`
- Cloudflare (Tunnel, Access): `*.cloudflare.com,*.cloudflaretunnel.net`
- ChatGPT/OpenAI: `chatgpt.com,*.chatgpt.com,openai.com,*.openai.com,oaiusercontent.com`
- RPA4All interno: `*.rpa4all.com,ssh.rpa4all.com`
- Dev tools (instalar Windsurf, extensões VS Code, etc):
  - `marketplace.visualstudio.com` (VS Code extensions)
  - `snapcraft.io,*.snapcraft.io` (Snap store)
  - `flathub.org,*.flathub.org,dl.flathub.org` (Flatpak store)
  - `codeium.com,*.codeium.com,api.codeium.com,dl.codeium.com` (Codeium AI)
  - `github.com,*.github.com,githubusercontent.com,*.githubusercontent.com` (GitHub)

## Motivo técnico
Proxy Squid de saída (ProtonVPN) bloqueia alguns servidores de repositório (Snap, Flatpak, Codeium, VS Code Marketplace). 
Adicionar domínios ao NO_PROXY permite acesso direto LAN→internet sem passar pela VPN.

## Relacionadas
- [[HTTP_PROXY]], [[HTTPS_PROXY]], [[http_proxy]], [[https_proxy]]
- Função `homelab_proxy_on()` / `homelab_proxy_off()` em `~/.config/homelab/proxy.sh`
