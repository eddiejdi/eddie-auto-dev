# 🔧 Plano de Correção — Eddie Central Dashboard

**Data:** 24 de fevereiro de 2026  
**Status:** ⏳ REQUER AÇÃO (2 de 13 problemas são críticos)

---

## 📋 Sumário Executivo

| Aspecto | Situação |
|---------|----------|
| **Taxa de Sucesso** | 35% (7/20 gauges) |
| **Problemas Críticos** | 2 (métricas faltando) |
| **Painéis Bloqueados** | 11 (sem query) |
| **Tempo Estimado de Correção** | 2-4 horas |
| **Impacto** | ALTO - Monitoramento parcial |

---

## 🔴 Ação Imediata (Hoje) — Crítico

### 1️⃣ Adicionar Métrica `agent_count_total`

**Localização:** `specialized_agents/agent_manager.py`

**Código a adicionar:**

```python
# ============================================
# No topo do arquivo, após imports
# ============================================

from prometheus_client import Gauge, Counter, Histogram

# Definir gauge de agentes ativos
active_agents_gauge = Gauge(
    'agent_count_total',
    'Número de agentes especializados ativos',
    ['language']
)

# ============================================
# Dentro da classe AgentManager
# ============================================

class AgentManager:
    def __init__(self):
        # ... código existente ...
        self.active_agents = {}
        self.last_metrics_update = 0
    
    def start_agent(self, language, agent_id):
        """Inicia um agente e atualiza métrica"""
        # ... código de inicialização ...
        self.active_agents[agent_id] = {
            'language': language,
            'started_at': time.time()
        }
        self._update_agent_metrics()
    
    def stop_agent(self, agent_id):
        """Para um agente e atualiza métrica"""
        # ... código de parada ...
        if agent_id in self.active_agents:
            del self.active_agents[agent_id]
        self._update_agent_metrics()
    
    def _update_agent_metrics(self):
        """Atualiza métricas de Prometheus"""
        try:
            # Contar por linguagem
            by_language = {}
            for agent_id, info in self.active_agents.items():
                lang = info.get('language', 'unknown')
                by_language[lang] = by_language.get(lang, 0) + 1
            
            # Atualizar gauge
            for lang, count in by_language.items():
                active_agents_gauge.labels(language=lang).set(count)
            
            # Total geral
            total = sum(by_language.values())
            active_agents_gauge.labels(language='all').set(total)
        except Exception as e:
            print(f"❌ Erro ao atualizar métricas de agentes: {e}")
```

**Teste de validação:**

```bash
# 1. Reiniciar serviço
sudo systemctl restart specialized-agents-api

# 2. Aguardar 5 segundos
sleep 5

# 3. Verificar métrica
curl http://192.168.15.2:9090/api/v1/query?query=agent_count_total

# 4. Esperado (JSON):
# {
#   "status": "success",
#   "data": {
#     "resultType": "vector",
#     "result": [{ "metric": {"__name__": "agent_count_total"}, "value": [...] }]
#   }
# }
```

---

### 2️⃣ Adicionar Métrica `message_rate_total`

**Localização:** `specialized_agents/agent_interceptor.py`

**Código a adicionar:**

```python
# ============================================
# No topo do arquivo, após imports
# ============================================

from prometheus_client import Counter, Histogram

# Definir counters de mensagens
message_counter = Counter(
    'message_rate_total',
    'Total de mensagens processadas',
    ['message_type', 'status']
)

message_duration = Histogram(
    'message_processing_seconds',
    'Tempo de processamento de mensagens'
)

# ============================================
# Classe AgentInterceptor
# ============================================

class AgentInterceptor:
    def __init__(self):
        # ... código existente ...
        pass
    
    def publish(self, message_type, source, target, content, metadata=None):
        """Publica mensagem no bus e registra métrica"""
        start_time = time.time()
        
        try:
            # ... código de publicação existente ...
            
            # Incrementar contador
            status = "success"
            message_counter.labels(
                message_type=message_type,
                status=status
            ).inc()
            
            # Registrar duração
            duration = time.time() - start_time
            message_duration.observe(duration)
            
        except Exception as e:
            # Registrar erro
            message_counter.labels(
                message_type=message_type,
                status="error"
            ).inc()
            raise
    
    def log_response(self, request_id, source, target, content, metadata=None):
        """Registra resposta e atualiza métricas"""
        # ... código de log existente ...
        
        # Incrementar contador de respostas
        message_counter.labels(
            message_type="response",
            status="success"
        ).inc()
```

**Teste de validação:**

```bash
# 1. Reiniciar serviço
sudo systemctl restart specialized-agents-api
sleep 5

# 2. Gerar algumas mensagens (via Telegram ou teste)
# ... executar algumas operações ...

# 3. Verificar métrica
curl http://192.168.15.2:9090/api/v1/query?query=message_rate_total

# 4. Verificar taxa (mensagens por segundo)
curl 'http://192.168.15.2:9090/api/v1/query?query=rate(message_rate_total[1m])'
```

---

## 🟠 Ação Segundo Plano (Próxima Semana) — Alta

### Adicionar 11 Queries Customizadas ao Grafana

**Dashboard:** Eddie Central  
**Método:** Edit mode → Add queries

#### Grupo A: Atendimentos por Tipo de Agente

**3️⃣ Query: Copilot — Atendimentos 24h**
```promql
sum(increase(conversation_count_total{agent_type="copilot"}[24h]))
```
- **Panel ID:** 409
- **Tipo:** gauge
- **Unidade:** short
- **Ajuste:** Adicionar query usando sumário de last_seen

**4️⃣ Query: Copilot — Total Acumulado**
```promql
sum(conversation_count_total{agent_type="copilot"})
```
- **Panel ID:** 410
- **Tipo:** gauge
- **Unidade:** short

**5️⃣ Query: Agentes Locais — Atendimentos 24h**
```promql
sum(increase(conversation_count_total{agent_type!="copilot"}[24h]))
```
- **Panel ID:** 411
- **Tipo:** gauge
- **Unidade:** short

**6️⃣ Query: Agentes Locais — Total Acumulado**
```promql
sum(conversation_count_total{agent_type!="copilot"})
```
- **Panel ID:** 412
- **Tipo:** gauge
- **Unidade:** short

---

#### Grupo B: Métricas de Comunicação

**7️⃣ Query: Total Mensagens**
```promql
sum(message_rate_total)
```
- **Panel ID:** 13
- **Tipo:** stat
- **Unidade:** short

**8️⃣ Query: Conversas Ativas**
```promql
sum(active_conversations_total)
```
- **Panel ID:** 14
- **Tipo:** stat (pode usar `count(conservation_last_seen)` temporariamente)

**9️⃣ Query: Decisões em Memória**
```promql
sum(agent_memory_decisions_total)
```
- **Panel ID:** 15
- **Tipo:** stat
- **Unidade:** short

**🔟 Query: IPC Pendentes**
```promql
sum(ipc_pending_requests)
```
- **Panel ID:** 16
- **Tipo:** stat
- **Unidade:** short

**1️⃣1️⃣ Query: Confiança Média**
```promql
avg(agent_confidence_score)
```
- **Panel ID:** 26
- **Tipo:** stat
- **Unidade:** percentunit

**1️⃣2️⃣ Query: Feedback Médio**
```promql
avg(agent_feedback_score)
```
- **Panel ID:** 27
- **Tipo:** stat
- **Unidade:** percentunit

**1️⃣3️⃣ Query: Conversas (24h)**
```promql
sum(increase(conversation_count_total[24h]))
```
- **Panel ID:** 406
- **Tipo:** gauge
- **Unidade:** short

---

## 📝 Procedimento de Atualização no Grafana

### Manual (Interface Web)

1. **Acessar Dashboard:**
   ```
   https://grafana.rpa4all.com/d/eddie-central/
   ```

2. **Entrar em Edit mode:**
   - Clique em **Edit** (ou Ctrl+E)

3. **Para cada panel:**
   - Clique no panel
   - Selecione a aba **Query**
   - Adicione PromQL (queries acima)
   - Clique em **Apply**

4. **Salvar Dashboard:**
   - Clique em **Save** (ou Ctrl+S)

### Via API (Programático)

```bash
#!/bin/bash

# Script: update_grafana_panels.sh

GRAFANA_URL="https://grafana.rpa4all.com"
DASHBOARD_UID="eddie-central"
USER="admin"
PASS="Eddie@2026"

# Obter dashboard atual
curl -s "$GRAFANA_URL/api/dashboards/uid/$DASHBOARD_UID" \
  -u $USER:$PASS | jq '.dashboard' > dashboard.json

# Editar panels (usar jq ou Python)
python3 << 'PYTHON'
import json

with open('dashboard.json', 'r') as f:
    dashboard = json.load(f)

# Exemplo: atualizar panel 409 (Copilot 24h)
for panel in dashboard.get('panels', []):
    if panel.get('id') == 409:
        panel['targets'] = [{
            'expr': 'sum(increase(conversation_count_total{agent_type="copilot"}[24h]))',
            'format': 'time_series',
            'intervalFactor': 2,
            'refId': 'A'
        }]

with open('dashboard_updated.json', 'w') as f:
    json.dump(dashboard, f)
PYTHON

# Upload dashboard atualizado
curl -X POST "$GRAFANA_URL/api/dashboards/db" \
  -u $USER:$PASS \
  -H "Content-Type: application/json" \
  -d @dashboard_updated.json
```

---

## 🧪 Plano de Testes

### Teste 1 — Verificar Métricas no Prometheus

```bash
#!/bin/bash

echo "🔍 Verificando métricas no Prometheus..."

# Test agent_count_total
response=$(curl -s http://192.168.15.2:9090/api/v1/query?query=agent_count_total)
if echo $response | jq '.data.result | length' | grep -q '[1-9]'; then
    echo "✅ agent_count_total existe e tem dados"
else
    echo "❌ agent_count_total NÃO tem dados"
fi

# Test message_rate_total
response=$(curl -s http://192.168.15.2:9090/api/v1/query?query=message_rate_total)
if echo $response | jq '.data.result | length' | grep -q '[1-9]'; then
    echo "✅ message_rate_total existe e tem dados"
else
    echo "❌ message_rate_total NÃO tem dados"
fi
```

### Teste 2 — Validar Dashboard após Queries

```bash
python3 validate_eddie_central_api.py

# Esperado:
# ✅ Taxa de sucesso aumenta de 35% para ~65%
# ✅ Apenas 2 problemas permanem (métricas exporters)
```

### Teste 3 — Alertas via Grafana

1. Abrir dashboard Eddie Central
2. Verificar que todos os 20 gauges mostram valores
3. Validar que não há mensagens de "No data"

---

## 📊 Validação Pós-Implementação

**Script:** `validate_eddie_central_api.py`

```bash
# Executar validação completa
python3 validate_eddie_central_api.py

# Esperado após correções completas:
# ✅ Taxa de sucesso: 100% (20/20 gauges)
```

---

## 📞 Escalação & Suporte

### Casos de Erro

| Erro | Causa | Solução |
|------|-------|---------|
| `agent_count_total` não aparece | Serviço não reiniciado | `sudo systemctl restart specialized-agents-api` |
| Queries retornam "No data" | Métrica não exportada | Verificar `/metrics` do agente |
| Grafana mostra valores antigos | Cache | Limpar cache (Ctrl+Shift+Delete) |
| Panel em branco | Query sintaxe errada | Validar PromQL no `/api/v1/query` |

### Contato

- **Slack:** #eddie-central-dashboard
- **Issues:** Link para GitHub issue (se necessário)
- **On-call:** Verificar rotation

---

## ✅ Checklist de Conclusão

- [ ] **Métrica `agent_count_total` adicionada**
  - [ ] Código implementado
  - [ ] Serviço reiniciado
  - [ ] Validado no Prometheus
  - [ ] Dashboard mostra valor

- [ ] **Métrica `message_rate_total` adicionada**
  - [ ] Código implementado
  - [ ] Serviço reiniciado
  - [ ] Validado no Prometheus
  - [ ] Dashboard mostra valor

- [ ] **11 Queries customizadas adicionadas**
  - [ ] Queries validadas no Prometheus
  - [ ] Panels no Grafana atualizados
  - [ ] Dashboard salvo
  - [ ] Sem erros visuais

- [ ] **Testes finais**
  - [ ] Validação passa (100% sucesso)
  - [ ] Alertas configurados (opcional)
  - [ ] Documentação atualizada
  - [ ] Relatório final gerado

---

**Última atualização:** 2026-02-24 10:26:33 UTC  
**Próxima revisão:** Após implementação das correções
**Status:** ⏳ PENDENTE

