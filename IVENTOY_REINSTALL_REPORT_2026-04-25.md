# iVentoy Reinstalação - Relatório Completo
**Data**: 25 de abril de 2026  
**Status**: ✅ **CONCLUÍDO COM SUCESSO**

---

## 1. FASE 1: LEVANTAMENTO DE CUSTOMIZAÇÕES ✅

Auditoria completa de todos os arquivos e configurações personalizadas:

### 1.1 Boot Scripts
- `boot.ipxe` - Script customizado com parâmetros de rede (gateway, DNS)
- `boot.ipxe.bak.20260425T144932` - Backup automático

### 1.2 Data Files (Persistência)
- `config.dat` (18KB) - Configuração principal do iVentoy
- `config.dat.bak` (18KB) - Backup automático
- `iventoy.dat` (7.7MB) - Banco de dados ISO
- `iventoy.dat.bak` (7.7MB) - Backup automático
- `config.dat.corrupted.1777157148` - Arquivo corrompido (preservado para análise)

### 1.3 User Scripts
- `rpi-kids-preseed.cfg` (2.2KB) - Preseed customizado para instalação RPi Desktop Kids Atom

### 1.4 Systemd Service
- `iventoy.service` - Service definition com hooks:
  - `ExecStartPre=/opt/iventoy/restore_config.sh` - Auto-restore de configurações
  - `ExecStartPost=-/opt/iventoy/auto_start_pxe.sh` - Auto-start de PXE

### 1.5 Infraestrutura
- dnsmasq config (PXE - linhas 31-36)
- Symlink: `/opt/iventoy` → `/opt/iventoy-1.0.25`

---

## 2. FASE 2: BACKUP COMPLETO ✅

**Local**: `/home/homelab/backups/iventoy_backup_2026-04-25_195701/`

```
iventoy_backup_2026-04-25_195701/
├── boot.ipxe (244B)
├── boot.ipxe.bak.20260425T144932 (599B)
├── iventoy.service (769B)
├── homelab-lan.conf.dnsmasq (1.2KB)
├── auto_start_pxe.sh (1.6KB)
├── iventoy.sh (2.1KB)
├── restore_config.sh (209B)
├── data/ (29MB)
│   ├── config.dat (18KB)
│   ├── config.dat.bak (18KB)
│   ├── config.dat.corrupted.1777157148 (8.9KB)
│   ├── iventoy.dat (7.7MB)
│   ├── iventoy.dat.bak (7.7MB)
│   ├── mac.db.bak (6.8MB)
│   └── mac.db.disabled (6.8MB)
└── user/scripts/
    ├── rpi-kids-preseed.cfg (2.2KB)
    └── example/ (exemplos padrão - 44KB)
```

**Total**: ~36MB de backup completo

---

## 3. FASE 3: REINSTALAÇÃO ✅

### 3.1 Remoção
- Parou iVentoy service
- Finalizou processos pendentes
- Removeu `/opt/iventoy` e `/opt/iventoy-1.0.25`
- Desabilitou systemd service

### 3.2 Extração
- Extraiu nova instância do tarball existente:
  - Fonte: `/opt/iventoy-1.0.25.bak.1777152185.tar.gz` (22.7MB)
  - Destino: `/opt/iventoy-1.0.25/`
  - Symlink: `/opt/iventoy` recriado

### 3.3 Restauração de Customizações
✅ Boot scripts restaurados
✅ Data files restaurados (config.dat, iventoy.dat)
✅ User scripts restaurados (rpi-kids-preseed.cfg)
✅ Systemd service restaurado

### 3.4 Inicialização
- Recarregou systemd daemon
- Habilitou iventoy.service
- Iniciou serviço com sucesso

---

## 4. VERIFICAÇÃO FINAL ✅

### 4.1 Status do Serviço
```
● iventoy.service - iVentoy PXE Boot Server
  Loaded: loaded (/etc/systemd/system/iventoy.service; enabled; preset: enabled)
  Active: active (running) since Sat 2026-04-25 20:01:10 -03
  Process: ExecStartPre=/opt/iventoy/restore_config.sh → SUCCESS
  Process: ExecStart=/opt/iventoy/iventoy.sh -R start → SUCCESS  
  Process: ExecStartPost=/opt/iventoy/auto_start_pxe.sh → SUCCESS
  Main PID: 1441750 (iventoy)
  Memory: 23.6M
```

### 4.2 Logs de Sucesso
```
[iventoy-autostart] PXE services started OK 
(uuid=2d2dad26-ef80-4e45-86ee-c08c73415443, result={ "result" : "success" })
```

### 4.3 Portas Ativas
- ✅ **26000** - WebUI (http://192.168.15.2:26000)
- ✅ **16000** - HTTP Boot Menu (http://192.168.15.2:16000/ipxe/...)
- ✅ **10809** - NBD Protocol (ISO boot)

---

## 5. ESTRUTURA PÓS-INSTALAÇÃO

```
/opt/iventoy-1.0.25/
├── iventoy (daemon executável)
├── iventoy.sh (script de controle)
├── restore_config.sh ✅ (auto-restore de configs)
├── auto_start_pxe.sh ✅ (auto-start de PXE)
├── data/ ✅ (customizado - config.dat + iventoy.dat restaurados)
├── ipxe-scripts/ ✅ (boot.ipxe customizado com network params)
├── user/scripts/ ✅ (rpi-kids-preseed.cfg restaurado)
├── lib/ (binários)
├── doc/ (documentação)
└── iso → /mnt/raid1/isos (link para ISOs - 4.1GB RPi Desktop Kids Atom ativo)

/etc/systemd/system/iventoy.service ✅ (service definition restaurado)
/opt/iventoy → /opt/iventoy-1.0.25 ✅ (symlink)
```

---

## 6. INTEGRIDADE DE CUSTOMIZAÇÕES

| Componente | Status | Verificado |
|-----------|--------|-----------|
| Boot script (network params) | ✅ Restaurado | 244 bytes |
| Data persistence (config.dat) | ✅ Restaurado | 18KB |
| Data persistence (iventoy.dat) | ✅ Restaurado | 7.7MB |
| User preseed (rpi-kids) | ✅ Restaurado | 2.2KB |
| Systemd service | ✅ Restaurado | Funcional |
| PXE auto-start | ✅ Funcional | Success logs |
| WebUI | ✅ Acessível | Port 26000 |
| HTTP menu | ✅ Acessível | Port 16000 |
| NBD (ISO boot) | ✅ Acessível | Port 10809 |

---

## 7. BACKUP DE SEGURANÇA

Localizado em: `/home/homelab/backups/iventoy_backup_2026-04-25_195701/`

**Ação recomendada**: Fazer download via SCP ou SSH para repositório remoto
```bash
scp -r homelab@192.168.15.2:/home/homelab/backups/iventoy_backup_2026-04-25_195701/ ./backups/
```

---

## 8. PRÓXIMOS PASSOS

✅ **Tudo pronto para operação normal**

- iVentoy está operacional e respondendo em todas as portas
- Customizações foram preservadas e restauradas
- Auto-recovery scripts funcionando (restore_config.sh, auto_start_pxe.sh)
- PXE boot pronto para novos clientes

Para testar PXE boot, envie signal DHCP de um cliente na rede 192.168.15.0/24

---

**Concluído por**: GitHub Copilot  
**Data de conclusão**: 25 de abril de 2026, 20:01 UTC-3
