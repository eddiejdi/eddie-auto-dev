# Network Inventory — Homelab 192.168.15.0/24
**Data:** 2026-06-08
**Descoberta:** nmap + ip addr + nmcli + MAC vendor lookup
**Destino:** NetBox CMDB (Sprint 2 input)

---

## Topologia de Rede

```
ISP GVT (fibra)
     │
     ▼
[ZTE GPON modem] ─── 192.168.15.1 (LAN 100Mb)
     │
     ├──[Switch/powerline LAN]
     │        │
     │        ├── 192.168.15.2  Homelab eth-onboard (LAN serving)   ──┐
     │        ├── 192.168.15.3  Homelab eth-wan     (WAN, gw→.1)     │ mesmo host
     │        ├── 192.168.15.251 storj-host0 (macvlan)                ┘
     │        │
     │        ├── 192.168.15.50   TP-Link AP (GVT-38AA WiFi, admin :80)
     │        ├── 192.168.15.114  [este laptop] wlp2s0 (WiFi GVT-38AA, DHCP)
     │        ├── 192.168.15.137  [este laptop] enp0s31f6 (RJ45, never-default)
     │        │
     │        ├── 192.168.15.140  Tuya Smart IoT #1
     │        ├── 192.168.15.143  Tuya Smart IoT #2
     │        └── 192.168.15.188  Tuya Smart IoT #3
     │
     └── 192.168.15.4  NAS (OFFLINE em 2026-06-08)
```

---

## Hosts — Tabela IPAM

| IP | MAC | Hostname | Fabricante | Role | Status | Notas |
|---|---|---|---|---|---|---|
| 192.168.15.1 | 00:d4:9e:16:6a:19 | ZTE GPON | ZTE | gateway/modem | UP (não responde ping) | ISP modem GVT fibra; LAN 100Mb; admin http://192.168.15.1 |
| 192.168.15.2 | 00:e0:4c:b6:3d:5e | homelab / pi.hole | Realtek | server | UP | eth-onboard; serving LAN; Nginx, SSH, NFS, Samba, Pi-hole, Prometheus |
| 192.168.15.3 | 00:e0:4c:b6:3d:5e | homelab eth-wan | Realtek | server (interface) | UP | eth-wan do mesmo host (.2); WAN route via .1 metric 50 |
| 192.168.15.4 | 00:e0:4c:b6:3d:5c | NAS | Realtek | nas | OFFLINE | NAS com drives LTO/HDD; unreachable em 2026-06-08 |
| 192.168.15.50 | 00:0a:eb:13:7b:00 | TP-Link AP | TP-Link | access-point | UP | Serve SSID "GVT-38AA" (ch.11); admin http://192.168.15.50; powerline TL-PA4010 |
| 192.168.15.114 | d4:6a:6a:fd:9d:47 | edenilson (WiFi) | — | workstation | UP (dinâmico) | wlp2s0; DHCP; conectado a GVT-38AA (TANK offline) |
| 192.168.15.137 | 18:66:da:fe:58:94 | edenilson (RJ45) | — | workstation | UP (dinâmico) | enp0s31f6; never-default; rota estática 192.168.15.0/24 metric 5 |
| 192.168.15.140 | 4c:a9:19:0d:d2:7d | IoT Tuya #1 | Tuya Smart | iot | UP | sem portas abertas detectadas; WiFi |
| 192.168.15.143 | f8:17:2d:f8:59:52 | IoT Tuya #2 | Tuya Smart | iot | UP | latência alta (WiFi); sem portas abertas |
| 192.168.15.188 | 20:f1:b2:56:ff:e7 | IoT Tuya #3 | Tuya Smart | iot | UP | latência alta (WiFi); sem portas abertas |
| 192.168.15.251 | 00:e0:4c:b6:3d:5e | storj-host0 | Realtek | vm/container | UP | macvlan sobre eth-wan do homelab; Storj node |

---

## Homelab — Interfaces e Serviços (192.168.15.2)

**Host:** Dell (físico), hostname `homelab`, Ubuntu 22/24.04

### Interfaces de rede

| Interface | IP | Uso |
|---|---|---|
| eth-onboard | 192.168.15.2/24 | LAN — serving; sem default route |
| eth-wan (USB RTL8153) | 192.168.15.3/24 | WAN — default route via 192.168.15.1 metric 50 |
| protonvpn (WireGuard) | 10.2.0.2/32 | ProtonVPN BR#51 (146.70.98.162:51820) |
| wg0 (WireGuard) | 10.66.66.1/24 | VPN para clientes homelab |
| storj-host0 (macvlan) | 192.168.15.251/32 | Storj node IP dedicado |
| virbr0 (KVM/libvirt) | 192.168.122.1/24 | Rede VMs locais |
| docker0 | 172.17.0.1/16 | Docker bridge padrão |
| br-* (Docker) | 172.18-24.x.1/16 | Bridges por stack Docker |
| tunl0 (IPIP) | 10.42.107.128/32 | Legado k3s/Akash |

### Serviços em execução (Docker)

| Container | Imagem | Porta host | Serviço |
|---|---|---|---|
| cmdb-netbox | netboxcommunity/netbox:v4.6-5.0.1 | 18091 | NetBox CMDB |
| cmdb-glpi | glpi/glpi:latest | 18092 | GLPI inventário |
| cmdb-netbox-postgres | postgres:18-alpine | interno | BD NetBox |
| cmdb-glpi-db | mariadb:11 | interno | BD GLPI |
| cmdb-netbox-redis | valkey:9.0-alpine | interno | Cache NetBox |
| nextcloud-app | nextcloud:latest | via nginx | Nextcloud |
| open-webui | open-webui:v0.6.16 | via nginx | OpenWebUI |
| authentik-server | goauthentik/server:2024.12 | via nginx | SSO Authentik |
| homeassistant | home-assistant:stable | via nginx | Home Assistant |
| wikijs | requarks/wiki:2 | via nginx | Wiki.js |
| storagenode | storjlabs/storagenode:latest | externo | Storj node |
| prometheus | prom/prometheus:latest | interno | Prometheus |

### Portas abertas (nmap)

| Porta | Serviço | Detalhe |
|---|---|---|
| 22/tcp | SSH | OpenSSH 9.6p1 Ubuntu |
| 80/tcp | HTTP | Nginx 1.24.0 |
| 139/tcp | Samba | NetBIOS |
| 443/tcp | HTTPS | Nginx 1.24.0 |
| 445/tcp | Samba | SMB |
| 2049/tcp | NFS | v3-4 |
| 3000/tcp | HTTP | Uvicorn (estou-aqui API) |
| 8080/tcp | HTTP | BaseHTTPServer Python 3.12 |
| 9090/tcp | HTTP | Go (Prometheus ou Storj) |
| 9100/tcp | node_exporter | Prometheus metrics |

---

## Redes e Prefixos

| Prefixo | Tipo | Uso | Gateway |
|---|---|---|---|
| 192.168.15.0/24 | LAN | Rede principal homelab | 192.168.15.1 (ZTE) / .2 (homelab) |
| 10.2.0.0/24 | VPN | ProtonVPN WireGuard | — |
| 10.66.66.0/24 | VPN | wg0 — clientes homelab-vpn | 10.66.66.1 |
| 192.168.122.0/24 | Hypervisor | KVM libvirt virbr0 | 192.168.122.1 |
| 172.17.0.0/16 | Container | Docker bridge padrão | 172.17.0.1 |
| 172.18-24.0.0/16 | Container | Docker bridges por stack | 172.x.0.1 |
| 10.42.0.0/16 | Legado | k3s/Akash (encerrado) | — |

---

## Este notebook — Dell Latitude 5480

**Hostname:** edenilson
**OS:** LMDE 7 (Debian base), Kernel 6.12.90
**Hardware:** Dell Latitude 5480, Firmware 1.39.0 (2024-11-06)

### Interfaces

| Interface | MAC | Rede atual | Conexão NM | Notas |
|---|---|---|---|---|
| wlp2s0 | d4:6a:6a:fd:9d:47 | 192.168.15.114/24 (DHCP) | GVT-38AA Automático | Preferida: TANK (offline 2026-06-08) |
| enp0s31f6 | 18:66:da:fe:58:94 | 192.168.15.137/24 (DHCP) | Wired connection 1 | never-default=yes; rota estática /24 metric 5 |

### Roteamento atual (2026-06-08)

```
default via 192.168.15.2 dev wlp2s0  metric 600  (WiFi GVT-38AA)
192.168.15.0/24 dev enp0s31f6  metric 5   (RJ45, static)
192.168.15.0/24 dev enp0s31f6  metric 800 (RJ45, kernel)
192.168.15.0/24 dev wlp2s0     metric 600 (WiFi, kernel)
```

### Conexões WiFi conhecidas

| SSID | Subnet | Uso | Status (2026-06-08) |
|---|---|---|---|
| TANK | 10.x.x.x | Internet direta (preferida) | OFFLINE — AP não visível |
| GVT-38AA | 192.168.15.0/24 | Homelab WiFi (fallback) | CONNECTED (auto-fallback) |
| TP-Link_71FA | ? | Powerline admin | Desconectado |
| TV Quarto.m | 192.168.15.0/24? | IoT / TV | Visível |

### VPNs configuradas

| Nome | Tipo | Status |
|---|---|---|
| homelab-vpn | WireGuard | Desconectado |
| wg0 | WireGuard | Desconectado |
| wg-panama | WireGuard | Desconectado |
| br101.nordvpn.com.udp | NordVPN/OpenVPN | Desconectado |

---

## Causa raiz do "internet via RJ45" (2026-06-08)

**Situação:** Usuário reportou internet vindo pelo RJ45 ao invés do WiFi.
**Causa:** TANK (rede WiFi de internet direta, subnet separada) estava offline. NetworkManager fez auto-fallback para GVT-38AA, que está na mesma subnet (192.168.15.0/24) que o RJ45. Com ambas interfaces na mesma subnet, o default route via WiFi (`wlp2s0`, metric 600) e via RJ45 estão no mesmo segmento — internet sai pelo homelab gateway (192.168.15.2) independente de qual interface.
**Solução imediata:** Nenhuma — NM configurado corretamente com `never-default=yes` no RJ45. Quando TANK voltar, WiFi migrará automaticamente.
**Proteção:** `ipv4.never-default: yes` e `ipv4.never-default: yes` (IPv6) configurados em "Wired connection 1" — RJ45 nunca vira gateway de internet.

---

## Pendências e Anomalias

| Item | Detalhe | Ação |
|---|---|---|
| NAS (192.168.15.4) | OFFLINE em 2026-06-08 | Verificar se desligado ou com problema |
| TANK AP | SSID não visível no scan | Verificar AP do TANK (BSSIDs: 92:94:83:6F:04:CC, D6:A5:46:A4:64:D6) |
| ZTE GPON (.1) | Não responde ping mas roteia tráfego | Normal (ICMP bloqueado) |
| API_TOKEN_PEPPERS | Não configurado no NetBox | Adicionar em `/home/homelab/cmdb/.env` para habilitar provision de tokens |
| 192.168.15.3 MAC | nmap mostra mesmo MAC que .2 | Confirmar — pode ser alias/macvlan ou GARP |
| Tuya IoT .140/.143/.188 | Sem hostname/função identificada | Mapear dispositivos Tuya no Home Assistant |
| Docker bridges 172.x/16 | 8 bridges ativas | Consolidar stacks para reduzir fragmentação |

---

## NetBox CMDB — Importação Sprint 2

Path: `http://192.168.15.2:18091/cmdb/netbox/`
Auth: sessão (login cmdb-admin) ou Token API (requer `API_TOKEN_PEPPERS` no .env)

### Checklist de cadastro

- [x] Site: homelab-main (já existe)
- [ ] Prefix: 192.168.15.0/24
- [ ] Prefix: 10.66.66.0/24 (wg0)
- [ ] Prefix: 10.2.0.0/24 (ProtonVPN)
- [ ] Device Type: Dell Latitude 5480
- [ ] Device Type: TP-Link AP
- [ ] Device: homelab server (192.168.15.2)
- [ ] Device: NAS (192.168.15.4)
- [ ] Device: edenilson laptop (192.168.15.114/137)
- [ ] Device: TP-Link AP (192.168.15.50)
- [ ] IPs: todos os hosts acima
- [ ] VMs/containers: Nextcloud, NetBox, GLPI, Authentik, WikiJS, HA, OpenWebUI, Storj
