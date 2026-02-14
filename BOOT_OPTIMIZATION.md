# Otimização de Boot do Servidor Homelab

**Data:** 2026-02-14  
**Status do Boot:** 48.5s (firmware 11.5s + loader 17.1s + kernel 2.7s + userspace 17.2s)

## Resumo Executivo

A maior parte do tempo de boot (28.6s = **59%**) é gasto em **firmware e BIOS**, que é **não-otimizável via software**. Os 17.2s restantes em userspace foram parcialmente otimizados removendo serviços desnecessários.

---

## Problema 1: Firmware/Loader (28.6s) — **BIOS/UEFI**

### Causa
- BIOS/UEFI executando verificações POST (Power-On Self Test)
- Scanning de dispositivos (USB, PCI, SATA/NVMe)
- Inicialização de chipset e controllers

### Solução: Reconfigurar BIOS

**Como acessar BIOS do seu servidor (i9-9900T):**
1. Reinicie o servidor
2. Imediatamente após POST, pressione `Del`, `F2`, ou `Esc` (depende do motherboard)
3. Ou segure `F11` para boot menu

**Otimizações recomendadas:**

| Configuração | Valor Atual | Valor Recomendado | Ganho Estimado |
|--------------|-------------|-------------------|-----------------|
| **Fast Boot / Quick Boot** | Desabilitado | **Habilitado** | -3-5s |
| **USB Boot Support** | Habilitado | Desabilitar se não usa boot USB | -1-2s |
| **Network Boot (PXE)** | Habilitado | **Desabilitar** | -1-2s |
| **Legacy Boot / CSM** | Pode estar ativo | Desabilitar se UEFI puro | -1-2s |
| **Drives de boot não-usadas** | Múltiplos DDDs/SSDs | Remover do boot order | -2-3s |
| **SMART Check no Boot** | Habilitado | Desabilitar ou reduzir | -1-2s |
| **Quiet Boot / Silent Mode** | Pode estar desabilitado | **Habilitado** | -0.5-1s |
| **Secure Boot** | Habilitado | Desabilitar (improvém boot) | -0.5-1s |

**Ganho total esperado:** ~10-15 segundos

---

## Problema 2: Userspace (17.2s) — **Software**

✅ **Já otimizado:**
- Mascarado `motd-news.service` (-67s em boot anterior)
- Mascarado `apt-daily.service` (-11.6s)
- Mascarado `apt-daily-upgrade.service` (-3.8s)
- Desabilitado `flyio-wireguard`, `autonomous_remediator` (Fly.io removido)
- Desabilitado `localtunnel@dev` (-5s)
- Criado timer para `btc-daily-report` (não bloqueia boot)

**Serviços ainda com tempo no boot:**
- `openwebui-ssh-tunnel.service`: 10s (necessário, SSH tunnel)
- `cloudflared@dev.service`: 5s (Cloudflare tunnel)
- `prometheus-node-exporter-apt.service`: 1.4s
- `systemd-networkd-wait-online.service`: 3.5s (já otimizado para 5s timeout)

---

## Ações Imediatas (Pós Software)

✅ **Completadas:**
```bash
# Serviços mascarados (não rodagem no boot)
sudo systemctl mask motd-news.timer motd-news.service
sudo systemctl mask apt-daily.service apt-daily.timer apt-daily-upgrade.service  
sudo systemctl mask flyio-proxy-toggle
sudo systemctl mask snap.cups.cupsd snap.cups.cups-browsed
sudo systemctl stop flyio-wireguard autonomous_remediator localtunnel@dev
sudo systemctl disable flyio-wireguard autonomous_remediator localtunnel@dev

# btc-daily-report removido do boot, timer criado para 10:00 UTC
sudo systemctl mask btc-daily-report.service
```

---

## Próximos Passos

### 1. Reconfigurar BIOS (Ganho Máximo: ~15s)
- Acesse BIOS e aplique otimizações da tabela acima
- Salve e reinicie

### 2. Testar Novo Boot
```bash
ssh homelab@192.168.15.2
systemd-analyze time
systemd-analyze blame | head -20
```

**Meta:** Reduzir para **~30-35s** (firmware 5-8s + loader 5-8s + kernel 2-3s + userspace 15-20s)

### 3. Monitoramento Pós-Deploy
```bash
# Verificar daily logs
systemctl list-timers --all | grep btc
# BTC report vai rodar diariamente às 10:00 UTC sem impactar boot
```

---

## Referência: Mudanças Aplicadas

**Arquivo de configuração gerado:**
```bash
/etc/systemd/system/systemd-networkd-wait-online.service.d/timeout.conf
→ ExecStart=/usr/lib/systemd/systemd-networkd-wait-online --timeout=5 --any
```

**Timer novo:**
```bash
/etc/systemd/system/eddie-btc-report-daily.timer
→ OnCalendar=*-*-* 10:00:00 (daily at 10 AM UTC)
```

---

## Monitoramento de Saúde

Após BIOS update e reboot, verificar:

```bash
# Boot time total
ssh homelab@192.168.15.2 systemd-analyze time

# CPU carga após boot (deve cair para 1-2)
ssh homelab@192.168.15.2 uptime

# Sem serviços falhados
ssh homelab@192.168.15.2 systemctl list-units --state=failed
```

---

## Notas de Segurança

- **Não desabilite Secure Boot** se o servidor estiver em rede corporativa
- **Fast Boot é seguro** — apenas pula testes POST redundantes
- **PXE é segurança** — desabilitar evita boot accidental de rede

---

**Contato:** Se boot ainda não melhorar após BIOS, verificar:
- Firmware motherboard desatualizado (atualizar BIOS)
- HDDs falhando diagnosticados pelo BIOS
- RAID rebuild em progresso (verificar `mdstat`)
