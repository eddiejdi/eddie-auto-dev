#!/usr/bin/env python3
"""
Monitor de Geração de Imagem com Qwen
Acompanha requisições em tempo real via message bus.
"""

import asyncio
import sys
import json
from pathlib import Path
from typing import Optional
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """
    Fluxo:
    1. Inicia Qwen Image Agent em background (se não estiver rodando)
    2. Faz requisição de imagem
    3. Monitora progresso no bus
    """
    
    logger.info("=" * 70)
    logger.info("🎨 MONITOR DE GERAÇÃO DE IMAGEM COM QWEN v3.14B")
    logger.info("=" * 70)
    
    try:
        # Import do agente
        logger.info("\n📦 Importando módulos...")
        from specialized_agents.qwen_image_agent import QwenImageAgent
        from specialized_agents.qwen_image_client import QwenImageClient
        from specialized_agents.agent_communication_bus import AgentCommunicationBus, MessageType
        
        logger.info("   ✓ Imports bem-sucedidos")
        
        # Inicializar bus
        logger.info("\n📬 Inicializando message bus...")
        bus = AgentCommunicationBus.get_instance()
        logger.info(f"   ✓ Bus inicializado (buffer size: {len(bus._messages)} msgs)")
        
        # Inicializar agente
        logger.info("\n🤖 Inicializando Qwen Image Agent...")
        agent = QwenImageAgent()
        logger.info(f"   ✓ Agent inicializado")
        logger.info(f"     - Agent ID: {agent.agent_id}")
        logger.info(f"     - Ollama Host: {agent.ollama_host}")
        logger.info(f"     - Model: {agent.qwen_model}")
        logger.info(f"     - Device: {agent.device}")
        
        # Iniciar agente em background (se suportar async)
        logger.info("\n🚀 Iniciando agente em background...")
        # Nota: O agente real rodaria em um processo/thread separado em produção
        
        # Criar cliente
        logger.info("\n👤 Criando cliente de requisição...")
        client = QwenImageClient(client_id="monitor")
        logger.info("   ✓ Cliente criado")
        
        # Fazer requisição de imagem
        logger.info("\n📝 Enviando requisição de geração...")
        prompt = "A beautiful sunset over the ocean with golden clouds and seagulls flying"
        logger.info(f"   Prompt: {prompt}")
        
        client.request_image_generation(
            prompt=prompt,
            num_inference_steps=40,
            guidance_scale=7.5,
            height=512,
            width=512,
            refine_prompt=True
        )
        
        logger.info("   ✓ Requisição enviada ao bus")
        
        # Monitorar bus por x segundos
        logger.info("\n⏱️  Monitorando progresso (60 segundos)...")
        logger.info("-" * 70)
        
        last_msg_count = 0
        start_time = asyncio.get_event_loop().time()
        timeout = 60
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            
            if elapsed > timeout:
                logger.info("-" * 70)
                logger.warning(f"⏰ Timeout após {timeout}s")
                break
            
            # Verificar novas mensagens
            current_msgs = len(bus._messages)
            if current_msgs > last_msg_count:
                logger.info(f"\n📨 Novas mensagens ({current_msgs} total):")
                
                # Mostrar últimas 3 mensagens
                recent = list(bus._messages)[-3:]
                for msg in recent:
                    logger.info(f"   [{msg.timestamp.strftime('%H:%M:%S')}] {msg.msg_type.value}")
                    logger.info(f"      From: {msg.source}")
                    logger.info(f"      Content: {str(msg.content)[:100]}...")
                
                last_msg_count = current_msgs
            
            # Procurar por mensagens de progresso/resultado
            for msg in reversed(list(bus._messages)):
                content = msg.content
                if isinstance(content, str):
                    try:
                        content = json.loads(content)
                    except json.JSONDecodeError:
                        pass
                
                # Verificar se é resultado de geração
                if isinstance(content, dict):
                    if "status" in content and "COMPLETED" in str(content.get("status", "")):
                        logger.info("\n" + "=" * 70)
                        logger.info("✅ IMAGEM GERADA COM SUCESSO!")
                        logger.info("=" * 70)
                        logger.info(f"   Paths: {content.get('image_paths', [])}")
                        logger.info(f"   Time: {content.get('generation_time', 0):.1f}s")
                        logger.info(f"   VRAM: {content.get('vram_used_gb', 0):.2f} GB")
                        
                        if content.get('refined_prompt'):
                            logger.info(f"   Refined: {content.get('refined_prompt')}")
                        
                        return 0
                    elif "status" in content and "FAILED" in str(content.get("status", "")):
                        logger.error("\n" + "=" * 70)
                        logger.error("❌ ERRO NA GERAÇÃO")
                        logger.error("=" * 70)
                        logger.error(f"   Error: {content.get('error_message', 'Unknown error')}")
                        return 1
            
            await asyncio.sleep(1)
        
        logger.info("\n⚠️  Nenhum resultado recebido no timeout")
        logger.info("   (O agente pode estar processando em background)")
        return 0
        
    except ImportError as e:
        logger.error(f"\n❌ Erro de import: {e}")
        logger.error("   Verifique se as dependências estão instaladas:")
        logger.error("   - torch")
        logger.error("   - diffusers")
        logger.error("   - transformers")
        return 1
    except Exception as e:
        logger.error(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
