# 🤖 Sistema LLM para Matching de Vagas

Sistema completo de compatibilidade entre currículos e vagas usando **LLM (eddie-whatsapp)** com **fine-tuning automático** baseado em feedback.

---

## 📋 Visão Geral

### Problema Original
- **Método Jaccard**: simples token matching, score muito baixo (max 1.1% em vagas reais)
- **Limitações**: não entende sinônimos (K8s ≠ Kubernetes), não considera contexto semântico

### Solução Implementada
1. **LLM Semantic Matching**: usa modelo eddie-whatsapp para análise semântica
2. **Hybrid Scoring**: 70% LLM + 30% Jaccard para balancear semântica e keywords
3. **Training Data Collection**: coleta automática de feedback (emails enviados, aceitos, rejeitados)
4. **Auto Fine-tuning**: re-treina modelo com dados coletados para melhorar precisão

---

## 🚀 Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                    apply_real_job.py                        │
│  (Pipeline principal: WhatsApp → Currículo → Email)        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
    ┌────────────────────────────────────────────────────┐
    │         llm_compatibility.py                       │
    │  ┌──────────────┬──────────────┬────────────────┐ │
    │  │ LLM Only     │ Jaccard Only │ Hybrid (70/30) │ │
    │  └──────────────┴──────────────┴────────────────┘ │
    └────────────────────┬───────────────────────────────┘
                         │
            ┌────────────┴────────────┐
            │                         │
            ▼                         ▼
  ┌──────────────────┐      ┌──────────────────────┐
  │ Ollama API       │      │ Training Data        │
  │ eddie-whatsapp   │      │ Collector            │
  │ :11434           │      │ (SQLite)             │
  └──────────────────┘      └──────────┬───────────┘
                                       │
                                       ▼
                            ┌──────────────────────┐
                            │ Fine-tuning          │
                            │ (JSONL → Modelfile)  │
                            └──────────────────────┘
```

---

## 📦 Componentes

### 1. `llm_compatibility.py`
**Funcionalidades:**
- `compute_compatibility_llm()`: scoring com LLM puro
- `compute_compatibility_hybrid()`: 70% LLM + 30% Jaccard
- `compute_compatibility_fallback()`: Jaccard tradicional (backup)
- `benchmark_compatibility_methods()`: compara todos os métodos

**Exemplo de uso:**
```python
from llm_compatibility import compute_compatibility_hybrid

score, explanation, details = compute_compatibility_hybrid(resume_text, job_text)
# score: 85.3
# explanation: "LLM: 92.0%, Jaccard: 68.5%, Final: 85.3% | Strong match: Kubernetes..."
# details: {"llm_score": 92.0, "jaccard_score": 68.5, "method": "hybrid"}
```

### 2. `training_data_collector.py`
**Funcionalidades:**
- `init_training_db()`: cria SQLite database `/tmp/whatsapp_training.db`
- `collect_training_sample()`: armazena cada comparação
- `update_training_feedback()`: atualiza com feedback manual
- `export_training_dataset()`: gera JSONL para fine-tuning
- `show_training_dashboard()`: estatísticas (MAE, accuracy, etc.)

**Tabela SQLite:**
```sql
CREATE TABLE training_samples (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    resume_text TEXT,
    job_text TEXT,
    predicted_score REAL,
    actual_score REAL,
    user_feedback TEXT,
    was_sent INTEGER,
    email_status TEXT,
    llm_explanation TEXT,
    jaccard_score REAL,
    method TEXT
)
```

### 3. `finetune_whatsapp_model.py`
**Funcionalidades:**
- `load_training_data()`: carrega JSONL dataset
- `create_modelfile()`: gera Modelfile com few-shot examples
- `create_model_via_api()`: cria modelo via Ollama API
- `validate_model()`: testa modelo após fine-tuning
- `compare_model_versions()`: compara original vs fine-tuned

**Workflow:**
1. Carrega `whatsapp_training_dataset.jsonl` (mínimo 10 samples)
2. Cria Modelfile com system prompt + few-shot examples
3. Chama Ollama API `/api/create` para treinar
4. Valida modelo com teste de sanidade
5. Compara performance: base model vs fine-tuned

### 4. `apply_real_job.py` (integrado)
**Mudanças:**
- `compute_compatibility()` retorna `(score, explanation, details)` tuple
- Coleta automática de training samples
- Log detalhado de LLM vs Jaccard scores
- Fallback automático se LLM falhar

---

## ⚙️ Variáveis de Ambiente

```bash
# LLM Configuration
export USE_LLM_COMPATIBILITY=1          # 1=enabled, 0=disabled
export COMPATIBILITY_METHOD=hybrid      # llm, jaccard, or hybrid
export COMPATIBILITY_THRESHOLD=1.0      # Score threshold (0-100)
export COLLECT_TRAINING_DATA=1          # 1=collect, 0=no collect

# Ollama
export OLLAMA_HOST=http://192.168.15.2:11434
export WHATSAPP_MODEL=eddie-whatsapp:latest

# Training
export TRAINING_DB=/tmp/whatsapp_training.db
```

---

## 🎯 Uso

### Modo Interativo (Recomendado)
```bash
python3 llm_system_demo.py
```

Menu:
1. **Test LLM Compatibility** - comparar métodos (Jaccard vs LLM vs Hybrid)
2. **Collect Training Data** - coletar 5-10 amostras simuladas
3. **Show Training Dashboard** - métricas (MAE, scores médios, etc.)
4. **Export Training Dataset** - gerar JSONL para fine-tuning
5. **Fine-tune Model** - re-treinar eddie-whatsapp
6. **Run Full Pipeline** - executar apply_real_job.py com LLM
7. **Exit**

### Uso Direto

#### 1. Testar compatibilidade (benchmark)
```bash
python3 llm_compatibility.py
```
Mostra 3 exemplos comparando Jaccard vs LLM vs Hybrid.

#### 2. Coletar dados de treino (manual)
```bash
export COLLECT_TRAINING_DATA=1
export DEMO_MODE=1
export COMPATIBILITY_THRESHOLD=60.0

# Executar 10x para coletar samples
for i in {1..10}; do
    python3 apply_real_job.py
done
```

#### 3. Ver estatísticas de treino
```bash
python3 training_data_collector.py stats
```
Output:
```
📊 DASHBOARD DE TREINAMENTO
   Total de amostras: 127
   Emails enviados: 18
   Amostras com feedback: 5
   Amostras com correção: 3
   
   Score médio predito: 62.5%
   Score médio real: 58.3%
   Erro absoluto médio: 4.2%
   
   Melhoria do LLM sobre Jaccard: +45.2%
```

#### 4. Exportar dataset para fine-tuning
```bash
python3 training_data_collector.py export
```
Gera `/tmp/whatsapp_training_dataset.jsonl` com formato:
```json
{"prompt": "Você é um especialista...\nCURRÍCULO: ...\nVAGA: ...", "completion": "Score: 85%\nJustificativa: Match excelente..."}
```

#### 5. Fazer fine-tuning
```bash
python3 finetune_whatsapp_model.py
```
Workflow:
- Carrega training dataset
- Cria Modelfile com few-shot examples
- Chama Ollama API para criar modelo
- Valida com teste
- Exibe comparação antes/depois

#### 6. Usar no pipeline de produção
```bash
export USE_LLM_COMPATIBILITY=1
export COMPATIBILITY_METHOD=hybrid
export COMPATIBILITY_THRESHOLD=1.0
export COLLECT_TRAINING_DATA=1

python3 apply_real_job.py
```

---

## 📊 Comparação de Métodos

### Jaccard (Baseline)
```
Vaga: "SRE para trabalhar com K8s e cloud AWS"
Currículo: "DevOps Engineer com Kubernetes, Docker, AWS"
Score: 15.2%  ❌ (não reconhece K8s = Kubernetes)
```

### LLM Only
```
Vaga: "SRE para trabalhar com K8s e cloud AWS"
Currículo: "DevOps Engineer com Kubernetes, Docker, AWS"
Score: 88.5%  ✅ (entende sinônimos e contexto)
Explicação: "Match excelente: experiência em Kubernetes (K8s), AWS, perfil DevOps/SRE compatível"
```

### Hybrid (70% LLM + 30% Jaccard)
```
Vaga: "SRE para trabalhar com K8s e cloud AWS"
Currículo: "DevOps Engineer com Kubernetes, Docker, AWS"
LLM: 88.5% | Jaccard: 15.2% → Final: 66.5%  ✅ (balanceado)
```

**Recomendação:** `hybrid` oferece melhor balanceamento entre análise semântica e keyword matching.

---

## 🔧 Fine-tuning Workflow

### 1. Coletar Dados (≥10 amostras)
```bash
# Modo automático (demo)
python3 llm_system_demo.py  # Opção 2

# Modo manual (vagas reais)
export COLLECT_TRAINING_DATA=1
python3 run_auto_apply.py 10
```

### 2. Adicionar Feedback Manual (opcional)
```python
from training_data_collector import update_training_feedback

# Correção de score
update_training_feedback(sample_id=15, user_feedback="good_match", actual_score=85.0)

# Apenas feedback qualitativo
update_training_feedback(sample_id=16, user_feedback="bad_match (spam)")
```

### 3. Exportar Dataset
```bash
python3 training_data_collector.py export
```

### 4. Fine-tune
```bash
python3 finetune_whatsapp_model.py
```

### 5. Validar Resultado
```bash
# Comparar antes/depois
python3 finetune_whatsapp_model.py compare

# Testar em produção
export WHATSAPP_MODEL=eddie-whatsapp:latest
python3 llm_compatibility.py
```

---

## 📈 Métricas e Monitoramento

### Training Dashboard
```bash
python3 training_data_collector.py stats
```
Mostra:
- Total de samples coletados
- Emails enviados
- Samples com feedback/correção
- Score médio: predito vs real
- Mean Absolute Error (MAE)
- Melhoria do LLM sobre Jaccard

### Logs Detalhados
```bash
tail -f /tmp/email_logs/email_log.txt
```
Cada comparação exibe:
```
2026-02-11 20:30:15 - INFO - 🤖 LLM Hybrid: 68.5% (LLM: 72.0%, Jaccard: 58.5%)
2026-02-11 20:30:15 - INFO - Found match with compat 68.5%
```

---

## 🎓 Conceitos

### Jaccard Similarity
```
score = |A ∩ B| / |A ∪ B| × 100
```
Onde:
- A = conjunto de tokens do currículo
- B = conjunto de tokens da vaga
- ∩ = interseção (palavras em comum)
- ∪ = união (todas as palavras únicas)

**Limitação:** apenas overlap literal, sem semântica.

### LLM Semantic Matching
- Usa modelo de linguagem (eddie-whatsapp) para entender **significado**
- Reconhece sinônimos (Kubernetes = K8s)
- Considera contexto (SRE ≈ DevOps ≈ Platform Engineer)
- Avalia senioridade (Pleno vs Sênior)
- Ignora diferenças irrelevantes (idioma, formato)

### Hybrid Approach
```
final_score = (llm_score × 0.7) + (jaccard_score × 0.3)
```
Combina:
- **Semântica** (LLM): entende significado e contexto
- **Keywords** (Jaccard): garante overlap de termos técnicos exatos

**Vantagem:** mais robusto - se LLM errar, Jaccard corrige; se Jaccard falhar (sinônimos), LLM compensa.

### Few-shot Learning
Fine-tuning adiciona exemplos no Modelfile:
```
### Exemplo 1:
USER: [prompt com currículo DevOps + vaga SRE]
ASSISTANT: Score: 85%\nJustificativa: Match excelente, experiência K8s/AWS...

### Exemplo 2:
USER: [prompt com currículo DevOps + vaga Data Science]
ASSISTANT: Score: 12%\nJustificativa: Áreas diferentes, mínimo overlap...
```
Modelo aprende padrões de scoring corretos.

---

## 🐛 Troubleshooting

### Erro: "LLM compatibility not available"
```bash
# Verificar módulos
python3 -c "from llm_compatibility import compute_compatibility_llm"

# Verificar Ollama
curl http://192.168.15.2:11434/api/tags
```

### Erro: "Model eddie-whatsapp not found"
```bash
# Listar modelos
curl -s http://192.168.15.2:11434/api/tags | python3 -m json.tool

# Criar modelo se necessário
python3 finetune_whatsapp_model.py
```

### Scores muito baixos (LLM + Jaccard)
- **Causa:** grupos do WhatsApp não contêm vagas relevantes
- **Solução:** entrar em grupos de DevOps/SRE/Platform Engineering ou ajustar threshold para 0.5-2.0%

### Fine-tuning falha: "Only X samples available"
- **Causa:** precisa ≥10 samples com correção para treino significativo
- **Solução:** coletar mais dados via `python3 llm_system_demo.py` opção 2

### LLM timeout
- **Causa:** Ollama sobrecarregado ou modelo muito pesado
- **Solução:** aguardar ou usar modelo menor (ex: `dolphin-llama3:8b` → `dolphin-llama3:3b`)

---

## 📚 Próximos Passos

### Melhorias Possíveis
1. **TF-IDF weighting**: dar mais peso a termos técnicos raros
2. **Named Entity Recognition (NER)**: extrair tecnologias específicas
3. **Embeddings**: usar sentence-transformers para similaridade vetorial
4. **Active Learning**: priorizar samples com alta incerteza para feedback
5. **A/B Testing**: comparar modelos em produção com split 50/50

### Escalabilidade
- Mover training DB para PostgreSQL (multi-process)
- Cache de embeddings para re-scoring rápido
- Batch processing para múltiplas vagas simultâneas
- API REST para scoring externo

---

## 📖 Referências

- [Ollama API Docs](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [Jaccard Similarity](https://en.wikipedia.org/wiki/Jaccard_index)
- [Few-shot Learning](https://arxiv.org/abs/2005.14165)
- [Fine-tuning LLMs](https://huggingface.co/docs/transformers/training)

---

## 🤝 Contribuindo

Para adicionar novo método de scoring:

1. Implementar em `llm_compatibility.py`:
```python
def compute_compatibility_new_method(resume_text, job_text):
    # Seu algoritmo aqui
    return score, explanation, details
```

2. Adicionar opção em `apply_real_job.py`:
```python
if COMPATIBILITY_METHOD == "new_method":
    score, explanation, details = compute_compatibility_new_method(resume_text, job_text)
```

3. Testar com benchmark:
```python
python3 llm_compatibility.py
```

---

## 📄 Licença

MIT License - use livremente, atribua créditos.

---

**👤 Autor:** Eddie Auto-Dev Team  
**📅 Data:** Fevereiro 2026  
**🔧 Versão:** 1.0.0
