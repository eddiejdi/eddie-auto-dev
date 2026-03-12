"""Testes unitários para o pipeline de fine-tuning batch do eddie-sentiment."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

# Importar módulo sob teste
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import ollama_finetune_batch as ft


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    """Diretório temporário para outputs do fine-tuning."""
    out = tmp_path / "finetune_output"
    out.mkdir()
    return out


@pytest.fixture
def tmp_backup_dir(tmp_path: Path) -> Path:
    """Diretório temporário para backups."""
    bk = tmp_path / "backups"
    bk.mkdir()
    return bk


@pytest.fixture
def sample_training_data(tmp_path: Path) -> Path:
    """Cria arquivo JSONL de treinamento de exemplo."""
    data_path = tmp_path / "training_data.jsonl"
    entries = []
    for i in range(5):
        entries.append({
            "instruction": f"Analyze crypto news {i}",
            "input": "",
            "output": f"SENTIMENT: 0.{i}5 | CONFIDENCE: 0.85 | DIRECTION: BULLISH | CATEGORY: adoption",
        })
    data_path.write_text(
        "\n".join(json.dumps(e) for e in entries) + "\n",
        encoding="utf-8",
    )
    return data_path


@pytest.fixture
def sample_backups(tmp_backup_dir: Path) -> list[Path]:
    """Cria backups de exemplo com idades diferentes."""
    backups = []
    now = time.time()
    for i, age_days in enumerate([1, 10, 20, 35, 60]):
        bk = tmp_backup_dir / f"eddie-sentiment_pre-finetune_2026{i:02d}01_030000.json"
        bk.write_text(json.dumps({"modelfile": f"backup_{i}"}), encoding="utf-8")
        # Ajustar mtime para simular idade
        mtime = now - (age_days * 86400)
        import os
        os.utime(bk, (mtime, mtime))
        backups.append(bk)
    return backups


# ── Testes de is_ollama_running ────────────────────────────────────────────────


class TestIsOllamaRunning:
    """Testes para verificação de status do Ollama."""

    @patch("ollama_finetune_batch.urllib.request.urlopen")
    def test_running(self, mock_urlopen: MagicMock) -> None:
        """Retorna True quando Ollama responde."""
        mock_urlopen.return_value.__enter__ = MagicMock()
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        assert ft.is_ollama_running("http://localhost:11434") is True

    @patch("ollama_finetune_batch.urllib.request.urlopen")
    def test_not_running(self, mock_urlopen: MagicMock) -> None:
        """Retorna False quando Ollama não responde."""
        mock_urlopen.side_effect = ConnectionRefusedError("Connection refused")
        assert ft.is_ollama_running("http://localhost:11434") is False

    @patch("ollama_finetune_batch.urllib.request.urlopen")
    def test_timeout(self, mock_urlopen: MagicMock) -> None:
        """Retorna False quando dá timeout."""
        mock_urlopen.side_effect = TimeoutError("Timeout")
        assert ft.is_ollama_running("http://localhost:11434") is False


# ── Testes de stop_ollama_gpu0 ─────────────────────────────────────────────────


class TestStopOllamaGpu0:
    """Testes para parada do Ollama GPU0."""

    @patch("ollama_finetune_batch.is_ollama_running", return_value=False)
    @patch("ollama_finetune_batch.time.sleep")
    @patch("ollama_finetune_batch.subprocess.run")
    def test_stop_success(
        self, mock_run: MagicMock, mock_sleep: MagicMock, mock_running: MagicMock
    ) -> None:
        """Para com sucesso quando systemctl funciona."""
        assert ft.stop_ollama_gpu0() is True
        # Deve chamar stop 2x (ollama + warmup timer)
        assert mock_run.call_count == 2

    @patch("ollama_finetune_batch.subprocess.run")
    def test_stop_timeout(self, mock_run: MagicMock) -> None:
        """Retorna False quando systemctl dá timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="stop", timeout=30)
        assert ft.stop_ollama_gpu0() is False

    @patch("ollama_finetune_batch.is_ollama_running", return_value=True)
    @patch("ollama_finetune_batch.time.sleep")
    @patch("ollama_finetune_batch.subprocess.run")
    def test_stop_still_running(
        self, mock_run: MagicMock, mock_sleep: MagicMock, mock_running: MagicMock
    ) -> None:
        """Retorna False se ainda está rodando após stop."""
        assert ft.stop_ollama_gpu0() is False


# ── Testes de start_ollama_gpu0 ────────────────────────────────────────────────


class TestStartOllamaGpu0:
    """Testes para reinício do Ollama GPU0."""

    @patch("ollama_finetune_batch.is_ollama_running", return_value=True)
    @patch("ollama_finetune_batch.time.sleep")
    @patch("ollama_finetune_batch.subprocess.run")
    def test_start_success(
        self, mock_run: MagicMock, mock_sleep: MagicMock, mock_running: MagicMock
    ) -> None:
        """Inicia com sucesso."""
        assert ft.start_ollama_gpu0() is True

    @patch("ollama_finetune_batch.is_ollama_running", return_value=False)
    @patch("ollama_finetune_batch.time.sleep")
    @patch("ollama_finetune_batch.subprocess.run")
    def test_start_never_comes_up(
        self, mock_run: MagicMock, mock_sleep: MagicMock, mock_running: MagicMock
    ) -> None:
        """Retorna False se não fica online."""
        assert ft.start_ollama_gpu0() is False


# ── Testes de validate_model ───────────────────────────────────────────────────


class TestValidateModel:
    """Testes para validação do modelo fine-tuned."""

    @patch("ollama_finetune_batch.urllib.request.urlopen")
    def test_all_pass(self, mock_urlopen: MagicMock) -> None:
        """Validação OK quando todas as respostas corretas."""
        responses = [
            b'{"response": "SENTIMENT: 0.90 | CONFIDENCE: 0.95 | DIRECTION: BULLISH | CATEGORY: adoption"}',
            b'{"response": "SENTIMENT: -0.85 | CONFIDENCE: 0.90 | DIRECTION: BEARISH | CATEGORY: hack"}',
            b'{"response": "SENTIMENT: 0.80 | CONFIDENCE: 0.85 | DIRECTION: BULLISH | CATEGORY: technical"}',
            b'{"response": "SENTIMENT: -0.80 | CONFIDENCE: 0.88 | DIRECTION: BEARISH | CATEGORY: regulation"}',
        ]
        mock_ctx = MagicMock()
        mock_urlopen.return_value.__enter__ = MagicMock(side_effect=[
            MagicMock(read=MagicMock(return_value=r)) for r in responses
        ])

        # Simular 4 respostas sequenciais
        call_idx = {"i": 0}
        def fake_urlopen(req, timeout=60):
            ctx = MagicMock()
            ctx.read.return_value = responses[call_idx["i"]]
            call_idx["i"] += 1
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        mock_urlopen.side_effect = fake_urlopen

        stable, passed, total = ft.validate_model()
        assert stable is True
        assert passed == 4
        assert total == 4

    @patch("ollama_finetune_batch.urllib.request.urlopen")
    def test_all_fail(self, mock_urlopen: MagicMock) -> None:
        """Instável quando nenhuma resposta correta."""
        def fake_urlopen(req, timeout=60):
            ctx = MagicMock()
            ctx.read.return_value = b'{"response": "SENTIMENT: 0.00 | DIRECTION: NEUTRAL"}'
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        mock_urlopen.side_effect = fake_urlopen

        stable, passed, total = ft.validate_model()
        assert stable is False
        assert passed == 0

    @patch("ollama_finetune_batch.urllib.request.urlopen")
    def test_connection_error(self, mock_urlopen: MagicMock) -> None:
        """Trata erros de conexão sem crash."""
        mock_urlopen.side_effect = ConnectionRefusedError()

        stable, passed, total = ft.validate_model()
        assert stable is False
        assert passed == 0
        assert total == 4


# ── Testes de cleanup_old_backups ──────────────────────────────────────────────


class TestCleanupOldBackups:
    """Testes para limpeza de backups antigos."""

    def test_no_backup_dir(self, tmp_path: Path) -> None:
        """Retorna 0 se diretório não existe."""
        with patch.object(ft, "BACKUP_DIR", tmp_path / "nonexistent"):
            assert ft.cleanup_old_backups() == 0

    def test_empty_backup_dir(self, tmp_backup_dir: Path) -> None:
        """Retorna 0 se diretório vazio."""
        with patch.object(ft, "BACKUP_DIR", tmp_backup_dir):
            assert ft.cleanup_old_backups() == 0

    def test_retains_recent_backups(
        self, tmp_backup_dir: Path, sample_backups: list[Path]
    ) -> None:
        """Mantém os N backups mais recentes."""
        with patch.object(ft, "BACKUP_DIR", tmp_backup_dir), \
             patch.object(ft, "OUTPUT_DIR", tmp_backup_dir / "output"):
            removed = ft.cleanup_old_backups(force=False)
            remaining = list(tmp_backup_dir.glob("eddie-sentiment_pre-finetune_*.json"))
            # 5 backups, retention=3, 2 oldest (35d e 60d) excedem MAX_AGE_DAYS=30
            assert removed == 2
            assert len(remaining) == 3

    def test_force_removes_all_extra(
        self, tmp_backup_dir: Path, sample_backups: list[Path]
    ) -> None:
        """Force=True remove todos além da retenção."""
        with patch.object(ft, "BACKUP_DIR", tmp_backup_dir), \
             patch.object(ft, "OUTPUT_DIR", tmp_backup_dir / "output"):
            removed = ft.cleanup_old_backups(force=True)
            remaining = list(tmp_backup_dir.glob("eddie-sentiment_pre-finetune_*.json"))
            assert removed == 2
            assert len(remaining) == 3

    def test_cleans_temp_dirs(self, tmp_backup_dir: Path) -> None:
        """Limpa diretórios temporários de treino."""
        output_dir = tmp_backup_dir / "output"
        output_dir.mkdir()
        for subdir in ["gguf", "lora_adapters", "merged_model"]:
            d = output_dir / subdir
            d.mkdir()
            (d / "dummy.bin").write_text("data")

        with patch.object(ft, "BACKUP_DIR", tmp_backup_dir), \
             patch.object(ft, "OUTPUT_DIR", output_dir), \
             patch.object(ft, "LORA_OUTPUT", output_dir / "lora_adapters"), \
             patch.object(ft, "MERGED_OUTPUT", output_dir / "merged_model"):
            ft.cleanup_old_backups()
            assert not (output_dir / "gguf").exists()
            assert not (output_dir / "lora_adapters").exists()
            assert not (output_dir / "merged_model").exists()

    def test_cleans_old_jsonl(self, tmp_backup_dir: Path) -> None:
        """Remove JSONL de treino com mais de 7 dias."""
        output_dir = tmp_backup_dir / "output"
        output_dir.mkdir()
        old_jsonl = output_dir / "training_data.jsonl"
        old_jsonl.write_text('{"test": true}')
        import os
        old_mtime = time.time() - (10 * 86400)  # 10 dias
        os.utime(old_jsonl, (old_mtime, old_mtime))

        with patch.object(ft, "BACKUP_DIR", tmp_backup_dir), \
             patch.object(ft, "OUTPUT_DIR", output_dir):
            ft.cleanup_old_backups()
            assert not old_jsonl.exists()


# ── Testes de write_run_report ─────────────────────────────────────────────────


class TestWriteRunReport:
    """Testes para gravação do relatório de execução."""

    def test_creates_report(self, tmp_backup_dir: Path) -> None:
        """Cria relatório JSON válido."""
        with patch.object(ft, "BACKUP_DIR", tmp_backup_dir):
            ft.write_run_report(
                success=True,
                stable=True,
                validation_passed=4,
                validation_total=4,
                elapsed_sec=1800.0,
                samples_count=500,
                backups_cleaned=2,
            )
            report_path = tmp_backup_dir / "last_finetune_report.json"
            assert report_path.exists()

            report = json.loads(report_path.read_text())
            assert report["success"] is True
            assert report["model_stable"] is True
            assert report["validation"] == "4/4"
            assert report["training_samples"] == 500
            assert report["elapsed_minutes"] == 30.0
            assert report["backups_cleaned"] == 2
            assert report["target_model"] == "eddie-sentiment"

    def test_creates_dir_if_missing(self, tmp_path: Path) -> None:
        """Cria diretório de backup se não existir."""
        bk_dir = tmp_path / "new_backups"
        with patch.object(ft, "BACKUP_DIR", bk_dir):
            ft.write_run_report(True, True, 4, 4, 60.0, 100, 0)
            assert bk_dir.exists()
            assert (bk_dir / "last_finetune_report.json").exists()


# ── Testes de generate_modelfile ───────────────────────────────────────────────


class TestGenerateModelfile:
    """Testes para geração do Modelfile."""

    def test_generates_valid_modelfile(self, tmp_output_dir: Path) -> None:
        """Gera Modelfile com conteúdo correto."""
        gguf = tmp_output_dir / "model.gguf"
        gguf.write_text("dummy")
        modelfile_out = tmp_output_dir / "Modelfile.finetuned"

        with patch.object(ft, "GGUF_OUTPUT", gguf), \
             patch.object(ft, "MODELFILE_OUTPUT", modelfile_out):
            result = ft.generate_modelfile()
            assert result == modelfile_out
            content = modelfile_out.read_text()
            assert f"FROM {gguf}" in content
            assert "SYSTEM" in content
            assert "eddie-sentiment" in content
            assert "temperature 0.05" in content
            assert "num_predict 80" in content


# ── Testes de backup_current_model ─────────────────────────────────────────────


class TestBackupCurrentModel:
    """Testes para backup do modelo atual."""

    @patch("ollama_finetune_batch.urllib.request.urlopen")
    def test_backup_success(
        self, mock_urlopen: MagicMock, tmp_backup_dir: Path
    ) -> None:
        """Cria backup JSON do modelo."""
        model_data = {"modelfile": "FROM phi4-mini\nSYSTEM test"}
        ctx = MagicMock()
        ctx.read.return_value = json.dumps(model_data).encode()
        ctx.__enter__ = MagicMock(return_value=ctx)
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = ctx

        with patch.object(ft, "BACKUP_DIR", tmp_backup_dir):
            result = ft.backup_current_model()
            assert result is not None
            assert result.exists()
            data = json.loads(result.read_text())
            assert data["modelfile"] == "FROM phi4-mini\nSYSTEM test"

    @patch("ollama_finetune_batch.urllib.request.urlopen")
    def test_backup_failure(
        self, mock_urlopen: MagicMock, tmp_backup_dir: Path
    ) -> None:
        """Retorna None se não conseguir fazer backup."""
        mock_urlopen.side_effect = ConnectionRefusedError()

        with patch.object(ft, "BACKUP_DIR", tmp_backup_dir):
            result = ft.backup_current_model()
            assert result is None


# ── Testes de import_to_ollama ─────────────────────────────────────────────────


class TestImportToOllama:
    """Testes para importação via Ollama API."""

    @patch("ollama_finetune_batch.urllib.request.urlopen")
    def test_import_success(
        self, mock_urlopen: MagicMock, tmp_output_dir: Path
    ) -> None:
        """Importa modelo com sucesso."""
        modelfile = tmp_output_dir / "Modelfile"
        modelfile.write_text("FROM /tmp/model.gguf\nSYSTEM test")

        ctx = MagicMock()
        ctx.read.return_value = b'{"status": "success"}'
        ctx.__enter__ = MagicMock(return_value=ctx)
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = ctx

        assert ft.import_to_ollama(modelfile) is True

    @patch("ollama_finetune_batch.urllib.request.urlopen")
    def test_import_failure(
        self, mock_urlopen: MagicMock, tmp_output_dir: Path
    ) -> None:
        """Retorna False se importação falhar."""
        modelfile = tmp_output_dir / "Modelfile"
        modelfile.write_text("FROM /tmp/model.gguf")
        mock_urlopen.side_effect = ConnectionRefusedError()
        assert ft.import_to_ollama(modelfile) is False
