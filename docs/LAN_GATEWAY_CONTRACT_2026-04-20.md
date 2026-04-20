# Contrato Operacional da LAN — 2026-04-20

## Resumo
- Gateway canônico da LAN: `192.168.15.2`
- DNS canônico da LAN: `192.168.15.2`
- Wi-Fi: contingência, com prioridade menor que o Ethernet
- `192.168.15.1`: legado de transição, fora de playbooks e automações ativas

## Componentes
- Estação local: perfil Ethernet persistido com gateway/DNS em `192.168.15.2`
- Homelab: NAT e forwarding aplicados por `homelab-lan-gateway.sh`
- NordVPN: watchdog separado garante que o egress continue em `nordlynx`

## Operação
- Validar o gateway da LAN:
```bash
ssh homelab@192.168.15.2 sudo /usr/local/bin/homelab-lan-gateway.sh --health-check
```

- Validar o cutover da estação:
```bash
sudo bash scripts/system/workstation-lan-cutover.sh --status
```

- Reaplicar watchdogs:
```bash
bash deploy/vpn/deploy-nordvpn-watchdog.sh
bash deploy/vpn/deploy-homelab-lan-gateway.sh
```
