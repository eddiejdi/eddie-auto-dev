**LocalTunnel — Túnel público gratuito (instruções rápidas)**

- **Requisitos:** `node` + `npm` (ou `npx`).
- **Instalação (opcional):** `npm install -g localtunnel` ou use `npx localtunnel` sem instalar.

1. Dê permissão de execução ao script:

   chmod +x tools/tunnels/start_localtunnel.sh

2. Inicie o túnel (exemplo para Open WebUI na porta 3000):

   ./tools/tunnels/start_localtunnel.sh --port 3000 --subdomain meu-tunel-eddie

3. O script tentará capturar a URL pública retornada pelo LocalTunnel e gravá-la em:

   `tools/simple_vault/secrets/public_tunnel_url.txt`

4. Notas importantes:
- O subdomínio é opcional e pode já estar em uso — se estiver, omita `--subdomain`.
- LocalTunnel é adequado para demos e uso pessoal; para produção considere soluções com controle de acesso.
- Este repositório salva a URL no cofre local (`tools/simple_vault/secrets`) para uso por scripts locais.

5. Alternativas:
- `ngrok` (exige conta para recursos avançados)
- `cloudflared` (Cloudflare Tunnel) — exige conta Cloudflare
