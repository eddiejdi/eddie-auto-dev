"""
Agent Communication Bus
Sistema de interceptação e logging de comunicação entre agentes em tempo real
"""

import json
from datetime import datetime
from typing import Dict, List, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import threading


class MessageType(Enum):
    """Tipos de mensagem entre agentes"""

    REQUEST = "request"  # Requisição de um agente
    RESPONSE = "response"  # Resposta de um agente
    TASK_START = "task_start"  # Início de tarefa
    TASK_END = "task_end"  # Fim de tarefa
    LLM_CALL = "llm_call"  # Chamada ao LLM
    LLM_RESPONSE = "llm_response"  # Resposta do LLM
    CODE_GEN = "code_gen"  # Código gerado
    TEST_GEN = "test_gen"  # Teste gerado
    EXECUTION = "execution"  # Execução de código
    ERROR = "error"  # Erro
    DOCKER = "docker"  # Operação Docker
    RAG = "rag"  # Busca RAG
    GITHUB = "github"  # Operação GitHub
    COORDINATOR = "coordinator"  # Mensagem do coordenador
    ANALYSIS = "analysis"  # Análise de requisitos


@dataclass
class AgentMessage:
    """Representa uma mensagem trocada entre agentes"""

    id: str
    timestamp: datetime
    message_type: MessageType
    source: str  # Agente de origem
    target: str  # Agente de destino (ou "all" para broadcast)
    content: str  # Conteúdo da mensagem
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "type": self.message_type.value,
            "source": self.source,
            "target": self.target,
            "content": (
                self.content[:2000] if len(self.content) > 2000 else self.content
            ),
            "content_truncated": len(self.content) > 2000,
            "metadata": self.metadata,
        }


class AgentCommunicationBus:
    """
    Bus central de comunicação entre agentes.
    Intercepta e registra todas as mensagens em tempo real.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Buffer circular de mensagens (últimas 1000)
        self.message_buffer: deque = deque(maxlen=1000)

        # Subscribers para notificações em tempo real
        self.subscribers: List[Callable[[AgentMessage], None]] = []

        # Filtros ativos
        self.active_filters: Dict[str, bool] = {
            MessageType.REQUEST.value: True,
            MessageType.RESPONSE.value: True,
            MessageType.TASK_START.value: True,
            MessageType.TASK_END.value: True,
            MessageType.LLM_CALL.value: True,
            MessageType.LLM_RESPONSE.value: True,
            MessageType.CODE_GEN.value: True,
            MessageType.TEST_GEN.value: True,
            MessageType.EXECUTION.value: True,
            MessageType.ERROR.value: True,
            MessageType.DOCKER.value: True,
            MessageType.RAG.value: True,
            MessageType.GITHUB.value: True,
            MessageType.COORDINATOR.value: True,
            MessageType.ANALYSIS.value: True,
        }

        # Contador de mensagens
        self._message_counter = 0

        # Flag de gravação
        self.recording = True

        # Estatísticas
        self.stats = {
            "total_messages": 0,
            "by_type": {},
            "by_source": {},
            "errors": 0,
            "start_time": datetime.now(),
        }

        self._initialized = True

    def _generate_message_id(self) -> str:
        """Gera ID único para mensagem"""
        self._message_counter += 1
        return (
            f"msg_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self._message_counter:06d}"
        )

    def publish(
        self,
        message_type: MessageType,
        source: str,
        target: str,
        content: str,
        metadata: Dict[str, Any] = None,
    ) -> AgentMessage:
        """
        Publica uma mensagem no bus.

        Args:
            message_type: Tipo da mensagem
            source: Agente de origem
            target: Agente de destino (ou "all")
            content: Conteúdo da mensagem
            metadata: Metadados adicionais

        Returns:
            AgentMessage criada
        """
        if not self.recording:
            return None

        # Verificar filtro
        if not self.active_filters.get(message_type.value, True):
            return None

        message = AgentMessage(
            id=self._generate_message_id(),
            timestamp=datetime.now(),
            message_type=message_type,
            source=source,
            target=target,
            content=content,
            metadata=metadata or {},
        )

        # Adicionar ao buffer
        self.message_buffer.append(message)

        # Atualizar estatísticas
        self.stats["total_messages"] += 1
        self.stats["by_type"][message_type.value] = (
            self.stats["by_type"].get(message_type.value, 0) + 1
        )
        self.stats["by_source"][source] = self.stats["by_source"].get(source, 0) + 1

        if message_type == MessageType.ERROR:
            self.stats["errors"] += 1

        # Notificar subscribers
        for subscriber in self.subscribers:
            try:
                subscriber(message)
            except Exception:
                pass

        return message

    def subscribe(self, callback: Callable[[AgentMessage], None]):
        """Adiciona subscriber para notificações em tempo real"""
        if callback not in self.subscribers:
            self.subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[AgentMessage], None]):
        """Remove subscriber"""
        if callback in self.subscribers:
            self.subscribers.remove(callback)

    def get_messages(
        self,
        limit: int = 100,
        message_types: List[MessageType] = None,
        source: str = None,
        target: str = None,
        since: datetime = None,
    ) -> List[AgentMessage]:
        """
        Obtém mensagens com filtros opcionais.

        Args:
            limit: Número máximo de mensagens
            message_types: Filtrar por tipos
            source: Filtrar por origem
            target: Filtrar por destino
            since: Mensagens após esta data

        Returns:
            Lista de mensagens filtradas
        """
        messages = list(self.message_buffer)

        # Aplicar filtros
        if message_types:
            type_values = [mt.value for mt in message_types]
            messages = [m for m in messages if m.message_type.value in type_values]

        if source:
            messages = [m for m in messages if source.lower() in m.source.lower()]

        if target:
            messages = [m for m in messages if target.lower() in m.target.lower()]

        if since:
            messages = [m for m in messages if m.timestamp >= since]

        # Retornar últimas mensagens
        return messages[-limit:]

    def get_conversation_thread(self, task_id: str = None) -> List[AgentMessage]:
        """Obtém thread de conversa por task_id"""
        if not task_id:
            return list(self.message_buffer)

        return [m for m in self.message_buffer if m.metadata.get("task_id") == task_id]

    def clear(self):
        """Limpa buffer de mensagens"""
        self.message_buffer.clear()
        self._message_counter = 0
        self.stats = {
            "total_messages": 0,
            "by_type": {},
            "by_source": {},
            "errors": 0,
            "start_time": datetime.now(),
        }

    def set_filter(self, message_type: str, enabled: bool):
        """Ativa/desativa filtro de tipo de mensagem"""
        self.active_filters[message_type] = enabled

    def pause_recording(self):
        """Pausa a gravação de mensagens"""
        self.recording = False

    def resume_recording(self):
        """Retoma a gravação de mensagens"""
        self.recording = True

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de comunicação"""
        uptime = (datetime.now() - self.stats["start_time"]).total_seconds()
        return {
            **self.stats,
            "uptime_seconds": uptime,
            "messages_per_minute": (
                (self.stats["total_messages"] / uptime * 60) if uptime > 0 else 0
            ),
            "buffer_size": len(self.message_buffer),
            "buffer_max": self.message_buffer.maxlen,
            "recording": self.recording,
        }

    def export_messages(self, format: str = "json") -> str:
        """Exporta mensagens para string"""
        messages = [m.to_dict() for m in self.message_buffer]

        if format == "json":
            return json.dumps(messages, indent=2, ensure_ascii=False)
        elif format == "markdown":
            lines = ["# Agent Communication Log\n"]
            for m in messages:
                lines.append(f"## [{m['timestamp']}] {m['type'].upper()}")
                lines.append(f"**{m['source']}** → **{m['target']}**\n")
                lines.append(f"```\n{m['content']}\n```\n")
            return "\n".join(lines)
        else:
            return str(messages)


# Singleton global
_bus_instance = None


def get_communication_bus() -> AgentCommunicationBus:
    """Obtém instância singleton do bus de comunicação"""
    global _bus_instance
    if _bus_instance is None:
        _bus_instance = AgentCommunicationBus()
    return _bus_instance


# Funções helper para publicação rápida
def log_request(source: str, target: str, content: str, **metadata):
    """Loga requisição entre agentes"""
    return get_communication_bus().publish(
        MessageType.REQUEST, source, target, content, metadata
    )


def log_response(source: str, target: str, content: str, **metadata):
    """Loga resposta entre agentes"""
    return get_communication_bus().publish(
        MessageType.RESPONSE, source, target, content, metadata
    )


def log_task_start(source: str, task_id: str, description: str, **metadata):
    """Loga início de tarefa"""
    return get_communication_bus().publish(
        MessageType.TASK_START,
        source,
        "system",
        f"Task {task_id}: {description}",
        {"task_id": task_id, **metadata},
    )


def log_task_end(source: str, task_id: str, status: str, **metadata):
    """Loga fim de tarefa"""
    return get_communication_bus().publish(
        MessageType.TASK_END,
        source,
        "system",
        f"Task {task_id} finalizada: {status}",
        {"task_id": task_id, "status": status, **metadata},
    )


def log_llm_call(source: str, prompt: str, model: str = None, **metadata):
    """Loga chamada ao LLM"""
    return get_communication_bus().publish(
        MessageType.LLM_CALL,
        source,
        "ollama",
        prompt[:500] + "..." if len(prompt) > 500 else prompt,
        {"model": model, "prompt_length": len(prompt), **metadata},
    )


def log_llm_response(source: str, response: str, model: str = None, **metadata):
    """Loga resposta do LLM"""
    return get_communication_bus().publish(
        MessageType.LLM_RESPONSE,
        "ollama",
        source,
        response[:1000] + "..." if len(response) > 1000 else response,
        {"model": model, "response_length": len(response), **metadata},
    )


def log_code_generation(
    source: str, description: str, code_snippet: str = "", **metadata
):
    """Loga geração de código"""
    return get_communication_bus().publish(
        MessageType.CODE_GEN,
        source,
        "user",
        f"{description}\n\n{code_snippet[:500]}...",
        {"code_length": len(code_snippet), **metadata},
    )


def log_execution(source: str, result: str, success: bool = True, **metadata):
    """Loga execução de código"""
    return get_communication_bus().publish(
        MessageType.EXECUTION,
        source,
        "docker",
        result[:1000] if len(result) > 1000 else result,
        {"success": success, **metadata},
    )


def log_error(source: str, error: str, **metadata):
    """Loga erro"""
    return get_communication_bus().publish(
        MessageType.ERROR, source, "system", error, metadata
    )


def log_docker_operation(source: str, operation: str, details: str = "", **metadata):
    """Loga operação Docker"""
    return get_communication_bus().publish(
        MessageType.DOCKER,
        source,
        "docker",
        f"{operation}: {details}",
        {"operation": operation, **metadata},
    )


def log_rag_search(source: str, query: str, results_count: int = 0, **metadata):
    """Loga busca RAG"""
    return get_communication_bus().publish(
        MessageType.RAG,
        source,
        "rag",
        f"Query: {query} | Resultados: {results_count}",
        {"query": query, "results_count": results_count, **metadata},
    )


def log_github_operation(source: str, operation: str, details: str = "", **metadata):
    """Loga operação GitHub"""
    return get_communication_bus().publish(
        MessageType.GITHUB,
        source,
        "github",
        f"{operation}: {details}",
        {"operation": operation, **metadata},
    )


def log_coordinator(message: str, **metadata):
    """Loga mensagem do coordenador"""
    return get_communication_bus().publish(
        MessageType.COORDINATOR, "coordinator", "all", message, metadata
    )


def log_analysis(source: str, analysis_type: str, content: str, **metadata):
    """Loga análise de requisitos"""
    return get_communication_bus().publish(
        MessageType.ANALYSIS,
        source,
        "analyst",
        f"[{analysis_type}] {content}",
        {"analysis_type": analysis_type, **metadata},
    )
