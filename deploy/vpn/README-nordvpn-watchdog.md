# 🔒 NordVPN Routing Watchdog — À Prova de Acidentes

**Problema:** Em 7 de abril, você reverteu acidentalmente a rota NordVPN para eth-onboard.  
**Solução:** Watchdog automático + SystemD drop-in à prova de sobrescrita

---

## 🏗️ Arquitetura

### 1. **SystemD NetworkD Drop-in** (`99-force-nordvpn-routing.network`)
- **Prioridade máxima (99)** — sobrescreve qualquer outra config
- **Rota padrão prioritária (50)** — ganha de eth-onboard (600)
- **À prova de netplan** — ignora mudanças em netplan

### 2. **Watchdog Service + Timer**
- **Executa a cada 5 minutos** — monitora rota NordVPN
- **Health check** — verifica IP público + rota + interface
- **Auto-fix** — se rota quebrar, corrige automaticamente
- **Persistent** — recupera se servidor reiniciar

### 3. **Pre-Deploy Validator**
- **Integração CI/CD** — bloqueia deploy se rota estiver quebrada
- **Fail-safe** — impede que deploy reintroduza o bug

---

## 🚀 Instalação

### Quick Setup
```bash
chmod +x /workspace/eddie-auto-dev/deploy/vpn/deploy-nordvpn-watchdog.sh
sudo bash /workspace/eddie-auto-dev/deploy/vpn/deploy-nordvpn-watchdog.sh
```

### Manual Setup (se prefer controle)
```bash
# 1. Copia script
sudo cp deploy/vpn/nordvpn-routing-watchdog.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/nordvpn-routing-watchdog.sh

# 2. Copia SystemD units
sudo cp deploy/vpn/nordvpn-routing-watchdog*.{service,timer} /etc/systemd/system/
sudo cp deploy/vpn/99-force-nordvpn-routing.network /etc/systemd/network/

# 3. Ativa
sudo systemctl daemon-reload
sudo systemctl enable --now nordvpn-routing-watchdog.timer
sudo systemctl restart systemd-networkd

# 4. Valida
/usr/local/bin/nordvpn-routing-watchdog.sh --health-check
```

---

## 📊 Monitoring

### Verificar Status
```bash
systemctl status nordvpn-routing-watchdog.timer
systemctl list-timers nordvpn-routing-watchdog*
```

### Ver Logs
```bash
journalctl -u nordvpn-routing-watchdog -f
journalctl -u nordvpn-routing-watchdog.timer -f
```

### Health Check Manual
```bash
/usr/local/bin/nordvpn-routing-watchdog.sh --health-check
```

### Forçar Fix Imediato
```bash
sudo /usr/local/bin/nordvpn-routing-watchdog.sh --fix
```

---

## 🛡️ Proteção contra Regressão

### O que impede o bug de volta?

| Camada | Proteção |
|--------|----------|
| **NetworkD** | Drop-in `99-` com prioridade máxima sobrescreve netplan |
| **Watchdog** | Se alguém mexer em netplan, watchdog corrige em 5 min |
| **Timer** | Monitora 24/7, auto-recupera após reboot |
| **Pre-Deploy** | CI/CD valida rota antes de permitir deploy |
| **Alertas** | Se problema persistir > 5 min, systemd gera alerta |

---

## 🔍 Dados Técnicos

### Rota Padrão Esperada
```
default via <nordvpn-gw> dev nordlynx metric 50
```
- **dev:** `nordlynx` (nunca `eth-onboard` para tráfego geral)
- **metric:** 50 (ganha de eth-onboard que é 600)
- **Priority rule:** Tabela 205 para tráfego que sair por nordlynx

### IP Público
- **Esperado:** IP da NordVPN (ex: 193.176.127.25)
- **Não deve ser:** seu IP ISP real

---

## 🧪 Teste de Verificação

```bash
# 1. Verificar rota atual
ip route show | grep default

# 2. Verificar IP público
curl https://api.ipify.org

# 3. Verificar interface ativa
ip route show dev nordlynx

# 4. Verificar regras de roteamento
ip rule show

# 5. Watchdog auto-test
/usr/local/bin/nordvpn-routing-watchdog.sh --health-check
```

---

## ⚠️ Fallback se NordVPN Cair

Se NordVPN desconectar (nordlynx desaparecer):
1. Watchdog detecta em até 5 min
2. Força para eth-onboard temporariamente (com métrica > 600)
3. Monitora reconexão de NordVPN
4. Automaticamente volta para nordlynx quando voltar

---

## 📝 Logs Importantes

```bash
# Sucessos
journalctl -u nordvpn-routing-watchdog -p info -f

# Problemas
journalctl -u nordvpn-routing-watchdog -p warning -f
journalctl -u nordvpn-routing-watchdog -p error -f

# Tudo
journalctl -u nordvpn-routing-watchdog -f
```

---

## 🔧 Customizações

### Mudar intervalo de monitoramento
Edite `/etc/systemd/system/nordvpn-routing-watchdog.timer`:
```ini
[Timer]
OnUnitActiveSec=5min  # ← mude para 1min, 10min, etc
```

### Mudar IP de validação
Edite `/usr/local/bin/nordvpn-routing-watchdog.sh`:
```bash
public_ip=$(curl -s --max-time 5 https://api.ipify.org || echo "TIMEOUT")
```

### Desabilitar auto-fix
```bash
sudo systemctl stop nordvpn-routing-watchdog-fix.service
```

---

## 📋 Checklist Pós-Instalação

- [ ] Deploy rodou sem erros
- [ ] `systemctl status nordvpn-routing-watchdog.timer` mostra `active`
- [ ] `ip route show | grep default` mostra `nordlynx`
- [ ] `curl https://api.ipify.org` retorna IP NordVPN
- [ ] `/usr/local/bin/nordvpn-routing-watchdog.sh --health-check` mostra✅

---

## 🚨 Troubleshooting

### "Interface nordlynx não encontrada"
```bash
# Verificar se NordVPN está rodando
systemctl status nordvpn-gui
systemctl status nordvpnd

# Reconectar
nordevpn connect
```

### "Rota padrão está via eth-onboard"
```bash
# Force manual
sudo /usr/local/bin/nordvpn-routing-watchdog.sh --fix

# Espere watchdog corrigir (máx 5 min)
journalctl -u nordvpn-routing-watchdog -f
```

### Timer não está rodando
```bash
sudo systemctl start nordvpn-routing-watchdog.timer
sudo systemctl enable nordvpn-routing-watchdog.timer
```

---

## 📞 Referência

- **Timer config:** `/etc/systemd/system/nordvpn-routing-watchdog.timer`
- **Service config:** `/etc/systemd/system/nordvpn-routing-watchdog*.service`
- **NetworkD drop-in:** `/etc/systemd/network/99-force-nordvpn-routing.network`
- **Script:** `/usr/local/bin/nordvpn-routing-watchdog.sh`
