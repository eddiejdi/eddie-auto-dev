#!/usr/bin/env python3
"""
Endpoint FastAPI para GitHub Copilot com modelo sk-or como fallback

Fornece:
- GET /v1/models - Lista modelos disponíveis
- POST /v1/chat/completions - Chat com fallback automático (GPU0 → GPU1 → sk-or)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

from .copilot_model_router import get_copilot_router, get_active_model_info

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = None
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.3
    max_tokens: Optional[int] = 8192
    top_p: Optional[float] = 0.9


@router.get("/v1/models")
async def list_models() -> Dict[str, Any]:
    """
    Listar modelos disponíveis (compatível com OpenAI API).
    
    Inclui informações de qual modelo será usado (GPU0/GPU1/sk-or).
    """
    model_info = await get_active_model_info()
    
    if model_info.get("status") != "ok":
        raise HTTPException(status_code=503, detail="No models available")
    
    return {
        "object": "list",
        "data": [
            {
                "id": model_info["model"],
                "object": "model",
                "owned_by": "shared-auto-dev",
                "permission": [],
                "created": 1704067200,
                "root": model_info["model"],
                "parent": None,
                "provider": model_info["provider"],
                "gpu": model_info.get("gpu", "UNKNOWN"),
            }
        ]
    }


@router.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest) -> Dict[str, Any]:
    """
    Chat completion com modelo automático (GPU0 → GPU1 → sk-or fallback).
    
    Compatível com OpenAI API.
    
    Body:
    {
        "messages": [
            {"role": "user", "content": "olá"},
        ],
        "temperature": 0.3,
        "max_tokens": 8192,
    }
    """
    try:
        router_instance = get_copilot_router()
        
        # Converter mensagens para dicts
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        
        # Chamar router com fallback
        response = await router_instance.proxy_chat_completion(
            messages=messages,
            temperature=request.temperature or 0.3,
            max_tokens=request.max_tokens or 8192,
            top_p=request.top_p or 0.9,
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Chat completion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/copilot/model-info")
async def model_info() -> Dict[str, Any]:
    """
    Informações do modelo ativo (para debug/monitoring).
    
    Response:
    {
        "status": "ok",
        "provider": "ollama" | "openai_compatible",
        "model": "qwen2.5-coder:7b",
        "gpu": "GPU0" | "GPU1" | "CLOUD",
        "base_url": "http://..."
    }
    """
    return await get_active_model_info()
