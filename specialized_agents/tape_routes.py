#!/usr/bin/env python3
"""Rotas FastAPI para o agente FC HBA Cable Tester.

Prefixo: /tape
Endpoints:
  POST /tape/hba-test        — inicia teste em background e retorna job_id
  GET  /tape/hba-test/status — status do job em andamento
  GET  /tape/hba-test/report — último relatório gerado
  GET  /tape/health          — healthcheck da rota
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tape", tags=["tape"])

# ─── Estado em memória (single-process) ──────────────────────────────────────

_last_report: dict[str, Any] | None = None
_active_job: dict[str, Any] | None = None  # {"job_id", "started_at", "status"}
_last_component_quality_report: dict[str, Any] | None = None
_active_component_quality_job: dict[str, Any] | None = None


# ─── Schemas ──────────────────────────────────────────────────────────────────

class HBATestRequest(BaseModel):
    """Parâmetros para disparo do teste HBA."""

    hosts: list[str] = Field(
        default=["host0", "host7"],
        description="Portas HBA a testar (ex: host0, host7)",
    )
    device: str = Field(
        default="/dev/sg0",
        description="Dispositivo SCSI do drive de fita",
    )
    window: int = Field(
        default=60,
        ge=0,
        le=600,
        description="Janela de monitoramento de estabilidade em segundos (0 = modo rápido)",
    )
    fast: bool = Field(
        default=False,
        description="Pular testes lentos (estabilidade/reconnect)",
    )


class HBATestJobStatus(BaseModel):
    """Status de um job de teste HBA."""

    job_id: str
    status: str  # queued | running | done | error
    started_at: str
    finished_at: str | None = None
    error: str | None = None
    report_available: bool = False


class TapeComponentQualityRequest(BaseModel):
    """Parametros para coleta de qualidade da stack de fita."""

    hosts: list[str] = Field(
        default=["host0"],
        description="Portas HBA a incluir na avaliacao",
    )
    device: str = Field(
        default="/dev/sg0",
        description="Dispositivo sg do drive de fita",
    )
    st_device: str = Field(
        default="/dev/st0",
        description="Dispositivo st do drive de fita",
    )
    nst_device: str = Field(
        default="/dev/nst0",
        description="Dispositivo nst do drive de fita",
    )
    service: str = Field(
        default="ltfs-lto6.service",
        description="Unit systemd do LTFS",
    )
    mount_point: str = Field(
        default="/mnt/tape/lto6",
        description="Mountpoint LTFS",
    )
    work_dir: str = Field(
        default="/var/lib/ltfs/work",
        description="Diretorio de trabalho LTFS",
    )


# ─── Background task ─────────────────────────────────────────────────────────

async def _run_hba_test_task(
    job_id: str,
    req: HBATestRequest,
) -> None:
    """Executa teste HBA em background e armazena resultado."""
    global _last_report, _active_job

    if _active_job:
        _active_job["status"] = "running"
    try:
        # Import lazy para não falhar na inicialização do FastAPI fora do NAS
        from tools.fc_hba_tester import run_dual_hba_test, report_to_dict

        report = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: run_dual_hba_test(
                hosts=req.hosts,
                device=req.device,
                stability_window=0 if req.fast else req.window,
                skip_slow=req.fast,
            ),
        )
        _last_report = report_to_dict(report)
        if _active_job:
            _active_job["status"] = "done"
            _active_job["finished_at"] = datetime.now().isoformat()
            _active_job["report_available"] = True
    except Exception as exc:
        logger.exception("Erro ao executar HBA test job %s", job_id)
        if _active_job:
            _active_job["status"] = "error"
            _active_job["error"] = str(exc)
            _active_job["finished_at"] = datetime.now().isoformat()


async def _run_component_quality_task(
    job_id: str,
    req: TapeComponentQualityRequest,
) -> None:
    """Executa coleta de qualidade da stack de fita em background."""
    global _last_component_quality_report, _active_component_quality_job

    if _active_component_quality_job:
        _active_component_quality_job["status"] = "running"
    try:
        from tools.tape_component_quality_agent import collect_component_quality, report_to_dict

        report = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: collect_component_quality(
                hosts=req.hosts,
                device=req.device,
                st_device=req.st_device,
                nst_device=req.nst_device,
                service_name=req.service,
                mount_point=req.mount_point,
                work_dir=req.work_dir,
            ),
        )
        _last_component_quality_report = report_to_dict(report)
        if _active_component_quality_job:
            _active_component_quality_job["status"] = "done"
            _active_component_quality_job["finished_at"] = datetime.now().isoformat()
            _active_component_quality_job["report_available"] = True
    except Exception as exc:
        logger.exception("Erro ao executar tape component quality job %s", job_id)
        if _active_component_quality_job:
            _active_component_quality_job["status"] = "error"
            _active_component_quality_job["error"] = str(exc)
            _active_component_quality_job["finished_at"] = datetime.now().isoformat()


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/health")
async def tape_health() -> dict[str, Any]:
    """Healthcheck das rotas de fita."""
    return {
        "ok": True,
        "service": "tape-routes",
        "job_active": _active_job is not None and _active_job.get("status") == "running",
        "report_available": _last_report is not None,
    }


@router.post("/hba-test", response_model=HBATestJobStatus, status_code=202)
async def start_hba_test(
    req: HBATestRequest,
    background_tasks: BackgroundTasks,
) -> HBATestJobStatus:
    """Inicia o teste de qualidade dual-HBA em background.

    Retorna imediatamente com job_id. Use GET /tape/hba-test/status para acompanhar.
    """
    global _active_job

    if _active_job and _active_job.get("status") == "running":
        raise HTTPException(
            status_code=409,
            detail=f"Já existe um teste em andamento (job_id={_active_job['job_id']}). "
                   "Aguarde conclusão antes de iniciar novo teste.",
        )

    job_id = str(uuid.uuid4())
    started_at = datetime.now().isoformat()

    _active_job = {
        "job_id": job_id,
        "status": "queued",
        "started_at": started_at,
        "finished_at": None,
        "error": None,
        "report_available": False,
    }

    background_tasks.add_task(_run_hba_test_task, job_id, req)

    logger.info(
        "HBA test job %s iniciado: hosts=%s device=%s fast=%s",
        job_id, req.hosts, req.device, req.fast,
    )
    return HBATestJobStatus(**_active_job)


@router.get("/hba-test/status", response_model=HBATestJobStatus)
async def get_hba_test_status() -> HBATestJobStatus:
    """Retorna status do job de teste HBA mais recente."""
    if not _active_job:
        raise HTTPException(status_code=404, detail="Nenhum teste HBA foi iniciado ainda.")
    return HBATestJobStatus(**_active_job)


@router.get("/hba-test/report")
async def get_hba_test_report() -> dict[str, Any]:
    """Retorna o último relatório completo de teste HBA."""
    if not _last_report:
        raise HTTPException(
            status_code=404,
            detail="Nenhum relatório disponível. Execute POST /tape/hba-test primeiro.",
        )
    return _last_report


@router.post("/component-quality", response_model=HBATestJobStatus, status_code=202)
async def start_component_quality_test(
    req: TapeComponentQualityRequest,
    background_tasks: BackgroundTasks,
) -> HBATestJobStatus:
    """Inicia avaliacao de qualidade da stack de fita em background."""
    global _active_component_quality_job

    if _active_component_quality_job and _active_component_quality_job.get("status") == "running":
        raise HTTPException(
            status_code=409,
            detail=(
                "Ja existe uma avaliacao de qualidade em andamento "
                f"(job_id={_active_component_quality_job['job_id']})."
            ),
        )

    job_id = str(uuid.uuid4())
    started_at = datetime.now().isoformat()
    _active_component_quality_job = {
        "job_id": job_id,
        "status": "queued",
        "started_at": started_at,
        "finished_at": None,
        "error": None,
        "report_available": False,
    }
    background_tasks.add_task(_run_component_quality_task, job_id, req)
    return HBATestJobStatus(**_active_component_quality_job)


@router.get("/component-quality/status", response_model=HBATestJobStatus)
async def get_component_quality_status() -> HBATestJobStatus:
    """Retorna o status da ultima avaliacao de qualidade da stack de fita."""
    if not _active_component_quality_job:
        raise HTTPException(status_code=404, detail="Nenhuma avaliacao foi iniciada ainda.")
    return HBATestJobStatus(**_active_component_quality_job)


@router.get("/component-quality/report")
async def get_component_quality_report() -> dict[str, Any]:
    """Retorna o ultimo relatorio de qualidade da stack de fita."""
    if not _last_component_quality_report:
        raise HTTPException(
            status_code=404,
            detail="Nenhum relatorio disponivel. Execute POST /tape/component-quality primeiro.",
        )
    return _last_component_quality_report
