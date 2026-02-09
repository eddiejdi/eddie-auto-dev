"""
Product Owner Agent — Agente PO para o Jira RPA4ALL.
Responsável por:
  • Criar e priorizar Epics, Stories e Tasks
  • Planejar Sprints e distribuir trabalho entre agentes
  • Acompanhar progresso e gerar relatórios de status
  • Aceitar ou rejeitar entregas (Definition of Done)
  • Comunicar-se via Communication Bus com todos os agentes
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from .models import (
    JiraTicket, JiraEpic, JiraSprint, JiraWorklog,
    TicketStatus, TicketPriority, TicketType, SprintStatus,
)
from .jira_board import JiraBoard, get_jira_board

# Bus de comunicação
try:
    from specialized_agents.agent_communication_bus import (
        get_communication_bus, MessageType,
        log_request, log_response, log_coordinator, log_analysis,
    )
    BUS_AVAILABLE = True
except ImportError:
    BUS_AVAILABLE = False

# LLM para decisões inteligentes do PO
try:
    from specialized_agents.base_agent import LLMClient
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False


# ─── Mapeamento de agentes por skill ─────────────────────────────────────────

AGENT_SKILLS: Dict[str, List[str]] = {
    "python_agent": [
        "python", "fastapi", "django", "flask", "data-science",
        "machine-learning", "automation", "selenium", "streamlit", "async",
    ],
    "javascript_agent": [
        "javascript", "node", "express", "react", "vue",
        "graphql", "socket.io", "jest", "frontend",
    ],
    "typescript_agent": [
        "typescript", "nextjs", "nestjs", "angular", "type-safe",
        "graphql", "monorepo",
    ],
    "go_agent": [
        "go", "golang", "microservice", "grpc", "cli",
        "performance", "concurrency", "kubernetes",
    ],
    "rust_agent": [
        "rust", "systems", "wasm", "performance", "safety",
        "embedded", "cli",
    ],
    "java_agent": [
        "java", "spring", "spring-boot", "maven", "gradle",
        "enterprise", "microservice", "kafka",
    ],
    "csharp_agent": [
        "csharp", "dotnet", ".net", "asp.net", "blazor",
        "azure", "enterprise", "wpf",
    ],
    "php_agent": [
        "php", "laravel", "symfony", "wordpress", "api",
        "web", "cms",
    ],
}

PO_SYSTEM_PROMPT = """Você é o Product Owner (PO) do projeto RPA4ALL.
Sua função:
1. Priorizar o backlog com base em valor de negócio e urgência.
2. Criar tickets claros com critérios de aceitação.
3. Atribuir tickets ao agente mais adequado por skills.
4. Planejar sprints de 2 semanas com velocity sustentável.
5. Aceitar ou rejeitar entregas com feedback construtivo.
6. Manter stakeholders informados via relatórios de status.

Regras:
- Sempre inclua "Critérios de Aceitação" na descrição dos tickets.
- Story points usam Fibonacci modificado: 1, 2, 3, 5, 8, 13.
- Priorize bugs CRITICAL acima de tudo.
- Mantenha WIP (work in progress) máximo de 3 tickets por agente.
- Responda sempre em JSON quando solicitado.
"""


class ProductOwnerAgent:
    """
    Agente PO — gerencia backlog, sprints e comunicação com os agentes.
    """

    def __init__(self, board: JiraBoard = None):
        self.board = board or get_jira_board()
        self.llm = LLMClient() if LLM_AVAILABLE else None
        self.name = "po_agent"

    # ═══════════════════════════ Inteligência ═════════════════════════════════

    async def _ask_llm(self, prompt: str) -> str:
        """Consulta LLM para decisões inteligentes."""
        if not self.llm:
            return ""
        try:
            return await self.llm.generate(prompt, system=PO_SYSTEM_PROMPT)
        except Exception as e:
            return f"[PO LLM Error] {e}"

    def _best_agent_for(self, labels: List[str]) -> str:
        """Determina o melhor agente para um conjunto de labels/skills."""
        scores: Dict[str, int] = {}
        for agent, skills in AGENT_SKILLS.items():
            score = sum(1 for lbl in labels if lbl.lower() in skills)
            # Penalizar agentes com muito WIP
            wip = len(self.board.list_tickets(
                assignee=agent, status=TicketStatus.IN_PROGRESS))
            score -= wip
            scores[agent] = score
        if not scores:
            return "python_agent"  # fallback
        return max(scores, key=scores.get)

    # ═══════════════════════════ Criação de trabalho ══════════════════════════

    async def create_epic_with_stories(
        self, epic_title: str, epic_description: str,
        stories: List[Dict[str, Any]],
        target_date: datetime = None,
    ) -> Dict[str, Any]:
        """
        Cria um Epic e suas Stories vinculadas.

        stories: [{"title": "...", "description": "...", "labels": [...], "points": 3}, ...]
        """
        epic = self.board.create_epic(epic_title, epic_description,
                                        owner=self.name, target_date=target_date)
        created_tickets = []
        for s in stories:
            labels = s.get("labels", [])
            assignee = s.get("assignee") or self._best_agent_for(labels)
            ticket = self.board.create_ticket(
                title=s["title"],
                description=s.get("description", ""),
                ticket_type=TicketType.STORY,
                priority=TicketPriority(s.get("priority", "medium")),
                assignee=assignee,
                reporter=self.name,
                epic_id=epic.id,
                story_points=s.get("points", 3),
                estimated_hours=s.get("estimated_hours", 0),
                labels=labels,
                due_date=target_date,
            )
            created_tickets.append(ticket)

        if BUS_AVAILABLE:
            log_coordinator(
                f"PO criou Epic {epic.key} com {len(created_tickets)} stories",
                epic_id=epic.id,
            )

        return {
            "epic": epic.to_dict(),
            "stories": [t.to_dict() for t in created_tickets],
        }

    async def plan_sprint(
        self, name: str, goal: str, ticket_ids: List[str] = None,
        duration_days: int = 14, auto_select: bool = True,
    ) -> Dict[str, Any]:
        """
        Planeja e cria um Sprint.
        Se auto_select=True, seleciona tickets do backlog automaticamente.
        """
        sprint = self.board.create_sprint(name, goal, duration_days)

        if auto_select and not ticket_ids:
            # Pegar tickets priorizados do backlog (até 30 story points)
            backlog = self.board.list_tickets(status=TicketStatus.BACKLOG)
            backlog.sort(key=lambda t: (
                {"critical": 0, "high": 1, "medium": 2, "low": 3, "trivial": 4}
                .get(t.priority.value, 5),
                -t.story_points,
            ))
            total_pts = 0
            selected = []
            for t in backlog:
                if total_pts + t.story_points <= 30:
                    selected.append(t.id)
                    total_pts += t.story_points
            ticket_ids = selected

        # Mover tickets para o sprint
        moved = []
        for tid in (ticket_ids or []):
            ticket = self.board.get_ticket(tid)
            if ticket:
                ticket.sprint_id = sprint.id
                ticket.status = TicketStatus.TODO
                ticket.updated_at = datetime.now()
                sprint.tickets.append(tid)
                sprint.velocity += ticket.story_points
                moved.append(ticket)

        self.board._save()

        if BUS_AVAILABLE:
            log_coordinator(
                f"Sprint '{name}' planejado: {len(moved)} tickets, "
                f"{sprint.velocity} pts, {duration_days}d",
                sprint_id=sprint.id,
            )

        return {
            "sprint": sprint.to_dict(),
            "tickets": [t.to_dict() for t in moved],
        }

    # ═══════════════════════════ Distribuição de trabalho ═════════════════════

    async def distribute_tickets(self, sprint_id: str = None) -> Dict[str, List[Dict]]:
        """
        Distribui tickets não-atribuídos entre os agentes por skills.
        """
        sprint = None
        if sprint_id:
            sprint = self.board.get_sprint(sprint_id)
        else:
            sprint = self.board.get_active_sprint()

        if not sprint:
            # Distribui no backlog geral
            unassigned = [t for t in self.board.tickets.values()
                          if not t.assignee and t.status in
                          (TicketStatus.BACKLOG, TicketStatus.TODO)]
        else:
            unassigned = [t for t in self.board.tickets.values()
                          if t.sprint_id == sprint.id and not t.assignee]

        assignments: Dict[str, List[Dict]] = {}
        for t in unassigned:
            agent = self._best_agent_for(t.labels)
            self.board.assign_ticket(t.id, agent)
            assignments.setdefault(agent, []).append(t.to_dict())

        if BUS_AVAILABLE and assignments:
            for agent, tickets in assignments.items():
                log_request(
                    self.name, agent,
                    f"Novos tickets atribuídos: {[t['key'] for t in tickets]}",
                    ticket_count=len(tickets),
                )

        return assignments

    # ═══════════════════════════ Aceite / Rejeição ═══════════════════════════

    async def review_delivery(self, ticket_id: str, accept: bool,
                              feedback: str = "") -> Dict[str, Any]:
        """
        Revisa entrega de um ticket. Aceita (DONE) ou rejeita (TODO + comentário).
        """
        ticket = self.board.get_ticket(ticket_id)
        if not ticket:
            return {"error": "Ticket não encontrado"}

        if accept:
            self.board.update_ticket_status(ticket_id, TicketStatus.DONE, self.name)
            self.board.add_comment(ticket_id, self.name,
                                    f"✅ Entrega ACEITA. {feedback}")
            if BUS_AVAILABLE:
                log_response(self.name, ticket.assignee,
                              f"Ticket {ticket.key} ACEITO — {feedback}",
                              ticket_id=ticket_id)
            return {"status": "accepted", "ticket": ticket.to_dict()}
        else:
            self.board.update_ticket_status(ticket_id, TicketStatus.TODO, self.name)
            self.board.add_comment(ticket_id, self.name,
                                    f"❌ Entrega REJEITADA. Motivo: {feedback}")
            if BUS_AVAILABLE:
                log_response(self.name, ticket.assignee,
                              f"Ticket {ticket.key} REJEITADO — {feedback}",
                              ticket_id=ticket_id)
            return {"status": "rejected", "ticket": ticket.to_dict(), "reason": feedback}

    # ═══════════════════════════ Relatórios ═══════════════════════════════════

    async def daily_standup_report(self) -> Dict[str, Any]:
        """
        Gera relatório de stand-up diário para todos os agentes.
        """
        sprint = self.board.get_active_sprint()
        report = {
            "date": datetime.now().isoformat(),
            "sprint": sprint.to_dict() if sprint else None,
            "agents": {},
        }
        for agent in self.board.project.team_members:
            if agent == self.name:
                continue
            tickets = self.board.get_agent_tickets(agent)
            in_progress = tickets.get("in_progress", [])
            done_today = [
                t for t in tickets.get("done", [])
                if t.resolved_at and t.resolved_at.date() == datetime.now().date()
            ]
            todo = tickets.get("todo", [])
            report["agents"][agent] = {
                "in_progress": [t.to_dict() for t in in_progress],
                "done_today": [t.to_dict() for t in done_today],
                "next_up": [t.to_dict() for t in todo[:2]],
                "total_logged_today": sum(
                    w.time_spent_minutes for t_list in tickets.values()
                    for t in t_list for w in t.worklogs
                    if w.started_at.date() == datetime.now().date()
                ),
            }

        if BUS_AVAILABLE:
            log_coordinator(
                f"📊 Daily Standup — {len(report['agents'])} agentes reportaram",
                report_type="daily_standup",
            )

        return report

    async def sprint_report(self, sprint_id: str = None) -> Dict[str, Any]:
        """Relatório detalhado de um sprint."""
        sprint = self.board.get_sprint(sprint_id) if sprint_id else self.board.get_active_sprint()
        if not sprint:
            return {"error": "Nenhum sprint ativo"}

        tickets = self.board.list_tickets(sprint_id=sprint.id)
        done = [t for t in tickets if t.status == TicketStatus.DONE]
        total_hours = sum(t.logged_hours for t in tickets)

        return {
            "sprint": sprint.to_dict(),
            "total_tickets": len(tickets),
            "completed": len(done),
            "remaining": len(tickets) - len(done),
            "completed_points": sprint.completed_points,
            "planned_points": sprint.velocity,
            "progress_pct": sprint.progress_pct,
            "total_logged_hours": round(total_hours, 1),
            "by_status": {
                s.value: len([t for t in tickets if t.status == s])
                for s in TicketStatus
            },
            "burndown": self._calculate_burndown(sprint, tickets),
        }

    def _calculate_burndown(self, sprint: JiraSprint,
                            tickets: List[JiraTicket]) -> List[Dict]:
        """Calcula dados de burndown chart."""
        if not sprint.start_date or not sprint.end_date:
            return []
        burndown = []
        current = sprint.start_date
        remaining = sprint.velocity
        while current <= min(sprint.end_date, datetime.now()):
            done_by_day = sum(
                t.story_points for t in tickets
                if t.status == TicketStatus.DONE and t.resolved_at
                and t.resolved_at.date() <= current.date()
            )
            burndown.append({
                "date": current.strftime("%Y-%m-%d"),
                "remaining": remaining - done_by_day,
                "ideal": max(0, remaining - (remaining / max(1, (sprint.end_date - sprint.start_date).days)) * (current - sprint.start_date).days),
            })
            current += timedelta(days=1)
        return burndown

    # ═══════════════════════════ Backlog intelligence ═════════════════════════

    async def auto_create_tasks_from_description(
        self, project_description: str
    ) -> Dict[str, Any]:
        """
        Usa LLM para quebrar uma descrição de projeto em Epic + Stories.
        """
        if not self.llm:
            return {"error": "LLM não disponível"}

        prompt = f"""Analise este projeto e crie um Epic com Stories detalhadas.
Retorne SOMENTE JSON no formato:
{{
  "epic_title": "...",
  "epic_description": "...",
  "stories": [
    {{
      "title": "...",
      "description": "Critérios de Aceitação:\\n- ...",
      "labels": ["python", "api"],
      "priority": "high",
      "points": 5
    }}
  ]
}}

Projeto: {project_description}
"""
        response = await self._ask_llm(prompt)
        try:
            # Tentar parsear JSON da resposta
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                result = await self.create_epic_with_stories(
                    epic_title=data["epic_title"],
                    epic_description=data.get("epic_description", ""),
                    stories=data.get("stories", []),
                )
                return result
        except (json.JSONDecodeError, KeyError) as e:
            return {"error": f"Falha ao parsear resposta do LLM: {e}", "raw": response}

        return {"error": "LLM não retornou JSON válido", "raw": response}

    # ═══════════════════════════ Notificações ═════════════════════════════════

    async def notify_agent(self, agent_name: str, message: str):
        """Envia notificação para um agente via bus."""
        if BUS_AVAILABLE:
            log_request(self.name, agent_name, message, notification=True)

    async def broadcast(self, message: str):
        """Broadcast para todos os agentes."""
        if BUS_AVAILABLE:
            log_coordinator(f"[PO Broadcast] {message}")

    # ═══════════════════════════ Status geral ═════════════════════════════════

    def get_status(self) -> Dict[str, Any]:
        """Retorna status geral do PO e do board."""
        metrics = self.board.get_board_metrics()
        return {
            "agent": self.name,
            "role": "Product Owner",
            "project": self.board.project.name,
            "board_metrics": metrics,
            "team": self.board.project.team_members,
        }
