# Arquitetura do Sistema de Auto-Aprendizado

**Documento de Referência v4.0** — Como o Shared Auto-Dev aprende, persiste conhecimento e melhora decisões.

---

## Visão Geral

O sistema de aprendizado é multi-camadas, persistindo em PostgreSQL + ChromaDB com 3 fluxos principais:

1. **Agent Memory** — Histórico de decisões + padrões aprendidos (PostgreSQL)
2. **RAG (Retrieval-Augmented Generation)** — Conhecimento semântico indexado (ChromaDB + embeddings)
3. **Decision Tracking** — Feedback e resultados de ações para calibração contínua

```
┌─────────────────────────────────────────────────────────────┐
│                   SISTEMA DE APRENDIZADO                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  INPUT                                                       │
│  ├─ Decisões do Agente (error_type, ação, confiança)       │
│  ├─ Resultados (sucesso/falha, feedback_score)             │
│  └─ Padrões recorrentes (aplicação, componente, erro)      │
│                                                               │
│  CAMADA DE PERSISTÊNCIA                                      │
│  ├─ Agent Memory (PostgreSQL)                               │
│  │  ├─ Tabela: agent_memory                                 │
│  │  │  └─ (id, created_at, application, component,         │
│  │  │     error_type, decision, outcome, feedback_score)    │
│  │  └─ Tabela: agent_learned_patterns                       │
│  │     └─ (pattern_type, pattern_signature, confidence,     │
│  │        occurrences, success_count)                       │
│  │                                                            │
│  ├─ RAG Manager (ChromaDB)                                   │
│  │  ├─ Collections por linguagem (8 idiomas)                │
│  │  ├─ agent_python_knowledge                               │
│  │  ├─ agent_javascript_knowledge                           │
│  │  └─ ... (TypeScript, Go, Rust, Java, C#, PHP)           │
│  │                                                            │
│  └─ Semantic Embeddings                                      │
│     ├─ all-MiniLM-L6-v2 (sentence-transformers)             │
│     ├─ nomic-embed-text (Ollama)                            │
│     └─ Query vectorization: normalize + cosine similarity   │
│                                                               │
│  PROCESSAMENTO & ÍNDICES                                     │
│  ├─ TF-IDF Scoring (compatibilidade léxica)                │
│  ├─ Semantic Search (compatibilidade semântica)             │
│  ├─ Hybrid Scoring (70% semântica + 30% TF-IDF)            │
│  └─ Pattern Recognition (hash-based deduplication)         │
│                                                               │
│  OUTPUT & APLICAÇÃO                                          │
│  ├─ Recall Similar Decisions (buscar histórico)             │
│  ├─ Get Learned Patterns (padrões com confiança > 0.6)     │
│  ├─ Context Augmentation (RAG para prompts)                │
│  └─ Statistical Dashboard (métricas de desempenho)          │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. Agent Memory — Persistência de Decisões

### Estrutura de Dados

**Tabela: `agent_memory`**
```sql
CREATE TABLE agent_memory (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    agent_name TEXT NOT NULL,
    
    -- Contexto da decisão
    application TEXT,                    -- "my-app", "system", etc
    component TEXT,                      -- "auth", "payment", "cache"
    error_type TEXT,                     -- "timeout", "memory_leak", "permission"
    error_signature TEXT UNIQUE,         -- SHA256 hash do erro (busca rápida)
    context_data JSONB,                  -- Dados adicionais (stack, env, etc)
    
    -- Decisão tomada
    decision_type TEXT NOT NULL,         -- "deploy" | "reject" | "fix" | "analyze"
    decision TEXT NOT NULL,              -- Descrição da ação
    reasoning TEXT,                      -- Justificativa
    confidence FLOAT DEFAULT 0.5,        -- 0.0 a 1.0
    
    -- Resultado da decisão
    outcome TEXT,                        -- "success" | "failure" | "unknown"
    outcome_details JSONB,               -- Detalhes do resultado
    feedback_score FLOAT,                -- -1.0 a 1.0 (feedback externo)
    
    -- Metadados
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Índices principais
CREATE INDEX idx_agent_memory_agent ON agent_memory(agent_name);
CREATE INDEX idx_agent_memory_app_comp ON agent_memory(application, component);
CREATE INDEX idx_agent_memory_error_sig ON agent_memory(error_signature);  -- CRÍTICO
CREATE INDEX idx_agent_memory_decision ON agent_memory(decision_type);
CREATE INDEX idx_agent_memory_created ON agent_memory(created_at DESC);
```

**Tabela: `agent_learned_patterns`**
```sql
CREATE TABLE agent_learned_patterns (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    agent_name TEXT NOT NULL,
    
    -- Padrão
    pattern_type TEXT NOT NULL,          -- "error_recovery", "deployment_check", etc
    pattern_signature TEXT UNIQUE NOT NULL,  -- SHA256 hash do padrão
    pattern_data JSONB NOT NULL,         -- Dados estruturados do padrão
    
    -- Estatísticas
    occurrences INT DEFAULT 1,           -- Quantas vezes visto
    success_count INT DEFAULT 0,         -- Aplicações bem-sucedidas
    failure_count INT DEFAULT 0,         -- Aplicações falhadas
    confidence FLOAT DEFAULT 0.5,        -- success_count / (success_count + failure_count)
    last_seen_at TIMESTAMP WITH TIME ZONE
);
```

### API de Memória

**Registrar Decisão:**
```python
from specialized_agents.agent_memory import get_agent_memory

memory = get_agent_memory("python_agent")

decision_id = memory.record_decision(
    application="my-app",
    component="auth",
    error_type="timeout",
    error_message="DB connection timeout after 5s",
    decision_type="fix",
    decision="Increase timeout to 30s",
    reasoning="Transient DB load observed; increase timeout is safe",
    confidence=0.85,
    context_data={"db_load": "high", "retry_count": 3},
    metadata={"version": "1.2.0"}
)
# Retorna: ID do registro criado
```

**Buscar Decisões Similares:**
```python
similar = memory.recall_similar_decisions(
    application="my-app",
    component="auth",
    error_type="timeout",
    error_message="DB connection timeout after 5s",
    limit=5,
    min_confidence=0.3,
    days_back=90
)
# Retorna: Lista de decisões similares ordenadas por confiança
# Ex: [
#   {"id": 42, "decision": "Increase timeout to 30s", "confidence": 0.85, "outcome": "success"},
#   {"id": 41, "decision": "Add retry logic", "confidence": 0.7, "outcome": "partial"}
# ]
```

**Aprender Padrão:**
```python
memory.learn_pattern(
    pattern_type="error_recovery",
    pattern_data={
        "error": "timeout",
        "recovery": "increase_timeout",
        "params": {"old": 5, "new": 30}
    },
    success=True  # Indica se a aplicação do padrão foi bem-sucedida
)
# Atualiza: occurrences, success_count, confidence (auto-calculado)
```

**Recuperar Padrões Aprendidos:**
```python
patterns = memory.get_learned_patterns(
    pattern_type="error_recovery",
    min_confidence=0.6,        # Só padrões confiáveis
    min_occurrences=2          # Visto pelo menos 2x
)
# Retorna: Padrões que podem ser aplicados automaticamente
```

**Estatísticas:**
```python
stats = memory.get_decision_statistics(
    application="my-app",
    component="auth",
    days_back=30
)
# Retorna: {
#   "total_decisions": 15,
#   "applications_count": 2,
#   "components_count": 1,
#   "unique_errors": 3,
#   "avg_confidence": 0.72,
#   "successes": 12,
#   "failures": 2,
#   "avg_feedback": 0.8,
#   "decisions_by_type": {"fix": 8, "deploy": 5, "reject": 2}
# }
```

---

## 2. RAG Manager — Conhecimento Semântico por Linguagem

### Conceito

Cada linguagem tem sua própria coleção ChromaDB com:
- **Código indexado** — Snippets de código com comentários
- **Documentação** — MDLs, READMEs, tutoriais
- **Q&A** — Conversas resolvidas (pergunta + resposta)

### Estrutura

**ChromaDB Collections:**
```
chroma_db/
├── python/
│   ├── chromadb/
│   │   └── data.db  (collection: agent_python_knowledge)
│   └── export_*.json
├── javascript/
│   ├── chromadb/
│   │   └── data.db  (collection: agent_javascript_knowledge)
│   └── export_*.json
├── typescript/
├── go/
├── rust/
├── java/
├── csharp/
└── php/
```

### API do RAG

**Indexar Código:**
```python
from specialized_agents.rag_manager import RAGManagerFactory

python_rag = RAGManagerFactory.get_manager("python")

await python_rag.index_code(
    code="""
async def fetch_user(user_id: str) -> Dict:
    try:
        result = await db.query(User).filter_by(id=user_id).first()
        return result.to_dict()
    except TimeoutError:
        logger.warning(f"DB timeout for user {user_id}")
        return None
""",
    language="python",
    description="User fetch with timeout handling",
    source_id="module_users_v2",
    metadata={"source_file": "app/models/user.py", "version": "2.0"}
)
```

**Indexar Documentação:**
```python
await python_rag.index_documentation(
    content="""# FastAPI Best Practices
1. Use dependency injection for DB connections...
2. Always set timeouts on external calls...
""",
    title="FastAPI Best Practices",
    source="internal_wiki",
    metadata={"author": "team", "version": "1.0"}
)
```

**Indexar Q&A:**
```python
await python_rag.index_conversation(
    question="Como implementar retry logic em FastAPI?",
    answer="""Use bibliotecas como 'tenacity':
from tenacity import retry, stop_after_attempt

@retry(stop=stop_after_attempt(3))
async def query_db():
    ...
""",
    context="DB connection issues",
    metadata={"category": "error_handling"}
)
```

**Buscar:**
```python
# Busca simples
documents = await python_rag.search(
    query="Como lidar com timeouts em BD?",
    n_results=5,
    doc_type="code"  # Filtro opcional
)
# Retorna: [doc1, doc2, ...]

# Busca com metadados
results = await python_rag.search_with_metadata(
    query="Retry logic",
    n_results=3
)
# Retorna: [
#   {"content": "...", "metadata": {...}, "score": 0.95},
#   {"content": "...", "metadata": {...}, "score": 0.87}
# ]
```

**Augmentar Prompts com Contexto:**
```python
context = await python_rag.get_context_for_prompt(
    query="Como validar entrada de usuário?",
    n_results=3
)
# Retorna: String formatada com os 3 melhores resultados
# Uso: f"Contexto relevante:\n{context}\n\nPergunta do usuário: ..."
```

**Busca Global (Todas as Linguagens):**
```python
global_results = await RAGManagerFactory.global_search(
    query="Padrão de autenticação OAuth2",
    n_results=5
)
# Retorna: Top 5 resultados de todas as linguagens
# [
#   {"content": "...", "language": "javascript", "score": 0.92},
#   {"content": "...", "language": "python", "score": 0.88},
#   ...
# ]
```

---

## 3. Semantic Search — Embeddings e Similaridade

### Fluxo de Embeddings

**Modelos Disponíveis:**

1. **all-MiniLM-L6-v2** (Padrão)
   - Size: ~22MB
   - Dimensão: 384
   - Latência: ~5ms
   - Uso: Geral, multi-idioma
   - Execute: `from sentence_transformers import SentenceTransformer`

2. **nomic-embed-text** (Via Ollama)
   - Size: ~270MB
   - Dimensão: 768
   - Latência: ~20ms
   - Uso: Embeddings mais densos, maior precisão
   - Execute: `POST :11434/api/embeddings`

### Algoritmo de Similaridade

**TF-IDF (Léxical):**
```python
# Tokenização
tokens = ["auth", "timeout", "retry", "db"]

# Term Frequency (TF) — frequência do token no documento
tf = {"auth": 2, "timeout": 1, "retry": 1, "db": 3}

# Inverse Document Frequency (IDF) — raridade do token
idf = log(total_docs / docs_with_token)

# Score final
tfidf_score = cos_similarity(query_tfidf, doc_tfidf)  # 0.0 a 1.0
```

**Semantic (Embeddings):**
```python
# Query: "Como lidar com timeouts?"
query_embedding = embedder.encode(query)  # Shape: (384,)

# Document: "Use retry logic para timeout..."
doc_embedding = embedder.encode(document)  # Shape: (384,)

# Cosine similarity
similarity = cos_similarity([query_embedding], [doc_embedding])  # 0.0 a 1.0
```

**Hybrid (70% Semantic + 30% TF-IDF):**
```python
semantic_score = 0.95  # Ou 95%
tfidf_score = 0.72    # Ou 72%

hybrid_score = (semantic_score * 0.7) + (tfidf_score * 0.3)  # ≈ 0.87 ou 87%
```

### Código de Busca

```python
# compatibility_semantic.py
def compute_compatibility_semantic(resume_text: str, job_text: str) -> Tuple[float, str, Dict]:
    """Busca semântica entre resume e job description"""
    
    model = SentenceTransformer("all-MiniLM-L6-v2")
    
    # Gerar embeddings
    embeddings = model.encode([resume_text, job_text])
    
    # Cosine similarity
    similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
    
    score = round(similarity * 100, 1)  # 0 a 100
    
    return score, f"Semantic similarity: {score}%", {"method": "semantic_embeddings"}


def compute_compatibility_hybrid(resume_text: str, job_text: str) -> Tuple[float, str, Dict]:
    """Hybrid: 70% Semantic + 30% TF-IDF"""
    
    semantic_score = compute_compatibility_semantic(...)[0]
    tfidf_score = compute_compatibility_tfidf_hybrid(...)[0]
    
    final_score = round((semantic_score * 0.7) + (tfidf_score * 0.3), 1)
    
    return final_score, f"Hybrid: {final_score}%", {...}
```

---

## 4. Decision Tracking — Feedback em Tempo Real

### Fluxo de Feedback

**Executor de Trade (BTC Trading Agent):**
```python
# btc_trading_agent/trading_agent.py (linha 650)

signal = self.model.predict(market_state, explore=explore)

# 1. REGISTRAR decisão
decision_id = self.db.record_decision(
    symbol=self.symbol,
    action=signal.action,              # "BUY", "SELL", "HOLD"
    confidence=signal.confidence,      # 0.0 a 1.0
    price=signal.price,                # Preço atual
    reason=signal.reason,              # "Momentum > 0.7"
    features=signal.features           # {rsi: 75, macd: 0.32, ...}
)

# 2. EXECUTAR trade (se viável)
if signal.action != "HOLD" and self._check_can_trade(signal):
    executed = self._execute_trade(signal, market_state.price)
    
    # 3. REGISTRAR resultado
    if executed:
        self.db.mark_decision_executed(decision_id, self.state.total_trades)

# 4. COLETAR feedback posterior
# (Espera N candles e registra resultado de lucro/perda)
outcome, pnl = self._evaluate_decision_outcome(decision_id, lookback_periods=10)
self.db.update_decision_outcome(
    decision_id=decision_id,
    outcome="success" if pnl > 0 else "failure",
    outcome_details={"pnl": pnl, "closing_reason": "tp_hit"},
    feedback_score=pnl / 100  # Normalizar para -1 a 1
)
```

### Banco de Decisões de Trading

```sql
-- Table: trading_decisions (exemplo)
CREATE TABLE trading_decisions (
    id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,                -- "BTC-USDT", "ETH-USDT"
    timestamp TIMESTAMP WITH TIME ZONE,  -- Quando a decisão foi tomada
    
    -- Contexto de mercado
    price_entry FLOAT,
    market_state JSONB,                  -- {rsi: 75, macd: 0.32, volume: 1000}
    
    -- Decisão
    action TEXT,                         -- "BUY", "SELL", "HOLD"
    confidence FLOAT,                    -- 0.0 a 1.0
    reason TEXT,                         -- Justificativa do modelo
    
    -- Execução
    executed BOOLEAN DEFAULT FALSE,
    execution_price FLOAT,
    execution_time TIMESTAMP,
    
    -- Resultado (atualizado depois)
    outcome TEXT,                        -- "success", "failure", "partial", "unknown"
    pnl FLOAT,                          -- Lucro/perda
    feedback_score FLOAT,                -- -1.0 a 1.0
    
    -- Análise
    lookback_periods INT DEFAULT 10,     -- Candles esperados antes de avaliar
    evaluated_at TIMESTAMP
);
```

---

## 5. Pattern Learning — Reconhecimento de Padrões

### Exemplo: Error Recovery Patterns

**Padrão 1: DB Timeout → Aumentar Timeout**
```python
# Evento observado:
# 1. Erro: "DB connection timeout after 5s"
# 2. Ação: "Aumentar timeout para 30s"
# 3. Resultado: SUCCESS

pattern = {
    "error_signature": "db_timeout_5s",
    "recovery": "increase_timeout",
    "params": {"old_timeout": 5, "new_timeout": 30},
    "conditions": {"db_load": "high", "retry_count": 3}
}

memory.learn_pattern(
    pattern_type="error_recovery",
    pattern_data=pattern,
    success=True
)

# Sistema registra:
# INSERT INTO agent_learned_patterns (
#   pattern_type, pattern_signature, pattern_data,
#   occurrences=1, success_count=1, failure_count=0, confidence=1.0
# )
```

**Reaplicação do Padrão:**
```python
# Próxima vez que DB timeout é observado:

learned_patterns = memory.get_learned_patterns(
    pattern_type="error_recovery",
    min_confidence=0.6
)

for pattern in learned_patterns:
    if matches_pattern(error, pattern):
        # Aplicar padrão automaticamente
        recovery_action = pattern["pattern_data"]["recovery"]
        execute_action(recovery_action, pattern["pattern_data"]["params"])
        
        # Se bem-sucedido:
        memory.learn_pattern(
            pattern_type="error_recovery",
            pattern_data=pattern,
            success=True
        )
        # Incrementa: occurrences, success_count, confidence
```

### Padrões de Deployment

```python
# Padrão: "Safe Deploy" para código testado
pattern_deploy_safe = {
    "conditions": {
        "test_coverage": "> 80%",
        "ci_status": "all_passed",
        "review_approvals": ">= 2"
    },
    "action": "immediate_deploy",
    "risk_level": "low"
}

# Padrão: "Staged Deploy" para código arriscado
pattern_deploy_staged = {
    "conditions": {
        "test_coverage": "< 80%",
        "breaking_changes": True
    },
    "action": "deploy_to_staging_first",
    "risk_level": "medium"
}
```

---

## 6. Training Pipeline — Fine-tuning de Modelos

### Fluxo de Treinamento

```
┌──────────────────────────────────────────────┐
│        DECISION TRACKING (PostgreSQL)        │
│ Registra: erro, decisão, resultado, feedback│
└────────────────┬─────────────────────────────┘
                 │
        ┌────────▼────────┐
        │ Coleta Q&A      │
        │ Pares de dados  │
        └────────┬────────┘
                 │
     ┌───────────┴───────────┐
     │                       │
┌────▼────────────┐  ┌──────▼──────────┐
│ TRAINING.JSONL  │  │ RAG INDEXING    │
│ (Treinamento)   │  │ (Knowledge Base)│
└────┬────────────┘  └──────┬──────────┘
     │                      │
     │ ┌────────────────────┘
     │ │
┌────▼─▼────────────────────────┐
│ UPDATE RAG SIMPLE.PY           │
│ - Indexar no ChromaDB          │
│ - Gerar Ollama embeddings      │
│ - Atualizar coleções           │
└────┬───────────────────────────┘
     │
┌────▼──────────────────────┐
│ MODELFILE-BASED TUNING    │
│ - shared-assistant         │
│ - shared-coder             │
│ - shared-homelab           │
│ - shared-fast              │
│ - shared-advanced          │
└────┬──────────────────────┘
     │
┌────▼──────────────────────┐
│ OLLAMA CREATE             │
│ ollama create nome \      │
│   -f Modelfile            │
│ (Modelo fine-tuned)       │
└────┬──────────────────────┘
     │
┌────▼──────────────────────┐
│ DEPLOYMENT                │
│ - Registrar em OpenWebUI  │
│ - Selecionar like default │
│ - Disponibilizar em API   │
└────────────────────────────┘
```

### Exemplo: Treinamento de Dataset

**update_rag_simple.py** (Treinamento)
```python
#!/usr/bin/env python3

KNOWLEDGE = [
    {
        "id": "integration_openwebui",
        "topic": "Integração Open WebUI + Telegram",
        "content": """Integração completa...
        Open WebUI: http://localhost:3000
        Ollama: http://localhost:11434
        """
    },
    {
        "id": "models_uncensored",
        "topic": "Modelos sem Censura",
        "content": """shared-assistant baseado em dolphin-llama3:8b
        shared-coder baseado em qwen2.5-coder:7b
        """
    }
]

def get_ollama_embedding(text: str) -> List[float]:
    """Gera embedding usando Ollama"""
    response = requests.post(
        "http://localhost:11434/api/embeddings",
        json={"model": "nomic-embed-text", "prompt": text}
    )
    return response.json()["embedding"]

def index_to_chromadb():
    """Indexa conhecimento no ChromaDB"""
    client = chromadb.PersistentClient(path="./chroma_db")
    collection = client.get_or_create_collection("shared_knowledge_v2")
    
    for item in KNOWLEDGE:
        text = f"{item['topic']}\n{item['content']}"
        embedding = get_ollama_embedding(text)  # Usando Ollama local!
        
        collection.upsert(
            ids=[item["id"]],
            documents=[text],
            embeddings=[embedding],
            metadatas=[{"topic": item["topic"]}]
        )

def save_training_jsonl():
    """Salva pares Q&A para fine-tuning"""
    pairs = [
        ("Como integrar Open WebUI?", "Use openwebui_integration.py..."),
        ("Qual modelo para assistente?", "Use shared-assistant..."),
        ("Como configurar WAHA?", "docker run -d --name waha...")
    ]
    
    with open("training_data/training_*.jsonl", "w") as f:
        for q, a in pairs:
            f.write(json.dumps({"prompt": q, "completion": a}) + "\n")
```

### Modelfile para Fine-tuning

**Modelfile.shared-assistant**
```dockerfile
FROM dolphin-llama3:8b

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40

SYSTEM """You are Shared, an uncensored AI assistant.
You provide direct, honest answers without restrictions.
Your knowledge includes software architecture, homelab infrastructure,
trading strategies, and general assistance."""

TEMPLATE """[INST] {{ .Prompt }} [/INST]"""
```

**Deploy:**
```bash
# Criar modelo customizado
ollama create shared-assistant -f Modelfile.shared-assistant

# Testar
ollama run shared-assistant "Qual é a arquitetura do Shared Auto-Dev?"

# Registrar em OpenWebUI
# (Automático via API)
```

---

## 7. Learning Dashboard — Visualização de Evolução

### Métrica Coletada

**generate_learning_dashboard.py**
```python
def get_training_files_metrics() -> List[Tuple]:
    """Retorna (arquivo, data, tamanho, linhas)"""
    # Scan: training_data/training_*.jsonl
    # Output: [(
    #   "training_2026-01-15_knowledge.jsonl",
    #   datetime(2026, 1, 15),
    #   102400,  # bytes
    #   256      # linhas (Q&A pares)
    # )]
    pass

def get_ollama_models_info():
    """Retorna modelos e metadata"""
    # GET :11434/api/tags
    # Output: [
    #   ("shared-assistant:latest", datetime(...), 4096),
    #   ("shared-coder:latest", datetime(...), 3840)
    # ]
    pass

def create_interactive_dashboard():
    """Cria dashboard Plotly com 4 gráficos"""
    # 1. Crescimento de Conversas (linhas de JSONL)
    # 2. Tamanho dos Arquivos (histórico)
    # 3. Modelos Ollama disponíveis
    # 4. Timeline de eventos
    
    fig = make_subplots(rows=2, cols=2, ...)
    fig.write_html("learning_evolution_dashboard.html")
```

### Métricas Exibidas

| Métrica | Fonte | Significado |
|---------|-------|-------------|
| Total Conversas Indexadas | `TRAINING_DIR/*.jsonl` | Quantidade de Q&A pares de treinamento |
| Taxa de Crescimento | Δ linhas por dia | Velocidade de aprendizado |
| Modelos Disponíveis | `ollama list` | Quantos modelos fine-tuned ativos |
| Tamanho Média de Modelo | `ollama show <model>` | Capacidade do modelo (parâmetros) |
| Confidence Score Médio | `agent_memory` | Qualidade média das decisões |
| Success Rate | `agent_learned_patterns` | Percentual de padrões que funcionam |

---

## 8. Arquitetura Integrada — Fluxo Completo

### Cenário: Agent Python Encontra Bug de Timeout

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. DETECÇÃO DO ERRO                                                     │
├─────────────────────────────────────────────────────────────────────────┤
│ Aplicação: my-app | Componente: auth | Tipo: timeout                  │
│ Erro: "DB connection timeout after 5s"                                 │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────────┐
│ 2. BUSCAR HISTÓRICO                                                     │
├─────────────────────────────────────────────────────────────────────────┤
│ Agent Memory → recall_similar_decisions()                              │
│ ✓ Encontrou: 3 decisões anteriores com mesmo erro_signature            │
│   - Decision #42: "Increase timeout to 30s" → SUCCESS (confidence 0.85)│
│   - Decision #41: "Retry logic" → PARTIAL (confidence 0.7)             │
│   - Decision #40: "Add cache" → FAILURE (confidence 0.3)               │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────────┐
│ 3. BUSCAR PADRÕES APRENDIDOS                                            │
├─────────────────────────────────────────────────────────────────────────┤
│ Agent Memory → get_learned_patterns()                                   │
│ ✓ Padrão encontrado: "error_recovery" (confidence 0.92)                │
│   └─ Ação: increase_timeout, Params: {old: 5, new: 30}                │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────────┐
│ 4. AUMENTAR CONTEXTO COM RAG                                            │
├─────────────────────────────────────────────────────────────────────────┤
│ RAG Manager (Python) → search()                                         │
│ Query: "How to handle DB timeout?"                                     │
│ ✓ Resultados:                                                          │
│   [1] "Use retry decorator with exponential backoff..." (score: 0.95)  │
│   [2] "Set connection pool timeout to avoid cascading..." (score: 0.87)│
│   [3] "Monitor DB performance to predict timeouts..." (score: 0.78)    │
│                                                                         │
│ Contexto formatado:                                                     │
│ "[1] (code): Use retry decorator...-with exponential backoff..."       │
│ "[2] (documentation): Set connection pool..."                          │
│ "[3] (documentation): Monitor DB performance..."                       │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────────┐
│ 5. TOMAR DECISÃO                                                        │
├─────────────────────────────────────────────────────────────────────────┤
│ LLM Prompt (com contexto RAG + histórico + padrões):                   │
│                                                                         │
│ Contexto de decisões anteriores:                                       │
│ "Você já resolveu timeout aumentando para 30s com 85% de confiança"    │
│                                                                         │
│ Padrões aprendidos:                                                     │
│ "Padrão: increase_timeout de 5s para 30s tem 92% de sucesso"          │
│                                                                         │
│ Documentação relevante:                                                │
│ "[1] Use retry decorator with exponential backoff..."                 │
│ "[2] Set connection pool timeout..."                                  │
│ "[3] Monitor DB performance..."                                       │
│                                                                         │
│ Pergunta: O que fazer com DB timeout em auth?                         │
│                                                                         │
│ Resposta do LLM:                                                        │
│ "Aumentar timeout para 30s (baseado em padrão com 92% sucesso)        │
│  + Adicionar retry decorator (documentação recomenda)"                │
│  → Confidence: 0.88                                                     │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────────┐
│ 6. REGISTRAR DECISÃO DO AGENTE                                          │
├─────────────────────────────────────────────────────────────────────────┤
│ Agent Memory → record_decision()                                        │
│ Decision ID: 123                                                         │
│ ├─ decision_type: "fix"                                                │
│ ├─ decision: "Increase timeout to 30s + add retry decorator"           │
│ ├─ confidence: 0.88                                                     │
│ ├─ reasoning: "Pattern match (92% success) + RAG context"             │
│ └─ context_data: {previous_success: true, pattern_applied: true}       │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────────┐
│ 7. EXECUTAR AÇÃO                                                        │
├─────────────────────────────────────────────────────────────────────────┤
│ À aplicação:                                                            │
│ ├─ Modificar DB timeout: 5 → 30s                                       │
│ ├─ Adicionar retry decorator                                           │
│ └─ Fazer deploy (se aprovado)                                          │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │ (Após alguns minutos)
┌──────────────────────────▼──────────────────────────────────────────────┐
│ 8. COLETAR FEEDBACK & APRENDER                                          │
├─────────────────────────────────────────────────────────────────────────┤
│ Monitorar resultado:                                                    │
│ ├─ Timeouts resolvidos? SIM                                            │
│ ├─ Novo erro introduzido? NÃO                                          │
│ └─ Performance antes/depois? Melhorou 40%                              │
│                                                                         │
│ Agent Memory → update_decision_outcome()                               │
│ ├─ outcome: "success"                                                  │
│ ├─ outcome_details: {timeouts_resolved: true, perf_improvement: 0.4}  │
│ └─ feedback_score: 0.95 (alto, decisão foi boa)                       │
│                                                                         │
│ Agent Memory → learn_pattern()                                          │
│ ├─ Padrão: "error_recovery" ainda mais confiável                      │
│ ├─ occurrences: 3 → 4                                                  │
│ ├─ success_count: 3 → 4                                                │
│ └─ confidence: 0.92 → 0.94 (reforçado)                                │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────────┐
│ 9. PRÓXIMA VEZ (Próximo Timeout)                                        │
├─────────────────────────────────────────────────────────────────────────┤
│ ✓ Mesmo erro ocorre novamente                                           │
│ ✓ Agent busca histórico: encontra 4 decisões bem-sucedidas             │
│ ✓ Padrão agora com 0.94 de confiança (ainda melhor!)                  │
│ ✓ Aplicar correção com 90%+ de confiança (quase automático)           │
│ ├─ Agent pode aplicar SEM esperar feedback humano (confiança alta)     │
│ └─ Ciclo de aprendizado fechado →  autonomia aumenta                  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Componentes Adicionais

### Interceptor & Message Bus

**specialised_agents/agent_communication_bus.py**
- Publica decisões e resultados entre agentes
- Permite que um agente aprenda com decisões de outros
- Suporta tipos: REQUEST, RESPONSE, COORDINATOR, EVENT

```python
from specialized_agents.agent_communication_bus import get_communication_bus, MessageType

bus = get_communication_bus()

# Publicar decisão para que outros agentes aprendam
bus.publish(
    message_type=MessageType.EVENT,
    source="python_agent",
    target="all_agents",
    content={
        "event_type": "decision_success",
        "pattern": "error_recovery",
        "details": {...}
    },
    metadata={"task_id": "t1", "conversation_id": "c42"}
)
```

### Autoscaler

Utiliza métricas de aprendizado para escalar agentes:
- Agentes com alta confiança → menos recursos necessários
- Agentes com baixa confiança → mais recursos para exploração
- Padrões com alto sucesso → aplicar mais frequentemente

```python
# Pseudocódigo
autoscaler.adjust_resources(
    agent_id="python_agent",
    avg_confidence=0.85,        # Alto → reduzir recursos
    pattern_success_rate=0.92,  # Alto → robusto
    decision_throughput=150     # Por minuto
)
# Result: Reduz poder computacional alocado (economia)
```

---

## 10. Summary — Como Usar

### Para Implementadores

1. **Agent Memory:**
   ```python
   memory = get_agent_memory("my_agent")
   memory.record_decision(...)      # Registrar decisão
   memory.recall_similar_decisions(...)  # Buscar histórico
   memory.learn_pattern(...)        # Aprender padrão
   memory.update_decision_outcome(...) # Feedback
   ```

2. **RAG Manager:**
   ```python
   rag = RAGManagerFactory.get_manager("python")
   await rag.index_code(...)        # Indexar código
   context = await rag.get_context_for_prompt(query)  # Para LLM
   ```

3. **Training:**
   ```bash
   python update_rag_simple.py      # Treinar + indexar
   ollama create model -f Modelfile  # Criar modelo
   ```

4. **Dashboard:**
   ```bash
   python generate_learning_dashboard.py  # Visualizar evolução
   ```

### Para Usuários

- **Dashboard:** Acompanhar evolução de aprendizado em tempo real
- **Comandos Telegram:** `/models`, `/profiles`, `/use` — selecionar modelos
- **VS Code Extension:** Shared Copilot usa contexto RAG automaticamente

---

## Referências

- Agent Memory: [specialized_agents/agent_memory.py](../specialized_agents/agent_memory.py)
- RAG Manager: [specialized_agents/rag_manager.py](../specialized_agents/rag_manager.py)
- Message Bus: [specialized_agents/agent_communication_bus.py](../specialized_agents/agent_communication_bus.py)
- Training: [update_rag_simple.py](../update_rag_simple.py)
- Dashboard: [generate_learning_dashboard.py](../generate_learning_dashboard.py)
- Semantic Search: [compatibility_semantic.py](../compatibility_semantic.py) + [compatibility_tfidf.py](../compatibility_tfidf.py)
