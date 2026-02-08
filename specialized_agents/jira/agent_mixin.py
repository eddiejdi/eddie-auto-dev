"""
Jira Agent Mixin — Integração dos agentes especializados com o Jira RPA4ALL.

Qualquer agente que herde este mixin ganha capacidade de:
  • Buscar seus tickets atribuídos (local + Jira Cloud)
  • Mover tickets entre status (sincronizado com Jira Cloud)
  • Registrar apontamento de horas (automático ou manual, com sync Cloud)
  • Adicionar comentários de progresso
  • Consultar próximo ticket a trabalhar
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from .models import TicketStatus, JiraTicket, JiraWorklog
from .jira_board import get_jira_board, JiraBoard

logger = logging.getLogger(__name__)

# Bus de comunicação
try:
    from specialized_agents.agent_communication_bus import log_task_start, log_task_end
    BUS_OK = True
except ImportError:
    BUS_OK = False

# Jira Cloud client (operações reais no Atlassian)
try:
    from .atlassian_client import get_jira_cloud_client
    CLOUD_AVAILABLE = True
except ImportError:
    CLOUD_AVAILABLE = False

# Mapeamento status local → status Jira Cloud
_LOCAL_TO_CLOUD_STATUS = {
    TicketStatus.TODO: "Tarefas pendentes",
    TicketStatus.BACKLOG: "Tarefas pendentes",
    TicketStatus.IN_PROGRESS: "Em andamento",
    TicketStatus.IN_REVIEW: "Em andamento",   # Jira Cloud pode não ter "In Review"
    TicketStatus.TESTING: "Em andamento",
    TicketStatus.DONE: "Concluído",
    TicketStatus.CANCELLED: "Concluído",
}


def _run_async(coro):
    """Executa coroutine de forma síncrona (para métodos sync do mixin)."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        # Já estamos em contexto async — agendar como task
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result(timeout=30)
    else:
        return asyncio.run(coro)


class JiraAgentMixin:
    """
    Mixin para integração de qualquer SpecializedAgent com o Jira RPA4ALL.
    Espera que a classe host tenha um atributo `language` (str).
    
    Sincroniza automaticamente com o Jira Cloud (rpa4all.atlassian.net)
    quando JIRA_API_TOKEN está configurado.
    """

    @property
    def _jira_agent_name(self) -> str:
        lang = getattr(self, "language", "unknown")
        return f"{lang}_agent"

    @property
    def _jira_board(self) -> JiraBoard:
        return get_jira_board()

    @property
    def _jira_cloud_enabled(self) -> bool:
        """Verifica se o Jira Cloud está disponível e configurado."""
        if not CLOUD_AVAILABLE:
            return False
        try:
            client = get_jira_cloud_client()
            return client.is_configured
        except Exception:
            return False

    def _sync_cloud_transition(self, issue_key: str, target_status: TicketStatus,
                                comment: str = "") -> bool:
        """Sincroniza transição de status com o Jira Cloud."""
        if not self._jira_cloud_enabled or not issue_key:
            return False
        cloud_status = _LOCAL_TO_CLOUD_STATUS.get(target_status)
        if not cloud_status:
            return False
        try:
            client = get_jira_cloud_client()
            result = _run_async(
                client.move_issue_to_status(issue_key, cloud_status, comment or None))
            logger.info("☁️  Jira Cloud: %s → %s (%s)", issue_key, cloud_status,
                        target_status.value)
            return True
        except ValueError as e:
            logger.warning("☁️  Jira Cloud transição não disponível para %s: %s",
                           issue_key, e)
            return False
        except Exception as e:
            logger.error("☁️  Jira Cloud sync falhou para %s: %s", issue_key, e)
            return False

    def _sync_cloud_comment(self, issue_key: str, body: str) -> bool:
        """Adiciona comentário no Jira Cloud."""
        if not self._jira_cloud_enabled or not issue_key:
            return False
        try:
            client = get_jira_cloud_client()
            _run_async(client.add_comment(issue_key, body))
            return True
        except Exception as e:
            logger.error("☁️  Jira Cloud comentário falhou para %s: %s", issue_key, e)
            return False

    def _sync_cloud_worklog(self, issue_key: str, time_spent: str,
                             comment: str = "") -> bool:
        """Adiciona worklog no Jira Cloud."""
        if not self._jira_cloud_enabled or not issue_key:
            return False
        try:
            client = get_jira_cloud_client()
            _run_async(client.add_worklog(issue_key, time_spent, comment))
            logger.info("☁️  Jira Cloud: worklog %s em %s", time_spent, issue_key)
            return True
        except Exception as e:
            logger.error("☁️  Jira Cloud worklog falhou para %s: %s", issue_key, e)
            return False

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

    def jira_my_tickets_cloud(self, project_key: str = "SCRUM") -> List[Dict[str, Any]]:
        """Busca tickets atribuídos a este agente diretamente do Jira Cloud."""
        if not self._jira_cloud_enabled:
            return self.jira_my_tickets()
        try:
            client = get_jira_cloud_client()
            jql = (f'project = {project_key} AND assignee = currentUser() '
                   f'ORDER BY priority DESC, updated DESC')
            result = _run_async(client.search_issues(jql))
            return result.get("issues", [])
        except Exception as e:
            logger.error("☁️  Erro buscando tickets Cloud: %s", e)
            return self.jira_my_tickets()

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

    def jira_next_ticket_cloud(self, project_key: str = "SCRUM") -> Optional[Dict[str, Any]]:
        """Busca próximo ticket do Jira Cloud (prioridade: TODO > Backlog)."""
        if not self._jira_cloud_enabled:
            return self.jira_next_ticket()
        try:
            client = get_jira_cloud_client()
            # Buscar tickets "Tarefas pendentes" do sprint ativo
            jql = (f'project = {project_key} '
                   f'AND status = "Tarefas pendentes" '
                   f'AND sprint in openSprints() '
                   f'ORDER BY priority DESC, created ASC')
            result = _run_async(client.search_issues(jql, max_results=1))
            issues = result.get("issues", [])
            if issues:
                return issues[0]
            return None
        except Exception as e:
            logger.error("☁️  Erro buscando próximo ticket Cloud: %s", e)
            return self.jira_next_ticket()

    # ─── Transições de status ─────────────────────────────────────────────────

    def jira_start_ticket(self, ticket_id: str, cloud_key: str = None) -> Optional[Dict[str, Any]]:
        """
        Move ticket para IN_PROGRESS e registra início.
        
        Args:
            ticket_id: ID local do ticket (board JSON)
            cloud_key: Key do Jira Cloud (ex: 'SCRUM-8'). Se fornecido,
                       sincroniza automaticamente com Jira Cloud.
        """
        ticket = self._jira_board.update_ticket_status(
            ticket_id, TicketStatus.IN_PROGRESS, self._jira_agent_name)
        if ticket:
            key = cloud_key or ticket.key
            if BUS_OK:
                log_task_start(self._jira_agent_name, key, ticket.title)
            # Sync com Jira Cloud
            self._sync_cloud_transition(
                key, TicketStatus.IN_PROGRESS,
                f"🤖 {self._jira_agent_name} iniciou trabalho neste ticket")
        return ticket.to_dict() if ticket else None

    def jira_start_ticket_cloud(self, issue_key: str) -> bool:
        """
        Move um ticket direto no Jira Cloud para 'Em andamento'.
        Use quando o ticket existe apenas no Cloud (sem equivalente local).
        """
        comment = f"🤖 {self._jira_agent_name} iniciou trabalho neste ticket"
        success = self._sync_cloud_transition(
            issue_key, TicketStatus.IN_PROGRESS, comment)
        if success and BUS_OK:
            log_task_start(self._jira_agent_name, issue_key, issue_key)
        return success

    def jira_submit_for_review(self, ticket_id: str, comment: str = "",
                                cloud_key: str = None) -> Optional[Dict[str, Any]]:
        """Move ticket para IN_REVIEW (aguardando aceite do PO)."""
        ticket = self._jira_board.update_ticket_status(
            ticket_id, TicketStatus.IN_REVIEW, self._jira_agent_name)
        if ticket:
            key = cloud_key or ticket.key
            if comment:
                self._jira_board.add_comment(ticket_id, self._jira_agent_name, comment)
            if BUS_OK:
                log_task_end(self._jira_agent_name, key, "in_review")
            # Sync com Jira Cloud (comentário de review)
            review_comment = (
                f"🤖 {self._jira_agent_name} submeteu para revisão"
                + (f": {comment}" if comment else ""))
            self._sync_cloud_comment(key, review_comment)
        return ticket.to_dict() if ticket else None

    def jira_complete_ticket(self, ticket_id: str, cloud_key: str = None) -> Optional[Dict[str, Any]]:
        """Move ticket direto para DONE."""
        ticket = self._jira_board.update_ticket_status(
            ticket_id, TicketStatus.DONE, self._jira_agent_name)
        if ticket:
            key = cloud_key or ticket.key
            if BUS_OK:
                log_task_end(self._jira_agent_name, key, "done")
            # Sync com Jira Cloud
            self._sync_cloud_transition(
                key, TicketStatus.DONE,
                f"🤖 {self._jira_agent_name} concluiu este ticket")
        return ticket.to_dict() if ticket else None

    def jira_complete_ticket_cloud(self, issue_key: str) -> bool:
        """
        Move um ticket direto no Jira Cloud para 'Concluído'.
        Use quando o ticket existe apenas no Cloud.
        """
        comment = f"🤖 {self._jira_agent_name} concluiu este ticket"
        success = self._sync_cloud_transition(issue_key, TicketStatus.DONE, comment)
        if success and BUS_OK:
            log_task_end(self._jira_agent_name, issue_key, "done")
        return success

    # ─── Apontamento de horas ─────────────────────────────────────────────────

    def jira_log_work(
        self, ticket_id: str, description: str,
        time_spent_minutes: int, auto: bool = False,
        metadata: Dict = None, cloud_key: str = None,
    ) -> Optional[Dict[str, Any]]:
        """Registra apontamento de horas em um ticket (local + Cloud)."""
        worklog = self._jira_board.log_work(
            ticket_id=ticket_id,
            agent_name=self._jira_agent_name,
            description=description,
            time_spent_minutes=time_spent_minutes,
            auto_logged=auto,
            metadata=metadata or {},
        )
        # Sync worklog com Jira Cloud
        if worklog and cloud_key:
            hours = time_spent_minutes // 60
            mins = time_spent_minutes % 60
            time_str = f"{hours}h {mins}m" if hours else f"{mins}m"
            self._sync_cloud_worklog(cloud_key, time_str, description)
        return worklog.to_dict() if worklog else None

    def jira_log_work_cloud(self, issue_key: str, description: str,
                             time_spent_minutes: int) -> bool:
        """Registra worklog direto no Jira Cloud."""
        hours = time_spent_minutes // 60
        mins = time_spent_minutes % 60
        time_str = f"{hours}h {mins}m" if hours else f"{mins}m"
        return self._sync_cloud_worklog(issue_key, time_str, description)

    def jira_auto_log(self, ticket_id: str, task_description: str,
                      start_time: datetime, end_time: datetime = None,
                      cloud_key: str = None) -> Optional[Dict[str, Any]]:
        """Auto-log de trabalho (cálculo automático de duração)."""
        end = end_time or datetime.now()
        minutes = max(1, int((end - start_time).total_seconds() / 60))
        return self.jira_log_work(
            ticket_id=ticket_id,
            description=f"[AUTO] {task_description}",
            time_spent_minutes=minutes,
            auto=True,
            metadata={"start": start_time.isoformat(), "end": end.isoformat()},
            cloud_key=cloud_key,
        )

    # ─── Comentários ──────────────────────────────────────────────────────────

    def jira_add_comment(self, ticket_id: str, body: str,
                          cloud_key: str = None) -> bool:
        """Adiciona comentário em um ticket (local + Cloud)."""
        comment = self._jira_board.add_comment(ticket_id, self._jira_agent_name, body)
        # Sync com Cloud
        if cloud_key:
            self._sync_cloud_comment(cloud_key, f"🤖 {self._jira_agent_name}: {body}")
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

        summary = {
            "agent": self._jira_agent_name,
            "tickets_by_status": {s: len(tl) for s, tl in all_tickets.items()},
            "total_tickets": sum(len(tl) for tl in all_tickets.values()),
            "total_logged_hours": round(total_logged, 1),
            "total_points_completed": total_points_done,
            "current_work": self.jira_my_current_work(),
            "next_up": self.jira_my_todo()[:3],
            "cloud_enabled": self._jira_cloud_enabled,
        }
        return summary
