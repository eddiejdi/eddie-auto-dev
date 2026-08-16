# 2026-08-11 — Migração WAN: USB Realtek antiga → nova USB Realtek

## Resumo

Migração da interface WAN do homelab de uma USB Realtek instável (`eth-wan`) para uma nova USB Realtek (`enx00e04c596710`), com IP estático `192.168.15.3/24` e gateway `192.168.15.1`.

## Timeline

| Hora | Evento |
|------|--------|
| ~08:50 | Inventário: `eth-wan` (USB antiga) ativa com IP `192.168.15.3`, `enx00e04c596710` (nova USB) detectada sem link |
| ~09:00 | Usuário conectou cabo na nova USB — link Gigabit ativo confirmado |
| ~09:05 | Tentativa DHCP na nova USB — roteador não ofereceu lease |
| ~09:10 | Aplicação de IP estático `192.168.15.3/24` via netplan na nova USB |
| ~09:15 | SSH caiu — residual state de `eth-wan` causou conflito de rota |
| ~09:20 | `eth-wan` removida fisicamente (USB desligada) |
| ~09:25 | Acesso recuperado via `192.168.15.3` (nova USB) — SSH com chave |
| ~09:30 | Cloudflare Tunnel reiniciado — `ssh.rpa4all.com` retornando 200 |
| ~09:35 | Validação: Internet, Docker, 17+ containers, Grafana, Nextcloud, Prometheus — todos OK |

## Interface antiga vs nova

| | Antiga (`eth-wan`) | Nova (`enx00e04c596710`) |
|---|---|---|
| MAC | `00:e0:4c:59:xx:xx` | `00:e0:4c:59:67:10` |
| Driver | r8152 (Realtek) | r8152 (Realtek) |
| Velocidade | Instável | 1 Gbps full-duplex estável |
| IP | `192.168.15.3/24` | `192.168.15.3/24` (mesmo IP) |
| Status | **Desligada** | **Ativa, WAN padrão** |

## Configuração final (netplan)

Arquivo: `/etc/netplan/01-static-ip.yaml`

```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    onboard:
      match:
        macaddress: "00:e0:4c:b6:3d:5e"
      set-name: eth-onboard
      dhcp4: false
      wakeonlan: true
      addresses:
        - 192.168.15.2/24
      nameservers:
        addresses:
          - 8.8.8.8
          - 8.8.4.4
    usb-wan:
      match:
        macaddress: "00:e0:4c:59:67:10"
      set-name: enx00e04c596710
      dhcp4: false
      addresses:
        - 192.168.15.3/24
      routes:
        - to: 192.168.15.1/32
          scope: link
        - to: default
          via: 192.168.15.1
          metric: 50
      nameservers:
        addresses:
          - 8.8.8.8
          - 8.8.4.4
```

## Interfaces do servidor

| Interface | IP | Função |
|---|---|---|
| `eth-onboard` | `192.168.15.2/24` | Admin/LAN — preservada |
| `enx00e04c596710` | `192.168.15.3/24` | WAN (Internet) — **nova** |
| `wg0` | `10.66.66.1/24` | WireGuard VPN |
| `protonvpn` | `10.2.0.2/32` | ProtonVPN |

## Rota padrão

```
default via 192.168.15.1 dev enx00e04c596710 proto static metric 50
```

## Validação

- [x] `ping 8.8.8.8` — OK
- [x] `curl https://ssh.rpa4all.com` — 200
- [x] `systemctl is-active cloudflared` — active
- [x] `docker ps` — 17+ containers Up
- [x] Grafana (`:8093`) — 200
- [x] Nginx (`:80`) — 301
- [x] Prometheus — running
- [x] Nextcloud — running
- [x] PostgreSQL (`:5433`) — running

## Rollback

Se a nova USB falhar:

```bash
# 1. Reconectar cabo na USB antiga
# 2. No console do homelab:
sudo ip link set enx00e04c596710 down
sudo ip addr add 192.168.15.3/24 dev eth-wan
sudo ip route add default via 192.168.15.1 dev eth-wan metric 100

# 3. Restaurar netplan anterior:
sudo cp /etc/netplan/01-static-ip.yaml.bak-migration-20260811-085804 /etc/netplan/01-static-ip.yaml
sudo netplan apply
```

## Lições aprendidas

1. **DHCP não funcionou** — o roroteador GVT não ofereceu lease para a nova USB; IP estático foi necessário
2. **Residual state** — `eth-wan` manteve IP/rota após cabo removido, causou conflito; sempre fazer `ip addr flush` antes de desligar interface
3. **Cloudflared parou** — serviço ficou `inactive (dead)` após troca de interface; precisou `systemctl start cloudflared`
4. **ARP REACHABLE ≠ ICMP OK** — tabela ARP pode mostrar host como REACHABLE mesmo com rota quebrada
