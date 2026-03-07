# Arquitetura de Sub-Agentes de IA — Eddie Auto-Dev

**Data:** 2026-03-03  
**Versão:** 1.0  
**Autor:** Documentação automática via Copilot

---

## 1. Visão Geral

O sistema Eddie Auto-Dev implementa uma arquitetura **multi-agente de 3 camadas** que combina inferência local dual-GPU, agentes especializados por linguagem isolados em Docker, e orquestração inteligente com paralelismo real.

### Diagrama de Fluxo

```
Usuário (Telegram/WebUI/VS Code)
  → MasterController.route_task()         # classifica complexidade, escolhe agente + modelo
    → AgentManager.split_and_execute_task()  # divide em subtarefas paralelas
      → SpecializedAgent (Python/JS/Go/...)  # executa em Docker isolado
        → LLMSubAgent.generate()             # roteia para GPU0 ou GPU1
          → Ollama (instância local)         # inferência real na GPU
```

---

## 2. Camada 1 — LLMSubAgent (Roteamento Dual-GPU)

**Arquivo:** `specialized_agents/base_agent.py` (classe `LLMSubAgent`, linha ~280)

### Hardware

| Instância | GPU | VRAM | Porta | Modelo Padrão | Throughput | Otimizações | Systemd |
|-----------|-----|------|-------|---------------|------------|---|---------|
| Principal | GPU0 — RTX 2060 SUPER | 8 GB | `:11434` | `qwen2.5-coder:7b` (Q4_K_M) | ~31 tok/s | PL 140W, Excl, Lock 1000MHz | `ollama.service` + `ollama-optimized.conf` |
| Secundária | GPU1 — GTX 1050 | 2 GB | `:11435` | `qwen3:0.6b` | ~62 tok/s | PL 70W, Excl, FA+q4_0 | `ollama-gpu1.service` |

### Modelos Disponíveis no Servidor (Março 2026)

| Modelo | Parâmetros | Tamanho | Quant. | Uso Recomendado |
|--------|-----------|---------|--------|-----------------|
| `qwen3:14b` | 14.8B | 8.6 GB | Q4_K_M | Raciocínio complexo (requer offload CPU, não cabe inteiro na GPU0) |
| `qwen3:8b` | 8.2B | 4.9 GB | Q4_K_M | Generalista — bom equilíbrio, cabe na GPU0 |
| `qwen2.5-coder:7b` | 7.6B | 4.4 GB | Q4_K_M | **Melhor para código** — otimizado para programação |
| `eddie-coder` | 8.2B | 4.9 GB | Q4_K_M | Custom qwen3:8b com system prompt para código |
| `eddie-assistant` | 8.2B | 4.9 GB | Q4_K_M | Custom qwen3:8b para assistente geral |
| `eddie-whatsapp` | 8.2B | 4.9 GB | Q4_K_M | Custom qwen3:8b para chat WhatsApp |
| `qwen3:1.7b` | 2.0B | 1.3 GB | Q4_K_M | **Tarefas leves** — ideal para GPU1 (2GB VRAM) |
| `qwen3:0.6b` | 752M | 498 MB | Q4_K_M | Ultra-leve — parsing, classificação simples |
| `nomic-embed-text` | 137M | 261 MB | F16 | **Embeddings** — RAG/busca semântica |

### Algoritmo de Roteamento

O método `_should_use_gpu1(prompt)` decide automaticamente:

1. Se contém keywords "expert" (refatoração, análise, review) → **GPU0**
2. Se contém keywords de tarefa leve (resumo, parsing, classificação) → **GPU1**
3. Se prompt < 500 chars → **GPU1**
4. Default → **GPU0**

```python
# Roteamento automático
sa = get_sub_agent()  # singleton
result = await sa.generate(prompt)                      # roteamento automático
result = await sa.generate(prompt, force_gpu="gpu1")    # forçar GPU leve
result = await ask_ollama(prompt, light=True)            # helper simplificado
```

### Fallback Automático

Se GPU1 falhar (timeout, erro, offline), o sistema faz fallback transparente para GPU0:

```
GPU1 tentativa → falha → marca _gpu1_healthy=False → redireciona para GPU0
```

Health check: `GET http://192.168.15.2:11435/api/tags` (cache do resultado).

---

## 3. Camada 2 — Agentes Especializados por Linguagem

**Arquivo:** `specialized_agents/language_agents.py`

Cada linguagem (Python, JS, Go, Rust, Java, C#, TS, PHP) tem um agente com:

- **Container Docker isolado** — execução segura de código gerado
- **RAG próprio (ChromaDB)** — memória semântica por linguagem (`agent_{language}_knowledge`)
- **Memória persistente (PostgreSQL)** — aprende com decisões passadas via `AgentMemory`

### Agentes Disponíveis

```python
from specialized_agents.language_agents import AGENT_CLASSES
# {'python': PythonAgent, 'javascript': JavaScriptAgent, 'go': GoAgent,
#  'rust': RustAgent, 'java': JavaAgent, 'csharp': CSharpAgent,
#  'typescript': TypeScriptAgent, 'php': PHPAgent}
```

### RAG por Linguagem

```python
from specialized_agents.rag_manager import RAGManagerFactory

# RAG específico de Python
python_rag = RAGManagerFactory.get_manager("python")
await python_rag.index_code(code, "python", "descrição")
results = await python_rag.search("como usar FastAPI")

# Busca global em todas linguagens
results = await RAGManagerFactory.global_search("docker patterns")
```

---

## 4. Camada 3 — Orquestração

### Componentes

| Componente | Arquivo | Papel |
|------------|---------|-------|
| `AgentManager` | `specialized_agents/agent_manager.py` | Cria/gerencia agentes, `split_and_execute_task()` divide tarefas paralelamente |
| `MasterController` | `specialized_agents/master_controller.py` | Roteia tarefas analisando complexidade, escolhe modelo + agente ideais |
| `CoordinatorAgent` | `dev_agent/coordinator.py` | Coordenador principal que orquestra DevAgent + RAG + Telegram |
| `Communication Bus` | `specialized_agents/agent_communication_bus.py` | Barramento pub/sub — toda comunicação inter-agente |
| `AgentsWebUIBridge` | `specialized_agents/agents_webui_bridge.py` | Ponte entre agentes e OpenWebUI |

### Communication Bus

Toda comunicação inter-agente passa pelo bus singleton:

```python
from specialized_agents.agent_communication_bus import get_communication_bus, MessageType

bus = get_communication_bus()
bus.publish(MessageType.REQUEST, "caller", "target_agent", {"op": "run"}, metadata={"task_id": "t1"})
```

---

## 5. Paralelismo e Ganho de Velocidade

### Nível 1: Dual-GPU Simultâneo

As GPUs rodam instâncias Ollama independentes (processos separados, portas separadas), processando ao mesmo tempo:

```
GPU0 (RTX 2060, 8GB) ─ refatoração complexa ─ ~31 tok/s ─┐
                                                            │ simultâneo
GPU1 (GTX 1050, 2GB) ─ parsing de log leve  ─ ~47 tok/s ─┘
```

**Ganho**: throughput combinado ~78 tok/s vs ~31 tok/s com GPU única = **~2.5x** para workloads mistos.

### Nível 2: Multi-Agente Paralelo (asyncio.gather)

O `split_and_execute_task()` em `agent_manager.py` (linha ~510):

1. **Divide** a tarefa em chunks (por features ou por sentenças)
2. **Distribui** cada chunk para agentes diferentes, balanceando por carga (`active_tasks`)
3. **Executa tudo em paralelo** com `asyncio.gather(*coros)`
4. **Combina** resultados, deduplicando código repetido

```python
# Código real do agent_manager.py
coros = [run_chunk(i, worker_langs[i], chunks[i]) for i in range(len(chunks))]
results = await asyncio.gather(*coros)  # paralelismo real
```

**Configuração**: até `max_workers=6` agentes simultâneos, `timeout_per_subtask=40s`.

### Nível 3: Fallback Inteligente

Se um agente sofre timeout:
- Remove da lista de disponíveis
- Redistribui a subtarefa para outro agente
- Controla profundidade: `max_fallback_depth=1`

### Ganho Estimado

| Cenário | Sequencial | Paralelo | Speedup |
|---------|------------|----------|---------|
| 4 features independentes | ~160s | ~40s (4 agentes) | **~4x** |
| Tarefa mista (1 pesada + 3 leves) | ~100s | ~40s (GPU0+GPU1) | **~2.5x** |
| Tarefa única simples | ~10s | ~10s | 1x (sem ganho) |

---

## 6. Economia de Tokens

### Token Economy Tracker

**Módulo:** `specialized_agents/token_economy.py` — singleton `TokenEconomyTracker`  
**Persistência:** `data/token_economy.jsonl` (append-only)

Dois caminhos independentes registram economia:
1. **Via Ollama direto** (`LLMClient` em `base_agent.py`): cada chamada registra tokens
2. **Via bus** (`log_llm_call` em `agent_communication_bus.py`)

### Custos de Referência (por 1K tokens)

| Provider | Input | Output |
|----------|-------|--------|
| GPT-4.1 (cloud) | $0.002 | $0.008 |
| Ollama GPU0 (eletricidade) | $0.00016 | $0.00016 |
| **Economia** | **~92%** | **~98%** |

```python
from specialized_agents.token_economy import get_token_economy

eco = get_token_economy()
eco.record_ollama_call(
    prompt_tokens=150, completion_tokens=300,
    model="qwen2.5-coder:7b", source="my_agent"
)
print(eco.get_summary())
# → {ollama_calls: 42, savings_usd: 0.0312, savings_percent: "98.5%"}
```

---

## 7. Política de Modelos

### Prioridade de Uso

```
Ollama GPU0 (:11434) → Ollama GPU1 (:11435) → GPT-4.1 (cloud) → GPT-5.1 (último recurso)
```

### Modelos Cloud Permitidos (base/gratuitos)

- GPT-4o, GPT-4o mini, GPT-4.1, GPT-4.1 mini, GPT-4.1 nano, GPT-5.1, Raptor Mini

### Modelos Cloud Proibidos (premium)

- Claude Opus 4, Claude Sonnet 4, o3, o4-mini, Gemini 2.5 Pro

### Regras

1. **Sempre preferir Ollama local** antes de qualquer token cloud
2. Usar cloud **apenas se**: ambas instâncias offline, contexto > 32K tokens, ou usuário solicitar explicitamente
3. Para **código/refatoração**: `qwen2.5-coder:7b` (GPU0)
4. Para **tarefas leves**: `qwen3:1.7b` (GPU1)
5. Para **raciocínio complexo**: `qwen3:8b` ou `qwen3:14b` (GPU0, com offload CPU se necessário)
6. Para **embeddings/RAG**: `nomic-embed-text` (CPU)

---

## 8. Otimizações de Infraestrutura

### GPU0 (RTX 2060 SUPER)

- `OLLAMA_SCHED_SPREAD=true` — distribui processamento
- `OLLAMA_GPU_OVERHEAD=512MB` — reserva VRAM para OS
- `OLLAMA_FLASH_ATTENTION=true` — atenção otimizada
- `CPUAffinity=3-15` — isolamento de cores
- KV cache: `q4_0` (reduz VRAM ~75% vs q8_0)

### GPU1 (GTX 1050)

- `CUDA_VISIBLE_DEVICES=1` — GPU dedicada
- `CPUAffinity=12-15` — 4 threads (não competir com principal)
- Backend: Vulkan (CUDA v13 não suporta Pascal CC 6.1)

### Configurações Systemd

- GPU0: `systemd/ollama-optimized.conf` (drop-in)
- GPU1: `systemd/ollama-gpu1.service` (unit dedicada)

---

## 9. API Endpoints Relevantes

| Endpoint | Método | Função |
|----------|--------|--------|
| `/rag/index` | POST | Indexa conteúdo no RAG |
| `/rag/search` | POST | Busca no RAG |
| `/rag/stats/{language}` | GET | Estatísticas do RAG |
| `/v1/models` | GET | Lista modelos/agentes disponíveis |
| `/v1/chat/completions` | POST | Chat com agente (compatível OpenAI) |
| `/agents` | GET | Lista agentes disponíveis |
| `/agents/{lang}` | GET | Info de agente específico |
| `/communication/publish` | POST | Publica no bus de comunicação |
| `/homelab/execute` | POST | Executa comando no homelab |

---

## 10. Referências Rápidas

### Singleton Helpers

```python
# Sub-agent dual-GPU
from specialized_agents.base_agent import get_sub_agent, ask_ollama

# RAG por linguagem
from specialized_agents.rag_manager import RAGManagerFactory

# Token economy
from specialized_agents.token_economy import get_token_economy

# Communication bus
from specialized_agents.agent_communication_bus import get_communication_bus

# Agent manager
from specialized_agents import get_agent_manager
```

### Variáveis de Ambiente

| Variável | Default | Descrição |
|----------|---------|-----------|
| `OLLAMA_HOST` | `http://192.168.15.2:11434` | GPU0 (principal) |
| `OLLAMA_HOST_GPU1` | `http://192.168.15.2:11435` | GPU1 (secundária) |
| `OLLAMA_MODEL` | `eddie-coder` | Modelo padrão |
| `DATABASE_URL` | - | PostgreSQL para memória/IPC |
| `DATA_DIR` | `./data` | Diretório de dados |
