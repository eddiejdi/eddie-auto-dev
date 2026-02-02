"""
Rotas para coordenação distribuída - Copilot vs Agentes Especializados
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging

from specialized_agents.distributed_coordinator import get_distributed_coordinator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/distributed", tags=["distributed"])

coordinator = get_distributed_coordinator()


@router.post("/route-task")
async def route_task(language: str, task: Dict[str, Any]) -> Dict[str, Any]:
    """
    Roteia uma tarefa para Copilot ou Agente baseado em precisão

    Query params:
        language: python, javascript, typescript, go, rust, java, csharp, php
        task: Descrição da tarefa em JSON
    """
    try:
        result = await coordinator.route_task(language, task)
        return {"status": "success", "result": result}
    except Exception as e:
        logger.error(f"Erro ao rotear tarefa: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/precision-dashboard")
def get_precision_dashboard() -> Dict[str, Any]:
    """Retorna dashboard de precisão dos agentes"""
    return coordinator.get_precision_dashboard()


@router.get("/agent-stats/{language}")
def get_agent_stats(language: str) -> Dict[str, Any]:
    """Retorna estatísticas de precisão de um agente específico"""
    score = coordinator.precision_scores.get(language)

    if not score:
        raise HTTPException(status_code=404, detail=f"Agente {language} não encontrado")

    return {
        "language": language,
        "precision": f"{score.precision:.1f}%",
        "total_tasks": score.total_tasks,
        "successful_tasks": score.successful_tasks,
        "failed_tasks": score.failed_tasks,
        "avg_execution_time": f"{score.avg_execution_time:.2f}s",
        "copilot_usage": f"{score.copilot_usage_ratio * 100:.0f}%",
        "status": (
            "🟢 Confiável"
            if score.precision >= 95
            else (
                "🟡 Bom"
                if score.precision >= 85
                else "🟠 Aceitável" if score.precision >= 70 else "🔴 Baixo"
            )
        ),
    }


@router.post("/record-result")
def record_result(
    language: str, success: bool, execution_time: float = 0.0
) -> Dict[str, Any]:
    """Registra resultado de uma execução para atualizar score de precisão"""
    try:
        if success:
            coordinator._record_success(language, {"execution_time": execution_time})
        else:
            coordinator._record_failure(language)

        score = coordinator.precision_scores.get(language)
        return {
            "status": "success",
            "language": language,
            "precision": f"{score.precision:.1f}%",
            "copilot_usage_ratio": f"{score.copilot_usage_ratio * 100:.0f}%",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
