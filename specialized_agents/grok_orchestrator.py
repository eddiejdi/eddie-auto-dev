#!/usr/bin/env python3
"""
Parte 3B: Grok Orchestrator - Integração de Master Controller, Resource Manager e CommBus

Este módulo integra:
1. Master Controller - decide qual agente executra a tarefa
2. Resource Manager - gerencia alocação de recursos  
3. CommBus - roteia mensagens entre componentes

Fluxo:
1. Task chega para Master Controller
2. Controller analisa complexidade via LLM (Ollama)
3. Controller consulta Resource Manager para disponibilidade
4. Controller seleciona melhor agente + modelo
5. CommBus publica decisão de routing
6. Agent executa e retorna resultado via CommBus
7. Controller registra outcome para learning
8. Resource Manager atualiza métricas
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass

from .master_controller import MasterController, get_master_controller, TaskComplexity, LLMModel
from .resource_manager import ResourceManager, ResourceStatus, TaskPriority
from .comm_bus import (
    CommBus,
    Message,
    MessageType,
    MessagePriority,
    get_comm_bus,
    publish_routing_decision,
    publish_execution_outcome,
    publish_resource_status,
)

logger = logging.getLogger(__name__)


@dataclass
class GrokTask:
    """Task to be executed by agents"""
    task_id: str
    description: str
    language_hint: Optional[str] = None
    priority: TaskPriority = TaskPriority.NORMAL
    timeout_ms: int = 30000
    max_retries: int = 2


@dataclass
class GrokExecutionPlan:
    """Execution plan created by Master Controller"""
    task_id: str
    selected_language: str
    selected_model: str
    complexity: str
    confidence: float
    estimated_timeout_ms: int
    reasoning: str
    timestamp: datetime
    # GPU routing: which Ollama endpoint to use
    ollama_endpoint: str = ""  # e.g. http://192.168.15.2:11434
    gpu_device: str = ""       # e.g. "GPU 0 (RTX 2060)" or "GPU 1 (GTX 1050)"


class GrokOrchestrator:
    """
    Central orchestrator combining Master Controller, Resource Manager, and CommBus.
    
    Coordinates task routing, resource allocation, and inter-component communication.
    """
    
    def __init__(
        self,
        agent_languages: List[str] = None,
        use_vault: bool = True,
        controller_id: str = "grok_master_controller",
        resource_mgr_id: str = "grok_resource_manager",
    ):
        """Initialize Grok Orchestrator"""
        if agent_languages is None:
            agent_languages = ["python", "javascript", "typescript", "go", "rust", "java", "csharp", "php"]
        
        # Initialize components
        self.controller = get_master_controller(use_vault=use_vault)
        self.resource_manager = ResourceManager(agent_languages)
        self.comm_bus = get_comm_bus()
        
        # Component IDs
        self.controller_id = controller_id
        self.resource_mgr_id = resource_mgr_id
        self.agent_languages = agent_languages
        
        # GPU endpoint mapping: model → Ollama URL
        import os
        self.gpu_endpoints = {
            LLMModel.CONTROLLER: os.environ.get(
                "OLLAMA_CONTROLLER_HOST", "http://192.168.15.2:11435"
            ),
            LLMModel.EXPERT: os.environ.get(
                "OLLAMA_EXPERT_HOST", "http://192.168.15.2:11434"
            ),
            LLMModel.ULTRA_EXPERT: os.environ.get(
                "OLLAMA_EXPERT_HOST", "http://192.168.15.2:11434"
            ),
        }
        self.gpu_labels = {
            LLMModel.CONTROLLER: "GPU 1 (GTX 1050 2GB)",
            LLMModel.EXPERT: "GPU 0 (RTX 2060 SUPER 8GB)",
            LLMModel.ULTRA_EXPERT: "GPU 0 (RTX 2060 SUPER 8GB)",
        }
        
        # Task tracking
        self.active_tasks: Dict[str, GrokExecutionPlan] = {}
        self.active_decisions: Dict[str, Any] = {}  # task_id -> RoutingDecision
        self.completed_tasks: Dict[str, Dict[str, Any]] = {}
        self.failed_tasks: Dict[str, str] = {}
        
        logger.info(
            f"GrokOrchestrator initialized for {len(agent_languages)} languages\n"
            f"  GPU routing: CONTROLLER → {self.gpu_endpoints[LLMModel.CONTROLLER]}\n"
            f"  GPU routing: EXPERT → {self.gpu_endpoints[LLMModel.EXPERT]}"
        )
    
    async def initialize(self) -> None:
        """Register components on CommBus"""
        await self.comm_bus.register_component(self.controller_id)
        await self.comm_bus.register_component(self.resource_mgr_id)
        
        # Register agents
        for lang in self.agent_languages:
            await self.comm_bus.register_component(f"agent_{lang}")
        
        # Subscribe to messages
        await self.comm_bus.subscribe(self.controller_id, MessageType.OUTCOME)
        await self.comm_bus.subscribe(self.resource_mgr_id, MessageType.STATUS)
        
        logger.info("GrokOrchestrator CommBus initialization complete")
    
    async def process_task(self, task: GrokTask) -> Optional[GrokExecutionPlan]:
        """
        Main entry point: process task through orchestrator.
        
        1. Analyze complexity using Master Controller
        2. Check resource availability with Resource Manager
        3. Make routing decision
        4. Publish decision via CommBus
        5. Wait for execution
        6. Return plan and outcome
        """
        logger.info(f"Processing task: {task.task_id}")
        
        try:
            # Step 1: Master Controller decides routing
            priority_map = {
                TaskPriority.URGENT: "urgent",
                TaskPriority.NORMAL: "normal",
                TaskPriority.BACKGROUND: "background",
            }
            
            routing_decision = await self.controller.route_task(
                task_description=task.description,
                language=task.language_hint,
                priority=priority_map[task.priority],
            )
            
            if not routing_decision:
                logger.warning(f"Control failed to route task {task.task_id}")
                self.failed_tasks[task.task_id] = "Routing failed"
                return None
            
            # Step 2: Check resource availability
            # selected_agent is a string, not an enum
            selected_lang = routing_decision.selected_agent
            can_allocate, reason, alloc_id = self.resource_manager.allocate_task(
                task_id=task.task_id,
                language=selected_lang,
                priority=task.priority,
            )
            
            if not can_allocate:
                logger.warning(f"Resource allocation failed for {selected_lang}: {reason}")
                # Try fallback agents
                for fallback_lang in self.agent_languages:
                    if fallback_lang == selected_lang:
                        continue
                    can_allocate, _, alloc_id = self.resource_manager.allocate_task(
                        task_id=task.task_id,
                        language=fallback_lang,
                        priority=task.priority,
                    )
                    if can_allocate:
                        selected_lang = fallback_lang
                        logger.info(f"Using fallback agent: {fallback_lang}")
                        break
                
                if not can_allocate:
                    self.failed_tasks[task.task_id] = f"No resources available ({reason})"
                    return None
            
            # Step 3: Start task in resource manager
            self.resource_manager.start_task(task.task_id)
            
            # Step 4: Resolve GPU endpoint based on selected model
            model_enum = routing_decision.selected_model
            model_str = model_enum.value if hasattr(model_enum, 'value') else str(model_enum)
            complexity_str = routing_decision.complexity.value if hasattr(routing_decision.complexity, 'value') else str(routing_decision.complexity)
            
            # Get GPU endpoint for this model
            ollama_endpoint = self.gpu_endpoints.get(model_enum, self.gpu_endpoints[LLMModel.EXPERT])
            gpu_device = self.gpu_labels.get(model_enum, "GPU 0 (RTX 2060 SUPER 8GB)")
            
            plan = GrokExecutionPlan(
                task_id=task.task_id,
                selected_language=selected_lang,
                selected_model=model_str,
                complexity=complexity_str,
                confidence=routing_decision.confidence,
                estimated_timeout_ms=routing_decision.estimated_timeout_ms,
                reasoning=routing_decision.reasoning,
                timestamp=datetime.now(),
                ollama_endpoint=ollama_endpoint,
                gpu_device=gpu_device,
            )
            
            self.active_tasks[task.task_id] = plan
            self.active_decisions[task.task_id] = routing_decision
            logger.info(
                f"Task {task.task_id} assigned to {selected_lang}\n"
                f"  Model: {model_str} → {ollama_endpoint} ({gpu_device})"
            )
            
            # Step 5: Publish routing decision
            msg_id = await publish_routing_decision(
                controller_id=self.controller_id,
                agent_language=selected_lang,
                task_id=task.task_id,
                complexity=routing_decision.confidence,
                selected_model=model_str,
                timeout_ms=routing_decision.estimated_timeout_ms,
                priority=MessagePriority.NORMAL if task.priority == TaskPriority.NORMAL else MessagePriority.URGENT,
            )
            
            logger.info(f"Routing decision published: {msg_id}")
            return plan
            
        except Exception as e:
            logger.error(f"Error processing task {task.task_id}: {str(e)}")
            self.failed_tasks[task.task_id] = str(e)
            return None
    
    async def handle_execution_outcome(
        self,
        task_id: str,
        agent_id: str,
        success: bool,
        output: str,
        duration_ms: int,
        quality_score: float = 0.5,
    ) -> None:
        """
        Handle execution outcome from agent.
        
        Updates:
        - Master Controller scores (for learning)
        - Resource Manager task status
        - CommBus message log
        """
        if task_id not in self.active_tasks:
            logger.warning(f"Unknown task result: {task_id}")
            return
        
        plan = self.active_tasks.pop(task_id)
        routing_decision = self.active_decisions.pop(task_id, None)
        
        # Step 1: Complete task in resource manager
        self.resource_manager.complete_task(task_id)
        
        # Step 2: Record outcome in master controller (for learning)
        try:
            if routing_decision is not None:
                self.controller.record_execution_outcome(
                    task_id=task_id,
                    decision=routing_decision,
                    success=success,
                    execution_time_ms=duration_ms,
                    response_quality=quality_score,
                    error_message=None if success else output,
                )
            else:
                logger.debug(f"No routing decision stored for {task_id}, skipping learning")
        except TypeError:
            # If signature doesn't match, just log it
            logger.debug(f"Could not record outcome for {task_id} to controller")
        
        # Step 3: Publish outcome via CommBus
        msg_id = await publish_execution_outcome(
            agent_id=agent_id,
            task_id=task_id,
            success=success,
            output=output,
            duration_ms=duration_ms,
            quality_score=quality_score,
        )
        
        # Step 4: Store in completion log
        if success:
            self.completed_tasks[task_id] = {
                "plan": plan,
                "success": True,
                "duration_ms": duration_ms,
                "quality_score": quality_score,
                "output": output[:500],  # First 500 chars
            }
            logger.info(f"Task completed: {task_id} ({duration_ms}ms, quality={quality_score:.2f})")
        else:
            self.failed_tasks[task_id] = output[:200]
            logger.warning(f"Task failed: {task_id}")
    
    async def update_resource_status(
        self,
        agent_language: str,
        cpu_percent: float,
        memory_mb: float,
        gpu_percent: float = 0.0,
        active_tasks: int = 0,
    ) -> None:
        """Update resource metrics for an agent"""
        from .resource_manager import ResourceMetrics
        
        metrics = ResourceMetrics(
            language=agent_language,
            cpu_percent=cpu_percent,
            memory_mb=memory_mb,
            memory_percent=(memory_mb / (32 * 1024)) * 100,  # Assuming 32GB
            gpu_utilization=gpu_percent,
            active_tasks=active_tasks,
        )
        
        self.resource_manager.update_metrics(agent_language, metrics)
        
        # Publish status update
        await publish_resource_status(
            resource_manager_id=self.resource_mgr_id,
            agent_language=agent_language,
            load=metrics.overall_load,
            memory_mb=memory_mb,
            active_tasks=active_tasks,
        )
    
    def get_orchestrator_status(self) -> Dict[str, Any]:
        """Get current orchestrator status"""
        return {
            "active_tasks": len(self.active_tasks),
            "completed_tasks": len(self.completed_tasks),
            "failed_tasks": len(self.failed_tasks),
            "resource_stats": self.resource_manager.get_statistics(),
            "controller_stats": self.controller.get_statistics(),
            "comm_bus_stats": self.comm_bus.get_stats(),
        }
    
    def get_task_plan(self, task_id: str) -> Optional[GrokExecutionPlan]:
        """Get execution plan for a task"""
        return self.active_tasks.get(task_id)
    
    def get_completed_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get completion data for a task"""
        return self.completed_tasks.get(task_id)
    
    def get_failed_task_reason(self, task_id: str) -> Optional[str]:
        """Get failure reason for a task"""
        return self.failed_tasks.get(task_id)


# Singleton orchestrator
_orchestrator: Optional[GrokOrchestrator] = None


async def get_grok_orchestrator(
    agent_languages: List[str] = None,
    use_vault: bool = True,
) -> GrokOrchestrator:
    """Get or create singleton Grok Orchestrator"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = GrokOrchestrator(
            agent_languages=agent_languages,
            use_vault=use_vault,
        )
        await _orchestrator.initialize()
    return _orchestrator
