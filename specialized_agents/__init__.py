"""
Sistema de Agentes Programadores Especializados
Cada agente é especializado em uma linguagem com RAG próprio

Imports pesados (chromadb, grpc) são carregados sob demanda (lazy) para que
módulos leves como agent_communication_bus e agent_interceptor iniciem rápido.
"""
import importlib as _importlib
import sys as _sys

# ── Imports leves — sempre disponíveis ──────────────────────────────────
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

# ── Lazy imports — carregam módulos pesados somente no primeiro acesso ──
_LAZY_MODULES = {
    # symbol -> (module, attribute)
    "AgentManager": (".agent_manager", "AgentManager"),
    "get_agent_manager": (".agent_manager", "get_agent_manager"),
    "SpecializedAgent": (".base_agent", "SpecializedAgent"),
    "PythonAgent": (".language_agents", "PythonAgent"),
    "JavaScriptAgent": (".language_agents", "JavaScriptAgent"),
    "GoAgent": (".language_agents", "GoAgent"),
    "RustAgent": (".language_agents", "RustAgent"),
    "JavaAgent": (".language_agents", "JavaAgent"),
    "CSharpAgent": (".language_agents", "CSharpAgent"),
    "TypeScriptAgent": (".language_agents", "TypeScriptAgent"),
    "PHPAgent": (".language_agents", "PHPAgent"),
    "DockerOrchestrator": (".docker_orchestrator", "DockerOrchestrator"),
    "FileManager": (".file_manager", "FileManager"),
    "CleanupService": (".cleanup_service", "CleanupService"),
    "LanguageRAGManager": (".rag_manager", "LanguageRAGManager"),
    "RequirementsAnalystAgent": (".requirements_analyst", "RequirementsAnalystAgent"),
    "get_requirements_analyst": (".requirements_analyst", "get_requirements_analyst"),
    "AgentMemory": (".agent_memory", "AgentMemory"),
    "get_agent_memory": (".agent_memory", "get_agent_memory"),
}


def __getattr__(name: str):
    if name in _LAZY_MODULES:
        mod_path, attr = _LAZY_MODULES[name]
        mod = _importlib.import_module(mod_path, __package__)
        val = getattr(mod, attr)
        # Cache no namespace do pacote para próximos acessos
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
