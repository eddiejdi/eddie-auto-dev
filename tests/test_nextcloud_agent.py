"""Testes unitários do NextcloudAgent — mocks completos, sem dependências externas."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import base64

import specialized_agents.nextcloud_agent as nextcloud_agent_module

from specialized_agents.nextcloud_agent import (
    NextcloudChatRequest,
    NextcloudFilesListRequest,
    NextcloudFileUploadRequest,
    NextcloudOccRequest,
    _occ_cmd_allowed,
    _OCC_ALLOWLIST,
    _classify_lto_mount,
    _is_same_webdav_resource,
    _MAX_UPLOAD_BYTES,
    _webdav_upload,
    nextcloud_files_list_post,
    nextcloud_files_upload,
    nextcloud_files_download,
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


def test_is_same_webdav_resource_true_with_trailing_slash():
    request_url = "https://nextcloud.rpa4all.com/remote.php/dav/files/eddie/"
    href = "/remote.php/dav/files/eddie/"
    assert _is_same_webdav_resource(request_url, href) is True


def test_is_same_webdav_resource_true_with_encoding():
    request_url = "https://nextcloud.rpa4all.com/remote.php/dav/files/eddie/Nextcloud%20Folder/"
    href = "/remote.php/dav/files/eddie/Nextcloud Folder/"
    assert _is_same_webdav_resource(request_url, href) is True


def test_is_same_webdav_resource_false_for_child():
    request_url = "https://nextcloud.rpa4all.com/remote.php/dav/files/eddie/"
    href = "/remote.php/dav/files/eddie/Documents/"
    assert _is_same_webdav_resource(request_url, href) is False


def test_classify_lto_mount_accepts_staging_bind():
    result = _classify_lto_mount(
        [{"Source": "/mnt/lto6-nc", "Destination": "/var/www/html/external/LTO", "Mode": "rw"}]
    )
    assert result["ok"] is True
    assert result["expected_staging_bind"] is True
    assert result["unsafe_source"] is False


def test_classify_lto_mount_flags_direct_ltfs_source():
    result = _classify_lto_mount(
        [{"Source": "/mnt/tape/lto6", "Destination": "/var/www/html/external/LTO", "Mode": "rw"}]
    )
    assert result["ok"] is False
    assert result["unsafe_source"] is True
    assert result["warnings"]


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
        new=AsyncMock(return_value=(plan_json, "http://host", "phi4-mini:latest")),
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
        new=AsyncMock(return_value=("não é json", "http://host", "phi4-mini:latest")),
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


@pytest.mark.asyncio
async def test_files_list_post_response_shape():
    mock_items = [
        {"href": "/remote.php/dav/files/eddie/Documents/", "name": "Documents", "type": "directory", "size": "0", "modified": ""}
    ]
    with patch(
        "specialized_agents.nextcloud_agent._webdav_propfind",
        new=AsyncMock(return_value=mock_items),
    ):
        req = NextcloudFilesListRequest(username="eddie", path="/", depth=1)
        resp = await nextcloud_files_list_post(req)

    assert resp.total_items == 1
    assert resp.items[0]["name"] == "Documents"


# ─── NextcloudAgent.chat ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_chat_success():
    plan = {
        "action": "admin.status",
        "params": {},
        "reasoning": "teste",
        "gpu_used": "http://host",
        "model_used": "phi4-mini:latest",
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
async def test_run_occ_resolves_container_alias():
    nextcloud_agent_module._NC_RESOLVED_CONTAINER = None
    with patch(
        "specialized_agents.nextcloud_agent._run_command",
        new=AsyncMock(
            side_effect=[
                (1, "", "Error: No such container: nextcloud-app"),
                (0, "/nextcloud-rpa4all", ""),
                (0, "ok", ""),
            ]
        ),
    ) as run_cmd:
        rc, out, err = await nextcloud_agent_module._run_occ("status")

    assert rc == 0
    assert out == "ok"
    assert err == ""
    assert run_cmd.await_args_list[1].args == (
        "docker",
        "inspect",
        "nextcloud-rpa4all",
        "--format",
        "{{.Name}}",
    )
    assert run_cmd.await_args_list[2].args[:5] == (
        "docker",
        "exec",
        "-u",
        "www-data",
        "nextcloud-rpa4all",
    )


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
    mock_resp_ollama.json = AsyncMock(return_value={"models": [{"name": "phi4-mini:latest"}]})
    mock_resp_ollama.__aenter__ = AsyncMock(return_value=mock_resp_ollama)
    mock_resp_ollama.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("specialized_agents.nextcloud_agent._run_occ", new=AsyncMock(return_value=(0, "ok", ""))),
        patch(
            "specialized_agents.nextcloud_agent._nextcloud_storage_diagnostics",
            new=AsyncMock(return_value={"ok": True}),
        ),
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


@pytest.mark.asyncio
async def test_dispatch_admin_storage_diagnostics():
    expected = {"ok": True, "write_probe": {"ok": True}}
    with patch(
        "specialized_agents.nextcloud_agent._nextcloud_storage_diagnostics",
        new=AsyncMock(return_value=expected),
    ):
        from specialized_agents.nextcloud_agent import _dispatch
        result = await _dispatch("admin.storage_diagnostics", {}, dry_run=False)

    assert result == expected


# ─── files.upload / files.download ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_files_upload_dry_run():
    from specialized_agents.nextcloud_agent import _dispatch
    content = base64.b64encode(b"hello world").decode()
    result = await _dispatch(
        "files.upload",
        {"username": "admin", "path": "/test.txt", "content_b64": content},
        dry_run=True,
    )
    assert result["dry_run"] is True
    assert "/test.txt" in result["url"]


@pytest.mark.asyncio
async def test_dispatch_files_upload_success():
    content = base64.b64encode(b"hello world").decode()
    with patch(
        "specialized_agents.nextcloud_agent._webdav_upload",
        new=AsyncMock(return_value=201),
    ):
        from specialized_agents.nextcloud_agent import _dispatch
        result = await _dispatch(
            "files.upload",
            {"username": "admin", "path": "/test.txt", "content_b64": content},
            dry_run=False,
        )
    assert result["status"] == 201
    assert result["uploaded"] is True


@pytest.mark.asyncio
async def test_dispatch_files_upload_invalid_b64():
    from specialized_agents.nextcloud_agent import _dispatch
    result = await _dispatch(
        "files.upload",
        {"username": "admin", "path": "/test.txt", "content_b64": "!!!nao_e_base64!!!"},
        dry_run=False,
    )
    assert "error" in result


@pytest.mark.asyncio
async def test_dispatch_files_upload_missing_params():
    from specialized_agents.nextcloud_agent import _dispatch
    result = await _dispatch("files.upload", {"username": "admin"}, dry_run=False)
    assert "error" in result


@pytest.mark.asyncio
async def test_dispatch_files_download_success():
    raw = b"conteudo do arquivo"
    with patch(
        "specialized_agents.nextcloud_agent._webdav_download",
        new=AsyncMock(return_value=raw),
    ):
        from specialized_agents.nextcloud_agent import _dispatch
        result = await _dispatch(
            "files.download",
            {"username": "admin", "path": "/test.txt"},
            dry_run=False,
        )
    assert result["size_bytes"] == len(raw)
    assert base64.b64decode(result["content_b64"]) == raw


@pytest.mark.asyncio
async def test_dispatch_files_download_missing_path():
    from specialized_agents.nextcloud_agent import _dispatch
    result = await _dispatch("files.download", {"username": "admin"}, dry_run=False)
    assert "error" in result


def test_webdav_upload_size_limit_constant():
    assert _MAX_UPLOAD_BYTES == 35 * 1024 * 1024


@pytest.mark.asyncio
async def test_webdav_upload_rejects_oversized():
    oversized = b"x" * (_MAX_UPLOAD_BYTES + 1)
    with pytest.raises(ValueError, match="35 MB"):
        await _webdav_upload("admin", "/big.bin", oversized)


@pytest.mark.asyncio
async def test_rest_upload_endpoint_success():
    raw = b"dados de teste"
    with patch(
        "specialized_agents.nextcloud_agent._webdav_upload",
        new=AsyncMock(return_value=201),
    ):
        req = NextcloudFileUploadRequest(
            username="admin",
            path="/upload.txt",
            content_b64=base64.b64encode(raw).decode(),
        )
        result = await nextcloud_files_upload(req)
    assert result["uploaded"] is True
    assert result["status"] == 201


@pytest.mark.asyncio
async def test_rest_download_endpoint_success():
    raw = b"conteudo baixado"
    with patch(
        "specialized_agents.nextcloud_agent._webdav_download",
        new=AsyncMock(return_value=raw),
    ):
        result = await nextcloud_files_download(username="admin", path="/download.txt")
    assert result["size_bytes"] == len(raw)
    assert base64.b64decode(result["content_b64"]) == raw
