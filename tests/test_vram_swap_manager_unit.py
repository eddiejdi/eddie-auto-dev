#!/usr/bin/env python3
"""
Testes unitários e de integração para VRAMSwapManager.

Unit tests: estruturas de dados, máquina de estados, métricas.
Integration tests: comunicação real com Ollama GPU0/GPU1.
Sem mocks — todos os testes usam dados reais.

Nota: importa módulos diretamente (sem __init__.py) para evitar
imports pesados do pacote specialized_agents.
"""

import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest

# ── Import direto (bypass __init__.py pesado) ──
_SA_DIR = Path(__file__).parent.parent / "specialized_agents"

# Registrar config primeiro (dependência do vram_swap_manager)
_spec_cfg = importlib.util.spec_from_file_location(
    "specialized_agents.config", str(_SA_DIR / "config.py")
)
_config_mod = importlib.util.module_from_spec(_spec_cfg)
sys.modules["specialized_agents.config"] = _config_mod
_spec_cfg.loader.exec_module(_config_mod)

# Agora importar vram_swap_manager
_spec_vsm = importlib.util.spec_from_file_location(
    "specialized_agents.vram_swap_manager", str(_SA_DIR / "vram_swap_manager.py")
)
_vsm_mod = importlib.util.module_from_spec(_spec_vsm)
sys.modules["specialized_agents.vram_swap_manager"] = _vsm_mod
_spec_vsm.loader.exec_module(_vsm_mod)

GPU0State = _vsm_mod.GPU0State
GPU0Status = _vsm_mod.GPU0Status
SwapMetrics = _vsm_mod.SwapMetrics
VRAMSwapManager = _vsm_mod.VRAMSwapManager


# ══════════════════════════════════════════════════
# UNIT TESTS — não dependem de serviços externos
# ══════════════════════════════════════════════════


class TestGPU0StateEnum:
    """Testes do enum GPU0State."""

    def test_todos_os_estados_existem(self) -> None:
        """Deve ter 6 estados possíveis."""
        assert len(GPU0State) == 6

    def test_estado_llm_loaded(self) -> None:
        """Estado LLM_LOADED é o padrão."""
        assert GPU0State.LLM_LOADED.value == "llm_loaded"

    def test_estado_media_active(self) -> None:
        """Estado MEDIA_ACTIVE durante geração."""
        assert GPU0State.MEDIA_ACTIVE.value == "media_active"

    def test_estado_error(self) -> None:
        """Estado ERROR em caso de falha."""
        assert GPU0State.ERROR.value == "error"

    def test_transicoes_validas(self) -> None:
        """Verifica que todos os estados de transição existem."""
        expected = {
            "llm_loaded", "llm_unloading", "media_ready",
            "media_active", "llm_reloading", "error",
        }
        actual = {s.value for s in GPU0State}
        assert actual == expected


class TestGPU0Status:
    """Testes do dataclass GPU0Status."""

    def test_status_defaults(self) -> None:
        """Status deve ter defaults sensatos."""
        status = GPU0Status(state=GPU0State.LLM_LOADED)
        assert status.current_model is None
        assert status.vram_used_mb == 0.0
        assert status.vram_total_mb == 8192.0
        assert status.swap_count == 0

    def test_status_com_modelo(self) -> None:
        """Status com modelo carregado."""
        status = GPU0Status(
            state=GPU0State.LLM_LOADED,
            current_model="qwen2.5-coder:7b",
            vram_used_mb=4700,
        )
        assert status.current_model == "qwen2.5-coder:7b"
        assert status.vram_used_mb == 4700


class TestSwapMetrics:
    """Testes do dataclass SwapMetrics."""

    def test_metrics_defaults(self) -> None:
        """Métricas devem começar zeradas."""
        m = SwapMetrics()
        assert m.total_swaps == 0
        assert m.total_unload_time_s == 0.0
        assert m.total_reload_time_s == 0.0
        assert m.errors == 0

    def test_metrics_acumulacao(self) -> None:
        """Métricas devem acumular corretamente."""
        m = SwapMetrics()
        m.total_swaps = 3
        m.total_unload_time_s = 5.5
        m.total_reload_time_s = 12.3
        assert m.total_swaps == 3
        assert m.total_unload_time_s == 5.5


class TestVRAMSwapManagerInit:
    """Testes de inicialização do VRAMSwapManager."""

    def test_estado_inicial_llm_loaded(self) -> None:
        """Estado inicial deve ser LLM_LOADED."""
        manager = VRAMSwapManager()
        assert manager.state == GPU0State.LLM_LOADED

    def test_urls_padrao(self) -> None:
        """URLs padrão devem apontar para o servidor correto."""
        manager = VRAMSwapManager()
        assert "192.168.15.2" in manager.gpu0_url
        assert ":11434" in manager.gpu0_url
        assert "192.168.15.2" in manager.gpu1_url
        assert ":11435" in manager.gpu1_url

    def test_urls_customizaveis(self) -> None:
        """Deve aceitar URLs customizadas."""
        manager = VRAMSwapManager(
            ollama_gpu0_url="http://localhost:11434",
            ollama_gpu1_url="http://localhost:11435",
        )
        assert manager.gpu0_url == "http://localhost:11434"
        assert manager.gpu1_url == "http://localhost:11435"

    def test_modelo_padrao(self) -> None:
        """Modelo padrão da GPU0 deve ser qwen2.5-coder:7b."""
        manager = VRAMSwapManager()
        assert manager.gpu0_model == "qwen2.5-coder:7b"

    def test_get_status_retorna_gpu0status(self) -> None:
        """get_status() deve retornar GPU0Status consistente."""
        manager = VRAMSwapManager()
        status = manager.get_status()
        assert isinstance(status, GPU0Status)
        assert status.state == GPU0State.LLM_LOADED
        assert status.swap_count == 0

    def test_metrics_iniciais_zeradas(self) -> None:
        """Métricas iniciais devem estar zeradas."""
        manager = VRAMSwapManager()
        m = manager.metrics
        assert m.total_swaps == 0
        assert m.errors == 0

    def test_timeouts_customizaveis(self) -> None:
        """Timeouts devem ser configuráveis."""
        manager = VRAMSwapManager(unload_timeout=10, reload_timeout=60)
        assert manager.unload_timeout == 10
        assert manager.reload_timeout == 60


# ══════════════════════════════════════════════════
# INTEGRATION TESTS — requerem Ollama rodando
# ══════════════════════════════════════════════════


@pytest.mark.integration
class TestVRAMSwapManagerHealthCheck:
    """Testes de health check com Ollama real."""

    def test_health_check_gpu1_healthy(self, ollama_gpu1_url: str) -> None:
        """Health check deve reportar GPU1 como saudável."""
        manager = VRAMSwapManager(
            ollama_gpu1_url=ollama_gpu1_url,
        )
        health = asyncio.run(manager.health_check())
        assert health["gpu1_healthy"] is True
        assert health["gpu1_model"] is not None
        assert "qwen3" in health["gpu1_model"].lower()

    def test_health_check_metricas_iniciais(self, ollama_gpu1_url: str) -> None:
        """Métricas no health check devem estar zeradas no início."""
        manager = VRAMSwapManager(
            ollama_gpu1_url=ollama_gpu1_url,
        )
        health = asyncio.run(manager.health_check())
        assert health["metrics"]["total_swaps"] == 0
        assert health["metrics"]["errors"] == 0

    def test_health_check_gpu0_state(self, ollama_gpu0_url: str) -> None:
        """Health check deve reportar estado correto da GPU0."""
        manager = VRAMSwapManager(
            ollama_gpu0_url=ollama_gpu0_url,
        )
        health = asyncio.run(manager.health_check())
        assert health["gpu0_state"] == "llm_loaded"


@pytest.mark.integration
class TestVRAMSwapManagerUnloadReload:
    """Testes de swap real: unload/reload de modelo na GPU0."""

    def test_unload_model_gpu0(self, ollama_gpu0_url: str) -> None:
        """Deve descarregar modelo da GPU0 e retornar tempo > 0."""
        manager = VRAMSwapManager(
            ollama_gpu0_url=ollama_gpu0_url,
        )
        elapsed = asyncio.run(manager._ollama_unload_model())
        assert elapsed >= 0.0

    @pytest.mark.timeout(180)
    def test_acquire_release_full_cycle(self, ollama_gpu0_url: str) -> None:
        """Ciclo completo: acquire → media_ready → release → llm_loaded.

        Nota: Este teste é lento (~60-120s) pois recarrega qwen2.5-coder:7b na GPU0.
        """

        async def _run() -> None:
            manager = VRAMSwapManager(
                ollama_gpu0_url=ollama_gpu0_url,
                reload_timeout=180,
            )
            assert manager.state == GPU0State.LLM_LOADED

            # Adquirir GPU0 para mídia
            await manager.acquire_gpu0_for_media()
            assert manager.state == GPU0State.MEDIA_READY
            assert manager.metrics.last_unload_time_s >= 0.0

            # Liberar GPU0 e recarregar LLM
            await manager.release_gpu0_for_llm()
            assert manager.state == GPU0State.LLM_LOADED
            assert manager.metrics.total_swaps == 1
            assert manager.metrics.last_reload_time_s >= 0.0

        asyncio.run(_run())

    @pytest.mark.timeout(180)
    def test_context_manager_swap(self, ollama_gpu0_url: str) -> None:
        """Context manager deve fazer swap completo automaticamente.

        Nota: Este teste é lento (~60-120s) pois faz unload+reload completo.
        """

        async def _run() -> None:
            manager = VRAMSwapManager(
                ollama_gpu0_url=ollama_gpu0_url,
                reload_timeout=180,
            )
            async with manager.gpu0_for_media():
                assert manager.state == GPU0State.MEDIA_ACTIVE

            # Após sair do context, LLM deve estar recarregado
            assert manager.state == GPU0State.LLM_LOADED
            assert manager.metrics.total_swaps == 1
            assert manager.metrics.total_media_time_s > 0.0

        asyncio.run(_run())
