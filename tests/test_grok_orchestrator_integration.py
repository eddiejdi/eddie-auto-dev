#!/usr/bin/env python3
"""
Integration Tests for Grok Orchestrator - Parte 3B (Simplified)

Testes focam na integração e comunicação, não em LLM calls
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from specialized_agents.grok_orchestrator import (
    GrokOrchestrator,
    GrokTask,
)
from specialized_agents.resource_manager import TaskPriority, ResourceMetrics, ResourceStatus
from specialized_agents.comm_bus import get_comm_bus, MessageType
from specialized_agents.master_controller import RoutingDecision, TaskComplexity, AgentLanguage, LLMModel


class TestGrokTaskStructure:
    """Testes de estrutura de tarefa"""
    
    def test_create_task(self):
        """Criar tarefa com valores padrão"""
        task = GrokTask(
            task_id="task_001",
            description="Write a Python script"
        )
        
        assert task.task_id == "task_001"
        assert task.priority == TaskPriority.NORMAL
        assert task.timeout_ms == 30000


@pytest.mark.asyncio
class TestGrokOrchestratorBasic:
    """Testes básicos do orchestrator"""
    
    async def test_orchestrator_creation(self):
        """Criar orchestrator"""
        orch = GrokOrchestrator(use_vault=False)
        
        assert orch.controller is not None
        assert orch.resource_manager is not None
        assert orch.comm_bus is not None
    
    async def test_orchestrator_initialization(self):
        """Inicializar orchestrator"""
        orch = GrokOrchestrator(
            agent_languages=["python", "go"],
            use_vault=False
        )
        await orch.initialize()
        
        bus = get_comm_bus()
        assert orch.controller_id in bus.inbox
        assert orch.resource_mgr_id in bus.inbox


@pytest.mark.asyncio
class TestGrokIntegration:
    """Testes de integração com mocks"""
    
    async def test_process_task_with_mock_controller(self):
        """Processar tarefa com controller mockado"""
        orch = GrokOrchestrator(use_vault=False)
        await orch.initialize()
        
        # Mock the route_task method
        mock_decision = RoutingDecision(
            task_id="test_001",
            language="python",
            complexity=TaskComplexity.MODERATE,
            selected_agent="python",
            selected_model=LLMModel.EXPERT,
            confidence=0.95,
            reasoning="Python is suitable",
            estimated_timeout_ms=5000,
        )
        
        orch.controller.route_task = AsyncMock(return_value=mock_decision)
        
        task = GrokTask(
            task_id="test_001",
            description="Test task"
        )
        
        plan = await orch.process_task(task)
        
        # Verify plan was created
        assert plan is not None
        assert plan.task_id == "test_001"
        assert plan.selected_language == "python"
    
    async def test_execution_outcome_handling(self):
        """Manejar resultado de execução"""
        orch = GrokOrchestrator(use_vault=False)
        await orch.initialize()
        
        # Mock controller
        orch.controller.route_task = AsyncMock(return_value=RoutingDecision(
            task_id="test_002",
            language="python",
            complexity=TaskComplexity.SIMPLE,
            selected_agent="python",
            selected_model=LLMModel.EXPERT,
            confidence=0.9,
            reasoning="Simple task",
            estimated_timeout_ms=5000,
        ))
        
        task = GrokTask(
            task_id="test_002",
            description="Simple task"
        )
        
        plan = await orch.process_task(task)
        assert plan is not None
        
        # Handle completion
        await orch.handle_execution_outcome(
            task_id="test_002",
            agent_id="agent_python_1",
            success=True,
            output="Success",
            duration_ms=1000,
            quality_score=0.9
        )
        
        # Task should be completed
        assert "test_002" not in orch.active_tasks
        assert "test_002" in orch.completed_tasks
    
    async def test_resource_update_integration(self):
        """Atualizar recursos"""
        orch = GrokOrchestrator(use_vault=False)
        await orch.initialize()
        
        bus = get_comm_bus()
        initial_msg_count = len(bus.message_log)
        
        # Update resources
        await orch.update_resource_status(
            agent_language="python",
            cpu_percent=50.0,
            memory_mb=2048.0,
            gpu_percent=10.0,
            active_tasks=2
        )
        
        # Check metrics updated
        metrics = orch.resource_manager.agent_metrics["python"]
        assert metrics.cpu_percent == 50.0
        
        # Check status message published
        status_msgs = [m for m in bus.message_log[initial_msg_count:] if m.message_type == MessageType.STATUS]
        assert len(status_msgs) > 0
    
    async def test_orchestrator_status(self):
        """Obter status do orchestrator"""
        orch = GrokOrchestrator(use_vault=False)
        await orch.initialize()
        
        status = orch.get_orchestrator_status()
        
        assert "active_tasks" in status
        assert "completed_tasks" in status
        assert "failed_tasks" in status
        assert "resource_stats" in status


@pytest.mark.asyncio
class TestGrokErrorHandling:
    """Testes de tratamento de erros"""
    
    async def test_task_failure_recording(self):
        """Registrar falha de tarefa"""
        orch = GrokOrchestrator(use_vault=False)
        await orch.initialize()
        
        # Hard-fail the controller to simulate routing error
        orch.controller.route_task = AsyncMock(return_value=None)
        
        task = GrokTask(
            task_id="failing_task",
            description="This will fail"
        )
        
        plan = await orch.process_task(task)
        
        # Should return None and record failure
        assert plan is None
        assert "failing_task" in orch.failed_tasks
    
    async def test_resource_exhaustion(self):
        """Lidar com recursos esgotados"""
        orch = GrokOrchestrator(
            agent_languages=["python"],
            use_vault=False
        )
        await orch.initialize()
        
        # Mark agent as exhausted
        exhausted = ResourceMetrics(
            language="python",
            cpu_percent=100.0,
            memory_percent=100.0,
            gpu_utilization=100.0,
            active_tasks=500,
        )
        orch.resource_manager.update_metrics("python", exhausted)
        
        # Try to process task
        orch.controller.route_task = AsyncMock(return_value=RoutingDecision(
            task_id="test_exhaustion",
            language="python",
            complexity=TaskComplexity.SIMPLE,
            selected_agent="python",
            selected_model=LLMModel.EXPERT,
            confidence=0.9,
            reasoning="Simple",
            estimated_timeout_ms=5000,
        ))
        
        task = GrokTask(
            task_id="test_exhaustion",
            description="Task with exhausted resources"
        )
        
        plan = await orch.process_task(task)
        
        # Should fail due to no resources
        assert plan is None
        assert "test_exhaustion" in orch.failed_tasks


@pytest.mark.asyncio
class TestGrokCommBusIntegration:
    """Testes de integração com CommBus"""
    
    async def test_routing_decision_published(self):
        """Decisão publicada no CommBus"""
        orch = GrokOrchestrator(use_vault=False)
        await orch.initialize()
        
        bus = get_comm_bus()
        bus.message_log.clear()
        
        orch.controller.route_task = AsyncMock(return_value=RoutingDecision(
            task_id="test_bus",
            language="go",
            complexity=TaskComplexity.MODERATE,
            selected_agent="go",
            selected_model=LLMModel.EXPERT,
            confidence=0.85,
            reasoning="Go is good for this",
            estimated_timeout_ms=10000,
        ))
        
        task = GrokTask(
            task_id="test_bus",
            description="Go task"
        )
        
        plan = await orch.process_task(task)
        
        if plan:
            # Mensagem de decisão deve ter sido publicada
            decisions = [m for m in bus.message_log if m.message_type == MessageType.DECISION]
            assert len(decisions) > 0
    
    async def test_outcome_published(self):
        """Resultado publicado no CommBus"""
        orch = GrokOrchestrator(use_vault=False)
        await orch.initialize()
        
        bus = get_comm_bus()
        
        orch.controller.route_task = AsyncMock(return_value=RoutingDecision(
            task_id="test_outcome",
            language="typescript",
            complexity=TaskComplexity.COMPLEX,
            selected_agent="typescript",
            selected_model=LLMModel.EXPERT,
            confidence=0.9,
            reasoning="TypeScript for complex",
            estimated_timeout_ms=15000,
        ))
        
        task = GrokTask(
            task_id="test_outcome",
            description="Complex TS task"
        )
        
        plan = await orch.process_task(task)
        
        if plan:
            initial_count = len(bus.message_log)
            
            await orch.handle_execution_outcome(
                task_id="test_outcome",
                agent_id="agent_typescript_1",
                success=True,
                output="Completed",
                duration_ms=5000,
                quality_score=0.92
            )
            
            # Nova mensagem de resultado deve estar no bus
            new_msgs = bus.message_log[initial_count:]
            outcomes = [m for m in new_msgs if m.message_type == MessageType.OUTCOME]
            assert len(outcomes) > 0
