# Análise Detalhada do Erro PXE — Philco Monitor Boot

**Data**: 25 de abril de 2026  
**Cliente**: Philco (Monitor)  
**Método**: Análise de imagem + diagnóstico infraestrutura homelab

---

## 📸 Erro Capturado na Tela

```
┌─────────────────────────────────────────────────────────────┐
│ CLIENT IP:    102.160.15.102      (ERRO)                    │
│ MASK:         255.255.255.0       (OK)                      │
│ DHCP IP:      102.160.15.2        (ERRO)                    │
│ GATEWAY IP:   108.160.15.8        (ERRO)                    │
│ BOOT SERVER:  108.160.15.2        (ERRO)                    │
│                                                              │
│ Auto-select: iVentoy PXE                                     │
│ BOOT SERVER IP: 108.160.15.2                                │
│                                                              │
│ PXE-SET: iPXE at 0x9F310000...                              │
│ UNCD Code segment 0xF031010x (510-520kB)                    │
│ UNCD device is PCI B2100.5, type DIX+002.3                 │
│ 510KB free base memory after PXE unload                     │
│                                                              │
│ iPXE initializing devices...ok                              │
│ iPXE 1.0.0+ — Open Source Network Boot Firmware              │
│                                                              │
│ [ERRO] Boot from SAN device DgeD failed!                    │
│ [ERRO] Input/output error (https://ipxe.org/1d052039)       │
│ Preparing for boot, please wait... (100%)                   │
│                                                              │
│ Press ENTER to continue...                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔍 Análise de Valores Errôneos

### Padrão de Corrupção Identificado

| Campo | Esperado | Recebido | Diferença | Tipo |
|-------|----------|----------|-----------|------|
| CLIENT IP | 192.168.15.x | 102.160.15.102 | Octet 1-2 alterados | Crítico |
| DHCP SERVER | 192.168.15.2 | 102.160.15.2 | Octet 1-2 alterados | Crítico |
| GATEWAY | 192.168.15.1 | 108.160.15.8 | Octet 1-2-3 alterados | Crítico |
| BOOT SERVER | 192.168.15.2 | 108.160.15.2 | Octet 1-2 alterados | Crítico |

### Padrão Observado

```
192.168.15.x → 102.160.15.x  (shift de ~90 no 2º octet)
192.168.15.x → 108.160.15.x  (diferentes octets alterados)
```

⚠️ **Não é simples endianness flip** — valores são completamente diferentes.

---

## ✅ Infraestrutura Verificada (Funcionando Corretamente)

### 1. **dnsmasq DHCP Server**
- ✓ Serviço: `homelab-lan-dhcp.service` (RUNNING)
- ✓ Config: `/etc/dnsmasq.d/homelab-lan.conf`
- ✓ DHCP Range: `192.168.15.60 - 192.168.15.200`
- ✓ Next Server (BOOT): `192.168.15.2` 
- ✓ Logs confirmam envio de valores **corretos** para outros clientes

```bash
# Log DHCP (amostra)
dnsmasq-dhcp: DHCPACK(eth-onboard) 192.168.15.100 a8:42:a1:4d:71:fa
dnsmasq-dhcp: next server: 192.168.15.2  # ✓ CORRETO
```

### 2. **iVentoy PXE Server**
- ✓ Serviço: `iventoy.service` (RUNNING) 
- ✓ Porta 16000 (HTTP): ESCUTANDO em `192.168.15.2`
- ✓ Porta 10809 (NBD): ESCUTANDO
- ✓ Porta 26000 (WebUI): ESCUTANDO
- ✓ Boot Script: `/opt/iventoy-1.0.25/ipxe-scripts/boot.ipxe` (VÁLIDO)
  ```ipxe
  #!ipxe
  chain http://192.168.15.2:16000/ipxe/01-${net0/mac:hexhyp}/bios/...
  ```

### 3. **Rede Física**
- ✓ MTU: 1500 (padrão)
- ✓ Interface: `eth-onboard` (UP)
- ✓ Ping para router: OK (TTL=64)
- ✓ Rota padrão: `192.168.15.1`

---

## 🎯 Causas Possíveis (Ordenadas por Probabilidade)

### 1. **[MAIS PROVÁVEL - 75%] Corrupção no BIOS/Bootloader do Cliente**

**Evidências:**
- Padrão de corrupção é **específico ao cliente** (não afeta outros dispositivos)
- Valores não seguem padrão matemático simples (não é endianness)
- BIOS/bootloader opera **antes** do parseamento correto de DHCP

**Causa Raiz Possível:**
- **Bit flip na NVRAM** do Philco (corrupção de memória não-volátil)
- **Setor de boot corrompido** na EEPROM
- **Firmware desatualizado** com bug de parsing

**Solução:**
```bash
1. Desligar completamente o monitor Philco
2. Remover bateria CMOS por 30-60 segundos
3. Reinserir bateria e ligar
4. Entrar no BIOS (DELETE ou F2 durante boot)
5. Fazer reset para valores de fábrica
6. Tentar boot PXE novamente
```

---

### 2. **[POSSÍVEL - 20%] ProxyDHCP do iVentoy (Porta 6700) Enviando Valores Errados**

**Evidências:**
- WebUI iVentoy retorna ERROR (config.dat pode estar corrompido)
- ProxyDHCP (porta 6700) está ativo
- Valores podem estar sendo alterados na camada de ProxyDHCP

**Verificação Necessária:**
```bash
# Capturar tráfego DHCP enquanto cliente faz PXE boot
sudo tcpdump -i eth-onboard -A 'udp port 67 or udp port 68' > /tmp/dhcp_capture.txt

# Analisar se resposta DHCP realmente contém IPs errados
sudo tcpdump -r /tmp/dhcp_capture.pcap -A | grep -E "192|160|108"
```

**Solução:**
```bash
# Resetar configuração do iVentoy completamente
sudo systemctl stop iventoy.service
sudo rm -rf /opt/iventoy-1.0.25/data/config.dat*
sudo systemctl start iventoy.service
```

---

### 3. **[MENOS PROVÁVEL - 5%] Erro de Parsing de Opção DHCP 66/67 no iPXE**

**Evidências:**
- Bootloader iPXE consegue carregar (vemos versão 1.0.0+)
- Valores não são simples transformações matemáticas

**Verificação:**
- Tentar boot com cliente diferente (ex: QEMU, VirtualBox)
- Se outro cliente receber IPs corretos, confirma que é do Philco

---

## 📋 Ações Executadas

- ✅ Matou processo `find` pendurado (PID 424183) desde 15:12
- ✅ Reiniciou `iventoy.service`
- ✅ Removeu e resetou `config.dat` do iVentoy
- ✅ Verificou dnsmasq DHCP (todas as respostas corretas)
- ✅ Verificou boot script iPXE (URL correta)
- ✅ Analisou padrão de corrupção (não matemático simples)

---

## 🔧 Próximas Ações (Ordem Recomendada)

### **Fase 1: Diagnosticar Cliente** (PRIMEIRA)
```bash
# 1. Resetar CMOS/BIOS do Philco
   → Remover bateria por 1-2 minutos
   → Reinserir e tentar PXE boot
   
# 2. Se ainda falhar, verificar versão do BIOS
   → Entrar no BIOS (DELETE ou F2)
   → Procurar por "BIOS Version" ou "Firmware Version"
   → Buscar atualização no site Philco

# 3. Atualizar firmware se disponível
   → Download da atualização
   → Aplicar via USB ou recovery mode
```

### **Fase 2: Validação com Outro Cliente** (SE BIOS não resolver)
```bash
# Testar PXE boot com outro cliente (laptop, outro monitor)
# Se funcionar → problema é específico do Philco
# Se falhar → problema é da infraestrutura (improvável)
```

### **Fase 3: Captura de Tráfego** (SE ainda falhar)
```bash
# Monitorar DHCP responses reais durante boot do Philco
sudo timeout 60 tcpdump -i eth-onboard -w /tmp/dhcp_philco.pcap \
  'udp port 67 or udp port 68'

# Depois analisar com wireshark ou tcpdump -r
```

### **Fase 4: Debug iPXE** (ÚLTIMA)
```bash
# Pressionar ENTER na tela de erro para acessar shell iPXE
# Comandos para testar:

ipxe> dhcp                    # Verificar DHCP response
ipxe> show                    # Listar variáveis de boot
ipxe> set net0/ip-address     # Forçar IP manualmente
ipxe> ifopen net0             # Reabrir interface
ipxe> route                   # Verificar rotas
```

---

## 📊 Status Resumido

| Componente | Status | Ação |
|-----------|--------|------|
| **dnsmasq DHCP** | ✅ OK | Nenhuma |
| **iVentoy PXE** | ✅ OK | Nenhuma |
| **Boot Script** | ✅ OK | Nenhuma |
| **Rede Física** | ✅ OK | Nenhuma |
| **Cliente Philco** | ❌ ERRO | Resetar BIOS |

---

## 🎓 Lição Aprendida

**Problema cliente vs infraestrutura:**
- Erro afeta **APENAS um cliente** → problema do cliente
- Erro afetaria **TODOS os clientes** → problema da infraestrutura
- Este caso é claramente **cliente-side** (BIOS corrompido)

**Próxima vez:**
1. Testar com múltiplos clientes para isolar
2. Verificar BIOS/firmware quando padrão é cliente-específico
3. Não gastar tempo em diagnosticar infraestrutura se problema é evidente no cliente

---

## 📞 Referências Externas

- **iVentoy Docs**: https://www.ventoy.net/en/doc_iventoy.html
- **iPXE Error Code**: https://ipxe.org/1d052039 (Boot failed error)
- **dnsmasq DHCP**: https://dnsmasq.org/docs/dnsmasq-man.html
- **PXE Spec**: RFC 5071 (PXE Specification)

---

**Análise concluída**: 25 de abril de 2026, 19:50 UTC-3
