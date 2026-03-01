#!/usr/bin/env python3
"""
Unit Tests for Master Controller - Parte 1

Tests cover:
- Initialization (with and without vault)
- Agent scoring and selection
- Model selection based on complexity
- Timeout estimation
- Execution outcome recording
- Statistics calculation
"""

import pytest
import asyncio
import os
from datetime import datetime
from specialized_agents.master_controller import (
    MasterController,
    MasterControllerConfig,
    TaskComplexity,
    AgentLanguage,
    LLMModel,
    AgentScore,
    RoutingDecision,
    ExecutionOutcome,
)


class TestInitialization:
    """Test MasterController initialization"""
    
    def test_init_without_vault(self):
        """Test initialization with vault disabled"""
        mc = MasterController(use_vault=False)
        
        assert mc.controller_host is not None
        assert mc.expert_host is not None
        assert len(mc.agent_scores) == 8
        assert len(mc.SUPPORTED_LANGUAGES) == 8
        assert mc.use_vault is False
    
    def test_init_with_vault(self):
        """Test initialization with vault enabled (default)"""
        mc = MasterController(use_vault=True)
        
        assert mc.controller_host is not None
        assert mc.expert_host is not None
        assert mc.use_vault is True
    
    def test_init_custom_values_override(self):
        """Test that custom values override vault"""
        mc = MasterController(
            controller_host="http://localhost:11435",
            expert_host="http://localhost:11434",
            use_vault=False
        )
        
        assert mc.controller_host == "http://localhost:11435"
        assert mc.expert_host == "http://localhost:11434"
    
    def test_all_languages_supported(self):
        """Verify all 8 languages are supported"""
        mc = MasterController(use_vault=False)
        expected = {"python", "javascript", "typescript", "go", "rust", "java", "csharp", "php"}
        assert set(mc.SUPPORTED_LANGUAGES) == expected
    
    def test_agent_scores_initialized(self):
        """Each language should have initial AgentScore"""
        mc = MasterController(use_vault=False)
        
        for lang in mc.SUPPORTED_LANGUAGES:
            score = mc.get_agent_score(lang)
            assert isinstance(score, AgentScore)
            assert score.language == lang
            assert score.total_executions == 0
            assert score.successful_executions == 0
            assert score.success_rate == 0.5  # Default when no data


class TestVaultConfiguration:
    """Test vault configuration loading"""
    
    def test_vault_config_returns_dict(self):
        """Test that vault configuration returns a proper dict"""
        config = MasterControllerConfig.load()
        
        assert isinstance(config, dict)
        assert "controller_host" in config
        assert "expert_host" in config
        assert "db_url" in config
        assert "enable_learning" in config
    
    def test_vault_values_are_strings(self):
        """Test that configuration values are properly typed"""
        config = MasterControllerConfig.load()
        
        # Should be strings
        assert isinstance(config["controller_host"], str)
        assert isinstance(config["expert_host"], str)
        assert isinstance(config["db_url"], str)
        
        # Learning flag should be bool
        assert isinstance(config["enable_learning"], bool)
    
    def test_vault_has_default_hosts(self):
        """Test that hosts have sensible defaults"""
        config = MasterControllerConfig.load()
        
        # Should have some value
        assert config["controller_host"] is not None
        assert config["expert_host"] is not None
        
        # Should look like URLs
        assert "http" in config["controller_host"] or "localhost" in config["controller_host"]
        assert ("http" in config["expert_host"] or "localhost" in config["expert_host"])


class TestAgentScoring:
    """Test agent scoring and selection"""
    
    def test_get_agent_score(self):
        """Test retrieving agent score"""
        mc = MasterController(use_vault=False)
        score = mc.get_agent_score("python")
        
        assert score.language == "python"
        assert score.total_executions == 0
    
    def test_success_rate_calculation(self):
        """Test success_rate property"""
        score = AgentScore(language="python")
        
        # No data: neutral
        assert score.success_rate == 0.5
        
        # With data
        score.total_executions = 10
        score.successful_executions = 8
        assert score.success_rate == 0.8
    
    def test_reliability_score(self):
        """Test reliability_score = (success_rate * 0.6) + (quality * 0.4)"""
        score = AgentScore(language="python")
        score.total_executions = 10
        score.successful_executions = 8  # 80% success
        score.avg_response_quality = 0.90
        
        expected = (0.8 * 0.6) + (0.90 * 0.4)  # 0.84
        assert abs(score.reliability_score - expected) < 0.001
    
    def test_select_best_agent_with_hint(self):
        """Test agent selection when language is provided"""
        mc = MasterController(use_vault=False)
        
        selected = mc._select_best_agent(language="rust")
        assert selected == "rust"
    
    def test_select_best_agent_by_score(self):
        """Test agent selection by highest score when no hint"""
        mc = MasterController(use_vault=False)
        
        # Set Python as best performer
        python_score = mc.get_agent_score("python")
        python_score.total_executions = 100
        python_score.successful_executions = 95
        python_score.avg_response_quality = 0.95
        
        selected = mc._select_best_agent(language=None)
        assert selected == "python"
    
    def test_select_best_agent_invalid_language(self):
        """Test fallback when invalid language provided"""
        mc = MasterController(use_vault=False)
        selected = mc._select_best_agent(language="cobol")
        
        assert selected in mc.SUPPORTED_LANGUAGES


class TestModelSelection:
    """Test LLM model selection based on complexity"""
    
    def test_simple_complexity_uses_controller(self):
        """SIMPLE tasks should use Controller (fast)"""
        mc = MasterController(use_vault=False)
        
        model = mc._select_model(TaskComplexity.SIMPLE)
        assert model == LLMModel.CONTROLLER
    
    def test_moderate_complexity_uses_controller(self):
        """MODERATE tasks should use Controller"""
        mc = MasterController(use_vault=False)
        
        model = mc._select_model(TaskComplexity.MODERATE)
        assert model == LLMModel.CONTROLLER
    
    def test_complex_uses_expert(self):
        """COMPLEX tasks should use Expert (deep)"""
        mc = MasterController(use_vault=False)
        
        model = mc._select_model(TaskComplexity.COMPLEX)
        assert model == LLMModel.EXPERT
    
    def test_edge_case_uses_expert(self):
        """EDGE_CASE should escalate to Expert"""
        mc = MasterController(use_vault=False)
        
        model = mc._select_model(TaskComplexity.EDGE_CASE)
        assert model == LLMModel.EXPERT
    
    def test_unknown_defaults_to_expert(self):
        """Unknown complexity defaults to Expert"""
        mc = MasterController(use_vault=False)
        
        model = mc._select_model(TaskComplexity.UNKNOWN)
        assert model == LLMModel.EXPERT


class TestTimeoutEstimation:
    """Test timeout estimation based on complexity and model"""
    
    def test_timeout_simple_controller(self):
        """SIMPLE + CONTROLLER should be ~15s (30s * 0.5)"""
        mc = MasterController(use_vault=False)
        
        timeout = mc._estimate_timeout(TaskComplexity.SIMPLE, LLMModel.CONTROLLER)
        assert 14000 < timeout < 16000  # ~15s
    
    def test_timeout_moderate_controller(self):
        """MODERATE + CONTROLLER should be ~30s (30s * 1.0)"""
        mc = MasterController(use_vault=False)
        
        timeout = mc._estimate_timeout(TaskComplexity.MODERATE, LLMModel.CONTROLLER)
        assert 28000 < timeout < 32000
    
    def test_timeout_complex_expert(self):
        """COMPLEX + EXPERT should be ~180s (120s * 1.5)"""
        mc = MasterController(use_vault=False)
        
        timeout = mc._estimate_timeout(TaskComplexity.COMPLEX, LLMModel.EXPERT)
        assert 175000 < timeout < 185000
    
    def test_timeout_edge_case_expert(self):
        """EDGE_CASE + EXPERT should be ~240s (120s * 2.0)"""
        mc = MasterController(use_vault=False)
        
        timeout = mc._estimate_timeout(TaskComplexity.EDGE_CASE, LLMModel.EXPERT)
        assert 235000 < timeout < 245000
    
    def test_timeout_ultra_expert(self):
        """ULTRA_EXPERT baseline should be 300s"""
        mc = MasterController(use_vault=False)
        
        # MODERATE + ULTRA_EXPERT = 300s * 1.0 = 300s
        timeout = mc._estimate_timeout(TaskComplexity.MODERATE, LLMModel.ULTRA_EXPERT)
        assert 295000 < timeout < 305000


class TestExecutionOutcomeRecording:
    """Test recording and processing execution outcomes"""
    
    def test_record_successful_outcome(self):
        """Test recording a successful execution"""
        mc = MasterController(use_vault=False)
        decision = RoutingDecision(
            task_id="test_1",
            language="python",
            complexity=TaskComplexity.SIMPLE,
            selected_agent="python",
            selected_model=LLMModel.CONTROLLER,
            confidence=0.95,
            reasoning="test",
            estimated_timeout_ms=30000,
        )
        
        outcome = mc.record_execution_outcome(
            task_id="test_1",
            decision=decision,
            success=True,
            execution_time_ms=500.0,
            response_quality=0.95,
        )
        
        assert outcome.success is True
        assert outcome.execution_time_ms == 500.0
        assert outcome.response_quality == 0.95
        assert len(mc.execution_outcomes) == 1
    
    def test_record_failed_outcome(self):
        """Test recording a failed execution"""
        mc = MasterController(use_vault=False)
        decision = RoutingDecision(
            task_id="test_fail",
            language="go",
            complexity=TaskComplexity.MODERATE,
            selected_agent="go",
            selected_model=LLMModel.CONTROLLER,
            confidence=0.70,
            reasoning="test",
            estimated_timeout_ms=30000,
        )
        
        outcome = mc.record_execution_outcome(
            task_id="test_fail",
            decision=decision,
            success=False,
            execution_time_ms=2000.0,
            response_quality=0.30,
            error_message="Timeout exceeded",
        )
        
        assert outcome.success is False
        assert outcome.error_message == "Timeout exceeded"
    
    def test_agent_scores_updated_on_outcome(self):
        """Test that agent scores are updated after outcome"""
        mc = MasterController(use_vault=False)
        decision = RoutingDecision(
            task_id="test_score",
            language="python",
            complexity=TaskComplexity.SIMPLE,
            selected_agent="python",
            selected_model=LLMModel.CONTROLLER,
            confidence=0.80,
            reasoning="test",
            estimated_timeout_ms=30000,
        )
        
        # Record success
        mc.record_execution_outcome(
            task_id="test_score",
            decision=decision,
            success=True,
            execution_time_ms=100.0,
            response_quality=0.95,
        )
        
        python_score = mc.get_agent_score("python")
        assert python_score.total_executions == 1
        assert python_score.successful_executions == 1
        assert python_score.failed_executions == 0
    
    def test_exponential_moving_average(self):
        """Test that execution times use exponential moving average"""
        mc = MasterController(use_vault=False)
        decision = RoutingDecision(
            task_id="test_avg",
            language="javascript",
            complexity=TaskComplexity.MODERATE,
            selected_agent="javascript",
            selected_model=LLMModel.CONTROLLER,
            confidence=0.80,
            reasoning="test",
            estimated_timeout_ms=30000,
        )
        
        # First execution: 100ms
        mc.record_execution_outcome(
            task_id="task_1",
            decision=decision,
            success=True,
            execution_time_ms=100.0,
            response_quality=0.90,
        )
        
        js_score = mc.get_agent_score("javascript")
        # avg = 0.2 * 100 + 0.8 * 0 = 20
        assert abs(js_score.avg_execution_time_ms - 20.0) < 0.1
        
        # Second execution: 200ms
        mc.record_execution_outcome(
            task_id="task_2",
            decision=decision,
            success=True,
            execution_time_ms=200.0,
            response_quality=0.90,
        )
        
        # avg = 0.2 * 200 + 0.8 * 20 = 40 + 16 = 56
        assert abs(js_score.avg_execution_time_ms - 56.0) < 0.1


class TestStatistics:
    """Test statistics and introspection methods"""
    
    def test_get_statistics_empty(self):
        """Test statistics with no executions"""
        mc = MasterController(use_vault=False)
        stats = mc.get_statistics()
        
        assert stats["total_decisions"] == 0
        assert stats["total_outcomes"] == 0
        assert stats["overall_success_rate"] == 0.0
        assert len(stats["agent_stats"]) == 8
    
    def test_get_statistics_with_outcomes(self):
        """Test statistics with some executions"""
        mc = MasterController(use_vault=False)
        
        # Add some decisions
        for i in range(3):
            decision = RoutingDecision(
                task_id=f"task_{i}",
                language="python",
                complexity=TaskComplexity.SIMPLE,
                selected_agent="python",
                selected_model=LLMModel.CONTROLLER,
                confidence=0.90,
                reasoning="test",
                estimated_timeout_ms=30000,
            )
            mc.decision_history.append(decision)
            
            # Record outcome
            mc.record_execution_outcome(
                task_id=f"task_{i}",
                decision=decision,
                success=(i < 2),  # 2 success, 1 fail
                execution_time_ms=100.0 * (i + 1),
                response_quality=0.90,
            )
        
        stats = mc.get_statistics()
        assert stats["total_decisions"] == 3
        assert stats["total_outcomes"] == 3
        assert stats["overall_success_rate"] == pytest.approx(2/3, abs=0.01)
        assert stats["agent_stats"]["python"]["total"] == 3
        assert stats["agent_stats"]["python"]["successful"] == 2
    
    def test_get_agent_stats(self):
        """Test agent-specific statistics"""
        mc = MasterController(use_vault=False)
        
        decision = RoutingDecision(
            task_id="agent_stat_test",
            language="rust",
            complexity=TaskComplexity.COMPLEX,
            selected_agent="rust",
            selected_model=LLMModel.EXPERT,
            confidence=0.85,
            reasoning="test",
            estimated_timeout_ms=120000,
        )
        
        mc.record_execution_outcome(
            task_id="agent_stat_test",
            decision=decision,
            success=True,
            execution_time_ms=5000.0,
            response_quality=0.92,
        )
        
        stats = mc.get_agent_stats("rust")
        assert stats["language"] == "rust"
        assert stats["total_executions"] == 1
        assert stats["successful_executions"] == 1
        assert stats["success_rate"] == 1.0
        assert stats["avg_execution_time_ms"] == pytest.approx(1000.0, abs=1.0)
    
    def test_get_agent_stats_unknown_language(self):
        """Test stats for unknown language returns None"""
        mc = MasterController(use_vault=False)
        stats = mc.get_agent_stats("brainfuck")
        assert stats is None


class TestComplexityThresholds:
    """Test complexity classification"""
    
    def test_complexity_thresholds_exist(self):
        """Verify complexity thresholds are defined"""
        mc = MasterController(use_vault=False)
        
        # 4 thresholds: SIMPLE, MODERATE, COMPLEX, EDGE_CASE
        # UNKNOWN is used internally but doesn't have a threshold
        assert len(mc.complexity_thresholds) == 4
        assert TaskComplexity.SIMPLE in mc.complexity_thresholds
        assert TaskComplexity.MODERATE in mc.complexity_thresholds
        assert TaskComplexity.COMPLEX in mc.complexity_thresholds
        assert TaskComplexity.EDGE_CASE in mc.complexity_thresholds
    
    def test_thresholds_are_disjoint(self):
        """Verify threshold ranges don't overlap"""
        mc = MasterController(use_vault=False)
        
        # Extract ranges
        ranges = []
        for complexity in [TaskComplexity.SIMPLE, TaskComplexity.MODERATE, 
                          TaskComplexity.COMPLEX, TaskComplexity.EDGE_CASE]:
            min_val, max_val = mc.complexity_thresholds[complexity]
            ranges.append((min_val, max_val))
        
        # Check coverage: should span 0.0 to 1.0
        assert ranges[0][0] == 0.0
        assert ranges[-1][1] == 1.0
        
        # Check continuity
        for i in range(len(ranges) - 1):
            assert ranges[i][1] == ranges[i + 1][0]


class TestResetScores:
    """Test score reset functionality"""
    
    def test_reset_single_agent_score(self):
        """Test resetting score for single agent"""
        mc = MasterController(use_vault=False)
        
        # Pollute a score
        score = mc.get_agent_score("python")
        score.total_executions = 50
        score.successful_executions = 45
        
        # Reset
        mc.reset_scores("python")
        
        score = mc.get_agent_score("python")
        assert score.total_executions == 0
        assert score.successful_executions == 0
    
    def test_reset_all_scores(self):
        """Test resetting all agent scores"""
        mc = MasterController(use_vault=False)
        
        # Pollute all scores
        for lang in mc.SUPPORTED_LANGUAGES:
            score = mc.get_agent_score(lang)
            score.total_executions = 100
        
        # Reset all
        mc.reset_scores()
        
        # Verify all reset
        for lang in mc.SUPPORTED_LANGUAGES:
            score = mc.get_agent_score(lang)
            assert score.total_executions == 0


class TestDecisionDataStructures:
    """Test RoutingDecision and ExecutionOutcome data structures"""
    
    def test_routing_decision_to_dict(self):
        """Test RoutingDecision serialization"""
        decision = RoutingDecision(
            task_id="test_serial",
            language="python",
            complexity=TaskComplexity.COMPLEX,
            selected_agent="python",
            selected_model=LLMModel.EXPERT,
            confidence=0.88,
            reasoning="test decision",
            estimated_timeout_ms=120000,
            priority="urgent",
        )
        
        d = decision.to_dict()
        assert d["task_id"] == "test_serial"
        assert d["language"] == "python"
        assert d["complexity"] == "complex"
        assert d["selected_model"] == "expert"
        assert d["priority"] == "urgent"
        assert "timestamp" in d
    
    def test_execution_outcome_creation(self):
        """Test ExecutionOutcome creation"""
        decision = RoutingDecision(
            task_id="outcome_test",
            language="go",
            complexity=TaskComplexity.MODERATE,
            selected_agent="go",
            selected_model=LLMModel.CONTROLLER,
            confidence=0.80,
            reasoning="test",
            estimated_timeout_ms=30000,
        )
        
        outcome = ExecutionOutcome(
            task_id="outcome_test",
            language="go",
            routing_decision=decision,
            actual_complexity=TaskComplexity.SIMPLE,  # Was simpler than expected
            execution_time_ms=200.0,
            success=True,
            response_quality=0.97,
        )
        
        assert outcome.task_id == "outcome_test"
        assert outcome.actual_complexity == TaskComplexity.SIMPLE
        assert outcome.success is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
