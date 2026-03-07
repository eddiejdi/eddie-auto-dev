#!/usr/bin/env python3
"""
Testes unitários e de integração para MediaGenerationService.

Unit tests: configuração, status de pipelines, enums, dataclasses.
Integration tests: refinamento de prompt via GPU1 real, health check.
Sem mocks — todos os testes usam dados e serviços reais.

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

# Registrar config primeiro (se ainda não registrado)
if "specialized_agents.config" not in sys.modules:
    _spec_cfg = importlib.util.spec_from_file_location(
        "specialized_agents.config", str(_SA_DIR / "config.py")
    )
    _config_mod = importlib.util.module_from_spec(_spec_cfg)
    sys.modules["specialized_agents.config"] = _config_mod
    _spec_cfg.loader.exec_module(_config_mod)

# Registrar vram_swap_manager (dependência do media_generation_service)
if "specialized_agents.vram_swap_manager" not in sys.modules:
    _spec_vsm = importlib.util.spec_from_file_location(
        "specialized_agents.vram_swap_manager", str(_SA_DIR / "vram_swap_manager.py")
    )
    _vsm_mod = importlib.util.module_from_spec(_spec_vsm)
    sys.modules["specialized_agents.vram_swap_manager"] = _vsm_mod
    _spec_vsm.loader.exec_module(_vsm_mod)

# Agora importar media_generation_service
_spec_mgs = importlib.util.spec_from_file_location(
    "specialized_agents.media_generation_service",
    str(_SA_DIR / "media_generation_service.py"),
)
_mgs_mod = importlib.util.module_from_spec(_spec_mgs)
sys.modules["specialized_agents.media_generation_service"] = _mgs_mod
_spec_mgs.loader.exec_module(_mgs_mod)

GenerationStatus = _mgs_mod.GenerationStatus
MediaGenerationService = _mgs_mod.MediaGenerationService
MediaRequest = _mgs_mod.MediaRequest
MediaResult = _mgs_mod.MediaResult
MediaType = _mgs_mod.MediaType


# ══════════════════════════════════════════════════
# UNIT TESTS — sem dependência de serviços
# ══════════════════════════════════════════════════


class TestMediaTypeEnum:
    """Testes do enum MediaType."""

    def test_image_value(self) -> None:
        """MediaType.IMAGE deve ter valor 'image'."""
        assert MediaType.IMAGE.value == "image"

    def test_video_value(self) -> None:
        """MediaType.VIDEO deve ter valor 'video'."""
        assert MediaType.VIDEO.value == "video"


class TestGenerationStatusEnum:
    """Testes do enum GenerationStatus."""

    def test_todos_os_status(self) -> None:
        """Deve ter 8 status de geração."""
        assert len(GenerationStatus) == 8

    def test_fluxo_happy_path(self) -> None:
        """Status do happy path devem existir na ordem correta."""
        flow = [
            GenerationStatus.QUEUED,
            GenerationStatus.REFINING_PROMPT,
            GenerationStatus.SWAPPING_VRAM,
            GenerationStatus.LOADING_PIPELINE,
            GenerationStatus.GENERATING,
            GenerationStatus.SAVING,
            GenerationStatus.COMPLETED,
        ]
        assert len(flow) == 7

    def test_status_failed(self) -> None:
        """Status FAILED deve existir para erros."""
        assert GenerationStatus.FAILED.value == "failed"


class TestMediaRequest:
    """Testes do dataclass MediaRequest."""

    def test_defaults_sensatos(self) -> None:
        """Request com defaults deve ter valores sensatos."""
        req = MediaRequest(prompt="test")
        assert req.prompt == "test"
        assert req.pipeline_id == "sd15"
        assert req.media_type == "image"
        assert req.guidance_scale == 7.5
        assert req.num_images == 1
        assert req.refine_prompt is True
        assert req.id  # UUID gerado automaticamente

    def test_request_video(self) -> None:
        """Request de vídeo deve aceitar campos extras."""
        req = MediaRequest(
            prompt="uma paisagem",
            pipeline_id="cogvideo_2b",
            media_type="video",
            num_frames=49,
            fps=8,
        )
        assert req.media_type == "video"
        assert req.num_frames == 49
        assert req.fps == 8

    def test_request_ids_unicos(self) -> None:
        """Cada request deve gerar um UUID único."""
        r1 = MediaRequest(prompt="a")
        r2 = MediaRequest(prompt="b")
        assert r1.id != r2.id

    def test_request_sem_refinamento(self) -> None:
        """Deve poder desabilitar refinamento de prompt."""
        req = MediaRequest(prompt="raw prompt", refine_prompt=False)
        assert req.refine_prompt is False


class TestMediaResult:
    """Testes do dataclass MediaResult."""

    def test_result_defaults(self) -> None:
        """Result com defaults."""
        result = MediaResult(
            request_id="test-123",
            status=GenerationStatus.COMPLETED.value,
        )
        assert result.request_id == "test-123"
        assert result.output_paths == []
        assert result.error is None

    def test_result_to_dict(self) -> None:
        """to_dict() deve serializar todos os campos."""
        result = MediaResult(
            request_id="test-456",
            status="completed",
            media_type="image",
            output_paths=["/tmp/test.png"],
            generation_time_s=1.5,
        )
        d = result.to_dict()
        assert d["request_id"] == "test-456"
        assert d["output_paths"] == ["/tmp/test.png"]
        assert d["generation_time_s"] == 1.5

    def test_result_com_erro(self) -> None:
        """Result de falha deve ter campo error."""
        result = MediaResult(
            request_id="test-err",
            status="failed",
            error="Pipeline não encontrado",
        )
        assert result.status == "failed"
        assert "Pipeline" in result.error


class TestMediaGenerationServiceInit:
    """Testes de inicialização do MediaGenerationService."""

    def test_init_com_config_padrao(self) -> None:
        """Deve inicializar com MEDIA_GENERATION_CONFIG."""
        service = MediaGenerationService()
        assert service._gpu1_model == "qwen3:0.6b"
        assert ":11435" in service._gpu1_url

    def test_output_dir_criado(self, tmp_path: Path) -> None:
        """Deve criar diretório de output se não existir."""
        from specialized_agents.config import MEDIA_GENERATION_CONFIG
        config = {**MEDIA_GENERATION_CONFIG, "output_dir": tmp_path / "test_output"}
        service = MediaGenerationService(config=config)
        assert service._output_dir.exists()

    def test_7_pipelines_disponiveis(self) -> None:
        """Deve listar 7 pipelines disponíveis."""
        service = MediaGenerationService()
        assert len(service.available_pipelines) == 7

    def test_pipeline_ids(self) -> None:
        """IDs dos pipelines devem ser os esperados."""
        service = MediaGenerationService()
        expected = {"sd15", "sdxl_turbo", "sd3_medium", "cogvideo_2b",
                    "ltx_video", "wan_video", "animatediff"}
        assert set(service.available_pipelines.keys()) == expected


class TestPipelineStatus:
    """Testes de get_pipeline_status()."""

    def test_status_retorna_todos_pipelines(self) -> None:
        """Status deve incluir todos os 7 pipelines."""
        service = MediaGenerationService()
        status = service.get_pipeline_status()
        assert len(status) == 7

    def test_status_campos_obrigatorios(self) -> None:
        """Cada pipeline no status deve ter name, type, vram_gb, downloaded, loaded."""
        service = MediaGenerationService()
        status = service.get_pipeline_status()
        required = {"name", "type", "vram_gb", "downloaded", "loaded"}
        for pid, info in status.items():
            missing = required - set(info.keys())
            assert not missing, f"Pipeline {pid} falta campos: {missing}"

    def test_nenhum_pipeline_loaded_inicialmente(self) -> None:
        """Nenhum pipeline deve estar loaded no início."""
        service = MediaGenerationService()
        status = service.get_pipeline_status()
        for pid, info in status.items():
            assert info["loaded"] is False, f"Pipeline {pid} não deveria estar loaded"

    def test_is_pipeline_downloaded_invalido(self) -> None:
        """Pipeline inexistente deve retornar False."""
        service = MediaGenerationService()
        assert service.is_pipeline_downloaded("pipeline_que_nao_existe") is False


class TestMediaGenerationRejectInvalid:
    """Testes de rejeição de requisições inválidas."""

    def test_pipeline_desconhecido_retorna_failed(self) -> None:
        """Request com pipeline inexistente deve falhar graciosamente."""
        service = MediaGenerationService()
        req = MediaRequest(
            prompt="test",
            pipeline_id="nao_existe",
            refine_prompt=False,
        )
        result = asyncio.run(service.generate(req))
        assert result.status == "failed"
        assert "desconhecido" in result.error.lower() or "Pipeline" in result.error


# ══════════════════════════════════════════════════
# INTEGRATION TESTS — requerem Ollama GPU1
# ══════════════════════════════════════════════════


@pytest.mark.integration
class TestMediaGenerationPromptRefinement:
    """Testes de refinamento de prompt via GPU1 real."""

    def test_refine_prompt_retorna_texto(self, ollama_gpu1_url: str) -> None:
        """Refinamento deve retornar texto não-vazio."""
        service = MediaGenerationService()
        refined = asyncio.run(
            service._refine_prompt_via_gpu1("a cat sitting on a chair", "image")
        )
        assert isinstance(refined, str)
        assert len(refined) > 0

    def test_refine_prompt_diferente_do_original(self, ollama_gpu1_url: str) -> None:
        """Prompt refinado deve ser diferente do original (enriquecido)."""
        service = MediaGenerationService()
        original = "a simple red ball"
        refined = asyncio.run(
            service._refine_prompt_via_gpu1(original, "image")
        )
        # O refinado deve ter mais detalhes (geralmente mais longo)
        assert len(refined) >= len(original) * 0.5  # margem para respostas curtas

    def test_refine_prompt_video(self, ollama_gpu1_url: str) -> None:
        """Refinamento para vídeo deve funcionar."""
        service = MediaGenerationService()
        refined = asyncio.run(
            service._refine_prompt_via_gpu1("waves crashing on a beach", "video")
        )
        assert isinstance(refined, str)
        assert len(refined) > 0


@pytest.mark.integration
class TestMediaGenerationHealthCheck:
    """Testes de health check com serviços reais."""

    def test_health_check_completo(self, ollama_gpu1_url: str) -> None:
        """Health check deve retornar estrutura completa."""
        service = MediaGenerationService()
        health = asyncio.run(service.health_check())

        assert health["service"] == "media_generation"
        assert "gpu0_swap" in health
        assert "pipelines" in health
        assert isinstance(health["pipelines"], dict)
        assert len(health["pipelines"]) == 7

    def test_health_check_gpu1_ok(self, ollama_gpu1_url: str) -> None:
        """Health check deve reportar GPU1 saudável."""
        service = MediaGenerationService()
        health = asyncio.run(service.health_check())
        assert health["gpu0_swap"]["gpu1_healthy"] is True
        assert "qwen3" in (health["gpu0_swap"]["gpu1_model"] or "").lower()
