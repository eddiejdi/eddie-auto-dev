"""Integração com Hugging Face Inference API para recursos de mídia.

Este módulo expõe endpoints para:
- Descobrir recursos disponíveis para geração de imagem
- Gerar imagem via Inference API
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import aiohttp
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from specialized_agents.config import HUGGINGFACE_INFERENCE_CONFIG, MEDIA_GENERATION_CONFIG

logger = logging.getLogger(__name__)

router = APIRouter()


class HFImageGenerateRequest(BaseModel):
    """Payload para geração de imagem via Hugging Face."""

    prompt: str = Field(min_length=1, max_length=4000)
    model: str | None = Field(default=None, max_length=300)
    negative_prompt: str | None = Field(default=None, max_length=2000)
    width: int = Field(default=1024, ge=256, le=1536)
    height: int = Field(default=1024, ge=256, le=1536)
    steps: int = Field(default=30, ge=1, le=80)
    guidance_scale: float = Field(default=7.0, ge=1.0, le=20.0)
    save_to_disk: bool = Field(default=True)


class HuggingFaceInferenceClient:
    """Cliente assíncrono para o Hugging Face Inference API."""

    def __init__(self) -> None:
        self.base_url = str(HUGGINGFACE_INFERENCE_CONFIG.get("base_url", "")).rstrip("/")
        self.api_token = str(HUGGINGFACE_INFERENCE_CONFIG.get("api_token", ""))
        self.default_image_model = str(
            HUGGINGFACE_INFERENCE_CONFIG.get(
                "default_image_model", "stabilityai/stable-diffusion-xl-base-1.0"
            )
        )
        self.resources_limit = int(HUGGINGFACE_INFERENCE_CONFIG.get("resources_limit", 12))
        self.timeout_seconds = int(HUGGINGFACE_INFERENCE_CONFIG.get("timeout_seconds", 90))
        self.enabled = bool(HUGGINGFACE_INFERENCE_CONFIG.get("enabled", False))
        self.output_dir = Path(MEDIA_GENERATION_CONFIG["output_dir"]) / "huggingface"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _auth_headers(self) -> dict[str, str]:
        """Monta headers de autenticação para a API da Hugging Face."""
        headers: dict[str, str] = {}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    async def list_text_to_image_models(self) -> list[dict[str, Any]]:
        """Lista modelos públicos de texto-para-imagem mais populares."""
        url = (
            "https://huggingface.co/api/models"
            f"?pipeline_tag=text-to-image&sort=downloads&direction=-1&limit={self.resources_limit}"
        )
        timeout = aiohttp.ClientTimeout(total=max(5, self.timeout_seconds // 2))
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    body = await response.text()
                    raise RuntimeError(
                        f"Falha ao listar modelos text-to-image ({response.status}): {body[:300]}"
                    )
                data = await response.json()
        models: list[dict[str, Any]] = []
        for item in data:
            models.append(
                {
                    "id": item.get("id"),
                    "downloads": item.get("downloads"),
                    "likes": item.get("likes"),
                    "private": item.get("private", False),
                }
            )
        return models

    async def get_account_status(self) -> dict[str, Any]:
        """Retorna estado da credencial Hugging Face configurada."""
        if not self.api_token:
            return {
                "configured": False,
                "authenticated": False,
                "message": "HF_TOKEN/HUGGINGFACEHUB_API_TOKEN não configurado.",
            }

        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                "https://huggingface.co/api/whoami-v2",
                headers=self._auth_headers(),
            ) as response:
                if response.status == 200:
                    payload = await response.json()
                    return {
                        "configured": True,
                        "authenticated": True,
                        "name": payload.get("name"),
                        "type": payload.get("type"),
                    }
                body = await response.text()
                return {
                    "configured": True,
                    "authenticated": False,
                    "status_code": response.status,
                    "message": body[:300],
                }

    async def list_available_resources(self) -> dict[str, Any]:
        """Consolida recursos disponíveis para uso pelo orquestrador."""
        account = await self.get_account_status()
        models: list[dict[str, Any]] = []
        error: str | None = None

        try:
            models = await self.list_text_to_image_models()
        except Exception as exc:
            error = str(exc)

        configured_local_image_models = [
            {
                "id": pipeline.get("model_id"),
                "name": pipeline.get("name"),
                "runtime": "local_diffusers_gpu0",
            }
            for pipeline in MEDIA_GENERATION_CONFIG.get("pipelines", {}).values()
            if pipeline.get("type") == "image"
        ]

        return {
            "enabled": self.enabled,
            "provider": "huggingface-inference-api",
            "base_url": self.base_url,
            "default_image_model": self.default_image_model,
            "account": account,
            "remote_text_to_image_models": models,
            "local_gpu0_image_pipelines": configured_local_image_models,
            "resources_fetch_error": error,
        }

    async def generate_image(self, request: HFImageGenerateRequest) -> dict[str, Any]:
        """Gera imagem a partir de prompt usando Hugging Face Inference API."""
        if not self.enabled:
            raise RuntimeError("Integração Hugging Face está desabilitada (HF_INFERENCE_ENABLED=false).")
        if not self.api_token:
            raise RuntimeError("Token Hugging Face não configurado em HF_TOKEN.")

        model_id = request.model or self.default_image_model
        endpoint = f"{self.base_url}/models/{model_id}"
        payload: dict[str, Any] = {
            "inputs": request.prompt,
            "parameters": {
                "width": request.width,
                "height": request.height,
                "num_inference_steps": request.steps,
                "guidance_scale": request.guidance_scale,
            },
        }
        if request.negative_prompt:
            payload["parameters"]["negative_prompt"] = request.negative_prompt

        headers = {
            **self._auth_headers(),
            "Content-Type": "application/json",
            "Accept": "image/png",
        }

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(endpoint, json=payload, headers=headers) as response:
                content_type = response.headers.get("Content-Type", "")
                if response.status != 200:
                    body = await response.text()
                    raise RuntimeError(
                        f"Hugging Face retornou {response.status}: {body[:500]}"
                    )

                image_bytes = await response.read()
                if "image/" not in content_type and not image_bytes:
                    raise RuntimeError("Resposta inválida da API de imagem.")

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_model = model_id.replace("/", "_").replace(":", "_")
        file_name = f"hf_{safe_model}_{timestamp}.png"
        file_path = self.output_dir / file_name

        if request.save_to_disk:
            file_path.write_bytes(image_bytes)

        image_b64 = base64.b64encode(image_bytes).decode("ascii")

        return {
            "success": True,
            "provider": "huggingface-inference-api",
            "model": model_id,
            "bytes": len(image_bytes),
            "content_type": "image/png",
            "file_path": str(file_path) if request.save_to_disk else None,
            "image_base64": image_b64,
        }


_client_instance: HuggingFaceInferenceClient | None = None


def get_huggingface_client() -> HuggingFaceInferenceClient:
    """Retorna singleton do cliente Hugging Face."""
    global _client_instance
    if _client_instance is None:
        _client_instance = HuggingFaceInferenceClient()
    return _client_instance


@router.get("/resources")
async def huggingface_resources() -> dict[str, Any]:
    """Lista recursos disponíveis da integração Hugging Face para o orquestrador."""
    try:
        return await get_huggingface_client().list_available_resources()
    except Exception as exc:
        logger.error("Erro ao listar recursos Hugging Face: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/image/generate")
async def huggingface_generate_image(payload: HFImageGenerateRequest) -> dict[str, Any]:
    """Gera imagem via Hugging Face Inference API."""
    try:
        return await get_huggingface_client().generate_image(payload)
    except Exception as exc:
        logger.error("Erro na geração de imagem Hugging Face: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
