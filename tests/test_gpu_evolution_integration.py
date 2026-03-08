#!/usr/bin/env python3
"""
Testes de integração para a evolução GPU completa.

Valida em tempo real:
- GPU1 Ollama rodando com CUDA cuda_v12
- qwen3:0.6b carregado permanentemente (Forever)
- Inferência real na GPU1
- Consistência dos configs BTC self-heal
- post-boot-check.sh retorna 0 FAIL
Sem mocks — tudo bate em serviços reais.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

# ── Import direto do config.py (bypass __init__.py pesado) ──
_SA_DIR = Path(__file__).parent.parent / "specialized_agents"
if "specialized_agents.config" not in sys.modules:
    _spec_cfg = importlib.util.spec_from_file_location(
        "specialized_agents.config", str(_SA_DIR / "config.py")
    )
    _config_mod = importlib.util.module_from_spec(_spec_cfg)
    sys.modules["specialized_agents.config"] = _config_mod
    _spec_cfg.loader.exec_module(_config_mod)

_config = sys.modules["specialized_agents.config"]
LLM_GPU1_CONFIG = _config.LLM_GPU1_CONFIG


@pytest.mark.integration
class TestGPU1OllamaService:
    """Testes do serviço Ollama na GPU1 via rede."""

    def test_gpu1_api_acessivel(self, ollama_gpu1_url: str) -> None:
        """API da GPU1 (:11435) deve responder."""
        resp = httpx.get(f"{ollama_gpu1_url}/api/tags", timeout=5)
        assert resp.status_code == 200

    def test_gpu1_modelo_qwen3_carregado(self, gpu1_model_info: dict) -> None:
        """qwen3:0.6b deve estar carregado na GPU1."""
        model_name = gpu1_model_info.get("name", "")
        assert "qwen3" in model_name.lower(), f"Modelo inesperado: {model_name}"

    def test_gpu1_modelo_forever(self, gpu1_model_info: dict) -> None:
        """Modelo da GPU1 deve ter expiração muito distante (keep_alive=-1)."""
        expires = gpu1_model_info.get("expires_at", "")
        # Ollama com keep_alive=-1 pode retornar:
        # - "0001-01-01T00:00:00Z" (literalmente Never)
        # - Uma data centenas de anos no futuro (ex: 2318)
        # Ambos indicam modelo permanente
        from datetime import datetime
        try:
            # Extrair ano da data ISO
            year = int(expires[:4])
            # Se o ano é > 2100, é efetivamente "Forever"
            assert year > 2100 or year == 1, (
                f"expires_at indica expiração em {year}, "
                f"esperado > 2100 ou 0001 para Forever: {expires}"
            )
        except (ValueError, IndexError):
            pytest.fail(f"Não foi possível parsear expires_at: {expires}")

    def test_gpu1_vram_acima_500mb(self, gpu1_model_info: dict) -> None:
        """GPU1 deve estar usando > 500 MiB de VRAM com o modelo."""
        size_vram = gpu1_model_info.get("size_vram", 0)
        # size_vram está em bytes, converter para MiB
        size_mb = size_vram / (1024 * 1024)
        assert size_mb > 500, f"VRAM usada muito baixa: {size_mb:.0f} MiB"

    def test_gpu1_modelo_100_percent_gpu(self, gpu1_model_info: dict) -> None:
        """Modelo deve estar 100% na GPU (sem offload para CPU)."""
        size = gpu1_model_info.get("size", 0)
        size_vram = gpu1_model_info.get("size_vram", 0)
        if size > 0:
            gpu_pct = (size_vram / size) * 100
            assert gpu_pct >= 95, f"Apenas {gpu_pct:.0f}% na GPU (esperado 100%)"


@pytest.mark.integration
class TestGPU1InferenciaReal:
    """Testes de inferência real na GPU1."""

    def test_gpu1_generate_responde(self, ollama_gpu1_url: str) -> None:
        """GPU1 deve gerar resposta para prompt simples."""
        resp = httpx.post(
            f"{ollama_gpu1_url}/api/generate",
            json={
                "model": "qwen3:0.6b",
                "prompt": "What is 2+2? Answer with just the number.",
                "stream": False,
            },
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data
        assert len(data["response"]) > 0

    def test_gpu1_velocidade_acima_40_toks(self, ollama_gpu1_url: str) -> None:
        """GPU1 CUDA deve manter > 40 tok/s."""
        resp = httpx.post(
            f"{ollama_gpu1_url}/api/generate",
            json={
                "model": "qwen3:0.6b",
                "prompt": "List 5 colors.",
                "stream": False,
            },
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()

        # eval_count / eval_duration (ns → s)
        eval_count = data.get("eval_count", 0)
        eval_duration_ns = data.get("eval_duration", 1)
        if eval_count > 0 and eval_duration_ns > 0:
            toks_per_sec = eval_count / (eval_duration_ns / 1e9)
            assert toks_per_sec > 40, (
                f"Velocidade {toks_per_sec:.1f} tok/s < 40 tok/s — "
                "CUDA pode não estar ativo"
            )


@pytest.mark.integration
class TestGPU0OllamaService:
    """Testes do serviço Ollama na GPU0."""

    def test_gpu0_api_acessivel(self, ollama_gpu0_url: str) -> None:
        """API da GPU0 (:11434) deve responder."""
        resp = httpx.get(f"{ollama_gpu0_url}/api/tags", timeout=5)
        assert resp.status_code == 200

    def test_gpu0_tem_modelos(self, ollama_gpu0_url: str) -> None:
        """GPU0 deve ter pelo menos 1 modelo disponível."""
        resp = httpx.get(f"{ollama_gpu0_url}/api/tags", timeout=5)
        models = resp.json().get("models", [])
        assert len(models) >= 1


@pytest.mark.integration
class TestBTCSelfHealMigracao:
    """Testes de integração validando a migração do BTC self-heal para GPU1."""

    def test_config_json_consistente_com_config_py(self, selfheal_config: dict) -> None:
        """JSON do self-heal deve ser consistente com LLM_GPU1_CONFIG."""
        ollama_cfg = selfheal_config["ollama"]

        # Ambos devem apontar para GPU1
        assert ":11435" in ollama_cfg["host"]
        assert ":11435" in LLM_GPU1_CONFIG["base_url"]

        # Mesmo modelo
        assert ollama_cfg["model"] == LLM_GPU1_CONFIG["model"]

    def test_selfheal_aponta_para_gpu1_real(
        self, selfheal_config: dict, ollama_gpu1_url: str
    ) -> None:
        """Self-heal deve apontar para a mesma GPU1 que está rodando."""
        ollama_host = selfheal_config["ollama"]["host"]
        # Verificar que o host do config é acessível
        resp = httpx.get(f"{ollama_host}/api/tags", timeout=5)
        assert resp.status_code == 200

    def test_grafana_exporter_consistente(
        self, selfheal_config: dict, grafana_selfheal_config: dict
    ) -> None:
        """Grafana exporter deve ter mesmo host/modelo que trading config."""
        assert ":11435" in grafana_selfheal_config["ollama_host"]
        assert grafana_selfheal_config["ollama_model"] == selfheal_config["ollama"]["model"]


@pytest.mark.integration
class TestSelfHealExporterConfig:
    """Testes dos defaults no exporter Python."""

    def test_exporter_defaults_gpu1(self) -> None:
        """Defaults do exporter .py devem apontar para GPU1."""
        exporter_path = (
            Path(__file__).parent.parent
            / "btc_trading_agent"
            / "trading_selfheal_exporter.py"
        )
        if not exporter_path.exists():
            pytest.skip("Exporter não encontrado")

        text = exporter_path.read_text()
        assert ":11435" in text, "Exporter deve ter default :11435"
        assert "qwen3:0.6b" in text, "Exporter deve ter default qwen3:0.6b"

    def test_systemd_service_gpu1(self) -> None:
        """Systemd service do exporter deve usar GPU1."""
        service_path = (
            Path(__file__).parent.parent
            / "btc_trading_agent"
            / "systemd"
            / "trading-selfheal-exporter.service"
        )
        if not service_path.exists():
            pytest.skip("Service file não encontrado")

        text = service_path.read_text()
        assert ":11435" in text or "GPU1" in text, "Service deve referenciar GPU1"


@pytest.mark.integration
class TestPostBootCheck:
    """Testes do script post-boot-check.sh."""

    def test_post_boot_check_existe(self) -> None:
        """Script v3.0 deve existir."""
        script = Path(__file__).parent.parent / "systemd" / "post-boot-check.sh"
        assert script.exists(), f"Script não encontrado: {script}"

    def test_post_boot_check_v3(self) -> None:
        """Script deve ser versão 3.0+."""
        script = Path(__file__).parent.parent / "systemd" / "post-boot-check.sh"
        text = script.read_text()
        # Verifica que contém referência à versão 3
        assert "v3" in text.lower() or "3.0" in text, "Script deve ser v3.0+"

    def test_post_boot_check_verifica_gpu1(self) -> None:
        """Script deve verificar GPU1 (:11435)."""
        script = Path(__file__).parent.parent / "systemd" / "post-boot-check.sh"
        text = script.read_text()
        assert "11435" in text, "Script deve checar porta 11435 (GPU1)"
        assert "qwen3" in text.lower(), "Script deve checar qwen3"

    def test_post_boot_check_0_fail_remoto(self) -> None:
        """Executar post-boot-check.sh no servidor deve resultar em 0 FAIL."""
        script = Path(__file__).parent.parent / "systemd" / "post-boot-check.sh"
        if not script.exists():
            pytest.skip("Script não encontrado")

        result = subprocess.run(
            [
                "ssh", "-o", "ConnectTimeout=5", "homelab@192.168.15.2",
                "bash", "/opt/shared/systemd/post-boot-check.sh",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        # Extrair contagem de FAIL da saída
        output = result.stdout + result.stderr
        fail_count = output.count("[FAIL]")
        assert fail_count == 0, (
            f"post-boot-check.sh reportou {fail_count} FAIL(s):\n{output[-500:]}"
        )
