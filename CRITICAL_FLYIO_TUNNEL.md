# 🚨 DOCUMENTAÇÃO CRÍTICA - Túnel Fly.io + Open WebUI OAuth

> ⚠️ **ATENÇÃO**: Este fluxo é **CRÍTICO** e **NÃO DEVE SER MODIFICADO** sem justificativa forte e aprovação explícita.
> 
> **Última atualização funcionando**: 2026-01-13
> **Responsável**: Eddie
> **Backup criado em**: `/home/homelab/backups/critical-20260113/`

---

## 📋 Resumo do Sistema

Este documento descreve a configuração completa do túnel Fly.io que permite acesso externo ao homelab, incluindo:
- **Open WebUI** com autenticação Google OAuth
- **Ollama** para LLMs
- Serviços RAG e dashboards

---

## 🔐 Credenciais Críticas (NÃO ALTERAR)

### Google OAuth
| Campo | Valor |
|-------|-------|
| **Client ID** | `<VER_BACKUP_LOCAL>` |
| **Client Secret** | `<VER_BACKUP_LOCAL>` |
| **Project ID** | `home-lab-483803` |
| **Redirect URI** | `https://homelab-tunnel-sparkling-sun-3565.fly.dev/oauth/google/callback` |

> ⚠️ Se o Client Secret for regenerado no Google Cloud Console, o login OAuth **QUEBRARÁ IMEDIATAMENTE**.

### URLs Públicas
| Ambiente | URL | Portas Proxy |
|----------|-----|--------------|
| **PROD** | https://homelab-tunnel-sparkling-sun-3565.fly.dev | 8081-8085 |
| **HOM** | https://homelab-tunnel-hom.fly.dev | 8091-8095 |
| **CER** | https://homelab-tunnel-cer.fly.dev | 8101-8105 |
| **Região** | GRU (São Paulo) | - |

---

## 🏗️ Arquitetura

```
Internet
    │
    ▼
┌─────────────────────────────────────┐
│  Fly.io Apps                        │
│  PROD: homelab-tunnel-sparkling-... │
│  HOM:  homelab-tunnel-hom           │
│  CER:  homelab-tunnel-cer           │
│  Caddy Proxy + WireGuard            │
│  IPv6: fdaa:3b:60e0:a7b:8cfe:...    │
└──────────────┬──────────────────────┘
               │ WireGuard (fly0)
               ▼
┌─────────────────────────────────────┐
│  Homelab (192.168.15.2)             │
│  IPv6 Proxy (ipv6-proxy.py)         │
│  ┌─────────────────────────────────┐│
│  │ PROD (8081-8085)                ││
│  │ Porta 8081 → localhost:3000    ││ ← Open WebUI
│  │ Porta 8082 → localhost:11434   ││ ← Ollama
│  │ Porta 8083 → localhost:8001    ││ ← RAG API
│  │ Porta 8084 → https://heights-treasure-auto-phones.trycloudflare.com    ││ ← RAG Dashboard
│  │ Porta 8085 → localhost:8502    ││ ← GitHub Agent
│  │                                 ││
│  │ HOM (8091-8095) - mesmo mapea- ││
│  │ CER (8101-8105)   mento local  ││
│  └─────────────────────────────────┘│
└─────────────────────────────────────┘
```

---

## 🐳 Container Open WebUI

### Comando de Criação (EXATO)
```bash
docker run -d --name open-webui \
  --restart unless-stopped \
  -p 3000:8080 \
  -v open-webui:/app/backend/data \
  -e OLLAMA_BASE_URL=http://192.168.15.2:11434 \
  -e WEBUI_URL=https://homelab-tunnel-sparkling-sun-3565.fly.dev \
  -e WEBUI_AUTH=true \
  -e ENABLE_LOGIN_FORM=true \
  -e ENABLE_SIGNUP=true \
  -e ENABLE_OAUTH_SIGNUP=true \
  -e GOOGLE_CLIENT_ID=<VER_BACKUP_LOCAL> \
  -e GOOGLE_CLIENT_SECRET=<VER_BACKUP_LOCAL> \
  -e OAUTH_MERGE_ACCOUNTS_BY_EMAIL=true \
  -e ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION=false \
  -e RAG_EMBEDDING_ENGINE=ollama \
  -e RAG_EMBEDDING_MODEL=nomic-embed-text \
  ghcr.io/open-webui/open-webui:main
```

### Variáveis Críticas
| Variável | Valor | Motivo |
|----------|-------|--------|
| `WEBUI_URL` | URL do Fly.io | Necessário para OAuth redirect funcionar |
| `GOOGLE_CLIENT_SECRET` | Secret atual | Deve coincidir com Google Cloud Console |
| `RAG_EMBEDDING_ENGINE` | `ollama` | Evita timeout baixando modelos do HuggingFace |
| `RAG_EMBEDDING_MODEL` | `nomic-embed-text` | Modelo local no Ollama |

---

## 🔧 Serviços Systemd

### ipv6-proxy.service
```ini
[Unit]
Description=IPv6-to-IPv4 Proxy for Fly.io Private Network
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 -u /home/homelab/ipv6-proxy.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Script**: `/home/homelab/ipv6-proxy.py`
- Escuta em IPv6 (`fdaa:3b:60e0:a7b:8cfe:0:a:202`) e IPv4 (`0.0.0.0`)
- Roteia conexões para serviços locais

---

## 🌐 WireGuard (fly0)

### Configuração `/etc/wireguard/fly0.conf`
```ini
[Interface]
PrivateKey = <PRIVATE_KEY>
Address = fdaa:3b:60e0:a7b:8cfe:0:a:202/120
DNS = fdaa:3b:60e0::3

[Peer]
PublicKey = <FLY_PUBLIC_KEY>
AllowedIPs = fdaa:3b:60e0::/48
Endpoint = <FLY_GATEWAY>:51820
PersistentKeepalive = 15
```

### Comandos Úteis
```bash
# Status do WireGuard
sudo wg show

# Verificar tráfego bidirecional (DEVE mostrar bytes enviados E recebidos)
sudo wg show fly0

# Reiniciar interface
sudo wg-quick down fly0 && sudo wg-quick up fly0
```

---

## 🔍 Troubleshooting

### Problema: OAuth retorna "email or password incorrect"
**Causa**: Client Secret no Google Cloud Console foi regenerado.
**Solução**:
1. Acessar https://console.cloud.google.com/apis/credentials
2. Baixar novo JSON de credenciais
3. Atualizar `GOOGLE_CLIENT_SECRET` no container
4. Recriar container com comando acima

### Problema: Container "unhealthy"
**Causa**: Tentando baixar modelos do HuggingFace (timeout).
**Solução**: Garantir `RAG_EMBEDDING_ENGINE=ollama`

### Problema: Túnel não conecta
**Verificar**:
```bash
# WireGuard deve mostrar tráfego bidirecional
sudo wg show fly0

# IPv6 proxy deve estar rodando
systemctl status ipv6-proxy

# Container deve estar healthy
docker ps | grep open-webui
```

---

## 📁 Backup

### Localização
```
/home/homelab/backups/critical-20260113/
├── docker-containers.txt      # Lista de containers
├── docker-volumes.txt         # Volumes Docker
├── ipv6-proxy.py              # Script do proxy
├── ipv6-proxy.service         # Unit systemd
├── open-webui-env.txt         # Variáveis de ambiente
├── open-webui-inspect.json    # Configuração completa do container
├── wireguard-fly0.conf        # Configuração WireGuard
└── wireguard-status.txt       # Status no momento do backup
```

### Restaurar Container
```bash
# 1. Parar e remover container atual
docker stop open-webui && docker rm open-webui

# 2. Recriar com comando documentado acima

# 3. Verificar health
docker ps | grep open-webui
```

---

## ❌ O QUE NÃO FAZER

1. **NÃO regenerar Client Secret** no Google Cloud Console sem necessidade
2. **NÃO alterar** `WEBUI_URL` - OAuth depende dela
3. **NÃO remover** o volume `open-webui` sem backup dos dados
4. **NÃO alterar** configuração do WireGuard sem testar primeiro
5. **NÃO desabilitar** o serviço `ipv6-proxy`
6. **NÃO usar** `RAG_EMBEDDING_ENGINE` diferente de `ollama` (causa timeout)

---

## ✅ Checklist de Validação

Após qualquer manutenção, verificar:

- [ ] `docker ps | grep open-webui` mostra `(healthy)`
- [ ] `sudo wg show fly0` mostra bytes recebidos E enviados
- [ ] `systemctl status ipv6-proxy` mostra `active (running)`
- [ ] https://homelab-tunnel-sparkling-sun-3565.fly.dev carrega
- [ ] Login com Google funciona

---

## 📞 Contato

Se precisar modificar este sistema, documente:
1. **Motivo** da alteração
2. **Backup** antes da mudança
3. **Teste** após a mudança
4. **Rollback** se necessário

---

**Documento criado em**: 2026-01-13  
**Versão**: 1.0  
**Status**: ✅ FUNCIONANDO
