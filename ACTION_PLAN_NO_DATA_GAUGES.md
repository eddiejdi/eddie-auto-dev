# 🔴 **PLANO DE AÇÃO IMEDIATO — CORRIGIR 13 GAUGES SEM DADOS**

**Data:** 24 de fevereiro de 2026  
**Status:** 8 métricas faltando no Prometheus + 11 painéis sem queries

---

## 📊 **DIAGNÓSTICO FINAL**

```
🔴 MÉTRICAS COMPLETAMENTE FALTANDO (8):
  ❌ agent_count_total
  ❌ message_rate_total
  ❌ conversation_count_total
  ❌ active_conversations_total
  ❌ agent_memory_decisions_total
  ❌ ipc_pending_requests
  ❌ agent_confidence_score
  ❌ agent_feedback_score

⚪ PAINÉIS SEM QUERIES (11):
  Dependem das métricas acima para funcionar
```

---

## ✅ **SOLUÇÃO — 3 FASES**

### **FASE 1: ADICIONAR 3 MÉTRICAS CRÍTICAS** (Hoje ~ 2h)

Estas são as mais importantes e têm código pronto:

#### **1️⃣ Métrica: `agent_count_total`**

**Arquivo:** `specialized_agents/agent_manager.py`

**Localizar esta seção (procure por "class AgentManager"):**
```python
class AgentManager:
    def __init__(self):
        # ... código existente ...
```

**Adicionar ANTES de `__init__` (na seção de imports, linha 1-30):**
```python
from prometheus_client import Gauge

# ============ MÉTRICAS PROMETHEUS ============
agents_gauge = Gauge(
    'agent_count_total',
    'Número de agentes especializados ativos',
    ['language']
)
```

**Dentro de `__init__`, adicionar:**
```python
def __init__(self):
    # ... código existente ...
    self.active_agents = {}  # CERTIFIQUE-SE QUE EXISTE
```

**Criar novo método (adicionar no final da classe):**
```python
def _update_agent_metrics(self):
    """Atualiza métricas de agentes no Prometheus"""
    try:
        # Contar por linguagem
        by_language = {}
        for agent_id, agent in self.active_agents.items():
            lang = getattr(agent, 'language', 'unknown')
            by_language[lang] = by_language.get(lang, 0) + 1
        
        # Atualizar gauge por linguagem
        for lang, count in by_language.items():
            agents_gauge.labels(language=lang).set(count)
        
        # Total
        total = sum(by_language.values())
        agents_gauge.labels(language='total').set(total)
    except Exception as e:
        print(f"❌ Erro ao atualizar métricas: {e}")
```

**Chamar em 2 lugares (procure por essas funções e adicione a chamada):**

```python
# No método start_agent()
def start_agent(self, ...):
    # ... código de início ...
    self.active_agents[agent_id] = agent  # Certifique-se que existe
    self._update_agent_metrics()  # ADICIONAR ESTA LINHA

# No método stop_agent()
def stop_agent(self, agent_id):
    # ... código de parada ...
    if agent_id in self.active_agents:
        del self.active_agents[agent_id]
    self._update_agent_metrics()  # ADICIONAR ESTA LINHA
```

---

#### **2️⃣ Métrica: `message_rate_total`**

**Arquivo:** `specialized_agents/agent_interceptor.py`

**Adicionar ANTES da classe (imports, linha 1-30):**
```python
from prometheus_client import Counter

# ============ MÉTRICAS PROMETHEUS ============
message_counter = Counter(
    'message_rate_total',
    'Total de mensagens processadas',
    ['message_type', 'status']
)
```

**Dentro de `publish()` (procure por `def publish`):**
```python
def publish(self, message_type, source, target, content, metadata=None):
    """Publica mensagem no bus"""
    try:
        # ... código existente de publicação ...
        
        # ADICIONAR ESTAS LINHAS (após publicação bem-sucedida):
        message_counter.labels(
            message_type=message_type,
            status='success'
        ).inc()
        
    except Exception as e:
        # ADICIONAR ANTES DO RAISE:
        message_counter.labels(
            message_type=message_type,
            status='error'
        ).inc()
        raise e
```

---

#### **3️⃣ Métrica: `conversation_count_total`**

**Arquivo:** `specialized_agents/agent_interceptor.py`

**Adicionar ao imports (junto com message_counter):**
```python
from prometheus_client import Counter, Gauge

# Métrica de conversas
conversation_gauge = Gauge(
    'conversation_count_total',
    'Total de conversas por tipo de agente',
    ['agent_type']
)
```

**Dentro de `log_request()` ou método que registra conversas:**
```python
def log_request(self, ...):
    # ... código existente ...
    
    # ADICIONAR (após registrar conversa):
    agent_type = metadata.get('agent_type', 'unknown') if metadata else 'unknown'
    conversation_gauge.labels(agent_type=agent_type).inc()
```

---

### **VALIDAR FASE 1:**

```bash
# 1. Reiniciar serviço
sudo systemctl restart specialized-agents-api

# 2. Aguardar 5 segundos
sleep 5

# 3. Testar métricas
curl -s http://192.168.15.2:9090/api/v1/query?query=agent_count_total | jq '.data.result | length'
curl -s http://192.168.15.2:9090/api/v1/query?query=message_rate_total | jq '.data.result | length'
curl -s http://192.168.15.2:9090/api/v1/query?query=conversation_count_total | jq '.data.result | length'

# 4. Se retornar >0, está funcionando ✅
# Se retornar 0, checar logs: journalctl -u specialized-agents-api -f
```

---

### **FASE 2: CONFIGURAR 11 QUERIES NO GRAFANA** (Próxima semana ~ 2h)

**URL:** https://grafana.rpa4all.com/d/eddie-central/

**Procedimento:**
1. Abrir dashboard
2. Clicar em **Edit** (ou Ctrl+E)
3. Para cada panel abaixo:
   - Clicar no panel
   - Tab **Query**
   - Adicionar PromQL
   - **Apply**
4. **Save** (Ctrl+S)

#### **Queries Necessárias:**

| Panel ID | Título | PromQL |
|----------|--------|--------|
| 409 | 🤖 Copilot — Atendimentos 24h | `sum(increase(conversation_count_total{agent_type="copilot"}[24h]))` |
| 410 | 🤖 Copilot — Total Acumulado | `sum(conversation_count_total{agent_type="copilot"})` |
| 411 | ⚙️ Agentes Locais — Atendimentos 24h | `sum(increase(conversation_count_total{agent_type!="copilot"}[24h]))` |
| 412 | ⚙️ Agentes Locais — Total Acumulado | `sum(conversation_count_total{agent_type!="copilot"})` |
| 13 | Total Mensagens | `sum(message_rate_total)` |
| 14 | Conversas | `sum(conversation_count_total)` |
| 406 | Conversas (24h) | `sum(increase(conversation_count_total[24h]))` |
| 15 | Decisões (Memória) | `sum(agent_memory_decisions_total)` |
| 16 | IPC Pendentes | `sum(ipc_pending_requests)` |
| 26 | Confiança Média | `avg(agent_confidence_score)` |
| 27 | Feedback Médio | `avg(agent_feedback_score)` |

---

### **FASE 3: ADICIONAR MÉTRICAS FALTANTES** (Próxima semana ~2-3h)

As últimas 5 métricas precisam ser criadas em seus respectivos módulos:

#### **4️⃣ `active_conversations_total`** (Gauge)
```python
# Arquivo: specialized_agents/agent_interceptor.py
from prometheus_client import Gauge

active_conv_gauge = Gauge('active_conversations_total', 'Conversas ativas')

# Chamar periodicamente (ex: a cada minuto):
def update_active_conversations(self):
    count = len([c for c in self.conversations.values() if c.is_active])
    active_conv_gauge.set(count)
```

#### **5️⃣ `agent_memory_decisions_total`** (Gauge)
```python
# Arquivo: specialized_agents/language_agents.py
from prometheus_client import Gauge

memory_decisions_gauge = Gauge('agent_memory_decisions_total', 'Decisões em memória')

# Chamar ao atualizar memória:
def update_memory_metrics(self):
    count = len(self.memory_database)
    memory_decisions_gauge.set(count)
```

#### **6️⃣ `ipc_pending_requests`** (Gauge)
```python
# Arquivo: tools/agent_ipc.py ou specialized_agents/agent_communication_bus.py
from prometheus_client import Gauge

ipc_pending_gauge = Gauge('ipc_pending_requests', 'Requisições IPC pendentes')

# Chamar ao verificar fila:
def update_ipc_metrics(self):
    pending = len([r for r in self.queue if not r.is_completed])
    ipc_pending_gauge.set(pending)
```

#### **7️⃣ `agent_confidence_score`** (Gauge com labels)
```python
# Arquivo: specialized_agents/language_agents.py
from prometheus_client import Gauge

confidence_gauge = Gauge('agent_confidence_score', 'Confiança dos agentes', ['agent_id'])

# Chamar após decisão:
def update_confidence(self, agent_id, score):
    confidence_gauge.labels(agent_id=agent_id).set(score)
```

#### **8️⃣ `agent_feedback_score`** (Gauge com labels)
```python
# Arquivo: specialized_agents/language_agents.py
from prometheus_client import Gauge

feedback_gauge = Gauge('agent_feedback_score', 'Feedback dos agentes', ['agent_id'])

# Chamar após receber feedback:
def update_feedback(self, agent_id, score):
    feedback_gauge.labels(agent_id=agent_id).set(score)
```

---

## 🎯 **RESUMO DA AÇÃO**

```
HOJE (2-3h):
  ✅ Adicionar agent_count_total
  ✅ Adicionar message_rate_total  
  ✅ Adicionar conversation_count_total
  ✅ Testar com validate_eddie_central_api.py
  ← Dashboard passa para 10/20 gauges (50%)

PRÓXIMA SEMANA (2h):
  ✅ Configurar 11 queries no Grafana
  ← Dashboard passa para 18/20 gauges (90%)

DEPOIS (2-3h):
  ✅ Adicionar últimas 5 métricas
  ← Dashboard passa para 20/20 gauges (100%)
```

---

## 🧪 **TESTE APÓS CADA FASE**

```bash
# Validar
python3 validate_eddie_central_api.py

# Monitorar logs
journalctl -u specialized-agents-api -f

# Verificar Prometheus
http://192.168.15.2:9090
```

---

## ❗ **NOTAS IMPORTANTES**

1. **Não modificar código sem `_update_agent_metrics()`** — métricas não vão atualizar
2. **Restart obrigatório** — `sudo systemctl restart specialized-agents-api`
3. **Cache do Grafana** — Pode ser necessário limpar (Ctrl+Shift+Delete)
4. **Testar localmente primeiro** — Antes de fazer push ao repo
5. **Prometheus leva 30s** — Para scrape as novas métricas

