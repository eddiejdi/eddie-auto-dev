"""Run Diretor as a long-running service that listens on the AgentCommunicationBus.

This service subscribes to REQUEST messages targeted to 'Diretor' or 'diretor',
and orchestrates task delegation to specialized agents.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import time
import traceback

logger = logging.getLogger("dev_agent.diretor_service")


def _should_delegate_to_huggingface(content: str) -> bool:
    """Decide se a requisição deve ser delegada ao agente Hugging Face de imagem."""
    lowered = content.lower()
    keywords = (
        "huggingface",
        "hf inference",
        "inference-api",
        "text-to-image",
        "gerar imagem",
        "criar imagem",
        "generate image",
    )
    return any(keyword in lowered for keyword in keywords)


def _extract_huggingface_prompt(content: str) -> str:
    """Extrai prompt de imagem da mensagem, com fallback para o próprio conteúdo."""
    stripped = content.strip()
    if not stripped:
        return "Arte digital abstrata, alta qualidade, iluminação cinematográfica."
    return stripped


def _should_list_huggingface_resources(content: str) -> bool:
    """Identifica se o pedido envolve listagem de recursos/modelos disponíveis."""
    lowered = content.lower()
    keywords = (
        "listar recursos",
        "recursos disponíveis",
        "quais modelos",
        "list models",
        "available resources",
    )
    return any(keyword in lowered for keyword in keywords)


def _run_huggingface_resources() -> str:
    """Consulta recursos disponíveis da integração Hugging Face."""
    from specialized_agents.huggingface_inference_agent import get_huggingface_client

    result = asyncio.run(get_huggingface_client().list_available_resources())
    return str(result)


def _run_huggingface_generation(content: str, metadata: dict[str, object] | None) -> str:
    """Executa geração de imagem via agente Hugging Face e serializa o resultado."""
    from specialized_agents.huggingface_inference_agent import (
        HFImageGenerateRequest,
        get_huggingface_client,
    )

    prompt = _extract_huggingface_prompt(content)
    data = metadata or {}
    payload = HFImageGenerateRequest(
        prompt=prompt,
        model=(str(data.get("model")) if data.get("model") else None),
        width=int(data.get("width", 1024)),
        height=int(data.get("height", 1024)),
        steps=int(data.get("steps", 30)),
        guidance_scale=float(data.get("guidance_scale", 7.0)),
        save_to_disk=bool(data.get("save_to_disk", True)),
    )
    result = asyncio.run(get_huggingface_client().generate_image(payload))
    return str(result)


def handle_message(msg) -> None:
    from specialized_agents.agent_communication_bus import (
        AgentCommunicationBus,
        MessageType,
    )

    bus = AgentCommunicationBus()
    if msg.message_type.value != "request":
        return
    if msg.target not in ("Diretor", "diretor", "agent_diretor"):
        return

    logger.info("[DiretorService] Received request from %s", msg.source)
    request_id = msg.metadata.get("request_id", msg.id)

    try:
        if _should_delegate_to_huggingface(msg.content):
            if _should_list_huggingface_resources(msg.content):
                logger.info("[DiretorService] Delegando listagem de recursos ao agente Hugging Face")
                response_content = _run_huggingface_resources()
            else:
                logger.info("[DiretorService] Delegando requisição de imagem ao agente Hugging Face")
                response_content = _run_huggingface_generation(msg.content, msg.metadata)
        else:
            from dev_agent.config import OLLAMA_HOST, OLLAMA_MODEL
            from dev_agent.agent import DevAgent
            from dev_agent.coordinator import CoordinatorAgent

            agent = DevAgent(llm_url=OLLAMA_HOST, model=OLLAMA_MODEL)
            rag_url = os.getenv("RAG_API_URL", "")
            coordinator = CoordinatorAgent(dev_agent=agent, rag_api_url=rag_url)
            result = coordinator.decide_and_execute(msg.content)
            response_content = str(result)
    except Exception:
        response_content = "[DiretorService] handler error:\n" + traceback.format_exc()
        logger.error(response_content)

    bus.publish(
        message_type=MessageType.RESPONSE,
        source="Diretor",
        target=msg.source,
        content=response_content,
        metadata={"request_id": request_id},
    )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    from specialized_agents.agent_communication_bus import AgentCommunicationBus

    bus = AgentCommunicationBus()
    bus.recording = True
    bus.subscribe(handle_message)

    logger.info("[DiretorService] Listening for requests on the AgentCommunicationBus...")

    stop = False

    def _handle_signal(sig, frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    try:
        while not stop:
            time.sleep(1)
    finally:
        bus.unsubscribe(handle_message)
        logger.info("[DiretorService] Shutting down")


if __name__ == "__main__":
    main()
