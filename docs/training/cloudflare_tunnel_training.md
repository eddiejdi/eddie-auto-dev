# Treinamento: Cloudflare Tunnel (cloudflared)

Objetivo: capacitar operadores e desenvolvedores para migrar e operar túneis com `cloudflared`.

Sumário do curso
- Visão geral do Cloudflare Tunnel
- Instalação e autenticação
- Configuração: `config.yml`, ingress rules
- Deploy como serviço (systemd)
- Rotinas de verificação e troubleshooting
- Laboratório prático: migrar serviço Streamlit e API

Exercício prático (lab)
1. Requisitos: máquina Linux com acesso root e DNS para teste.
2. Instale `cloudflared` (ver `deploy/tunnel/cloudflare/README.md`).
3. Execute `cloudflared tunnel login` e registre o túnel.
4. Crie `/etc/cloudflared/config.yml` apontando `eddie.example.com` para `https://heights-treasure-auto-phones.trycloudflare.com`.
5. Habilite e inicie o service systemd.
6. Teste externamente: `curl -I https://eddie.example.com`.

Checklist de aceitação
- Túnel autenticado e `cloudflared` em versão suportada.
- Registro DNS apontando para o túnel (CNAME ou via Dashboard configurado).
- Serviço acessível externamente por hostname configurado.
- Logs do systemd sem erros contínuos 24h após cutover.

Troubleshooting rápido
- `sudo journalctl -u cloudflared-tunnel -f`
- `cloudflared tunnel list`
- Verificar permissões de `/etc/cloudflared` e arquivos de credenciais

Material adicional
- Link de referência: https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/
