"""
Gerenciador On-Demand para Componentes
Inicia componentes apenas quando necessário e desliga após inatividade
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, Callable, Awaitable
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ComponentStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"


class OnDemandComponent:
    """Representa um componente gerenciado on-demand"""

    def __init__(
        self,
        name: str,
        start_func: Callable[[], Awaitable[Any]],
        stop_func: Callable[[], Awaitable[Any]],
        health_check: Optional[Callable[[], Awaitable[bool]]] = None,
        idle_timeout_seconds: int = 300,  # 5 minutos padrão
        warm_up_seconds: int = 5,
    ):
        self.name = name
        self.start_func = start_func
        self.stop_func = stop_func
        self.health_check = health_check
        self.idle_timeout = idle_timeout_seconds
        self.warm_up_seconds = warm_up_seconds

        self.status = ComponentStatus.STOPPED
        self.last_activity = None
        self.instance = None
        self.start_count = 0
        self.error_count = 0
        self._lock = asyncio.Lock()

    async def ensure_running(self) -> Any:
        """Garante que o componente está rodando"""
        async with self._lock:
            if self.status == ComponentStatus.RUNNING:
                self.last_activity = datetime.now()
                return self.instance

            if self.status == ComponentStatus.STARTING:
                # Aguardar startup
                for _ in range(self.warm_up_seconds * 2):
                    await asyncio.sleep(0.5)
                    if self.status == ComponentStatus.RUNNING:
                        return self.instance
                return self.instance

            # Iniciar componente
            self.status = ComponentStatus.STARTING
            logger.info(f"[OnDemand] Iniciando componente: {self.name}")

            try:
                self.instance = await self.start_func()
                self.status = ComponentStatus.RUNNING
                self.last_activity = datetime.now()
                self.start_count += 1
                logger.info(f"[OnDemand] Componente iniciado: {self.name}")
                return self.instance
            except Exception as e:
                self.status = ComponentStatus.STOPPED
                self.error_count += 1
                logger.error(f"[OnDemand] Erro ao iniciar {self.name}: {e}")
                import traceback

                logger.error(traceback.format_exc())
                raise

    async def stop(self):
        """Para o componente"""
        async with self._lock:
            if self.status != ComponentStatus.RUNNING:
                return

            self.status = ComponentStatus.STOPPING
            logger.info(f"[OnDemand] Parando componente: {self.name}")

            try:
                await self.stop_func()
                self.instance = None
                self.status = ComponentStatus.STOPPED
                logger.info(f"[OnDemand] Componente parado: {self.name}")
            except Exception as e:
                logger.error(f"[OnDemand] Erro ao parar {self.name}: {e}")
                self.status = ComponentStatus.STOPPED

    def is_idle(self) -> bool:
        """Verifica se o componente está ocioso"""
        if self.status != ComponentStatus.RUNNING:
            return False

        if not self.last_activity:
            return True

        idle_time = datetime.now() - self.last_activity
        return idle_time.total_seconds() > self.idle_timeout

    def get_status(self) -> Dict[str, Any]:
        """Retorna status do componente"""
        idle_seconds = 0
        if self.last_activity:
            idle_seconds = (datetime.now() - self.last_activity).total_seconds()

        return {
            "name": self.name,
            "status": self.status.value,
            "last_activity": (
                self.last_activity.isoformat() if self.last_activity else None
            ),
            "idle_seconds": int(idle_seconds),
            "idle_timeout": self.idle_timeout,
            "start_count": self.start_count,
            "error_count": self.error_count,
        }


class OnDemandManager:
    """Gerenciador central de componentes on-demand"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.components: Dict[str, OnDemandComponent] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        self._cleanup_interval = 60  # Verificar a cada 60 segundos
        self._initialized = True

    def register(
        self,
        name: str,
        start_func: Callable[[], Awaitable[Any]],
        stop_func: Callable[[], Awaitable[Any]],
        health_check: Optional[Callable[[], Awaitable[bool]]] = None,
        idle_timeout_seconds: int = 300,
    ):
        """Registra um componente para gerenciamento on-demand"""
        self.components[name] = OnDemandComponent(
            name=name,
            start_func=start_func,
            stop_func=stop_func,
            health_check=health_check,
            idle_timeout_seconds=idle_timeout_seconds,
        )
        logger.info(
            f"[OnDemand] Componente registrado: {name} (timeout: {idle_timeout_seconds}s)"
        )

    async def get(self, name: str) -> Any:
        """Obtém instância de um componente (inicia se necessário)"""
        if name not in self.components:
            raise ValueError(f"Componente não registrado: {name}")

        return await self.components[name].ensure_running()

    async def stop(self, name: str):
        """Para um componente específico"""
        if name in self.components:
            await self.components[name].stop()

    async def stop_all(self):
        """Para todos os componentes"""
        tasks = [comp.stop() for comp in self.components.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def start_cleanup_loop(self):
        """Inicia loop de limpeza de componentes ociosos"""
        if self._running:
            return

        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("[OnDemand] Loop de limpeza iniciado")

    async def stop_cleanup_loop(self):
        """Para o loop de limpeza"""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def _cleanup_loop(self):
        """Loop que verifica e para componentes ociosos"""
        while self._running:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self._cleanup_idle_components()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[OnDemand] Erro no cleanup loop: {e}")

    async def _cleanup_idle_components(self):
        """Para componentes que estão ociosos"""
        for name, component in self.components.items():
            if component.is_idle():
                logger.info(f"[OnDemand] Componente ocioso detectado: {name}")
                await component.stop()

    def get_status(self) -> Dict[str, Any]:
        """Retorna status de todos os componentes"""
        running_count = sum(
            1 for c in self.components.values() if c.status == ComponentStatus.RUNNING
        )

        return {
            "total_components": len(self.components),
            "running_components": running_count,
            "cleanup_running": self._running,
            "cleanup_interval": self._cleanup_interval,
            "components": {
                name: comp.get_status() for name, comp in self.components.items()
            },
        }

    def set_idle_timeout(self, name: str, timeout_seconds: int):
        """Altera timeout de ociosidade de um componente"""
        if name in self.components:
            self.components[name].idle_timeout = timeout_seconds

    def set_global_timeout(self, timeout_seconds: int):
        """Define timeout padrão para todos os componentes"""
        for component in self.components.values():
            component.idle_timeout = timeout_seconds


# Singleton global
_on_demand_manager: Optional[OnDemandManager] = None


def get_on_demand_manager() -> OnDemandManager:
    """Obtém instância do gerenciador on-demand"""
    global _on_demand_manager
    if _on_demand_manager is None:
        _on_demand_manager = OnDemandManager()
    return _on_demand_manager


# ================== Componentes Pré-definidos ==================


class LazyRAGManager:
    """RAG Manager com inicialização lazy"""

    def __init__(self, language: str):
        self.language = language
        self._manager = None

    async def _start(self):
        from .rag_manager import RAGManagerFactory

        self._manager = RAGManagerFactory.get_manager(self.language)
        return self._manager

    async def _stop(self):
        self._manager = None

    async def get(self):
        if self._manager is None:
            await self._start()
        return self._manager


class LazyDockerOrchestrator:
    """Docker Orchestrator com inicialização lazy"""

    def __init__(self):
        self._orchestrator = None

    async def _start(self):
        from .docker_orchestrator import DockerOrchestrator

        self._orchestrator = DockerOrchestrator()
        return self._orchestrator

    async def _stop(self):
        if self._orchestrator:
            # Parar containers gerenciados
            for container_id in list(self._orchestrator.containers.keys()):
                try:
                    await self._orchestrator.stop_container(container_id)
                except:
                    pass
        self._orchestrator = None

    async def get(self):
        if self._orchestrator is None:
            await self._start()
        return self._orchestrator


class LazyGitHubClient:
    """GitHub Client com inicialização lazy"""

    def __init__(self):
        self._client = None

    async def _start(self):
        from .github_client import GitHubAgentClient

        self._client = GitHubAgentClient()
        return self._client

    async def _stop(self):
        self._client = None

    async def get(self):
        if self._client is None:
            await self._start()
        return self._client


class LazyLLMClient:
    """LLM Client com inicialização lazy"""

    def __init__(self):
        self._client = None

    async def _start(self):
        import httpx
        from .config import LLM_CONFIG

        self._client = httpx.AsyncClient(
            base_url=LLM_CONFIG["base_url"], timeout=LLM_CONFIG["timeout"]
        )
        return self._client

    async def _stop(self):
        if self._client:
            await self._client.aclose()
        self._client = None

    async def get(self):
        if self._client is None:
            await self._start()
        return self._client
