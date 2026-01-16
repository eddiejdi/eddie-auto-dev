# 🌐 Multi-Environment Fly.io Tunnels

## Arquitetura

```
                    ┌─────────────────────────────────────────────────────┐
                    │                      INTERNET                        │
                    └─────────────────────────────────────────────────────┘
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    │                       │                       │
                    ▼                       ▼                       ▼
        ┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
        │   PROD (Fly.io)   │   │   HOM (Fly.io)    │   │   CER (Fly.io)    │
        │  homelab-tunnel-  │   │  homelab-tunnel-  │   │  homelab-tunnel-  │
        │  sparkling-sun-   │   │      hom          │   │      cer          │
        │     3565          │   │                   │   │                   │
        │ Portas: 8081-8085 │   │ Portas: 8091-8095 │   │ Portas: 8101-8105 │
        └─────────┬─────────┘   └─────────┬─────────┘   └─────────┬─────────┘
                  │                       │                       │
                  └───────────────────────┼───────────────────────┘
                                          │
                                    WireGuard (fly0)
                                          │
                                          ▼
                    ┌─────────────────────────────────────────────────────┐
                    │              HOMELAB (192.168.15.2)                   │
                    │                                                       │
                    │   ipv6-proxy.py                                       │
                    │   ┌─────────────────────────────────────────────┐     │
                    │   │ PROD       HOM        CER                   │     │
                    │   │ 8081 ─┬─  8091 ─┬─  8101 ─┬─> 3000 WebUI   │     │
                    │   │ 8082 ─┤   8092 ─┤   8102 ─┤─> 11434 Ollama │     │
                    │   │ 8083 ─┤   8093 ─┤   8103 ─┤─> 8001 RAG API │     │
                    │   │ 8084 ─┤   8094 ─┤   8104 ─┤─> 8501 RAG Dash│     │
                    │   │ 8085 ─┘   8095 ─┘   8105 ─┘─> 8502 GitHub  │     │
                    │   └─────────────────────────────────────────────┘     │
                    └─────────────────────────────────────────────────────┘
```

## URLs dos Ambientes

| Ambiente | URL Pública | Portas Proxy |
|----------|-------------|--------------|
| **PROD** | https://homelab-tunnel-sparkling-sun-3565.fly.dev | 8081-8085 |
| **HOM** | https://homelab-tunnel-hom.fly.dev | 8091-8095 |
| **CER** | https://homelab-tunnel-cer.fly.dev | 8101-8105 |

## Mapeamento de Portas

Cada ambiente usa um range de 5 portas consecutivas:

| Offset | Serviço | Porta Local |
|--------|---------|-------------|
| +0 | Open WebUI | 3000 |
| +1 | Ollama | 11434 |
| +2 | RAG API | 8001 |
| +3 | RAG Dashboard | 8501 |
| +4 | GitHub Agent | 8502 |

## Comandos de Deploy

```bash
# Setup completo
./setup_multi_env.sh

# Deploy individual
cd HOM && fly deploy
cd CER && fly deploy

# Verificar status
fly status --app homelab-tunnel-hom
fly status --app homelab-tunnel-cer
```

## Configuração de OAuth (Opcional)

Para ter login Google separado em cada ambiente:

1. **Google Cloud Console** -> APIs & Services -> Credentials
2. Adicionar Redirect URIs:
   - `https://homelab-tunnel-hom.fly.dev/oauth/google/callback`
   - `https://homelab-tunnel-cer.fly.dev/oauth/google/callback`
3. Criar containers Open WebUI separados (opcional)

## ⚠️ Importante

- **MESMO SERVIDOR**: Todos os ambientes apontam para 192.168.15.2
- **SEPARAÇÃO POR GIT**: A diferença entre ambientes é o branch deployado
- **SERVIÇOS COMPARTILHADOS**: Ollama, RAG, etc são compartilhados

## Troubleshooting

```bash
# Verificar ipv6-proxy
ssh homelab@192.168.15.2 "systemctl status ipv6-proxy"
ssh homelab@192.168.15.2 "journalctl -u ipv6-proxy -f"

# Testar portas
curl http://192.168.15.2:8091  # HOM WebUI
curl http://192.168.15.2:8101  # CER WebUI

# Verificar WireGuard
ssh homelab@192.168.15.2 "sudo wg show fly0"
```
