# Homelab Network Recovery — 2026-04-15

> Restauração operacional do Pi-hole, Cloudflare Tunnel e serviços publicados no homelab `192.168.15.2`.

## Resumo Executivo

Em 2026-04-15 o homelab apresentou falhas simultaneas em tres camadas:

1. **Pi-hole** ativo em container, mas com inicializacao instavel por conflito de DHCP.
2. **Cloudflare Tunnel** ativo de forma intermitente e com falha de conectividade por causa da VPN.
3. **Backends publicados** parcialmente indisponiveis, incluindo `mail.rpa4all.com` e `guardrails.rpa4all.com`.

Ao final da intervencao, o estado ficou:

- **Pi-hole** restaurado para DNS na LAN.
- **DHCP** mantido no host via `dnsmasq`, sem delegar DHCP ao Pi-hole.
- **Cloudflare Tunnel** restaurado com conectividade estavel.
- **Principais dominios** publicados novamente com sucesso.
- **Guardrails** corrigido para responder adequadamente a `HEAD`.
- **Roundcube / mail** reativado.
- **Pendente real**: `nas.rpa4all.com` continua em `502` porque o destino configurado (`192.168.15.4`) nao responde na LAN.

---

## Escopo da Intervencao

### Componentes revisados

- Docker no host `homelab`
- Container `pihole`
- Servico `homelab-lan-dhcp.service`
- Servico `cloudflared-rpa4all.service`
- Regras de bypass da VPN para Cloudflare
- Nginx local para rotas protegidas
- Servico `trading-guardrails-control.service`
- Container `roundcube`

### Validacoes executadas

- `systemctl is-active` dos servicos criticos
- `ss -lntup` para portas `53`, `67`, `8053`, `7844`
- `dig @192.168.15.2 google.com`
- `dig @192.168.15.2 pi.hole`
- `curl -I http://192.168.15.2:8053/admin/`
- `curl -I` para dominios `*.rpa4all.com` a partir do servidor
- verificacao de backends locais em `127.0.0.1`

---

## Diagnostico Inicial

### 1. Pi-hole

O Pi-hole estava configurado em Docker com `network_mode: host`, mas o FTL falhava ao subir por tentar abrir o socket DHCP em uma maquina que ja possuia `dnsmasq` escutando na LAN.

Sintoma observado:

- erro de bind do socket DHCP
- inicializacao inconsistente do container
- DNS parcialmente disponivel

### 2. Docker

Durante a recuperacao, o daemon Docker entrou em estado ruim:

- `docker.service` ficou preso em transicao
- houve sinais de `daemonShuttingDown=true`
- alguns containers criticos ficaram indisponiveis temporariamente

### 3. Cloudflare Tunnel

O `cloudflared` estava subindo, mas o trafego de saida para a edge da Cloudflare era impactado pela VPN NordVPN e pelo kill-switch.

Impacto observado:

- tunel com conectividade degradada
- origens atingidas de forma irregular
- dominios publicos falhando mesmo com backend local saudavel

### 4. Backends publicados

Havia mistura de problemas:

- backend local parado
- backend local autenticado, mas respondendo mal a `HEAD`
- destino final do NAS indisponivel na propria LAN

---

## Decisoes Operacionais

### DHCP permaneceu no host

Foi mantido o desenho onde:

- **Pi-hole** faz apenas DNS
- **dnsmasq do host** continua responsavel por DHCP na interface LAN

Motivo:

- o host ja possui `homelab-lan-dhcp.service`
- havia conflito direto de porta UDP `67`
- mover DHCP para o Pi-hole exigiria replanejar a LAN, nao apenas restaurar disponibilidade

### Cloudflare deve permanecer como excecao a VPN

Como os tuneis precisam funcionar mesmo com VPN ativa:

- sub-redes da edge da Cloudflare foram explicitamente roteadas pela LAN
- o trafego do `cloudflared` deixou de depender do caminho tunelado da VPN para funcionar

---

## Alteracoes Aplicadas

## Pi-hole

### Arquivo alterado

- `/home/homelab/pihole/docker-compose.yml`

### Ajustes

- `FTLCONF_dhcp_active: "false"`
- remocao de `FTLCONF_dns_listeningAddress` invalido
- troca de `FTLCONF_dhcp_interface` por `FTLCONF_dns_interface`

### Novo bootstrap via systemd

Foram criados / ajustados:

- `/usr/local/sbin/pihole-run.sh`
- `/etc/systemd/system/pihole.service`

Objetivo:

- evitar dependencia de um caminho quebrado de `docker-compose`
- garantir start idempotente do container

## Cloudflare Tunnel

### Arquivo alterado

- `/etc/cloudflared/config.yml`

### Ajuste aplicado

- `protocol: http2`

### Bypass da VPN

Arquivo alterado:

- `/usr/local/sbin/cloudflared-vpn-routes.sh`

Ajuste:

- roteamento das redes Cloudflare pela interface LAN (`eth-onboard`)

### Allowlist NordVPN

Foram liberados:

- porta `7844`
- `198.41.192.0/24`
- `198.41.200.0/24`

## Guardrails

Arquivo alterado:

- `/home/homelab/myClaude/tools/trading_guardrails_control.py`

Ajuste:

- adicionado suporte a `HEAD`

Resultado:

- antes: `501 Unsupported method ('HEAD')`
- depois: `401 Unauthorized`

Isto normalizou a publicacao via Cloudflare para `guardrails.rpa4all.com`, mantendo autenticacao.

## Mail / Roundcube

Ajuste operacional:

- container `roundcube` reativado

Resultado:

- `127.0.0.1:9080` voltou a responder `200`
- `mail.rpa4all.com` voltou a responder `302` na borda, com backend funcional por tras do Authentik

---

## Estado Final Validado

## Servicos locais

Todos ativos:

- `docker`
- `pihole.service`
- `homelab-lan-dhcp.service`
- `cloudflared-rpa4all.service`
- `trading-guardrails-control.service`

## Pi-hole na LAN

Validado com sucesso:

- `dig @192.168.15.2 google.com` -> `NOERROR`
- `dig @192.168.15.2 pi.hole` -> `NOERROR`
- `curl -I http://192.168.15.2:8053/admin/` -> `302 Found`

## Backends locais

Validados no host:

- `http://127.0.0.1:3000` -> `200`
- `http://127.0.0.1:3002` -> `200`
- `http://127.0.0.1:3009` -> `200`
- `http://127.0.0.1:9000` -> `302`
- `http://127.0.0.1:9001` -> `302`
- `http://127.0.0.1:8053/admin/` -> `302`
- `http://127.0.0.1:9080` -> `200`
- `http://127.0.0.1:8765/` -> `401`

## Dominios publicados

Validados a partir do proprio servidor:

| Dominio | Estado |
|---|---|
| `www.rpa4all.com` | `200` |
| `auth.rpa4all.com` | `302` |
| `openwebui.rpa4all.com` | `200` |
| `grafana.rpa4all.com` | `200` |
| `wiki.rpa4all.com` | `200` |
| `homelab.rpa4all.com` | `302` |
| `mail.rpa4all.com` | `302` |
| `guardrails.rpa4all.com` | `401` |
| `nas.rpa4all.com` | `502` |

---

## Pendencias e Riscos Remanescentes

### NAS

`nas.rpa4all.com` continua quebrado por causa do destino configurado no proxy local:

- nginx em `127.0.0.1:9004` aponta para `http://192.168.15.4`
- `192.168.15.4` nao responde a ARP, ping ou HTTP a partir do `homelab`

Conclusao:

- o problema restante **nao esta no Cloudflare Tunnel**
- o problema restante **nao esta no proxy da borda**
- o problema esta no **destino do NAS**, provavelmente desligado, com IP trocado ou fora da LAN

### Acesso do cliente local a Cloudflare

Durante a analise houve indicios de timeout do cliente local ao acessar Cloudflare na `443`, mesmo quando o servidor respondia normalmente.

Interpretacao:

- pode existir um problema de caminho especifico do cliente
- isso nao invalida a restauracao do lado do servidor

---

## Comandos de Verificacao Rapida

```bash
# Estado dos servicos principais
ssh homelab 'systemctl is-active docker pihole.service homelab-lan-dhcp.service cloudflared-rpa4all.service trading-guardrails-control.service'

# DNS pela LAN
dig +time=3 +tries=1 @192.168.15.2 google.com
dig +time=3 +tries=1 @192.168.15.2 pi.hole

# Painel do Pi-hole
curl -I http://192.168.15.2:8053/admin/

# Dominios publicados
ssh homelab 'for d in www.rpa4all.com auth.rpa4all.com openwebui.rpa4all.com grafana.rpa4all.com wiki.rpa4all.com homelab.rpa4all.com mail.rpa4all.com guardrails.rpa4all.com nas.rpa4all.com; do curl -4 -kIsS --max-time 12 https://$d | head -n 1; done'

# Tamanho do problema remanescente
ssh homelab 'curl -kisS --max-time 10 http://127.0.0.1:9004/ | head'
ssh homelab 'ip neigh show 192.168.15.4; ping -c 1 -W 2 192.168.15.4 || true'
```

---

## Conclusao

A restauracao do homelab foi bem-sucedida no que dependia do host `192.168.15.2`, do Docker, do Pi-hole, do `cloudflared`, do `roundcube` e dos proxies locais.

O unico item ainda aberto e `nas.rpa4all.com`, cujo destino final nao responde na rede local e precisa de acao sobre o proprio NAS ou revisao do IP configurado.

---

**Data:** 2026-04-15  
**Host:** `homelab` (`192.168.15.2`)  
**Status Geral:** restaurado com 1 pendencia externa ao tunel
