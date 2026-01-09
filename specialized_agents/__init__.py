"""
Sistema de Agentes Programadores Especializados
Cada agente é especializado em uma linguagem com RAG próprio
"""

from .agent_manager import AgentManager, get_agent_manager
from .base_agent import SpecializedAgent
from .language_agents import (
    PythonAgent,
    JavaScriptAgent,
    GoAgent,
    RustAgent,
    JavaAgent,
    CSharpAgent,
    TypeScriptAgent,
    PHPAgent
)
from .docker_orchestrator import DockerOrchestrator
from .file_manager import FileManager
from .cleanup_service import CleanupService
from .rag_manager import LanguageRAGManager
from .requirements_analyst import RequirementsAnalystAgent, get_requirements_analyst

__version__ = "1.0.0"
__all__ = [
    "AgentManager",
    "get_agent_manager",
    "SpecializedAgent",
    "PythonAgent",
    "JavaScriptAgent", 
    "GoAgent",
    "RustAgent",
    "JavaAgent",
    "CSharpAgent",
    "TypeScriptAgent",
    "PHPAgent",
    "DockerOrchestrator",
    "FileManager",
    "CleanupService",
    "LanguageRAGManager",
    "RequirementsAnalystAgent",
    "get_requirements_analyst"
]
