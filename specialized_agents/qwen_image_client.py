"""
Cliente de Requisição para Qwen Image Agent
Exemplo de como usar o agent de geração de imagens via message bus.
"""

import asyncio
import json
import httpx
from pathlib import Path
from typing import Optional, Dict, Any
import logging

from .agent_communication_bus import AgentCommunicationBus, MessageType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QwenImageClient:
    """Cliente para requisitar geração de imagens ao Qwen Image Agent."""
    
    def __init__(self, client_id: str = "image-client"):
        self.client_id = client_id
        self.bus = AgentCommunicationBus()
        self.agent_id = "qwen-image-gen"
    
    def request_image_generation(
        self,
        prompt: str,
        num_inference_steps: int = 30,
        guidance_scale: float = 7.5,
        height: int = 512,
        width: int = 512,
        num_images: int = 1,
        refine_prompt: bool = True,
        timeout: int = 300
    ) -> Optional[Dict[str, Any]]:
        """
        Requisita geração de imagem ao agent.
        
        Args:
            prompt: Descrição da imagem a gerar
            num_inference_steps: Passos do inference (mais = melhor qualidade, mais lento)
            guidance_scale: Scale de guia (7.5 é recomendado)
            height: Altura da imagem em pixels
            width: Largura da imagem em pixels
            num_images: Número de imagens a gerar
            refine_prompt: Se Qwen deve refinar o prompt
            timeout: Timeout em segundos
            
        Returns:
            Resultado da geração ou None se erro
        """
        logger.info(f"Requisitando geração: {prompt[:80]}...")
        
        # Preparar payload
        request_payload = {
            "prompt": prompt,
            "num_inference_steps": num_inference_steps,
            "guidance_scale": guidance_scale,
            "height": height,
            "width": width,
            "num_images": num_images,
            "refine_prompt": refine_prompt
        }
        
        # Enviar via bus
        self.bus.publish(
            message_type=MessageType.REQUEST,
            source=self.client_id,
            target=self.agent_id,
            content=json.dumps(request_payload),
            metadata={"prompt": prompt[:100]}
        )
        
        # Não há resposta síncrona - o agent retorna via bus
        logger.info("Requisição enviada ao agent")
        return None
    
    def get_recent_messages(self, n: int = 10) -> list:
        """Obtém mensagens recentes do bus."""
        return list(self.bus.message_buffer)[-n:]


# Exemplos de uso
async def example_simple_request():
    """Exemplo simples: requisitar uma imagem."""
    client = QwenImageClient()
    
    prompt = "A futuristic cyberpunk city with neon lights, flying cars, and towering buildings"
    
    client.request_image_generation(
        prompt=prompt,
        num_inference_steps=40,
        guidance_scale=7.5
    )
    
    print("\n✓ Requisição enviada. Aguarde resposta via message bus.")


async def example_batch_requests():
    """Exemplo avançado: múltiplas requisições em série."""
    client = QwenImageClient()
    
    prompts = [
        "A serene mountain landscape at sunset with golden light",
        "Deep ocean waters with bioluminescent creatures glowing in the dark",
        "An ancient library with floating books and magical crystals"
    ]
    
    for i, prompt in enumerate(prompts):
        logger.info(f"\n[{i+1}/{len(prompts)}] Enviando requisição...")
        client.request_image_generation(
            prompt=prompt,
            num_inference_steps=30,
            refine_prompt=True
        )
        
        # Aguardar um intervalo entre requisições
        await asyncio.sleep(2)
    
    print("\n✓ Todas as requisições foram enviadas.")


def example_with_telegram_integration():
    """
    Exemplo: Integração com Telegram Bot
    Quando alguém enviar /gerar <prompt> no Telegram, 
    isso faz uma requisição ao Qwen Image Agent.
    """
    
    code_snippet = '''
# No telegram_client.py ou handler de comandos:

async def handle_generate_command(message):
    """Handler para comando /gerar prompt"""
    text = message.text.replace("/gerar", "").strip()
    
    if not text:
        await message.reply("Use: /gerar <descrição da imagem>")
        return
    
    # Requisitar geração
    from specialized_agents.qwen_image_client import QwenImageClient
    client = QwenImageClient(client_id="telegram-bot")
    
    client.request_image_generation(
        prompt=text,
        num_inference_steps=40,
        refine_prompt=True
    )
    
    await message.reply(f"🎨 Gerando imagem: {text[:50]}...\\nAguarde alguns minutos")
    
    # Depois, quando o agent responder, o bot envia a imagem:
    # Seria via callback no message bus
    '''
    
    print(code_snippet)


def example_with_api_endpoint():
    """
    Exemplo: Expor como endpoint HTTP
    POST /api/generate-image
    {
        "prompt": "description",
        "refine_prompt": true,
        "num_inference_steps": 40
    }
    """
    
    code_snippet = '''
# No api.py ou endpoints.py:

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio

app = FastAPI()

class ImageGenerationRequest(BaseModel):
    prompt: str
    refine_prompt: bool = True
    num_inference_steps: int = 30
    guidance_scale: float = 7.5
    height: int = 512
    width: int = 512

@app.post("/api/generate-image")
async def generate_image(req: ImageGenerationRequest):
    """Endpoint para gerar imagem."""
    from specialized_agents.qwen_image_client import QwenImageClient
    
    client = QwenImageClient(client_id="api-client")
    
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
        "message": f"Gerando: {req.prompt[:50]}...",
        "check_bus": "Use /api/messages para ver respostas"
    }

@app.get("/api/messages")
async def get_messages():
    """Obtém mensagens recentes do bus."""
    from specialized_agents.qwen_image_client import QwenImageClient
    client = QwenImageClient()
    return {"messages": client.get_recent_messages(10)}
    '''
    
    print(code_snippet)


def show_architecture():
    """Mostra a arquitetura de integração."""
    
    architecture = """
╔════════════════════════════════════════════════════════════════════════════╗
║                    ARQUITETURA: QWEN IMAGE AGENT                          ║
╠════════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║  ┌──────────────┐                                                         ║
║  │ Telegram Bot │────────────┐                                            ║
║  └──────────────┘            │                                            ║
║                              │                                            ║
║  ┌──────────────┐            │      ┌─────────────────────────────────┐   ║
║  │  HTTP API    │────────────┼────→ │  Agent Communication Bus        │   ║
║  └──────────────┘            │      │  (message_buffer, subscribers)  │   ║
║                              │      └──────────────┬──────────────────┘   ║
║  ┌──────────────┐            │                     │                      ║
║  │  Custom Tool │────────────┘                     ↓                      ║
║  └──────────────┘                                                         ║
║                              ┌─────────────────────────────────────────┐  ║
║                              │     QwenImageAgent                      │  ║
║                              │  ┌─────────────────────────────────┐    │  ║
║                              │  │ 1. Parse requisição             │    │  ║
║                              │  │ 2. Qwen refina prompt (Ollama)  │    │  ║
║                              │  │ 3. Diffusion gera (GPU CUDA)    │    │  ║
║                              │  │ 4. Salva em cache               │    │  ║
║                              │  │ 5. Responde via bus             │    │  ║
║                              │  └─────────────────────────────────┘    │  ║
║                              │                                         │  ║
║                              │  Hardware:                              │  ║
║                              │  - Ollama GPU0: RTX 2060 SUPER (8GB)   │  ║
║                              │  - Diffusion: Mesma GPU                │  ║
║                              │  - Modelo: Stable Diffusion 1.5 FP16   │  ║
║                              │  - Contexto: 4-8 sec por imagem        │  ║
║                              └─────────────────────────────────────────┘  ║
║                                                                            ║
║  Fluxo de Dados:                                                           ║
║                                                                            ║
║  "(descrição)" → [Qwen: refina] → [Diffusion: gera] → [Cache] → URL      ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
    """
    
    print(architecture)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "simple":
            print("\n=== Exemplo Simples ===")
            asyncio.run(example_simple_request())
        
        elif cmd == "batch":
            print("\n=== Exemplo Batch ===")
            asyncio.run(example_batch_requests())
        
        elif cmd == "telegram":
            print("\n=== Integração Telegram ===")
            example_with_telegram_integration()
        
        elif cmd == "api":
            print("\n=== Integração HTTP API ===")
            example_with_api_endpoint()
        
        elif cmd == "arch":
            print("\n=== Arquitetura ===")
            show_architecture()
        
        else:
            print(f"Comando desconhecido: {cmd}")
            print("\nUso: python qwen_image_client.py [simple|batch|telegram|api|arch]")
    
    else:
        print("\nExemplos disponíveis:")
        print("  python qwen_image_client.py simple       # Um prompt simples")
        print("  python qwen_image_client.py batch        # Múltiplos prompts")
        print("  python qwen_image_client.py telegram     # Integração Telegram")
        print("  python qwen_image_client.py api          # Integração HTTP API")
        print("  python qwen_image_client.py arch         # Mostrar arquitetura")
