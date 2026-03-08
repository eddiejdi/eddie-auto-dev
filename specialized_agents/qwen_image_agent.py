"""
Agente Qwen de Geração de Imagem
Integração de Qwen (Ollama) com modelos de difusão para geração de imagens.
Comunica via agent_communication_bus.

Fluxo:
1. Recebe requisição de geração de imagem via message bus
2. Qwen refina/interpreta o prompt
3. Usa diffusers (Stable Diffusion 1.5) para gerar a imagem
4. Salva e retorna URL da imagem via bus
"""

import asyncio
import json
import httpx
import torch
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

# Imports locais
from .config import DATA_DIR
from .agent_communication_bus import AgentCommunicationBus, MessageType, AgentMessage

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ImageGenerationStatus(Enum):
    """Status das requisições de geração"""
    PENDING = "pending"
    PROCESSING_PROMPT = "processing_prompt"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ImageGenerationRequest:
    """Requisição de geração de imagem"""
    id: str
    prompt: str
    source_agent: str
    num_inference_steps: int = 30
    guidance_scale: float = 7.5
    height: int = 512
    width: int = 512
    num_images: int = 1
    refine_prompt: bool = True  # Usar Qwen para refinar prompt
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class ImageGenerationResult:
    """Resultado da geração de imagem"""
    request_id: str
    status: str
    image_paths: List[str] = None
    refined_prompt: Optional[str] = None
    error_message: Optional[str] = None
    generation_time: float = 0.0
    vram_used_gb: float = 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)


class QwenImageAgent:
    """
    Agente especializado em geração de imagens usando Qwen + diffusers.
    
    Endpoints Ollama:
    - GPU0 (RTX 2060): http://192.168.15.2:11434
    - GPU1 (GTX 1050): http://192.168.15.2:11435
    
    Modelos disponíveis:
    - qwen2.5:7b (análise de prompts)
    - shared-coder (fallback)
    """
    
    def __init__(
        self,
        agent_id: str = "qwen-image-gen",
        ollama_host: str = "http://192.168.15.2:11434",
        qwen_model: str = "qwen2.5:7b",
        diffusion_model: str = "runwayml/stable-diffusion-v1-5",
        device: str = "cuda:0",
        cache_dir: Optional[Path] = None
    ):
        """
        Inicializa o agente Qwen de geração de imagem.
        
        Args:
            agent_id: ID único do agente
            ollama_host: URL do servidor Ollama
            qwen_model: Modelo Qwen a usar
            diffusion_model: Modelo de difusão
            device: Device CUDA para usar
            cache_dir: Diretório para cache de modelos
        """
        self.agent_id = agent_id
        self.ollama_host = ollama_host
        self.qwen_model = qwen_model
        self.diffusion_model = diffusion_model
        self.device = device
        self.cache_dir = cache_dir or DATA_DIR / "image_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Bus de comunicação
        self.bus = AgentCommunicationBus()
        
        # Estado
        self.running = False
        self.processing_requests: Dict[str, ImageGenerationRequest] = {}
        
        logger.info(f"Qwen Image Agent inicializado: {agent_id}")
        logger.info(f"  Ollama: {ollama_host}")
        logger.info(f"  Qwen: {qwen_model}")
        logger.info(f"  Diffusion: {diffusion_model}")
        logger.info(f"  Device: {device}")
    
    async def initialize_pipelines(self):
        """Carrega modelos e pipelines."""
        try:
            logger.info("Carregando pipeline de difusão...")
            from diffusers import StableDiffusionPipeline
            
            self.pipeline = StableDiffusionPipeline.from_pretrained(
                self.diffusion_model,
                torch_dtype=torch.float16,
                cache_dir=str(self.cache_dir)
            )
            self.pipeline = self.pipeline.to(self.device)
            
            logger.info("✓ Pipeline de difusão carregado com sucesso")
            
            # Testar conexão com Ollama
            await self._test_ollama_connection()
            
        except Exception as e:
            logger.error(f"Erro ao carregar pipelines: {e}")
            raise
    
    async def _test_ollama_connection(self) -> bool:
        """Testa conectividade com servidor Ollama."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.ollama_host}/api/tags", timeout=5)
                if resp.status_code == 200:
                    models = resp.json().get("models", [])
                    available = [m["name"] for m in models]
                    logger.info(f"✓ Ollama conectado. Modelos: {available}")
                    return True
        except Exception as e:
            logger.warning(f"Ollama não está acessível: {e}")
            return False
    
    async def refine_prompt_with_qwen(self, prompt: str) -> str:
        """
        Usa Qwen para refinar e expandir o prompt de geração.
        
        Args:
            prompt: Prompt original
            
        Returns:
            Prompt refinado
        """
        try:
            logger.info(f"Refinando prompt com Qwen: {prompt[:100]}...")
            
            system_prompt = """Você é um especialista em análise de prompts de geração de imagem.
Seu trabalho é refinar prompts para serem mais descritivos e adequados para modelos de difusão.

Directrizes:
- Manter o significado original
- Adicionar detalhes visuais relevantes
- Melhorar a clareza e estrutura
- Responder apenas com o prompt refinado, sem explicações"""
            
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.ollama_host}/api/generate",
                    json={
                        "model": self.qwen_model,
                        "prompt": f"{system_prompt}\n\nPrompt original: {prompt}",
                        "stream": False,
                        "temperature": 0.7,
                    },
                    timeout=60
                )
                
                if resp.status_code == 200:
                    result = resp.json()
                    refined = result.get("response", "").strip()
                    logger.info(f"Prompt refinado: {refined[:100]}...")
                    return refined or prompt
                else:
                    logger.warning(f"Erro ao refinar prompt: {resp.status_code}")
                    return prompt
                    
        except Exception as e:
            logger.error(f"Erro ao refinar prompt com Qwen: {e}")
            return prompt
    
    async def generate_image(
        self,
        request: ImageGenerationRequest
    ) -> ImageGenerationResult:
        """
        Gera imagem baseada no prompt da requisição.
        
        Args:
            request: Requisição de geração
            
        Returns:
            Resultado da geração
        """
        result = ImageGenerationResult(
            request_id=request.id,
            status=ImageGenerationStatus.PROCESSING_PROMPT.value
        )
        
        try:
            # Registrar início da tarefa
            self.bus.publish(
                message_type=MessageType.TASK_START,
                source=self.agent_id,
                target=request.source_agent,
                content=f"Iniciando geração de imagem: {request.prompt[:100]}",
                metadata={"request_id": request.id}
            )
            
            # Refinar prompt se solicitado
            prompt = request.prompt
            if request.refine_prompt:
                prompt = await self.refine_prompt_with_qwen(prompt)
                result.refined_prompt = prompt
            
            # Gerar imagem
            logger.info(f"Gerando imagem com diffusion: {prompt[:80]}...")
            result.status = ImageGenerationStatus.GENERATING.value
            
            t0 = datetime.now()
            
            with torch.cuda.amp.autocast(dtype=torch.float16):
                image_output = self.pipeline(
                    prompt=prompt,
                    negative_prompt="blurry, low quality, distorted",
                    num_inference_steps=request.num_inference_steps,
                    guidance_scale=request.guidance_scale,
                    height=request.height,
                    width=request.width,
                    num_images_per_prompt=request.num_images,
                    generator=torch.manual_seed(42)
                ).images
            
            elapsed = (datetime.now() - t0).total_seconds()
            result.generation_time = elapsed
            
            # Salvar imagens
            image_paths = []
            for idx, img in enumerate(image_output):
                filename = f"{request.id}_{idx}_{datetime.now().strftime('%H%M%S')}.png"
                filepath = self.cache_dir / filename
                img.save(filepath)
                image_paths.append(str(filepath))
                logger.info(f"Imagem salva: {filepath}")
            
            result.image_paths = image_paths
            result.status = ImageGenerationStatus.COMPLETED.value
            
            # Medir VRAM
            if torch.cuda.is_available():
                result.vram_used_gb = (
                    torch.cuda.mem_get_info(0)[1] - 
                    torch.cuda.mem_get_info(0)[0]
                ) / (1024**3)
            
            # Registrar conclusão
            self.bus.publish(
                message_type=MessageType.TASK_END,
                source=self.agent_id,
                target=request.source_agent,
                content=f"Geração concluída em {elapsed:.1f}s",
                metadata={
                    "request_id": request.id,
                    "images": image_paths,
                    "generation_time": elapsed
                }
            )
            
            logger.info(f"✓ Imagem gerada com sucesso: {image_paths}")
            
        except Exception as e:
            logger.error(f"Erro ao gerar imagem: {e}")
            result.status = ImageGenerationStatus.FAILED.value
            result.error_message = str(e)
            
            self.bus.publish(
                message_type=MessageType.ERROR,
                source=self.agent_id,
                target=request.source_agent,
                content=f"Erro na geração: {e}",
                metadata={"request_id": request.id}
            )
        
        return result
    
    async def handle_request(self, message: AgentMessage) -> ImageGenerationResult:
        """
        Manipula requisição recebida via message bus.
        
        Args:
            message: Mensagem do bus
            
        Returns:
            Resultado da geração
        """
        try:
            # Parse da requisição
            payload = json.loads(message.content)
            
            request = ImageGenerationRequest(
                id=str(uuid.uuid4()),
                prompt=payload["prompt"],
                source_agent=message.source,
                num_inference_steps=payload.get("num_inference_steps", 30),
                guidance_scale=payload.get("guidance_scale", 7.5),
                height=payload.get("height", 512),
                width=payload.get("width", 512),
                num_images=payload.get("num_images", 1),
                refine_prompt=payload.get("refine_prompt", True)
            )
            
            # Adicionar ao registro
            self.processing_requests[request.id] = request
            
            # Gerar imagem
            result = await self.generate_image(request)
            
            # Remover do registro
            del self.processing_requests[request.id]
            
            # Retornar resposta via bus
            self.bus.publish(
                message_type=MessageType.RESPONSE,
                source=self.agent_id,
                target=message.source,
                content=json.dumps(result.to_dict()),
                metadata={"request_id": request.id}
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Erro ao processar requisição: {e}")
            return ImageGenerationResult(
                request_id="unknown",
                status=ImageGenerationStatus.FAILED.value,
                error_message=str(e)
            )
    
    async def run(self):
        """Inicia o agente em modo listener."""
        try:
            logger.info(f"Iniciando {self.agent_id}...")
            
            # Carregar modelos
            await self.initialize_pipelines()
            
            self.running = True
            logger.info(f"✓ {self.agent_id} pronto para processar requisições")
            
            # Loop de processamento (em production, seria via callbacks do bus)
            while self.running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info(f"Encerrando {self.agent_id}...")
            self.running = False
        except Exception as e:
            logger.error(f"Erro no agent: {e}")
            raise
    
    def shutdown(self):
        """Encerra o agente de forma segura."""
        self.running = False
        if hasattr(self, "pipeline"):
            del self.pipeline
        torch.cuda.empty_cache()
        logger.info(f"{self.agent_id} encerrado")


# Função de teste
async def test_agent():
    """Testa o agente com um exemplo simples."""
    agent = QwenImageAgent()
    await agent.initialize_pipelines()
    
    # Requisição de teste
    request = ImageGenerationRequest(
        id=str(uuid.uuid4()),
        prompt="A serene mountain landscape at sunset with golden light, purple clouds, and a calm lake",
        source_agent="test_client"
    )
    
    logger.info("Iniciando teste de geração...")
    result = await agent.generate_image(request)
    
    logger.info("\n=== RESULTADO ===")
    logger.info(f"Status: {result.status}")
    logger.info(f"Prompt Refinado: {result.refined_prompt}")
    logger.info(f"Tempo: {result.generation_time:.1f}s")
    logger.info(f"VRAM: {result.vram_used_gb:.1f} GB")
    logger.info(f"Imagens: {result.image_paths}")


if __name__ == "__main__":
    # Executar teste
    asyncio.run(test_agent())
