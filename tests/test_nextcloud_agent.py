"""Testes unitários do NextcloudAgent — mocks completos, sem dependências externas."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specialized_agents.nextcloud_agent import (
    NextcloudChatRequest,
    NextcloudOccRequest,
    _occ_cmd_allowed,
    _OCC_ALLOWLIST,
    get_nextcloud_agent,
)


# ─── _occ_cmd_allowed ─────────────────────────────────────────────────────────

def test_occ_allowed_status():
    assert _occ_cmd_allowed(["status"]) is True


def test_occ_allowed_user_list():
    assert _occ_cmd_allowed(["user:list", "--output=json"]) is True


def test_occ_blocked_user_delete():
    assert _occ_cmd_allowed(["user:delete", "admin"]) is False


def test_occ_blocked_empty():
    assert _occ_cmd_allowed([]) is False


def test_occ_blocked_shell_injection():
    assert _occ_cmd_allowed(["status; rm -rf /"]) is False


def test_occ_allowlist_not_empty():
    assert len(_OCC_ALLOWLIST) > 10


# ─── _ollama_plan ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ollama_plan_valid_json():
    """Retorna plano correto quando Ollama responde JSON válido."""
    plan_json = json.dumps({
        "action": "admin.status",
        "params": {},
        "reasoning": "Usuário pediu status do sistema",
    })
    with patch(
        "specialized_agents.nextcloud_agent._ollama_chat",
        new=AsyncMock(return_value=(plan_json, "http://host", "qwen2.5:3b")),
    ):
        from specialized_agents.nextcloud_agent import _ollama_plan
        result = await _ollama_plan("qual o status do nextcloud?")

    assert result["action"] == "admin.status"
    assert "reasoning" in result


@pytest.mark.asyncio
async def test_ollama_plan_fallback_on_invalid_json():
    """Retorna fallback admin.status quando Ollama retorna JSON inválido."""
    with patch(
        "specialized_agents.nextcloud_agent._ollama_chat",
        new=AsyncMock(return_value=("não é json", "http://host", "qwen2.5:3b")),
    ):
        from specialized_agents.nextcloud_agent import _ollama_plan
        result = await _ollama_plan("qualquer coisa")

    assert result["action"] == "admin.status"


# ─── _dispatch ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_files_list():
    items = [{"href": "/dav/files/admin/", "name": "admin", "type": "directory", "size": "0", "modified": ""}]
    with patch(
        "specialized_agents.nextcloud_agent._webdav_propfind",
        new=AsyncMock(return_value=items),
    ):
        from specialized_agents.nextcloud_agent import _dispatch
        result = await _dispatch("files.list", {"username": "admin", "path": "/"}, dry_run=False)

    assert isinstance(result, list)
    assert result[0]["name"] == "admin"


@pytest.mark.asyncio
async def test_dispatch_files_mkdir_dry_run():
    from specialized_agents.nextcloud_agent import _dispatch
    result = await _dispatch("files.mkdir", {"username": "admin", "path": "/Teste"}, dry_run=True)
    assert result["dry_run"] is True


@pytest.mark.asyncio
async def test_dispatch_admin_status():
    with patch(
        "specialized_agents.nextcloud_agent._run_occ",
        new=AsyncMock(return_value=(0, "Nextcloud is not in maintenance mode", "")),
    ):
        from specialized_agents.nextcloud_agent import _dispatch
        result = await _dispatch("admin.status", {}, dry_run=False)

    assert result["rc"] == 0
    assert "maintenance" in result["output"].lower()


@pytest.mark.asyncio
async def test_dispatch_admin_maintenance_invalid_mode():
    from specialized_agents.nextcloud_agent import _dispatch
    result = await _dispatch("admin.maintenance", {"mode": "invalid"}, dry_run=False)
    assert "error" in result


@pytest.mark.asyncio
async def test_dispatch_unknown_action():
    from specialized_agents.nextcloud_agent import _dispatch
    result = await _dispatch("inexistente.acao", {}, dry_run=False)
    assert "error" in result


# ─── NextcloudAgent.chat ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_chat_success():
    plan = {
        "action": "admin.status",
        "params": {},
        "reasoning": "teste",
        "gpu_used": "http://host",
        "model_used": "qwen2.5:3b",
    }
    dispatch_result = {"rc": 0, "output": "ok"}

    with (
        patch("specialized_agents.nextcloud_agent._ollama_plan", new=AsyncMock(return_value=plan)),
        patch("specialized_agents.nextcloud_agent._dispatch", new=AsyncMock(return_value=dispatch_result)),
    ):
        agent = get_nextcloud_agent()
        req = NextcloudChatRequest(message="status do sistema", username="admin")
        resp = await agent.chat(req)

    assert resp.ok is True
    assert resp.action == "admin.status"
    assert resp.result == dispatch_result


@pytest.mark.asyncio
async def test_agent_chat_ollama_failure_fallback():
    """Quando Ollama falha, o agente usa fallback admin.status."""
    dispatch_result = {"rc": 0, "output": "fallback ok"}

    with (
        patch(
            "specialized_agents.nextcloud_agent._ollama_plan",
            new=AsyncMock(side_effect=Exception("Ollama down")),
        ),
        patch("specialized_agents.nextcloud_agent._dispatch", new=AsyncMock(return_value=dispatch_result)),
    ):
        agent = get_nextcloud_agent()
        req = NextcloudChatRequest(message="qualquer coisa", username="admin")
        resp = await agent.chat(req)

    assert resp.ok is True
    assert resp.action == "admin.status"


# ─── NextcloudAgent.run_occ ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_occ_allowed():
    with patch(
        "specialized_agents.nextcloud_agent._run_occ",
        new=AsyncMock(return_value=(0, '{"users": []}', "")),
    ):
        agent = get_nextcloud_agent()
        result = await agent.run_occ(NextcloudOccRequest(args=["user:list", "--output=json"]))

    assert result["rc"] == 0


@pytest.mark.asyncio
async def test_run_occ_blocked():
    from fastapi import HTTPException
    agent = get_nextcloud_agent()
    with pytest.raises(HTTPException) as exc_info:
        await agent.run_occ(NextcloudOccRequest(args=["user:delete", "admin"]))
    assert exc_info.value.status_code == 403


# ─── NextcloudAgent.health ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_all_ok():
    mock_resp_nc = AsyncMock()
    mock_resp_nc.status = 200
    mock_resp_nc.__aenter__ = AsyncMock(return_value=mock_resp_nc)
    mock_resp_nc.__aexit__ = AsyncMock(return_value=False)

    mock_resp_ollama = AsyncMock()
    mock_resp_ollama.status = 200
    mock_resp_ollama.json = AsyncMock(return_value={"models": [{"name": "qwen2.5:3b"}]})
    mock_resp_ollama.__aenter__ = AsyncMock(return_value=mock_resp_ollama)
    mock_resp_ollama.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("specialized_agents.nextcloud_agent._run_occ", new=AsyncMock(return_value=(0, "ok", ""))),
        patch("aiohttp.ClientSession") as mock_session_cls,
    ):
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock(return_value=mock_resp_ollama)
        mock_session_cls.return_value = mock_session

        agent = get_nextcloud_agent()
        result = await agent.health()

    assert "components" in result
