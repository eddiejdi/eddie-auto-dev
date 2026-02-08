"""
Modelos de dados do Jira RPA4ALL.
Tickets, Sprints, Epics, Worklogs, etc.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any


# ─── Enums ────────────────────────────────────────────────────────────────────

class TicketStatus(Enum):
    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    TESTING = "testing"
    DONE = "done"
    CANCELLED = "cancelled"


class TicketPriority(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    TRIVIAL = "trivial"


class TicketType(Enum):
    EPIC = "epic"
    STORY = "story"
    TASK = "task"
    BUG = "bug"
    SUBTASK = "subtask"
    IMPROVEMENT = "improvement"
    SPIKE = "spike"


class SprintStatus(Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    COMPLETED = "completed"


# ─── Modelos ──────────────────────────────────────────────────────────────────

@dataclass
class JiraWorklog:
    """Apontamento de horas de trabalho"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    ticket_id: str = ""
    agent_name: str = ""
    description: str = ""
    time_spent_minutes: int = 0
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None
    auto_logged: bool = False  # Se foi registrado automaticamente pelo agente
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "agent_name": self.agent_name,
            "description": self.description,
            "time_spent_minutes": self.time_spent_minutes,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "auto_logged": self.auto_logged,
            "metadata": self.metadata,
        }


@dataclass
class JiraComment:
    """Comentário em um ticket"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    author: str = ""
    body: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "author": self.author,
            "body": self.body,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class JiraTicket:
    """Ticket Jira (Story, Task, Bug, etc.)"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    key: str = ""                          # ex: RPA-001
    project_key: str = "RPA"
    title: str = ""
    description: str = ""
    ticket_type: TicketType = TicketType.TASK
    status: TicketStatus = TicketStatus.BACKLOG
    priority: TicketPriority = TicketPriority.MEDIUM
    assignee: str = ""                     # Nome do agente
    reporter: str = "po_agent"             # Quem criou
    epic_id: Optional[str] = None
    sprint_id: Optional[str] = None
    parent_id: Optional[str] = None        # Para subtasks
    labels: List[str] = field(default_factory=list)
    story_points: int = 0
    estimated_hours: float = 0.0
    logged_hours: float = 0.0
    comments: List[JiraComment] = field(default_factory=list)
    worklogs: List[JiraWorklog] = field(default_factory=list)
    subtasks: List[str] = field(default_factory=list)   # IDs dos subtasks
    dependencies: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    due_date: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "key": self.key,
            "project_key": self.project_key,
            "title": self.title,
            "description": self.description,
            "ticket_type": self.ticket_type.value,
            "status": self.status.value,
            "priority": self.priority.value,
            "assignee": self.assignee,
            "reporter": self.reporter,
            "epic_id": self.epic_id,
            "sprint_id": self.sprint_id,
            "parent_id": self.parent_id,
            "labels": self.labels,
            "story_points": self.story_points,
            "estimated_hours": self.estimated_hours,
            "logged_hours": self.logged_hours,
            "comments": [c.to_dict() for c in self.comments],
            "worklogs": [w.to_dict() for w in self.worklogs],
            "subtasks": self.subtasks,
            "dependencies": self.dependencies,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "metadata": self.metadata,
        }


@dataclass
class JiraEpic:
    """Epic - Agrupador de Stories"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    key: str = ""
    title: str = ""
    description: str = ""
    status: TicketStatus = TicketStatus.TODO
    owner: str = "po_agent"
    tickets: List[str] = field(default_factory=list)  # IDs de tickets
    start_date: Optional[datetime] = None
    target_date: Optional[datetime] = None
    progress_pct: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "key": self.key,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "owner": self.owner,
            "tickets": self.tickets,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "target_date": self.target_date.isoformat() if self.target_date else None,
            "progress_pct": self.progress_pct,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class JiraSprint:
    """Sprint - Iteração de desenvolvimento"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    goal: str = ""
    status: SprintStatus = SprintStatus.PLANNING
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    tickets: List[str] = field(default_factory=list)  # IDs de tickets
    velocity: int = 0                                  # Story points planejados
    completed_points: int = 0
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def days_remaining(self) -> int:
        if not self.end_date:
            return 0
        delta = self.end_date - datetime.now()
        return max(0, delta.days)

    @property
    def progress_pct(self) -> float:
        if self.velocity == 0:
            return 0.0
        return round((self.completed_points / self.velocity) * 100, 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "goal": self.goal,
            "status": self.status.value,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "tickets": self.tickets,
            "velocity": self.velocity,
            "completed_points": self.completed_points,
            "days_remaining": self.days_remaining,
            "progress_pct": self.progress_pct,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class JiraProject:
    """Projeto no Jira RPA4ALL"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    key: str = "RPA"
    name: str = "RPA4ALL"
    description: str = "Automações e Agentes Inteligentes"
    lead: str = "po_agent"
    team_members: List[str] = field(default_factory=list)  # Nomes dos agentes
    epics: List[JiraEpic] = field(default_factory=list)
    sprints: List[JiraSprint] = field(default_factory=list)
    ticket_counter: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def next_ticket_key(self) -> str:
        self.ticket_counter += 1
        return f"{self.key}-{self.ticket_counter:03d}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "lead": self.lead,
            "team_members": self.team_members,
            "epics": [e.to_dict() for e in self.epics],
            "sprints": [s.to_dict() for s in self.sprints],
            "ticket_counter": self.ticket_counter,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }
