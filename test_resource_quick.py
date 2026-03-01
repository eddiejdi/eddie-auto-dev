#!/usr/bin/env python3
"""Quick test to validate resource_manager logic without pytest overhead"""

import sys
from datetime import datetime, timedelta

# Direct imports to avoid big dependencies
sys.path.insert(0, '/home/edenilson/eddie-auto-dev')

from specialized_agents.resource_manager import (
    ResourceManager,
    ResourceMetrics,
    ResourceStatus,
    TaskPriority,
)

def test_exhausted_status():
    """Test that metrics with 100% load returns EXHAUSTED"""
    metrics = ResourceMetrics(
        language="python",
        cpu_percent=100.0,
        memory_percent=100.0,
        gpu_utilization=100.0,
        active_tasks=50,
    )
    print(f"✓ Metrics: cpu=100%, mem=100%, gpu=100%, tasks=50")
    print(f"  overall_load = {metrics.overall_load:.4f}")
    print(f"  status = {metrics.status}")
    assert metrics.status == ResourceStatus.EXHAUSTED, f"Expected EXHAUSTED, got {metrics.status}"
    print(f"  ✓ Status is EXHAUSTED")
    return True

def test_critical_status():
    """Test that metrics between 0.7-0.95 load return CRITICAL"""
    metrics = ResourceMetrics(
        language="python",
        cpu_percent=95.0,
        memory_percent=80.0,
        gpu_utilization=70.0,
        active_tasks=3,
    )
    print(f"✓ Metrics: cpu=95%, mem=80%, gpu=70%, tasks=3")
    print(f"  overall_load = {metrics.overall_load:.4f}")
    print(f"  status = {metrics.status}")
    assert metrics.status == ResourceStatus.CRITICAL, f"Expected CRITICAL, got {metrics.status}"
    print(f"  ✓ Status is CRITICAL")
    return True

def test_agent_selection():
    """Test that lighter loaded agent is selected"""
    rm = ResourceManager(["python", "go"])
    
    # Python: heavy (load ~0.65)
    python_metrics = ResourceMetrics(
        language="python",
        cpu_percent=80.0,
        memory_percent=80.0,
        gpu_utilization=40.0,
        active_tasks=3,
    )
    rm.update_metrics("python", python_metrics)
    
    # Go: light (load ~0.15)
    go_metrics = ResourceMetrics(
        language="go",
        cpu_percent=20.0,
        memory_percent=10.0,
        gpu_utilization=10.0,
        active_tasks=0,
    )
    rm.update_metrics("go", go_metrics)
    
    best_lang, score = rm.select_best_agent()
    print(f"✓ Agent Selection Test")
    print(f"  Python load: {python_metrics.overall_load:.4f}")
    print(f"  Go load: {go_metrics.overall_load:.4f}")
    print(f"  Selected: {best_lang} with score {score:.4f}")
    assert best_lang == "go", f"Expected 'go', got '{best_lang}'"
    print(f"  ✓ Go selected (lighter load)")
    return True

def test_recency():
    """Test LRU selection based on recency"""
    rm = ResourceManager(["python", "javascript"])
    
    # Both with equal load
    metrics = ResourceMetrics(
        language="python",
        cpu_percent=50.0,
        memory_percent=50.0,
        gpu_utilization=50.0,
    )
    rm.update_metrics("python", metrics)
    rm.update_metrics("javascript", metrics)
    
    # Python: used now
    rm.agent_last_execution["python"] = datetime.now()
    # JavaScript: not used for 1 hour
    rm.agent_last_execution["javascript"] = datetime.now() - timedelta(hours=1)
    
    best_lang, score = rm.select_best_agent()
    print(f"✓ Recency (LRU) Test")
    print(f"  Python: used now")
    print(f"  JavaScript: used 1 hour ago")
    print(f"  Selected: {best_lang} with score {score:.4f}")
    assert best_lang == "javascript", f"Expected 'javascript', got '{best_lang}'"
    print(f"  ✓ JavaScript selected (not used recently)")
    return True

def test_task_tracking():
    """Test that task tracking works"""
    rm = ResourceManager(["python"])
    
    # Allocate tasks
    success, reason, task_id = rm.allocate_task("task_1", "python")
    assert success and task_id, f"Failed to allocate task_1"
    
    success, reason, task_id2 = rm.allocate_task("task_2", "python")
    assert success and task_id2, f"Failed to allocate task_2"
    
    print(f"✓ Allocated 2 tasks")
    
    # Start first task
    rm.start_task("task_1")
    
    # Get summary
    summary = rm.get_agent_summary("python")
    print(f"  Active tasks: {summary['active_tasks']}")
    print(f"  Queued tasks: {summary['queued_tasks']}")
    
    assert summary['active_tasks'] == 1, f"Expected 1 active, got {summary['active_tasks']}"
    assert summary['queued_tasks'] == 1, f"Expected 1 queued, got {summary['queued_tasks']}"
    print(f"  ✓ Task tracking working")
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("Resource Manager Quick Tests")
    print("=" * 60)
    
    tests = [
        ("Exhausted Status", test_exhausted_status),
        ("Critical Status", test_critical_status),
        ("Agent Selection (Load)", test_agent_selection),
        ("Recency (LRU)", test_recency),
        ("Task Tracking", test_task_tracking),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_fn in tests:
        print(f"\n{name}:")
        try:
            if test_fn():
                passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {str(e)}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    sys.exit(0 if failed == 0 else 1)
