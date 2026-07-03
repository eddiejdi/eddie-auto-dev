# ProtonVPN Routing Watchdog — À Prova de Acidentes

**Problema:** Reversão acidental da rota VPN para eth-onboard; LAN fica sem internet quando ip rules 32764/32765 somem.  
**Solução:** Três camadas de proteção — dispatcher NM (imediato) + drop-in ExecStartPost (t+5s) + watchdog timer (a cada 5min).

> **Princípio:** VPN é a regra. Bypass é a exceção explícita para IoT.  
> Veja arquitetura completa em [`docs/PROTONVPN_LAN_ROUTING_ARCHITECTURE.md`](../../docs/PROTONVPN_LAN_ROUTING_ARCHITECTURE.md).

---

## Arquitetura

### 1. **NM Dispatcher** (`51-protonvpn-policy-routing`) ✅ _principal_
- **Imediato** — executado pelo NetworkManager assim que `protonvpn` sobe
- Restaura as regras `32764` e `32765` sem nenhum delay
- Cobre reconexões automáticas do ProtonVPN
- **Deploy:** `sudo cp deploy/vpn/51-protonvpn-policy-routing /etc/NetworkManager/dispatcher.d/ && sudo chmod 755 ...`

### 2. **Drop-in ExecStartPost** (`restore-iprules.conf`)
- Backup para o caso de wg-quick sem NM gerenciar a interface
- `sleep 5` antes de chamar o watchdog — aguarda handshake inicial
- **Localização:** `/etc/systemd/system/wg-quick@protonvpn.service.d/restore-iprules.conf`

### 3. **Watchdog Service + Timer**
- **Executa a cada 5 minutos** — health check completo
- Verifica: interface, tabela 205, ip rules 32764/32765, caminho efetivo da LAN, rotas Docker, IP público
- **Auto-fix** — restaura tudo automaticamente se detectar desvio

### 4. **Gateway da LAN**
- **Contrato operacional:** clientes da LAN usam `192.168.15.2` como gateway e DNS
- **Sem dependência ativa de `192.168.15.1`**
- **Watchdog dedicado:** `homelab-lan-gateway.sh` reaplica NAT/forwarding e valida DNS da LAN

### 5. **Pre-Deploy Validator**
- **Integração CI/CD** — bloqueia deploy se rota estiver quebrada

---

## Instalação

### Quick Setup
```bash
chmod +x /workspace/eddie-auto-dev/deploy/vpn/deploy-protonvpn-watchdog.sh
sudo bash /workspace/eddie-auto-dev/deploy/vpn/deploy-protonvpn-watchdog.sh
bash /workspace/eddie-auto-dev/deploy/vpn/deploy-homelab-lan-gateway.sh
```

### Manual Setup
```bash
# 1. Dispatcher NM (principal — aplica regras imediatamente ao subir protonvpn)
sudo cp deploy/vpn/51-protonvpn-policy-routing /etc/NetworkManager/dispatcher.d/
sudo chmod 755 /etc/NetworkManager/dispatcher.d/51-protonvpn-policy-routing

# 2. Copia script do watchdog
sudo cp deploy/vpn/protonvpn-routing-watchdog.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/protonvpn-routing-watchdog.sh

# 3. Copia SystemD units
sudo cp deploy/vpn/protonvpn-routing-watchdog*.{service,timer} /etc/systemd/system/
sudo cp deploy/vpn/99-force-protonvpn-routing.network /etc/systemd/network/

# 4. Ativa
sudo systemctl daemon-reload
sudo systemctl enable --now protonvpn-routing-watchdog.timer
sudo systemctl restart systemd-networkd

# 5. Valida
/usr/local/bin/protonvpn-routing-watchdog.sh --health-check
```

---

## Pré-requisito: ProtonVPN via wg-quick

O watchdog espera ProtonVPN instalado como WireGuard via wg-quick:

```bash
# Coloque a config ProtonVPN em /etc/wireguard/protonvpn.conf
# (baixe do painel ProtonVPN em: Account → Downloads → WireGuard config)

# Habilita e inicia
sudo systemctl enable --now wg-quick@protonvpn

# Verifica
sudo wg show protonvpn
ip link show protonvpn
```

---

## Monitoring

### Verificar Status
```bash
systemctl status protonvpn-routing-watchdog.timer
systemctl list-timers protonvpn-routing-watchdog*
systemctl status homelab-lan-gateway.timer
```

### Ver Logs
```bash
journalctl -u protonvpn-routing-watchdog -f
journalctl -u protonvpn-routing-watchdog.timer -f
```

### Health Check Manual
```bash
/usr/local/bin/protonvpn-routing-watchdog.sh --health-check
```

### Forçar Fix Imediato
```bash
sudo /usr/local/bin/protonvpn-routing-watchdog.sh --fix
```

---

## Dados Técnicos

### Rota Padrão Esperada
```
default dev protonvpn table 205
```
- **dev:** `protonvpn`
- **table:** `205`
- **LAN:** `192.168.15.0/24` permanece direta em `eth-onboard`

### QoS — porta WireGuard
- ProtonVPN WireGuard usa UDP **51820** por padrão
- O QoS em `setup-qos.sh` marca tráfego na interface `protonvpn` (mark 2, classe 1:20)

---

## Troubleshooting

### "Interface protonvpn não encontrada"
```bash
# Verificar se wg-quick está ativo
systemctl status wg-quick@protonvpn

# Reconectar
sudo wg-quick up protonvpn
# ou
sudo systemctl restart wg-quick@protonvpn
```

### "Dispositivo LAN sem internet (exceto IoT)"
```bash
# 1. Verificar se as ip rules críticas existem
ip rule list | grep -E '32764|32765'

# 2. Verificar rota efetiva do dispositivo
ip route get 1.1.1.1 from <IP-DISPOSITIVO> iif eth-onboard
# Esperado: "dev protonvpn table 205"
# Problema:  "Network is unreachable" → rules 32764/32765 ausentes

# 3. Fix
sudo /usr/local/bin/protonvpn-routing-watchdog.sh --fix
```

> Não adicione dispositivos normais ao bypass IoT. Diagnóstico completo em `docs/PROTONVPN_LAN_ROUTING_ARCHITECTURE.md`.

### "Rota padrão está via eth-onboard"
```bash
# Force manual
sudo /usr/local/bin/protonvpn-routing-watchdog.sh --fix

# Espere watchdog corrigir (máx 5 min)
journalctl -u protonvpn-routing-watchdog -f
```

### SSH bloqueado pela VPN
```bash
sudo bash deploy/vpn/recover-protonvpn-ssh-lockout.sh --auto
```

---

## Referência

| Arquivo | Localização | Função |
|---|---|---|
| `51-protonvpn-policy-routing` | `/etc/NetworkManager/dispatcher.d/` | Aplica ip rules **imediatamente** ao subir |
| `restore-iprules.conf` | `/etc/systemd/system/wg-quick@protonvpn.service.d/` | Backup ExecStartPost t+5s |
| `protonvpn-routing-watchdog.sh` | `/usr/local/bin/` | Health check + auto-fix |
| `protonvpn-routing-watchdog.timer` | `/etc/systemd/system/` | Timer 5min |
| `99-force-protonvpn-routing.network` | `/etc/systemd/network/` | NetworkD drop-in |
| `homelab-proxy.nft` | carregado no boot | DROP rule LAN→eth-wan sem bypass |

**Documentação de arquitetura:** [`docs/PROTONVPN_LAN_ROUTING_ARCHITECTURE.md`](../../docs/PROTONVPN_LAN_ROUTING_ARCHITECTURE.md)
