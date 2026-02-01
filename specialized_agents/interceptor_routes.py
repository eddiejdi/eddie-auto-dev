"""
API REST para Interceptação de Conversas
Endpoints para acessar dados de conversas interceptadas
"""

from fastapi import APIRouter, Query, HTTPException, WebSocket, WebSocketDisconnect
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import asyncio
import logging

from .agent_interceptor import get_agent_interceptor, ConversationPhase
from .agent_communication_bus import get_communication_bus, MessageType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interceptor", tags=["Interceptor de Conversas"])


# ============================================================================
# ENDPOINTS DE CONVERSAS
# ============================================================================


@router.get("/conversations/active")
async def get_active_conversations(
    agent: Optional[str] = Query(None, description="Filtrar por agente"),
    phase: Optional[str] = Query(None, description="Filtrar por fase"),
):
    """Lista conversas ativas"""
    interceptor = get_agent_interceptor()
    convs = interceptor.list_active_conversations()

    if agent:
        convs = [
            c
            for c in convs
            if any(agent.lower() in p.lower() for p in c["participants"])
        ]

    if phase:
        convs = [c for c in convs if c["phase"].upper() == phase.upper()]

    return {"status": "success", "count": len(convs), "conversations": convs}


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Obtém detalhes de uma conversa específica"""
    interceptor = get_agent_interceptor()
    conv = interceptor.get_conversation(conversation_id)

    if not conv:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")

    return {"status": "success", "conversation": conv}


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=1000),
    message_type: Optional[str] = Query(None),
):
    """Obtém mensagens de uma conversa"""
    interceptor = get_agent_interceptor()

    message_types = [message_type] if message_type else None
    messages = interceptor.get_conversation_messages(conversation_id, message_types)

    return {
        "status": "success",
        "conversation_id": conversation_id,
        "count": len(messages),
        "messages": messages[-limit:],
    }


@router.get("/conversations/{conversation_id}/analysis")
async def analyze_conversation(conversation_id: str):
    """Obtém análise detalhada de uma conversa"""
    interceptor = get_agent_interceptor()
    analysis = interceptor.analyze_conversation(conversation_id)

    if not analysis:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")

    return {"status": "success", "analysis": analysis}


@router.get("/conversations/history")
async def get_conversation_history(
    limit: int = Query(50, ge=1, le=500),
    agent: Optional[str] = Query(None),
    phase: Optional[str] = Query(None),
    since_hours: Optional[int] = Query(None, description="Últimas N horas"),
):
    """Obtém histórico de conversas"""
    interceptor = get_agent_interceptor()

    since = None
    if since_hours:
        since = datetime.now() - timedelta(hours=since_hours)

    convs = interceptor.list_conversations(
        limit=limit, agent=agent, phase=phase, since=since
    )

    return {"status": "success", "count": len(convs), "conversations": convs}


@router.post("/conversations/{conversation_id}/finalize")
async def finalize_conversation(conversation_id: str):
    """Finaliza uma conversa"""
    interceptor = get_agent_interceptor()
    success = interceptor.finalize_conversation(conversation_id)

    if not success:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")

    return {"status": "success", "message": f"Conversa {conversation_id} finalizada"}


@router.post("/conversations/{conversation_id}/snapshot")
async def take_conversation_snapshot(conversation_id: str):
    """Tira snapshot de uma conversa"""
    interceptor = get_agent_interceptor()
    snapshot = interceptor.take_snapshot(conversation_id)

    if not snapshot:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")

    return {
        "status": "success",
        "snapshot": {
            "conversation_id": snapshot.conversation_id,
            "timestamp": snapshot.timestamp.isoformat(),
            "phase": snapshot.phase.value,
            "participants": snapshot.participants,
            "message_count": snapshot.message_count,
            "duration_seconds": snapshot.duration_seconds,
        },
    }


# ============================================================================
# ENDPOINTS DE EXPORTAÇÃO
# ============================================================================


@router.get("/conversations/{conversation_id}/export")
async def export_conversation(
    conversation_id: str, format: str = Query("json", regex="^(json|markdown|text)$")
):
    """Exporta conversa em formato específico"""
    interceptor = get_agent_interceptor()
    exported = interceptor.export_conversation(conversation_id, format)

    if not exported:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")

    return {
        "status": "success",
        "format": format,
        "conversation_id": conversation_id,
        "content": exported,
    }


# ============================================================================
# ENDPOINTS DE ESTATÍSTICAS
# ============================================================================


@router.get("/stats")
async def get_interceptor_stats():
    """Obtém estatísticas do interceptador"""
    interceptor = get_agent_interceptor()
    bus = get_communication_bus()

    interceptor_stats = interceptor.get_stats()
    bus_stats = bus.get_stats()

    return {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "interceptor": interceptor_stats,
        "communication_bus": bus_stats,
    }


@router.get("/stats/by-phase")
async def get_stats_by_phase():
    """Obtém estatísticas agrupadas por fase"""
    interceptor = get_agent_interceptor()

    phases = {}
    for phase in ConversationPhase:
        convs = interceptor.list_conversations(phase=phase.value, limit=1000)
        phases[phase.value] = {
            "count": len(convs),
            "avg_duration": (
                sum(c["duration_seconds"] for c in convs) / len(convs) if convs else 0
            ),
            "avg_messages": (
                sum(c["message_count"] for c in convs) / len(convs) if convs else 0
            ),
        }

    return {"status": "success", "by_phase": phases}


@router.get("/stats/by-agent")
async def get_stats_by_agent():
    """Obtém estatísticas agrupadas por agente"""
    bus = get_communication_bus()

    messages = bus.get_messages(limit=10000)
    agents = {}

    for msg in messages:
        if msg.source not in agents:
            agents[msg.source] = {"sent": 0, "received": 0}
        if msg.target not in agents:
            agents[msg.target] = {"sent": 0, "received": 0}

        agents[msg.source]["sent"] += 1
        agents[msg.target]["received"] += 1

    return {"status": "success", "by_agent": agents}


# ============================================================================
# ENDPOINTS DE CONTROLE
# ============================================================================


@router.post("/recording/pause")
async def pause_recording():
    """Pausa a gravação de mensagens"""
    bus = get_communication_bus()
    bus.pause_recording()

    return {"status": "success", "message": "Gravação pausada", "recording": False}


@router.post("/recording/resume")
async def resume_recording():
    """Retoma a gravação de mensagens"""
    bus = get_communication_bus()
    bus.resume_recording()

    return {"status": "success", "message": "Gravação retomada", "recording": True}


@router.post("/recording/clear")
async def clear_recording():
    """Limpa buffer de mensagens"""
    bus = get_communication_bus()
    bus.clear()

    return {"status": "success", "message": "Buffer limpo"}


@router.post("/filters/{message_type}/{enabled}")
async def set_message_filter(message_type: str, enabled: bool):
    """Ativa/desativa filtro de tipo de mensagem"""
    bus = get_communication_bus()

    # Validar tipo
    valid_types = [mt.value for mt in MessageType]
    if message_type.lower() not in valid_types:
        raise HTTPException(status_code=400, detail=f"Tipo inválido: {message_type}")

    bus.set_filter(message_type.lower(), enabled)

    return {
        "status": "success",
        "message": f"Filtro {message_type} {'ativado' if enabled else 'desativado'}",
        "filters": bus.active_filters,
    }


# ============================================================================
# WEBSOCKET PARA TEMPO REAL
# ============================================================================


class ConnectionManager:
    """Gerencia conexões WebSocket"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


@router.websocket("/ws/conversations")
async def websocket_conversations(websocket: WebSocket):
    """WebSocket para receber atualizações de conversas em tempo real"""
    await manager.connect(websocket)
    interceptor = get_agent_interceptor()

    def on_conversation_event(event: Dict[str, Any]):
        """Callback para novos eventos de conversa"""
        asyncio.create_task(manager.broadcast(event))

    interceptor.subscribe_conversation_events(on_conversation_event)

    try:
        while True:
            # Manter conexão aberta
            data = await websocket.receive_text()

            # Processar comandos (opcional)
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        interceptor.unsubscribe_conversation_events(on_conversation_event)


@router.websocket("/ws/messages")
async def websocket_messages(websocket: WebSocket):
    """WebSocket para receber mensagens em tempo real"""
    await manager.connect(websocket)
    bus = get_communication_bus()

    def on_message(message):
        """Callback para novas mensagens"""
        asyncio.create_task(manager.broadcast(message.to_dict()))

    bus.subscribe(on_message)

    try:
        while True:
            # Manter conexão aberta
            data = await websocket.receive_text()

            # Processar comandos
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        bus.unsubscribe(on_message)


# ============================================================================
# ENDPOINTS DE BUSCA
# ============================================================================


@router.get("/search/by-content")
async def search_conversations_by_content(
    query: str, limit: int = Query(20, ge=1, le=100)
):
    """Busca conversas por conteúdo"""
    interceptor = get_agent_interceptor()
    bus = get_communication_bus()

    messages = bus.get_messages(limit=10000)
    matching_messages = [m for m in messages if query.lower() in m.content.lower()]

    # Agrupar por conversa
    conversations = {}
    for msg in matching_messages[:limit]:
        conv_id = msg.metadata.get("conversation_id", "unknown")
        if conv_id not in conversations:
            conversations[conv_id] = []
        conversations[conv_id].append(msg.to_dict())

    return {
        "status": "success",
        "query": query,
        "matches": len(matching_messages),
        "conversations": conversations,
    }


@router.get("/search/by-agent")
async def search_conversations_by_agent(agent: str):
    """Busca conversas de um agente específico"""
    interceptor = get_agent_interceptor()

    convs = interceptor.list_conversations(agent=agent, limit=1000)

    return {
        "status": "success",
        "agent": agent,
        "count": len(convs),
        "conversations": convs,
    }


@router.get("/search/by-phase")
async def search_conversations_by_phase(phase: str):
    """Busca conversas por fase"""
    interceptor = get_agent_interceptor()

    # Validar fase
    valid_phases = [p.value for p in ConversationPhase]
    if phase.lower() not in valid_phases:
        raise HTTPException(status_code=400, detail=f"Fase inválida: {phase}")

    convs = interceptor.list_conversations(phase=phase.lower(), limit=1000)

    return {
        "status": "success",
        "phase": phase,
        "count": len(convs),
        "conversations": convs,
    }
