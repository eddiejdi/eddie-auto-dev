"""
NextcloudAgent LangGraph — wrapper de governança LangGraph sobre o NextcloudAgent.

Adiciona:
  - Action Journal: toda operação gera intent_id rastreável
  - Approval Telegram: operações destrutivas e VPN → risk=medium/high
  - Shared Memory: resultados indexados no ChromaDB
  - Checkpoint: estado preservado durante operações longas (chat+plan+dispatch)

Risk levels por operação::
    health, files_list, files_download, share_list, admin_status  → low
    files_upload, files_mkdir, share_create, run_occ               → medium
    files_delete                                                   → medium
    chat (com plan+dispatch)                                       → medium
    vpn_provision, vpn_install                                     → high

Feature flag::
    NEXTCLOUD_AGENT_VERSION=v1  (default produção)
    NEXTCLOUD_AGENT_VERSION=v2
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from specialized_agents.langgraph_base import AgentState, HomelabAgent
from specialized_agents.nextcloud_agent import (
    NextcloudAgent,
    NextcloudChatRequest,
    NextcloudChatResponse,
    NextcloudOccRequest,
    NextcloudFilesListRequest,
    NextcloudFilesListResponse,
    NextcloudFileUploadRequest,
    NextcloudShareCreateRequest,
)

logger = logging.getLogger(__name__)


def _get_v1() -> NextcloudAgent:
    from specialized_agents.nextcloud_agent import get_nextcloud_agent
    return get_nextcloud_agent()


def _run_async(coro) -> Any:
    try:
        loop = asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(asyncio.run, coro).result(timeout=300)
    except RuntimeError:
        return asyncio.run(coro)


# ── Chat Agent (risk=medium — executa plan + dispatch) ────────────────────────

class NextcloudChatAgent(HomelabAgent):
    AGENT_ID    = "nextcloud_agent"
    ACTION_TYPE = "nextcloud_chat"
    RISK_LEVEL  = "medium"

    def _describe_work(self, state: AgentState) -> str:
        msg = state.get("extra", {}).get("message", "?")[:100]
        return f"Nextcloud chat (plan+dispatch): {msg}"

    def _execute_work(self, state: AgentState) -> dict:
        req_data = state.get("extra", {})
        req    = NextcloudChatRequest(**req_data)
        result: NextcloudChatResponse = _run_async(_get_v1().chat(req))
        actions = getattr(result, "actions_taken", [])
        reply   = getattr(result, "reply", "") or ""
        outcome = f"Chat Nextcloud concluído. Ações: {len(actions)}. Resposta: {reply[:150]}"
        return {
            "outcome":     outcome,
            "memory_fact": f"nextcloud_agent: chat '{req.message[:80]}' → {len(actions)} ação(ões)",
        }


# ── OCC Agent (risk=medium — comandos administrativos) ────────────────────────

class NextcloudOccAgent(HomelabAgent):
    AGENT_ID    = "nextcloud_agent"
    ACTION_TYPE = "nextcloud_occ"
    RISK_LEVEL  = "medium"

    def _describe_work(self, state: AgentState) -> str:
        cmd = " ".join(state.get("extra", {}).get("args", []))[:100]
        return f"Nextcloud OCC: {cmd}"

    def _execute_work(self, state: AgentState) -> dict:
        req_data = state.get("extra", {})
        req    = NextcloudOccRequest(**req_data)
        result = _run_async(_get_v1().run_occ(req))
        rc     = result.get("returncode", "?")
        stdout = result.get("stdout", "")[:200]
        cmd    = " ".join(req.args)
        outcome = f"OCC {cmd}: rc={rc}. {stdout}"
        return {
            "outcome":     outcome,
            "memory_fact": f"nextcloud_agent: occ '{cmd}' rc={rc}",
        }


# ── File Upload Agent (risk=medium) ───────────────────────────────────────────

class NextcloudFileUploadAgent(HomelabAgent):
    AGENT_ID    = "nextcloud_agent"
    ACTION_TYPE = "nextcloud_file_upload"
    RISK_LEVEL  = "medium"

    def _describe_work(self, state: AgentState) -> str:
        req_data = state.get("extra", {})
        return f"Upload Nextcloud: {req_data.get('username', '?')}:{req_data.get('path', '?')}"

    def _execute_work(self, state: AgentState) -> dict:
        from specialized_agents.nextcloud_agent import _webdav_upload
        req_data = state.get("extra", {})
        req  = NextcloudFileUploadRequest(**req_data)
        rc   = _run_async(_webdav_upload(req.username, req.path, req.content_base64 or b"", req.content_type or "application/octet-stream"))
        outcome = f"Upload {req.username}:{req.path} → HTTP {rc}"
        return {
            "outcome":     outcome,
            "memory_fact": f"nextcloud_agent: upload '{req.path}' user={req.username} rc={rc}",
        }


# ── Share Create Agent (risk=medium) ─────────────────────────────────────────

class NextcloudShareCreateAgent(HomelabAgent):
    AGENT_ID    = "nextcloud_agent"
    ACTION_TYPE = "nextcloud_share_create"
    RISK_LEVEL  = "medium"

    def _describe_work(self, state: AgentState) -> str:
        req_data = state.get("extra", {})
        return f"Criar share Nextcloud: {req_data.get('username', '?')}:{req_data.get('path', '?')}"

    def _execute_work(self, state: AgentState) -> dict:
        from specialized_agents.nextcloud_agent import _ocs_share_create
        req_data = state.get("extra", {})
        req    = NextcloudShareCreateRequest(**req_data)
        result = _run_async(_ocs_share_create(
            req.username, req.path,
            share_type=req.share_type,
            permissions=req.permissions,
            share_with=req.share_with,
            password=req.password,
            expire_date=req.expire_date,
        ))
        token = result.get("token", "?")
        outcome = f"Share criado: {req.path} → token={token}"
        return {
            "outcome":     outcome,
            "memory_fact": f"nextcloud_agent: share '{req.path}' token={token}",
        }


# ── VPN Provision Agent (risk=high → Telegram obrigatório) ────────────────────

class NextcloudVpnAgent(HomelabAgent):
    AGENT_ID    = "nextcloud_agent"
    ACTION_TYPE = "nextcloud_vpn_provision"
    RISK_LEVEL  = "high"

    def _describe_work(self, state: AgentState) -> str:
        req_data = state.get("extra", {})
        user = req_data.get("username", "?")
        return f"Provisionar VPN Nextcloud para usuário {user}"

    def _execute_work(self, state: AgentState) -> dict:
        from specialized_agents.nextcloud_agent import nextcloud_vpn_provision
        from specialized_agents.nextcloud_agent import NextcloudVpnProvisionRequest
        req_data = state.get("extra", {})
        req    = NextcloudVpnProvisionRequest(**req_data)
        result = _run_async(nextcloud_vpn_provision(req))
        peer_ip = result.get("peer_ip", "?")
        outcome = f"VPN provisionada para {req.username}: peer_ip={peer_ip}"
        return {
            "outcome":     outcome,
            "memory_fact": f"nextcloud_agent: VPN {req.username} peer_ip={peer_ip}",
        }


# ── Fachada pública ────────────────────────────────────────────────────────────

class NextcloudAgentV2:
    """Drop-in replacement do NextcloudAgent com camada de governança LangGraph."""

    def __init__(self):
        self._chat_agent   = NextcloudChatAgent()
        self._occ_agent    = NextcloudOccAgent()
        self._upload_agent = NextcloudFileUploadAgent()
        self._share_agent  = NextcloudShareCreateAgent()
        self._vpn_agent    = NextcloudVpnAgent()

    def close(self):
        for a in (self._chat_agent, self._occ_agent, self._upload_agent,
                  self._share_agent, self._vpn_agent):
            a.close()

    def _unwrap(self, state: dict) -> dict:
        """Extrai resultado ou lança HTTPException."""
        if state.get("approval") == "pending":
            from fastapi import HTTPException
            raise HTTPException(
                status_code=202,
                detail=f"Aguardando aprovação Telegram. thread_id={state.get('thread_id')}",
            )
        if state.get("status") == "failed":
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=state.get("error", "operation failed"))
        return state

    async def chat(self, req: NextcloudChatRequest) -> NextcloudChatResponse:
        state = self._unwrap(
            await asyncio.to_thread(self._chat_agent.run, target="nextcloud", extra=req.model_dump())
        )
        # Fallback: outcome como reply se o resultado real não estiver no state
        return NextcloudChatResponse(
            reply=state.get("outcome", "ok"),
            actions_taken=[],
        )

    async def run_occ(self, req: NextcloudOccRequest) -> dict[str, Any]:
        state = self._unwrap(
            await asyncio.to_thread(self._occ_agent.run, target=" ".join(req.args), extra=req.model_dump())
        )
        return {"ok": True, "outcome": state.get("outcome")}

    async def health(self) -> dict[str, Any]:
        return await _get_v1().health()

    async def vpn_provision(self, req) -> dict[str, Any]:
        state = self._unwrap(
            await asyncio.to_thread(
                self._vpn_agent.run,
                target=getattr(req, "username", "?"),
                extra=req.model_dump(),
            )
        )
        return {"ok": True, "outcome": state.get("outcome")}


# ── Singleton ─────────────────────────────────────────────────────────────────

_agent_v2: NextcloudAgentV2 | None = None


def get_nextcloud_agent_langgraph() -> NextcloudAgentV2:
    global _agent_v2
    if _agent_v2 is None:
        _agent_v2 = NextcloudAgentV2()
    return _agent_v2
