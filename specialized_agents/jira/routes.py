"""
Rotas FastAPI do Jira RPA4ALL.
Endpoints para gerenciamento de projetos, tickets, sprints, worklogs e PO agent.
"""
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .jira_board import get_jira_board
from .po_agent import ProductOwnerAgent
from .models import TicketStatus, TicketPriority, TicketType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jira", tags=["Jira RPA4ALL"])


# ─── Schemas Pydantic ─────────────────────────────────────────────────────────

class CreateTicketRequest(BaseModel):
    title: str
    description: str = ""
    ticket_type: str = "task"
    priority: str = "medium"
    assignee: str = ""
    epic_id: Optional[str] = None
    sprint_id: Optional[str] = None
    story_points: int = 0
    estimated_hours: float = 0.0
    labels: List[str] = []
    parent_id: Optional[str] = None


class UpdateStatusRequest(BaseModel):
    status: str
    agent: str = "system"


class CreateEpicRequest(BaseModel):
    title: str
    description: str = ""
    owner: str = "po_agent"


class CreateSprintRequest(BaseModel):
    name: str
    goal: str = ""
    duration_days: int = 14


class PlanSprintRequest(BaseModel):
    name: str
    goal: str = ""
    ticket_ids: List[str] = []
    duration_days: int = 14
    auto_select: bool = True


class CreateWorklogRequest(BaseModel):
    agent_name: str
    description: str
    time_spent_minutes: int
    auto_logged: bool = False


class AddCommentRequest(BaseModel):
    author: str
    body: str


class ReviewDeliveryRequest(BaseModel):
    accept: bool
    feedback: str = ""


class AutoCreateRequest(BaseModel):
    project_description: str


class EpicWithStoriesRequest(BaseModel):
    epic_title: str
    epic_description: str = ""
    stories: List[dict] = []


class AssignTicketRequest(BaseModel):
    assignee: str


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _board():
    return get_jira_board()


def _po():
    return ProductOwnerAgent()


# ═══════════════════════════ Project ══════════════════════════════════════════

@router.get("/project")
async def get_project():
    """Retorna informações do projeto RPA4ALL."""
    return _board().project.to_dict()


@router.get("/metrics")
async def get_metrics():
    """Retorna métricas do board."""
    return _board().get_board_metrics()


# ═══════════════════════════ Epics ════════════════════════════════════════════

@router.get("/epics")
async def list_epics():
    return [e.to_dict() for e in _board().list_epics()]


@router.post("/epics")
async def create_epic(req: CreateEpicRequest):
    epic = _board().create_epic(req.title, req.description, req.owner)
    return epic.to_dict()


@router.post("/epics/with-stories")
async def create_epic_with_stories(req: EpicWithStoriesRequest):
    """Cria Epic com suas Stories (PO Agent)."""
    result = await _po().create_epic_with_stories(
        req.epic_title, req.epic_description, req.stories)
    return result


# ═══════════════════════════ Sprints ══════════════════════════════════════════

@router.get("/sprints")
async def list_sprints():
    return [s.to_dict() for s in _board().list_sprints()]


@router.get("/sprints/active")
async def get_active_sprint():
    sprint = _board().get_active_sprint()
    if not sprint:
        raise HTTPException(404, "Nenhum sprint ativo")
    return sprint.to_dict()


@router.post("/sprints")
async def create_sprint(req: CreateSprintRequest):
    sprint = _board().create_sprint(req.name, req.goal, req.duration_days)
    return sprint.to_dict()


@router.post("/sprints/plan")
async def plan_sprint(req: PlanSprintRequest):
    """PO planeja sprint (com auto-seleção opcional de tickets)."""
    result = await _po().plan_sprint(
        req.name, req.goal, req.ticket_ids, req.duration_days, req.auto_select)
    return result


@router.post("/sprints/{sprint_id}/start")
async def start_sprint(sprint_id: str):
    sprint = _board().start_sprint(sprint_id)
    if not sprint:
        raise HTTPException(404, "Sprint não encontrado")
    return sprint.to_dict()


@router.post("/sprints/{sprint_id}/complete")
async def complete_sprint(sprint_id: str):
    sprint = _board().complete_sprint(sprint_id)
    if not sprint:
        raise HTTPException(404, "Sprint não encontrado")
    return sprint.to_dict()


# ═══════════════════════════ Tickets ══════════════════════════════════════════

@router.get("/tickets")
async def list_tickets(
    status: Optional[str] = None,
    assignee: Optional[str] = None,
    sprint_id: Optional[str] = None,
    epic_id: Optional[str] = None,
    ticket_type: Optional[str] = None,
):
    kwargs = {}
    if status:
        kwargs["status"] = TicketStatus(status)
    if assignee:
        kwargs["assignee"] = assignee
    if sprint_id:
        kwargs["sprint_id"] = sprint_id
    if epic_id:
        kwargs["epic_id"] = epic_id
    if ticket_type:
        kwargs["ticket_type"] = TicketType(ticket_type)
    tickets = _board().list_tickets(**kwargs)
    return [t.to_dict() for t in tickets]


@router.get("/tickets/search")
async def search_tickets(q: str):
    return [t.to_dict() for t in _board().search_tickets(q)]


@router.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: str):
    ticket = _board().get_ticket(ticket_id) or _board().get_ticket_by_key(ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket não encontrado")
    return ticket.to_dict()


@router.post("/tickets")
async def create_ticket(req: CreateTicketRequest):
    ticket = _board().create_ticket(
        title=req.title,
        description=req.description,
        ticket_type=TicketType(req.ticket_type),
        priority=TicketPriority(req.priority),
        assignee=req.assignee,
        epic_id=req.epic_id,
        sprint_id=req.sprint_id,
        story_points=req.story_points,
        estimated_hours=req.estimated_hours,
        labels=req.labels,
        parent_id=req.parent_id,
    )
    return ticket.to_dict()


@router.patch("/tickets/{ticket_id}/status")
async def update_ticket_status(ticket_id: str, req: UpdateStatusRequest):
    ticket = _board().update_ticket_status(
        ticket_id, TicketStatus(req.status), req.agent)
    if not ticket:
        raise HTTPException(404, "Ticket não encontrado")
    return ticket.to_dict()


@router.patch("/tickets/{ticket_id}/assign")
async def assign_ticket(ticket_id: str, req: AssignTicketRequest):
    ticket = _board().assign_ticket(ticket_id, req.assignee)
    if not ticket:
        raise HTTPException(404, "Ticket não encontrado")
    return ticket.to_dict()


# ═══════════════════════════ Worklogs ═════════════════════════════════════════

@router.get("/tickets/{ticket_id}/worklogs")
async def get_ticket_worklogs(ticket_id: str):
    return [w.to_dict() for w in _board().get_worklogs(ticket_id=ticket_id)]


@router.post("/tickets/{ticket_id}/worklogs")
async def add_worklog(ticket_id: str, req: CreateWorklogRequest):
    worklog = _board().log_work(
        ticket_id=ticket_id,
        agent_name=req.agent_name,
        description=req.description,
        time_spent_minutes=req.time_spent_minutes,
        auto_logged=req.auto_logged,
    )
    if not worklog:
        raise HTTPException(404, "Ticket não encontrado")
    return worklog.to_dict()


@router.get("/worklogs")
async def list_worklogs(agent_name: Optional[str] = None):
    return [w.to_dict() for w in _board().get_worklogs(agent_name=agent_name)]


# ═══════════════════════════ Comments ═════════════════════════════════════════

@router.post("/tickets/{ticket_id}/comments")
async def add_comment(ticket_id: str, req: AddCommentRequest):
    comment = _board().add_comment(ticket_id, req.author, req.body)
    if not comment:
        raise HTTPException(404, "Ticket não encontrado")
    return comment.to_dict()


# ═══════════════════════════ PO Agent ═════════════════════════════════════════

@router.get("/po/status")
async def po_status():
    return _po().get_status()


@router.post("/po/review/{ticket_id}")
async def po_review_delivery(ticket_id: str, req: ReviewDeliveryRequest):
    return await _po().review_delivery(ticket_id, req.accept, req.feedback)


@router.post("/po/distribute")
async def po_distribute_tickets(sprint_id: Optional[str] = None):
    return await _po().distribute_tickets(sprint_id)


@router.get("/po/standup")
async def po_daily_standup():
    return await _po().daily_standup_report()


@router.get("/po/sprint-report")
async def po_sprint_report(sprint_id: Optional[str] = None):
    return await _po().sprint_report(sprint_id)


@router.post("/po/auto-create")
async def po_auto_create_tasks(req: AutoCreateRequest):
    """Usa LLM para criar Epic + Stories a partir de descrição de projeto."""
    return await _po().auto_create_tasks_from_description(req.project_description)


# ═══════════════════════════ Agent-specific ═══════════════════════════════════

@router.get("/agents/{agent_name}/tickets")
async def get_agent_tickets(agent_name: str):
    """Retorna tickets de um agente agrupados por status."""
    grouped = _board().get_agent_tickets(agent_name)
    return {status: [t.to_dict() for t in tickets] for status, tickets in grouped.items()}


@router.get("/agents/{agent_name}/summary")
async def get_agent_summary(agent_name: str):
    """Resumo de atividade de um agente."""
    grouped = _board().get_agent_tickets(agent_name)
    total_logged = 0.0
    total_points = 0
    for tickets in grouped.values():
        for t in tickets:
            total_logged += t.logged_hours
            if t.status == TicketStatus.DONE:
                total_points += t.story_points
    return {
        "agent": agent_name,
        "tickets_by_status": {s: len(tl) for s, tl in grouped.items()},
        "total_tickets": sum(len(tl) for tl in grouped.values()),
        "total_logged_hours": round(total_logged, 1),
        "total_points_completed": total_points,
    }


@router.get("/agents/{agent_name}/next")
async def get_agent_next_ticket(agent_name: str):
    """Retorna o próximo ticket a ser trabalhado pelo agente."""
    tickets = _board().list_tickets(assignee=agent_name, status=TicketStatus.TODO)
    if not tickets:
        tickets = _board().list_tickets(assignee=agent_name, status=TicketStatus.BACKLOG)
    if not tickets:
        raise HTTPException(404, "Nenhum ticket disponível")
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "trivial": 4}
    tickets.sort(key=lambda t: priority_order.get(t.priority.value, 5))
    return tickets[0].to_dict()
