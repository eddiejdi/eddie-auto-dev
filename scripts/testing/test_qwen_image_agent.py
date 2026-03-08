"""
Script de Teste: Qwen Image Agent
Valida todos os componentes e executa testes de geração.
"""

import asyncio
import sys
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class QwenImageAgentTest:
    """Suite de testes para Qwen Image Agent."""
    
    def __init__(self):
        self.results = {
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "details": []
        }
    
    async def test_imports(self) -> bool:
        """Test 1: Verificar imports necessários."""
        test_name = "Imports"
        logger.info(f"\n{'='*60}")
        logger.info(f"TEST 1: {test_name}")
        logger.info('='*60)
        
        try:
            logger.info("  Verificando imports...")
            import torch
            logger.info("  ✓ torch")
            
            from diffusers import StableDiffusionPipeline
            logger.info("  ✓ diffusers")
            
            import httpx
            logger.info("  ✓ httpx")
            
            from specialized_agents.agent_communication_bus import AgentCommunicationBus
            logger.info("  ✓ agent_communication_bus")
            
            logger.info("\n✅ TEST PASSED: Todos os imports disponíveis")
            self.results["tests_passed"] += 1
            return True
            
        except ImportError as e:
            logger.error(f"\n❌ TEST FAILED: {e}")
            self.results["details"].append(f"Import error: {e}")
            self.results["tests_failed"] += 1
            return False
    
    async def test_ollama_connection(self) -> bool:
        """Test 2: Verificar conectividade com Ollama."""
        test_name = "Ollama Connection"
        logger.info(f"\n{'='*60}")
        logger.info(f"TEST 2: {test_name}")
        logger.info('='*60)
        
        try:
            import httpx
            
            ollama_host = "http://192.168.15.2:11434"
            logger.info(f"  Conectando a Ollama: {ollama_host}")
            
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{ollama_host}/api/tags")
                
                if resp.status_code == 200:
                    models = resp.json().get("models", [])
                    logger.info(f"  ✓ Ollama respondendo")
                    
                    model_names = [m["name"] for m in models]
                    logger.info(f"  Modelos disponíveis: {model_names}")
                    
                    has_qwen = any("qwen" in m.lower() for m in model_names)
                    if has_qwen:
                        logger.info("  ✓ Modelo Qwen encontrado")
                    else:
                        logger.warning("  ⚠️ Nenhum modelo Qwen encontrado (OK para teste)")
                    
                    logger.info("\n✅ TEST PASSED: Ollama acessível")
                    self.results["tests_passed"] += 1
                    return True
                else:
                    logger.error(f"  Status: {resp.status_code}")
                    raise Exception(f"HTTP {resp.status_code}")
                    
        except Exception as e:
            logger.error(f"\n❌ TEST FAILED: {e}")
            logger.warning("  Nota: Se Ollama não está rodando, é esperado. Teste continuará com mocks.")
            self.results["details"].append(f"Ollama error: {e}")
            self.results["tests_failed"] += 1
            return False
    
    async def test_cuda_availability(self) -> bool:
        """Test 3: Verificar disponibilidade de CUDA/GPU."""
        test_name = "CUDA/GPU"
        logger.info(f"\n{'='*60}")
        logger.info(f"TEST 3: {test_name}")
        logger.info('='*60)
        
        try:
            import torch
            
            has_cuda = torch.cuda.is_available()
            logger.info(f"  CUDA Disponível: {has_cuda}")
            
            if has_cuda:
                device_count = torch.cuda.device_count()
                logger.info(f"  Número de GPUs: {device_count}")
                
                for i in range(device_count):
                    name = torch.cuda.get_device_name(i)
                    total_memory = torch.cuda.get_device_properties(i).total_memory / 1024**3
                    logger.info(f"    [{i}] {name}: {total_memory:.1f} GB")
                
                # Teste de alocação
                logger.info("  Testando alocação de memória...")
                x = torch.randn(100, 100, device="cuda:0")
                memory = torch.cuda.memory_allocated(0) / 1024**3
                logger.info(f"  ✓ Tensor criado. VRAM usado: {memory:.3f} GB")
                del x
                torch.cuda.empty_cache()
                
                logger.info("\n✅ TEST PASSED: GPU disponível e funcional")
                self.results["tests_passed"] += 1
                return True
            else:
                logger.warning("\n⚠️ TEST WARNING: CUDA não disponível (CPU mode)")
                logger.warning("  Testes continuarão em CPU (mais lento)")
                self.results["tests_passed"] += 1
                return True
                
        except Exception as e:
            logger.error(f"\n❌ TEST FAILED: {e}")
            self.results["details"].append(f"CUDA error: {e}")
            self.results["tests_failed"] += 1
            return False
    
    async def test_agent_initialization(self) -> bool:
        """Test 4: Inicializar QwenImageAgent."""
        test_name = "Agent Initialization"
        logger.info(f"\n{'='*60}")
        logger.info(f"TEST 4: {test_name}")
        logger.info('='*60)
        
        try:
            logger.info("  Importando QwenImageAgent...")
            from specialized_agents.qwen_image_agent import QwenImageAgent
            
            logger.info("  Criando instance...")
            agent = QwenImageAgent(
                agent_id="test-qwen-image",
                ollama_host="http://192.168.15.2:11434",
                qwen_model="qwen2.5:7b",
                device="cuda:0" if __import__("torch").cuda.is_available() else "cpu"
            )
            
            logger.info(f"  ✓ Agent criado: {agent.agent_id}")
            logger.info(f"    Ollama: {agent.ollama_host}")
            logger.info(f"    Qwen: {agent.qwen_model}")
            logger.info(f"    Device: {agent.device}")
            logger.info(f"    Cache: {agent.cache_dir}")
            
            logger.info("\n✅ TEST PASSED: Agent inicializado com sucesso")
            self.results["tests_passed"] += 1
            return True
            
        except Exception as e:
            logger.error(f"\n❌ TEST FAILED: {e}")
            self.results["details"].append(f"Agent init error: {e}")
            self.results["tests_failed"] += 1
            return False
    
    async def test_message_bus(self) -> bool:
        """Test 5: Verificar integração com Message Bus."""
        test_name = "Message Bus"
        logger.info(f"\n{'='*60}")
        logger.info(f"TEST 5: {test_name}")
        logger.info('='*60)
        
        try:
            logger.info("  Importando AgentCommunicationBus...")
            from specialized_agents.agent_communication_bus import AgentCommunicationBus, MessageType
            
            logger.info("  Criando instância do bus...")
            bus = AgentCommunicationBus()
            
            logger.info("  Publicando mensagem de teste...")
            msg = bus.publish(
                message_type=MessageType.REQUEST,
                source="test-agent",
                target="qwen-image-gen",
                content='{"prompt": "test"}',
                metadata={"test": True}
            )
            
            logger.info(f"  ✓ Mensagem publicada: {msg.id}")
            logger.info(f"    Timestamp: {msg.timestamp}")
            logger.info(f"    Tipo: {msg.message_type.value}")
            
            # Verificar se a mensagem está no buffer
            messages = list(bus.message_buffer)
            logger.info(f"  ✓ Total de mensagens no bus: {len(messages)}")
            
            logger.info("\n✅ TEST PASSED: Message Bus funcional")
            self.results["tests_passed"] += 1
            return True
            
        except Exception as e:
            logger.error(f"\n❌ TEST FAILED: {e}")
            self.results["details"].append(f"Bus error: {e}")
            self.results["tests_failed"] += 1
            return False
    
    async def test_diffusion_model_loading(self) -> bool:
        """Test 6: Carregando modelo de difusão (pode ser lento)."""
        test_name = "Diffusion Model Loading"
        logger.info(f"\n{'='*60}")
        logger.info(f"TEST 6: {test_name}")
        logger.info('='*60)
        logger.info("  ⏳ AVISO: Este teste downloads/loads larga modelo (~4GB)")
        logger.info("     Pode levar 2-5 minutos na primeira vez\n")
        
        try:
            import torch
            from diffusers import StableDiffusionPipeline
            from pathlib import Path
            
            logger.info("  Carregando StableDiffusionPipeline...")
            logger.info("  (Primeira execução fará download de ~4GB)")
            
            cache_dir = Path.home() / "agent_data" / "diffusion_cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            import time
            t0 = time.time()
            
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
            logger.info(f"  Device: {device}")
            
            pipeline = StableDiffusionPipeline.from_pretrained(
                "runwayml/stable-diffusion-v1-5",
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                cache_dir=str(cache_dir)
            )
            
            logger.info(f"  ✓ Modelo baixado/carregado em {time.time()-t0:.1f}s")
            
            logger.info("  Movendo para device...")
            pipeline = pipeline.to(device)
            logger.info("  ✓ Pipeline movido para device")
            
            # Medir VRAM
            if torch.cuda.is_available():
                vram_used = (torch.cuda.mem_get_info(0)[1] - torch.cuda.mem_get_info(0)[0]) / 1024**3
                logger.info(f"  VRAM usado: {vram_used:.1f} GB")
            
            del pipeline
            torch.cuda.empty_cache()
            
            logger.info("\n✅ TEST PASSED: Modelo de difusão carregado")
            self.results["tests_passed"] += 1
            return True
            
        except Exception as e:
            logger.error(f"\n❌ TEST FAILED: {e}")
            self.results["details"].append(f"Diffusion loading error: {e}")
            self.results["tests_failed"] += 1
            return False
    
    async def test_image_generation(self) -> bool:
        """Test 7: Teste real de geração de imagem."""
        test_name = "Image Generation"
        logger.info(f"\n{'='*60}")
        logger.info(f"TEST 7: {test_name}")
        logger.info('='*60)
        
        try:
            logger.info("  Importando QwenImageAgent...")
            from specialized_agents.qwen_image_agent import QwenImageAgent, ImageGenerationRequest
            import torch
            import uuid
            
            logger.info("  Criando agent...")
            agent = QwenImageAgent(
                device="cuda:0" if torch.cuda.is_available() else "cpu"
            )
            
            logger.info("  Inicializando pipelines...")
            await agent.initialize_pipelines()
            
            logger.info("  Criando requisição de teste...")
            request = ImageGenerationRequest(
                id=str(uuid.uuid4()),
                prompt="A beautiful blue butterfly on a green leaf",
                source_agent="test-client",
                num_inference_steps=10,  # Poucos passos para teste rápido
                height=256,  # Pequeno para teste
                width=256,
                refine_prompt=False  # Pular refinamento do Qwen para teste rápido
            )
            
            logger.info(f"  Gerando imagem: {request.prompt}")
            logger.info(f"  Steps: {request.num_inference_steps}, Size: {request.width}x{request.height}")
            
            import time
            t0 = time.time()
            
            result = await agent.generate_image(request)
            
            elapsed = time.time() - t0
            
            logger.info(f"\n  Status: {result.status}")
            logger.info(f"  Tempo: {elapsed:.1f}s")
            logger.info(f"  Prompt refinado: {result.refined_prompt}")
            logger.info(f"  Imagens geradas: {result.image_paths}")
            
            if result.image_paths:
                for path in result.image_paths:
                    file_size = Path(path).stat().st_size / 1024
                    logger.info(f"    ✓ {Path(path).name} ({file_size:.0f} KB)")
            
            logger.info(f"  VRAM pico: {result.vram_used_gb:.1f} GB")
            
            if result.status == "completed" and result.image_paths:
                logger.info("\n✅ TEST PASSED: Imagem gerada com sucesso!")
                self.results["tests_passed"] += 1
                return True
            else:
                logger.error(f"\n❌ TEST FAILED: Status={result.status}, Erro={result.error_message}")
                self.results["tests_failed"] += 1
                return False
            
        except Exception as e:
            logger.error(f"\n❌ TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            self.results["details"].append(f"Image generation error: {e}")
            self.results["tests_failed"] += 1
            return False
    
    async def test_client_integration(self) -> bool:
        """Test 8: Teste do cliente."""
        test_name = "Client Integration"
        logger.info(f"\n{'='*60}")
        logger.info(f"TEST 8: {test_name}")
        logger.info('='*60)
        
        try:
            logger.info("  Importando QwenImageClient...")
            from specialized_agents.qwen_image_client import QwenImageClient
            
            logger.info("  Criando cliente...")
            client = QwenImageClient(client_id="test-client")
            
            logger.info("  Requisitando geração via bus...")
            client.request_image_generation(
                prompt="Test image generation",
                num_inference_steps=5,
                refine_prompt=False
            )
            
            logger.info("  ✓ Requisição enviada ao bus")
            
            logger.info("  Verificando mensagens no bus...")
            messages = client.get_recent_messages(5)
            logger.info(f"  ✓ {len(messages)} mensagens no buffer")
            
            # Verificar se há alguma mensagem de requisição
            has_request = any("request" in m.message_type.value.lower() for m in messages)
            if has_request:
                logger.info("  ✓ Mensagem de requisição encontrada")
            
            logger.info("\n✅ TEST PASSED: Cliente funcional")
            self.results["tests_passed"] += 1
            return True
            
        except Exception as e:
            logger.error(f"\n❌ TEST FAILED: {e}")
            self.results["details"].append(f"Client error: {e}")
            self.results["tests_failed"] += 1
            return False
    
    async def run_all_tests(self):
        """Executa todos os testes."""
        logger.info("\n" + "="*60)
        logger.info("QWEN IMAGE AGENT - TEST SUITE")
        logger.info("="*60)
        
        tests = [
            ("Imports", self.test_imports),
            ("Ollama Connection", self.test_ollama_connection),
            ("CUDA/GPU", self.test_cuda_availability),
            ("Agent Initialization", self.test_agent_initialization),
            ("Message Bus", self.test_message_bus),
            ("Diffusion Model Loading", self.test_diffusion_model_loading),
            ("Image Generation", self.test_image_generation),
            ("Client Integration", self.test_client_integration),
        ]
        
        self.results["tests_run"] = len(tests)
        
        for test_name, test_func in tests:
            try:
                await test_func()
            except Exception as e:
                logger.error(f"Erro ao executar teste: {e}")
                self.results["tests_failed"] += 1
        
        # Resumo final
        logger.info("\n" + "="*60)
        logger.info("RESUMO DOS TESTES")
        logger.info("="*60)
        logger.info(f"Total: {self.results['tests_run']}")
        logger.info(f"✅ Passou: {self.results['tests_passed']}")
        logger.info(f"❌ Falhou: {self.results['tests_failed']}")
        
        if self.results["details"]:
            logger.info("\nDetalhes dos erros:")
            for detail in self.results["details"]:
                logger.info(f"  - {detail}")
        
        # Status final
        if self.results["tests_failed"] == 0:
            logger.info("\n🎉 TODOS OS TESTES PASSARAM!")
            return True
        else:
            logger.info(f"\n⚠️ {self.results['tests_failed']} teste(s) falharam")
            return False


async def main():
    """Ponto de entrada."""
    tester = QwenImageAgentTest()
    success = await tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
