"""
VRAM Swap Manager — Exclusão mútua entre Ollama e Diffusers na GPU0.

Gerencia a GPU0 (RTX 2060 SUPER 8GB) alternando entre:
- Ollama LLM (qwen2.5-coder:7b ~4.7GB)
- Diffusers pipelines (SD 1.5, SDXL Turbo, CogVideoX, etc.)

A GPU1 (GTX 1050 2GB) mantém qwen3:0.6b permanentemente carregado como
controller e NÃO é afetada pelo swap.

Fluxo:
1. acquire_gpu0_for_media() → descarrega Ollama → retorna lock
2. Pipeline diffusers roda na GPU0
3. release_gpu0_for_llm() → limpa VRAM → recarrega Ollama

Uso:
    manager = VRAMSwapManager()
    async with manager.gpu0_for_media():
        # GPU0 livre para diffusers
        pipeline = load_pipeline("cuda:0")
        result = pipeline(prompt)
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class GPU0State(Enum):
    """Estado atual da GPU0."""
    LLM_LOADED = "llm_loaded"
    LLM_UNLOADING = "llm_unloading"
    MEDIA_READY = "media_ready"
    MEDIA_ACTIVE = "media_active"
    LLM_RELOADING = "llm_reloading"
    ERROR = "error"


@dataclass
class GPU0Status:
    """Snapshot do estado da GPU0."""
    state: GPU0State
    current_model: Optional[str] = None
    vram_used_mb: float = 0.0
    vram_total_mb: float = 8192.0
    last_swap_at: Optional[datetime] = None
    swap_count: int = 0
    total_swap_time_s: float = 0.0
    error: Optional[str] = None


@dataclass
class SwapMetrics:
    """Métricas de swap acumuladas."""
    total_swaps: int = 0
    total_unload_time_s: float = 0.0
    total_reload_time_s: float = 0.0
    total_media_time_s: float = 0.0
    last_unload_time_s: float = 0.0
    last_reload_time_s: float = 0.0
    errors: int = 0


class VRAMSwapManager:
    """
    Gerenciador de exclusão mútua entre Ollama e Diffusers na GPU0.

    A GPU0 é compartilhada: LLM (Ollama port 11434) ou pipelines de mídia
    (diffusers via torch). Nunca ambos ao mesmo tempo.
    """

    def __init__(
        self,
        ollama_gpu0_url: str = "http://192.168.15.2:11434",
        ollama_gpu0_model: str = "qwen2.5-coder:7b",
        ollama_gpu1_url: str = "http://192.168.15.2:11435",
        unload_timeout: float = 30.0,
        reload_timeout: float = 120.0,
    ) -> None:
        """
        Inicializa o gerenciador de VRAM swap.

        Args:
            ollama_gpu0_url: URL do Ollama na GPU0.
            ollama_gpu0_model: Modelo padrão que roda na GPU0.
            ollama_gpu1_url: URL do Ollama na GPU1 (controller, não afetado).
            unload_timeout: Timeout em segundos para descarregar modelo.
            reload_timeout: Timeout em segundos para recarregar modelo.
        """
        self.gpu0_url = ollama_gpu0_url
        self.gpu0_model = ollama_gpu0_model
        self.gpu1_url = ollama_gpu1_url
        self.unload_timeout = unload_timeout
        self.reload_timeout = reload_timeout

        self._lock = asyncio.Lock()
        self._state = GPU0State.LLM_LOADED
        self._current_model: Optional[str] = None
        self._metrics = SwapMetrics()

        logger.info(
            f"VRAMSwapManager inicializado — GPU0: {ollama_gpu0_url} "
            f"modelo: {ollama_gpu0_model}"
        )

    @property
    def state(self) -> GPU0State:
        """Estado atual da GPU0."""
        return self._state

    @property
    def metrics(self) -> SwapMetrics:
        """Métricas acumuladas de swap."""
        return self._metrics

    def get_status(self) -> GPU0Status:
        """Retorna snapshot do estado atual da GPU0."""
        return GPU0Status(
            state=self._state,
            current_model=self._current_model,
            swap_count=self._metrics.total_swaps,
            total_swap_time_s=(
                self._metrics.total_unload_time_s
                + self._metrics.total_reload_time_s
            ),
        )

    async def _ollama_unload_model(self) -> float:
        """
        Descarrega modelo LLM da GPU0 via API Ollama.

        Envia keep_alive=0 para liberar VRAM imediatamente.

        Returns:
            Tempo em segundos para descarregar.
        """
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self.unload_timeout) as client:
                # Verificar modelos carregados
                resp = await client.get(f"{self.gpu0_url}/api/ps")
                resp.raise_for_status()
                loaded = resp.json().get("models", [])

                if not loaded:
                    logger.info("GPU0: nenhum modelo LLM carregado — skip unload")
                    return time.monotonic() - t0

                # Descarregar cada modelo carregado
                for model_info in loaded:
                    model_name = model_info.get("name", self.gpu0_model)
                    logger.info(f"GPU0: descarregando {model_name}...")
                    await client.post(
                        f"{self.gpu0_url}/api/generate",
                        json={
                            "model": model_name,
                            "prompt": "",
                            "keep_alive": 0,
                        },
                    )

                # Aguardar VRAM livre (poll até ps vazio)
                for _ in range(int(self.unload_timeout)):
                    await asyncio.sleep(1)
                    resp = await client.get(f"{self.gpu0_url}/api/ps")
                    loaded = resp.json().get("models", [])
                    if not loaded:
                        break

                elapsed = time.monotonic() - t0
                logger.info(f"GPU0: modelo descarregado em {elapsed:.1f}s")
                return elapsed

        except Exception as e:
            elapsed = time.monotonic() - t0
            logger.error(f"GPU0: erro ao descarregar modelo: {e}")
            self._metrics.errors += 1
            raise RuntimeError(f"Falha ao descarregar LLM da GPU0: {e}") from e

    async def _ollama_reload_model(self) -> float:
        """
        Recarrega modelo LLM na GPU0 via API Ollama.

        Faz uma chamada dummy para forçar o carregamento.

        Returns:
            Tempo em segundos para recarregar.
        """
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self.reload_timeout) as client:
                logger.info(f"GPU0: recarregando {self.gpu0_model}...")
                resp = await client.post(
                    f"{self.gpu0_url}/api/generate",
                    json={
                        "model": self.gpu0_model,
                        "prompt": "ping",
                        "stream": False,
                    },
                )
                resp.raise_for_status()

                elapsed = time.monotonic() - t0
                self._current_model = self.gpu0_model
                logger.info(
                    f"GPU0: {self.gpu0_model} recarregado em {elapsed:.1f}s"
                )
                return elapsed

        except Exception as e:
            elapsed = time.monotonic() - t0
            logger.error(f"GPU0: erro ao recarregar modelo: {e}")
            self._metrics.errors += 1
            raise RuntimeError(
                f"Falha ao recarregar LLM na GPU0: {e}"
            ) from e

    async def acquire_gpu0_for_media(self) -> None:
        """
        Adquire GPU0 para uso exclusivo por pipeline de mídia.

        Descarrega o modelo LLM do Ollama e libera VRAM.
        Bloqueante se outro swap está em andamento.
        """
        await self._lock.acquire()
        try:
            self._state = GPU0State.LLM_UNLOADING
            unload_time = await self._ollama_unload_model()
            self._metrics.last_unload_time_s = unload_time
            self._metrics.total_unload_time_s += unload_time

            # Liberar cache CUDA
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    logger.info("GPU0: torch.cuda.empty_cache() executado")
            except ImportError:
                pass

            self._state = GPU0State.MEDIA_READY
            self._current_model = None
            logger.info("GPU0: pronta para pipeline de mídia")

        except Exception:
            self._state = GPU0State.ERROR
            self._lock.release()
            raise

    async def release_gpu0_for_llm(self) -> None:
        """
        Libera GPU0 e recarrega o modelo LLM do Ollama.

        Deve ser chamado após o pipeline de mídia terminar.
        """
        try:
            # Liberar VRAM de diffusers
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    logger.info("GPU0: VRAM limpa após pipeline de mídia")
            except ImportError:
                pass

            self._state = GPU0State.LLM_RELOADING
            reload_time = await self._ollama_reload_model()
            self._metrics.last_reload_time_s = reload_time
            self._metrics.total_reload_time_s += reload_time
            self._metrics.total_swaps += 1
            self._state = GPU0State.LLM_LOADED
            logger.info(
                f"GPU0: swap #{self._metrics.total_swaps} concluído — "
                f"LLM restaurado"
            )

        except Exception:
            self._state = GPU0State.ERROR
            raise
        finally:
            self._lock.release()

    @asynccontextmanager
    async def gpu0_for_media(self):
        """
        Context manager para uso exclusivo da GPU0 por pipelines de mídia.

        Exemplo::

            async with manager.gpu0_for_media():
                pipeline = StableDiffusionPipeline.from_pretrained(...).to("cuda:0")
                result = pipeline(prompt)
                del pipeline
        """
        t0 = time.monotonic()
        await self.acquire_gpu0_for_media()
        try:
            self._state = GPU0State.MEDIA_ACTIVE
            yield
        finally:
            media_time = time.monotonic() - t0
            self._metrics.total_media_time_s += media_time
            await self.release_gpu0_for_llm()

    async def health_check(self) -> dict:
        """
        Verifica saúde de ambas as GPUs.

        Returns:
            Dict com status de GPU0 e GPU1.
        """
        result = {
            "gpu0_state": self._state.value,
            "gpu0_model": self._current_model,
            "gpu1_healthy": False,
            "gpu1_model": None,
            "metrics": {
                "total_swaps": self._metrics.total_swaps,
                "total_unload_time_s": round(
                    self._metrics.total_unload_time_s, 2
                ),
                "total_reload_time_s": round(
                    self._metrics.total_reload_time_s, 2
                ),
                "total_media_time_s": round(
                    self._metrics.total_media_time_s, 2
                ),
                "errors": self._metrics.errors,
            },
        }

        # Check GPU1 controller
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.gpu1_url}/api/ps")
                if resp.status_code == 200:
                    models = resp.json().get("models", [])
                    result["gpu1_healthy"] = True
                    if models:
                        result["gpu1_model"] = models[0].get("name")
        except Exception as e:
            logger.warning(f"GPU1 health check falhou: {e}")

        return result
