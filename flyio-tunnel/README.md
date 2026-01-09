# Fly.io Tunnel 🚀

Túnel seguro para expor serviços do homelab na internet via Fly.io.
**Este é o caminho oficial para acesso externo aos serviços do homelab.**

## URL de Acesso

🌐 **https://homelab-tunnel-sparkling-sun-3565.fly.dev**

## Arquitetura

```
Internet → Fly.io (Edge GRU/São Paulo) → Proxy Caddy → Homelab (192.168.15.2)
                     ↓
         https://homelab-tunnel-sparkling-sun-3565.fly.dev
```

## Serviços Expostos

| Serviço | Porta Local | URL Fly.io |
|---------|-------------|------------|
| Health Check | - | /health |
| Ollama API (OpenAI) | 11434 | /v1/* |
| Ollama API (Native) | 11434 | /api/ollama/* |
| RAG Dashboard | 8501 | /rag/* |
| GitHub Agent | 8502 | /github/* |
| Open WebUI | 3000 | /webui/* |

## Exemplos de Uso

### Ollama (OpenAI Compatible)
```bash
# Listar modelos
curl https://homelab-tunnel-sparkling-sun-3565.fly.dev/v1/models

# Chat completion
curl https://homelab-tunnel-sparkling-sun-3565.fly.dev/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen2.5-coder:7b", "messages": [{"role": "user", "content": "Hello"}]}'
```

### Open WebUI (Aplicativo Mobile)
Configure no app Open WebUI:
- **URL**: `https://homelab-tunnel-sparkling-sun-3565.fly.dev`
- O app se conectará automaticamente ao Ollama via `/v1/*`

## Gerenciamento

### Verificar Status
```bash
/home/homelab/.fly/bin/fly status -a homelab-tunnel-sparkling-sun-3565
```

### Iniciar Máquina (se parada)
```bash
/home/homelab/.fly/bin/fly machine start <MACHINE_ID> -a homelab-tunnel-sparkling-sun-3565
```

### Ver Logs
```bash
/home/homelab/.fly/bin/fly logs -a homelab-tunnel-sparkling-sun-3565
```

### Reiniciar
```bash
/home/homelab/.fly/bin/fly apps restart homelab-tunnel-sparkling-sun-3565
```

## Configuração do App

- **App Name**: homelab-tunnel-sparkling-sun-3565
- **Região**: GRU (São Paulo)
- **Memória**: 256MB
- **CPU**: Shared 1x
- **Auto-stop**: Desabilitado (sempre ativo)

## Importante

⚠️ **Cloudflared foi removido** - Não use mais túneis temporários do Cloudflare.
O Fly.io é o único ponto de entrada externo autorizado.

## Instalação (já feito)

### 1. Fly CLI instalado em
```
/home/homelab/.fly/bin/fly
```

### 2. Arquivos de configuração
```
/home/homelab/projects/flyio-tunnel/
├── Caddyfile      # Configuração do proxy reverso
├── Dockerfile     # Imagem com Caddy
├── fly.toml       # Configuração do Fly.io
└── README.md      # Esta documentação
```

## Troubleshooting

### Máquina suspensa/parada
O Fly.io pode suspender a máquina após inatividade. Para reativar:
```bash
# Ver status
/home/homelab/.fly/bin/fly status -a homelab-tunnel-sparkling-sun-3565

# Iniciar (pegue o MACHINE_ID do status)
/home/homelab/.fly/bin/fly machine start <MACHINE_ID> -a homelab-tunnel-sparkling-sun-3565
```

### Erro 502/504
Verifique se os serviços locais estão rodando:
```bash
# Ollama
systemctl status ollama

# Open WebUI
docker ps | grep open-webui
```

### Logs de erro
```bash
/home/homelab/.fly/bin/fly logs -a homelab-tunnel-sparkling-sun-3565
```

## Licença

MIT
