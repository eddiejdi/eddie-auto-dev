"""Testes FastAPI para specialized_agents.tape_routes."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from specialized_agents import tape_routes


@pytest.fixture()
def client() -> TestClient:
    """Cliente HTTP de teste com router de fita montado."""
    app = FastAPI()
    app.include_router(tape_routes.router)

    tape_routes._last_report = None
    tape_routes._active_job = None
    tape_routes._last_component_quality_report = None
    tape_routes._active_component_quality_job = None

    return TestClient(app, raise_server_exceptions=False)


def test_tape_health_exposes_initial_state(client: TestClient) -> None:
    response = client.get("/tape/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["report_available"] is False


def test_component_quality_job_runs_and_exposes_report(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_report = {
        "hostname": "nas-test",
        "generated_at": "2026-05-08T09:00:00",
        "overall_score": 92.5,
        "components": [
            {
                "component": "fc_host7",
                "category": "hba",
                "target": "host7",
                "score": 97.0,
                "status": "pass",
                "message": "Porta excelente.",
                "details": {},
            }
        ],
        "summary": {"pass": 1, "degraded": 0, "fail": 0},
    }

    monkeypatch.setattr(
        "tools.tape_component_quality_agent.collect_component_quality",
        lambda **kwargs: fake_report,
    )
    monkeypatch.setattr(
        "tools.tape_component_quality_agent.report_to_dict",
        lambda report: report,
    )

    response = client.post("/tape/component-quality", json={"hosts": ["host7"]})

    assert response.status_code == 202
    status_payload = response.json()
    assert status_payload["status"] in {"queued", "done"}

    status_response = client.get("/tape/component-quality/status")
    assert status_response.status_code == 200
    assert status_response.json()["report_available"] is True

    report_response = client.get("/tape/component-quality/report")
    assert report_response.status_code == 200
    assert report_response.json()["overall_score"] == 92.5


def test_component_quality_report_404_before_run(client: TestClient) -> None:
    response = client.get("/tape/component-quality/report")

    assert response.status_code == 404


def test_hba_test_job_runs_and_exposes_report(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_report = {"overall_score": 82.1, "best_port": "host7", "worst_port": "host0", "ports": []}

    monkeypatch.setattr(
        "tools.fc_hba_tester.run_dual_hba_test",
        lambda **kwargs: fake_report,
    )
    monkeypatch.setattr(
        "tools.fc_hba_tester.report_to_dict",
        lambda report: report,
    )

    response = client.post("/tape/hba-test", json={"hosts": ["host0", "host7"], "fast": True})

    assert response.status_code == 202

    status_response = client.get("/tape/hba-test/status")
    assert status_response.status_code == 200
    assert status_response.json()["report_available"] is True

    report_response = client.get("/tape/hba-test/report")
    assert report_response.status_code == 200
    assert report_response.json()["best_port"] == "host7"
