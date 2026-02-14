# 🛡️ Sistema de Processamento Seguro de Vagas WhatsApp

## Problema Identificado
O processamento de mensagens do WhatsApp estava causando **queda do servidor** devido à sobrecarga. O sistema processava muitas mensagens simultaneamente sem controles adequados.

## ✅ Soluções Implementadas

### 1. **Verificações de Saúde Automáticas**
- ✅ Conectividade SSH
- ✅ Serviços críticos (WAHA, Ollama, Docker)
- ✅ Uso de memória (<90%)
- ✅ Uso de CPU (<80%)
- ✅ Espaço em disco (<90%)
- ✅ Status WAHA (WORKING)

### 2. **Controles de Rate Limiting**
- ✅ **Máximo 5 mensagens por execução** (`MAX_MESSAGES_PER_RUN=5`)
- ✅ **10 segundos entre jobs** (`DELAY_BETWEEN_JOBS=10`)
- ✅ **Verificações de saúde a cada 30s** (`HEALTH_CHECK_INTERVAL=30`)
- ✅ **Circuit breaker** (para após 3 falhas consecutivas)

### 3. **Modo Seguro One-by-One**
```bash
# Processamento gradual e seguro
./safe_process.sh --process-one-by-one
```

### 4. **Sistema de Recuperação Automática**
```bash
# Tenta restaurar conectividade automaticamente
./recover_homelab.sh
```

## 🚀 Como Usar

### Pré-requisitos
1. **Servidor homelab ligado** (192.168.15.2)
2. **WhatsApp conectado** na sessão WAHA
3. **Chave API WAHA** configurada

### Fluxo de Uso Seguro

```bash
# 1. Verificar saúde do sistema
./health_check.sh

# 2. Se necessário, recuperar conectividade
./recover_homelab.sh

# 3. Processar mensagens de forma segura
./safe_process.sh --process-one-by-one

# 4. Monitorar logs em tempo real
tail -f /tmp/email_logs/email_log.txt
```

### Scripts Disponíveis

| Script | Função | Quando Usar |
|--------|--------|-------------|
| `health_check.sh` | Verifica saúde completa | Antes de qualquer processamento |
| `recover_homelab.sh` | Restaura conectividade | Quando servidor está offline |
| `safe_process.sh` | Processamento seguro | Para executar jobs |
| `apply_real_job.py` | Script principal | Via wrapper seguro |

## ⚙️ Configurações de Segurança

### Variáveis de Ambiente
```bash
# Máximo de mensagens por execução
export MAX_MESSAGES_PER_RUN=5

# Delay entre jobs (segundos)
export DELAY_BETWEEN_JOBS=10

# Intervalo de verificação de saúde
export HEALTH_CHECK_INTERVAL=30

# Threshold para circuit breaker
export CIRCUIT_BREAKER_THRESHOLD=3
```

### Timeouts e Limites
- **Timeout SSH:** 5-10 segundos
- **Timeout processamento:** 30 minutos máximo
- **Verificações:** A cada 30 segundos durante processamento
- **Circuit breaker:** Ativa após 3 falhas em 5 minutos

## 🔍 Monitoramento

### Logs em Tempo Real
```bash
# Logs do processamento
tail -f /tmp/email_logs/email_log.txt

# Logs de auditoria (homelab)
ssh homelab@192.168.15.2 "tail -f /home/homelab/message_audit_*.log"
```

### Métricas de Saúde
```bash
# Uso de recursos
ssh homelab@192.168.15.2 "htop"

# Status WAHA
ssh homelab@192.168.15.2 "curl -s -H 'X-Api-Key: 757fae2686eb44479b9a34f1b62dbaf3' 'http://localhost:3001/api/sessions' | jq ."
```

## 🚨 Sinais de Alerta

### Interromper Imediatamente Se:
- ❌ **Ping falha** para 192.168.15.2
- ❌ **SSH timeout**
- ❌ **Uso de memória >90%**
- ❌ **Uso de CPU >80%**
- ❌ **WAHA retorna erros 5xx**

### Ações de Emergência
```bash
# Parar todos os processos
ssh homelab@192.168.15.2 "pkill -f apply_real_job"

# Reiniciar serviços
ssh homelab@192.168.15.2 "sudo systemctl restart waha ollama"

# Liberar memória
ssh homelab@192.168.15.2 "sudo sync && sudo echo 3 > /proc/sys/vm/drop_caches"
```

## 📊 Resultados Esperados

### Com as Otimizações:
- ✅ **Sem quedas de servidor**
- ✅ **Processamento gradual**
- ✅ **Recuperação automática**
- ✅ **Monitoramento contínuo**
- ✅ **Taxa de sucesso >95%**

### Métricas de Segurança:
- 🔒 **Rate limiting:** 5 jobs/10s delays
- 🔒 **Health checks:** 30s intervalos
- 🔒 **Circuit breaker:** 3 falhas threshold
- 🔒 **Timeout protection:** 30min máximo

## 🎯 Benefícios

1. **Estabilidade:** Servidor não cai mais
2. **Confiabilidade:** Recuperação automática
3. **Segurança:** Múltiplas camadas de proteção
4. **Monitoramento:** Visibilidade completa do estado
5. **Escalabilidade:** Processamento gradual e controlado

---

**Status:** ✅ **SISTEMA OTIMIZADO E SEGURO**

**Próximo passo:** Execute `./safe_process.sh --process-one-by-one` quando o servidor estiver estável.