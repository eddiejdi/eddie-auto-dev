"""
CmdbAgent v2 — wrapper de governança LangGraph sobre o CmdbAgent v1.

Adiciona:
  - Action Journal: toda operação gera intent_id rastreável
  - Approval Telegram: apply/netbox e apply/glpi com execute=True → risk=medium
  - Shared Memory: resultado de cada run indexado no ChromaDB
  - Checkpoint: estado preservado se processo reiniciar durante apply longo

Interface HTTP idêntica à v1 (mesmos endpoints, mesmos payloads).

Feature flag::
    CMDB_AGENT_VERSION=v1   (default produção)
    CMDB_AGENT_VERSION=v2   (ativa este wrapper)

Risk levels::
    cmdb_run         → low   (lê inventário, gera arquivos locais)
    apply_netbox     → medium se dry_run=False, low se dry_run=True
    apply_glpi       → medium se execute=True, low se dry_run
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from specialized_agents.langgraph_base import AgentState, HomelabAgent
from specialized_agents.cmdb_agent import (
    CmdbAgentRunRequest,
    CmdbNetboxApplyRequest,
    CmdbGlpiApplyRequest,
    CmdbLoadAgent,
    NetBoxPackageApplier,
    GLPIPackageApplier,
    REPO_ROOT,
    DEFAULT_INVENTORY,
    DEFAULT_OUTPUT_DIR,
)

logger = logging.getLogger(__name__)


# ── Agente run (low-risk) ─────────────────────────────────────────────────────


class CmdbRunAgent(HomelabAgent):
    AGENT_ID    = "cmdb_agent"
    ACTION_TYPE = "cmdb_run"
    RISK_LEVEL  = "low"

    def _describe_work(self, state: AgentState) -> str:
        req_data = state.get("extra", {})
        inv = req_data.get("inventory_file", str(DEFAULT_INVENTORY))
        return f"Gerar baseline CMDB do inventário {Path(inv).name}"

    def _execute_work(self, state: AgentState) -> dict:
        req_data = state.get("extra", {})
        agent = CmdbLoadAgent(
            repo_root      = Path(req_data["repo_root"])       if req_data.get("repo_root")       else REPO_ROOT,
            inventory_file = Path(req_data["inventory_file"])  if req_data.get("inventory_file")  else DEFAULT_INVENTORY,
            output_dir     = Path(req_data["output_dir"])      if req_data.get("output_dir")       else DEFAULT_OUTPUT_DIR,
            overrides_file = Path(req_data["overrides_file"])  if req_data.get("overrides_file")  else None,
            site_name      = req_data.get("site_name"),
        )
        result = agent.run(write_artifacts=req_data.get("write_outputs", True))
        hosts   = result.get("stats", {}).get("hosts_total", "?")
        written = result.get("artifacts_written", [])
        outcome = f"Baseline CMDB gerado: {hosts} hosts, {len(written)} artefato(s)."
        return {
            "outcome":     outcome,
            "memory_fact": f"cmdb_agent: baseline gerado ({hosts} hosts, site={req_data.get('site_name', 'default')})",
            "_result":     result,
        }


# ── Agente apply/netbox (low se dry_run, medium caso contrário) ────────────────


class CmdbApplyNetboxAgent(HomelabAgent):
    AGENT_ID    = "cmdb_agent"
    ACTION_TYPE = "cmdb_apply_netbox"
    RISK_LEVEL  = "low"  # sobrescrito dinamicamente

    def _describe_work(self, state: AgentState) -> str:
        req_data = state.get("extra", {})
        pkg  = Path(req_data.get("package_path", "?")).name
        mode = "DRY-RUN" if req_data.get("dry_run", True) else "APPLY REAL"
        return f"Aplicar CMDB no NetBox ({mode}) — pacote {pkg}"

    def _execute_work(self, state: AgentState) -> dict:
        req_data = state.get("extra", {})
        applier = NetBoxPackageApplier(
            package_path   = Path(req_data["package_path"]),
            container_name = req_data.get("container_name", "cmdb-netbox"),
        )
        result   = applier.apply(dry_run=req_data.get("dry_run", True))
        created  = result.get("created", 0)
        updated  = result.get("updated", 0)
        dry_run  = req_data.get("dry_run", True)
        outcome  = (
            f"NetBox apply {'(dry-run) ' if dry_run else ''}concluído: "
            f"{created} criados, {updated} atualizados."
        )
        return {
            "outcome":     outcome,
            "memory_fact": f"cmdb_agent: NetBox apply dry_run={dry_run} ({created} criados, {updated} atualizados)",
            "_result":     result,
        }


# ── Agente apply/glpi (low se dry_run, medium caso contrário) ─────────────────


class CmdbApplyGlpiAgent(HomelabAgent):
    AGENT_ID    = "cmdb_agent"
    ACTION_TYPE = "cmdb_apply_glpi"
    RISK_LEVEL  = "low"

    def _describe_work(self, state: AgentState) -> str:
        req_data = state.get("extra", {})
        pkg  = Path(req_data.get("package_path", "?")).name
        exec_ = req_data.get("execute", False)
        mode  = "APPLY REAL" if exec_ else "DRY-RUN"
        return f"Aplicar CMDB no GLPI ({mode}) — pacote {pkg}"

    def _execute_work(self, state: AgentState) -> dict:
        req_data = state.get("extra", {})
        applier = GLPIPackageApplier(
            package_path = Path(req_data["package_path"]),
            env_file     = Path(req_data.get("env_file", "/etc/default/cmdb")),
            db_container = req_data.get("db_container", ""),
        )
        execute = req_data.get("execute", False)
        result  = applier.apply(dry_run=not execute)
        items   = result.get("items_processed", result.get("total", "?"))
        outcome = (
            f"GLPI apply {'real' if execute else '(dry-run)'} concluído: "
            f"{items} item(s) processado(s)."
        )
        return {
            "outcome":     outcome,
            "memory_fact": f"cmdb_agent: GLPI apply execute={execute} ({items} itens)",
            "_result":     result,
        }


# ── Fachada pública ────────────────────────────────────────────────────────────


class CmdbAgentV2:
    """Drop-in replacement dos route handlers do cmdb_agent com governança LangGraph."""

    def __init__(self):
        self._run_agent   = CmdbRunAgent()
        self._nb_agent    = CmdbApplyNetboxAgent()
        self._glpi_agent  = CmdbApplyGlpiAgent()

    def close(self):
        for a in (self._run_agent, self._nb_agent, self._glpi_agent):
            a.close()

    async def run(self, payload: CmdbAgentRunRequest) -> dict[str, Any]:
        state = await asyncio.to_thread(
            self._run_agent.run,
            target = str(payload.inventory_file or DEFAULT_INVENTORY),
            extra  = payload.model_dump(),
        )
        if state.get("status") == "failed":
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=state.get("error", "cmdb_run failed"))
        return state.get("_result") or {"ok": True, "outcome": state.get("outcome")}

    async def apply_netbox(self, payload: CmdbNetboxApplyRequest) -> dict[str, Any]:
        # Risk dinâmico: dry_run=False → medium (requer aprovação Telegram)
        self._nb_agent.RISK_LEVEL = "low" if payload.dry_run else "medium"
        state = await asyncio.to_thread(
            self._nb_agent.run,
            target = payload.package_path,
            extra  = payload.model_dump(),
        )
        approval = state.get("approval", "")
        if approval == "pending":
            from fastapi import HTTPException
            raise HTTPException(
                status_code=202,
                detail=f"Aguardando aprovação Telegram. thread_id={state.get('thread_id')}",
            )
        if state.get("status") == "failed":
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=state.get("error", "apply_netbox failed"))
        return state.get("_result") or {"ok": True, "outcome": state.get("outcome")}

    async def apply_glpi(self, payload: CmdbGlpiApplyRequest) -> dict[str, Any]:
        self._glpi_agent.RISK_LEVEL = "medium" if payload.execute else "low"
        state = await asyncio.to_thread(
            self._glpi_agent.run,
            target = payload.package_path,
            extra  = payload.model_dump(),
        )
        approval = state.get("approval", "")
        if approval == "pending":
            from fastapi import HTTPException
            raise HTTPException(
                status_code=202,
                detail=f"Aguardando aprovação Telegram. thread_id={state.get('thread_id')}",
            )
        if state.get("status") == "failed":
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=state.get("error", "apply_glpi failed"))
        return state.get("_result") or {"ok": True, "outcome": state.get("outcome")}


# ── Singleton ─────────────────────────────────────────────────────────────────

_agent_v2: CmdbAgentV2 | None = None


def get_cmdb_agent_v2() -> CmdbAgentV2:
    global _agent_v2
    if _agent_v2 is None:
        _agent_v2 = CmdbAgentV2()
    return _agent_v2
