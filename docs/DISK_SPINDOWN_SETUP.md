# Disk Spindown Configuration para Homelab

## 📋 Resumo

Configuração de **spindown automático de discos após 2 horas de inatividade** para reduzir consumo de energia e prolongar vida útil dos HDDs.

## 🔧 Componentes Instalados

### 1. Script Principal: `/usr/local/bin/configure-disk-spindown.sh`

**Responsabilidade:**
- Configura APM (Advanced Power Management) para cada disco
- Define timeout de spindown de 2 horas (1440 * 5 segundos = 7200s)
- Registra ações em `/var/log/disk-spindown.log`
- Suporta múltiplos discos (`/dev/sda`, `/dev/sdb`, `/dev/sdc`)

**Comando hdparm utilizado:**
```bash
sudo hdparm -M 254 -S 1440 /dev/sda
```

| Opção | Significado |
|-------|------------|
| `-M 254` | Acoustic management desabilitado|
| `-S 1440` | Spindown timeout = 1440 × 5s = 2 horas |

### 2. Systemd Service: `/etc/systemd/system/disk-spindown.service`

**Execução:**
- Type: `oneshot` (executa uma vez)
- Executado após `local-fs.target`
- Logs via systemd journal e arquivo

**Status:**
```bash
systemctl status disk-spindown.service
```

### 3. Systemd Timer: `/etc/systemd/system/disk-spindown.timer`

**Agendamento:**
- Primeira execução: 1 minuto após boot
- Execuções posteriores: A cada 6 horas
- Persistente: Reexecuta se máquina foi reiniciada durante intervalo agendado

**Próxima execução:**
```bash
systemctl list-timers disk-spindown.timer
```

## 📊 Configuração dos Discos

| Disco | Tamanho | Mountpoint | Status |
|-------|---------|-----------|--------|
| `/dev/sda` | 298.1G | `/mnt/disk1` | ✅ Spindown 2h |
| `/dev/sdb` | 298.1G | `/mnt/disk2` | ✅ Spindown 2h |
| `/dev/sdc` | 465.8G | `/` + outros | ✅ Spindown 2h |

## 🚀 Como Verificar

### Status atual
```bash
# Ver logs da última execução
sudo tail -20 /var/log/disk-spindown.log

# Verificar rpm dos discos
sudo hdparm -C /dev/sda /dev/sdb /dev/sdc
# Output: "standby" = spindown ativo, "active" = rotacionando

# Status do systemd
systemctl status disk-spindown.service disk-spindown.timer
```

### Próximas execuções agendadas
```bash
systemctl list-timers disk-spindown.timer
# Mostra: NEXT (próxima execução), LEFT (tempo até execução)
```

## ⚙️ Comportamento

1. **Boot**: Script executa 1 minuto após `local-fs.target`
2. **A cada 6 horas**: Timer reexecuta configuração (para garantir em caso de erro/desligamento)
3. **Após 2h inativo**: Disco entra em spindown automaticamente
4. **Ao acessar disco**: Motor acorda imediatamente (transparente ao sistema)

## 📝 Logs

Arquivo principal: `/var/log/disk-spindown.log`

Exemplo de saída:
```
[2026-03-05T13:59:45Z] Configurando spindown de discos...
[2026-03-05T13:59:45Z] ✅ Spindown configurado: /dev/sda (timeout=1440*5s)
[2026-03-05T13:59:45Z] ✅ Spindown configurado: /dev/sdb (timeout=1440*5s)
[2026-03-05T13:59:45Z] ✅ Spindown configurado: /dev/sdc (timeout=1440*5s)
[2026-03-05T13:59:45Z] Configuração concluída
```

## 💾 Economia Esperada

### Consumo de Energia
- **HDD em rotação**: ~5-8W por disco
- **HDD em spindown**: ~0.5-1W por disco
- **Economia** (3 discos inativos 18h/dia): ~30-35W contínuos = ~7-8 kWh/mês

### Vida útil
- Menos tempo em rotação = menos desgaste mecânico
- Reduz temperatura operacional
- Diminui risco de falha

## 🔧 Personalização

### Aumentar/Diminuir tempo de spindown

Editar `/usr/local/bin/configure-disk-spindown.sh`:

```bash
# Alterar SPINDOWN_VALUE
SPINDOWN_VALUE=480   # 40 minutos (480 * 5s)
SPINDOWN_VALUE=1440  # 2 horas (padrão atual)
SPINDOWN_VALUE=2880  # 4 horas
```

Depois recarregar:
```bash
sudo systemctl daemon-reload
sudo systemctl start disk-spindown.service
```

### Adicionar/Remover discos

Editar loop no script:
```bash
for disk in /dev/sda /dev/sdb /dev/sdc /dev/sdd; do
    configure_disk "$disk" "$SPINDOWN_VALUE" || true
done
```

## ⚠️ Notas Importantes

1. **HDD vs SSD**: Configuração aplica a todos. SSDs ignoram spindown (não têm motor)
2. **Discos NVMe**: Usam seu próprio gerenciamento de potência (não controlados por hdparm)
3. **Persistência**: Configuração não é permanente no disco (reapplicada a cada 6h)
4. **Falhas de sense data**: Mensagens `SG_IO: bad/missing sense data` são normais em alguns HDDs, não indicam erro

## 📚 Referências

- `man hdparm` — Advanced Power Management
- `/var/log/disk-spindown.log` — Logs detalhados
- [Systemd Timers](https://www.freedesktop.org/software/systemd/man/systemd.timer.html)

---

**Instalado em:** 2026-03-05  
**Status:** ✅ Ativo e agendado  
**Próxima execução:** Ver com `systemctl list-timers disk-spindown.timer`
