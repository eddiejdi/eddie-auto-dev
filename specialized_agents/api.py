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

OLLAMA_API_HOST = os.getenv("OLLAMA_API_HOST", "").rstrip("/")
OLLAMA_BACKGROUND_MODEL = os.getenv("OLLAMA_BACKGROUND_MODEL", "phi4-mini:latest")
OLLAMA_REQUEST_TIMEOUT = float(os.getenv("OLLAMA_REQUEST_TIMEOUT", "20"))


def _candidate_ollama_hosts() -> list[str]:
    configured = [host.strip().rstrip("/") for host in os.getenv("OLLAMA_API_HOSTS", "").split(",") if host.strip()]
    defaults = [
        OLLAMA_API_HOST,
        "http://192.168.15.2:11434",
        "http://127.0.0.1:11434",
        "http://192.168.15.2:11435",
        "http://127.0.0.1:11435",
    ]
    ordered = configured + defaults
    unique: list[str] = []
    for host in ordered:
        if host and host not in unique:
            unique.append(host)
    return unique


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
        "ollama_host": _candidate_ollama_hosts()[0],
        "ollama_candidates": _candidate_ollama_hosts(),
        "ollama_model": OLLAMA_BACKGROUND_MODEL,
    }


@app.post("/llm-tools/chat")
def llm_tools_chat(payload: LlmChatRequest) -> dict[str, Any]:
    model = (payload.model or OLLAMA_BACKGROUND_MODEL).strip() or OLLAMA_BACKGROUND_MODEL
    last_error: Exception | None = None
    data: dict[str, Any] | None = None
    selected_host = ""

    for host in _candidate_ollama_hosts():
        try:
            response = requests.post(
                f"{host}/api/generate",
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
            selected_host = host
            break
        except requests.RequestException as exc:
            last_error = exc
            continue

    if data is None:
        if isinstance(last_error, requests.Timeout):
            raise HTTPException(status_code=504, detail="Ollama timeout") from last_error
        logger.exception("Ollama request failed across all hosts")
        raise HTTPException(status_code=502, detail=f"Ollama request failed: {last_error}") from last_error

    answer = (data.get("response") or "").strip()
    if not answer:
        raise HTTPException(status_code=502, detail="Ollama returned empty response")

    return {
        "answer": answer,
        "model": model,
        "ollama_host": selected_host,
        "conversation_id": payload.conversation_id,
    }
