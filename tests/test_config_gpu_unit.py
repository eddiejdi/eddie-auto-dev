#!/usr/bin/env python3
"""
Testes unitários para configurações GPU1 e Media Generation.

Valida que as constantes em config.py e os arquivos JSON de self-heal
apontam para GPU1 (:11435) com qwen3:0.6b, sem mocks.

Nota: importa config.py diretamente (sem __init__.py) para evitar
imports pesados do pacote specialized_agents.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# ── Import direto do config.py (bypass __init__.py pesado) ──
_CONFIG_PATH = Path(__file__).parent.parent / "specialized_agents" / "config.py"
_spec = importlib.util.spec_from_file_location("sa_config", str(_CONFIG_PATH))
_config_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_config_mod)

LLM_GPU1_CONFIG = _config_mod.LLM_GPU1_CONFIG
MEDIA_GENERATION_CONFIG = _config_mod.MEDIA_GENERATION_CONFIG


class TestLLMGPU1Config:
    """Testes da configuração LLM_GPU1_CONFIG em config.py."""

    def test_gpu1_enabled(self) -> None:
        """GPU1 deve estar habilitada por padrão."""
        assert LLM_GPU1_CONFIG["enabled"] is True

    def test_gpu1_base_url_porta_11435(self) -> None:
        """Base URL deve apontar para porta 11435 (GPU1)."""
        assert ":11435" in LLM_GPU1_CONFIG["base_url"]
        assert "192.168.15.2" in LLM_GPU1_CONFIG["base_url"]

    def test_gpu1_model_qwen3(self) -> None:
        """Modelo deve ser qwen3:0.6b (cabe em 2GB VRAM)."""
        assert LLM_GPU1_CONFIG["model"] == "qwen3:0.6b"

    def test_gpu1_backend_cuda_v12(self) -> None:
        """Backend deve ser cuda_v12 (CC 6.1 da GTX 1050)."""
        assert LLM_GPU1_CONFIG["backend"] == "cuda_v12"

    def test_gpu1_keep_alive_permanente(self) -> None:
        """keep_alive=-1 mantém modelo carregado permanentemente."""
        assert LLM_GPU1_CONFIG["keep_alive"] == -1

    def test_gpu1_controller_roles(self) -> None:
        """GPU1 deve ter roles de controller definidos."""
        roles = LLM_GPU1_CONFIG["controller_roles"]
        assert "media_orchestration" in roles
        assert "btc_selfheal" in roles
        assert "light_inference" in roles

    def test_gpu1_task_keywords_contém_selfheal(self) -> None:
        """Keywords de roteamento devem incluir selfheal e media."""
        keywords = LLM_GPU1_CONFIG["task_keywords"]
        assert "selfheal" in keywords
        assert "media" in keywords
        assert "video" in keywords

    def test_gpu1_expert_keywords_protege_tarefas_complexas(self) -> None:
        """Tarefas complexas nunca devem ir para GPU1."""
        expert = LLM_GPU1_CONFIG["expert_keywords"]
        assert "refatorar" in expert or "refactor" in expert
        assert "code" in expert or "código" in expert

    def test_gpu1_timeout_razoavel(self) -> None:
        """Timeout deve ser entre 30 e 120 segundos."""
        assert 30 <= LLM_GPU1_CONFIG["timeout"] <= 120


class TestMediaGenerationConfig:
    """Testes da configuração MEDIA_GENERATION_CONFIG em config.py."""

    def test_media_enabled(self) -> None:
        """Serviço de media deve estar habilitado."""
        assert MEDIA_GENERATION_CONFIG["enabled"] is True

    def test_media_device_cuda0(self) -> None:
        """Device deve ser cuda:0 (GPU0 RTX 2060)."""
        assert MEDIA_GENERATION_CONFIG["device"] == "cuda:0"

    def test_media_models_dir_raid(self) -> None:
        """Modelos em /mnt/raid1/models (RAID com espaço)."""
        models_dir = str(MEDIA_GENERATION_CONFIG["models_dir"])
        assert "/mnt/raid1/models" in models_dir

    def test_media_7_pipelines_configurados(self) -> None:
        """Devem existir exatamente 7 pipelines."""
        pipelines = MEDIA_GENERATION_CONFIG["pipelines"]
        assert len(pipelines) == 7

    def test_media_pipelines_imagem(self) -> None:
        """3 pipelines de imagem: sd15, sdxl_turbo, sd3_medium."""
        pipelines = MEDIA_GENERATION_CONFIG["pipelines"]
        image_pids = [p for p, cfg in pipelines.items() if cfg["type"] == "image"]
        assert sorted(image_pids) == ["sd15", "sd3_medium", "sdxl_turbo"]

    def test_media_pipelines_video(self) -> None:
        """4 pipelines de vídeo: cogvideo, ltx, wan, animatediff."""
        pipelines = MEDIA_GENERATION_CONFIG["pipelines"]
        video_pids = [p for p, cfg in pipelines.items() if cfg["type"] == "video"]
        assert len(video_pids) == 4
        assert "cogvideo_2b" in video_pids
        assert "animatediff" in video_pids

    def test_media_pipeline_vram_dentro_de_8gb(self) -> None:
        """Cada pipeline deve caber na GPU0 (< 8GB VRAM)."""
        for pid, cfg in MEDIA_GENERATION_CONFIG["pipelines"].items():
            assert cfg["vram_gb"] < 8.0, f"Pipeline {pid} requer {cfg['vram_gb']}GB > 8GB"

    def test_media_pipeline_tem_campos_obrigatorios(self) -> None:
        """Cada pipeline deve ter type, name, model_id, vram_gb, default_steps, default_size."""
        required = {"type", "name", "model_id", "vram_gb", "default_steps", "default_size"}
        for pid, cfg in MEDIA_GENERATION_CONFIG["pipelines"].items():
            missing = required - set(cfg.keys())
            assert not missing, f"Pipeline {pid} falta campos: {missing}"

    def test_media_swap_timeouts(self) -> None:
        """Timeouts de swap devem ser razoáveis."""
        assert MEDIA_GENERATION_CONFIG["swap_unload_timeout_s"] >= 10
        assert MEDIA_GENERATION_CONFIG["swap_reload_timeout_s"] >= 30


class TestBTCSelfHealConfig:
    """Testes dos arquivos JSON de self-heal migrados para GPU1."""

    def test_trading_selfheal_aponta_gpu1(self, selfheal_config: dict) -> None:
        """Config do trading agent deve apontar para GPU1 :11435."""
        ollama = selfheal_config["ollama"]
        assert ":11435" in ollama["host"]
        assert "192.168.15.2" in ollama["host"]

    def test_trading_selfheal_modelo_qwen3(self, selfheal_config: dict) -> None:
        """Modelo do self-heal deve ser qwen3:0.6b."""
        assert selfheal_config["ollama"]["model"] == "qwen3:0.6b"

    def test_trading_selfheal_postgresql_porta_5433(self, selfheal_config: dict) -> None:
        """PostgreSQL deve usar porta 5433."""
        pg = selfheal_config["postgresql"]
        assert pg["port"] == 5433
        assert pg["schema"] == "btc"

    def test_trading_selfheal_agentes_habilitados(self, selfheal_config: dict) -> None:
        """Deve ter pelo menos 5 agentes configurados (BTC, ETH, XRP, SOL, DOGE...)."""
        agents = selfheal_config["agents"]
        assert len(agents) >= 5
        symbols = [a["symbol"] for a in agents]
        assert "BTC-USDT" in symbols

    def test_grafana_selfheal_aponta_gpu1(self, grafana_selfheal_config: dict) -> None:
        """Config do Grafana exporter deve apontar para GPU1 :11435."""
        assert ":11435" in grafana_selfheal_config["ollama_host"]

    def test_grafana_selfheal_modelo_qwen3(self, grafana_selfheal_config: dict) -> None:
        """Modelo do Grafana exporter deve ser qwen3:0.6b."""
        assert grafana_selfheal_config["ollama_model"] == "qwen3:0.6b"

    def test_grafana_selfheal_agentes(self, grafana_selfheal_config: dict) -> None:
        """Grafana exporter deve listar agentes de trading."""
        agents = grafana_selfheal_config["agents"]
        assert len(agents) >= 5
        symbols = [a["symbol"] for a in agents]
        assert "BTC" in symbols
