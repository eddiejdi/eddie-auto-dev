#!/usr/bin/env python3
"""
Script para testar integração do modelo OpenAI-compatible (sk-or-v1)

Uso:
    python3 test_openai_compatible_model.py
    
Variáveis de ambiente:
    OPENAI_COMPATIBLE_ENABLED=true
    OPENAI_COMPATIBLE_API_KEY=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
    OPENAI_COMPATIBLE_BASE_URL=https://openrouter.ai/api/v1  # opcional, padrão
    OPENAI_COMPATIBLE_MODEL=gpt-4  # opcional, padrão
"""

import json
import os
import sys
import logging
from pathlib import Path

import requests

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from specialized_agents.config import LLM_OPENAI_COMPATIBLE_CONFIG, LLM_CONFIG, LLM_GPU1_CONFIG


def test_ollama_availability():
    """Testar se Ollama (GPU0/GPU1) está disponível"""
    logger.info("🔍 Testando disponibilidade do Ollama...")
    
    try:
        # Testar GPU0
        resp = requests.get(
            f"{LLM_CONFIG['base_url']}/api/tags",
            timeout=3
        )
        if resp.status_code == 200:
            logger.info("✅ GPU0 (Ollama) disponível")
            return True
    except Exception as e:
        logger.warning(f"⚠️  GPU0 indisponível: {e}")
    
    try:
        # Testar GPU1
        resp = requests.get(
            f"{LLM_GPU1_CONFIG['base_url']}/api/tags",
            timeout=3
        )
        if resp.status_code == 200:
            logger.info("✅ GPU1 (Ollama) disponível")
            return True
    except Exception as e:
        logger.warning(f"⚠️  GPU1 indisponível: {e}")
    
    logger.warning("❌ Nenhuma GPU disponível, testando fallback OpenAI-compatible...")
    return False


def test_openai_compatible():
    """Testar configuração e conectividade do modelo OpenAI-compatible"""
    logger.info("\n🔍 Testando modelo OpenAI-compatible...")
    
    # Validar configuração
    if not LLM_OPENAI_COMPATIBLE_CONFIG["enabled"]:
        logger.warning("⚠️  Modelo OpenAI-compatible está desabilitado (OPENAI_COMPATIBLE_ENABLED=false)")
        return False
    
    api_key = LLM_OPENAI_COMPATIBLE_CONFIG.get("api_key", "")
    if not api_key:
        logger.error("❌ API key não configurada (OPENAI_COMPATIBLE_API_KEY)")
        return False
    
    logger.info(f"✓ API key detectada: {api_key[:10]}...")
    
    base_url = LLM_OPENAI_COMPATIBLE_CONFIG["base_url"]
    model = LLM_OPENAI_COMPATIBLE_CONFIG["model"]
    
    logger.info(f"✓ Provider: {LLM_OPENAI_COMPATIBLE_CONFIG['provider']}")
    logger.info(f"✓ Base URL: {base_url}")
    logger.info(f"✓ Model: {model}")
    
    # Testar conectividade
    logger.info("\n📡 Testando conectividade com API...")
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": "Responda com uma única palavra: 'funcionando'"
                }
            ],
            "temperature": 0.3,
            "max_tokens": 100,
        }
        
        response = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            logger.info("✅ Conexão bem-sucedida!")
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            logger.info(f"✓ Resposta do modelo: {content[:50]}")
            return True
        else:
            logger.error(f"❌ API retornou status {response.status_code}")
            logger.error(f"Response: {response.text[:500]}")
            return False
            
    except requests.exceptions.Timeout:
        logger.error("❌ Timeout na conexão (30s)")
        return False
    except requests.exceptions.ConnectionError as e:
        logger.error(f"❌ Erro de conexão: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Erro ao testar: {e}")
        return False


def test_fallback_routing():
    """Testar roteamento de fallback: GPU → OpenAI-compatible"""
    logger.info("\n🔍 Testando roteamento de fallback...")
    
    ollama_available = test_ollama_availability()
    
    if ollama_available:
        logger.info("✅ GPU disponível - usando localmente (recomendado)")
        logger.info("ℹ️  Para testar OpenAI-compatible manualmente:")
        logger.info("   OPENAI_COMPATIBLE_ENABLED=true python3 test_openai_compatible_model.py")
    else:
        logger.info("⚠️  GPU não disponível - usando fallback OpenAI-compatible")
        success = test_openai_compatible()
        if success:
            logger.info("\n✅ Fallback OpenAI-compatible FUNCIONAL")
        else:
            logger.error("\n❌ Fallback OpenAI-compatible com ERRO")
        return success
    
    return True


def main():
    """Teste completo"""
    logger.info("="*60)
    logger.info("TESTE DE INTEGRAÇÃO - MODELO OpenAI-compatible (sk-or-v1)")
    logger.info("="*60)
    
    # Mostrar configuração
    logger.info("\n📋 Configuração detectada:")
    logger.info(f"  Provider: {LLM_OPENAI_COMPATIBLE_CONFIG['provider']}")
    logger.info(f"  Enabled: {LLM_OPENAI_COMPATIBLE_CONFIG['enabled']}")
    logger.info(f"  Fallback Only: {LLM_OPENAI_COMPATIBLE_CONFIG['use_as_fallback_only']}")
    
    # Testar roteamento
    success = test_fallback_routing()
    
    logger.info("\n" + "="*60)
    if success:
        logger.info("✅ TESTE COMPLETO COM SUCESSO!")
    else:
        logger.error("❌ TESTE FAILED - Verificar configuração")
    logger.info("="*60)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
