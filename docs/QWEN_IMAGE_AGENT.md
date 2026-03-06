# 🎨 Qwen Image Agent - Documentação Completa

## Visão Geral

O **Qwen Image Agent** é um agente especializado que integra:

1. **Qwen 2.5 7B** (via Ollama) - Análise e refinamento de prompts
2. **Stable Diffusion 1.5** (via diffusers) - Geração de imagens
3. **Agent Communication Bus** - Integração com o ecossistema Eddie

O agente se comunica via message bus, permitindo integração com:
- Telegram Bot
- HTTP API
- Outros agentes
- Interfaces web

---

## 🚀 Quick Start

### 1. Iniciar o Agent

```bash
cd /home/edenilson/eddie-auto-dev

# Ativar venv
source .venv/bin/activate

# Executar agent (aguarda requisições via bus)
python -m specialized_agents.qwen_image_agent
```

### 2. Enviar Requisição (outro terminal)

```bash
source .venv/bin/activate

# Executar exemplo simples
python specialized_agents/qwen_image_client.py simple
```

### 3. Resultado

- Imagem gerada em: `~/agent_data/image_cache/`
- Resposta no message bus
- Tempo: ~5-10 segundos por imagem

---

## 📋 Exemplos de Uso

### A. Cliente Python Puro

```python
from specialized_agents.qwen_image_client import QwenImageClient
import asyncio

client = QwenImageClient(client_id="meu-cliente")

# Requisitar uma imagem
client.request_image_generation(
    prompt="A beautiful sunset over the ocean",
    num_inference_steps=40,
    guidance_scale=7.5,
    refine_prompt=True
)

# Verificar mensagens do bus
messages = client.get_recent_messages(5)
for msg in messages:
    print(f"{msg.source} → {msg.target}: {msg.content[:100]}")
```

### B. Integração com Telegram Bot

**Archivo**: `specialized_agents/telegram_client.py`

```python
from telegram import Update
from telegram.ext import ContextTypes

async def handle_generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /gerar_imagem <prompt>"""
    
    text = update.message.text.replace("/gerar_imagem", "").strip()
    
    if not text:
        await update.message.reply_text(
            "Use: `/gerar_imagem descrição da imagem`",
            parse_mode="Markdown"
        )
        return
    
    # Requisitar geração
    from specialized_agents.qwen_image_client import QwenImageClient
    client = QwenImageClient(client_id=f"telegram_{update.effective_user.id}")
    
    client.request_image_generation(
        prompt=text,
        num_inference_steps=40,
        guidance_scale=7.5,
        refine_prompt=True
    )
    
    await update.message.reply_text(
        f"🎨 Gerando imagem para: *{text[:40]}...*\n"
        f"⏳ Aguarde ~5-10 segundos",
        parse_mode="Markdown"
    )
    
    # Depois registrar callback para quando a resposta chegar
    # (via message bus listener)

# Registrar no application
app.add_handler(CommandHandler("gerar_imagem", handle_generate_image))
```

### C. Integração HTTP/REST API

**Archivo**: `specialized_agents/api.py`

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import json

app = FastAPI()

class ImageGenerationRequest(BaseModel):
    prompt: str
    refine_prompt: bool = True
    num_inference_steps: int = 30
    guidance_scale: float = 7.5
    height: int = 512
    width: int = 512

@app.post("/api/v1/generate-image")
async def generate_image(req: ImageGenerationRequest):
    """Endpoint para gerar imagem via API HTTP."""
    
    from specialized_agents.qwen_image_client import QwenImageClient
    
    client = QwenImageClient(client_id="http-api")
    
    client.request_image_generation(
        prompt=req.prompt,
        num_inference_steps=req.num_inference_steps,
        guidance_scale=req.guidance_scale,
        height=req.height,
        width=req.width,
        refine_prompt=req.refine_prompt
    )
    
    return {
        "status": "processing",
        "message": f"Gerando imagem: {req.prompt[:60]}...",
        "estimated_time": "5-10 segundos",
        "hint": "Confira /api/v1/messages para ver a resposta quando pronto"
    }

@app.get("/api/v1/messages")
async def get_messages(n: int = 10):
    """Obtém últimas n mensagens do bus."""
    from specialized_agents.qwen_image_client import QwenImageClient
    
    client = QwenImageClient()
    messages = client.get_recent_messages(n)
    
    return {
        "total": len(messages),
        "messages": [
            {
                "timestamp": msg.timestamp.isoformat(),
                "type": msg.message_type.value,
                "source": msg.source,
                "target": msg.target,
                "content": msg.content[:200]
            }
            for msg in messages
        ]
    }
```

**Uso via curl**:

```bash
# Gerar imagem
curl -X POST http://localhost:8503/api/v1/generate-image \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A futuristic city with flying cars",
    "num_inference_steps": 40,
    "refine_prompt": true
  }'

# Verificar status/resposta
curl http://localhost:8503/api/v1/messages?n=5
```

### D. Integração com Agent Manager

**Archivo**: `agent_manager.py`

```python
from specialized_agents.qwen_image_agent import QwenImageAgent
import asyncio

class AgentManager:
    async def initialize_agents(self):
        # ... outros agentes ...
        
        # Inicializar Qwen Image Agent
        self.image_agent = QwenImageAgent(
            agent_id="qwen-image-gen",
            ollama_host="http://192.168.15.2:11434",
            qwen_model="qwen2.5:7b",
            device="cuda:0"
        )
        
        asyncio.create_task(self.image_agent.run())
        
        logger.info("✓ Qwen Image Agent iniciado")
```

---

## 🔧 Configuração

### Variáveis de Ambiente

```bash
# .env ou exportar

# Ollama
OLLAMA_HOST=http://192.168.15.2:11434
OLLAMA_MODEL=qwen2.5:7b

# Diffusion
DIFFUSION_MODEL=runwayml/stable-diffusion-v1-5
DIFFUSION_DEVICE=cuda:0  # ou cuda:1 para GTX 1050

# Cache
IMAGE_CACHE_DIR=~/agent_data/image_cache
```

### Hardware Requerido

| Componente | Requisito | O que tem |
|-----------|-----------|----------|
| GPU (vídeo) | Mínimo RTX 2060 | RTX 2060 SUPER 8GB ✅ |
| VRAM | ~5GB para SD 1.5 | 8GB disponível ✅ |
| Processador | Qualquer i7/i9 | i9-9900T ✅ |
| RAM | ~8GB | 31GB ✅ |
| Ollama | Rodando | http://192.168.15.2:11434 ✅ |

### Tempos Estimados

| Modelo | Inferência | Qwen Refine | Total |
|--------|-----------|-----------|-------|
| SD 1.5 @ 30 passos | 6-8s | 1-2s | 7-10s |
| SD 1.5 @ 40 passos | 8-10s | 1-2s | 9-12s |
| SD 1.5 @ 50 passos | 10-12s | 1-2s | 11-14s |

---

## 📊 Monitoramento

### Logs do Agent

```bash
# Terminal 1: Agent
python -m specialized_agents.qwen_image_agent

# Saída esperada:
# INFO:qwen_image_agent:Qwen Image Agent inicializado: qwen-image-gen
# INFO:qwen_image_agent:  Ollama: http://192.168.15.2:11434
# INFO:qwen_image_agent:✓ Pipeline de difusão carregado com sucesso
# INFO:qwen_image_agent:✓ Ollama conectado. Modelos: ['qwen2.5:7b', ...]
```

### Ver Mensagens no Bus

```bash
# Terminal 2: Monitor
python -c "
from specialized_agents.qwen_image_client import QwenImageClient
import time

client = QwenImageClient()
while True:
    msgs = client.get_recent_messages(3)
    if msgs:
        for msg in msgs:
            print(f'[{msg.timestamp.strftime(\"%H:%M:%S\")}] {msg.source} → {msg.target}')
    time.sleep(2)
"
```

### Hardware Monitoring

```bash
# Terminal 3: Monitor GPU
watch -n 1 nvidia-smi
```

---

## 🎯 Casos de Uso

### 1. Geração On-Demand via Telegram
- User: `/gerar_imagem um gato cinzento em uma biblioteca mágica`
- Bot: Envia ao agent
- Agent: Refina com Qwen → Gera com SD 1.5 → Salva
- Bot: Retorna imagem gerada

### 2. Pipeline de Conteúdo
```
[Texto] → [Qwen cria prompt] → [Imagem] → [Publicado]
```

### 3. Geração em Lote
```python
prompts = [
    "Mountain landscape",
    "Ocean sunset",
    "Forest path"
]

for prompt in prompts:
    client.request_image_generation(prompt)
    await asyncio.sleep(15)  # Aguardar entre
```

---

## 🐛 Troubleshooting

### Erro: "CUDA out of memory"

Solução: Reduzir height/width ou num_inference_steps

```python
client.request_image_generation(
    prompt=prompt,
    height=384,  # em vez de 512
    width=384,
    num_inference_steps=20  # em vez de 30
)
```

### Erro: "Ollama não está acessível"

```bash
# Verificar se Ollama está rodando
curl http://192.168.15.2:11434/api/tags

# Se não:
ssh homelab@192.168.15.2
# Iniciar Ollama ou verificar porta
```

### Imagens de baixa qualidade

- Aumentar num_inference_steps (máximo 50)
- Já está refinando prompt? `refine_prompt=True`
- Usar guidance_scale entre 7.0-9.0

---

## 📚 API Completa

### QwenImageAgent

```python
agent = QwenImageAgent(
    agent_id: str = "qwen-image-gen",
    ollama_host: str = "http://192.168.15.2:11434",
    qwen_model: str = "qwen2.5:7b",
    diffusion_model: str = "runwayml/stable-diffusion-v1-5",
    device: str = "cuda:0",
    cache_dir: Optional[Path] = None
)

# Métodos
await agent.initialize_pipelines()  # Carregar modelos
result = await agent.generate_image(request)  # Gerar imagem
await agent.run()  # Iniciar listener
agent.shutdown()  # Encerrar
```

### QwenImageClient

```python
client = QwenImageClient(client_id: str = "image-client")

# Métodos
client.request_image_generation(
    prompt: str,
    num_inference_steps: int = 30,
    guidance_scale: float = 7.5,
    height: int = 512,
    width: int = 512,
    num_images: int = 1,
    refine_prompt: bool = True,
    timeout: int = 300
)

messages = client.get_recent_messages(n: int = 10)
```

---

## 🚀 Próximas Melhorias

- [ ] Caching de prompts já refinados
- [ ] Suporte a LoRA/custom embeddings
- [ ] Batch processing otimizado
- [ ] WebUI para visualização
- [ ] Integração WebSocket para real-time updates
- [ ] Fallback automático para GPU1 se GPU0 estiver ocupada

---

## 📖 Referências

- [Ollama](https://ollama.ai)
- [Diffusers](https://huggingface.co/docs/diffusers)
- [Stable Diffusion](https://huggingface.co/runwayml/stable-diffusion-v1-5)
- [Qwen Models](https://huggingface.co/Qwen)
