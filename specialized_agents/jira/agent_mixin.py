"""
Jira Agent Mixin — Integração dos agentes especializados com o Jira RPA4ALL.

Qualquer agente que herde este mixin ganha capacidade de:
  • Buscar seus tickets atribuídos
  • Mover tickets entre status
  • Registrar apontamento de horas (automático ou manual)
  • Adicionar comentários de progresso
  • Consultar próximo ticket a trabalhar
"""
from datetime import datetime
from typing import Dict, List, Any, Optional

from .models import TicketStatus, JiraTicket, JiraWorklog
from .jira_board import get_jira_board, JiraBoard

# Bus de comunicação
try:
    from specialized_agents.agent_communication_bus import log_task_start, log_task_end
    BUS_OK = True
except ImportError:
    BUS_OK = False


class JiraAgentMixin:
    """
    Mixin para integração de qualquer SpecializedAgent com o Jira RPA4ALL.
    Espera que a classe host tenha um atributo `language` (str).
    """

    @property
    def _jira_agent_name(self) -> str:
        lang = getattr(self, "language", "unknown")
        return f"{lang}_agent"

    @property
    def _jira_board(self) -> JiraBoard:
        return get_jira_board()

    # ─── Consultar atividades ─────────────────────────────────────────────────

    def jira_my_tickets(self, status: TicketStatus = None) -> List[Dict[str, Any]]:
        """Retorna tickets atribuídos a este agente."""
        if status:
            tickets = self._jira_board.list_tickets(
                assignee=self._jira_agent_name, status=status)
        else:
            tickets = []
            for s in TicketStatus:
                tickets.extend(self._jira_board.list_tickets(
                    assignee=self._jira_agent_name, status=s))
        return [t.to_dict() for t in tickets]

    def jira_my_current_work(self) -> List[Dict[str, Any]]:
        """Tickets atualmente IN_PROGRESS para este agente."""
        return self.jira_my_tickets(TicketStatus.IN_PROGRESS)

    def jira_my_todo(self) -> List[Dict[str, Any]]:
        """Tickets TODO para este agente (próximos a pegar)."""
        return self.jira_my_tickets(TicketStatus.TODO)

    def jira_my_backlog(self) -> List[Dict[str, Any]]:
        """Tickets no backlog para este agente."""
        return self.jira_my_tickets(TicketStatus.BACKLOG)

    def jira_next_ticket(self) -> Optional[Dict[str, Any]]:
        """Retorna o próximo ticket a ser trabalhado (maior prioridade TODO)."""
        tickets = self._jira_board.list_tickets(
            assignee=self._jira_agent_name, status=TicketStatus.TODO)
        if not tickets:
            tickets = self._jira_board.list_tickets(
                assignee=self._jira_agent_name, status=TicketStatus.BACKLOG)
        if not tickets:
            return None
        # Ordenar por prioridade
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "trivial": 4}
        tickets.sort(key=lambda t: priority_order.get(t.priority.value, 5))
        return tickets[0].to_dict()

    # ─── Transições de status ─────────────────────────────────────────────────

    def jira_start_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """Move ticket para IN_PROGRESS e registra início."""
        ticket = self._jira_board.update_ticket_status(
            ticket_id, TicketStatus.IN_PROGRESS, self._jira_agent_name)
        if ticket and BUS_OK:
            log_task_start(self._jira_agent_name, ticket.key, ticket.title)
        return ticket.to_dict() if ticket else None

    def jira_submit_for_review(self, ticket_id: str, comment: str = "") -> Optional[Dict[str, Any]]:
        """Move ticket para IN_REVIEW (aguardando aceite do PO)."""
        ticket = self._jira_board.update_ticket_status(
            ticket_id, TicketStatus.IN_REVIEW, self._jira_agent_name)
        if ticket:
            if comment:
                self._jira_board.add_comment(ticket_id, self._jira_agent_name, comment)
            if BUS_OK:
                log_task_end(self._jira_agent_name, ticket.key, "in_review")
        return ticket.to_dict() if ticket else None

    def jira_complete_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """Move ticket direto para DONE."""
        ticket = self._jira_board.update_ticket_status(
            ticket_id, TicketStatus.DONE, self._jira_agent_name)
        if ticket and BUS_OK:
            log_task_end(self._jira_agent_name, ticket.key, "done")
        return ticket.to_dict() if ticket else None

    # ─── Apontamento de horas ─────────────────────────────────────────────────

    def jira_log_work(
        self, ticket_id: str, description: str,
        time_spent_minutes: int, auto: bool = False,
        metadata: Dict = None,
    ) -> Optional[Dict[str, Any]]:
        """Registra apontamento de horas em um ticket."""
        worklog = self._jira_board.log_work(
            ticket_id=ticket_id,
            agent_name=self._jira_agent_name,
            description=description,
            time_spent_minutes=time_spent_minutes,
            auto_logged=auto,
            metadata=metadata or {},
        )
        return worklog.to_dict() if worklog else None

    def jira_auto_log(self, ticket_id: str, task_description: str,
                      start_time: datetime, end_time: datetime = None) -> Optional[Dict[str, Any]]:
        """Auto-log de trabalho (cálculo automático de duração)."""
        end = end_time or datetime.now()
        minutes = max(1, int((end - start_time).total_seconds() / 60))
        return self.jira_log_work(
            ticket_id=ticket_id,
            description=f"[AUTO] {task_description}",
            time_spent_minutes=minutes,
            auto=True,
            metadata={"start": start_time.isoformat(), "end": end.isoformat()},
        )

    # ─── Comentários ──────────────────────────────────────────────────────────

    def jira_add_comment(self, ticket_id: str, body: str) -> bool:
        """Adiciona comentário em um ticket."""
        comment = self._jira_board.add_comment(ticket_id, self._jira_agent_name, body)
        return comment is not None

    # ─── Resumo do agente ─────────────────────────────────────────────────────

    def jira_agent_summary(self) -> Dict[str, Any]:
        """Resumo de atividade do agente no Jira."""
        all_tickets = self._jira_board.get_agent_tickets(self._jira_agent_name)
        total_logged = 0
        total_points_done = 0
        for status, tickets in all_tickets.items():
            for t in tickets:
                total_logged += t.logged_hours
                if t.status == TicketStatus.DONE:
                    total_points_done += t.story_points

        return {
            "agent": self._jira_agent_name,
            "tickets_by_status": {s: len(tl) for s, tl in all_tickets.items()},
            "total_tickets": sum(len(tl) for tl in all_tickets.values()),
            "total_logged_hours": round(total_logged, 1),
            "total_points_completed": total_points_done,
            "current_work": self.jira_my_current_work(),
            "next_up": self.jira_my_todo()[:3],
        }
