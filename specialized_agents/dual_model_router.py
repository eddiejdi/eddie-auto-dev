#!/usr/bin/env python3
"""
Dual Model Router - Controller/Expert Architecture
Similar to Grok 4.1: qwen3:0.6b (Controller) routes tasks to qwen2.5-coder:7b (Expert)

Architecture:
- Controller (GTX 1050, port 11435): qwen3:0.6b - Fast decision-making, route planning
- Expert (RTX 2060, port 11434): qwen2.5-coder:7b - Complex code, reasoning
"""

import json
import httpx
import asyncio
from typing import Literal, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TaskComplexity(Enum):
    """Task complexity levels determine routing"""
    SIMPLE = "simple"      # Controller can handle locally
    MODERATE = "moderate"  # Mixed: controller + expert
    COMPLEX = "complex"    # Expert needed
    UNKNOWN = "unknown"    # Controller needs to decide

@dataclass
class RouterDecision:
    """Decision made by controller about task routing"""
    complexity: TaskComplexity
    agent: Literal["controller", "expert"]
    confidence: float  # 0.0-1.0
    reasoning: str
    model: str
    
@dataclass
class DualModelResponse:
    """Final response with routing metadata"""
    answer: str
    routing_decision: RouterDecision
    controller_time_ms: float
    expert_time_ms: float
    total_time_ms: float

class DualModelRouter:
    """
    Controller-Expert routing system.
    
    qwen3:0.6b (Controller) on port 11435:
    - Analyzes incoming requests
    - Decides complexity level
    - Routes to self or expert
    
    qwen2.5-coder:7b (Expert) on port 11434:
    - Handles complex code/reasoning tasks
    - Called only when needed (saves latency)
    """
    
    def __init__(
        self,
        controller_host: str = "http://192.168.15.2:11435",
        expert_host: str = "http://192.168.15.2:11434",
    ):
        self.controller_host = controller_host
        self.expert_host = expert_host
        self.controller_model = "qwen3:0.6b"
        self.expert_model = "qwen2.5-coder:7b-cline"
        
    async def _call_model(self, host: str, model: str, prompt: str, timeout: int = 120) -> tuple[str, float]:
        """Call an Ollama model and return response + time"""
        import time
        start = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{host}/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": False,
                    }
                )
                response.raise_for_status()
                data = response.json()
                elapsed_ms = (time.time() - start) * 1000
                return data.get("response", ""), elapsed_ms
        except Exception as e:
            logger.error(f"Error calling {model}: {e}")
            return f"[ERROR] {str(e)}", (time.time() - start) * 1000
    
    async def route_request(self, user_prompt: str) -> DualModelResponse:
        """
        Main routing logic. Controller decides if task is simple or routes to expert.
        """
        import time
        total_start = time.time()
        
        # STEP 1: Controller analyzes complexity
        classification_prompt = f"""You are a task router. Analyze this request and decide if it's SIMPLE or COMPLEX.

Request: {user_prompt}

Respond with JSON:
{{"complexity": "simple" or "complex", "reasoning": "brief explanation", "confidence": 0.0-1.0}}

Simple tasks: basic questions, simple logic, current info lookup
Complex tasks: coding, debugging, system design, analysis"""
        
        logger.info(f"🎯 Controller analyzing: {user_prompt[:50]}...")
        controller_response, controller_time = await self._call_model(
            self.controller_host,
            self.controller_model,
            classification_prompt,
            timeout=30
        )
        
        # Parse controller decision
        try:
            decision_json = json.loads(controller_response)
            complexity = TaskComplexity(decision_json.get("complexity", "unknown"))
            reasoning = decision_json.get("reasoning", "")
            confidence = decision_json.get("confidence", 0.5)
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"Failed to parse controller decision: {controller_response}")
            complexity = TaskComplexity.UNKNOWN
            reasoning = controller_response[:100]
            confidence = 0.3
        
        # STEP 2: Route based on complexity
        expert_time = 0.0
        final_answer = ""
        agent_used = "controller"
        
        if complexity in [TaskComplexity.COMPLEX, TaskComplexity.MODERATE]:
            # Task is complex → use Expert
            logger.info(f"📤 Routing to Expert (complexity: {complexity.value})")
            
            expert_prompt = f"""Task: {user_prompt}

Context from controller: {reasoning}

Provide a detailed, comprehensive response."""
            
            final_answer, expert_time = await self._call_model(
                self.expert_host,
                self.expert_model,
                expert_prompt,
                timeout=120
            )
            agent_used = "expert"
            
        else:
            # Task is simple → Controller handles directly
            logger.info(f"✅ Controller handling locally (complexity: {complexity.value})")
            
            response_prompt = f"""Respond directly to this request:

{user_prompt}"""
            
            final_answer, _ = await self._call_model(
                self.controller_host,
                self.controller_model,
                response_prompt,
                timeout=30
            )
            agent_used = "controller"
        
        total_time = (time.time() - total_start) * 1000
        
        # Build response with routing metadata
        return DualModelResponse(
            answer=final_answer,
            routing_decision=RouterDecision(
                complexity=complexity,
                agent=agent_used,
                confidence=confidence,
                reasoning=reasoning,
                model=self.expert_model if agent_used == "expert" else self.controller_model
            ),
            controller_time_ms=controller_time,
            expert_time_ms=expert_time,
            total_time_ms=total_time
        )

    def format_response(self, response: DualModelResponse) -> str:
        """Pretty-print response with routing metadata"""
        return f"""
╔════════════════════════════════════════════════════════════════╗
║                    DUAL MODEL ROUTER RESPONSE                  ║
╚════════════════════════════════════════════════════════════════╝

📋 ROUTING DECISION:
  Agent Used:     {response.routing_decision.agent.upper()}
  Complexity:     {response.routing_decision.complexity.value.upper()}
  Model:          {response.routing_decision.model}
  Confidence:     {response.routing_decision.confidence:.1%}
  Reasoning:      {response.routing_decision.reasoning}

⏱️  TIMING:
  Controller:     {response.controller_time_ms:.0f}ms
  Expert:         {response.expert_time_ms:.0f}ms
  Total:          {response.total_time_ms:.0f}ms

📝 RESPONSE:
{response.answer}

╔════════════════════════════════════════════════════════════════╗
"""

async def main():
    """Example usage"""
    router = DualModelRouter()
    
    # Test cases
    test_prompts = [
        "What's 2+2?",  # Simple
        "Write a Python function to merge two sorted arrays",  # Complex
        "Explain REST APIs",  # Moderate
    ]
    
    for prompt in test_prompts:
        print(f"\n🔄 Processing: {prompt}")
        response = await router.route_request(prompt)
        print(router.format_response(response))
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
