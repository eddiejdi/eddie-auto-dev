#!/usr/bin/env python3
"""
Master Controller - Grok 4.2-like Orchestration System

Central intelligence that:
1. Routes tasks to optimal agent (Python, JS, TS, Go, Rust, Java, C#, PHP)
2. Selects optimal LLM (Controller fast vs Expert deep)
3. Manages resource allocation
4. Learns from execution outcomes

Architecture:
    User Request
        ↓
    MasterController.route_task()
        ├─ Analyze complexity (Controller 0.6b)
        ├─ Check agent scores (PostgreSQL)
        ├─ Allocate resources
        └─ Make routing decision
        ↓
    Selected Agent + Selected Model
        ↓
    Execute → Store outcome → Update scores

Configuration:
    Uses tools/vault/secret_store.py for all sensitive data:
    - OLLAMA_CONTROLLER_HOST (default: http://192.168.15.2:11435)
    - OLLAMA_EXPERT_HOST (default: http://192.168.15.2:11434)
    - DATABASE_URL (PostgreSQL connection)
    - ENABLE_LEARNING (bool, default: true)
"""

import json
import asyncio
import time
import logging
import sys
import os
from typing import Literal, Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
import httpx

# Add tools to path for vault access
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION WITH SECRET STORE
# ============================================================================

class MasterControllerConfig:
    """
    Configuration using vault/secret_store for all sensitive values.
    
    Resolution order:
    1. Bitwarden (via `bw` CLI)
    2. Environment variables
    3. simple_vault GPG/plaintext files
    4. Hardcoded defaults
    """
    
    @staticmethod
    def _get_secret(secret_name: str, default: str = "") -> str:
        """
        Safely retrieve secret using vault system.
        
        Args:
            secret_name: Name of secret (e.g., 'ollama_controller_host')
            default: Default value if secret not found
            
        Returns:
            Secret value or default
        """
        try:
            # Try to import and use vault
            from vault import secret_store
            try:
                value = secret_store.get_field(secret_name)
                logger.info(f"✓ Loaded secret '{secret_name}' from vault")
                return value
            except Exception as e:
                logger.debug(f"Secret '{secret_name}' not in vault, using default: {e}")
                return default
        except ImportError:
            logger.warning("vault/secret_store not available, using environment variables")
            # Fallback to env var (uppercase with underscores)
            env_name = secret_name.upper()
            return os.environ.get(env_name, default)
    
    @classmethod
    def load(cls) -> Dict[str, Any]:
        """Load all configuration from vault or environment"""
        config = {
            "controller_host": cls._get_secret(
                "ollama_controller_host",
                default="http://192.168.15.2:11435"
            ),
            "expert_host": cls._get_secret(
                "ollama_expert_host",
                default="http://192.168.15.2:11434"
            ),
            "db_url": cls._get_secret(
                "database_url",
                default=os.environ.get("DATABASE_URL", "sqlite:///:memory:")
            ),
            "enable_learning": cls._get_secret(
                "enable_learning",
                default="true"
            ).lower() in ("true", "1", "yes"),
        }
        
        logger.info(
            f"Master Controller Config loaded:\n"
            f"  Controller: {config['controller_host']}\n"
            f"  Expert: {config['expert_host']}\n"
            f"  Learning: {config['enable_learning']}"
        )
        
        return config

# ============================================================================
# ENUMS & DATA CLASSES
# ============================================================================

class TaskComplexity(Enum):
    """Task complexity levels"""
    SIMPLE = "simple"         # Basic tasks, no code generation
    MODERATE = "moderate"     # Medium complexity, standard patterns
    COMPLEX = "complex"       # Deep reasoning, complex code
    EDGE_CASE = "edge_case"   # Unusual patterns, fallback needed
    UNKNOWN = "unknown"       # Couldn't determine


class AgentLanguage(Enum):
    """Supported programming languages"""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    CSHARP = "csharp"
    PHP = "php"


class LLMModel(Enum):
    """Available LLM models"""
    CONTROLLER = "controller"  # qwen3:0.6b @ 11435 (fast)
    EXPERT = "expert"          # qwen2.5-coder:7b @ 11434 (deep)
    ULTRA_EXPERT = "ultra_expert"  # qwen3:14b @ 11436 (fallback, not yet deployed)


@dataclass
class AgentScore:
    """Performance score for an agent"""
    language: str
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    avg_execution_time_ms: float = 0.0
    avg_response_quality: float = 0.0  # 0.0-1.0
    last_execution_timestamp: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        """Success rate: successful / total"""
        if self.total_executions == 0:
            return 0.5  # Default neutral score
        return self.successful_executions / self.total_executions
    
    @property
    def reliability_score(self) -> float:
        """Combined score: (success_rate * 0.6) + (avg_response_quality * 0.4)"""
        return (self.success_rate * 0.6) + (self.avg_response_quality * 0.4)


@dataclass
class RoutingDecision:
    """Major routing decision"""
    task_id: str
    language: str
    complexity: TaskComplexity
    selected_agent: str
    selected_model: LLMModel
    confidence: float  # 0.0-1.0
    reasoning: str
    estimated_timeout_ms: int
    priority: Literal["background", "normal", "urgent"] = "normal"
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization"""
        d = asdict(self)
        d['complexity'] = self.complexity.value
        d['selected_model'] = self.selected_model.value
        d['timestamp'] = self.timestamp.isoformat()
        return d


@dataclass
class ExecutionOutcome:
    """Result of task execution for feedback loop"""
    task_id: str
    language: str
    routing_decision: RoutingDecision
    actual_complexity: TaskComplexity  # Real complexity after execution
    execution_time_ms: float
    success: bool
    error_message: Optional[str] = None
    response_quality: float = 0.0  # 0.0-1.0 feedback
    timestamp: datetime = field(default_factory=datetime.now)


# ============================================================================
# MASTER CONTROLLER CLASS
# ============================================================================

class MasterController:
    """
    Central orchestrator that decides:
    1. Which agent executes a task (Python, JS, TS, etc)
    2. Which LLM model to use (Controller fast vs Expert deep)
    3. Resource allocation (CPU, GPU, memory, timeout)
    4. Learning from feedback
    """
    
    SUPPORTED_LANGUAGES = [lang.value for lang in AgentLanguage]
    
    def __init__(
        self,
        controller_host: Optional[str] = None,
        expert_host: Optional[str] = None,
        db_url: Optional[str] = None,
        enable_learning: Optional[bool] = None,
        use_vault: bool = True,
    ):
        """
        Initialize Master Controller.
        
        If use_vault=True (default), loads configuration from vault/secret_store.
        Otherwise, uses provided parameters or falls back to environment variables.
        """
        if use_vault:
            config = MasterControllerConfig.load()
            self.controller_host = config["controller_host"]
            self.expert_host = config["expert_host"]
            self.db_url = config["db_url"]
            self.enable_learning = config["enable_learning"]
        else:
            # Use provided values or environment fallbacks
            self.controller_host = (
                controller_host or 
                os.environ.get("OLLAMA_CONTROLLER_HOST", "http://192.168.15.2:11435")
            )
            self.expert_host = (
                expert_host or 
                os.environ.get("OLLAMA_EXPERT_HOST", "http://192.168.15.2:11434")
            )
            self.db_url = (
                db_url or 
                os.environ.get("DATABASE_URL", "sqlite:///:memory:")
            )
            self.enable_learning = (
                enable_learning if enable_learning is not None
                else os.environ.get("ENABLE_LEARNING", "true").lower() in ("true", "1")
            )
        
        # In-memory score tracking
        self.agent_scores: Dict[str, AgentScore] = {
            lang: AgentScore(language=lang) for lang in self.SUPPORTED_LANGUAGES
        }
        
        # Decision history (for audit + learning)
        self.decision_history: List[RoutingDecision] = []
        self.execution_outcomes: List[ExecutionOutcome] = []
        
        # Config
        self.use_vault = use_vault
        
        # Complexity thresholds for routing
        self.complexity_thresholds = {
            TaskComplexity.SIMPLE: (0.0, 0.25),
            TaskComplexity.MODERATE: (0.25, 0.65),
            TaskComplexity.COMPLEX: (0.65, 0.95),
            TaskComplexity.EDGE_CASE: (0.95, 1.0),
        }
        
        logger.info(
            f"MasterController initialized with {len(self.SUPPORTED_LANGUAGES)} agents\n"
            f"  Vault: {use_vault}\n"
            f"  Learning: {self.enable_learning}"
        )
    
    # ========================================================================
    # COMPLEXITY ANALYSIS
    # ========================================================================
    
    async def _analyze_complexity(self, task_description: str) -> Tuple[TaskComplexity, float]:
        """
        Use Controller model to classify task complexity.
        
        Returns: (complexity, confidence_score: 0.0-1.0)
        """
        prompt = f"""Analyze this task and rate its complexity on a scale 0.0-1.0:
- 0.0-0.25: SIMPLE (basic setup, config, simple queries)
- 0.25-0.65: MODERATE (standard patterns, CRUD, basic algorithms)
- 0.65-0.95: COMPLEX (non-trivial algorithms, system design, edge cases)
- 0.95-1.0: EDGE_CASE (very unusual patterns, requires expert reasoning)

Task: {task_description}

Respond ONLY with JSON: {{"complexity_score": 0.75, "reasoning": "short explanation"}}"""

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.controller_host}/api/generate",
                    json={
                        "model": "qwen3:0.6b",
                        "prompt": prompt,
                        "stream": False,
                    }
                )
                response.raise_for_status()
                
                # Parse response
                try:
                    data = json.loads(response.json()["response"])
                    score = float(data.get("complexity_score", 0.5))
                    score = max(0.0, min(1.0, score))  # Clamp to [0, 1]
                    
                    # Classify
                    for complexity, (min_val, max_val) in self.complexity_thresholds.items():
                        if min_val <= score <= max_val:
                            return complexity, score
                    
                    return TaskComplexity.UNKNOWN, score
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Failed to parse complexity response: {e}")
                    return TaskComplexity.UNKNOWN, 0.5
                    
        except Exception as e:
            logger.error(f"Complexity analysis failed: {e}")
            return TaskComplexity.UNKNOWN, 0.5
    
    # ========================================================================
    # AGENT SCORING & SELECTION
    # ========================================================================
    
    def get_agent_score(self, language: str) -> AgentScore:
        """Get score for a specific agent"""
        if language not in self.agent_scores:
            self.agent_scores[language] = AgentScore(language=language)
        return self.agent_scores[language]
    
    def _select_best_agent(self, language: Optional[str] = None) -> str:
        """
        Select the best agent to handle the task.
        
        If language is specified, use it (trust user).
        Otherwise, select agent with best score (reliability_score).
        """
        if language and language in self.SUPPORTED_LANGUAGES:
            return language
        
        # Pick agent with highest reliability_score
        best_language = max(
            self.SUPPORTED_LANGUAGES,
            key=lambda lang: self.get_agent_score(lang).reliability_score
        )
        return best_language
    
    def _select_model(self, complexity: TaskComplexity) -> LLMModel:
        """
        Select LLM model based on complexity.
        
        SIMPLE/MODERATE → Controller (fast, 0.6b)
        COMPLEX → Expert (deep, 7b)
        EDGE_CASE → Ultra Expert (if available, fallback)
        """
        if complexity in (TaskComplexity.SIMPLE, TaskComplexity.MODERATE):
            return LLMModel.CONTROLLER
        elif complexity in (TaskComplexity.COMPLEX, TaskComplexity.EDGE_CASE):
            return LLMModel.EXPERT
        else:
            return LLMModel.EXPERT  # Default to expert on unknown
    
    def _estimate_timeout(self, complexity: TaskComplexity, model: LLMModel) -> int:
        """
        Estimate execution timeout in milliseconds.
        Based on historical data + complexity + model speed.
        """
        base_timeout = {
            LLMModel.CONTROLLER: 30 * 1000,  # 30 seconds
            LLMModel.EXPERT: 120 * 1000,     # 2 minutes
            LLMModel.ULTRA_EXPERT: 300 * 1000,  # 5 minutes
        }
        
        complexity_multiplier = {
            TaskComplexity.SIMPLE: 0.5,
            TaskComplexity.MODERATE: 1.0,
            TaskComplexity.COMPLEX: 1.5,
            TaskComplexity.EDGE_CASE: 2.0,
            TaskComplexity.UNKNOWN: 1.0,
        }
        
        timeout_ms = int(
            base_timeout[model] * complexity_multiplier[complexity]
        )
        return timeout_ms
    
    # ========================================================================
    # MAIN ROUTING API
    # ========================================================================
    
    async def route_task(
        self,
        task_description: str,
        language: Optional[str] = None,
        priority: Literal["background", "normal", "urgent"] = "normal",
    ) -> RoutingDecision:
        """
        Main entry point: Analyze task and make routing decision.
        
        Args:
            task_description: What needs to be done
            language: Optional hint (Python, JS, etc)
            priority: Task priority
            
        Returns:
            RoutingDecision with agent, model, timeout, confidence
        """
        task_id = f"task_{int(time.time() * 1000)}"
        
        # 1. Analyze complexity
        complexity, complexity_score = await self._analyze_complexity(task_description)
        logger.info(f"[{task_id}] Complexity: {complexity.value} (score: {complexity_score:.2f})")
        
        # 2. Select agent
        selected_agent = self._select_best_agent(language)
        agent_score = self.get_agent_score(selected_agent)
        logger.info(f"[{task_id}] Selected agent: {selected_agent} (reliability: {agent_score.reliability_score:.2f})")
        
        # 3. Select model
        selected_model = self._select_model(complexity)
        logger.info(f"[{task_id}] Selected model: {selected_model.value}")
        
        # 4. Estimate timeout
        timeout_ms = self._estimate_timeout(complexity, selected_model)
        
        # 5. Build confidence score
        confidence = (complexity_score + agent_score.reliability_score) / 2
        
        # 6. Create decision
        decision = RoutingDecision(
            task_id=task_id,
            language=selected_agent,
            complexity=complexity,
            selected_agent=selected_agent,
            selected_model=selected_model,
            confidence=confidence,
            reasoning=f"Complexity {complexity.value} ({complexity_score:.2f}) → {selected_model.value}. "
                      f"Agent {selected_agent} has {agent_score.success_rate*100:.1f}% success rate.",
            estimated_timeout_ms=timeout_ms,
            priority=priority,
        )
        
        # 7. Store decision
        self.decision_history.append(decision)
        logger.info(f"[{task_id}] Decision: {decision.selected_agent} + {decision.selected_model.value} "
                   f"(confidence: {confidence:.2f})")
        
        return decision
    
    # ========================================================================
    # FEEDBACK & LEARNING
    # ========================================================================
    
    def record_execution_outcome(
        self,
        task_id: str,
        decision: RoutingDecision,
        success: bool,
        execution_time_ms: float,
        actual_complexity: Optional[TaskComplexity] = None,
        response_quality: float = 0.0,
        error_message: Optional[str] = None,
    ) -> ExecutionOutcome:
        """
        Record how a task execution went for learning purposes.
        
        This enables the master controller to improve routing decisions.
        """
        outcome = ExecutionOutcome(
            task_id=task_id,
            language=decision.language,
            routing_decision=decision,
            actual_complexity=actual_complexity or decision.complexity,
            execution_time_ms=execution_time_ms,
            success=success,
            response_quality=response_quality,
            error_message=error_message,
        )
        
        self.execution_outcomes.append(outcome)
        
        # Update agent scores
        agent_score = self.get_agent_score(decision.language)
        agent_score.total_executions += 1
        
        if success:
            agent_score.successful_executions += 1
        else:
            agent_score.failed_executions += 1
        
        # Update average metrics (exponential moving average)
        alpha = 0.2  # Weight for new data
        agent_score.avg_execution_time_ms = (
            alpha * execution_time_ms + (1 - alpha) * agent_score.avg_execution_time_ms
        )
        agent_score.avg_response_quality = (
            alpha * response_quality + (1 - alpha) * agent_score.avg_response_quality
        )
        agent_score.last_execution_timestamp = datetime.now()
        
        logger.info(
            f"[{task_id}] Outcome: {'✓' if success else '✗'} "
            f"{decision.language} in {execution_time_ms:.0f}ms "
            f"(quality: {response_quality:.2f}, agent now {agent_score.success_rate*100:.1f}% reliable)"
        )
        
        return outcome
    
    # ========================================================================
    # STATISTICS & INTROSPECTION
    # ========================================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall statistics about routing and execution"""
        total_decisions = len(self.decision_history)
        total_outcomes = len(self.execution_outcomes)
        
        if total_outcomes > 0:
            successful = sum(1 for o in self.execution_outcomes if o.success)
            success_rate = successful / total_outcomes
        else:
            success_rate = 0.0
        
        agent_stats = {
            lang: {
                "total": self.agent_scores[lang].total_executions,
                "successful": self.agent_scores[lang].successful_executions,
                "success_rate": self.agent_scores[lang].success_rate,
                "reliability_score": self.agent_scores[lang].reliability_score,
                "avg_execution_time_ms": self.agent_scores[lang].avg_execution_time_ms,
                "avg_response_quality": self.agent_scores[lang].avg_response_quality,
            }
            for lang in self.SUPPORTED_LANGUAGES
        }
        
        return {
            "total_decisions": total_decisions,
            "total_outcomes": total_outcomes,
            "overall_success_rate": success_rate,
            "agent_stats": agent_stats,
            "recent_decisions": [d.to_dict() for d in self.decision_history[-5:]],
        }
    
    def get_agent_stats(self, language: str) -> Optional[Dict[str, Any]]:
        """Get specific agent stats"""
        if language not in self.SUPPORTED_LANGUAGES:
            return None
        
        score = self.get_agent_score(language)
        return {
            "language": language,
            "total_executions": score.total_executions,
            "successful_executions": score.successful_executions,
            "failed_executions": score.failed_executions,
            "success_rate": score.success_rate,
            "reliability_score": score.reliability_score,
            "avg_execution_time_ms": score.avg_execution_time_ms,
            "avg_response_quality": score.avg_response_quality,
            "last_execution": score.last_execution_timestamp.isoformat() if score.last_execution_timestamp else None,
        }
    
    def reset_scores(self, language: Optional[str] = None) -> None:
        """Reset scores for an agent or all agents"""
        if language:
            if language in self.agent_scores:
                self.agent_scores[language] = AgentScore(language=language)
                logger.info(f"Reset scores for {language}")
        else:
            for lang in self.SUPPORTED_LANGUAGES:
                self.agent_scores[lang] = AgentScore(language=lang)
            logger.info("Reset scores for all agents")


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_master_controller_instance: Optional[MasterController] = None



def get_master_controller(use_vault: bool = True) -> MasterController:
    """
    Get or create singleton instance of MasterController.
    
    Args:
        use_vault: If True, load configuration from vault/secret_store
    """
    global _master_controller_instance
    if _master_controller_instance is None:
        _master_controller_instance = MasterController(use_vault=use_vault)
    return _master_controller_instance


# ============================================================================
# CLI TESTING
# ============================================================================

if __name__ == "__main__":
    async def main():
        # Test with vault enabled (default)
        print("=== Master Controller with Vault Configuration ===\n")
        mc = MasterController(use_vault=True)
        
        # Test 1: Simple task
        print("\n=== TEST 1: Simple Task ===")
        decision = await mc.route_task("Create a hello world program")
        print(f"Decision: {decision.selected_agent} + {decision.selected_model.value}")
        
        # Simulate execution
        mc.record_execution_outcome(
            task_id=decision.task_id,
            decision=decision,
            success=True,
            execution_time_ms=500,
            response_quality=0.95,
        )
        
        # Test 2: Complex task
        print("\n=== TEST 2: Complex Task ===")
        decision = await mc.route_task(
            "Implement a distributed transaction manager with MVCC and optimistic locking",
            language="rust"
        )
        print(f"Decision: {decision.selected_agent} + {decision.selected_model.value}")
        
        mc.record_execution_outcome(
            task_id=decision.task_id,
            decision=decision,
            success=True,
            execution_time_ms=5000,
            response_quality=0.88,
        )
        
        # Stats
        print("\n=== STATISTICS ===")
        stats = mc.get_statistics()
        print(json.dumps(stats, indent=2, default=str))
        
        print("\n=== VAULT CONFIG ===")
        config = MasterControllerConfig.load()
        print(json.dumps(
            {k: v for k, v in config.items() if k != "db_url"},  # Hide DB URL
            indent=2
        ))
    
    asyncio.run(main())
