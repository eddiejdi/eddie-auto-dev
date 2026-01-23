Cloudflare Tunnel — Guia para Confluence

Use este conteúdo para criar uma página no Confluence. Copie/cole o texto abaixo em uma nova página e ajuste imagens/diagrama conforme necessário.

Resumo

Este documento descreve a migração do túnel atual (VM sempre-on) para o Cloudflare Tunnel (`cloudflared`). O objetivo é reduzir custos e melhorar segurança usando conexões outbound para a rede Cloudflare.

Passos de migração

1. Planejamento
   - Inventariar serviços que usam o túnel atual (ports, hosts, health checks).
   - Definir janela de migração e fallback.

2. Preparação do host
   - Instalar `cloudflared`.
   - Garantir acesso para `cloudflared tunnel login`.

3. Criar e configurar o túnel
   - `cloudflared tunnel create <NAME>`
   - Criar `/etc/cloudflared/config.yml` com regras `ingress`.

4. Deploy e cutover
   - Habilitar unit systemd.
   - Atualizar DNS para apontar para o novo hostname (CNAME ou via Dashboard).
   - Testar e validar.

5. Pós-migração
   - Remover tunneis antigos e ajustar automações de deploy.
   - Atualizar runbooks e playbooks de incidentes.

Anexos técnicos
- Exemplo de `config.yml` e systemd: ver arquivo `deploy/tunnel/cloudflare/README.md` no repositório.
- Diagrama da solução: anexar `docs/diagrams/cloudflare_tunnel.drawio`.

Checklist para Confluence
- [ ] Página criada e linkada no espaço de Operações
- [ ] Passos de rollback documentados
- [ ] Owners e contatos adicionados
