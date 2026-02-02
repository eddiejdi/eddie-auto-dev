"""
Exportador de métricas Prometheus para o sistema de fallback distribuído.

Coleta métricas do agent communication bus, status dos agentes e recursos Docker.
"""

import asyncio
import time
from typing import Dict, Any, TYPE_CHECKING
from collections import defaultdict, deque
from datetime import datetime, timedelta
import logging

from prometheus_client import Counter, Gauge, Histogram, Summary, CollectorRegistry, generate_latest

logger = logging.getLogger(__name__)

# Lazy imports para evitar circular dependencies
if TYPE_CHECKING:
    from specialized_agents.agent_manager import AgentManager


class MetricsCollector:
    """Coleta e expõe métricas do sistema de fallback distribuído."""

    def __init__(self, registry: CollectorRegistry = None):
        """Inicializa o coletor de métricas."""
        self.registry = registry or CollectorRegistry()
        self.agent_manager = None
        
        # Métricas de distribuição de tarefas
        self.task_split_total = Counter(
            "task_split_total",
            "Total de vezes que tarefas foram divididas (fallback acionado)",
            registry=self.registry
        )
        
        self.task_split_chunks = Counter(
            "task_split_chunks_total",
            "Total de chunks criados em distribuição",
            registry=self.registry
        )
        
        # Métricas de timeout
        self.timeout_events = Counter(
            "timeout_events_total",
            "Total de eventos de timeout",
            ["agent_id", "reason"],
            registry=self.registry
        )
        
        self.fallback_depth_exceeded = Counter(
            "fallback_depth_exceeded_total",
            "Total de vezes que max_fallback_depth foi excedido",
            registry=self.registry
        )
        
        # Métricas de execução
        self.task_execution_time = Histogram(
            "task_execution_seconds",
            "Tempo de execução de tarefas",
            ["stage"],  # original, chunk, retry
            buckets=(1, 5, 10, 30, 60, 120, 300),
            registry=self.registry
        )
        
        self.chunk_execution_time = Histogram(
            "chunk_execution_seconds",
            "Tempo de execução individual de chunks",
            ["agent_id"],
            buckets=(1, 5, 10, 30, 60),
            registry=self.registry
        )
        
        # Métricas de sucesso/falha
        self.task_success = Counter(
            "task_success_total",
            "Total de tarefas executadas com sucesso",
            ["stage"],
            registry=self.registry
        )
        
        self.task_failure = Counter(
            "task_failure_total",
            "Total de tarefas que falharam",
            ["stage", "reason"],
            registry=self.registry
        )
        
        # Métricas de carga de agentes
        self.agent_active_tasks = Gauge(
            "agent_active_tasks",
            "Número de tarefas ativas por agente",
            ["agent_id"],
            registry=self.registry
        )
        
        self.agent_total_executed = Counter(
            "agent_tasks_executed_total",
            "Total de tarefas executadas por agente",
            ["agent_id"],
            registry=self.registry
        )
        
        # Métricas de recursos Docker
        self.docker_container_cpu = Gauge(
            "docker_container_cpu_limit",
            "Limite de CPU por container em milicores",
            ["container_id"],
            registry=self.registry
        )
        
        self.docker_container_memory = Gauge(
            "docker_container_memory_limit_bytes",
            "Limite de memória por container em bytes",
            ["container_id"],
            registry=self.registry
        )
        
        self.docker_elastic_adjustment = Counter(
            "docker_elastic_adjustment_total",
            "Total de ajustes de recursos elásticos",
            ["resource_type"],  # cpu, memory, memory_swap
            registry=self.registry
        )
        
        # Métricas de qualidade do merge
        self.merge_deduplication = Counter(
            "merge_deduplication_total",
            "Total de duplicatas removidas no merge",
            registry=self.registry
        )
        
        self.merge_chunks_combined = Counter(
            "merge_chunks_combined_total",
            "Total de chunks combinados com sucesso",
            registry=self.registry
        )
        
        # Histórico para análise
        self.task_history = deque(maxlen=1000)
        self.timeout_history = deque(maxlen=500)
        self.agent_load_history = defaultdict(lambda: deque(maxlen=288))  # 24h a 5min
        
        # Estado de coleta
        self._collection_started = False
        self._collection_task = None

    async def start_collection(self, agent_manager, interval: int = 10):
        """Inicia a coleta periódica de métricas.
        
        Args:
            agent_manager: Gerenciador de agentes para coleta de status
            interval: Intervalo de coleta em segundos
        """
        self.agent_manager = agent_manager
        self._collection_started = True
        self._collection_task = asyncio.create_task(
            self._collection_loop(interval)
        )
        logger.info(f"metrics_collection_started: interval={interval}")

    async def stop_collection(self):
        """Para a coleta periódica de métricas."""
        self._collection_started = False
        if self._collection_task:
            self._collection_task.cancel()
            try:
                await self._collection_task
            except asyncio.CancelledError:
                pass
        logger.info("metrics_collection_stopped")

    async def _collection_loop(self, interval: int):
        """Loop principal de coleta de métricas."""
        while self._collection_started:
            try:
                await asyncio.sleep(interval)
                await self._collect_agent_metrics()
            except Exception as e:
                logger.error(f"metrics_collection_error: {str(e)}", exc_info=True)

    async def _collect_agent_metrics(self):
        """Coleta métricas dos agentes."""
        if not self.agent_manager:
            return

        agents = self.agent_manager.agents
        for agent_id, agent in agents.items():
            try:
                status = await agent.get_status()
                self.agent_active_tasks.labels(agent_id=agent_id).set(
                    status.get("active_tasks", 0)
                )
                
                # Histórico
                self.agent_load_history[agent_id].append({
                    "timestamp": datetime.now(),
                    "active_tasks": status.get("active_tasks", 0)
                })
            except Exception as e:
                logger.warning(f"agent_metrics_error: agent_id={agent_id}, error={str(e)}")

    def record_task_split(self, num_chunks: int, reason: str = "timeout"):
        """Registra um evento de divisão de tarefa.
        
        Args:
            num_chunks: Número de chunks criados
            reason: Motivo do split (timeout, memory, load_balance)
        """
        self.task_split_total.inc()
        self.task_split_chunks.inc(num_chunks)
        
        self.task_history.append({
            "timestamp": datetime.now(),
            "event": "task_split",
            "num_chunks": num_chunks,
            "reason": reason
        })
        
        logger.info(f"task_split_recorded: chunks={num_chunks}, reason={reason}")

    def record_timeout(self, agent_id: str, timeout_seconds: float, stage: str = "execution"):
        """Registra um evento de timeout.
        
        Args:
            agent_id: ID do agente que sofreu timeout
            timeout_seconds: Tempo de timeout em segundos
            stage: Estágio onde ocorreu (execution, chunk)
        """
        self.timeout_events.labels(agent_id=agent_id, reason=stage).inc()
        
        self.timeout_history.append({
            "timestamp": datetime.now(),
            "agent_id": agent_id,
            "timeout_seconds": timeout_seconds,
            "stage": stage
        })
        
        logger.info(f"timeout_recorded: agent_id={agent_id}, timeout_seconds={timeout_seconds}, stage={stage}")

    def record_fallback_depth_exceeded(self):
        """Registra tentativa de exceder max_fallback_depth."""
        self.fallback_depth_exceeded.inc()
        logger.warning("fallback_depth_exceeded")

    def record_task_execution(self, stage: str, duration_seconds: float, success: bool, error_reason: str = None):
        """Registra execução de tarefa.
        
        Args:
            stage: Estágio (original, chunk, retry)
            duration_seconds: Duração em segundos
            success: Se foi bem-sucedido
            error_reason: Motivo do erro (se houver)
        """
        self.task_execution_time.labels(stage=stage).observe(duration_seconds)
        
        if success:
            self.task_success.labels(stage=stage).inc()
        else:
            self.task_failure.labels(
                stage=stage,
                reason=error_reason or "unknown"
            ).inc()

    def record_chunk_execution(self, agent_id: str, duration_seconds: float, success: bool = True):
        """Registra execução de um chunk individual.
        
        Args:
            agent_id: ID do agente que executou
            duration_seconds: Duração em segundos
            success: Se foi bem-sucedido
        """
        self.chunk_execution_time.labels(agent_id=agent_id).observe(duration_seconds)
        
        if success:
            self.agent_total_executed.labels(agent_id=agent_id).inc()

    def record_agent_executed(self, agent_id: str):
        """Registra que um agente executou uma tarefa."""
        self.agent_total_executed.labels(agent_id=agent_id).inc()

    def record_docker_resource_allocation(self, container_id: str, cpu_limit: float, memory_limit_mb: int):
        """Registra alocação de recursos Docker.
        
        Args:
            container_id: ID do container
            cpu_limit: Limite de CPU em cores
            memory_limit_mb: Limite de memória em MB
        """
        self.docker_container_cpu.labels(container_id=container_id).set(int(cpu_limit * 1000))
        self.docker_container_memory.labels(container_id=container_id).set(memory_limit_mb * 1024 * 1024)
        
        self.docker_elastic_adjustment.labels(resource_type="cpu").inc()
        self.docker_elastic_adjustment.labels(resource_type="memory").inc()

    def record_merge_deduplication(self, num_duplicates: int, num_chunks: int):
        """Registra deduplicação no merge.
        
        Args:
            num_duplicates: Número de duplicatas removidas
            num_chunks: Número total de chunks após merge
        """
        self.merge_deduplication.inc(num_duplicates)
        self.merge_chunks_combined.inc(num_chunks)

    def get_metrics(self) -> bytes:
        """Retorna métricas em formato Prometheus."""
        return generate_latest(self.registry)

    def get_summary(self) -> Dict[str, Any]:
        """Retorna resumo das métricas coletadas."""
        recent_splits = sum(1 for t in self.task_history if t["event"] == "task_split")
        recent_timeouts = len(self.timeout_history)
        
        avg_active_tasks = 0
        if self.agent_load_history:
            total_active = sum(
                sum(entry["active_tasks"] for entry in history)
                for history in self.agent_load_history.values()
            )
            total_entries = sum(len(history) for history in self.agent_load_history.values())
            avg_active_tasks = total_active / total_entries if total_entries > 0 else 0

        return {
            "period_start": (datetime.now() - timedelta(hours=1)).isoformat(),
            "period_end": datetime.now().isoformat(),
            "task_splits_last_hour": recent_splits,
            "timeouts_last_hour": recent_timeouts,
            "avg_active_tasks": round(avg_active_tasks, 2),
            "total_chunks": int(self.task_split_chunks._value.get()),
            "agents_monitored": len(self.agent_load_history)
        }


# Instância global singleton
_metrics_collector: MetricsCollector = None


def get_metrics_collector() -> MetricsCollector:
    """Obtém a instância global do coletor de métricas."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def init_metrics_collector() -> MetricsCollector:
    """Inicializa o coletor de métricas."""
    global _metrics_collector
    _metrics_collector = MetricsCollector()
    return _metrics_collector
