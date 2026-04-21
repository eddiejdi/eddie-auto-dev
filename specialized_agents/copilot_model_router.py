#!/usr/bin/env python3
"""
Integração do modelo OpenAI-compatible (sk-or-v1) com GitHub Copilot

Fornece fallback automático:
- GPU0/GPU1 (Ollama local) → MODEL sk-or via OpenAI-compatible API
- Usado como fallback quando GPUs não estão disponíveis
"""

import os
import logging
import asyncio
import json
from typing import Optional, Dict, Any
import aiohttp

from specialized_agents.config import (
    LLM_CONFIG,
    LLM_GPU1_CONFIG,
    LLM_OPENAI_COMPATIBLE_CONFIG,
)

logger = logging.getLogger(__name__)


class CopilotModelRouter:
    """
    Roteador de modelos para GitHub Copilot com fallback automático.
    
    Ordem de tentativa:
    1. GPU0 (Ollama local - qwen2.5-coder:7b)
    2. GPU1 (Ollama GPU1 - qwen3:0.6b)
    3. OpenAI-compatible (sk-or-v1 via OpenRouter)
    """
    
    def __init__(self):
        self.gpu0_url = LLM_CONFIG.get("base_url", "http://192.168.15.2:11434")
        self.gpu1_url = LLM_GPU1_CONFIG.get("base_url", "http://192.168.15.2:11435")
        self.openai_compat_url = LLM_OPENAI_COMPATIBLE_CONFIG.get(
            "base_url", "https://openrouter.ai/api/v1"
        )
        self.openai_compat_key = LLM_OPENAI_COMPATIBLE_CONFIG.get("api_key", "")
        self.timeout = 5  # segundos para considerar GPU indisponível
        
    async def _test_endpoint(self, url: str, timeout: int = 3) -> bool:
        """Testar se endpoint está disponível"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as resp:
                    return resp.status == 200
        except Exception:
            return False
    
    async def get_available_model(self) -> Dict[str, Any]:
        """
        Retorna o modelo disponível (primeiro que responde).
        
        Returns:
            {
                "provider": "ollama" | "openai_compatible",
                "model": "qwen2.5-coder:7b" | "gpt-4",
                "base_url": "http://...",
                "available": True/False
            }
        """
        # Testar GPU0
        gpu0_ok = await self._test_endpoint(self.gpu0_url, self.timeout)
        if gpu0_ok:
            return {
                "provider": "ollama",
                "model": LLM_CONFIG.get("model", "qwen2.5-coder:7b"),
                "base_url": self.gpu0_url,
                "gpu": "GPU0",
                "available": True
            }
        
        logger.warning("⚠️  GPU0 não respondeu, testando GPU1...")
        
        # Testar GPU1
        gpu1_ok = await self._test_endpoint(self.gpu1_url, self.timeout)
        if gpu1_ok:
            return {
                "provider": "ollama",
                "model": LLM_GPU1_CONFIG.get("model", "qwen3:0.6b"),
                "base_url": self.gpu1_url,
                "gpu": "GPU1",
                "available": True
            }
        
        logger.warning("⚠️  GPU1 não respondeu, usando fallback OpenAI-compatible...")
        
        # Usar OpenAI-compatible como fallback
        if self.openai_compat_key:
            return {
                "provider": "openai_compatible",
                "model": LLM_OPENAI_COMPATIBLE_CONFIG.get("model", "gpt-4"),
                "base_url": self.openai_compat_url,
                "api_key": self.openai_compat_key,
                "gpu": "CLOUD",
                "available": True
            }
        
        logger.error("❌ Nenhum modelo disponível!")
        return {"available": False}
    
    async def proxy_chat_completion(
        self,
        messages: list,
        temperature: float = 0.3,
        max_tokens: int = 8192,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Proxy para chat completion com fallback automático.
        
        Usa o modelo disponível (GPU0 → GPU1 → OpenAI-compatible)
        """
        model_info = await self.get_available_model()
        
        if not model_info.get("available"):
            raise Exception("Nenhum modelo disponível (GPU e OpenAI-compatible)")
        
        provider = model_info["provider"]
        
        if provider == "ollama":
            return await self._call_ollama(
                model_info["base_url"],
                model_info["model"],
                messages,
                temperature,
                max_tokens,
                **kwargs
            )
        else:  # openai_compatible
            return await self._call_openai_compatible(
                model_info["base_url"],
                model_info["model"],
                model_info.get("api_key"),
                messages,
                temperature,
                max_tokens,
                **kwargs
            )
    
    async def _call_ollama(
        self,
        base_url: str,
        model: str,
        messages: list,
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> Dict[str, Any]:
        """Chamar Ollama"""
        url = f"{base_url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        raise Exception(f"Ollama error: {resp.status}")
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            raise
    
    async def _call_openai_compatible(
        self,
        base_url: str,
        model: str,
        api_key: Optional[str],
        messages: list,
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> Dict[str, Any]:
        """Chamar provedor OpenAI-compatible"""
        url = f"{base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        headers = {
            "Content-Type": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        raise Exception(
                            f"OpenAI-compatible error: {resp.status} - {await resp.text()}"
                        )
        except Exception as e:
            logger.error(f"OpenAI-compatible call failed: {e}")
            raise


# Singleton instance
_router_instance: Optional[CopilotModelRouter] = None


def get_copilot_router() -> CopilotModelRouter:
    """Obter instância singleton do router"""
    global _router_instance
    if _router_instance is None:
        _router_instance = CopilotModelRouter()
    return _router_instance


async def get_active_model_info() -> Dict[str, Any]:
    """Info do modelo ativo (para display)"""
    router = get_copilot_router()
    model_info = await router.get_available_model()
    
    if not model_info.get("available"):
        return {"status": "error", "message": "Nenhum modelo disponível"}
    
    return {
        "status": "ok",
        "provider": model_info["provider"],
        "model": model_info["model"],
        "gpu": model_info.get("gpu", "UNKNOWN"),
        "base_url": model_info["base_url"],
    }


if __name__ == "__main__":
    # Teste rápido
    async def test():
        router = get_copilot_router()
        info = await get_active_model_info()
        print(json.dumps(info, indent=2))
    
    asyncio.run(test())
