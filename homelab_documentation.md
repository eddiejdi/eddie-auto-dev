# Homelab Server - Documentação Completa

## Informações do Sistema
- **Hostname**: homelab
- **IP**: 192.168.15.2
- **OS**: "Ubuntu 24.04.3 LTS"
- **Uptime**: up 2 days, 15 hours, 6 minutes
- **Memória Total**: 31Gi
- **Espaço em Disco Livre**: 171G
- **Última Atualização**: 2026-01-09T10:20:52.671580

## Serviços Principais

### Ollama (LLM Local)
- **Porta**: 11434
- **URL**: http://192.168.15.2:11434
- **Modelos Disponíveis**:
  - eddie-coder:latest
  - qwen2.5-coder:7b
  - qwen2.5-coder:1.5b
  - nomic-embed-text:latest
  - deepseek-coder-v2:16b
  - codestral:22b
  - github-agent:latest

### Open WebUI
- **Porta**: 3000
- **URL Local**: http://192.168.15.2:3000
- **URL Externa**: https://homelab-tunnel-sparkling-sun-3565.fly.dev
- **Autenticação**: Google OAuth
- **Recursos**:
  - Chat com modelos Ollama
  - Upload de documentos para RAG
  - Histórico de conversas
  - Múltiplos modelos

### External Access / Tunnel

The previous Fly.io-based tunnel has been removed from the project. External
access to homelab services is no longer provided via Fly.io. If you require
public exposure of services, consider one of the supported alternatives:

- Cloudflare Tunnel (`cloudflared`) — recommended for secure, short-lived
  tunnels and zero-trust access.
- Tailscale — peer-to-peer mesh networking for trusted devices.

Local endpoints continue to be available (see Ollama and Open WebUI sections).

## Containers Docker

### open-webui
- **Imagem**: ghcr.io/open-webui/open-webui:main
- **Status**: Up 17 minutes (healthy)
- **Portas**: 0.0.0.0:3000->8080/tcp, [::]:3000->8080/tcp

## Serviços Systemd
- ✅ **ollama**: active
- ✅ **docker**: active

- `/home/homelab/projects`
- `/home/homelab/projects/homelab-scripts`
- `/home/homelab/projects/homelab-scripts/.git`
- `/home/homelab/projects/github-agent`
- `/home/homelab/projects/github-agent/templates`
- `/home/homelab/projects/github-agent/venv`
- `/home/homelab/projects/github-agent/.git`
## Estrutura de Projetos
Note: `flyio-tunnel` project has been removed from the repository and is no
longer present on homelab.
- `/home/homelab/projects/rag-dashboard`
- `/home/homelab/projects/rag-dashboard/.git`
- `/home/homelab/projects/github-mcp-server`
- `/home/homelab/projects/github-mcp-server/config`
- `/home/homelab/projects/github-mcp-server/src`
- `/home/homelab/projects/github-mcp-server/venv`
- `/home/homelab/projects/github-mcp-server/.git`

## Comandos de Gerenciamento

### Ollama
```bash
# Listar modelos
ollama list

# Executar modelo interativo
ollama run eddie-coder

# Testar API
curl http://localhost:11434/api/tags

# Gerar resposta
curl http://localhost:11434/api/generate -d '{"model":"eddie-coder","prompt":"Hello"}'
```

### Docker
```bash
# Ver containers
docker ps

# Logs do Open WebUI
docker logs open-webui --tail 50

# Reiniciar Open WebUI
docker restart open-webui
```

### Fly.io Tunnel
```bash
# Status
~/bin/fly-tunnel status

# Testar endpoints
~/bin/fly-tunnel test

# Ver logs
~/bin/fly-tunnel logs

# Reiniciar
~/bin/fly-tunnel restart
```

## API Endpoints

### Ollama API (Local)
- GET http://192.168.15.2:11434/api/tags - Lista modelos
- POST http://192.168.15.2:11434/api/generate - Gerar texto
- POST http://192.168.15.2:11434/api/chat - Chat completion

### Ollama API (Via Tunnel)
- GET https://homelab-tunnel-sparkling-sun-3565.fly.dev/api/ollama - Status
- POST https://homelab-tunnel-sparkling-sun-3565.fly.dev/api/ollama/api/generate - Gerar texto

## Troubleshooting

### Ollama não responde
```bash
systemctl status ollama
systemctl restart ollama
journalctl -u ollama -f
```

### Open WebUI com erro
```bash
docker logs open-webui
docker restart open-webui
```

### Túnel Fly.io offline
```bash
~/bin/fly-tunnel status
~/.fly/bin/fly machine start <MACHINE_ID> -a homelab-tunnel-sparkling-sun-3565
```

## Contato e Suporte
- Servidor gerenciado por: Eddie
- Localização: Rede local 192.168.15.x
