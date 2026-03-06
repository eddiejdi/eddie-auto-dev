---
applyTo: "**/*ollama*,**/*llm*,**/*token*,**/*economy*,**/*agent*,**/*base_agent*"
---

# Regras Ollama & LLM Routing — Eddie Auto-Dev

## 🔴 ROTEAMENTO — REGRA IMPERATIVA
Todo agente DEVE rotear para homelab. Ollama é o LLM primário — usar ANTES de qualquer API cloud.
- Violação = desperdício de tokens

### Para homelab (via API ou SSH):
- Logs, status, métricas, saúde
- Docker/systemd/cgroups
- BD queries, processamento pesado
- Testes, builds, compilação

### Local APENAS:
- Edição de config simples
- Orquestração UI
- Resumos curtos

## Dual-GPU (2 instâncias Ollama)
| Instância | GPU | Porta | Modelo | Uso |
|-----------|-----|-------|--------|-----|
| Principal | GPU0 RTX 2060 8GB | `:11434` | `qwen2.5-coder:7b` | Tarefas complexas: code review, refatoração |
| Secundária | GPU1 GTX 1050 2GB | `:11435` | `qwen3:1.7b` | Tarefas leves: resumos, classificação, parsing |

### Env vars:
- `OLLAMA_HOST` = `http://192.168.15.2:11434`
- `OLLAMA_HOST_GPU1` = `http://192.168.15.2:11435`
- `OLLAMA_MODEL` = `eddie-coder`

### Fallback chain:
Ollama GPU0 → Ollama GPU1 → OpenWebUI → Copilot API (último recurso)

### Exceções para tokens cloud:
- Ambas instâncias offline
- Contexto > 32K tokens
- Usuário solicita explicitamente

## Modelos Copilot
- **Permitidos (gratuitos)**: GPT-4o, GPT-4o mini, GPT-4.1, GPT-4.1 mini, GPT-4.1 nano, GPT-5.1, Raptor Mini
- **Proibidos (premium)**: Claude Opus 4, Claude Sonnet 4, o3, o4-mini, Gemini 2.5 Pro
- Avise o custo se o usuário pedir premium

## Token Economy Tracker
- Módulo: `specialized_agents/token_economy.py` (singleton)
- Persistência: `data/token_economy.jsonl`
- Economia estimada: ~92-98% vs cloud
