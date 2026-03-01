#!/usr/bin/env python3
"""
Resource Manager - Gerenciamento de recursos por agente

Responsabilidades:
1. Monitorar disponibilidade de recursos (CPU, GPU, memória)
2. Implementar fila de prioridade (urgent > normal > background)
3. Throttling inteligente (recusar tarefas se sobrecarregado)
4. Algoritmo LRU + Scoring para seleção de agente
5. Timeouts dinâmicos baseado em carga atual

Com 32GB de RAM, suporta:
- Múltiplas execuções simultâneas por agente
- Modelos LLM grandes em paralelo
- Fair scheduling entre agentes
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple, Literal
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque
import sys
import os

# Vault integration
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# DATA CLASSES & ENUMS
# ============================================================================

class TaskPriority(Enum):
    """Task priority levels"""
    BACKGROUND = "background"  # Low priority, can be deferred
    NORMAL = "normal"          # Standard priority
    URGENT = "urgent"          # High priority, execute ASAP


class ResourceStatus(Enum):
    """Resource availability status"""
    HEALTHY = "healthy"        # Plenty of resources
    WARNING = "warning"        # Some constraints
    CRITICAL = "critical"      # Severely limited
    EXHAUSTED = "exhausted"    # No resources available


@dataclass
class ResourceMetrics:
    """Current resource usage for an agent"""
    language: str
    cpu_percent: float = 0.0       # 0-100%
    memory_mb: float = 0.0          # MB used
    memory_percent: float = 0.0     # 0-100%
    gpu_memory_mb: float = 0.0     # GPU VRAM used
    gpu_memory_percent: float = 0.0  # 0-100%
    gpu_utilization: float = 0.0    # 0-100%
    active_tasks: int = 0           # Current executing tasks
    queued_tasks: int = 0           # Waiting in queue
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def overall_load(self) -> float:
        """Overall load: 0.0-1.0"""
        # Weight CPU (0.2), Memory (0.3), GPU (0.3), Task count (0.2)
        task_load = min(self.active_tasks / 5.0, 1.0)  # Normalize to 5 concurrent
        
        return (
            (self.cpu_percent / 100.0) * 0.2 +
            (self.memory_percent / 100.0) * 0.3 +
            (self.gpu_utilization / 100.0) * 0.3 +
            task_load * 0.2
        )
    
    @property
    def status(self) -> ResourceStatus:
        """Determine resource status"""
        load = self.overall_load
        
        if load < 0.3:
            return ResourceStatus.HEALTHY
        elif load < 0.7:
            return ResourceStatus.WARNING
        elif load < 0.95:
            return ResourceStatus.CRITICAL
        else:
            return ResourceStatus.EXHAUSTED


@dataclass
class TaskAllocation:
    """Resource allocation for a task"""
    task_id: str
    language: str
    priority: TaskPriority
    allocated_cpu_percent: float
    allocated_memory_mb: float
    allocated_gpu_memory_mb: float
    estimated_duration_ms: int
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    @property
    def is_active(self) -> bool:
        """Task is currently executing"""
        return self.started_at is not None and self.completed_at is None
    
    @property
    def is_queued(self) -> bool:
        """Task is waiting to execute"""
        return self.started_at is None
    
    @property
    def duration_ms(self) -> Optional[float]:
        """Actual execution duration"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return None


# ============================================================================
# RESOURCE MANAGER CLASS
# ============================================================================

class ResourceManager:
    """
    Central resource manager for all agents.
    
    Tracks CPU, GPU, memory per agent. Implements fair scheduling with
    priority queue, throttling, and dynamic timeout adjustment.
    """
    
    # System-wide constraints (32GB RAM system)
    SYSTEM_MEMORY_MB = 32 * 1024          # 32GB
    SYSTEM_CPU_CORES = 8                  # Typical
    SYSTEM_GPU_VRAM_MB = 8192 + 2048      # RTX 2060 (8GB) + GTX 1050 (2GB)
    
    # Per-agent limits
    MAX_MEMORY_PERCENT_PER_AGENT = 50.0   # Max 50% of system RAM per agent
    MAX_GPU_UTILIZATION = 95.0             # Max 95% GPU utilization
    MEMORY_HEADROOM_MB = 1024              # Keep 1GB free system RAM
    
    # Task queue settings
    MAX_QUEUED_TASKS_PER_AGENT = 50       # Max tasks in queue
    
    def __init__(self, agent_languages: List[str]):
        """
        Initialize Resource Manager.
        
        Args:
            agent_languages: List of supported agent languages
        """
        self.agent_languages = agent_languages
        
        # Resource tracking per agent
        self.agent_metrics: Dict[str, ResourceMetrics] = {
            lang: ResourceMetrics(language=lang) for lang in agent_languages
        }
        
        # Task allocations (global and per-agent)
        self.all_allocations: List[TaskAllocation] = []
        self.agent_allocations: Dict[str, List[TaskAllocation]] = {
            lang: [] for lang in agent_languages
        }
        
        # Task priority queue
        self.task_queue: Dict[TaskPriority, deque] = {
            priority: deque() for priority in TaskPriority
        }
        
        # Last execution time per agent (for LRU)
        self.agent_last_execution: Dict[str, datetime] = {
            lang: datetime.now() for lang in agent_languages
        }
        
        logger.info(
            f"ResourceManager initialized for {len(agent_languages)} agents\n"
            f"  System RAM: {self.SYSTEM_MEMORY_MB}MB\n"
            f"  System GPU VRAM: {self.SYSTEM_GPU_VRAM_MB}MB"
        )
    
    # ========================================================================
    # RESOURCE MONITORING
    # ========================================================================
    
    def update_metrics(self, language: str, metrics: ResourceMetrics) -> None:
        """Update resource metrics for an agent"""
        if language not in self.agent_languages:
            logger.warning(f"Unknown language: {language}")
            return
        
        self.agent_metrics[language] = metrics
        logger.debug(f"Updated metrics for {language}: load={metrics.overall_load:.2f}")
    
    def get_metrics(self, language: str) -> Optional[ResourceMetrics]:
        """Get current metrics for an agent"""
        return self.agent_metrics.get(language)
    
    def get_all_metrics(self) -> Dict[str, ResourceMetrics]:
        """Get metrics for all agents"""
        return dict(self.agent_metrics)
    
    # ========================================================================
    # RESOURCE AVAILABILITY CHECKING
    # ========================================================================
    
    def can_allocate(
        self,
        language: str,
        estimated_duration_ms: int,
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> Tuple[bool, str]:
        """
        Check if resources are available to execute a task.
        
        Returns:
            (can_allocate: bool, reason: str)
        """
        if language not in self.agent_languages:
            return False, f"Unknown language: {language}"
        
        metrics = self.agent_metrics[language]
        
        # Check 1: Agent status
        if metrics.status == ResourceStatus.EXHAUSTED:
            return False, f"Agent {language} is exhausted (load: {metrics.overall_load:.2f})"
        
        # Check 2: Queue size
        queue_size = len(self.agent_allocations[language])
        if queue_size >= self.MAX_QUEUED_TASKS_PER_AGENT:
            return False, f"Agent {language} queue full ({queue_size} tasks)"
        
        # Check 3: For CRITICAL status, only allow URGENT
        if metrics.status == ResourceStatus.CRITICAL and priority != TaskPriority.URGENT:
            return False, f"Agent {language} CRITICAL - only URGENT allowed"
        
        # Check 4: System memory headroom
        total_memory_used = sum(m.memory_mb for m in self.agent_metrics.values())
        if total_memory_used + self.MEMORY_HEADROOM_MB >= self.SYSTEM_MEMORY_MB:
            return False, "System RAM exhausted"
        
        return True, "OK"
    
    def get_agent_status(self, language: str) -> ResourceStatus:
        """Get resource status for an agent"""
        if language not in self.agent_languages:
            return ResourceStatus.EXHAUSTED
        return self.agent_metrics[language].status
    
    # ========================================================================
    # RESOURCE ALLOCATION
    # ========================================================================
    
    def allocate_task(
        self,
        task_id: str,
        language: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        estimated_duration_ms: int = 30000,
        cpu_percent: float = 10.0,
        memory_mb: float = 256.0,
        gpu_memory_mb: float = 0.0,
    ) -> Tuple[bool, str, Optional[TaskAllocation]]:
        """
        Allocate resources for a task.
        
        Returns:
            (success: bool, reason: str, allocation: TaskAllocation or None)
        """
        # Check availability
        can_alloc, reason = self.can_allocate(language, estimated_duration_ms, priority)
        if not can_alloc:
            return False, reason, None
        
        # Create allocation
        allocation = TaskAllocation(
            task_id=task_id,
            language=language,
            priority=priority,
            allocated_cpu_percent=cpu_percent,
            allocated_memory_mb=memory_mb,
            allocated_gpu_memory_mb=gpu_memory_mb,
            estimated_duration_ms=estimated_duration_ms,
        )
        
        # Store allocation
        self.all_allocations.append(allocation)
        self.agent_allocations[language].append(allocation)
        
        # Add to appropriate priority queue
        self.task_queue[priority].append(allocation)
        
        logger.info(
            f"✓ Allocated task {task_id} to {language} "
            f"({priority.value}, mem: {memory_mb}MB)"
        )
        
        return True, "OK", allocation
    
    def start_task(self, task_id: str) -> bool:
        """Mark a task as started"""
        for allocation in self.all_allocations:
            if allocation.task_id == task_id and allocation.started_at is None:
                allocation.started_at = datetime.now()
                return True
        return False
    
    def complete_task(self, task_id: str) -> bool:
        """Mark a task as completed and free resources"""
        for allocation in self.all_allocations:
            if allocation.task_id == task_id and allocation.started_at and not allocation.completed_at:
                allocation.completed_at = datetime.now()
                
                # Remove from queue if still queued (shouldn't happen)
                for priority in self.task_queue.values():
                    try:
                        priority.remove(allocation)
                    except ValueError:
                        pass
                
                logger.info(
                    f"✓ Completed task {task_id} in {allocation.duration_ms:.0f}ms"
                )
                return True
        return False
    
    def deallocate_task(self, task_id: str) -> bool:
        """Remove task allocation (if never started)"""
        allocation_to_remove = None
        for allocation in self.all_allocations:
            if allocation.task_id == task_id:
                allocation_to_remove = allocation
                break
        
        if allocation_to_remove:
            self.all_allocations.remove(allocation_to_remove)
            self.agent_allocations[allocation_to_remove.language].remove(allocation_to_remove)
            return True
        return False
    
    # ========================================================================
    # TASK SCHEDULING & PRIORITY QUEUE
    # ========================================================================
    
    def get_next_task(self) -> Optional[TaskAllocation]:
        """
        Get next task from priority queue (URGENT > NORMAL > BACKGROUND).
        
        Tasks are ordered by insertion time (FIFO within priority).
        """
        for priority in [TaskPriority.URGENT, TaskPriority.NORMAL, TaskPriority.BACKGROUND]:
            if self.task_queue[priority]:
                return self.task_queue[priority].popleft()
        return None
    
    def get_queued_tasks(self, language: Optional[str] = None) -> List[TaskAllocation]:
        """Get queued (not yet started) tasks"""
        if language:
            return [t for t in self.agent_allocations[language] if t.is_queued]
        else:
            return [t for t in self.all_allocations if t.is_queued]
    
    def get_active_tasks(self, language: Optional[str] = None) -> List[TaskAllocation]:
        """Get active (currently executing) tasks"""
        if language:
            return [t for t in self.agent_allocations[language] if t.is_active]
        else:
            return [t for t in self.all_allocations if t.is_active]
    
    # ========================================================================
    # AGENT SELECTION (LRU + SCORING)
    # ========================================================================
    
    def select_best_agent(
        self,
        available_languages: Optional[List[str]] = None,
    ) -> Tuple[str, float]:
        """
        Select best agent using LRU + load scoring.
        
        Algorithm:
        1. Filter agents by language availability
        2. Score by: load (0.5) + execution_recency (0.3) + queue_size (0.2)
        3. Lower score = better
        
        Returns:
            (language: str, score: float)
        """
        if available_languages is None:
            available_languages = self.agent_languages
        
        candidates = [lang for lang in available_languages if lang in self.agent_languages]
        if not candidates:
            raise ValueError(f"No candidates from {available_languages}")
        
        best_lang = None
        best_score = float('inf')
        
        for lang in candidates:
            metrics = self.agent_metrics[lang]
            queue_size = len(self.get_queued_tasks(lang))
            
            # Minutes since last execution
            last_exec = self.agent_last_execution[lang]
            recency_minutes = (datetime.now() - last_exec).total_seconds() / 60.0
            # LRU: agents not used recently have low score (good)
            # recency_score: 1.0 (recently used) to 0.0 (not used in 10+ minutes)
            recency_score = max(1.0 - min(recency_minutes / 10.0, 1.0), 0.0)
            
            # Combined score (lower is better)
            # IMPORTANT: High load = high score (bad), Low load = low score (good)
            score = (
                metrics.overall_load * 0.5 +                # Load: favor LOW load (0-0.5)
                recency_score * 0.3 +                        # Recency: favor LEAST recently used
                min(queue_size / 10.0, 1.0) * 0.2          # Queue: favor empty queues
            )
            
            if score < best_score:
                best_score = score
                best_lang = lang
        
        return best_lang, best_score
    
    def update_last_execution(self, language: str) -> None:
        """Update last execution timestamp for LRU"""
        self.agent_last_execution[language] = datetime.now()
    
    # ========================================================================
    # DYNAMIC TIMEOUT ADJUSTMENT
    # ========================================================================
    
    def adjust_timeout(
        self,
        base_timeout_ms: int,
        language: str,
    ) -> int:
        """
        Adjust timeout based on current agent load.
        
        Logic:
        - Healthy: base timeout
        - Warning: +25% timeout
        - Critical: +50% timeout
        - Exhausted: +75% timeout (but shouldn't allocate)
        """
        metrics = self.agent_metrics[language]
        
        multipliers = {
            ResourceStatus.HEALTHY: 1.0,
            ResourceStatus.WARNING: 1.25,
            ResourceStatus.CRITICAL: 1.5,
            ResourceStatus.EXHAUSTED: 1.75,
        }
        
        multiplier = multipliers.get(metrics.status, 1.0)
        adjusted = int(base_timeout_ms * multiplier)
        
        return adjusted
    
    # ========================================================================
    # STATISTICS & REPORTING
    # ========================================================================
    
    def get_statistics(self) -> Dict[str, any]:
        """Get overall resource statistics"""
        active_count = len(self.get_active_tasks())
        queued_count = len(self.get_queued_tasks())
        completed_count = len([t for t in self.all_allocations if t.completed_at])
        
        total_memory_used = sum(m.memory_mb for m in self.agent_metrics.values())
        total_memory_percent = (total_memory_used / self.SYSTEM_MEMORY_MB) * 100.0
        
        agent_stats = {
            lang: {
                "status": self.agent_metrics[lang].status.value,
                "load": self.agent_metrics[lang].overall_load,
                "memory_mb": self.agent_metrics[lang].memory_mb,
                "memory_percent": self.agent_metrics[lang].memory_percent,
                "active_tasks": len(self.get_active_tasks(lang)),
                "queued_tasks": len(self.get_queued_tasks(lang)),
            }
            for lang in self.agent_languages
        }
        
        return {
            "total_allocations": len(self.all_allocations),
            "active_tasks": active_count,
            "queued_tasks": queued_count,
            "completed_tasks": completed_count,
            "system_memory_mb": total_memory_used,
            "system_memory_percent": total_memory_percent,
            "agent_stats": agent_stats,
        }
    
    def get_agent_summary(self, language: str) -> Dict[str, any]:
        """Get summary for a specific agent"""
        if language not in self.agent_languages:
            return {}
        
        metrics = self.agent_metrics[language]
        active = self.get_active_tasks(language)
        queued = self.get_queued_tasks(language)
        
        return {
            "language": language,
            "status": metrics.status.value,
            "load": metrics.overall_load,
            "memory_mb": metrics.memory_mb,
            "memory_percent": metrics.memory_percent,
            "gpu_memory_mb": metrics.gpu_memory_mb,
            "gpu_utilization": metrics.gpu_utilization,
            "active_tasks": len(active),
            "queued_tasks": len(queued),
            "last_execution": self.agent_last_execution[language].isoformat(),
        }
    
    def cleanup_completed_tasks(self, age_minutes: int = 60) -> int:
        """Remove completed tasks older than N minutes"""
        cutoff_time = datetime.now() - timedelta(minutes=age_minutes)
        
        to_remove = [
            t for t in self.all_allocations
            if t.completed_at and t.completed_at < cutoff_time
        ]
        
        for task in to_remove:
            self.all_allocations.remove(task)
            self.agent_allocations[task.language].remove(task)
        
        return len(to_remove)


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_resource_manager_instance: Optional[ResourceManager] = None


def get_resource_manager(
    agent_languages: Optional[List[str]] = None,
) -> ResourceManager:
    """Get or create singleton ResourceManager"""
    global _resource_manager_instance
    
    if agent_languages is None:
        agent_languages = [
            "python", "javascript", "typescript", "go", 
            "rust", "java", "csharp", "php"
        ]
    
    if _resource_manager_instance is None:
        _resource_manager_instance = ResourceManager(agent_languages)
    
    return _resource_manager_instance


# ============================================================================
# CLI DEMO
# ============================================================================

if __name__ == "__main__":
    import json
    
    # Initialize
    rm = ResourceManager([
        "python", "javascript", "typescript", "go",
        "rust", "java", "csharp", "php"
    ])
    
    # Simulate some metrics
    print("=== RESOURCE MANAGER DEMO ===\n")
    
    # Simulate Python agent under load
    python_metrics = ResourceMetrics(
        language="python",
        cpu_percent=45.0,
        memory_mb=2048.0,
        memory_percent=25.0,
        gpu_memory_mb=3000.0,
        gpu_memory_percent=36.6,
        gpu_utilization=42.0,
        active_tasks=3,
        queued_tasks=5,
    )
    rm.update_metrics("python", python_metrics)
    
    # Simulate Go agent lightly loaded
    go_metrics = ResourceMetrics(
        language="go",
        cpu_percent=10.0,
        memory_mb=256.0,
        memory_percent=3.0,
        gpu_memory_mb=0.0,
        gpu_memory_percent=0.0,
        gpu_utilization=0.0,
        active_tasks=0,
        queued_tasks=0,
    )
    rm.update_metrics("go", go_metrics)
    
    # Test allocation
    print("1. Allocate Python task (normal priority):")
    success, reason, alloc = rm.allocate_task(
        "task_001", "python",
        priority=TaskPriority.NORMAL,
        estimated_duration_ms=30000,
        memory_mb=512.0,
    )
    print(f"   Result: {success} - {reason}\n")
    
    # Test agent selection
    print("2. Select best agent:")
    best_lang, score = rm.select_best_agent()
    print(f"   Best: {best_lang} (score: {score:.2f})\n")
    
    # Test status
    print("3. Resource Status:")
    print(f"   Python: {rm.get_agent_status('python').value}")
    print(f"   Go: {rm.get_agent_status('go').value}\n")
    
    # Test allocation with high priority
    print("4. Allocate Urgent task to Go:")
    success, reason, alloc = rm.allocate_task(
        "task_002", "go",
        priority=TaskPriority.URGENT,
        estimated_duration_ms=5000,
        memory_mb=128.0,
    )
    print(f"   Result: {success} - {reason}\n")
    
    # Statistics
    print("5. Statistics:")
    stats = rm.get_statistics()
    print(json.dumps(stats, indent=2, default=str))
