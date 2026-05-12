# Nextcloud VPN Setup & Watchdog

**Status:** ✅ Deployed (2026-05-05)  
**Tags:** `nextcloud`, `vpn`, `automation`, `backup`

---

## Overview

Nextcloud agent agora gerencia VPN **on-demand** com detecção de idle automática, ao invés de 24/7.

**Benefício:** Reduz bandwidth e CPU quando não há sync/backup ativo.

---

## Componentes

### 1. VPN Automático

#### Instalação Automática
```bash
curl -s https://path/to/script | sudo bash
```

**O que faz:**
- Download VPN binary (OpenVPN/WireGuard)
- Cria systemd service `vpn@nextcloud`
- Configura credentials via Authentik

#### Ativação
```bash
systemctl start vpn@nextcloud
# Aguarda até estar ready
```

#### Desativação
```bash
systemctl stop vpn@nextcloud
```

---

### 2. Watchdog Idle Detection

**Componente:** `nextcloud-agent/watchdog.py`

#### Lógica
```
→ Monitor network activity em /proc/net/dev
→ Se tráfego = 0 por N minutos
→ Desativa VPN
→ Se tráfego > 0
→ Reativa VPN (lazy start)
```

#### Configuração
```yaml
# nextcloud_agent.yaml
vpn:
  watchdog_idle_timeout: 300  # 5 minutos
  check_interval: 30           # Verificar a cada 30s
  auto_start: true             # Iniciar ao necessário
```

---

### 3. Files API

**Novo:** nextcloud_agent agora expõe `files.upload` e `files.download`

#### Upload
```python
response = nextcloud_agent.files.upload(
    local_path="/data/backup.tar.gz",
    remote_path="/Backups/weekly/",
    verify_checksum=True
)
```

#### Download
```python
response = nextcloud_agent.files.download(
    remote_path="/Shared/document.pdf",
    local_path="/tmp/",
    timeout=600  # 10 minutos
)
```

---

## Cloudflare Bypass

**Problema:** Uploads >30 minutos causavam Cloudflare 524 (timeout)

**Solução:** rclone com `--contimeout=600`

```bash
rclone sync /local/backup remote:Backups/ \
  --contimeout=600 \
  --transfers=1 \
  --bwlimit=5M \
  --checkers=1
```

**Parâmetros:**
- `--contimeout=600` — Timeout de conexão 10 minutos (padrão 60s)
- `--transfers=1` — Upload sequencial (evita limite Cloudflare)
- `--bwlimit=5M` — Limita bandwidth (teste em 5M, ajustar conforme)
- `--checkers=1` — Verificação sequencial

---

## Monitoramento

### Prometheus Metrics
```
nextcloud_vpn_status{host="homelab"} = 1|0  # 1=ativo, 0=inativo
nextcloud_vpn_uptime_seconds{...}
nextcloud_vpn_idle_timeout_seconds{...}
nextcloud_agent_upload_duration_seconds{...}
nextcloud_agent_upload_errors_total{...}
```

### Alertas
```yaml
- name: "Nextcloud VPN Down"
  condition: "nextcloud_vpn_status == 0"
  duration: 5m
  severity: warning

- name: "VPN Watchdog Stuck"
  condition: "increase(nextcloud_vpn_toggle_errors[1h]) > 5"
  severity: critical
```

---

## Troubleshooting

| Sintoma | Causa | Fix |
|---------|-------|-----|
| VPN não ativa | watchdog disabled | `systemctl start nextcloud-vpn-watchdog` |
| Upload muito lento | bandwidth limit | Aumentar `--bwlimit` |
| Cloudflare 524 | contimeout insuficiente | Aumentar para 900s |
| Watchdog não desativa | idle detection bug | Checar `/proc/net/dev` manualmente |

---

## Próximos Passos

- [ ] Validar watchdog em produção por 48h
- [ ] Testar cenário de Cloudflare rate limit
- [ ] Implementar retry automático em falha
- [ ] Adicionar metrics de checksum verification

---

**Última atualização:** 2026-05-05  
**Mantido por:** nextcloud_agent, wiki_agent  
**Docs relacionadas:** Nextcloud Agent, Backup Strategy
