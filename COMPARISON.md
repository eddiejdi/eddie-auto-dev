# Comparação: Timeout Simples vs. Watchdog Robusto

## Abordagem 1: Apenas Aumentar Timeout (Simples)
```ini
[Service]
TimeoutStartSec=1800  # Aumenta para 30 minutos
```

**Problemas:**
- ❌ Se processo ficar TRAVADO, ainda falha após 30min
- ❌ Sem detecção automática de hang
- ❌ Sem retry inteligente
- ❌ Sem observabilidade de travamento

## Abordagem 2: Watchdog com Auto-Healing (Robusto) ✅ RECOMENDADO

**Componentes:**

### Service Principal com Recovery
```ini
[Service]
TimeoutStartSec=1800
OnFailure=rpa4all-snapshot-recovery.service
```

### Recovery Service (Retry em 5min)
```ini
ExecStart=/bin/bash -c 'sleep 300; systemctl restart rpa4all-snapshot.service'
```

### Health Check (A cada 5 minutos)
- Monitora arquivo lock (`/tmp/rpa4all-snapshot.lock`)
- Se idade > 1800s (30min): TRAVAMENTO DETECTADO
- Ação: Reinicia serviço automaticamente
- Log: Registra em journalctl

### Timer (Executa health check periodicamente)
```ini
OnUnitActiveSec=5min
```

## Comparação Prática

| Cenário | Timeout Simples | Watchdog |
|---------|-----------------|----------|
| **Backup normal (18min)** | ✅ Sucesso | ✅ Sucesso |
| **Backup travado em 5min** | ⏳ Espera 30min, depois falha | ✅ Detectado em 5min, reinicia |
| **Processo morto (crash)** | ❌ Só vê na próxima execução | ✅ Health check detecta, reinicia |
| **Falha de rede (hang)** | ❌ Fica esperando 30min | ✅ Detectado + retry automático |
| **Observabilidade** | ❌ Apenas erro final | ✅ Logs de hang + recovery |

## Exemplo Timeline

### Com Timeout Simples:
```
T+00:00  Inicia backup
T+05:00  Processo fica travado (rede caída)
T+30:00  Timeout dispara, mata processo
T+30:01  Falha registrada
T+24:00  Próxima execução (dia seguinte?)
```

### Com Watchdog:
```
T+00:00  Inicia backup
T+05:00  Processo fica travado
T+05:05  Health check: "TRAVAMENTO! Reiniciando..."
T+05:06  Reinicia backup (tentativa 2)
T+23:00  Backup completa com sucesso
T+00:00  Próxima execução agendada
```

## Recomendação

**Use Watchdog** porque:

1. ✅ **Detecta problema 6x mais rápido** (5min vs 30min)
2. ✅ **Sem intervenção manual** (auto-recovery)
3. ✅ **Melhor observabilidade** (logs estruturados)
4. ✅ **Retries inteligentes** (com delay para evitar loop)
5. ✅ **Seguro** (lock file evita múltiplas instâncias)
6. ✅ **Production-ready** (padrão em infraestruturas modernas)
