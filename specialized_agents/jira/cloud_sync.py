"""
Jira Cloud Sync — Sincronização periódica entre board local e Jira Cloud.

Mantém o board local (jira_rpa4all.json) em sincronia com o Jira Cloud
(rpa4all.atlassian.net), permitindo que métricas locais e dashboards
reflitam o estado real do projeto.

Inclui distribuição inteligente de tickets para agentes por labels/skills.

Uso:
    # Sync manual
    python -m specialized_agents.jira.cloud_sync

    # Dentro do código
    from specialized_agents.jira.cloud_sync import sync_from_cloud, distribute_and_sync
    await sync_from_cloud()
    await distribute_and_sync()  # Puxa + distribui + inicia
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from .models import (
    JiraTicket, JiraEpic, JiraSprint,
    TicketStatus, TicketPriority, TicketType, SprintStatus,
)
from .jira_board import get_jira_board

logger = logging.getLogger(__name__)

# ─── Labels → Agent mapping ──────────────────────────────────────────────────

# Labels que indicam qual agente deve pegar o ticket
_LABEL_TO_AGENT = {
    "python_agent": "python_agent",
    "python-agent": "python_agent",
    "python": "python_agent",
    "fastapi": "python_agent",
    "django": "python_agent",
    "flask": "python_agent",
    "selenium": "python_agent",
    "streamlit": "python_agent",
    "javascript_agent": "javascript_agent",
    "js-agent": "javascript_agent",
    "javascript": "javascript_agent",
    "node": "javascript_agent",
    "react": "javascript_agent",
    "express": "javascript_agent",
    "typescript_agent": "typescript_agent",
    "ts-agent": "typescript_agent",
    "typescript": "typescript_agent",
    "nextjs": "typescript_agent",
    "angular": "typescript_agent",
    "go_agent": "go_agent",
    "go-agent": "go_agent",
    "golang": "go_agent",
    "go": "go_agent",
    "rust_agent": "rust_agent",
    "rust-agent": "rust_agent",
    "rust": "rust_agent",
    "java_agent": "java_agent",
    "java-agent": "java_agent",
    "java": "java_agent",
    "spring": "java_agent",
    "csharp_agent": "csharp_agent",
    "csharp-agent": "csharp_agent",
    "csharp": "csharp_agent",
    "dotnet": "csharp_agent",
    "php_agent": "php_agent",
    "php-agent": "php_agent",
    "php": "php_agent",
    "laravel": "php_agent",
    "po_agent": "po_agent",
    "po-agent": "po_agent",
}


def _resolve_agent_from_labels(labels: List[str]) -> str:
    """Determina o melhor agente a partir das labels de um ticket."""
    if not labels:
        return ""
    # Primeiro, procurar match direto de agent name
    for lbl in labels:
        agent = _LABEL_TO_AGENT.get(lbl.lower())
        if agent:
            return agent
    return ""

# Mapeamento de status Cloud → local
_CLOUD_TO_LOCAL_STATUS = {
    "tarefas pendentes": TicketStatus.TODO,
    "to do": TicketStatus.TODO,
    "a fazer": TicketStatus.TODO,
    "backlog": TicketStatus.BACKLOG,
    "em andamento": TicketStatus.IN_PROGRESS,
    "in progress": TicketStatus.IN_PROGRESS,
    "em revisão": TicketStatus.IN_REVIEW,
    "in review": TicketStatus.IN_REVIEW,
    "testing": TicketStatus.TESTING,
    "concluído": TicketStatus.DONE,
    "done": TicketStatus.DONE,
    "concluída": TicketStatus.DONE,
}

_CLOUD_TO_LOCAL_PRIORITY = {
    "highest": TicketPriority.CRITICAL,
    "high": TicketPriority.HIGH,
    "medium": TicketPriority.MEDIUM,
    "low": TicketPriority.LOW,
    "lowest": TicketPriority.TRIVIAL,
    "mais alta": TicketPriority.CRITICAL,
    "alta": TicketPriority.HIGH,
    "média": TicketPriority.MEDIUM,
    "baixa": TicketPriority.LOW,
    "mais baixa": TicketPriority.TRIVIAL,
}

_CLOUD_TO_LOCAL_TYPE = {
    "epic": TicketType.EPIC,
    "story": TicketType.STORY,
    "task": TicketType.TASK,
    "tarefa": TicketType.TASK,
    "bug": TicketType.BUG,
    "sub-task": TicketType.SUBTASK,
    "subtarefa": TicketType.SUBTASK,
    "improvement": TicketType.IMPROVEMENT,
    "melhoria": TicketType.IMPROVEMENT,
}


def _parse_status(cloud_status: str) -> TicketStatus:
    return _CLOUD_TO_LOCAL_STATUS.get(cloud_status.lower(), TicketStatus.TODO)


def _parse_priority(cloud_priority: str) -> TicketPriority:
    return _CLOUD_TO_LOCAL_PRIORITY.get(cloud_priority.lower(), TicketPriority.MEDIUM)


def _parse_type(cloud_type: str) -> TicketType:
    return _CLOUD_TO_LOCAL_TYPE.get(cloud_type.lower(), TicketType.TASK)


async def sync_from_cloud(project_key: str = "SCRUM") -> Dict[str, Any]:
    """
    Sincroniza board local a partir do Jira Cloud.
    Puxa todas as issues do projeto e atualiza/cria tickets locais.
    
    Returns:
        Dict com contadores: created, updated, unchanged, errors
    """
    from .atlassian_client import get_jira_cloud_client

    client = get_jira_cloud_client()
    if not client.is_configured:
        return {"error": "JIRA_API_TOKEN não configurado"}

    board = get_jira_board()
    stats = {"created": 0, "updated": 0, "unchanged": 0, "errors": 0, "synced_at": None}

    try:
        # Buscar todas as issues do projeto
        jql = f"project = {project_key} ORDER BY key ASC"
        result = await client.search_issues(
            jql,
            fields="summary,status,issuetype,priority,labels,assignee,"
                   "created,updated,parent,description,customfield_10016",
            max_results=200,
        )
        issues = result.get("issues", [])
        logger.info("☁️  Sync: %d issues encontradas no Jira Cloud", len(issues))

        # Buscar sprints ativos
        boards = await client.get_boards(project_key)
        active_sprint_ids: Dict[str, str] = {}  # issue_key -> sprint_name
        if boards:
            board_id = boards[0]["id"]
            try:
                sprints = await client.get_sprints(board_id, state="active")
                for sprint in sprints:
                    sprint_issues = await client.get_sprint_issues(sprint["id"])
                    for si in sprint_issues:
                        active_sprint_ids[si.get("key", "")] = sprint.get("name", "")
            except Exception as e:
                logger.warning("☁️  Não foi possível buscar sprints: %s", e)

        # Processar cada issue
        for issue in issues:
            try:
                fields = issue.get("fields", {})
                key = issue.get("key", "")
                cloud_id = issue.get("id", "")

                status_name = fields.get("status", {}).get("name", "To Do") if fields.get("status") else "To Do"
                type_name = fields.get("issuetype", {}).get("name", "Task") if fields.get("issuetype") else "Task"
                priority_name = fields.get("priority", {}).get("name", "Medium") if fields.get("priority") else "Medium"
                assignee = fields.get("assignee")
                assignee_name = ""
                if assignee:
                    display = assignee.get("displayName", "")
                    assignee_name = display

                labels = fields.get("labels", [])
                # MAPEAR labels para agente local — ESSENCIAL para distribuição
                agent_from_labels = _resolve_agent_from_labels(labels)
                local_assignee = agent_from_labels or assignee_name
                story_points = fields.get("customfield_10016") or 0
                parent = fields.get("parent", {})
                parent_key = parent.get("key") if parent else None

                # Verificar se ticket local já existe (por key)
                existing = None
                for tid, t in board.tickets.items():
                    if t.key == key:
                        existing = t
                        break

                local_status = _parse_status(status_name)
                local_priority = _parse_priority(priority_name)
                local_type = _parse_type(type_name)

                if existing:
                    # Atualizar ticket existente
                    changed = False
                    if existing.status != local_status:
                        existing.status = local_status
                        changed = True
                    if existing.priority != local_priority:
                        existing.priority = local_priority
                        changed = True
                    if existing.title != fields.get("summary", ""):
                        existing.title = fields.get("summary", "")
                        changed = True
                    if existing.labels != labels:
                        existing.labels = labels
                        changed = True
                    if existing.story_points != story_points:
                        existing.story_points = story_points
                        changed = True
                    # Atualizar assignee se veio das labels e estava vazio/diferente
                    if agent_from_labels and existing.assignee != agent_from_labels:
                        existing.assignee = agent_from_labels
                        changed = True
                    if changed:
                        existing.updated_at = datetime.now()
                        if local_status == TicketStatus.DONE and not existing.resolved_at:
                            existing.resolved_at = datetime.now()
                        stats["updated"] += 1
                    else:
                        stats["unchanged"] += 1
                else:
                    # Criar novo ticket local com assignee mapeado das labels
                    ticket = board.create_ticket(
                        title=fields.get("summary", key),
                        description="",  # Descrição ADF é complexa, simplificar
                        ticket_type=local_type,
                        priority=local_priority,
                        assignee=local_assignee,
                        reporter="cloud_sync",
                        story_points=story_points,
                        labels=labels,
                    )
                    # Sobrescrever key com a do Cloud
                    ticket.key = key
                    ticket.status = local_status
                    if local_status == TicketStatus.DONE:
                        ticket.resolved_at = datetime.now()
                    ticket.metadata = {"cloud_id": cloud_id}
                    stats["created"] += 1

            except Exception as e:
                logger.error("☁️  Erro sincronizando issue %s: %s",
                             issue.get("key", "?"), e)
                stats["errors"] += 1

        board._save()
        stats["synced_at"] = datetime.now().isoformat()
        logger.info("☁️  Sync completo: %d criados, %d atualizados, %d unchanged, %d erros",
                     stats["created"], stats["updated"], stats["unchanged"], stats["errors"])

    except Exception as e:
        logger.error("☁️  Sync falhou: %s", e)
        stats["errors"] += 1
        stats["error_message"] = str(e)

    return stats


async def sync_to_cloud(project_key: str = "SCRUM") -> Dict[str, Any]:
    """
    Sincroniza tickets locais que mudaram de status para o Jira Cloud.
    Útil para quando agentes movem tickets no board local.
    """
    from .atlassian_client import get_jira_cloud_client

    client = get_jira_cloud_client()
    if not client.is_configured:
        return {"error": "JIRA_API_TOKEN não configurado"}

    board = get_jira_board()
    stats = {"transitioned": 0, "skipped": 0, "errors": 0}

    # Mapeamento status local → Cloud
    local_to_cloud = {
        TicketStatus.TODO: "Tarefas pendentes",
        TicketStatus.BACKLOG: "Tarefas pendentes",
        TicketStatus.IN_PROGRESS: "Em andamento",
        TicketStatus.IN_REVIEW: "Em andamento",
        TicketStatus.DONE: "Concluído",
    }

    for tid, ticket in board.tickets.items():
        if not ticket.key or not ticket.key.startswith(project_key):
            continue

        target_cloud_status = local_to_cloud.get(ticket.status)
        if not target_cloud_status:
            stats["skipped"] += 1
            continue

        try:
            # Verificar status atual no Cloud
            cloud_issue = await client.get_issue(ticket.key, fields="status")
            current_cloud_status = cloud_issue.get("fields", {}).get(
                "status", {}).get("name", "")

            if current_cloud_status.lower() == target_cloud_status.lower():
                stats["skipped"] += 1
                continue

            # Transicionar
            await client.move_issue_to_status(
                ticket.key, target_cloud_status,
                f"🤖 Sync automático: {ticket.status.value}")
            stats["transitioned"] += 1
            logger.info("☁️  Sync→Cloud: %s %s → %s",
                         ticket.key, current_cloud_status, target_cloud_status)

        except ValueError as e:
            logger.warning("☁️  Transição não disponível para %s: %s", ticket.key, e)
            stats["skipped"] += 1
        except Exception as e:
            logger.error("☁️  Erro sync→Cloud para %s: %s", ticket.key, e)
            stats["errors"] += 1

    return stats


async def get_cloud_board_summary(project_key: str = "SCRUM") -> Dict[str, Any]:
    """
    Retorna resumo do estado atual do board no Jira Cloud.
    Útil para diagnóstico e dashboards.
    """
    from .atlassian_client import get_jira_cloud_client

    client = get_jira_cloud_client()
    if not client.is_configured:
        return {"error": "JIRA_API_TOKEN não configurado"}

    try:
        # Issues por status
        result = await client.search_issues(
            f"project = {project_key} ORDER BY status ASC",
            max_results=200,
        )
        issues = result.get("issues", [])

        by_status: Dict[str, List[str]] = {}
        by_assignee: Dict[str, int] = {}
        total = len(issues)

        for iss in issues:
            fields = iss.get("fields", {})
            status = fields.get("status", {}).get("name", "Unknown")
            key = iss.get("key", "?")
            summary = fields.get("summary", "?")
            assignee = fields.get("assignee")
            a_name = assignee.get("displayName", "Não atribuído") if assignee else "Não atribuído"

            by_status.setdefault(status, []).append(f"{key}: {summary}")
            by_assignee[a_name] = by_assignee.get(a_name, 0) + 1

        # Sprint ativo
        sprint_info = None
        boards = await client.get_boards(project_key)
        if boards:
            try:
                sprints = await client.get_sprints(boards[0]["id"], state="active")
                if sprints:
                    sprint_info = {
                        "name": sprints[0].get("name", ""),
                        "goal": sprints[0].get("goal", ""),
                        "state": sprints[0].get("state", ""),
                    }
            except Exception:
                pass

        return {
            "project": project_key,
            "total_issues": total,
            "by_status": {s: len(items) for s, items in by_status.items()},
            "by_status_detail": by_status,
            "by_assignee": by_assignee,
            "active_sprint": sprint_info,
            "queried_at": datetime.now().isoformat(),
        }

    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════ Distribuição Integrada ═══════════════════════════

async def distribute_and_sync(project_key: str = "SCRUM") -> Dict[str, Any]:
    """
    Pipeline completo de distribuição:
    1. Puxa todos os tickets do Jira Cloud → board local (com labels→agent mapping)
    2. Distribui tickets sem agente usando PO Agent
    3. Move tickets atribuídos para IN_PROGRESS no board local
    3.5. Cria feature branches no GitHub para cada ticket iniciado
    4. Sincroniza transições de volta para o Jira Cloud
    5. Publica notificações no bus para cada agente (com branch name)
    
    Returns:
        Dict com resultados de cada etapa
    """
    from .atlassian_client import get_jira_cloud_client

    try:
        from specialized_agents.agent_communication_bus import (
            get_communication_bus, MessageType,
        )
        bus = get_communication_bus()
        bus_ok = True
    except ImportError:
        bus_ok = False

    client = get_jira_cloud_client()
    if not client.is_configured:
        return {"error": "JIRA_API_TOKEN não configurado"}

    result = {
        "step_1_sync": {},
        "step_2_distribute": {},
        "step_3_start": {},
        "step_3_5_branches": {},
        "step_4_cloud_sync": {},
        "step_5_notify": {},
    }

    # ─── Step 1: Pull Cloud → Local ──────────────────────────────────────────
    logger.info("📥 Step 1: Sincronizando Cloud → Local...")
    sync_result = await sync_from_cloud(project_key)
    result["step_1_sync"] = sync_result

    # ─── Step 2: Distribuir tickets sem agente ────────────────────────────────
    logger.info("📋 Step 2: Distribuindo tickets sem agente...")
    board = get_jira_board()
    distributed = {}
    unassigned_count = 0

    for tid, ticket in board.tickets.items():
        if not ticket.key.startswith(project_key):
            continue
        if ticket.status in (TicketStatus.DONE, TicketStatus.CANCELLED):
            continue
        if ticket.assignee and ticket.assignee in (
            "python_agent", "javascript_agent", "typescript_agent",
            "go_agent", "rust_agent", "java_agent", "csharp_agent",
            "php_agent", "po_agent",
        ):
            continue  # Já distribuído para um agente válido

        # Tentar resolver pelo labels
        agent = _resolve_agent_from_labels(ticket.labels)
        if not agent:
            # Fallback: usar PO Agent para decidir
            try:
                from .po_agent import ProductOwnerAgent, AGENT_SKILLS
                po = ProductOwnerAgent(board)
                agent = po._best_agent_for(ticket.labels)
            except Exception:
                agent = "python_agent"  # Fallback final

        if agent:
            ticket.assignee = agent
            ticket.updated_at = datetime.now()
            distributed.setdefault(agent, []).append(ticket.key)
            unassigned_count += 1

    board._save()
    result["step_2_distribute"] = {
        "distributed": unassigned_count,
        "by_agent": {a: len(keys) for a, keys in distributed.items()},
        "details": distributed,
    }

    # ─── Step 3: Mover tickets TODO → IN_PROGRESS (1 por agente, WIP limit) ──
    logger.info("🚀 Step 3: Iniciando tickets (1 por agente, WIP=2)...")
    started = {}
    WIP_LIMIT = 2

    for agent_name in [
        "python_agent", "javascript_agent", "typescript_agent",
        "go_agent", "rust_agent", "java_agent", "csharp_agent",
        "php_agent",
    ]:
        # Verificar WIP atual
        in_progress = board.list_tickets(
            assignee=agent_name, status=TicketStatus.IN_PROGRESS)
        if len(in_progress) >= WIP_LIMIT:
            continue

        # Pegar próximo ticket TODO
        slots = WIP_LIMIT - len(in_progress)
        todo = board.list_tickets(assignee=agent_name, status=TicketStatus.TODO)
        if not todo:
            todo = board.list_tickets(assignee=agent_name, status=TicketStatus.BACKLOG)
        if not todo:
            continue

        # Ordenar por prioridade
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "trivial": 4}
        todo.sort(key=lambda t: priority_order.get(t.priority.value, 5))

        for ticket in todo[:slots]:
            board.update_ticket_status(ticket.id, TicketStatus.IN_PROGRESS, "po_agent")
            started.setdefault(agent_name, []).append(ticket.key)

    result["step_3_start"] = {
        "started_count": sum(len(v) for v in started.values()),
        "by_agent": started,
    }

    # ─── Step 3.5: Criar branches no GitHub ──────────────────────────────────
    logger.info("🌿 Step 3.5: Criando feature branches no GitHub...")
    branch_results = {"skipped": False}
    try:
        from .github_branch import create_branches_for_tickets, PROJECT_REPOS

        if project_key in PROJECT_REPOS:
            # Coletar summaries dos tickets para gerar nomes de branch
            all_ticket_keys = {}
            ticket_summaries = {}
            for agent_name, keys in {**distributed, **started}.items():
                for key in keys:
                    all_ticket_keys.setdefault(agent_name, [])
                    if key not in [k for ks in all_ticket_keys.values() for k in ks]:
                        all_ticket_keys[agent_name].append(key)
                    ticket = board.tickets.get(key) or board.tickets.get(
                        next((tid for tid, t in board.tickets.items() if t.key == key), ""))
                    if ticket:
                        ticket_summaries[key] = ticket.title

            branch_results = await create_branches_for_tickets(
                tickets_by_agent=all_ticket_keys,
                project_key=project_key,
                ticket_summaries=ticket_summaries,
            )
        else:
            branch_results["skipped"] = True
            branch_results["reason"] = f"No GitHub repo mapped for {project_key}"
            logger.info("Skipping branches — no repo for project %s", project_key)
    except Exception as e:
        logger.error("Branch creation failed: %s", e)
        branch_results = {"error": str(e), "skipped": True}

    result["step_3_5_branches"] = branch_results

    # ─── Step 4: Sync transições → Cloud ─────────────────────────────────────
    logger.info("☁️  Step 4: Sincronizando transições → Cloud...")
    cloud_transitions = {"success": 0, "skipped": 0, "errors": 0}

    local_to_cloud_status = {
        TicketStatus.IN_PROGRESS: "Em andamento",
        TicketStatus.DONE: "Concluído",
    }

    for agent_name, keys in started.items():
        for key in keys:
            try:
                await client.move_issue_to_status(
                    key, "Em andamento",
                    f"🤖 {agent_name} iniciou trabalho neste ticket")
                cloud_transitions["success"] += 1
                logger.info("☁️  %s → Em andamento (por %s)", key, agent_name)
            except ValueError as e:
                # Transição já feita ou não disponível
                logger.warning("☁️  Transição não disponível para %s: %s", key, e)
                cloud_transitions["skipped"] += 1
            except Exception as e:
                logger.error("☁️  Erro transição Cloud %s: %s", key, e)
                cloud_transitions["errors"] += 1

    result["step_4_cloud_sync"] = cloud_transitions

    # ─── Step 5: Notificar agentes via bus ────────────────────────────────────
    logger.info("📢 Step 5: Notificando agentes...")
    notifications = []

    if bus_ok:
        # Build branch lookup from step 3.5
        branch_lookup = {}
        if isinstance(branch_results, dict) and "branches" in branch_results:
            for key, binfo in branch_results["branches"].items():
                branch_lookup[key] = binfo.get("branch", "")

        for agent_name in set(list(distributed.keys()) + list(started.keys())):
            dist_keys = distributed.get(agent_name, [])
            start_keys = started.get(agent_name, [])
            msg_parts = []
            if dist_keys:
                msg_parts.append(f"Tickets atribuídos: {dist_keys}")
            if start_keys:
                msg_parts.append(f"Tickets iniciados: {start_keys}")
                # Include branch names
                for k in start_keys:
                    br = branch_lookup.get(k)
                    if br:
                        msg_parts.append(f"  → {k}: branch={br}")
            if msg_parts:
                msg = f"🎯 {agent_name}: {' | '.join(msg_parts)}"
                try:
                    meta = {"action": "work_assigned"}
                    # Add branch info to metadata
                    agent_branches = {k: branch_lookup[k] for k in start_keys if k in branch_lookup}
                    if agent_branches:
                        meta["branches"] = agent_branches
                        meta["repo"] = branch_results.get("repo", "")
                    bus.publish(
                        MessageType.REQUEST, "po_agent", agent_name,
                        msg, meta)
                    notifications.append(msg)
                except Exception as e:
                    logger.error("Bus notify falhou: %s", e)

    result["step_5_notify"] = {"sent": len(notifications), "messages": notifications}

    # ─── Resumo final ────────────────────────────────────────────────────────
    total_distributed = result["step_2_distribute"]["distributed"]
    total_started = result["step_3_start"]["started_count"]
    total_cloud = cloud_transitions["success"]

    logger.info(
        "✅ Distribuição completa: %d distribuídos, %d iniciados, %d sincronizados no Cloud",
        total_distributed, total_started, total_cloud)

    result["summary"] = {
        "total_distributed": total_distributed,
        "total_started": total_started,
        "total_cloud_transitioned": total_cloud,
        "branches_created": branch_results.get("created", 0) if isinstance(branch_results, dict) else 0,
        "timestamp": datetime.now().isoformat(),
    }

    return result


# ─── CLI ──────────────────────────────────────────────────────────────────────

async def _main():
    """Execução via CLI: python -m specialized_agents.jira.cloud_sync"""
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")

    cmd = sys.argv[1] if len(sys.argv) > 1 else "summary"

    if cmd == "pull":
        print("☁️  Sincronizando Cloud → Local...")
        result = await sync_from_cloud()
        print(f"   Criados: {result.get('created', 0)}")
        print(f"   Atualizados: {result.get('updated', 0)}")
        print(f"   Sem mudança: {result.get('unchanged', 0)}")
        print(f"   Erros: {result.get('errors', 0)}")

    elif cmd == "push":
        print("☁️  Sincronizando Local → Cloud...")
        result = await sync_to_cloud()
        print(f"   Transicionados: {result.get('transitioned', 0)}")
        print(f"   Pulados: {result.get('skipped', 0)}")
        print(f"   Erros: {result.get('errors', 0)}")

    elif cmd == "distribute":
        print("🎯 Distribuindo tickets Cloud → Agentes...")
        result = await distribute_and_sync()
        s = result.get("summary", {})
        print(f"   Distribuídos: {s.get('total_distributed', 0)}")
        print(f"   Iniciados: {s.get('total_started', 0)}")
        print(f"   Cloud sync: {s.get('total_cloud_transitioned', 0)}")
        print(f"\n   Detalhes por agente:")
        dist = result.get("step_2_distribute", {}).get("details", {})
        started = result.get("step_3_start", {}).get("by_agent", {})
        all_agents = set(list(dist.keys()) + list(started.keys()))
        for agent in sorted(all_agents):
            d = dist.get(agent, [])
            s = started.get(agent, [])
            print(f"     {agent}: atribuídos={d}, iniciados={s}")

    elif cmd == "summary":
        print("☁️  Resumo do Board Jira Cloud...")
        result = await get_cloud_board_summary()
        if "error" in result:
            print(f"   Erro: {result['error']}")
            return
        print(f"   Projeto: {result['project']}")
        print(f"   Total issues: {result['total_issues']}")
        print(f"   Por status:")
        for status, count in result.get("by_status", {}).items():
            print(f"     {status}: {count}")
        print(f"   Por responsável:")
        for name, count in result.get("by_assignee", {}).items():
            print(f"     {name}: {count}")
        if result.get("active_sprint"):
            print(f"   Sprint ativo: {result['active_sprint']['name']}")

    else:
        print(f"Uso: python -m specialized_agents.jira.cloud_sync [pull|push|distribute|summary]")


if __name__ == "__main__":
    asyncio.run(_main())
