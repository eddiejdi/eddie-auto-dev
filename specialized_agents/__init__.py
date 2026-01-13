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
from .agent_communication_bus import (
    AgentCommunicationBus,
    get_communication_bus,
    MessageType,
    AgentMessage,
    log_coordinator,
    log_request,
    log_response,
    log_task_start,
    log_task_end,
    log_llm_call,
    log_llm_response,
    log_code_generation,
    log_execution,
    log_error,
    log_docker_operation,
    log_rag_search,
    log_github_operation,
    log_analysis
)

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
    "get_requirements_analyst",
    # Agent Communication Bus
    "AgentCommunicationBus",
    "get_communication_bus",
    "MessageType",
    "AgentMessage",
    "log_coordinator",
    "log_request",
    "log_response",
    "log_task_start",
    "log_task_end",
    "log_llm_call",
    "log_llm_response",
    "log_code_generation",
    "log_execution",
    "log_error",
    "log_docker_operation",
    "log_rag_search",
    "log_github_operation",
    "log_analysis"
]
