#!/usr/bin/env python3
"""
Review API Routes — Endpoints FastAPI para o sistema de review
"""
import json
from typing import Optional, List

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from .review_agent import ReviewAgent
from .review_queue import get_review_queue

router = APIRouter(prefix="/review", tags=["Code Review"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class SubmitReviewRequest(BaseModel):
    commit_id: str
    branch: str
    author_agent: str
    diff: str
    files_changed: List[str]
    priority: int = 0


class ReviewActionRequest(BaseModel):
    action: str  # approve, reject, request_changes
    feedback: Optional[str] = None


# ─── Helper ───────────────────────────────────────────────────────────────────

def _review_agent():
    return ReviewAgent()


def _review_queue():
    return get_review_queue()


# ═══════════════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/submit")
async def submit_for_review(req: SubmitReviewRequest, bg_tasks: BackgroundTasks):
    """
    Submeter um commit para review.
    O ReviewAgent o processará automaticamente em background.
    
    Returns:
        queue_id para tracking
    """
    queue = _review_queue()
    
    queue_id = queue.submit_for_review(
        commit_id=req.commit_id,
        branch=req.branch,
        author_agent=req.author_agent,
        diff=req.diff,
        files_changed=req.files_changed,
        priority=req.priority,
    )
    
    return {
        "status": "submitted",
        "queue_id": queue_id,
        "message": f"Commit {req.commit_id[:7]} aguardando revisão"
    }


@router.get("/queue")
async def get_queue_status():
    """Status geral da fila"""
    queue = _review_queue()
    stats = queue.get_stats()
    return {
        "queue": stats,
        "message": f"Fila: {stats['pending']} pending, {stats['approved']} approved, {stats['merged']} merged"
    }


@router.get("/queue/{queue_id}")
async def get_review_status(queue_id: str):
    """Status de um item específico"""
    queue = _review_queue()
    item = queue.get_item(queue_id)
    
    if not item:
        raise HTTPException(status_code=404, detail="Queue item não encontrado")
    
    return {
        "queue_id": queue_id,
        "commit_id": item["commit_id"],
        "branch": item["branch"],
        "author_agent": item["author_agent"],
        "status": item["status"],
        "created_at": item["created_at"],
        "reviewed_at": item["reviewed_at"],
        "retry_count": item["retry_count"],
        "score": json.loads(item.get("review_result") or "{}").get("score", "N/A"),
    }


@router.get("/queue/pending")
async def get_pending_items(limit: int = 5):
    """Obter próximos items da fila"""
    queue = _review_queue()
    pending = queue.get_pending_items(limit)
    
    return {
        "count": len(pending),
        "items": [
            {
                "queue_id": item["queue_id"],
                "commit_id": item["commit_id"][:7],
                "author_agent": item["author_agent"],
                "branch": item["branch"],
                "priority": item["priority"],
                "created_at": item["created_at"],
            }
            for item in pending
        ]
    }


@router.get("/agent/status")
async def review_agent_status():
    """Status do ReviewAgent"""
    agent = _review_agent()
    status = agent.get_status()
    return status


@router.get("/retrospective/{agent_name}")
async def get_retrospective(agent_name: str, period_days: int = 7):
    """
    Retrospectiva de um agente: como evoluiu?
    """
    agent = _review_agent()
    
    try:
        retro = await asyncio.to_thread(
            agent.retrospective, agent_name, period_days
        )
        return retro
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/action")
async def manual_review_action(
    queue_id: str,
    action: str,
    feedback: Optional[str] = None
):
    """
    Executar ação manual (para casos que ReviewAgent não conseguiu decidir).
    
    Actions: approve, reject, request_changes
    """
    queue = _review_queue()
    item = queue.get_item(queue_id)
    
    if not item:
        raise HTTPException(status_code=404, detail="Queue item não encontrado")
    
    # Map ação para status
    status_map = {
        "approve": "approved",
        "reject": "rejected",
        "request_changes": "request_changes",
    }
    
    new_status = status_map.get(action)
    if not new_status:
        raise HTTPException(status_code=400, detail="Ação inválida")
    
    result = {
        "action": action,
        "decision": action,
        "feedback": feedback,
        "reviewed_by": "admin",
        "timestamp": None,
    }
    
    queue.update_status(queue_id, new_status, result)
    
    return {
        "status": "updated",
        "queue_id": queue_id,
        "new_status": new_status,
    }


@router.get("/metrics")
async def review_metrics():
    """Métricas gerais de review"""
    queue = _review_queue()
    agent = _review_agent()
    
    queue_stats = queue.get_stats()
    agent_status = agent.get_status()
    
    return {
        "queue": queue_stats,
        "agent": agent_status,
        "health": {
            "approval_rate": queue_stats.get("approval_rate", 0),
            "total_reviews": agent_status.get("total_reviews", 0),
            "pending_items": queue_stats.get("pending", 0),
        }
    }


@router.post("/cleanup")
async def cleanup_old_reviews(days: int = 30):
    """Limpar reviews antigos"""
    queue = _review_queue()
    cleaned = queue.cleanup_old_items(days)
    
    return {
        "status": "cleaned",
        "items_removed": cleaned,
        "reason": f"Reviews merged há mais de {days} dias"
    }


# ─── Imports (adicionado aqui pra não circular)

import asyncio
