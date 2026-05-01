# DR Checklist - Homelab RPA4All

**Objetivo:** checklist operacional para restauracao do homelab apos reboot inesperado, perda de rede, falha de servicos ou incidente de publicacao.

**Host principal:** `homelab`  
**LAN:** `192.168.15.2`  
**SSH local:** `ssh homelab@192.168.15.2`  
**SSH fallback:** `ssh -o ProxyCommand='cloudflared access ssh --hostname %h' homelab@ssh.rpa4all.com`

**Fontes consolidadas para este runbook:**
- `docs/SERVER_CONFIG.md`
- `docs/HOMELAB_QUICK_REFERENCE.md`
- `docs/HOMELAB_NETWORK_RECOVERY_2026-04-15.md`
- `docs/OPERATIONAL_STATUS_2026-04-15.md`
- `docs/EDDIE_CENTRAL_OPERATIONS_GUIDE.md`
- `docs/WHATSAPP_BOT_AUDIT_AND_OPERATIONS.md`
- `docs/LTFS_CRASH_SELFHEAL_SYSTEM.md`
- `docs/MONITORING_SETUP.md`
- `docs/WIKI_IMPORT_INSTRUCTIONS.md`
- `docs/WIKI_PUBLICATION_CHECKLIST.md`
- inventario real de `systemd`, `docker`, portas e endpoints do servidor em `2026-04-28`

## 1. Regra de Ouro

- Restaurar em camadas: **acesso -> rede -> DNS/DHCP -> runtime -> publicacao -> dados -> aplicacoes -> validacao externa**.
- Nao começar reiniciando tudo sem diagnostico.
- Registrar horario do incidente, impacto, ultimo estado conhecido e alteracoes executadas.
- Antes de mexer em aplicacoes, confirmar se o problema nao e fisico: energia, cabo, switch, link speed.

## 2. Acesso Inicial

### 2.1 Confirmar conectividade

```bash
ping -c 3 192.168.15.2
ssh homelab@192.168.15.2 'uptime'
```

### 2.2 Se LAN falhar

```bash
ssh -o ProxyCommand='cloudflared access ssh --hostname %h' homelab@ssh.rpa4all.com
```

### 2.3 Se SSH falhar

- Acessar console fisico.
- Validar boot completo.
- Confirmar que a tela local chegou ao `btop`/login prompt.

## 3. Baseline do Host

Executar sempre no inicio:

```bash
hostname
uptime
ip -br addr
ip route
systemctl is-system-running
systemctl --failed --no-pager
df -h /
df -h /mnt/storage
free -h
```

### Resultado esperado

- host `homelab`
- interface LAN com `192.168.15.2/24`
- rota default ativa
- sem falhas criticas em `systemctl --failed`
- espaco livre em `/` e `/mnt/storage`

## 4. Camada 1 - Rede e Acesso

### 4.1 Validar interface fisica

```bash
ip -br link
ethtool eth-onboard
networkctl status eth-onboard
```

### Esperado

- `eth-onboard` `UP`
- `Link detected: yes`
- `Auto-negotiation: on`
- velocidade ideal `1000Mb/s`

### Se cair para `100Mb/s`

- trocar cabo
- trocar porta no switch
- validar speed/duplex no parceiro de link
- renegociar com:

```bash
sudo ethtool -r eth-onboard
```

### 4.2 Validar gateway e internet

```bash
ping -c 3 192.168.15.1
ping -c 3 8.8.8.8
getent ahostsv4 google.com | head
```

## 5. Camada 2 - DNS, DHCP e Publicacao Base

Servicos base de rede descritos na documentacao:

- `homelab-lan-dhcp.service` -> DHCP LAN via `dnsmasq`
- `pihole.service` -> DNS Pi-hole na LAN
- `cloudflared-rpa4all.service` -> publicacao externa
- `nginx.service` -> reverse proxy local

### 5.1 Validar servicos

```bash
systemctl status homelab-lan-dhcp.service --no-pager
systemctl status pihole.service --no-pager
systemctl status cloudflared-rpa4all.service --no-pager
systemctl status nginx.service --no-pager
```

### 5.2 Validar portas

```bash
ss -lntup | egrep ':(53|67|80|443|7844|8053)\b'
```

### 5.3 Validar DNS Pi-hole

```bash
dig @192.168.15.2 google.com
dig @192.168.15.2 pi.hole
curl -I http://192.168.15.2:8053/admin/
```

### Esperado

- `dig` com `NOERROR`
- admin do Pi-hole respondendo `302`

### 5.4 Validar tunel Cloudflare

```bash
systemctl status cloudflared-rpa4all.service --no-pager
journalctl -u cloudflared-rpa4all.service -n 100 --no-pager
```

Se houver VPN ativa, validar rotas de excecao do Cloudflare conforme `docs/HOMELAB_NETWORK_RECOVERY_2026-04-15.md`.

## 6. Camada 3 - Runtime e Persistencia

### 6.1 Runtime

```bash
systemctl status docker --no-pager
docker ps --format 'table {{.Names}}\t{{.Status}}'
```

### 6.2 Bancos e caches em container

Containers observados como base de persistencia:

- `eddie-postgres`
- `wikijs-db`
- `authentik-postgres`
- `authentik-redis`
- `nextcloud-db`
- `nextcloud-redis`

### 6.3 Validar containers de dados

```bash
docker ps --format '{{.Names}}' | egrep 'eddie-postgres|wikijs-db|authentik-postgres|authentik-redis|nextcloud-db|nextcloud-redis'
```

Se banco nao subir, nao prosseguir para aplicacoes dependentes antes de restaurar persistencia.

## 7. Ordem de Restauracao das Aplicacoes

Usar esta ordem sempre:

1. Acesso e rede
2. DNS/DHCP
3. Docker + bancos + redis
4. Nginx + Cloudflare Tunnel
5. Identidade e publicacao
6. Observabilidade
7. APIs internas
8. Bots e automacoes
9. Sistemas auxiliares
10. Validacao externa

## 8. Matriz de Aplicacoes e Validacoes

## 8.1 Publicacao, IAM e colaboracao

### Open WebUI

- Container: `open-webui`
- URL local: `http://127.0.0.1:3000`
- URL publica: `https://openwebui.rpa4all.com`

```bash
docker ps --format '{{.Names}} {{.Status}}' | grep open-webui
curl -I http://127.0.0.1:3000
```

### Authentik

- Containers: `authentik-server`, `authentik-worker`, `authentik-postgres`, `authentik-redis`, `authentik-ldap-outpost`
- Porta local observada: `9000`
- Papel: SSO para Wiki.js e demais apps

```bash
docker ps --format '{{.Names}} {{.Status}}' | egrep 'authentik-(server|worker|postgres|redis|ldap-outpost)'
curl -I http://127.0.0.1:9000
```

### Wiki.js

- Containers: `wikijs`, `wikijs-db`
- URL local: `http://127.0.0.1:3009`
- URL publica: `https://wiki.rpa4all.com`

```bash
docker ps --format '{{.Names}} {{.Status}}' | egrep 'wikijs|wikijs-db'
curl -I http://127.0.0.1:3009
```

### Nginx / site principal

- Servico: `nginx.service`
- Backend local documentado: `127.0.0.1:8090`
- Dominios: `www.rpa4all.com`, `rpa4all.com`

```bash
systemctl status nginx.service --no-pager
curl -I http://127.0.0.1:8090
```

## 8.2 Observabilidade

### Grafana

- Container: `grafana`
- URL local: `http://127.0.0.1:3002`
- URL publica: `https://grafana.rpa4all.com`

```bash
docker ps --format '{{.Names}} {{.Status}}' | grep grafana
curl -I http://127.0.0.1:3002
```

### Alertmanager

- Servico: `alertmanager.service`
- Porta observada: `9093`

```bash
systemctl status alertmanager.service --no-pager
curl -I http://127.0.0.1:9093
```

### Prometheus

- Documentado em `docs/MONITORING_SETUP.md`
- Porta esperada: `9090`

```bash
ss -lntp | grep ':9090\b' || true
curl -I http://127.0.0.1:9090 || true
```

Se indisponivel, confirmar se esta desativado por desenho atual ou se houve falha de DR.

### Exporters

- `prometheus-node-exporter.service`
- `ollama-metrics-exporter.service`
- `eddie-central-metrics.service`
- `eddie-whatsapp-exporter.service`
- `storj-exporter.service`
- `storj-selfheal-exporter.service`
- `tunnel-healthcheck-exporter.service`

```bash
systemctl status prometheus-node-exporter.service --no-pager
systemctl status eddie-central-metrics.service --no-pager
systemctl status eddie-whatsapp-exporter.service --no-pager
```

## 8.3 APIs e agentes

### Specialized Agents API

- Servico: `specialized-agents-api.service`
- Porta: `8503`

```bash
systemctl status specialized-agents-api.service --no-pager
curl -I http://127.0.0.1:8503/docs
```

### Dashboard de agentes

- Porta observada: `8502`

```bash
ss -lntp | grep ':8502\b'
curl -I http://127.0.0.1:8502
```

### Secrets Agent

- Servico: `secrets_agent.service`
- Porta observada: `8088`

```bash
systemctl status secrets_agent.service --no-pager
curl -sS --max-time 5 http://127.0.0.1:8088/health || true
```

### Personaide RAG

- Servico: `personaide-rag.service`
- Porta observada: `8001`

```bash
systemctl status personaide-rag.service --no-pager
curl -I http://127.0.0.1:8001
```

### Storage Portal API

- Servico: `storage-portal-api.service`
- Porta esperada: `8511`

```bash
systemctl status storage-portal-api.service --no-pager
ss -lntp | grep ':8511\b' || true
```

## 8.4 Bots e automacoes

### Telegram bot

- Servico: `eddie-telegram-bot.service`

```bash
systemctl status eddie-telegram-bot.service --no-pager
journalctl -u eddie-telegram-bot.service -n 50 --no-pager
```

### WhatsApp bot

- Servico: `eddie-whatsapp-bot.service`
- Dependencias relevantes: `secrets_agent.service`, Postgres, WAHA/HTTP backend
- Referencia operacional: `docs/WHATSAPP_BOT_AUDIT_AND_OPERATIONS.md`

```bash
systemctl status eddie-whatsapp-bot.service --no-pager
journalctl -u eddie-whatsapp-bot.service -n 100 --no-pager
```

### WhatsApp exporter

```bash
systemctl status eddie-whatsapp-exporter.service --no-pager
```

### Guardrails de trading

- Servico: `trading-guardrails-control.service`

```bash
systemctl status trading-guardrails-control.service --no-pager
```

## 8.5 Infraestrutura de IA

### Ollama

- Porta observada: `11434`
- watchdog: `ollama-gpu-selfheal.service`

```bash
ss -lntp | grep ':11434\b'
systemctl status ollama-gpu-selfheal.service --no-pager
curl -I http://127.0.0.1:11434 || true
```

## 8.6 Aplicacoes de produtividade e plataforma

### Home Assistant

- Container: `homeassistant`
- URL local: `http://127.0.0.1:8123`

```bash
docker ps --format '{{.Names}} {{.Status}}' | grep homeassistant
curl -I http://127.0.0.1:8123
```

### Nextcloud

- Containers: `nextcloud-app`, `nextcloud-db`, `nextcloud-redis`

```bash
docker ps --format '{{.Names}} {{.Status}}' | egrep 'nextcloud-(app|db|redis)'
```

### Mail / Roundcube

- Containers: `mailserver`, `roundcube`
- Portas observadas: `25`, `80`, `143`, `443`, `465`, `587`, `993`, `9080`
- URL local Roundcube: `http://127.0.0.1:9080`

```bash
docker ps --format '{{.Names}} {{.Status}}' | egrep 'mailserver|roundcube'
curl -I http://127.0.0.1:9080
```

### iVentoy / PXE

- Servico: `iventoy.service`
- Portas observadas: `16000`, `16001`, `16002`, `26000`

```bash
systemctl status iventoy.service --no-pager
ss -lntp | egrep ':(16000|16001|16002|26000)\b'
```

### ntopng

- Servico: `ntopng.service`
- Compose documentado em `docker/docker-compose.ntopng.yml`
- Porta esperada: `8877/ntopng`

```bash
systemctl status ntopng.service --no-pager
ss -lntp | grep ':8877\b' || true
```

### Print services

- `printshare.service`
- `print-ondemand.service`
- `cups.service`

```bash
systemctl status printshare.service --no-pager
systemctl status print-ondemand.service --no-pager
systemctl status cups.service --no-pager
```

## 8.7 Storage, NAS e backup

### Storj

- Container: `storagenode`
- Exporters: `storj-exporter.service`, `storj-selfheal-exporter.service`

```bash
docker ps --format '{{.Names}} {{.Status}}' | grep storagenode
systemctl status storj-exporter.service --no-pager
systemctl status storj-selfheal-exporter.service --no-pager
```

### NAS / LTFS

Referencias:
- `docs/LTFS_CRASH_SELFHEAL_SYSTEM.md`
- `docs/MONITORING_SETUP.md`

Validar:

```bash
tail -50 /var/log/ltfs-selfheal.log 2>/dev/null || true
curl -sS http://127.0.0.1:9090/api/v1/alerts 2>/dev/null | head || true
```

Se o NAS `192.168.15.4` estiver no escopo do incidente:

```bash
ping -c 3 192.168.15.4
```

## 9. Validacao Externa dos Endpoints Publicos

Executar apos rede, nginx, Cloudflare e apps base estarem OK:

```bash
for url in \
  https://www.rpa4all.com \
  https://openwebui.rpa4all.com \
  https://grafana.rpa4all.com \
  https://wiki.rpa4all.com \
  https://homelab.rpa4all.com \
  https://mail.rpa4all.com \
  https://guardrails.rpa4all.com
do
  echo "== $url =="
  curl -k -I -sS --max-time 10 "$url" | head -n 1
done
```

### Resultado esperado tipico

- `www.rpa4all.com` -> `200`
- `openwebui.rpa4all.com` -> `200`
- `grafana.rpa4all.com` -> `200`
- `wiki.rpa4all.com` -> `200`
- `homelab.rpa4all.com` -> `302` ou resposta autenticada
- `mail.rpa4all.com` -> `302`
- `guardrails.rpa4all.com` -> `401` autenticado

## 10. Falhas Ja Observadas no Boot de 2026-04-28

Registrar como referencia de DR, nao como baseline desejado:

- `eddie-whatsapp-bot.service` em `auto-restart` com `status=2`
- `storage-portal-api.service` em `auto-restart` com `status=203/EXEC`
- `eddie-whatsapp-exporter.service` falho
- `nas-ai-assessor.service` falho
- `prometheus.service` inativo
- link fisico LAN negociando em `100Mb/s` porque o parceiro de link anuncia apenas `10/100`

## 11. Checklist de Encerramento do DR

- Confirmar servicos criticos restaurados.
- Confirmar endpoints locais e publicos.
- Confirmar DNS, DHCP e tunnel.
- Confirmar containers e bancos.
- Confirmar bots prioritarios.
- Registrar RCA preliminar.
- Atualizar documentacao do incidente em `docs/INCIDENTS/`.
- Se houver impacto relevante, publicar resumo na Wiki.js seguindo `docs/WIKI_IMPORT_INSTRUCTIONS.md`.

### Automacao de fechamento de boot

- Script: `scripts/monitoring/final_boot_status_agent.py`
- Unit template: `tools/systemd/final-boot-status-agent.service`
- Entrega: envia resumo de boot ao Telegram via `specialized-agents-api`
- Endpoint usado: `POST /notify/telegram` com fallback legado `POST /api/notify`

## 12. Checklist Resumido de Execucao

```bash
ssh homelab@192.168.15.2 '
echo "== HOST ==" &&
uptime &&
ip -br addr &&
systemctl --failed --no-pager &&
echo "== NETWORK ==" &&
ping -c 2 192.168.15.1 &&
echo "== CORE SERVICES ==" &&
systemctl is-active docker nginx cloudflared-rpa4all.service homelab-lan-dhcp.service pihole.service specialized-agents-api.service secrets_agent.service &&
echo "== CONTAINERS ==" &&
docker ps --format "{{.Names}} {{.Status}}" &&
echo "== LOCAL URLS ==" &&
for u in http://127.0.0.1:8090 http://127.0.0.1:3000 http://127.0.0.1:3002 http://127.0.0.1:3009 http://127.0.0.1:8123 http://127.0.0.1:8503/docs http://127.0.0.1:9080; do
  printf "%s -> " "$u"; curl -k -sS -o /dev/null -w "%{http_code}\n" --max-time 5 "$u" || echo fail;
done
'
```

## 13. Donos e Dependencias Rapidas

| Camada | Componentes principais |
|---|---|
| Acesso | `ssh`, `eth-onboard`, gateway `192.168.15.1` |
| Rede | `homelab-lan-dhcp.service`, `pihole.service`, `nginx.service`, `cloudflared-rpa4all.service` |
| Runtime | `docker.service`, volumes, redes Docker |
| IAM | `authentik-*` |
| Colaboracao | `wikijs`, `open-webui`, `specialized-agents-api.service` |
| Observabilidade | `grafana`, `alertmanager.service`, exporters |
| Bots | `eddie-telegram-bot.service`, `eddie-whatsapp-bot.service` |
| Dados | `eddie-postgres`, `wikijs-db`, `authentik-postgres`, `nextcloud-db` |
| Casa e utilitarios | `homeassistant`, `iventoy.service`, `ntopng.service`, `printshare.service` |
| Storage | `storagenode`, LTFS/NAS exporters e self-heal |

---

**Ultima consolidacao:** `2026-04-28`  
**Manter atualizado sempre que surgir novo servico, porta, dominio ou dependencia critica.**
