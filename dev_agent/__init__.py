# Dev Agent - Agente Programador Autonomo
__version__ = "1.0.0"

from .agent import DevAgent, ProjectSpec, Task, TaskStatus
from .config import LLM_CONFIG, DOCKER_CONFIG, SUPPORTED_TECHNOLOGIES
from .llm_client import LLMClient, CodeGenerator, ConversationManager
from .docker_manager import DockerManager
from .test_runner import TestRunner, AutoFixer
from .coordinator import CoordinatorAgent, create_coordinator

__all__ = [
    "DevAgent",
    "ProjectSpec", 
    "Task",
    "TaskStatus",
    "LLMClient",
    "CodeGenerator",
    "ConversationManager",
    "DockerManager",
    "TestRunner",
    "AutoFixer",
    "CoordinatorAgent",
    "create_coordinator",
    "LLM_CONFIG",
    "DOCKER_CONFIG",
    "SUPPORTED_TECHNOLOGIES",
]
