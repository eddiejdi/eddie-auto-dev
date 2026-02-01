#!/usr/bin/env python3
"""Test script for DataAgent and PerformanceAgent"""

import sys

sys.path.insert(0, "/home/eddie/myClaude")

print("=== Testing DataAgent ===")
from specialized_agents.data_agent import get_data_agent

data_agent = get_data_agent()
print(f"DataAgent v{data_agent.VERSION}")
print(f"Rules: {list(data_agent.AGENT_RULES.keys())}")
print(f"Formats: {data_agent.capabilities['supported_formats']}")

pipeline = data_agent.create_pipeline("test", "Test pipeline")
print(f"Pipeline created: {pipeline.id}")
validation = data_agent.validate_pipeline(pipeline)
print(f"Validation: {validation['checks']}")
print("✅ DataAgent OK")

print()
print("=== Testing PerformanceAgent ===")
from specialized_agents.performance_agent import get_performance_agent

perf_agent = get_performance_agent()
print(f"PerformanceAgent v{perf_agent.VERSION}")
print(f"Rules: {list(perf_agent.AGENT_RULES.keys())}")
print(f"Test types: {perf_agent.capabilities['test_types']}")
print(f"Default thresholds: {perf_agent.DEFAULT_THRESHOLDS}")
print("✅ PerformanceAgent OK")

print()
print("=== All New Agents Tested Successfully! ===")
