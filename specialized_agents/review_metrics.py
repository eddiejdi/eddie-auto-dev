"""
Prometheus Metrics Exporter para Review Quality Gate System

Expõe métricas para monitoramento em Grafana:
- Fila de review (total, pending, approved, rejected, merged)
- ReviewAgent status (total_reviews, approvals, rejections, avg_score)
- Taxa de aprovação
- Tempo de processamento
"""
import os
import logging
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    CollectorRegistry,
    generate_latest,
)
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Registry global
_registry = CollectorRegistry()

# ================== Métricas da Fila ==================
review_queue_total = Gauge(
    "review_queue_total",
    "Total de items na fila de review",
    registry=_registry
)

review_queue_pending = Gauge(
    "review_queue_pending",
    "Items pendentes na fila",
    registry=_registry
)

review_queue_approved = Gauge(
    "review_queue_approved",
    "Items aprovados",
    registry=_registry
)

review_queue_rejected = Gauge(
    "review_queue_rejected",
    "Items rejeitados",
    registry=_registry
)

review_queue_merged = Gauge(
    "review_queue_merged",
    "Items merged com sucesso",
    registry=_registry
)

# ================== Métricas do ReviewAgent ==================
review_agent_total_reviews = Counter(
    "review_agent_total_reviews",
    "Total de reviews feitos pelo ReviewAgent",
    registry=_registry
)

review_agent_approvals = Counter(
    "review_agent_approvals",
    "Total de approvals pelo ReviewAgent",
    registry=_registry
)

review_agent_rejections = Counter(
    "review_agent_rejections",
    "Total de rejections pelo ReviewAgent",
    registry=_registry
)

review_agent_avg_score = Gauge(
    "review_agent_avg_score",
    "Score médio dos reviews (0-100)",
    registry=_registry
)

# ================== Métricas de Taxa ==================
review_approval_rate = Gauge(
    "review_approval_rate",
    "Taxa de aprovação (%)",
    registry=_registry
)

review_rejection_rate = Gauge(
    "review_rejection_rate",
    "Taxa de rejeição (%)",
    registry=_registry
)

# ================== Métricas de Performance ==================
review_processing_time = Histogram(
    "review_processing_time_seconds",
    "Tempo de processamento de um review (segundos)",
    buckets=(5, 10, 30, 60, 120, 300),
    registry=_registry
)

review_cycle_duration = Histogram(
    "review_cycle_duration_seconds",
    "Duração de um ciclo completo de review",
    buckets=(10, 30, 60, 120, 300),
    registry=_registry
)

# ================== Métricas de Saúde ==================
review_service_cycles = Counter(
    "review_service_cycles_total",
    "Total de ciclos executados pelo review service",
    registry=_registry
)

review_service_errors = Counter(
    "review_service_errors_total",
    "Total de erros no review service",
    registry=_registry
)

review_service_up = Gauge(
    "review_service_up",
    "Review service up/down (1=up, 0=down)",
    registry=_registry
)

# ================== Métricas de Agentes ==================
review_agent_training_feedback = Counter(
    "review_agent_training_feedback_total",
    "Total de feedback de treinamento registrado",
    labelnames=["agent_name", "feedback_type"],
    registry=_registry
)

review_agent_retrospective_score = Gauge(
    "review_agent_retrospective_score",
    "Score da retrospectiva por agente",
    labelnames=["agent_name"],
    registry=_registry
)


def update_metrics_from_queue(queue_stats: Dict[str, Any]) -> None:
    """Atualiza métricas a partir das estatísticas da fila"""
    try:
        review_queue_total.set(queue_stats.get("total", 0))
        review_queue_pending.set(queue_stats.get("pending", 0))
        review_queue_approved.set(queue_stats.get("approved", 0))
        review_queue_rejected.set(queue_stats.get("rejected", 0))
        review_queue_merged.set(queue_stats.get("merged", 0))
        
        # Calcular taxas
        total = queue_stats.get("total", 0)
        if total > 0:
            approval_rate = (queue_stats.get("approved", 0) / total) * 100
            rejection_rate = (queue_stats.get("rejected", 0) / total) * 100
        else:
            approval_rate = 0
            rejection_rate = 0
        
        review_approval_rate.set(approval_rate)
        review_rejection_rate.set(rejection_rate)
    except Exception as e:
        logger.error(f"Erro ao atualizar métricas da fila: {e}")


def update_metrics_from_agent(agent_stats: Dict[str, Any]) -> None:
    """Atualiza métricas a partir das estatísticas do ReviewAgent"""
    try:
        total = agent_stats.get("total_reviews", 0)
        approvals = agent_stats.get("approvals", 0)
        rejections = agent_stats.get("rejections", 0)
        avg_score = agent_stats.get("avg_score", 0)
        
        review_agent_total_reviews._value.get_value = lambda: total
        review_agent_approvals._value.get_value = lambda: approvals
        review_agent_rejections._value.get_value = lambda: rejections
        review_agent_avg_score.set(avg_score)
    except Exception as e:
        logger.error(f"Erro ao atualizar métricas do agent: {e}")


def record_review_time(duration_seconds: float) -> None:
    """Registra tempo de processamento de um review"""
    try:
        review_processing_time.observe(duration_seconds)
    except Exception as e:
        logger.error(f"Erro ao registrar tempo de review: {e}")


def record_cycle_time(duration_seconds: float) -> None:
    """Registra tempo de um ciclo completo"""
    try:
        review_cycle_duration.observe(duration_seconds)
    except Exception as e:
        logger.error(f"Erro ao registrar tempo de ciclo: {e}")


def record_cycle() -> None:
    """Incrementa contador de ciclos"""
    try:
        review_service_cycles.inc()
    except Exception as e:
        logger.error(f"Erro ao registrar ciclo: {e}")


def record_error() -> None:
    """Incrementa contador de erros"""
    try:
        review_service_errors.inc()
    except Exception as e:
        logger.error(f"Erro ao registrar erro: {e}")


def set_service_health(is_up: bool) -> None:
    """Define status de saúde do serviço"""
    try:
        review_service_up.set(1 if is_up else 0)
    except Exception as e:
        logger.error(f"Erro ao definir saúde do serviço: {e}")


def record_training_feedback(agent_name: str, feedback_type: str) -> None:
    """Registra feedback de treinamento para um agente"""
    try:
        review_agent_training_feedback.labels(
            agent_name=agent_name,
            feedback_type=feedback_type
        ).inc()
    except Exception as e:
        logger.error(f"Erro ao registrar feedback: {e}")


def record_retrospective_score(agent_name: str, score: float) -> None:
    """Registra score da retrospectiva para um agente"""
    try:
        review_agent_retrospective_score.labels(agent_name=agent_name).set(score)
    except Exception as e:
        logger.error(f"Erro ao registrar score retrospectiva: {e}")


def get_metrics() -> bytes:
    """Retorna métricas em formato Prometheus"""
    try:
        return generate_latest(_registry)
    except Exception as e:
        logger.error(f"Erro ao gerar métricas: {e}")
        return b""


def get_registry():
    """Retorna registry do Prometheus"""
    return _registry
