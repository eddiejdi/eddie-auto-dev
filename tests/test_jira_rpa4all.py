"""\nTestes do Jira RPA4ALL — Board, Tickets, Sprints, PO Agent e Mixin.\n"""
import pytest
import asyncio
from datetime import datetime, timedelta

pytestmark = pytest.mark.asyncio(loop_scope="function")

from specialized_agents.jira.models import (
    JiraProject, JiraEpic, JiraSprint, JiraTicket, JiraWorklog,
    TicketStatus, TicketPriority, TicketType, SprintStatus,
)
from specialized_agents.jira.jira_board import JiraBoard
from specialized_agents.jira.po_agent import ProductOwnerAgent
from specialized_agents.jira.agent_mixin import JiraAgentMixin


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def board():
    b = JiraBoard()
    b.reset()
    return b


@pytest.fixture
def po(board):
    return ProductOwnerAgent(board=board)


# ─── Modelos ──────────────────────────────────────────────────────────────────

class TestModels:
    def test_ticket_defaults(self):
        t = JiraTicket(title="Test")
        assert t.status == TicketStatus.BACKLOG
        assert t.priority == TicketPriority.MEDIUM
        assert t.ticket_type == TicketType.TASK

    def test_ticket_to_dict(self):
        t = JiraTicket(key="RPA-001", title="Algo")
        d = t.to_dict()
        assert d["key"] == "RPA-001"
        assert "status" in d

    def test_sprint_progress(self):
        s = JiraSprint(velocity=10, completed_points=5)
        assert s.progress_pct == 50.0

    def test_project_next_key(self):
        p = JiraProject(key="RPA")
        k1 = p.next_ticket_key()
        k2 = p.next_ticket_key()
        assert k1 == "RPA-001"
        assert k2 == "RPA-002"


# ─── JiraBoard ────────────────────────────────────────────────────────────────

class TestJiraBoard:
    def test_create_ticket(self, board):
        t = board.create_ticket("Implementar login", assignee="python_agent",
                                story_points=5)
        assert t.key.startswith("RPA-")
        assert t.assignee == "python_agent"
        assert t.story_points == 5

    def test_create_and_get(self, board):
        t = board.create_ticket("Task X")
        fetched = board.get_ticket(t.id)
        assert fetched is not None
        assert fetched.title == "Task X"

    def test_get_by_key(self, board):
        t = board.create_ticket("Task Y")
        fetched = board.get_ticket_by_key(t.key)
        assert fetched.id == t.id

    def test_update_status(self, board):
        t = board.create_ticket("Task Z")
        updated = board.update_ticket_status(t.id, TicketStatus.IN_PROGRESS, "python_agent")
        assert updated.status == TicketStatus.IN_PROGRESS

    def test_complete_ticket(self, board):
        t = board.create_ticket("Task Done", story_points=3)
        board.update_ticket_status(t.id, TicketStatus.DONE, "go_agent")
        assert board.get_ticket(t.id).resolved_at is not None

    def test_assign_ticket(self, board):
        t = board.create_ticket("Assign me")
        board.assign_ticket(t.id, "rust_agent")
        assert board.get_ticket(t.id).assignee == "rust_agent"

    def test_list_tickets_filter(self, board):
        board.create_ticket("A", assignee="python_agent")
        board.create_ticket("B", assignee="go_agent")
        board.create_ticket("C", assignee="python_agent")
        py = board.list_tickets(assignee="python_agent")
        assert len(py) == 2

    def test_search_tickets(self, board):
        board.create_ticket("Implementar API REST")
        board.create_ticket("Corrigir bug no login")
        found = board.search_tickets("api")
        assert len(found) == 1

    def test_log_work(self, board):
        t = board.create_ticket("Work on it")
        wl = board.log_work(t.id, "python_agent", "Coding", 60)
        assert wl is not None
        assert board.get_ticket(t.id).logged_hours == 1.0

    def test_add_comment(self, board):
        t = board.create_ticket("Comment me")
        c = board.add_comment(t.id, "go_agent", "Progresso: 50%")
        assert c is not None
        assert len(board.get_ticket(t.id).comments) == 1

    def test_create_epic(self, board):
        epic = board.create_epic("MVP", "Primeira versão")
        assert epic.key.startswith("RPA-")
        assert len(board.list_epics()) == 1

    def test_create_sprint(self, board):
        sprint = board.create_sprint("Sprint 1", "Entregar MVP", 14)
        assert sprint.name == "Sprint 1"
        assert sprint.status == SprintStatus.PLANNING

    def test_start_complete_sprint(self, board):
        sprint = board.create_sprint("Sprint 2")
        board.start_sprint(sprint.id)
        assert board.get_sprint(sprint.id).status == SprintStatus.ACTIVE
        board.complete_sprint(sprint.id)
        assert board.get_sprint(sprint.id).status == SprintStatus.COMPLETED

    def test_agent_tickets(self, board):
        board.create_ticket("A", assignee="java_agent")
        t2 = board.create_ticket("B", assignee="java_agent")
        board.update_ticket_status(t2.id, TicketStatus.IN_PROGRESS, "java_agent")
        grouped = board.get_agent_tickets("java_agent")
        assert "backlog" in grouped or "in_progress" in grouped

    def test_metrics(self, board):
        board.create_ticket("M1", assignee="python_agent", story_points=3)
        m = board.get_board_metrics()
        assert m["total_tickets"] == 1
        assert m["project"] == "RPA4ALL"

    def test_team_management(self, board):
        board.add_team_member("new_agent")
        assert "new_agent" in board.project.team_members
        board.remove_team_member("new_agent")
        assert "new_agent" not in board.project.team_members


# ─── PO Agent ─────────────────────────────────────────────────────────────────

class TestPOAgent:
    @pytest.mark.asyncio
    async def test_create_epic_with_stories(self, po):
        result = await po.create_epic_with_stories(
            "Autenticação",
            "Sistema de auth completo",
            stories=[
                {"title": "Login API", "labels": ["python", "api"], "points": 5},
                {"title": "Frontend login", "labels": ["typescript", "nextjs"], "points": 3},
            ],
        )
        assert "epic" in result
        assert len(result["stories"]) == 2
        # Verificar auto-atribuição por skills
        assignees = {s["assignee"] for s in result["stories"]}
        assert len(assignees) >= 1  # Pelo menos um agente atribuído

    @pytest.mark.asyncio
    async def test_plan_sprint_auto(self, po):
        # Criar tickets no backlog
        for i in range(5):
            po.board.create_ticket(f"Task {i}", story_points=3,
                                   priority=TicketPriority.HIGH)
        result = await po.plan_sprint("Sprint Auto", "Testar auto-seleção",
                                       auto_select=True)
        assert "sprint" in result
        assert len(result["tickets"]) > 0

    @pytest.mark.asyncio
    async def test_distribute_tickets(self, po):
        po.board.create_ticket("Python task", labels=["python", "api"])
        po.board.create_ticket("Go task", labels=["go", "microservice"])
        assignments = await po.distribute_tickets()
        assert len(assignments) >= 1

    @pytest.mark.asyncio
    async def test_review_accept(self, po):
        t = po.board.create_ticket("Review me", assignee="python_agent")
        po.board.update_ticket_status(t.id, TicketStatus.IN_REVIEW, "python_agent")
        result = await po.review_delivery(t.id, accept=True, feedback="OK")
        assert result["status"] == "accepted"
        assert po.board.get_ticket(t.id).status == TicketStatus.DONE

    @pytest.mark.asyncio
    async def test_review_reject(self, po):
        t = po.board.create_ticket("Reject me", assignee="go_agent")
        po.board.update_ticket_status(t.id, TicketStatus.IN_REVIEW, "go_agent")
        result = await po.review_delivery(t.id, accept=False, feedback="Faltou testes")
        assert result["status"] == "rejected"
        assert po.board.get_ticket(t.id).status == TicketStatus.TODO

    @pytest.mark.asyncio
    async def test_daily_standup(self, po):
        po.board.create_ticket("Standup Task", assignee="python_agent")
        report = await po.daily_standup_report()
        assert "agents" in report
        assert "date" in report

    @pytest.mark.asyncio
    async def test_sprint_report(self, po):
        sprint = po.board.create_sprint("Report Sprint")
        po.board.start_sprint(sprint.id)
        t = po.board.create_ticket("Sprint task", sprint_id=sprint.id,
                                    story_points=5, assignee="python_agent")
        po.board.update_ticket_status(t.id, TicketStatus.DONE, "python_agent")
        report = await po.sprint_report(sprint.id)
        assert report["completed"] == 1

    def test_po_status(self, po):
        status = po.get_status()
        assert status["role"] == "Product Owner"
        assert status["project"] == "RPA4ALL"

    def test_best_agent_for(self, po):
        agent = po._best_agent_for(["python", "fastapi"])
        assert agent == "python_agent"
        agent = po._best_agent_for(["go", "grpc"])
        assert agent == "go_agent"


# ─── JiraAgentMixin ───────────────────────────────────────────────────────────

class FakeAgent(JiraAgentMixin):
    """Agente fake para testar o mixin."""
    def __init__(self, language: str, board: JiraBoard = None):
        self.language = language
        self._board_override = board

    @property
    def _jira_board(self):
        if self._board_override:
            return self._board_override
        return get_jira_board()


class TestMixin:
    def setup_method(self):
        self.board = JiraBoard()
        self.board.reset()
        self.agent = FakeAgent("python", board=self.board)

    def test_my_tickets(self):
        self.board.create_ticket("Mixin test", assignee="python_agent")
        tickets = self.agent.jira_my_tickets()
        assert len(tickets) >= 1

    def test_start_and_log(self):
        t = self.board.create_ticket("Start me", assignee="python_agent")
        started = self.agent.jira_start_ticket(t.id)
        assert started["status"] == "in_progress"

        wl = self.agent.jira_log_work(t.id, "Coding API", 45)
        assert wl is not None
        assert wl["time_spent_minutes"] == 45

    def test_submit_for_review(self):
        t = self.board.create_ticket("Submit me", assignee="python_agent")
        self.board.update_ticket_status(t.id, TicketStatus.IN_PROGRESS, "python_agent")
        result = self.agent.jira_submit_for_review(t.id, "Pronto para review")
        assert result["status"] == "in_review"

    def test_next_ticket(self):
        t1 = self.board.create_ticket("Low prio", assignee="python_agent",
                                priority=TicketPriority.LOW)
        t2 = self.board.create_ticket("High prio", assignee="python_agent",
                                priority=TicketPriority.HIGH)
        # Mover ambos para TODO para que next_ticket funcione
        self.board.update_ticket_status(t1.id, TicketStatus.TODO, "system")
        self.board.update_ticket_status(t2.id, TicketStatus.TODO, "system")
        nxt = self.agent.jira_next_ticket()
        assert nxt is not None
        assert nxt["priority"] == "high"

    def test_auto_log(self):
        t = self.board.create_ticket("Auto log", assignee="python_agent")
        self.board.update_ticket_status(t.id, TicketStatus.IN_PROGRESS, "python_agent")
        start = datetime.now() - timedelta(minutes=30)
        wl = self.agent.jira_auto_log(t.id, "Implementação automática", start)
        assert wl is not None
        assert wl["time_spent_minutes"] >= 29

    def test_agent_summary(self):
        self.board.create_ticket("Summary t", assignee="python_agent",
                                story_points=5)
        summary = self.agent.jira_agent_summary()
        assert summary["agent"] == "python_agent"
        assert summary["total_tickets"] >= 1
