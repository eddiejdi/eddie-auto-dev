"""Testes unitários para tape_quality_ollama_narrator."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import tools.tape_quality_ollama_narrator as mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_prom_result(component: str, score: float) -> dict:
    return {
        "metric": {"component": component},
        "value": [1000000000, str(score)],
    }


# ---------------------------------------------------------------------------
# fetch_component_scores
# ---------------------------------------------------------------------------


def test_fetch_component_scores_parses_prometheus_response() -> None:
    """Deve extrair scores corretamente da resposta Prometheus."""
    raw = [
        _make_prom_result("fc_link_state", 100.0),
        _make_prom_result("ltfs_service_unit", 0.0),
        _make_prom_result("drive_transport", 50.0),
    ]
    with patch.object(mod, "query_prometheus", return_value=raw):
        scores = mod.fetch_component_scores()

    assert scores["fc_link_state"] == pytest.approx(100.0)
    assert scores["ltfs_service_unit"] == pytest.approx(0.0)
    assert scores["drive_transport"] == pytest.approx(50.0)


def test_fetch_component_scores_returns_empty_on_prom_failure() -> None:
    """Retorna dict vazio quando Prometheus está indisponível."""
    with patch.object(mod, "query_prometheus", return_value=[]):
        scores = mod.fetch_component_scores()
    assert scores == {}


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------


def test_build_prompt_contains_all_sections() -> None:
    """O prompt gerado deve conter as seções estruturais obrigatórias."""
    scores = {
        "fc_link_state": 0.0,
        "ltfs_service_unit": 0.0,
        "ltfs_stack": 100.0,
        "drive_transport": 35.0,
    }
    prompt = mod.build_prompt(scores, overall=28.8)

    assert "HARDWARE" in prompt
    assert "SOFTWARE" in prompt
    assert "CASCATA" in prompt
    assert "fc_link_state" in prompt
    assert "ltfs_service_unit" in prompt
    # ltfs_service_unit deveria ser marcado como cascata de fc_link_state
    assert "cascata" in prompt.lower()


def test_build_prompt_cascade_detection() -> None:
    """fc_link_state=0 deve marcar ltfs_service_unit como cascata."""
    scores = {"fc_link_state": 0.0, "ltfs_service_unit": 0.0}
    prompt = mod.build_prompt(scores, overall=0.0)
    assert "ltfs_service_unit" in prompt
    assert "cascata" in prompt.lower()


def test_build_prompt_no_cascade_when_hw_ok() -> None:
    """Se hardware OK, cascata não deve ser mencionada para software."""
    scores = {"fc_link_state": 100.0, "ltfs_service_unit": 0.0}
    prompt = mod.build_prompt(scores, overall=50.0)
    # Sem falha de hardware, não deve ter seção de cascata
    assert "CASCATA DETECTADA" not in prompt


def test_classify_score_thresholds() -> None:
    """Classificação de score deve seguir os limiares corretos."""
    assert "FALHA" in mod._classify_score(0.0)
    assert "FALHA" in mod._classify_score(29.9)
    assert "DEGRADADO" in mod._classify_score(30.0)
    assert "DEGRADADO" in mod._classify_score(69.9)
    assert "OK" in mod._classify_score(70.0)
    assert "OK" in mod._classify_score(100.0)


# ---------------------------------------------------------------------------
# already_ran_today / save_state
# ---------------------------------------------------------------------------


def test_already_ran_today_returns_false_when_no_state_file(tmp_path: Path) -> None:
    with patch.object(mod, "STATE_FILE", tmp_path / "state.json"):
        assert mod.already_ran_today() is False


def test_already_ran_today_returns_true_when_ran_today(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"last_run_date": date.today().isoformat()}))
    with patch.object(mod, "STATE_FILE", state_file):
        assert mod.already_ran_today() is True


def test_already_ran_today_returns_false_for_yesterday(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"last_run_date": "2000-01-01"}))
    with patch.object(mod, "STATE_FILE", state_file):
        assert mod.already_ran_today() is False


def test_save_state_creates_file_with_today(tmp_path: Path) -> None:
    state_file = tmp_path / "subdir" / "state.json"
    with patch.object(mod, "STATE_FILE", state_file):
        mod.save_state("texto gerado")
    content = json.loads(state_file.read_text())
    assert content["last_run_date"] == date.today().isoformat()
    assert content["narration_length"] == len("texto gerado")


# ---------------------------------------------------------------------------
# call_ollama GPU-first
# ---------------------------------------------------------------------------


def test_call_ollama_tries_gpu0_first() -> None:
    """GPU0 deve ser tentado antes de GPU1."""
    call_order: list[str] = []

    def fake_post(url: str, **kwargs) -> MagicMock:  # noqa: ANN001
        call_order.append(url)
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"response": "diagnóstico gerado"}
        return resp

    with patch("tools.tape_quality_ollama_narrator.requests.post", side_effect=fake_post):
        result = mod.call_ollama("prompt")

    assert result == "diagnóstico gerado"
    assert call_order[0].startswith(mod.OLLAMA_GPU0)


def test_call_ollama_falls_back_to_gpu1() -> None:
    """Se GPU0 falhar, deve tentar GPU1."""
    call_order: list[str] = []

    def fake_post(url: str, **kwargs) -> MagicMock:  # noqa: ANN001
        call_order.append(url)
        if mod.OLLAMA_GPU0 in url:
            raise ConnectionError("GPU0 offline")
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"response": "fallback ok"}
        return resp

    with patch("tools.tape_quality_ollama_narrator.requests.post", side_effect=fake_post):
        result = mod.call_ollama("prompt")

    assert result == "fallback ok"
    assert any(mod.OLLAMA_GPU1 in u for u in call_order)


def test_call_ollama_returns_none_when_both_gpus_down() -> None:
    """Deve retornar None se ambas as GPUs estiverem indisponíveis."""
    with patch(
        "tools.tape_quality_ollama_narrator.requests.post",
        side_effect=ConnectionError("offline"),
    ):
        result = mod.call_ollama("prompt")

    assert result is None


# ---------------------------------------------------------------------------
# update_ai_panel_content
# ---------------------------------------------------------------------------


def test_update_ai_panel_content_updates_correct_panel() -> None:
    """Deve atualizar o conteúdo exatamente no painel com id=AI_PANEL_ID."""
    dashboard_data = {
        "dashboard": {
            "panels": [
                {"id": 1, "options": {"content": "antigo"}},
                {"id": mod.AI_PANEL_ID, "options": {"content": "antigo"}},
            ]
        }
    }
    updated = mod.update_ai_panel_content(dashboard_data, "novo conteúdo")
    panels = {p["id"]: p for p in updated["dashboard"]["panels"]}

    assert panels[mod.AI_PANEL_ID]["options"]["content"] == "novo conteúdo"
    assert panels[1]["options"]["content"] == "antigo"


# ---------------------------------------------------------------------------
# run() — fluxo completo
# ---------------------------------------------------------------------------


def test_run_returns_2_when_already_ran_today(tmp_path: Path) -> None:
    """Deve retornar 2 se já rodou hoje e --force não for passado."""
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"last_run_date": date.today().isoformat()}))
    with patch.object(mod, "STATE_FILE", state_file):
        assert mod.run(force=False) == 2


def test_run_dry_run_returns_0_and_does_not_update_grafana(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """dry_run deve imprimir o conteúdo e retornar 0 sem chamar Grafana."""
    state_file = tmp_path / "state.json"

    with (
        patch.object(mod, "STATE_FILE", state_file),
        patch.object(mod, "fetch_component_scores", return_value={"fc_link_state": 0.0}),
        patch.object(mod, "fetch_overall_score", return_value=0.0),
        patch.object(mod, "call_ollama", return_value="diagnóstico detalhado"),
        patch.object(mod, "get_dashboard") as mock_gd,
        patch.object(mod, "push_dashboard") as mock_push,
    ):
        code = mod.run(force=True, dry_run=True)

    assert code == 0
    mock_gd.assert_not_called()
    mock_push.assert_not_called()
    captured = capsys.readouterr()
    assert "diagnóstico detalhado" in captured.out


def test_run_returns_1_when_prometheus_empty(tmp_path: Path) -> None:
    """Deve retornar 1 quando Prometheus não retorna scores."""
    with (
        patch.object(mod, "STATE_FILE", tmp_path / "s.json"),
        patch.object(mod, "fetch_component_scores", return_value={}),
    ):
        assert mod.run(force=True) == 1


def test_run_returns_1_when_ollama_down(tmp_path: Path) -> None:
    """Deve retornar 1 quando Ollama está indisponível."""
    with (
        patch.object(mod, "STATE_FILE", tmp_path / "s.json"),
        patch.object(mod, "fetch_component_scores", return_value={"fc_link_state": 0.0}),
        patch.object(mod, "fetch_overall_score", return_value=0.0),
        patch.object(mod, "call_ollama", return_value=None),
    ):
        assert mod.run(force=True) == 1
