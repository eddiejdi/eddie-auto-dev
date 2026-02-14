# VPN Externa para Homelab - Configuração Funcional

**Status:** ✅ **FUNCIONANDO** (2026-02-14)

## Visão Geral

VPN WireGuard externa que funciona através de **SSH tunnel + UDP-over-TCP relay** para contornar limitações do Cloudflare Tunnel (que não suporta UDP nativo).

### Arquitetura

```
Cliente (rede externa)
  ↓ WireGuard UDP (local)
  ↓ Relay Client (UDP:51823 → TCP:51822)
  ↓ SSH Tunnel (local:51822 → homelab:51821)
  ↓ Cloudflare Tunnel (ssh.rpa4all.com)
  ↓ Homelab: TCP:51821
  ↓ Relay Server (TCP → UDP:51820)
  ↓ WireGuard Server (UDP:51820)
```

## Componentes

### 1. Relay Server (homelab)
- **Localização:** `/home/homelab/udp_tcp_relay.py`
- **Systemd:** `udp-tcp-relay.service`
- **Porta:** TCP 51821 → UDP 51820
- **Status:** `sudo systemctl status udp-tcp-relay`

### 2. SSH Tunnel
- **Comando:** `ssh -N -L 51822:127.0.0.1:51821 ssh.rpa4all.com`
- **Via:** Cloudflare Tunnel `ssh.rpa4all.com`
- **Fallback:** `cloudflared access tcp --hostname vpn.rpa4all.com --url localhost:51822`

### 3. Relay Client (local)
- **Script:** `tools/udp_tcp_relay.py client`
- **Porta:** UDP 51823 → TCP 51822
- **Log:** `/tmp/relay-client.log`

### 4. WireGuard Client
- **Config:** `/etc/wireguard/homelab-vpn.conf` ou `homelab-vpn-external.conf`
- **Interface:** `homelab-vpn`
- **IP:** 10.66.66.2/24
- **Gateway:** 10.66.66.1 (homelab)
- **AllowedIPs:** `10.66.66.0/24,192.168.15.0/24` (VPN + rede interna homelab)

## Acesso à Rede Interna

A VPN está configurada para permitir acesso à rede interna do homelab (`192.168.15.0/24`):

- **Homelab (gateway):** `10.66.66.1` ou `192.168.15.2`
- **Serviços disponíveis:**
  - Open WebUI: `http://192.168.15.2:3000/`
  - Grafana: `http://192.168.15.2:3002/`
  - API: `http://192.168.15.2:8503/`
  - Outros serviços na rede 192.168.15.0/24

**Nota:** O WireGuard server no homelab usa NAT (`iptables MASQUERADE`) para rotear tráfego da VPN para a rede interna.

## Uso Rápido

### Iniciar VPN

```bash
# Opção 1: wg-quick (automático, PreUp/PostDown)
sudo cp homelab-vpn-external.conf /etc/wireguard/homelab-vpn.conf
sudo wg-quick up homelab-vpn

# Opção 2: Manual (passo a passo)
# 1. SSH tunnel
ssh -f -N -L 51822:127.0.0.1:51821 ssh.rpa4all.com

# 2. Relay client
nohup python3 tools/udp_tcp_relay.py client --udp-listen 51823 --tcp-target 127.0.0.1:51822 > /tmp/relay-client.log 2>&1 &

# 3. WireGuard
sudo ip link add homelab-vpn type wireguard
sudo wg set homelab-vpn private-key /tmp/wg-priv.key \
  peer RJTM75HsZRGG2Jcr2ylA/wC1rcT1QE4POOB/hw3PIWA= \
  preshared-key /tmp/wg-psk.key \
  endpoint 127.0.0.1:51823 \
  allowed-ips 10.66.66.0/24 \
  persistent-keepalive 25
sudo ip addr add 10.66.66.2/24 dev homelab-vpn
sudo ip link set homelab-vpn up
```

### Testar Conectividade

```bash
# Ping VPN gateway
ping -c 4 10.66.66.1

# Ping homelab (rede interna)
ping -c 4 192.168.15.2

# SSH via VPN gateway
ssh homelab@10.66.66.1

# Acessar serviços internos (ex: Open WebUI)
curl http://192.168.15.2:3000/

# Verificar rotas
ip route get 10.66.66.1
ip route get 192.168.15.2
```

### Parar VPN

```bash
# wg-quick
sudo wg-quick down homelab-vpn

# Manual
sudo ip link delete homelab-vpn
pkill -f 'udp_tcp_relay.py client'
pkill -f 'ssh.*51822:127.0.0.1:51821'
```

## Troubleshooting

### Problema: Ping não funciona

1. **Verificar interfaces conflitantes:**
   ```bash
   ip link show | grep homelab
   # Se houver homelab-local, desligar:
   sudo wg-quick down homelab-local
   ```

2. **Verificar rota:**
   ```bash
   ip route get 10.66.66.1
   # Deve mostrar: dev homelab-vpn (não homelab-local)
   ```

3. **Verificar relay client:**
   ```bash
   ps aux | grep udp_tcp_relay
   tail -30 /tmp/relay-client.log
   # Deve mostrar: "Connected to TCP:127.0.0.1:51822"
   ```

4. **Verificar SSH tunnel:**
   ```bash
   ss -tlnp | grep 51822
   # Deve mostrar: ssh process listening na porta 51822
   ```

### Problema: "TCP connection refused"

Relay client não consegue conectar ao SSH tunnel. Soluções:

```bash
# Reiniciar SSH tunnel
pkill -f 'ssh.*51822'
ssh -f -N -L 51822:127.0.0.1:51821 ssh.rpa4all.com
sleep 2

# Reiniciar relay client
pkill -f 'udp_tcp_relay.py client'
python3 tools/udp_tcp_relay.py client --udp-listen 51823 --tcp-target 127.0.0.1:51822 > /tmp/relay-client.log 2>&1 &
```

### Problema: WireGuard handshake mas sem data plane

Este era o problema crítico resolvido! Causas:
- Interface WireGuard errada (`homelab-local` vs `homelab-vpn`)
- SSH tunnel não estava rodando
- Relay client não conectado ao tunnel

Após correção → **100% packet loss → 0% packet loss** ✅

## Performance

### Latência

**VPN Gateway (10.66.66.1):**
- RTT min: ~40ms
- RTT avg: ~150ms  
- RTT max: ~360ms

**Rede Interna (192.168.15.2):**
- RTT min: ~48ms
- RTT avg: ~144ms
- RTT max: ~298ms

**HTTP (192.168.15.2:3000):**
- Connect time: ~0.53s
- Total time: ~0.88s
- Status: 200 OK ✅

**Nota:** SSH tunnel tem melhor performance que cloudflared TCP para este caso de uso.

## Manutenção

### Logs

```bash
# Relay client (local)
tail -f /tmp/relay-client.log

# Relay server (homelab)
ssh homelab@ssh.rpa4all.com 'sudo journalctl -u udp-tcp-relay -f'

# WireGuard
sudo wg show homelab-vpn
```

### Atualizar relay server no homelab

```bash
scp tools/udp_tcp_relay.py homelab@ssh.rpa4all.com:/home/homelab/
ssh homelab@ssh.rpa4all.com 'sudo systemctl restart udp-tcp-relay'
```

## Alternativas Consideradas

1. **Cloudflare Tunnel direto** — ❌ não suporta UDP
2. **wstunnel** — ❌ handshake OK mas data plane falha
3. **socat** — ❌ não preserva datagram boundaries
4. **IPv6 direto** — ❌ ISP bloqueia UDP IPv6
5. **SSH tunnel + custom relay** — ✅ **FUNCIONA**

## Referências

- WireGuard server config: `/etc/wireguard/wg0.conf` (homelab)
- Relay server service: `/etc/systemd/system/udp-tcp-relay.service` (homelab)
- Cloudflare config: `/etc/cloudflared/config.yml` (homelab)
- Secrets Agent: chaves armazenadas em `eddie-wireguard-keys`

**Timestamp:** 2026-02-14 15:58:00
