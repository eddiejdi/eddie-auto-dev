# ProtonVPN Routing Watchdog — À Prova de Acidentes

**Problema:** Reversão acidental da rota VPN para eth-onboard.
**Solução:** Watchdog automático + contrato explícito de gateway da LAN em `192.168.15.2`

---

## Arquitetura

### 1. **SystemD NetworkD Drop-in** (`99-force-protonvpn-routing.network`)
- **Prioridade máxima (99)** — sobrescreve qualquer outra config
- **Rota padrão prioritária (50)** — ganha de eth-onboard (600)
- **À prova de netplan** — ignora mudanças em netplan

### 2. **Watchdog Service + Timer**
- **Executa a cada 5 minutos** — monitora rota ProtonVPN
- **Health check** — verifica IP público + tabela 205 + caminho efetivo da LAN
- **Auto-fix** — se rota quebrar, corrige automaticamente via `systemctl restart wg-quick@protonvpn`
- **Persistent** — recupera se servidor reiniciar

### 3. **Gateway da LAN**
- **Contrato operacional:** clientes da LAN usam `192.168.15.2` como gateway e DNS
- **Sem dependência ativa de `192.168.15.1`**
- **Watchdog dedicado:** `homelab-lan-gateway.sh` reaplica NAT/forwarding e valida DNS da LAN

### 4. **Pre-Deploy Validator**
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
# 1. Copia script
sudo cp deploy/vpn/protonvpn-routing-watchdog.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/protonvpn-routing-watchdog.sh

# 2. Copia SystemD units
sudo cp deploy/vpn/protonvpn-routing-watchdog*.{service,timer} /etc/systemd/system/
sudo cp deploy/vpn/99-force-protonvpn-routing.network /etc/systemd/network/

# 3. Ativa
sudo systemctl daemon-reload
sudo systemctl enable --now protonvpn-routing-watchdog.timer
sudo systemctl restart systemd-networkd

# 4. Valida
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

- **Timer config:** `/etc/systemd/system/protonvpn-routing-watchdog.timer`
- **Service config:** `/etc/systemd/system/protonvpn-routing-watchdog*.service`
- **NetworkD drop-in:** `/etc/systemd/network/99-force-protonvpn-routing.network`
- **Script:** `/usr/local/bin/protonvpn-routing-watchdog.sh`
- **WireGuard config:** `/etc/wireguard/protonvpn.conf`
