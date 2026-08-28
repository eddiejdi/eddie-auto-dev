# Configuração de Atualização Automática do Sistema

## Status ✅
- **Script**: `/usr/local/bin/system-auto-update`
- **Serviço**: `system-auto-update.service`
- **Timer**: `system-auto-update.timer` (**ATIVO**)
- **Log**: `/var/log/system-auto-update.log`

## Agendamento
- **Frequência**: Diariamente
- **Horário**: 02:30 UTC (horário servidor)
- **Timezone**: UTC-3
- **Próxima execução**: Verificar com `sudo systemctl list-timers`

## O que é executado

A atualização automática faz:

```bash
apt-get update       # Atualiza lista de pacotes
apt-get upgrade -y   # Instala todas as atualizações disponíveis
apt-get autoremove   # Remove pacotes não-utilizados
apt-get autoclean    # Limpa cache de pacotes
```

Tudo com output silencioso (`-qq`) e logging completo.

## Gerenciamento

### Ver status do timer
```bash
sudo systemctl status system-auto-update.timer
sudo systemctl list-timers system-auto-update.timer
```

### Ver logs
```bash
tail -f /var/log/system-auto-update.log
sudo journalctl -u system-auto-update.service -f
```

### Desabilitar temporariamente
```bash
sudo systemctl stop system-auto-update.timer
```

### Reabilitar
```bash
sudo systemctl start system-auto-update.timer
```

### Executar manualmente agora
```bash
sudo systemctl start system-auto-update.service
```

### Ver histórico de execuções
```bash
sudo systemctl list-timers --all system-auto-update.timer
```

## Arquivos de Configuração

| Arquivo | Descrição |
|---------|-----------|
| `/usr/local/bin/system-auto-update` | Script executável |
| `/etc/systemd/system/system-auto-update.service` | Definição do serviço |
| `/etc/systemd/system/system-auto-update.timer` | Agendamento (cron) |
| `/var/log/system-auto-update.log` | Log de execuções |

## Modificar horário

Para alterar o horário de execução (ex: 03:00 UTC):

```bash
sudo systemctl edit system-auto-update.timer
```

Altere a linha:
```ini
OnCalendar=*-*-* 02:30:00
```

Para:
```ini
OnCalendar=*-*-* 03:00:00
```

Depois recarregue:
```bash
sudo systemctl daemon-reload
sudo systemctl restart system-auto-update.timer
```

## Notas

- O timer persiste entre reboots (`Persistent=true`)
- Se o sistema estiver desligado no horário de execução, rodarará na próxima inicialização
- Logs são acumulativos — considere usar `logrotate` se crescerem muito
- O script roda como `root` para ter permissões de instalação de pacotes
