from __future__ import annotations

import logging
import os
from typing import Any

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from specialized_agents.storage_access import router as storage_router

logger = logging.getLogger(__name__)

app = FastAPI(title="Specialized Agents API", version="2026.03.15")
app.include_router(storage_router)

OLLAMA_API_HOST = os.getenv("OLLAMA_API_HOST", "http://127.0.0.1:11435").rstrip("/")
OLLAMA_BACKGROUND_MODEL = os.getenv("OLLAMA_BACKGROUND_MODEL", "qwen3:0.6b")
OLLAMA_REQUEST_TIMEOUT = float(os.getenv("OLLAMA_REQUEST_TIMEOUT", "20"))


class LlmChatRequest(BaseModel):
    prompt: str
    model: str | None = None
    max_rounds: int | None = 1
    use_native_tools: bool | None = False
    conversation_id: str | None = None


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "ollama_host": OLLAMA_API_HOST,
        "ollama_model": OLLAMA_BACKGROUND_MODEL,
    }


@app.post("/llm-tools/chat")
def llm_tools_chat(payload: LlmChatRequest) -> dict[str, Any]:
    model = (payload.model or OLLAMA_BACKGROUND_MODEL).strip() or OLLAMA_BACKGROUND_MODEL
    try:
        response = requests.post(
            f"{OLLAMA_API_HOST}/api/generate",
            json={
                "model": model,
                "prompt": payload.prompt,
                "stream": False,
                "options": {
                    "temperature": 0.9,
                    "num_predict": 1800,
                },
            },
            timeout=OLLAMA_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except requests.Timeout as exc:
        raise HTTPException(status_code=504, detail="Ollama timeout") from exc
    except requests.RequestException as exc:
        logger.exception("Ollama request failed")
        raise HTTPException(status_code=502, detail=f"Ollama request failed: {exc}") from exc

    answer = (data.get("response") or "").strip()
    if not answer:
        raise HTTPException(status_code=502, detail="Ollama returned empty response")

    return {
        "answer": answer,
        "model": model,
        "conversation_id": payload.conversation_id,
    }
