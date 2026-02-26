# 🧠 Agent Memory System

Sistema de memória persistente para agentes que permite aprendizado incremental e tomada de decisões informadas baseadas em experiências passadas.

## 📋 Visão Geral

O Agent Memory System armazena decisões, contextos e resultados em PostgreSQL, permitindo que agentes:

- 🔍 **Lembrem** de decisões anteriores para contextos similares
- 📈 **Aprendam** com sucessos e falhas
- 🚫 **Evitem** repetir erros do passado
- 💡 **Tomem decisões** mais confiantes baseadas em experiência acumulada

## 🏗️ Arquitetura

┌─────────────────────────────────────────────────┐
│           SpecializedAgent                      │
│  ┌──────────────────────────────────────┐      │
│  │  make_informed_decision()            │      │
│  │   ├─ recall_past_decisions()         │      │
│  │   ├─ Consulta LLM + contexto        │      │
│  │   └─ should_remember_decision()      │      │
│  └──────────────────────────────────────┘      │
│                    ▼                             │
│  ┌──────────────────────────────────────┐      │
│  │  AgentMemory                          │      │
│  │   ├─ record_decision()               │      │
│  │   ├─ recall_similar_decisions()      │      │
│  │   ├─ update_decision_outcome()       │      │
│  │   ├─ learn_pattern()                 │      │
│  │   └─ get_decision_statistics()       │      │
│  └──────────────────────────────────────┘      │
└─────────────────────┬───────────────────────────┘
                      ▼
        ┌─────────────────────────────┐
        │  PostgreSQL Database        │
        │  ┌────────────────────────┐ │
        │  │  agent_memory          │ │
        │  │  - decisions           │ │
        │  │  - contexts            │ │
        │  │  - outcomes            │ │
        │  │  - feedbacks           │ │
        │  └────────────────────────┘ │
        │  ┌────────────────────────┐ │
        │  │  agent_learned_patterns│ │
        │  │  - pattern_type        │ │
        │  │  - occurrences         │ │
        │  │  - success_rate        │ │
        │  │  - confidence          │ │
        │  └────────────────────────┘ │
        └─────────────────────────────┘
## 🚀 Uso Rápido

### 1. Configuração

```bash
# Configure DATABASE_URL (obrigatório)
export DATABASE_URL="postgresql://postgress:eddie_memory_2026@192.168.15.2:5432/postgres"
Environment="DATABASE_URL=postgresql://postgress:eddie_memory_2026@192.168.15.2:5432/postgres"
Environment="DATABASE_URL=postgresql://postgress:postgres@localhost:5432/postgres"
Environment="DATABASE_URL=postgresql://postgress:eddie_memory_2026@192.168.15.2:5432/postgres"
### 2. Uso Básico

from specialized_agents.language_agents import PythonAgent

# Criar agente (já vem com memória integrada)
agent = PythonAgent()

# Registrar uma decisão
decision_id = agent.should_remember_decision(
    application="my-api",
    component="auth-service",
    error_type="token_expired",
    error_message="JWT token expired after 5 minutes",
    decision_type="fix",
    decision="Increase token lifetime to 30 minutes",
    reasoning="Short expiration causing excessive re-auth",
    confidence=0.8
)

# Buscar decisões similares
past_decisions = agent.recall_past_decisions(
    application="my-api",
    component="auth-service",
    error_type="token_expired",
    error_message="JWT token expired after 5 minutes"
)

# Atualizar resultado após deploy
agent.update_decision_feedback(
    decision_id=decision_id,
    success=True,
    details={"re_auth_reduced_by": "90%"}
)
### 3. Decisão Informada (LLM + Memória)

# Tomar decisão consultando memória automaticamente
decision = await agent.make_informed_decision(
    application="payment-service",
    component="processor",
    error_type="memory_leak",
    error_message="Memory grows to 2GB after 1000 requests",
    context={"current_usage": "2GB", "requests": 1000}
)

print(f"Decisão: {decision['decision']}")
print(f"Confiança: {decision['confidence']}")
print(f"Experiências consultadas: {decision['past_experiences']}")
## 📚 API Completa

### AgentMemory

#### `record_decision()`
Registra uma decisão tomada pelo agente.

decision_id = memory.record_decision(
    application="app-name",
    component="component-name",
    error_type="error-type",
    error_message="error message",
    decision_type="deploy|reject|fix|analyze|investigate",
    decision="What was decided",
    reasoning="Why this decision",
    confidence=0.0-1.0,
    context_data={"key": "value"},
    metadata={"any": "data"}
)
#### `recall_similar_decisions()`
Busca decisões similares na memória.

similar = memory.recall_similar_decisions(
    application="app-name",
    component="component-name",
    error_type="error-type",
    error_message="error message",
    limit=5,
    min_confidence=0.3,
    days_back=90
)
#### `update_decision_outcome()`
Atualiza o resultado de uma decisão.

memory.update_decision_outcome(
    decision_id=123,
    outcome="success|failure|partial",
    outcome_details={"what": "happened"},
    feedback_score=-1.0 to 1.0
)
#### `learn_pattern()`
Aprende um padrão recorrente.

memory.learn_pattern(
    pattern_type="error_recovery",
    pattern_data={"solution": "retry_with_backoff"},
    success=True
)
#### `get_decision_statistics()`
Obtém estatísticas agregadas.

stats = memory.get_decision_statistics(
    application="app-name",
    component="component-name",
    days_back=30
)
# Returns: total_decisions, success_count, avg_confidence, etc.
### SpecializedAgent (métodos adicionados)

#### `should_remember_decision()`
Registra decisão na memória do agente.

#### `recall_past_decisions()`
Busca decisões similares.

#### `make_informed_decision()`
Toma decisão consultando memória + LLM.

#### `update_decision_feedback()`
Atualiza feedback após ver resultado.

## 🎯 Casos de Uso

### 1. Evitar Repetir Deploy com Erro Conhecido

# Buscar histórico
past = agent.recall_past_decisions(app, comp, error, msg)

# Se houve falha anterior com mesmo erro
if any(d['outcome'] == 'failure' and d['decision_type'] == 'deploy' 
       for d in past):
    print("⚠️ Deploy anterior falhou com este erro!")
    decision = "investigate"  # Não repetir erro
### 2. Aumentar Confiança com Experiência

# Primeira vez: baixa confiança
agent.should_remember_decision(..., confidence=0.5)

# Após sucesso
agent.update_decision_feedback(dec_id, success=True)

# Próxima decisão similar: maior confiança baseada em histórico
### 3. Aprendizado de Padrões

# Registrar padrão bem-sucedido
agent.memory.learn_pattern(
    pattern_type="deployment_check",
    pattern_data={"check": "memory_usage", "threshold": "1GB"},
    success=True
)

# Após várias ocorrências, o padrão ganha confiança
patterns = agent.memory.get_learned_patterns(min_confidence=0.7)
## 🧪 Testes

```bash
# Configurar DATABASE_URL
export DATABASE_URL="postgresql://postgress:eddie_memory_2026@192.168.15.2:5432/postgres"

# Testes unitários
python3 test_agent_memory.py

# Exemplo prático
python3 example_agent_memory.py
## 📊 Schema do Banco

### Tabela `agent_memory`
```sql
- id (SERIAL PRIMARY KEY)
- created_at (TIMESTAMP)
- agent_name (TEXT) -- ex: "python_agent"
- application (TEXT)
- component (TEXT)
- error_type (TEXT)
- error_signature (TEXT) -- hash para busca rápida
- context_data (JSONB)
- decision_type (TEXT) -- deploy, reject, fix, analyze
- decision (TEXT)
- reasoning (TEXT)
- confidence (FLOAT)
- outcome (TEXT) -- success, failure, unknown
- outcome_details (JSONB)
- feedback_score (FLOAT) -- -1.0 a 1.0
### Tabela `agent_learned_patterns`
```sql
- id (SERIAL PRIMARY KEY)
- agent_name (TEXT)
- pattern_type (TEXT)
- pattern_signature (TEXT UNIQUE)
- pattern_data (JSONB)
- occurrences (INT)
- success_count (INT)
- failure_count (INT)
- confidence (FLOAT) -- calculado automaticamente
- last_seen_at (TIMESTAMP)
## 🔍 Busca e Indexação

O sistema usa múltiplas estratégias de busca:

1. **Busca exata por signature** (hash do erro): Mais rápida
2. **Busca por aplicação + componente + tipo**: Mais flexível
3. **Filtros de confiança e tempo**: Ignora decisões antigas/ruins

Índices criados automaticamente:
- `idx_agent_memory_agent`
- `idx_agent_memory_app_comp`
- `idx_agent_memory_error_sig`
- `idx_agent_memory_decision`

## ⚙️ Configuração Avançada

### Ajustar Parâmetros de Busca

similar = memory.recall_similar_decisions(
    ...,
    limit=10,              # Mais resultados
    min_confidence=0.6,    # Apenas decisões confiáveis
    days_back=180          # Buscar histórico mais longo
)
### Integração com Systemd Services

Adicione `DATABASE_URL` nos drop-ins:

```bash
# /etc/systemd/system/specialized-agents-api.service.d/env.conf
[Service]
Environment="DATABASE_URL=postgresql://postgress:postgres@localhost:5432/postgres"
```bash
sudo systemctl daemon-reload
sudo systemctl restart specialized-agents-api
## 📈 Métricas e Monitoramento

# Estatísticas por aplicação
stats = agent.memory.get_decision_statistics(
    application="my-app",
    days_back=30
)

print(f"Taxa de sucesso: {stats['successes']}/{stats['total_decisions']}")
print(f"Confiança média: {stats['avg_confidence']:.2f}")
print(f"Erros únicos: {stats['unique_errors']}")
## 🚨 Troubleshooting

### Erro: `DATABASE_URL not set`
```bash
export DATABASE_URL="postgresql://user:pass@host:5432/db"
### Erro: `connection refused`
```bash
# Verificar se Postgres está rodando
docker ps | grep postgres

# Testar conectividade
nc -zv 192.168.15.2 5432
### Memória não disponível em agente
if not agent.memory:
    print("⚠️ Memória não configurada")
    # Verificar DATABASE_URL e dependências
## 📝 Boas Práticas

1. ✅ **Sempre registre decisões importantes** (deploy, reject, fix)
2. ✅ **Atualize feedback** após ver resultado (sucesso/falha)
3. ✅ **Use `make_informed_decision()`** para decisões críticas
4. ✅ **Monitore estatísticas** periodicamente
5. ✅ **Ajuste `confidence`** baseado em certeza real
6. ⚠️ **Não registre decisões triviais** (para evitar poluir memória)
7. ⚠️ **Lembre de `context_data`** para decisões complexas

## 🔗 Integração com Outros Componentes

- **Agent Communication Bus**: Decisões são logadas no bus automaticamente
- **RAG Manager**: Complementa com busca semântica de código
- **Metrics Exporter**: Estatísticas podem ser exportadas para Prometheus
- **Diretor**: Pode consultar memória para aprovar/rejeitar decisões

## 📖 Exemplos Completos

Veja `example_agent_memory.py` para exemplos práticos:
- Decisão de deploy informada por memória
- Aprendizado com erros repetidos
- Consulta de estatísticas

---

**Autor**: Eddie Auto-Dev Team  
**Data**: 2026-02-03  
**Versão**: 1.0.0
