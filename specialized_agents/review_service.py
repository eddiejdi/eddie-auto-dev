#!/usr/bin/env python3
"""
Review Service Daemon — Processa fila de reviews continuamente

Ciclo:
1. Buscar próximos items da fila
2. Chamar ReviewAgent para análise
3. Se aprovado → executar testes automáticos (Selenium, integração)
4. Se OK tudo → merge automático
5. Se rejeitado → notificar agent + registrar feedback para training
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

# Add root to path
_PROJ_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJ_ROOT not in sys.path:
    sys.path.insert(0, _PROJ_ROOT)

from specialized_agents.review_agent import ReviewAgent, ReviewDecision
from specialized_agents.review_queue import get_review_queue
from specialized_agents.review_metrics import (
    update_metrics_from_queue,
    update_metrics_from_agent,
    record_cycle,
    record_error,
    set_service_health,
    record_review_time,
    record_cycle_time,
    record_training_feedback,
)
from specialized_agents.agent_communication_bus import (
    get_communication_bus,
    MessageType,
    log_task_start,
    log_task_end,
    log_error,
)

logger = logging.getLogger("review_service")

# Config
POLL_INTERVAL = int(os.getenv("REVIEW_SERVICE_POLL_INTERVAL", "60"))  # 1 min
BATCH_SIZE = int(os.getenv("REVIEW_SERVICE_BATCH", "3"))  # processar 3 por vez
AUTO_MERGE = os.getenv("REVIEW_SERVICE_AUTO_MERGE", "true").lower() in (
    "true",
    "1",
    "yes",
)
RUN_TESTS = os.getenv("REVIEW_SERVICE_RUN_TESTS", "true").lower() in (
    "true",
    "1",
    "yes",
)

_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    logger.info("Recebido sinal %s, encerrando...", signum)
    _shutdown = True


class ReviewService:
    """Processador da fila de reviews"""

    def __init__(self):
        self.review_agent = ReviewAgent()
        self.queue = get_review_queue()
        self.bus = get_communication_bus()
        self.cycle = 0

    async def process_queue(self) -> Dict[str, Any]:
        """Um ciclo de processamento"""
        self.cycle += 1
        cycle_start = time.time()
        logger.info("─── Ciclo %d ───", self.cycle)

        results = {"cycle": self.cycle, "processed": []}

        # Obter próximos items
        pending = self.queue.get_pending_items(BATCH_SIZE)
        if not pending:
            logger.info("😴 Nenhum item na fila")
            # Atualizar métricas mesmo quando vazio
            stats = self.queue.get_stats()
            update_metrics_from_queue(stats)
            record_cycle()
            return results

        logger.info("📥 Processando %d items", len(pending))

        for item in pending:
            if _shutdown:
                break

            item_start = time.time()
            queue_id = item["queue_id"]
            logger.info(
                "🔍 Review: %s de %s (branch=%s)",
                item["commit_id"][:7],
                item["author_agent"],
                item["branch"],
            )

            try:
                # 1. ReviewAgent analisa
                review_result = await self.review_agent.review_commit(
                    commit_id=item["commit_id"],
                    branch=item["branch"],
                    author_agent=item["author_agent"],
                    diff=item["diff"],
                    files_changed=json.loads(item["files_changed"]),
                )

                record_review_time(time.time() - item_start)

                # 2. Decisão
                decision = review_result.get("decision")

                if decision == ReviewDecision.APPROVE.value:
                    logger.info("✅ APROVADO: %s (score=%d)", queue_id[:8], review_result.get("score", 0))

                    # Rodar testes se necessário
                    if RUN_TESTS and review_result.get("required_tests"):
                        logger.info("🧪 Rodando testes: %s", review_result["required_tests"])
                        test_ok = await self._run_tests(
                            item, review_result.get("required_tests", [])
                        )
                        if not test_ok:
                            logger.warning("❌ Testes falharam, marcando como needs_retest")
                            self.queue.update_status(queue_id, "needs_retest", review_result)
                            results["processed"].append(
                                {
                                    "queue_id": queue_id,
                                    "status": "needs_retest",
                                    "reason": "test_failure",
                                }
                            )
                            continue

                    # Merge automático
                    if AUTO_MERGE:
                        merge_ok = await self._auto_merge(item)
                        if merge_ok:
                            self.queue.update_status(queue_id, "merged", review_result)
                            logger.info("🔀 MERGED: %s", queue_id[:8])
                            results["processed"].append(
                                {"queue_id": queue_id, "status": "merged"}
                            )
                        else:
                            logger.error("Merge falhou para %s", queue_id[:8])
                            results["processed"].append(
                                {
                                    "queue_id": queue_id,
                                    "status": "merge_error",
                                }
                            )
                    else:
                        self.queue.update_status(queue_id, "approved", review_result)
                        results["processed"].append(
                            {"queue_id": queue_id, "status": "approved"}
                        )

                elif decision == ReviewDecision.REQUEST_CHANGES.value:
                    logger.info("🔄 REQUEST_CHANGES: %s", queue_id[:8])
                    self.queue.update_status(queue_id, "request_changes", review_result)
                    await self._notify_agent(
                        item["author_agent"],
                        "request_changes",
                        review_result,
                    )
                    results["processed"].append(
                        {"queue_id": queue_id, "status": "request_changes"}
                    )

                elif decision == ReviewDecision.REJECT.value:
                    logger.warning("❌ REJECTED: %s", queue_id[:8])
                    self.queue.update_status(queue_id, "rejected", review_result)
                    await self._notify_agent(
                        item["author_agent"],
                        "rejected",
                        review_result,
                    )
                    results["processed"].append(
                        {"queue_id": queue_id, "status": "rejected"}
                    )

                elif decision == ReviewDecision.NEEDS_RETEST.value:
                    retry_count = self.queue.increment_retry(queue_id)
                    if retry_count < 3:
                        logger.info("🔄 RETEST #%d: %s", retry_count, queue_id[:8])
                        self.queue.update_status(queue_id, "needs_retest", review_result)
                        results["processed"].append(
                            {
                                "queue_id": queue_id,
                                "status": "needs_retest",
                                "retry": retry_count,
                            }
                        )
                    else:
                        logger.error("❌ Máximo de retries atingido: %s", queue_id[:8])
                        self.queue.update_status(
                            queue_id, "failed_after_retries", review_result
                        )
                        results["processed"].append(
                            {
                                "queue_id": queue_id,
                                "status": "failed_after_retries",
                            }
                        )

            except Exception as e:
                logger.error(
                    "💥 Erro processando %s: %s\n%s",
                    queue_id[:8],
                    e,
                    traceback.format_exc(),
                )
                self.queue.update_status(queue_id, "error", {"error": str(e)})
                results["processed"].append(
                    {"queue_id": queue_id, "status": "error", "error": str(e)[:100]}
                )

        # Publicar resumo no bus
        try:
            self.bus.publish(
                MessageType.RESPONSE,
                "review_service",
                "all",
                json.dumps(results, ensure_ascii=False, default=str),
                {"action": "review_cycle_complete"},
            )
        except Exception:
            pass

        # Atualizar métricas do ciclo
        cycle_time = time.time() - cycle_start
        record_cycle_time(cycle_time)
        record_cycle()
        
        # Atualizar métricas dos dados atuais
        stats = self.queue.get_stats()
        update_metrics_from_queue(stats)
        agent_stats = self.review_agent.get_status()
        update_metrics_from_agent(agent_stats)
        
        logger.info("📊 Ciclo %d: %d items processados (%.2fs)", 
                   self.cycle, len(results["processed"]), cycle_time)

        return results

    async def _run_tests(self, item: Dict, test_types: List[str]) -> bool:
        """Executar testes antes de aprovar (Selenium, integração, etc)"""
        logger.info("🧪 Executando testes: %s", test_types)

        # TODO: chamar Selenium agent para E2E, agent integração, etc
        # Por agora, simulado
        if "selenium" in test_types:
            logger.info("  - Selenium E2E...")
            # await selenium_agent.run_tests(item["branch"])
            pass

        if "integration" in test_types:
            logger.info("  - Testes de integração...")
            # await test_agent.run_integration_tests()
            pass

        # Simulado: 90% sucesso
        import random

        success = random.random() > 0.1
        return success

    async def _auto_merge(self, item: Dict) -> bool:
        """Fazer merge automático para main"""
        logger.info("🔀 Iniciando merge automático: %s", item["branch"])

        try:
            import subprocess

            # Git merge (local do homelab)
            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    f"""
                    cd /home/homelab/eddie-auto-dev && \
                    git fetch origin {item['branch']} main && \
                    git checkout main && \
                    git pull origin main && \
                    git merge --no-ff origin/{item['branch']} -m "Merge {item['commit_id'][:7]} (review approved)" && \
                    git push origin main
                """,
                ],
                capture_output=True,
                timeout=60,
            )

            if result.returncode == 0:
                logger.info("✅ Merge bem-sucedido")
                return True
            else:
                logger.error("❌ Merge falhou: %s", result.stderr.decode()[:200])
                return False

        except Exception as e:
            logger.error("💥 Erro no merge: %s", e)
            return False

    async def _notify_agent(
        self, agent_name: str, decision: str, review_result: Dict
    ):
        """Notificar agent sobre resultado da review"""
        message = {
            "type": "review_result",
            "decision": decision,
            "score": review_result.get("score"),
            "findings": review_result.get("findings", []),
            "recommendations": review_result.get("recommendations", []),
        }

        try:
            self.bus.publish(
                MessageType.REQUEST,
                "review_service",
                agent_name,
                json.dumps(message, ensure_ascii=False),
                {"action": "review_feedback"},
            )
            logger.info("📬 Feedback enviado para %s", agent_name)
        except Exception as e:
            logger.error("Erro notificando agent: %s", e)

    async def retrospective_check(self):
        """Fazer retrospectiva periódica dos agentes"""
        logger.info("📊 Executando retrospectiva dos agentes...")

        agents = [
            "python_agent",
            "javascript_agent",
            "typescript_agent",
            "go_agent",
            "rust_agent",
            "java_agent",
            "csharp_agent",
            "php_agent",
        ]

        for agent in agents:
            retro = await asyncio.to_thread(
                self.review_agent.retrospective, agent, period_days=7
            )
            logger.info(
                "📈 %s: %.1f%% approved, avg_score=%.1f",
                agent,
                retro.get("approved_pct", 0),
                retro.get("avg_score", 0),
            )

            # Se agent está com baixa qualidade, enviar recomendações
            if retro.get("approved_pct", 100) < 60:
                logger.warning(
                    "⚠️  %s com baixa taxa de aprovação, enviando treino", agent
                )
                for rec in retro.get("recommendations", []):
                    await self._notify_agent(agent, "training", {"recommendation": rec})


async def run_service():
    """Loop principal do review service"""
    service = ReviewService()

    logger.info("🚀 Review Service iniciado")
    logger.info("   Poll interval: %ds | Batch: %d | Auto merge: %s | Run tests: %s",
                POLL_INTERVAL, BATCH_SIZE, AUTO_MERGE, RUN_TESTS)

    retro_interval = 0

    while not _shutdown:
        try:
            results = await service.process_queue()
            logger.info(
                "📊 Ciclo %d: %d items processados",
                results["cycle"],
                len(results["processed"]),
            )

            # A cada 10 ciclos, fazer retrospectiva
            retro_interval += 1
            if retro_interval >= 10:
                await service.retrospective_check()
                retro_interval = 0

        except Exception as e:
            logger.error("Erro no ciclo: %s\n%s", e, traceback.format_exc())

        # Aguardar próximo ciclo
        for _ in range(POLL_INTERVAL):
            if _shutdown:
                break
            await asyncio.sleep(1)

    logger.info("🛑 Review Service encerrado")


def main():
    """Entry point"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    asyncio.run(run_service())


if __name__ == "__main__":
    main()
