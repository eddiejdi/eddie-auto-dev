"""
Agente Principal de Desenvolvimento
"""

import asyncio
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from enum import Enum

from .config import LLM_CONFIG, SUPPORTED_TECHNOLOGIES
from .llm_client import LLMClient, CodeGenerator, ConversationManager
from .docker_manager import DockerManager
from .test_runner import TestRunner, AutoFixer


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    TESTING = "testing"
    FIXING = "fixing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    id: str
    description: str
    language: str = "python"
    status: TaskStatus = TaskStatus.PENDING
    code: str = ""
    tests: str = ""
    errors: List[str] = field(default_factory=list)
    iterations: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


@dataclass
class ProjectSpec:
    name: str
    description: str
    language: str = "python"
    technologies: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)


class DevAgent:
    def __init__(self, llm_url: str = None, model: str = None):
        llm_url = llm_url or LLM_CONFIG["base_url"]
        model = model or LLM_CONFIG["model"]

        self.llm = LLMClient(llm_url, model)
        self.docker = DockerManager()
        self.code_gen = CodeGenerator(self.llm)
        self.test_runner = TestRunner(self.docker)
        self.auto_fixer = AutoFixer(self.llm, self.docker)
        self.conversation = ConversationManager(self.llm)
        self.tasks: Dict[str, Task] = {}
        self._task_counter = 0
        # Squad/autoscale integration (optional)
        try:
            from .squad_manager import SquadManager
        except Exception:
            SquadManager = None

        import os

        self.squad_min = int(os.getenv("SQUAD_MIN", 1))
        self.squad_max = int(os.getenv("SQUAD_MAX", 4))
        self._squad_capacity = self.squad_min
        self._squad_active = 0
        self._squad_semaphore = asyncio.Semaphore(self._squad_capacity)
        self._squad_manager = (
            SquadManager(
                self.set_squad_capacity,
                min_capacity=self.squad_min,
                max_capacity=self.squad_max,
            )
            if SquadManager
            else None
        )

        # try auto-start if event loop is running
        try:
            loop = asyncio.get_running_loop()
            if self._squad_manager:
                loop.create_task(self._squad_manager.start())
        except RuntimeError:
            # no running loop; caller can start via enable_squad_autoscale()
            pass

    async def check_health(self) -> Dict[str, Any]:
        llm_ok = await self.llm.check_connection()
        docker_ok = self.docker.is_docker_available()
        models = await self.llm.list_models() if llm_ok else []

        return {
            "llm_connected": llm_ok,
            "docker_available": docker_ok,
            "available_models": models,
            "current_model": self.llm.model,
            "status": "healthy" if (llm_ok and docker_ok) else "degraded",
        }

    def create_task(self, description: str, language: str = "python") -> Task:
        self._task_counter += 1
        task_id = f"task_{self._task_counter}"
        task = Task(id=task_id, description=description, language=language)
        self.tasks[task_id] = task
        return task

    async def execute_task(self, task_id: str) -> Task:
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} nao encontrada")
        # acquire a squad slot before executing
        await self._acquire_squad_slot()

        task.status = TaskStatus.IN_PROGRESS

        try:
            result = await self.auto_fixer.generate_and_fix(
                task.description, task.language, generate_tests=True
            )
        finally:
            await self._release_squad_slot()

        task.code = result.final_code
        task.iterations = result.iterations
        task.errors = result.errors

        if result.success:
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
        else:
            task.status = TaskStatus.FAILED

        return task

    async def develop(
        self, description: str, language: str = "python"
    ) -> Dict[str, Any]:
        task = self.create_task(description, language)
        completed_task = await self.execute_task(task.id)

        return {
            "task_id": completed_task.id,
            "status": completed_task.status.value,
            "code": completed_task.code,
            "iterations": completed_task.iterations,
            "errors": completed_task.errors,
            "success": completed_task.status == TaskStatus.COMPLETED,
        }

    async def quick_run(self, code: str, language: str = "python") -> Dict[str, Any]:
        result = self.test_runner.run_code(code, language)

        return {
            "success": result.success,
            "output": result.stdout,
            "errors": result.stderr,
            "exit_code": result.exit_code,
        }

    async def fix_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        result = await self.auto_fixer.fix_until_works(code, language)

        return {
            "success": result.success,
            "original_code": result.original_code,
            "fixed_code": result.final_code,
            "iterations": result.iterations,
            "errors": result.errors,
        }

    async def chat(self, message: str) -> str:
        return await self.conversation.send(message)

    async def create_project(self, spec: ProjectSpec) -> Dict[str, Any]:
        prompt = f"""Crie a estrutura de um projeto {spec.language} chamado "{spec.name}".
Descricao: {spec.description}
Tecnologias: {", ".join(spec.technologies)}
Requisitos: {", ".join(spec.requirements)}

Retorne a estrutura de arquivos e o codigo principal."""

        response = await self.llm.generate(prompt)

        if response.success:
            return {
                "success": True,
                "project_name": spec.name,
                "structure": response.content,
            }
        return {"success": False, "error": response.error}

    def get_supported_technologies(self) -> List[str]:
        return list(SUPPORTED_TECHNOLOGIES.keys())

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        task = self.tasks.get(task_id)
        if not task:
            return None
        return {
            "id": task.id,
            "description": task.description,
            "status": task.status.value,
            "iterations": task.iterations,
            "has_code": bool(task.code),
        }

    async def _acquire_squad_slot(self):
        if not hasattr(self, "_squad_semaphore") or self._squad_semaphore is None:
            return
        await self._squad_semaphore.acquire()
        self._squad_active += 1

    async def _release_squad_slot(self):
        if not hasattr(self, "_squad_semaphore") or self._squad_semaphore is None:
            return
        try:
            self._squad_semaphore.release()
        except ValueError:
            # semaphore already at max
            pass
        self._squad_active = max(0, self._squad_active - 1)

    async def set_squad_capacity(self, n: int):
        # adjust semaphore to have 'n' permits
        n = max(1, int(n))
        self._squad_capacity = n
        if not hasattr(self, "_squad_semaphore") or self._squad_semaphore is None:
            self._squad_semaphore = asyncio.Semaphore(n)
            return

        # recreate semaphore preserving currently active slots
        current_active = self._squad_active
        new_permits = max(0, n - current_active)
        self._squad_semaphore = asyncio.Semaphore(new_permits)

    def enable_squad_autoscale(self):
        if self._squad_manager:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._squad_manager.start())
            except RuntimeError:
                # caller should start the loop
                pass

    def disable_squad_autoscale(self):
        if self._squad_manager:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._squad_manager.stop())
            except RuntimeError:
                pass

    def cleanup(self):
        self.docker.cleanup_all()
        self.conversation.clear_history()
