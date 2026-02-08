"""
Rotas FastAPI para Jira Cloud Atlassian (rpa4all.atlassian.net).
Expõe a API real do Jira dentro do Eddie, permitindo que agentes interajam.
"""
import logging
from typing import Optional, List
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .atlassian_client import get_jira_cloud_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jira/cloud", tags=["Jira Cloud (Atlassian)"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class CreateIssueRequest(BaseModel):
    project_key: str = "SCRUM"
    summary: str
    issue_type: str = "Task"
    description: str = ""
    priority: str = "Medium"
    assignee_id: Optional[str] = None
    labels: List[str] = []
    parent_key: Optional[str] = None
    story_points: Optional[int] = None


class TransitionRequest(BaseModel):
    target_status: str
    comment: str = ""


class CommentRequest(BaseModel):
    body: str


class WorklogRequest(BaseModel):
    time_spent: str  # "2h", "30m", "1h 30m"
    comment: str = ""


class CreateSprintRequest(BaseModel):
    board_id: int
    name: str
    goal: str = ""
    duration_days: int = 14


class MoveToSprintRequest(BaseModel):
    sprint_id: int
    issue_keys: List[str]


class JQLSearchRequest(BaseModel):
    jql: str
    fields: Optional[str] = None
    max_results: int = 50


class CreateProjectRequest(BaseModel):
    name: str = "RPA4ALL"
    key: str = "RPA"


class AssignRequest(BaseModel):
    account_id: Optional[str] = None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _client():
    c = get_jira_cloud_client()
    if not c.is_configured:
        raise HTTPException(503, "JIRA_API_TOKEN não configurado. "
                           "Configure via env var ou simple_vault.")
    return c


# ═══════════════════════════ Connection ═══════════════════════════════════════

@router.get("/health")
async def jira_cloud_health():
    """Verifica conexão com Jira Cloud."""
    try:
        c = _client()
        info = await c.server_info()
        me = await c.myself()
        return {
            "status": "connected",
            "url": c.base_url,
            "user": me.get("displayName", me.get("emailAddress", "")),
            "server": info.get("serverTitle", ""),
        }
    except Exception as e:
        raise HTTPException(503, f"Jira Cloud inacessível: {e}")


# ═══════════════════════════ Projects ═════════════════════════════════════════

@router.get("/projects")
async def list_projects():
    return await _client().list_projects()


@router.get("/projects/{key}")
async def get_project(key: str):
    try:
        return await _client().get_project(key)
    except Exception as e:
        raise HTTPException(404, str(e))


@router.post("/projects")
async def create_project(req: CreateProjectRequest):
    """Cria projeto no Jira Cloud."""
    c = _client()
    try:
        me = await c.myself()
        result = await c.create_project(
            name=req.name, key=req.key,
            lead_account_id=me.get("accountId"),
        )
        return result
    except Exception as e:
        raise HTTPException(400, str(e))


# ═══════════════════════════ Issues ═══════════════════════════════════════════

@router.post("/issues")
async def create_issue(req: CreateIssueRequest):
    """Cria issue no Jira Cloud."""
    try:
        return await _client().create_issue(
            project_key=req.project_key,
            summary=req.summary,
            issue_type=req.issue_type,
            description=req.description,
            priority=req.priority,
            assignee_id=req.assignee_id,
            labels=req.labels,
            parent_key=req.parent_key,
            story_points=req.story_points,
        )
    except Exception as e:
        raise HTTPException(400, str(e))


@router.get("/issues/{issue_key}")
async def get_issue(issue_key: str):
    try:
        return await _client().get_issue(issue_key)
    except Exception as e:
        raise HTTPException(404, str(e))


@router.post("/issues/search")
async def search_issues(req: JQLSearchRequest):
    """Busca issues via JQL."""
    try:
        return await _client().search_issues(req.jql, req.fields, req.max_results)
    except Exception as e:
        raise HTTPException(400, str(e))


@router.delete("/issues/{issue_key}")
async def delete_issue(issue_key: str):
    try:
        return await _client().delete_issue(issue_key)
    except Exception as e:
        raise HTTPException(400, str(e))


# ═══════════════════════════ Transitions ══════════════════════════════════════

@router.get("/issues/{issue_key}/transitions")
async def get_transitions(issue_key: str):
    return await _client().get_transitions(issue_key)


@router.post("/issues/{issue_key}/transition")
async def transition_issue(issue_key: str, req: TransitionRequest):
    """Move issue para um novo status."""
    try:
        return await _client().move_issue_to_status(
            issue_key, req.target_status, req.comment)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(400, str(e))


@router.patch("/issues/{issue_key}/assign")
async def assign_issue(issue_key: str, req: AssignRequest):
    return await _client().assign_issue(issue_key, req.account_id)


# ═══════════════════════════ Comments ═════════════════════════════════════════

@router.get("/issues/{issue_key}/comments")
async def get_comments(issue_key: str):
    return await _client().get_comments(issue_key)


@router.post("/issues/{issue_key}/comments")
async def add_comment(issue_key: str, req: CommentRequest):
    return await _client().add_comment(issue_key, req.body)


# ═══════════════════════════ Worklogs ═════════════════════════════════════════

@router.get("/issues/{issue_key}/worklogs")
async def get_worklogs(issue_key: str):
    return await _client().get_worklogs(issue_key)


@router.post("/issues/{issue_key}/worklogs")
async def add_worklog(issue_key: str, req: WorklogRequest):
    """Apontar horas no Jira Cloud."""
    return await _client().add_worklog(issue_key, req.time_spent, req.comment)


# ═══════════════════════════ Sprints ══════════════════════════════════════════

@router.get("/boards")
async def get_boards(project_key: str = "SCRUM"):
    return await _client().get_boards(project_key)


@router.get("/boards/{board_id}/sprints")
async def get_sprints(board_id: int, state: Optional[str] = None):
    return await _client().get_sprints(board_id, state)


@router.post("/sprints")
async def create_sprint(req: CreateSprintRequest):
    """Cria sprint no Jira Cloud."""
    now = datetime.now()
    end = now + timedelta(days=req.duration_days)
    return await _client().create_sprint(
        board_id=req.board_id,
        name=req.name,
        goal=req.goal,
        start_date=now.strftime("%Y-%m-%dT%H:%M:%S.000+0000"),
        end_date=end.strftime("%Y-%m-%dT%H:%M:%S.000+0000"),
    )


@router.post("/sprints/move")
async def move_to_sprint(req: MoveToSprintRequest):
    return await _client().move_to_sprint(req.sprint_id, req.issue_keys)


@router.get("/sprints/{sprint_id}/issues")
async def get_sprint_issues(sprint_id: int):
    return await _client().get_sprint_issues(sprint_id)


# ═══════════════════════════ Users ════════════════════════════════════════════

@router.get("/users/search")
async def search_users(query: str):
    return await _client().search_users(query)


@router.get("/users/assignable")
async def get_assignable_users(project_key: str = "RPA"):
    return await _client().get_assignable_users(project_key)


# ═══════════════════════════ Meta ═════════════════════════════════════════════

@router.get("/statuses")
async def get_statuses(project_key: Optional[str] = None):
    return await _client().get_statuses(project_key)


@router.get("/priorities")
async def get_priorities():
    return await _client().get_priorities()


@router.get("/labels")
async def get_labels():
    return await _client().get_labels()


@router.get("/issue-types")
async def get_issue_types(project_key: str = "RPA"):
    return await _client().get_issue_types(project_key)
