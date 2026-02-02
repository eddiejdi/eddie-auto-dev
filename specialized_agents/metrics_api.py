"""
API FastAPI para exposição de métricas Prometheus e dashboard Grafana.

Integra-se com o sistema de monitoramento existente.
"""

import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, JSONResponse
import logging

from specialized_agents.metrics_exporter import get_metrics_collector

logger = logging.getLogger(__name__)


# Router para métricas
metrics_router = APIRouter(prefix="/metrics", tags=["metrics"])


@metrics_router.get("/prometheus")
async def get_prometheus_metrics():
    """Expõe métricas em formato Prometheus para scraping pelo Grafana."""
    try:
        collector = get_metrics_collector()
        metrics_bytes = collector.get_metrics()
        return Response(content=metrics_bytes, media_type="text/plain; charset=utf-8")
    except Exception as e:
        logger.error("metrics_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@metrics_router.get("/summary")
async def get_metrics_summary():
    """Retorna resumo de métricas em JSON."""
    try:
        collector = get_metrics_collector()
        summary = collector.get_summary()
        return JSONResponse(content=summary)
    except Exception as e:
        logger.error("metrics_summary_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@metrics_router.get("/health")
async def metrics_health():
    """Health check para Grafana/Prometheus."""
    return {
        "status": "ok",
        "service": "eddie-metrics-exporter",
        "version": "1.0"
    }


# Router para eventos de métricas (webhook do bus)
events_router = APIRouter(prefix="/events", tags=["events"])


@events_router.post("/task_split")
async def on_task_split(num_chunks: int, reason: str = "timeout"):
    """Webhook: registra divisão de tarefa."""
    try:
        collector = get_metrics_collector()
        collector.record_task_split(num_chunks, reason)
        return {"status": "recorded", "num_chunks": num_chunks}
    except Exception as e:
        logger.error("task_split_event_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@events_router.post("/timeout")
async def on_timeout(agent_id: str, timeout_seconds: float, stage: str = "execution"):
    """Webhook: registra timeout."""
    try:
        collector = get_metrics_collector()
        collector.record_timeout(agent_id, timeout_seconds, stage)
        return {"status": "recorded", "agent_id": agent_id}
    except Exception as e:
        logger.error("timeout_event_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@events_router.post("/chunk_executed")
async def on_chunk_executed(agent_id: str, duration_seconds: float, success: bool = True):
    """Webhook: registra execução de chunk."""
    try:
        collector = get_metrics_collector()
        collector.record_chunk_execution(agent_id, duration_seconds, success)
        return {"status": "recorded", "agent_id": agent_id, "duration": duration_seconds}
    except Exception as e:
        logger.error("chunk_executed_event_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@events_router.post("/docker_allocated")
async def on_docker_allocated(container_id: str, cpu_limit: float, memory_limit_mb: int):
    """Webhook: registra alocação de recursos Docker."""
    try:
        collector = get_metrics_collector()
        collector.record_docker_resource_allocation(container_id, cpu_limit, memory_limit_mb)
        return {"status": "recorded", "container_id": container_id}
    except Exception as e:
        logger.error("docker_allocated_event_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@events_router.post("/merge_dedup")
async def on_merge_dedup(num_duplicates: int, num_chunks: int):
    """Webhook: registra deduplicação no merge."""
    try:
        collector = get_metrics_collector()
        collector.record_merge_deduplication(num_duplicates, num_chunks)
        return {"status": "recorded", "duplicates": num_duplicates, "chunks": num_chunks}
    except Exception as e:
        logger.error("merge_dedup_event_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


def setup_metrics_routes(app):
    """Registra rotas de métricas na aplicação FastAPI."""
    app.include_router(metrics_router)
    app.include_router(events_router)
    logger.info("metrics_routes_registered")
