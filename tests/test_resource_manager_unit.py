#!/usr/bin/env python3
"""
Unit Tests for Resource Manager - Parte 2

Testes cobrem:
- Inicialização
- Métricas e monitoramento
- Alocação de recursos e throttling
- Fila de prioridade
- Seleção de agente (LRU + scoring)
- Timeout dinâmico
- Estatísticas
"""

import pytest
from datetime import datetime, timedelta
from specialized_agents.resource_manager import (
    ResourceManager,
    ResourceMetrics,
    ResourceStatus,
    TaskPriority,
    TaskAllocation,
)


class TestInitialization:
    """Testes de inicialização"""
    
    def test_init_with_languages(self):
        """Teste inicialização com lista de linguagens"""
        languages = ["python", "javascript", "go"]
        rm = ResourceManager(languages)
        
        assert len(rm.agent_languages) == 3
        assert "python" in rm.agent_languages
        assert len(rm.agent_metrics) == 3
    
    def test_system_limits(self):
        """Teste constantes de limite do sistema"""
        rm = ResourceManager(["python"])
        
        assert rm.SYSTEM_MEMORY_MB == 32 * 1024  # 32GB
        assert rm.MAX_MEMORY_PERCENT_PER_AGENT == 50.0
        assert rm.MAX_GPU_UTILIZATION == 95.0
    
    def test_initial_metrics_empty(self):
        """Teste que métricas iniciam vazias"""
        rm = ResourceManager(["python", "go"])
        
        for lang in ["python", "go"]:
            metrics = rm.get_metrics(lang)
            assert metrics.language == lang
            assert metrics.cpu_percent == 0.0
            assert metrics.active_tasks == 0


class TestResourceMetrics:
    """Testes da classe ResourceMetrics"""
    
    def test_metrics_overall_load_empty(self):
        """Teste load overall com métricas vazias"""
        metrics = ResourceMetrics(language="python")
        
        assert metrics.overall_load == 0.0
    
    def test_metrics_overall_load_calculation(self):
        """Teste cálculo de overall_load"""
        # Load: (0.2 * CPU) + (0.3 * MEM) + (0.3 * GPU) + (0.2 * TASK)
        metrics = ResourceMetrics(
            language="python",
            cpu_percent=50.0,      # 0.2 * 0.5 = 0.10
            memory_percent=50.0,    # 0.3 * 0.5 = 0.15
            gpu_utilization=50.0,   # 0.3 * 0.5 = 0.15
            active_tasks=1,         # 0.2 * (1/5) = 0.04
        )
        
        expected = 0.10 + 0.15 + 0.15 + 0.04  # 0.44
        assert abs(metrics.overall_load - expected) < 0.01
    
    def test_metrics_status_healthy(self):
        """Teste status HEALTHY (load < 0.3)"""
        metrics = ResourceMetrics(
            language="python",
            cpu_percent=10.0,
            memory_percent=10.0,
        )
        
        assert metrics.status == ResourceStatus.HEALTHY
    
    def test_metrics_status_warning(self):
        """Teste status WARNING (0.3 <= load < 0.7)"""
        metrics = ResourceMetrics(
            language="python",
            cpu_percent=80.0,
            memory_percent=80.0,
            gpu_utilization=20.0,
        )
        
        assert metrics.status == ResourceStatus.WARNING
    
    def test_metrics_status_critical(self):
        """Teste status CRITICAL (0.7 <= load < 0.95)"""
        metrics = ResourceMetrics(
            language="python",
            cpu_percent=95.0,
            memory_percent=95.0,
            gpu_utilization=80.0,
        )
        
        assert metrics.status == ResourceStatus.CRITICAL
    
    def test_metrics_status_exhausted(self):
        """Teste status EXHAUSTED (load >= 0.95)"""
        metrics = ResourceMetrics(
            language="python",
            cpu_percent=100.0,
            memory_percent=100.0,
            gpu_utilization=100.0,
            active_tasks=50,
        )
        
        assert metrics.status == ResourceStatus.EXHAUSTED


class TestResourceAllocation:
    """Testes de alocação de recursos"""
    
    def test_allocate_simple_task(self):
        """Teste alocação simples de tarefa"""
        rm = ResourceManager(["python"])
        
        success, reason, alloc = rm.allocate_task(
            "task_001", "python",
            priority=TaskPriority.NORMAL,
            memory_mb=256.0,
        )
        
        assert success is True
        assert reason == "OK"
        assert alloc is not None
        assert alloc.task_id == "task_001"
        assert alloc.language == "python"
        assert len(rm.all_allocations) == 1
    
    def test_allocate_multiple_tasks(self):
        """Teste múltiplas alocações"""
        rm = ResourceManager(["python"])
        
        for i in range(5):
            success, _, alloc = rm.allocate_task(
                f"task_{i:03d}", "python",
                memory_mb=256.0,
            )
            assert success
        
        assert len(rm.all_allocations) == 5
        assert len(rm.agent_allocations["python"]) == 5
    
    def test_task_allocation_lifecycle(self):
        """Teste ciclo de vida de tarefa"""
        rm = ResourceManager(["python"])
        
        _, _, alloc = rm.allocate_task("task_001", "python")
        assert alloc.is_queued
        assert not alloc.is_active
        
        rm.start_task("task_001")
        assert not alloc.is_queued
        assert alloc.is_active
        
        rm.complete_task("task_001")
        assert alloc.completed_at is not None
        assert alloc.duration_ms is not None
    
    def test_allocate_unknown_language(self):
        """Teste alocação com linguagem desconhecida"""
        rm = ResourceManager(["python"])
        
        success, reason, _ = rm.allocate_task(
            "task_001", "cobol"
        )
        
        assert success is False
        assert "Unknown language" in reason


class TestThrottling:
    """Testes de throttling e rejeição"""
    
    def test_reject_exhausted_agent(self):
        """Teste rejeição de agente exhausted"""
        rm = ResourceManager(["python"])
        
        # Simular agente exhausted (load >= 0.95)
        exhausted_metrics = ResourceMetrics(
            language="python",
            cpu_percent=100.0,
            memory_percent=100.0,
            gpu_utilization=100.0,
            active_tasks=50,
        )
        assert exhausted_metrics.status == ResourceStatus.EXHAUSTED
        rm.update_metrics("python", exhausted_metrics)
        
        success, reason, _ = rm.allocate_task("task_001", "python")
        assert success is False
        assert "exhausted" in reason.lower()
    
    def test_reject_full_queue(self):
        """Teste rejeição quando fila está cheia"""
        rm = ResourceManager(["python"])
        
        # Encher a fila
        for i in range(rm.MAX_QUEUED_TASKS_PER_AGENT):
            rm.allocate_task(f"task_{i:03d}", "python")
        
        # Tentar adicionar mais uma
        success, reason, _ = rm.allocate_task("task_overflow", "python")
        assert success is False
        assert "queue full" in reason.lower()
    
    def test_only_urgent_on_critical(self):
        """Teste que apenas URGENT é permitido em CRITICAL"""
        rm = ResourceManager(["python"])
        
        # Simular crítico (0.7 <= load < 0.95)
        critical_metrics = ResourceMetrics(
            language="python",
            cpu_percent=95.0,
            memory_percent=80.0,
            gpu_utilization=70.0,
            active_tasks=3,
        )
        assert critical_metrics.status == ResourceStatus.CRITICAL
        rm.update_metrics("python", critical_metrics)
        
        # NORMAL deve ser rejeitado
        success, _, _ = rm.allocate_task(
            "task_normal", "python",
            priority=TaskPriority.NORMAL,
        )
        assert success is False
        
        # URGENT deve passar
        success, _, _ = rm.allocate_task(
            "task_urgent", "python",
            priority=TaskPriority.URGENT,
        )
        assert success is True


class TestPriorityQueue:
    """Testes da fila de prioridades"""
    
    def test_priority_ordering(self):
        """Teste que tarefas saem por ordem de prioridade"""
        rm = ResourceManager(["python"])
        
        # Adicionar tarefas em ordem: NORMAL, BACKGROUND, URGENT
        rm.allocate_task("task_normal", "python", priority=TaskPriority.NORMAL)
        rm.allocate_task("task_bg", "python", priority=TaskPriority.BACKGROUND)
        rm.allocate_task("task_urgent", "python", priority=TaskPriority.URGENT)
        
        # Devem sair em ordem: URGENT, NORMAL, BACKGROUND
        task1 = rm.get_next_task()
        assert task1.task_id == "task_urgent"
        
        task2 = rm.get_next_task()
        assert task2.task_id == "task_normal"
        
        task3 = rm.get_next_task()
        assert task3.task_id == "task_bg"
    
    def test_fifo_within_priority(self):
        """Teste FIFO dentro da mesma prioridade"""
        rm = ResourceManager(["python"])
        
        # Adicionar 3 NORMAL
        for i in range(3):
            rm.allocate_task(f"task_{i}", "python", priority=TaskPriority.NORMAL)
        
        # Devem sair em ordem de inserção
        task1 = rm.get_next_task()
        assert task1.task_id == "task_0"
        
        task2 = rm.get_next_task()
        assert task2.task_id == "task_1"
        
        task3 = rm.get_next_task()
        assert task3.task_id == "task_2"


class TestAgentSelection:
    """Testes de seleção de agente (LRU + Scoring)"""
    
    def test_select_least_loaded(self):
        """Teste seleção do agente menos carregado"""
        rm = ResourceManager(["python", "go"])
        
        # Python: pesado (load ~0.65)
        python_metrics = ResourceMetrics(
            language="python",
            cpu_percent=80.0,
            memory_percent=80.0,
            gpu_utilization=40.0,
            active_tasks=3,
        )
        rm.update_metrics("python", python_metrics)
        
        # Go: leve (load ~0.15)
        go_metrics = ResourceMetrics(
            language="go",
            cpu_percent=20.0,
            memory_percent=10.0,
            gpu_utilization=10.0,
            active_tasks=0,
        )
        rm.update_metrics("go", go_metrics)
        
        best_lang, score = rm.select_best_agent()
        assert best_lang == "go", f"Expected go but got {best_lang}"
    
    def test_select_by_recency(self):
        """Teste seleção por recency LRU"""
        rm = ResourceManager(["python", "javascript"])
        
        # Ambos com carga igual
        metrics = ResourceMetrics(
            language="python",
            cpu_percent=50.0,
            memory_percent=50.0,
            gpu_utilization=50.0,
        )
        rm.update_metrics("python", metrics)
        
        metrics2 = ResourceMetrics(
            language="javascript",
            cpu_percent=50.0,
            memory_percent=50.0,
            gpu_utilization=50.0,
        )
        rm.update_metrics("javascript", metrics2)
        
        # Python foi executado agora
        rm.agent_last_execution["python"] = datetime.now()
        # JavaScript faz 1 hora (menos utilizado recentemente)
        rm.agent_last_execution["javascript"] = datetime.now() - timedelta(hours=1)
        
        best_lang, _ = rm.select_best_agent()
        # Deve selecionar JavaScript porque foi menos usado (LRU prefer unused)
        assert best_lang == "javascript", f"Expected javascript but got {best_lang}"
    
    def test_select_with_language_filter(self):
        """Teste seleção com filtro de linguagem"""
        rm = ResourceManager(["python", "go", "rust"])
        
        # Selecionar apenas entre Go e Rust
        best_lang, _ = rm.select_best_agent(["go", "rust"])
        
        assert best_lang in ["go", "rust"]


class TestTimeoutAdjustment:
    """Testes de ajuste dinâmico de timeout"""
    
    def test_timeout_healthy_status(self):
        """Teste timeout é base para HEALTHY"""
        rm = ResourceManager(["python"])
        
        # Simular healthy
        healthy_metrics = ResourceMetrics(
            language="python",
            cpu_percent=20.0,
            memory_percent=20.0,
        )
        rm.update_metrics("python", healthy_metrics)
        
        adjusted = rm.adjust_timeout(30000, "python")
        assert adjusted == 30000  # Sem ajuste
    
    def test_timeout_warning_status(self):
        """Teste timeout +25% para WARNING"""
        rm = ResourceManager(["python"])
        
        warning_metrics = ResourceMetrics(
            language="python",
            cpu_percent=80.0,
            memory_percent=80.0,
            gpu_utilization=20.0,
        )
        assert warning_metrics.status == ResourceStatus.WARNING
        rm.update_metrics("python", warning_metrics)
        
        adjusted = rm.adjust_timeout(30000, "python")
        assert adjusted == int(30000 * 1.25)  # 37500
    
    def test_timeout_critical_status(self):
        """Teste timeout +50% para CRITICAL"""
        rm = ResourceManager(["python"])
        
        critical_metrics = ResourceMetrics(
            language="python",
            cpu_percent=95.0,
            memory_percent=95.0,
            gpu_utilization=80.0,
        )
        assert critical_metrics.status == ResourceStatus.CRITICAL
        rm.update_metrics("python", critical_metrics)
        
        adjusted = rm.adjust_timeout(30000, "python")
        assert adjusted == int(30000 * 1.5)  # 45000


class TestStatistics:
    """Testes de estatísticas e relatórios"""
    
    def test_get_statistics_empty(self):
        """Teste estatísticas com nenhuma alocação"""
        rm = ResourceManager(["python", "go"])
        
        stats = rm.get_statistics()
        assert stats["total_allocations"] == 0
        assert stats["active_tasks"] == 0
        assert stats["queued_tasks"] == 0
    
    def test_get_statistics_with_tasks(self):
        """Teste estatísticas com tarefas"""
        rm = ResourceManager(["python"])
        
        # Alocar 5 tarefas
        for i in range(5):
            rm.allocate_task(f"task_{i}", "python")
        
        stats = rm.get_statistics()
        assert stats["total_allocations"] == 5
        assert stats["queued_tasks"] == 5
        assert stats["active_tasks"] == 0
        
        # Iniciar 2
        rm.start_task("task_0")
        rm.start_task("task_1")
        
        stats = rm.get_statistics()
        assert stats["active_tasks"] == 2
        assert stats["queued_tasks"] == 3
    
    def test_get_agent_summary(self):
        """Teste sumário de agente específico"""
        rm = ResourceManager(["python"])
        
        metrics = ResourceMetrics(
            language="python",
            cpu_percent=50.0,
            memory_mb=2048.0,
            active_tasks=2,
        )
        rm.update_metrics("python", metrics)
        
        # Adicionar tarefas
        rm.allocate_task("task_1", "python")
        rm.allocate_task("task_2", "python")
        rm.start_task("task_1")
        
        summary = rm.get_agent_summary("python")
        assert summary["language"] == "python"
        assert summary["load"] == metrics.overall_load
        assert summary["memory_mb"] == 2048.0
        assert summary["active_tasks"] == 1
        assert summary["queued_tasks"] == 1


class TestTaskOperations:
    """Testes de operações em tarefas"""
    
    def test_get_queued_tasks(self):
        """Teste obtenção de tarefas queued"""
        rm = ResourceManager(["python"])
        
        rm.allocate_task("task_1", "python")
        rm.allocate_task("task_2", "python")
        
        queued = rm.get_queued_tasks("python")
        assert len(queued) == 2
        
        rm.start_task("task_1")
        queued = rm.get_queued_tasks("python")
        assert len(queued) == 1
    
    def test_get_active_tasks(self):
        """Teste obtenção de tarefas ativas"""
        rm = ResourceManager(["python"])
        
        rm.allocate_task("task_1", "python")
        rm.allocate_task("task_2", "python")
        
        active = rm.get_active_tasks("python")
        assert len(active) == 0
        
        rm.start_task("task_1")
        rm.start_task("task_2")
        
        active = rm.get_active_tasks("python")
        assert len(active) == 2
    
    def test_deallocate_task(self):
        """Teste desalocação de tarefa"""
        rm = ResourceManager(["python"])
        
        rm.allocate_task("task_1", "python")
        assert len(rm.all_allocations) == 1
        
        rm.deallocate_task("task_1")
        assert len(rm.all_allocations) == 0


class TestCleanup:
    """Testes de limpeza"""
    
    def test_cleanup_completed_tasks(self):
        """Teste limpeza de tarefas concluídas antigas"""
        rm = ResourceManager(["python"])
        
        # Criar e completar 2 tarefas
        _, _, alloc1 = rm.allocate_task("task_1", "python")
        _, _, alloc2 = rm.allocate_task("task_2", "python")
        
        rm.start_task("task_1")
        rm.complete_task("task_1")
        
        rm.start_task("task_2")
        rm.complete_task("task_2")
        
        assert len(rm.all_allocations) == 2
        
        # Forçar timestamp antigo para task_1
        alloc1.completed_at = datetime.now() - timedelta(hours=2)
        
        # Limpar tarefas com mais de 1 hora
        removed = rm.cleanup_completed_tasks(age_minutes=60)
        
        assert removed == 1
        assert len(rm.all_allocations) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
