#!/usr/bin/env python3
"""
Jira Worker Service — O "last mile" que faz agentes executarem tickets.

Este serviço:
  1) Periodicamente consulta tickets IN_PROGRESS/TODO atribuídos a cada agente
  2) Para cada ticket encontrado, instancia o agente correto
  3) Cria uma Task a partir do ticket e executa via execute_task()
  4) Registra worklog, atualiza status e sincroniza com Jira Cloud

Sem este serviço, tickets são distribuídos mas nunca executados.
"""
import asyncio
import json
import logging
import os
import signal
import sys
import time
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any

# Adiciona raiz do projeto ao path
_PROJ_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJ_ROOT not in sys.path:
    sys.path.insert(0, _PROJ_ROOT)

from specialized_agents.language_agents import AGENT_CLASSES, create_agent
from specialized_agents.jira.jira_board import get_jira_board
from specialized_agents.jira.models import TicketStatus

logger = logging.getLogger("jira_worker")

# ─── Config ──────────────────────────────────────────────────────────────────
POLL_INTERVAL = int(os.getenv("JIRA_WORKER_POLL_INTERVAL", "120"))   # segundos entre polls
MAX_CONCURRENT_TASKS = int(os.getenv("JIRA_WORKER_MAX_CONCURRENT", "2"))
TASK_TIMEOUT = int(os.getenv("JIRA_WORKER_TASK_TIMEOUT", "300"))      # 5 min por ticket
DRY_RUN = os.getenv("JIRA_WORKER_DRY_RUN", "").lower() in ("1", "true", "yes")

# Map agent_name → language
AGENT_NAME_TO_LANGUAGE = {f"{lang}_agent": lang for lang in AGENT_CLASSES}

# Bus de comunicação
try:
    from specialized_agents.agent_communication_bus import (
        get_communication_bus, MessageType,
        log_task_start, log_task_end, log_error as bus_log_error
    )
    BUS_OK = True
except ImportError:
    BUS_OK = False

_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    logger.info("Recebido sinal %s, encerrando...", signum)
    _shutdown = True


async def _execute_ticket(agent, ticket_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa um ticket Jira usando o agente.
    
    Fluxo:
      1. jira_start_ticket (se ainda não IN_PROGRESS)
      2. create_task + execute_task (gera código, testa, corrige)
      3. jira_auto_log (registra tempo gasto)
      4. jira_submit_for_review ou jira_complete_ticket
    """
    ticket_id = ticket_dict["id"]
    ticket_key = ticket_dict.get("key", ticket_id)
    title = ticket_dict.get("title", "")
    description = ticket_dict.get("description", "") or title
    cloud_key = ticket_dict.get("key", "")  # ex: SCRUM-8

    result = {
        "ticket_id": ticket_id,
        "ticket_key": ticket_key,
        "agent": agent.name,
        "language": agent.language,
        "status": "started",
        "error": None,
    }

    start_time = datetime.now()

    try:
        # 1. Garantir que está IN_PROGRESS
        if ticket_dict.get("status") != TicketStatus.IN_PROGRESS.value:
            if hasattr(agent, "jira_start_ticket"):
                agent.jira_start_ticket(ticket_id, cloud_key=cloud_key)
                logger.info("▶️  [%s] Ticket %s iniciado", agent.language, ticket_key)

        # 2. Criar task e executar
        task_description = f"[{ticket_key}] {title}\n\n{description}"
        task = agent.create_task(task_description, metadata={
            "jira_ticket_id": ticket_id,
            "jira_ticket_key": ticket_key,
            "jira_cloud_key": cloud_key,
        })

        if BUS_OK:
            log_task_start(f"{agent.language}_agent", ticket_key, title)

        logger.info("⚙️  [%s] Executando task %s para ticket %s...",
                     agent.language, task.id, ticket_key)

        # Executa com timeout
        completed_task = await asyncio.wait_for(
            agent.execute_task(task.id),
            timeout=TASK_TIMEOUT
        )

        result["task_id"] = completed_task.id
        result["task_status"] = completed_task.status.value
        result["iterations"] = completed_task.iterations
        result["code_length"] = len(completed_task.code) if completed_task.code else 0
        result["project_path"] = completed_task.project_path

        # 3. Registrar worklog
        end_time = datetime.now()
        if hasattr(agent, "jira_auto_log"):
            agent.jira_auto_log(
                ticket_id, f"Implementação: {title}",
                start_time, end_time, cloud_key=cloud_key
            )
            logger.info("⏱️  [%s] Worklog registrado para %s", agent.language, ticket_key)

        # 4. Atualizar status baseado no resultado
        if completed_task.status.value == "completed":
            if hasattr(agent, "jira_submit_for_review"):
                agent.jira_submit_for_review(
                    ticket_id,
                    comment=f"Código gerado com sucesso em {completed_task.iterations} iteração(ões). "
                            f"Projeto em: {completed_task.project_path or 'N/A'}",
                    cloud_key=cloud_key
                )
                logger.info("✅ [%s] Ticket %s submetido para review",
                             agent.language, ticket_key)
                result["status"] = "submitted_for_review"
            else:
                result["status"] = "completed_no_review"
        else:
            # Task falhou, manter IN_PROGRESS e adicionar comentário
            if hasattr(agent, "jira_add_comment"):
                errors_summary = "; ".join(completed_task.errors[:3]) if completed_task.errors else "Erro desconhecido"
                agent.jira_add_comment(
                    ticket_id,
                    f"⚠️ Tentativa de implementação falhou após {completed_task.iterations} iterações: {errors_summary}",
                    cloud_key=cloud_key
                )
            result["status"] = "failed"
            result["errors"] = completed_task.errors[:5]
            logger.warning("❌ [%s] Ticket %s falhou: %s",
                           agent.language, ticket_key,
                           completed_task.errors[:2] if completed_task.errors else "unknown")

        if BUS_OK:
            log_task_end(f"{agent.language}_agent", ticket_key, result["status"])

    except asyncio.TimeoutError:
        result["status"] = "timeout"
        result["error"] = f"Timeout após {TASK_TIMEOUT}s"
        logger.error("⏰ [%s] Timeout executando ticket %s", agent.language, ticket_key)
        if hasattr(agent, "jira_add_comment"):
            agent.jira_add_comment(
                ticket_id,
                f"⏰ Timeout na execução ({TASK_TIMEOUT}s). Será retentado no próximo ciclo.",
                cloud_key=cloud_key
            )
        if BUS_OK:
            bus_log_error(f"{agent.language}_agent", f"Timeout no ticket {ticket_key}")

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        logger.error("💥 [%s] Erro no ticket %s: %s\n%s",
                      agent.language, ticket_key, e, traceback.format_exc())
        if hasattr(agent, "jira_add_comment"):
            try:
                agent.jira_add_comment(
                    ticket_id,
                    f"💥 Erro na execução: {str(e)[:200]}",
                    cloud_key=cloud_key
                )
            except Exception:
                pass
        if BUS_OK:
            bus_log_error(f"{agent.language}_agent", f"Erro no ticket {ticket_key}: {e}")

    return result


async def _poll_and_execute():
    """Um ciclo de polling: busca tickets e executa."""
    board = get_jira_board()
    executed = []
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

    for agent_name, language in AGENT_NAME_TO_LANGUAGE.items():
        if _shutdown:
            break

        # Buscar tickets IN_PROGRESS primeiro, depois TODO
        tickets = board.list_tickets(assignee=agent_name, status=TicketStatus.IN_PROGRESS)
        if not tickets:
            tickets = board.list_tickets(assignee=agent_name, status=TicketStatus.TODO)
        if not tickets:
            continue

        # Pegar apenas o primeiro ticket (respeitar MAX_CONCURRENT_TASKS)
        ticket = tickets[0]
        ticket_dict = ticket.to_dict()

        logger.info("📋 [%s] Encontrado ticket %s (%s): %s",
                     language, ticket_dict["key"], ticket_dict["status"],
                     ticket_dict["title"][:80])

        if DRY_RUN:
            logger.info("🔍 DRY_RUN: Pulando execução de %s", ticket_dict["key"])
            executed.append({"ticket_key": ticket_dict["key"], "status": "dry_run"})
            continue

        try:
            agent = create_agent(language)
            async with semaphore:
                result = await _execute_ticket(agent, ticket_dict)
                executed.append(result)
        except Exception as e:
            logger.error("Erro criando/executando agente %s: %s", language, e)
            executed.append({
                "ticket_key": ticket_dict.get("key", "?"),
                "status": "agent_error",
                "error": str(e)
            })

    return executed


async def run_worker_loop():
    """Loop principal do worker."""
    logger.info("🚀 Jira Worker Service iniciado")
    logger.info("   Poll interval: %ds | Max concurrent: %d | Task timeout: %ds | Dry run: %s",
                POLL_INTERVAL, MAX_CONCURRENT_TASKS, TASK_TIMEOUT, DRY_RUN)

    cycle = 0
    while not _shutdown:
        cycle += 1
        logger.info("─── Ciclo %d ───", cycle)

        try:
            results = await _poll_and_execute()
            if results:
                logger.info("📊 Resultado do ciclo %d: %d tickets processados", cycle, len(results))
                for r in results:
                    logger.info("   %s → %s %s",
                                r.get("ticket_key", "?"),
                                r.get("status", "?"),
                                f"({r.get('error', '')})" if r.get("error") else "")

                # Publicar resumo no bus
                if BUS_OK:
                    bus = get_communication_bus()
                    summary = {
                        "cycle": cycle,
                        "processed": len(results),
                        "results": [{k: v for k, v in r.items() if k != "errors"} for r in results]
                    }
                    try:
                        bus.publish(
                            MessageType.RESPONSE,
                            "jira_worker",
                            "all",
                            json.dumps(summary, ensure_ascii=False, default=str),
                            {"action": "work_cycle_complete"}
                        )
                    except Exception:
                        pass
            else:
                logger.info("😴 Nenhum ticket para processar neste ciclo")

        except Exception as e:
            logger.error("Erro no ciclo %d: %s\n%s", cycle, e, traceback.format_exc())

        # Aguardar próximo ciclo
        for _ in range(POLL_INTERVAL):
            if _shutdown:
                break
            await asyncio.sleep(1)

    logger.info("🛑 Jira Worker Service encerrado")


def main():
    """Entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    asyncio.run(run_worker_loop())


if __name__ == "__main__":
    main()
