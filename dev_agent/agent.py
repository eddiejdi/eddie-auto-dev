"""
Agente Principal de Desenvolvimento
"""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class TaskStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    testing = "testing"
    fixing = "fixing"
    completed = "completed"
    failed = "failed"


@dataclass
class Task:
    description: str
    language: str = "python"
    status: TaskStatus = TaskStatus.pending
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
    def __init__(self, llm_url: str, model: str):
        self.llm_url = llm_url
        self.model = model
        self._tasks: Dict[str, Task] = {}
        self._counter = 0
        SQUAD_MIN = int(os.getenv("SQUAD_MIN", "1"))
        SQUAD_MAX = int(os.getenv("SQUAD_MAX", "10"))
        import threading
        self._squad_semaphore = threading.Semaphore(SQUAD_MAX)

        try:
            from dev_agent.llm_client import LLMClient, CodeGenerator
            self.llm = LLMClient(base_url=llm_url, model=model)
            self.codegen = CodeGenerator(self.llm)
        except Exception:
            self.llm = None
            self.codegen = None

        try:
            from dev_agent.docker_manager import DockerManager
            self.docker = DockerManager()
        except Exception:
            self.docker = None

        try:
            from dev_agent.test_runner import TestRunner, AutoFixer
            self.test_runner = TestRunner(self.docker) if self.docker else None
            self.autofixer = AutoFixer(self.llm, self.docker) if (self.llm and self.docker) else None
        except Exception:
            self.test_runner = None
            self.autofixer = None

    def check_health(self) -> str:
        if self.llm and self.llm.check_connection():
            return "healthy"
        return "degraded"

    def create_task(self, description: str, language: str = "python") -> str:
        self._counter += 1
        task_id = f"task_{self._counter}"
        self._tasks[task_id] = Task(description=description, language=language)
        return task_id

    def execute_task(self, task_id: str) -> Dict[str, Any]:
        task = self._tasks.get(task_id)
        if not task:
            return {"success": False, "error": f"Task {task_id} nao encontrada"}
        task.status = TaskStatus.in_progress
        try:
            if self.codegen:
                result = self.codegen.generate_code(task.description, task.language)
                task.code = result.get("code", "")
                if result.get("success"):
                    task.status = TaskStatus.completed
                    task.completed_at = datetime.now()
                    return {"success": True, "task_id": task_id, "code": task.code}
            task.status = TaskStatus.failed
            return {"success": False, "error": "LLM unavailable"}
        except Exception as e:
            task.status = TaskStatus.failed
            task.errors.append(str(e))
            return {"success": False, "error": str(e)}

    def develop(self, description: str, language: str = "python") -> Dict[str, Any]:
        task_id = self.create_task(description, language)
        return self.execute_task(task_id)

    def quick_run(self, code: str, language: str = "python") -> Dict[str, Any]:
        if self.docker:
            try:
                from dev_agent.docker_manager import DockerManager
                return self.docker.run_code(code, language)
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "Docker not available"}

    def fix_code(self, code: str, language: str = "python") -> str:
        if self.codegen:
            result = self.codegen.fix_code(code, "syntax error", language)
            return result.get("code", code)
        return code

    def chat(self, message: str) -> str:
        if self.llm:
            return self.llm.generate_sync(message)
        return "LLM unavailable"

    def create_project(self, spec: ProjectSpec) -> Dict[str, Any]:
        prompt = (
            f"Crie a estrutura de um projeto {spec.language} chamado \"{spec.name}\".\n"
            f"Descricao: {spec.description}\n"
            f"Tecnologias: {', '.join(spec.technologies)}\n"
            f"Requisitos: {', '.join(spec.requirements)}\n\n"
            "Retorne a estrutura de arquivos e o codigo principal."
        )
        if self.llm:
            return {"success": True, "content": self.llm.generate_sync(prompt)}
        return {"success": False, "error": "LLM unavailable"}

    def get_supported_technologies(self) -> List[str]:
        from dev_agent import config
        return getattr(config, "EXTRA_FRAMEWORKS", [])

    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        task = self._tasks.get(task_id)
        return task.status if task else None

    def _acquire_squad_slot(self) -> None:
        self._squad_semaphore.acquire()

    def _release_squad_slot(self) -> None:
        self._squad_semaphore.release()

    def set_squad_capacity(self, n: int) -> None:
        import threading
        self._squad_semaphore = threading.Semaphore(n)

    def enable_squad_autoscale(self) -> None:
        pass

    def disable_squad_autoscale(self) -> None:
        pass

    def cleanup(self) -> None:
        if self.docker:
            try:
                self.docker.cleanup_all()
            except Exception:
                pass
