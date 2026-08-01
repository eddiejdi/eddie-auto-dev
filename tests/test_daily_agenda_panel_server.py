from __future__ import annotations

import json
import os
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import daily_agenda_panel_server as panel  # noqa: E402


@pytest.fixture
def server(tmp_path, monkeypatch):
    artifacts = tmp_path / "artifacts" / "daily_agenda"
    day = artifacts / "2026-07-09"
    day.mkdir(parents=True)
    (day / "source.txt").write_text("Fonte", encoding="utf-8")
    (day / "locution.txt").write_text("Locucao", encoding="utf-8")
    (day / "locution.wav").write_bytes(b"RIFF")
    cfg_path = artifacts / "panel_config.json"
    monkeypatch.setattr(panel, "ARTIFACTS_DIR", artifacts)
    monkeypatch.setattr(panel, "DEFAULT_JOB_PATH", artifacts / "panel_job.json")
    monkeypatch.setattr(panel, "JOB_LOG_PATH", artifacts / "panel_job.log")
    monkeypatch.setattr(panel, "API_KEY", "")
    # isola config de prompts no tmp
    import daily_agenda_config as dag_cfg

    monkeypatch.setattr(dag_cfg, "DEFAULT_CONFIG_PATH", cfg_path)
    monkeypatch.setattr(panel, "load_config", lambda path=None: dag_cfg.load_config(cfg_path))
    monkeypatch.setattr(
        panel,
        "save_config",
        lambda config, path=None: dag_cfg.save_config(config, cfg_path),
    )
    monkeypatch.setattr(panel, "load_prompt_templates", lambda: dag_cfg.load_prompt_templates(cfg_path))
    monkeypatch.setattr(panel, "default_prompt_templates", dag_cfg.default_prompt_templates)
    monkeypatch.setattr(
        panel,
        "youtube_auth_status",
        lambda _cfg=None: {"authenticated": False, "channel_title": "", "error": ""},
    )
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), panel.Handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def _get(url: str):
    import urllib.request

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=5) as response:
        return response.status, response.read(), response.headers.get("Content-Type", "")


def test_static_and_status(server) -> None:
    base = server
    status, body, ctype = _get(base + "/")
    assert status == 200
    assert "text/html" in ctype
    assert b"Agenda Di" in body

    status, body, ctype = _get(base + "/daily_agenda_panel.js")
    assert status == 200
    assert "javascript" in ctype

    status, body, _ = _get(base + "/api/status")
    payload = json.loads(body.decode())
    assert payload["editions"][0]["date"] == "2026-07-09"
    assert payload["config"]["youtube"]["enabled"] is True


def test_edition_detail_and_audio(server) -> None:
    base = server
    status, body, _ = _get(base + "/api/editions/2026-07-09")
    payload = json.loads(body.decode())
    assert payload["locution"] == "Locucao"
    assert payload["has_wav"] is True

    status, body, ctype = _get(base + "/api/editions/2026-07-09/audio")
    assert status == 200
    assert body == b"RIFF"
    assert ctype == "audio/wav"


def test_status_includes_prompts(server) -> None:
    base = server
    status, body, _ = _get(base + "/api/status")
    payload = json.loads(body.decode())
    assert status == 200
    assert "expansion_template" in payload["prompts"]
    assert "broadcast_template" in payload["prompts"]
    assert "{text}" in payload["prompts"]["expansion_template"]
    assert payload["prompt_defaults"]["expansion_template"]


def test_job_log_polling_reads_live_file(server, tmp_path, monkeypatch) -> None:
    base = server
    log_path = panel.JOB_LOG_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("linha1\nlinha2\n", encoding="utf-8")
    # pid real do pytest — evita reconciliar como stale/dead
    panel._set_job(
        {
            "status": "running",
            "phase": "broadcast",
            "date": "2026-07-31",
            "pid": os.getpid(),
            "started_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        }
    )

    status, body, _ = _get(base + "/api/job/log?since=0")
    assert status == 200
    payload = json.loads(body.decode())
    assert payload["ok"] is True
    assert "linha1" in payload["chunk"]
    assert payload["offset"] > 0
    assert payload["status"] == "running"

    # segunda leitura não repete
    status, body, _ = _get(base + f"/api/job/log?since={payload['offset']}")
    payload2 = json.loads(body.decode())
    assert payload2["chunk"] == ""

    # job com log live
    status, body, _ = _get(base + "/api/job")
    job = json.loads(body.decode())["job"]
    assert "linha2" in job.get("log", "")
    assert job.get("log_live") is True


def test_external_job_report_ingests_log(server) -> None:
    import urllib.request

    base = server
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    body = json.dumps(
        {
            "status": "running",
            "phase": "broadcast",
            "date": "2026-07-31",
            "source": "broadcast",
            "host": "workstation-test",
            "pid": 4242,
            "reset_log": True,
            "log_append": "[start] regenerando via telegram\n",
            "external": True,
        }
    ).encode()
    req = urllib.request.Request(
        base + "/api/job/report",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with opener.open(req, timeout=5) as resp:
        payload = json.loads(resp.read().decode())
    assert payload["ok"] is True
    assert payload["job"]["status"] == "running"
    assert payload["job"]["source"] == "broadcast"
    assert "regenerando via telegram" in payload["job"].get("log", "")

    # append more log
    body2 = json.dumps(
        {
            "status": "running",
            "log_append": "coletando fontes...\n",
            "host": "workstation-test",
            "source": "broadcast",
        }
    ).encode()
    req2 = urllib.request.Request(
        base + "/api/job/report",
        data=body2,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with opener.open(req2, timeout=5) as resp:
        payload2 = json.loads(resp.read().decode())
    assert "coletando fontes" in payload2["job"].get("log", "")

    status, body, _ = _get(base + "/api/job/log?since=0")
    chunk = json.loads(body.decode())["chunk"]
    assert "regenerando via telegram" in chunk
    assert "coletando fontes" in chunk


def test_save_and_use_prompts_without_redeploy(server) -> None:
    import urllib.request
    import daily_agenda_config as dag_cfg

    base = server
    custom_exp = "/no_think\nExpanda com tom X.\n\nTexto-base:\n{text}"
    custom_br = "/no_think\nLocucao com tom Y.\n\nTexto-base:\n{text}"
    req = urllib.request.Request(
        base + "/api/prompts",
        data=json.dumps(
            {
                "expansion_template": custom_exp,
                "broadcast_template": custom_br,
            }
        ).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=5) as resp:
        payload = json.loads(resp.read().decode())
    assert payload["ok"] is True
    assert payload["prompts"]["expansion_template"] == custom_exp

    # geração usa o template salvo (sem redeploy)
    rendered = dag_cfg.build_expansion_prompt("AGENDA DE HOJE")
    assert "tom X" in rendered
    assert "AGENDA DE HOJE" in rendered
    rendered_b = dag_cfg.build_broadcast_prompt("AGENDA DE HOJE")
    assert "tom Y" in rendered_b