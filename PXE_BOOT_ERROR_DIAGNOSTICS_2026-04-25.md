# PXE Boot Error Diagnostics — 2026-04-25

##  Problema Reportado (Imagem)
```
CLIENT IP: 192.160.15.102 (ERRADO — esperado 192.168.15.x)
DHCP IP: 102.160.15.2 (ERRADO)
GATEWAY IP: 108.160.15.8 (ERRADO)
BOOT SERVER: 108.160.15.2 (ERRADO)
```

**Erro Final**: "Boot from SAN device-DgeD failed! Input/output error"

## Root Cause Analysis

### Componentes Verificados
1. **dnsmasq DHCP server** ✓ CORRETO
   - Config: `/etc/dnsmasq.d/homelab-lan.conf`
   - DHCP range: 192.168.15.60-200
   - Next server (BOOT SERVER): 192.168.15.2
   - Resposta log confirma envio de 192.168.15.x

2. **iVentoy PXE**  ✓ RODANDO
   - Porta 16000 (HTTP): ESCUTANDO em 192.168.15.2
   - Porta 10809 (NBD): ESCUTANDO
   - Porta 26000 (WebUI): ESCUTANDO (mas com erro)
   - ProxyDHCP porta 6700: ESCUTANDO (pode estar enviando erro)

3. **Boot Script iPXE** ✓ CORRETO
   - Arquivo: `/opt/iventoy-1.0.25/ipxe-scripts/boot.ipxe`
   - URL: `http://192.168.15.2:16000/...` (correto)

4. **Rede Física**
   - MTU: 1500 (normal)
   - Interface: eth-onboard
   - Ping para .1: OK

### Causas Possíveis
1. **[MAIS PROVÁVEL] Corrupção no BIOS/Bootloader do Cliente**
   - IPs recebidos: 192.160.15.x (padrão muito suspeit — octet diferente em todos)
   - Pode ser bit flip na NVRAM ou bootloader corrompido
   - Sugere: Resetar BIOS, atualizar firmware do cliente

2. **[POSSÍVEL] ProxyDHCP do iVentoy enviando opções erradas**
   - Porta 6700 está ativa
   - WebUI retorna ERROR (indica config.dat corrompido)
   - Solução: Resetar config.dat do iVentoy

3. **[MENOS PROVÁVEL] Problema de rede física**
   - Ping funciona OK
   - DHCP responde corretamente para outros clientes
   - Seria necessário capturar tráfego específico desse cliente

4. **[MENOS PROVÁVEL] Erro de parsing de opções DHCP**
   - Bootloader iPXE pode estar parseando opção 66/67 incorretamente
   - Valores parecem muito alterados (não é simples endian flip)

## Ações Executadas
- [x] Matou processo `find` pendurado desde 15:12
- [x] Reiniciou iVentoy.service
- [x] Removeu config.dat corrompido (sistema restaurou backup)
- [x] Verificou dnsmasq DHCP (correto)
- [x] Verificou boot script iPXE (correto)

## Próximas Ações Recomendadas

### Opção 1: Diagnosticar Cliente (RECOMENDADO)
1. Verificar BIOS do Philco para versão/update
2. Resetar CMOS/NVRAM do cliente
3. Tentar boot em outro cliente PXE para comparar

### Opção 2: Forçar reconfigurat do iVentoy
1. Acessar WebUI iVentoy (http://192.168.15.2:26000)
2. Verificar "Boot Server" configurado vs esperado
3. Resetar modo ProxyDHCP

### Opção 3: Capturar tráfego específico
1. Monitorar DHCP com tcpdump enquanto cliente faz PXE boot
2. Verificar se resposta DHCP realmente contém IPs errados ou se é parsing do cliente

## Status Atual
- **iVentoy**: Online, PXE services operational
- **DHCP**: Online, respondendo corretamente
- **Boot script**: Válido
- **Cliente Philco**: ❌ Falhando com corrupção de IP (causa desconhecida)

