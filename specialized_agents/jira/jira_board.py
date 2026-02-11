"""
JiraBoard — Board central do Jira RPA4ALL.
Gerencia projetos, tickets, sprints, worklogs e a relação com agentes.
Persistência em JSON (SQLite/Postgres via interceptor já salva mensagens do bus).
"""
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

from .models import (
    JiraProject, JiraEpic, JiraSprint, JiraTicket, JiraWorklog,
    JiraComment, TicketStatus, TicketPriority, TicketType, SprintStatus,
)

# Import opcional para publicação no bus
try:
    from specialized_agents.agent_communication_bus import (
        get_communication_bus, MessageType,
        log_task_start, log_task_end,
    )
    BUS_AVAILABLE = True
except ImportError:
    BUS_AVAILABLE = False

# Diretório de persistência
DATA_DIR = Path(__file__).parent.parent.parent / "agent_data" / "jira"
DATA_DIR.mkdir(parents=True, exist_ok=True)

_DB_PATH = DATA_DIR / "jira_rpa4all.json"

# ─── Singleton thread-safe ────────────────────────────────────────────────────

_instance: Optional["JiraBoard"] = None
_lock = threading.Lock()


def get_jira_board() -> "JiraBoard":
    """Singleton do JiraBoard."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = JiraBoard()
    return _instance


# ─── Classe Principal ─────────────────────────────────────────────────────────

class JiraBoard:
    """
    Core do sistema Jira RPA4ALL.
    CRUD completo para projetos, epics, sprints, tickets e worklogs.
    Publica eventos significativos no AgentCommunicationBus.
    """

    def __init__(self):
        self.project: JiraProject = JiraProject()
        self.tickets: Dict[str, JiraTicket] = {}
        self._load()

    # ═══════════════════════════ Persistência ═════════════════════════════════

    def _save(self):
        """Salva estado atual em JSON."""
        state = {
            "project": self.project.to_dict(),
            "tickets": {k: v.to_dict() for k, v in self.tickets.items()},
        }
        _DB_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False, default=str))

    def _load(self):
        """Carrega estado do disco se existir."""
        if not _DB_PATH.exists():
            self._bootstrap_project()
            self._save()
            return
        try:
            raw = json.loads(_DB_PATH.read_text())
            proj = raw.get("project", {})
            self.project = JiraProject(
                id=proj.get("id", self.project.id),
                key=proj.get("key", "RPA"),
                name=proj.get("name", "RPA4ALL"),
                description=proj.get("description", ""),
                lead=proj.get("lead", "po_agent"),
                team_members=proj.get("team_members", []),
                ticket_counter=proj.get("ticket_counter", 0),
            )
            # Reconstituir epics
            for ep in proj.get("epics", []):
                self.project.epics.append(JiraEpic(
                    id=ep["id"], key=ep.get("key", ""), title=ep.get("title", ""),
                    description=ep.get("description", ""),
                    status=TicketStatus(ep.get("status", "todo")),
                    owner=ep.get("owner", "po_agent"),
                    tickets=ep.get("tickets", []),
                ))
            # Reconstituir sprints
            for sp in proj.get("sprints", []):
                sprint = JiraSprint(
                    id=sp["id"], name=sp.get("name", ""), goal=sp.get("goal", ""),
                    status=SprintStatus(sp.get("status", "planning")),
                    tickets=sp.get("tickets", []),
                    velocity=sp.get("velocity", 0),
                    completed_points=sp.get("completed_points", 0),
                )
                if sp.get("start_date"):
                    sprint.start_date = datetime.fromisoformat(sp["start_date"])
                if sp.get("end_date"):
                    sprint.end_date = datetime.fromisoformat(sp["end_date"])
                self.project.sprints.append(sprint)
            # Reconstituir tickets
            for tid, td in raw.get("tickets", {}).items():
                ticket = JiraTicket(
                    id=td["id"], key=td.get("key", ""),
                    project_key=td.get("project_key", "RPA"),
                    title=td.get("title", ""),
                    description=td.get("description", ""),
                    ticket_type=TicketType(td.get("ticket_type", "task")),
                    status=TicketStatus(td.get("status", "backlog")),
                    priority=TicketPriority(td.get("priority", "medium")),
                    assignee=td.get("assignee", ""),
                    reporter=td.get("reporter", "po_agent"),
                    epic_id=td.get("epic_id"),
                    sprint_id=td.get("sprint_id"),
                    parent_id=td.get("parent_id"),
                    labels=td.get("labels", []),
                    story_points=td.get("story_points", 0),
                    estimated_hours=td.get("estimated_hours", 0.0),
                    logged_hours=td.get("logged_hours", 0.0),
                    subtasks=td.get("subtasks", []),
                    dependencies=td.get("dependencies", []),
                )
                if td.get("created_at"):
                    ticket.created_at = datetime.fromisoformat(td["created_at"])
                if td.get("updated_at"):
                    ticket.updated_at = datetime.fromisoformat(td["updated_at"])
                if td.get("resolved_at"):
                    ticket.resolved_at = datetime.fromisoformat(td["resolved_at"])
                if td.get("due_date"):
                    ticket.due_date = datetime.fromisoformat(td["due_date"])
                # Comentários
                for c in td.get("comments", []):
                    ticket.comments.append(JiraComment(
                        id=c["id"], author=c.get("author", ""),
                        body=c.get("body", ""),
                    ))
                # Worklogs
                for w in td.get("worklogs", []):
                    ticket.worklogs.append(JiraWorklog(
                        id=w["id"], ticket_id=w.get("ticket_id", ""),
                        agent_name=w.get("agent_name", ""),
                        description=w.get("description", ""),
                        time_spent_minutes=w.get("time_spent_minutes", 0),
                        auto_logged=w.get("auto_logged", False),
                    ))
                self.tickets[tid] = ticket
        except Exception as e:
            print(f"[JiraBoard] Erro ao carregar dados: {e}")
            self._bootstrap_project()
            self._save()

    def _bootstrap_project(self):
        """Cria projeto inicial RPA4ALL com agentes cadastrados."""
        agents = [
            "python_agent", "javascript_agent", "typescript_agent",
            "go_agent", "rust_agent", "java_agent", "csharp_agent",
            "php_agent", "po_agent",
        ]
        self.project = JiraProject(
            key="RPA",
            name="RPA4ALL",
            description="Plataforma de Automação Inteligente — Agentes especializados por linguagem",
            lead="po_agent",
            team_members=agents,
        )

    # ═══════════════════════════ Bus helpers ══════════════════════════════════

    def _publish(self, mtype: str, source: str, target: str, content: str, meta: Dict = None):
        if not BUS_AVAILABLE:
            return
        bus = get_communication_bus()
        try:
            bus.publish(MessageType(mtype), source, target, content, meta or {})
        except Exception:
            pass

    # ═══════════════════════════ Epics ════════════════════════════════════════

    def create_epic(self, title: str, description: str = "", owner: str = "po_agent",
                    target_date: datetime = None) -> JiraEpic:
        key = self.project.next_ticket_key()
        epic = JiraEpic(
            key=key, title=title, description=description,
            owner=owner, start_date=datetime.now(), target_date=target_date,
        )
        self.project.epics.append(epic)
        self._save()
        self._publish("task_start", "po_agent", "all",
                       f"Epic criado: {key} — {title}", {"epic_id": epic.id, "key": key})
        return epic

    def get_epic(self, epic_id: str) -> Optional[JiraEpic]:
        return next((e for e in self.project.epics if e.id == epic_id), None)

    def list_epics(self) -> List[JiraEpic]:
        return list(self.project.epics)

    # ═══════════════════════════ Sprints ══════════════════════════════════════

    def create_sprint(self, name: str, goal: str = "",
                      duration_days: int = 14) -> JiraSprint:
        sprint = JiraSprint(
            name=name, goal=goal,
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=duration_days),
        )
        self.project.sprints.append(sprint)
        self._save()
        self._publish("coordinator", "po_agent", "all",
                       f"Sprint criado: {name} ({duration_days}d)", {"sprint_id": sprint.id})
        return sprint

    def start_sprint(self, sprint_id: str) -> Optional[JiraSprint]:
        sprint = self.get_sprint(sprint_id)
        if sprint:
            sprint.status = SprintStatus.ACTIVE
            sprint.start_date = datetime.now()
            self._save()
            self._publish("coordinator", "po_agent", "all",
                           f"Sprint iniciado: {sprint.name}", {"sprint_id": sprint_id})
        return sprint

    def complete_sprint(self, sprint_id: str) -> Optional[JiraSprint]:
        sprint = self.get_sprint(sprint_id)
        if sprint:
            sprint.status = SprintStatus.COMPLETED
            # Calcular completed_points baseado nos tickets DONE
            done_pts = sum(
                t.story_points for t in self.tickets.values()
                if t.sprint_id == sprint_id and t.status == TicketStatus.DONE
            )
            sprint.completed_points = done_pts
            self._save()
            self._publish("coordinator", "po_agent", "all",
                           f"Sprint finalizado: {sprint.name} | {done_pts}/{sprint.velocity} pts",
                           {"sprint_id": sprint_id})
        return sprint

    def get_sprint(self, sprint_id: str) -> Optional[JiraSprint]:
        return next((s for s in self.project.sprints if s.id == sprint_id), None)

    def get_active_sprint(self) -> Optional[JiraSprint]:
        return next((s for s in self.project.sprints if s.status == SprintStatus.ACTIVE), None)

    def list_sprints(self) -> List[JiraSprint]:
        return list(self.project.sprints)

    # ═══════════════════════════ Tickets ══════════════════════════════════════

    def create_ticket(
        self, title: str, description: str = "",
        ticket_type: TicketType = TicketType.TASK,
        priority: TicketPriority = TicketPriority.MEDIUM,
        assignee: str = "", reporter: str = "po_agent",
        epic_id: str = None, sprint_id: str = None,
        story_points: int = 0, estimated_hours: float = 0.0,
        labels: List[str] = None, due_date: datetime = None,
        parent_id: str = None,
    ) -> JiraTicket:
        key = self.project.next_ticket_key()
        ticket = JiraTicket(
            key=key, project_key=self.project.key,
            title=title, description=description,
            ticket_type=ticket_type, priority=priority,
            assignee=assignee, reporter=reporter,
            epic_id=epic_id, sprint_id=sprint_id,
            story_points=story_points, estimated_hours=estimated_hours,
            labels=labels or [], due_date=due_date, parent_id=parent_id,
        )
        self.tickets[ticket.id] = ticket

        # Vincular ao sprint se informado
        if sprint_id:
            sprint = self.get_sprint(sprint_id)
            if sprint:
                sprint.tickets.append(ticket.id)
                sprint.velocity += story_points

        # Vincular ao epic
        if epic_id:
            epic = self.get_epic(epic_id)
            if epic:
                epic.tickets.append(ticket.id)

        # Subtask
        if parent_id and parent_id in self.tickets:
            self.tickets[parent_id].subtasks.append(ticket.id)

        self._save()
        self._publish("task_start", reporter, assignee or "backlog",
                       f"Ticket criado: {key} — {title}",
                       {"ticket_id": ticket.id, "key": key, "assignee": assignee})
        return ticket

    def get_ticket(self, ticket_id: str) -> Optional[JiraTicket]:
        return self.tickets.get(ticket_id)

    def get_ticket_by_key(self, key: str) -> Optional[JiraTicket]:
        return next((t for t in self.tickets.values() if t.key == key), None)

    def update_ticket_status(self, ticket_id: str, new_status: TicketStatus,
                             agent: str = "system") -> Optional[JiraTicket]:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return None
        old_status = ticket.status
        ticket.status = new_status
        ticket.updated_at = datetime.now()
        if new_status == TicketStatus.DONE:
            ticket.resolved_at = datetime.now()
            # Atualizar sprint completed_points
            if ticket.sprint_id:
                sprint = self.get_sprint(ticket.sprint_id)
                if sprint:
                    sprint.completed_points += ticket.story_points
        self._save()
        self._publish("task_end", agent, "po_agent",
                       f"{ticket.key} {old_status.value} → {new_status.value}",
                       {"ticket_id": ticket_id, "key": ticket.key,
                        "old_status": old_status.value, "new_status": new_status.value})
        return ticket

    def assign_ticket(self, ticket_id: str, assignee: str) -> Optional[JiraTicket]:
        ticket = self.get_ticket(ticket_id)
        if ticket:
            ticket.assignee = assignee
            ticket.updated_at = datetime.now()
            self._save()
            self._publish("request", "po_agent", assignee,
                           f"Ticket {ticket.key} atribuído a {assignee}",
                           {"ticket_id": ticket_id, "key": ticket.key})
        return ticket

    def list_tickets(
        self, status: TicketStatus = None, assignee: str = None,
        sprint_id: str = None, epic_id: str = None,
        ticket_type: TicketType = None,
        project_key: str = None,
    ) -> List[JiraTicket]:
        result = list(self.tickets.values())
        if status:
            result = [t for t in result if t.status == status]
        if assignee:
            result = [t for t in result if t.assignee == assignee]
        if sprint_id:
            result = [t for t in result if t.sprint_id == sprint_id]
        if epic_id:
            result = [t for t in result if t.epic_id == epic_id]
        if ticket_type:
            result = [t for t in result if t.ticket_type == ticket_type]
        if project_key:
            result = [t for t in result if t.key.startswith(project_key)]
        return result

    def get_agent_tickets(self, agent_name: str) -> Dict[str, List[JiraTicket]]:
        """Retorna tickets de um agente agrupados por status."""
        all_tickets = self.list_tickets(assignee=agent_name)
        grouped: Dict[str, List[JiraTicket]] = {}
        for t in all_tickets:
            grouped.setdefault(t.status.value, []).append(t)
        return grouped

    def search_tickets(self, query: str) -> List[JiraTicket]:
        """Busca textual simples em título e descrição."""
        q = query.lower()
        return [
            t for t in self.tickets.values()
            if q in t.title.lower() or q in t.description.lower() or q in t.key.lower()
        ]

    # ═══════════════════════════ Worklogs ═════════════════════════════════════

    def log_work(
        self, ticket_id: str, agent_name: str, description: str,
        time_spent_minutes: int, auto_logged: bool = False,
        metadata: Dict = None,
    ) -> Optional[JiraWorklog]:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return None
        worklog = JiraWorklog(
            ticket_id=ticket_id, agent_name=agent_name,
            description=description, time_spent_minutes=time_spent_minutes,
            auto_logged=auto_logged, metadata=metadata or {},
        )
        ticket.worklogs.append(worklog)
        ticket.logged_hours += time_spent_minutes / 60.0
        ticket.updated_at = datetime.now()
        self._save()
        self._publish("task_end", agent_name, "po_agent",
                       f"Worklog: {agent_name} +{time_spent_minutes}min em {ticket.key}",
                       {"ticket_id": ticket_id, "key": ticket.key,
                        "minutes": time_spent_minutes, "auto": auto_logged})
        return worklog

    def get_worklogs(self, ticket_id: str = None, agent_name: str = None,
                     since: datetime = None) -> List[JiraWorklog]:
        """Lista worklogs com filtros opcionais."""
        result: List[JiraWorklog] = []
        for t in self.tickets.values():
            for w in t.worklogs:
                if ticket_id and w.ticket_id != ticket_id:
                    continue
                if agent_name and w.agent_name != agent_name:
                    continue
                if since and w.started_at < since:
                    continue
                result.append(w)
        return result

    # ═══════════════════════════ Comments ═════════════════════════════════════

    def add_comment(self, ticket_id: str, author: str, body: str) -> Optional[JiraComment]:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return None
        comment = JiraComment(author=author, body=body)
        ticket.comments.append(comment)
        ticket.updated_at = datetime.now()
        self._save()
        return comment

    # ═══════════════════════════ Métricas ═════════════════════════════════════

    def get_board_metrics(self) -> Dict[str, Any]:
        """KPIs do board."""
        total = len(self.tickets)
        by_status = {}
        by_agent = {}
        total_logged = 0.0
        for t in self.tickets.values():
            by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
            if t.assignee:
                by_agent.setdefault(t.assignee, {"total": 0, "done": 0, "points": 0, "hours": 0})
                by_agent[t.assignee]["total"] += 1
                by_agent[t.assignee]["hours"] += t.logged_hours
                if t.status == TicketStatus.DONE:
                    by_agent[t.assignee]["done"] += 1
                    by_agent[t.assignee]["points"] += t.story_points
            total_logged += t.logged_hours

        active_sprint = self.get_active_sprint()
        sprint_info = active_sprint.to_dict() if active_sprint else None

        return {
            "project": self.project.name,
            "total_tickets": total,
            "by_status": by_status,
            "by_agent": by_agent,
            "total_logged_hours": round(total_logged, 1),
            "epics_count": len(self.project.epics),
            "sprints_count": len(self.project.sprints),
            "active_sprint": sprint_info,
            "team_size": len(self.project.team_members),
        }

    # ═══════════════════════════ Utilidades ═══════════════════════════════════

    def add_team_member(self, agent_name: str):
        if agent_name not in self.project.team_members:
            self.project.team_members.append(agent_name)
            self._save()

    def remove_team_member(self, agent_name: str):
        if agent_name in self.project.team_members:
            self.project.team_members.remove(agent_name)
            self._save()

    def reset(self):
        """Reset completo (para testes)."""
        self.project = JiraProject()
        self.tickets = {}
        self._bootstrap_project()
        self._save()
