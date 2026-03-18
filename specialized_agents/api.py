from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from typing import Any

import requests
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from specialized_agents.conube_agent import router as conube_router
from specialized_agents.marketing_assets import router as marketing_router
from specialized_agents.storage_access import router as storage_router
from specialized_agents.agent_communication_bus import (
    get_communication_bus,
    MessageType,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Specialized Agents API", version="2026.03.15")
app.include_router(conube_router)
app.include_router(marketing_router)
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


# ==================== Communication Bus Routes ====================

class PublishRequest(BaseModel):
    """Payload para publicar mensagem no bus."""

    source: str
    target: str
    content: str
    message_type: str | None = "request"
    metadata: dict[str, Any] | None = None


@app.get("/communication/messages")
def communication_messages(
    limit: int = Query(default=100, ge=1, le=1000),
    source: str | None = Query(default=None),
    target: str | None = Query(default=None),
) -> dict[str, Any]:
    """Retorna mensagens do bus de comunicação inter-agente."""
    bus = get_communication_bus()
    messages = bus.get_messages(limit=limit, source=source, target=target)
    return {"messages": [m.to_dict() for m in messages], "total": len(messages)}


@app.post("/communication/publish")
def communication_publish(payload: PublishRequest) -> dict[str, Any]:
    """Publica mensagem no bus de comunicação."""
    bus = get_communication_bus()
    try:
        msg_type = MessageType(payload.message_type or "request")
    except ValueError:
        msg_type = MessageType.REQUEST

    msg = bus.publish(
        message_type=msg_type,
        source=payload.source,
        target=payload.target,
        content=payload.content,
        metadata=payload.metadata or {},
    )
    if msg is None:
        return {"success": False, "reason": "recording paused or filtered"}
    return {"success": True, "id": msg.id, "timestamp": msg.timestamp.isoformat()}


@app.post("/communication/send")
def communication_send(payload: PublishRequest) -> dict[str, Any]:
    """Alias para /communication/publish."""
    return communication_publish(payload)


@app.get("/communication/stats")
def communication_stats() -> dict[str, Any]:
    """Retorna estatísticas do bus de comunicação."""
    return get_communication_bus().get_stats()


@app.post("/communication/clear")
def communication_clear() -> dict[str, Any]:
    """Limpa buffer de mensagens do bus."""
    get_communication_bus().clear()
    return {"cleared": True}


@app.post("/communication/pause")
def communication_pause() -> dict[str, Any]:
    """Pausa gravação de mensagens no bus."""
    get_communication_bus().pause_recording()
    return {"recording": False}


@app.post("/communication/resume")
def communication_resume() -> dict[str, Any]:
    """Retoma gravação de mensagens no bus."""
    get_communication_bus().resume_recording()
    return {"recording": True}
