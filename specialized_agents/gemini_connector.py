"""Gemini Connector Agent

Recebe webhooks do Gemini/Google Assistant e encaminha para o agente
de Home Automation (`GoogleAssistantAgent`) para interpretação e execução.

Endpoints:
 - POST /gemini/webhook  -> recebe {text, user_id, request_id}
 - GET  /gemini/health   -> checagem de saúde
"""
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gemini", tags=["gemini-connector"])


class GeminiCommand(BaseModel):
    text: str
    user_id: Optional[str] = None
    request_id: Optional[str] = None


@router.post("/webhook")
async def webhook(cmd: GeminiCommand) -> Dict[str, Any]:
    """Recebe comando do Gemini e encaminha ao agente de Home Automation."""
    logger.info(f"[GeminiWebhook] {cmd.text} (user={cmd.user_id})")

    try:
        from specialized_agents.home_automation.agent import get_google_assistant_agent
    except Exception:
        from specialized_agents.home_automation.agent import GoogleAssistantAgent as GA
        # Fallback: instantiate a local agent
        agent = GA()
    else:
        agent = get_google_assistant_agent()

    if not agent:
        raise HTTPException(status_code=500, detail="Home Automation agent not available")

    result = await agent.process_command(cmd.text)
    return {"success": result.get("success", False), "response": result}


@router.get("/health")
async def health():
    return {"status": "ok", "connector": "gemini-connector"}
