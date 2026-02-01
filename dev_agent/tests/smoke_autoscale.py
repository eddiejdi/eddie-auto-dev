#!/usr/bin/env python3
import asyncio
import os
import sys
from pathlib import Path

# Adicionar path do projeto
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dev_agent.agent import DevAgent

# Garantir limites
os.environ.setdefault("SQUAD_MIN", "1")
os.environ.setdefault("SQUAD_MAX", "4")


async def fake_generate_and_fix(description, language, generate_tests=True):
    print(f"[fake] start: {description}")
    # simulate some work
    await asyncio.sleep(3)

    class R:
        pass

    r = R()
    r.final_code = "# result"
    r.iterations = 1
    r.errors = []
    r.success = True
    print(f"[fake] done: {description}")
    return r


async def monitor(agent: DevAgent, duration: int = 20):
    for _ in range(duration):
        cap = (
            agent._squad_manager.get_current_capacity()
            if getattr(agent, "_squad_manager", None)
            else agent._squad_capacity
        )
        print(f"[monitor] capacity={cap} active={getattr(agent, '_squad_active', 0)}")
        await asyncio.sleep(1)


async def main():
    agent = DevAgent()

    # monkeypatch auto_fixer to avoid external dependencies
    agent.auto_fixer.generate_and_fix = fake_generate_and_fix

    # enable autoscale (starts manager if loop running)
    agent.enable_squad_autoscale()

    # small delay to let manager start
    await asyncio.sleep(0.5)

    # spawn several develop tasks to stress the squad
    jobs = 8
    descriptions = [f"task-{i}" for i in range(jobs)]
    tasks = [asyncio.create_task(agent.develop(d)) for d in descriptions]

    monitor_task = asyncio.create_task(monitor(agent, duration=max(10, jobs)))

    results = await asyncio.gather(*tasks)
    await monitor_task

    print("All results: ", [(r["task_id"], r["status"]) for r in results])


if __name__ == "__main__":
    asyncio.run(main())
