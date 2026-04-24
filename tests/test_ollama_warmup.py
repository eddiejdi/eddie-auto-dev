"""Testes unitários para o script de warmup Ollama.

Testa check_gpu_status, warmup_model, run_warmup e show_status
mockando todas as chamadas HTTP.
"""

from __future__ import annotations

import json
import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Adicionar scripts/ ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from ollama_warmup import (
    GPU0_HOST,
    GPU1_HOST,
    GpuStatus,
    WarmupResult,
    _http_request,
    check_gpu_status,
    main,
    run_warmup,
    show_status,
    warmup_model,
)


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def mock_version_response() -> dict:
    """Resposta padrão de /api/version."""
    return {"version": "0.17.6"}


@pytest.fixture
def mock_ps_empty() -> dict:
    """Resposta /api/ps sem modelos carregados."""
    return {"models": []}


@pytest.fixture
def mock_tags_phi4() -> dict:
    """Resposta /api/tags com phi4-mini instalado."""
    return {"models": [{"name": "phi4-mini:latest", "size": 2684354560}]}


@pytest.fixture
def mock_ps_phi4() -> dict:
    """Resposta /api/ps com phi4-mini carregado."""
    return {"models": [{"name": "phi4-mini:latest", "size": 2684354560}]}


@pytest.fixture
def mock_ps_qwen() -> dict:
    """Resposta /api/ps com qwen3:0.6b carregado."""
    return {"models": [{"name": "qwen3:0.6b", "size": 536870912}]}


@pytest.fixture
def mock_generate_response() -> dict:
    """Resposta de /api/generate."""
    return {"model": "phi4-mini", "response": "", "done": True}


# ── Testes: check_gpu_status ─────────────────────────────────────

class TestCheckGpuStatus:
    """Testes para check_gpu_status."""

    def test_gpu_online_com_modelo(
        self, mock_version_response: dict, mock_ps_phi4: dict
    ) -> None:
        """Verifica GPU online com modelo carregado."""
        with patch("ollama_warmup._http_request") as mock_req:
            mock_req.side_effect = [mock_version_response, mock_ps_phi4]
            status = check_gpu_status(GPU0_HOST, "GPU0")

        assert status.online is True
        assert status.version == "0.17.6"
        assert "phi4-mini:latest" in status.loaded_models
        assert status.error == ""

    def test_gpu_online_sem_modelos(
        self, mock_version_response: dict, mock_ps_empty: dict
    ) -> None:
        """Verifica GPU online sem modelos carregados."""
        with patch("ollama_warmup._http_request") as mock_req:
            mock_req.side_effect = [mock_version_response, mock_ps_empty]
            status = check_gpu_status(GPU0_HOST, "GPU0")

        assert status.online is True
        assert status.loaded_models == []

    def test_gpu_offline(self) -> None:
        """Verifica GPU offline."""
        with patch("ollama_warmup._http_request") as mock_req:
            mock_req.side_effect = urllib.error.URLError("Connection refused")
            status = check_gpu_status(GPU0_HOST, "GPU0")

        assert status.online is False
        assert "recusada" in status.error.lower() or "refused" in status.error.lower()

    def test_gpu_erro_generico(self) -> None:
        """Verifica tratamento de erro genérico."""
        with patch("ollama_warmup._http_request") as mock_req:
            mock_req.side_effect = RuntimeError("Unexpected error")
            status = check_gpu_status(GPU1_HOST, "GPU1")

        assert status.online is False
        assert "Unexpected error" in status.error


# ── Testes: warmup_model ──────────────────────────────────────────

class TestWarmupModel:
    """Testes para warmup_model."""

    def test_modelo_ja_carregado(self, mock_ps_phi4: dict) -> None:
        """Pula warmup se modelo já está carregado."""
        with patch("ollama_warmup._http_request") as mock_req:
            mock_req.return_value = mock_ps_phi4
            result = warmup_model(GPU0_HOST, "phi4-mini")

        assert result.success is True
        assert result.already_loaded is True
        assert result.load_time_ms == 0.0

    def test_carrega_modelo_sucesso(
        self, mock_ps_empty: dict, mock_tags_phi4: dict, mock_generate_response: dict
    ) -> None:
        """Carrega modelo com sucesso."""
        with patch("ollama_warmup._http_request") as mock_req:
            mock_req.side_effect = [mock_ps_empty, mock_tags_phi4, mock_generate_response]
            result = warmup_model(GPU0_HOST, "phi4-mini")

        assert result.success is True
        assert result.already_loaded is False
        assert result.load_time_ms > 0

    def test_carrega_modelo_http_error(self, mock_ps_empty: dict, mock_tags_phi4: dict) -> None:
        """Trata erro HTTP ao carregar modelo."""
        http_err = urllib.error.HTTPError(
            "http://test/api/generate", 400, "Bad Request", {},
            MagicMock(read=MagicMock(return_value=b'{"error":"model not found"}'))
        )
        with patch("ollama_warmup._http_request") as mock_req:
            mock_req.side_effect = [mock_ps_empty, mock_tags_phi4, http_err]
            result = warmup_model(GPU0_HOST, "phi4-mini")

        assert result.success is False
        assert "400" in result.error

    def test_carrega_modelo_conexao_recusada(self, mock_ps_empty: dict, mock_tags_phi4: dict) -> None:
        """Trata erro de conexão ao carregar modelo."""
        with patch("ollama_warmup._http_request") as mock_req:
            mock_req.side_effect = [
                mock_ps_empty,
                mock_tags_phi4,
                ConnectionError("Connection refused"),
            ]
            result = warmup_model(GPU0_HOST, "phi4-mini")

        assert result.success is False
        assert "refused" in result.error.lower()

    def test_modelo_com_tag_latest(self, mock_ps_phi4: dict) -> None:
        """Modelo sem tag encontra 'model:latest' carregado."""
        with patch("ollama_warmup._http_request") as mock_req:
            mock_req.return_value = mock_ps_phi4
            result = warmup_model(GPU0_HOST, "phi4-mini")

        assert result.success is True
        assert result.already_loaded is True

    def test_ps_falha_tenta_carregar(
        self, mock_tags_phi4: dict, mock_generate_response: dict
    ) -> None:
        """Se /api/ps falha, tenta carregar mesmo assim."""
        with patch("ollama_warmup._http_request") as mock_req:
            mock_req.side_effect = [
                ConnectionError("ps failed"),
                mock_tags_phi4,
                mock_generate_response,
            ]
            result = warmup_model(GPU0_HOST, "phi4-mini")

        assert result.success is True
        assert result.already_loaded is False

    def test_falha_rapido_se_modelo_nao_instalado(self, mock_ps_empty: dict) -> None:
        """Retorna erro antes do cold load quando o modelo não existe."""
        with patch("ollama_warmup._http_request") as mock_req:
            mock_req.side_effect = [mock_ps_empty, {"models": [{"name": "qwen3:0.6b"}]}]
            result = warmup_model(GPU0_HOST, "phi4-mini")

        assert result.success is False
        assert "não está instalado" in result.error


# ── Testes: run_warmup ────────────────────────────────────────────

class TestRunWarmup:
    """Testes para run_warmup."""

    def test_ambas_gpus_warm(self) -> None:
        """Ambas GPUs já com modelos carregados."""
        with patch("ollama_warmup.check_gpu_status") as mock_status, \
             patch("ollama_warmup.warmup_model") as mock_warmup:
            mock_status.side_effect = [
                GpuStatus(host=GPU0_HOST, name="GPU0", online=True, version="0.17.6"),
                GpuStatus(host=GPU1_HOST, name="GPU1", online=True, version="0.17.6"),
            ]
            mock_warmup.side_effect = [
                WarmupResult(host=GPU0_HOST, model="phi4-mini", success=True, already_loaded=True),
                WarmupResult(host=GPU1_HOST, model="qwen3:0.6b", success=True, already_loaded=True),
            ]
            results, all_ok = run_warmup()

        assert all_ok is True
        assert len(results) == 2
        assert all(r.success for r in results)

    def test_gpu1_offline(self) -> None:
        """GPU1 offline não impede GPU0."""
        with patch("ollama_warmup.check_gpu_status") as mock_status, \
             patch("ollama_warmup.warmup_model") as mock_warmup:
            mock_status.side_effect = [
                GpuStatus(host=GPU0_HOST, name="GPU0", online=True, version="0.17.6"),
                GpuStatus(host=GPU1_HOST, name="GPU1", online=False, error="Connection refused"),
            ]
            mock_warmup.return_value = WarmupResult(
                host=GPU0_HOST, model="phi4-mini", success=True, already_loaded=True,
            )
            results, all_ok = run_warmup()

        assert all_ok is False  # GPU1 falhou
        assert len(results) == 2
        assert results[0].success is True  # GPU0 OK
        assert results[1].success is False  # GPU1 falhou

    def test_ambas_offline(self) -> None:
        """Ambas GPUs offline."""
        with patch("ollama_warmup.check_gpu_status") as mock_status:
            mock_status.side_effect = [
                GpuStatus(host=GPU0_HOST, name="GPU0", online=False, error="offline"),
                GpuStatus(host=GPU1_HOST, name="GPU1", online=False, error="offline"),
            ]
            results, all_ok = run_warmup()

        assert all_ok is False
        assert len(results) == 2
        assert all(not r.success for r in results)

    def test_warmup_falha_parcial(self) -> None:
        """Um modelo falha, outro sucesso."""
        with patch("ollama_warmup.check_gpu_status") as mock_status, \
             patch("ollama_warmup.warmup_model") as mock_warmup:
            mock_status.side_effect = [
                GpuStatus(host=GPU0_HOST, name="GPU0", online=True, version="0.17.6"),
                GpuStatus(host=GPU1_HOST, name="GPU1", online=True, version="0.17.6"),
            ]
            mock_warmup.side_effect = [
                WarmupResult(host=GPU0_HOST, model="phi4-mini", success=False, error="OOM"),
                WarmupResult(host=GPU1_HOST, model="qwen3:0.6b", success=True, load_time_ms=500),
            ]
            results, all_ok = run_warmup()

        assert all_ok is False
        assert results[0].success is False
        assert results[1].success is True


# ── Testes: show_status ──────────────────────────────────────────

class TestShowStatus:
    """Testes para show_status."""

    def test_show_status_online(self) -> None:
        """Exibe status de GPUs online."""
        with patch("ollama_warmup.check_gpu_status") as mock_status:
            mock_status.side_effect = [
                GpuStatus(
                    host=GPU0_HOST, name="GPU0", online=True,
                    version="0.17.6", loaded_models=["phi4-mini:latest"],
                ),
                GpuStatus(
                    host=GPU1_HOST, name="GPU1", online=True,
                    version="0.17.6", loaded_models=["qwen3:0.6b"],
                ),
            ]
            show_status()

        assert mock_status.call_count == 2

    def test_show_status_offline(self) -> None:
        """Exibe status de GPUs offline."""
        with patch("ollama_warmup.check_gpu_status") as mock_status:
            mock_status.side_effect = [
                GpuStatus(host=GPU0_HOST, name="GPU0", online=False, error="timeout"),
                GpuStatus(host=GPU1_HOST, name="GPU1", online=False, error="refused"),
            ]
            show_status()

        assert mock_status.call_count == 2


# ── Testes: main ──────────────────────────────────────────────────

class TestMain:
    """Testes para o entrypoint main."""

    def test_main_warmup_sucesso(self) -> None:
        """main() retorna 0 quando tudo OK."""
        with patch("ollama_warmup.run_warmup") as mock_run, \
             patch("sys.argv", ["warmup"]):
            mock_run.return_value = (
                [WarmupResult(host=GPU0_HOST, model="phi4-mini", success=True, already_loaded=True)],
                True,
            )
            assert main() == 0

    def test_main_warmup_falha(self) -> None:
        """main() retorna 1 quando há falha."""
        with patch("ollama_warmup.run_warmup") as mock_run, \
             patch("sys.argv", ["warmup"]):
            mock_run.return_value = (
                [WarmupResult(host=GPU0_HOST, model="phi4-mini", success=False, error="failed")],
                False,
            )
            assert main() == 1

    def test_main_status_mode(self) -> None:
        """main() com --status chama show_status."""
        with patch("ollama_warmup.show_status") as mock_show, \
             patch("sys.argv", ["warmup", "--status"]):
            assert main() == 0
            mock_show.assert_called_once()


# ── Testes: _http_request ────────────────────────────────────────

class TestHttpRequest:
    """Testes para _http_request."""

    def test_get_request(self) -> None:
        """GET request retorna JSON."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"version": "0.17.6"}'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = _http_request("http://localhost/api/version")

        assert result["version"] == "0.17.6"

    def test_post_request(self) -> None:
        """POST request envia dados e retorna JSON."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"done": true}'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            result = _http_request(
                "http://localhost/api/generate",
                data={"model": "phi4-mini", "prompt": "test"},
            )

        assert result["done"] is True
        # Verifica que foi criada uma Request com data
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.data is not None


# ── Testes: GpuStatus e WarmupResult ─────────────────────────────

class TestDataClasses:
    """Testes para data classes."""

    def test_gpu_status_defaults(self) -> None:
        """GpuStatus tem defaults corretos."""
        status = GpuStatus(host="http://test", name="GPU0")
        assert status.online is False
        assert status.version == ""
        assert status.loaded_models == []
        assert status.error == ""

    def test_warmup_result_defaults(self) -> None:
        """WarmupResult tem defaults corretos."""
        result = WarmupResult(host="http://test", model="phi4-mini")
        assert result.success is False
        assert result.already_loaded is False
        assert result.load_time_ms == 0.0
        assert result.error == ""

    def test_gpu_status_completo(self) -> None:
        """GpuStatus com todos os campos."""
        status = GpuStatus(
            host="http://192.168.15.2:11434",
            name="GPU0",
            online=True,
            version="0.17.6",
            loaded_models=["phi4-mini:latest"],
        )
        assert status.host == "http://192.168.15.2:11434"
        assert len(status.loaded_models) == 1


# ── Testes: Configuração ─────────────────────────────────────────

class TestConfig:
    """Testes para constantes de configuração."""

    def test_gpu_hosts(self) -> None:
        """Hosts das GPUs estão corretos."""
        assert GPU0_HOST == "http://192.168.15.2:11434"
        assert GPU1_HOST == "http://192.168.15.2:11435"

    def test_gpu0_modelo_padrao(self) -> None:
        """GPU0 aquece o modelo de produção configurado."""
        from ollama_warmup import GPU0_MODELS
        assert "trading-analyst:latest" in GPU0_MODELS

    def test_gpu1_modelo_padrao(self) -> None:
        """GPU1 tem qwen3:0.6b como padrão."""
        from ollama_warmup import GPU1_MODELS
        assert "qwen3:0.6b" in GPU1_MODELS

    def test_keep_alive_permanente(self) -> None:
        """keep_alive é -1 (permanente)."""
        from ollama_warmup import KEEP_ALIVE
        assert KEEP_ALIVE == -1
