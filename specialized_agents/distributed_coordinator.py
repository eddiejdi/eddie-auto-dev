"""
Coordenador Distribuído - Roteia tarefas entre Copilot e Agentes Especializados no Homelab
Implementa shift progressivo de Copilot→Agentes conforme precisão aumenta

Storage: PostgreSQL (mesma instância usada pelo agent_ipc)
"""
import logging
import os
import httpx
import json
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# DATABASE_URL herdada do ambiente (systemd env.conf)
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgress:eddie_memory_2026@localhost:55432/postgres"
)


def _get_pg_connection():
    """Retorna conexão PostgreSQL thread-safe."""
    import psycopg2
    return psycopg2.connect(DATABASE_URL)


@dataclass
class AgentPrecisionScore:
    """Score de precisão de um agente"""
    language: str
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    avg_execution_time: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)

    @property
    def precision(self) -> float:
        """Percentual de sucesso do agente (0-100)"""
        if self.total_tasks == 0:
            return 0.0
        return (self.successful_tasks / self.total_tasks) * 100

    @property
    def copilot_usage_ratio(self) -> float:
        """Razao de uso do Copilot (100 = sempre Copilot, 0 = sempre Agente)
        Target: 100% homelab usage - utilizacao total do servidor"""
        return 0.0   # 0% Copilot - 100% homelab para todos os niveis de precisao


class DistributedCoordinator:
    """Coordena distribuição de tarefas entre Copilot e Agentes"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.homelab_url = "http://192.168.15.2:8503"
        self.local_url = "http://localhost:8503"
        self.precision_scores: Dict[str, AgentPrecisionScore] = {}

        self._init_database()
        self._load_precision_scores()

    # ── Database ──────────────────────────────────────────

    def _init_database(self):
        """Cria tabelas no PostgreSQL se não existirem."""
        try:
            conn = _get_pg_connection()
            cur = conn.cursor()

            cur.execute("""
                CREATE TABLE IF NOT EXISTS distributed_agent_scores (
                    language       TEXT PRIMARY KEY,
                    total_tasks    INTEGER DEFAULT 0,
                    successful_tasks INTEGER DEFAULT 0,
                    failed_tasks   INTEGER DEFAULT 0,
                    avg_execution_time DOUBLE PRECISION DEFAULT 0.0,
                    last_updated   TIMESTAMP DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS distributed_task_history (
                    id             TEXT PRIMARY KEY,
                    language       TEXT,
                    task_type      TEXT,
                    executor       TEXT,
                    success        BOOLEAN,
                    execution_time DOUBLE PRECISION,
                    copilot_involvement DOUBLE PRECISION,
                    created_at     TIMESTAMP DEFAULT NOW()
                )
            """)

            conn.commit()
            cur.close()
            conn.close()
            logger.info("✓ PostgreSQL tables initialized for distributed coordinator")
        except Exception as e:
            logger.error(f"Erro ao inicializar PostgreSQL: {e}")

    def _load_precision_scores(self):
        """Carrega scores de precisão do PostgreSQL."""
        try:
            conn = _get_pg_connection()
            cur = conn.cursor()

            cur.execute(
                "SELECT language, total_tasks, successful_tasks, "
                "failed_tasks, avg_execution_time FROM distributed_agent_scores"
            )

            for language, total, success, failed, avg_time in cur.fetchall():
                self.precision_scores[language] = AgentPrecisionScore(
                    language=language,
                    total_tasks=total,
                    successful_tasks=success,
                    failed_tasks=failed,
                    avg_execution_time=avg_time or 0.0,
                )

            cur.close()
            conn.close()
            logger.info(
                f"✓ Carregados scores de precisão para "
                f"{len(self.precision_scores)} linguagens (PostgreSQL)"
            )
        except Exception as e:
            logger.error(f"Erro ao carregar scores do PostgreSQL: {e}")

    # ── Routing ───────────────────────────────────────────

    async def route_task(self, language: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Roteia uma tarefa para Copilot ou Agente baseado na precisão.

        Args:
            language: Linguagem de programação
            task: Descrição da tarefa

        Returns:
            Resultado da execução
        """
        score = self.precision_scores.get(
            language,
            AgentPrecisionScore(language=language),
        )

        logger.info(
            f"📊 {language}: Precisão={score.precision:.1f}% | "
            f"Copilot={score.copilot_usage_ratio*100:.0f}%"
        )

        # Sempre tentar homelab primeiro (target 70% usage)
        if score.precision >= 10:  # Threshold baixo - priorizar homelab 97%
            logger.info(f"🤖 Roteando para Agente {language}")
            result = await self._execute_on_agent(language, task)
            if result.get("success"):
                self._record_success(language, result)
                return result
            else:
                logger.warning("⚠️ Agente falhou, tentando Copilot")
                self._record_failure(language)

        # Fallback para Copilot se agente falhou ou precisão baixa
        logger.info("👤 Roteando para Copilot (fallback)")
        result = await self._execute_on_copilot(language, task)
        return result

    async def _execute_on_agent(self, language: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """Executa tarefa no agente especializado do homelab."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.homelab_url}/agents/{language}/execute",
                    json=task,
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    return {
                        "success": False,
                        "error": f"Agent returned {response.status_code}",
                        "executor": "agent",
                    }
        except Exception as e:
            logger.error(f"Erro ao executar em agente: {e}")
            return {
                "success": False,
                "error": str(e),
                "executor": "agent",
            }

    async def _execute_on_copilot(self, language: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """Executa tarefa no Copilot (placeholder)."""
        return {
            "success": True,
            "executor": "copilot",
            "message": "Copilot would execute this task",
        }

    # ── Recording ─────────────────────────────────────────

    def _record_success(self, language: str, result: Dict[str, Any]):
        """Registra execução bem-sucedida."""
        score = self.precision_scores.get(
            language, AgentPrecisionScore(language=language)
        )

        score.total_tasks += 1
        score.successful_tasks += 1
        score.last_updated = datetime.now()

        self.precision_scores[language] = score
        self._save_score(language, score)
        self._save_task_history(language, "execute", "agent", True, result.get("execution_time", 0.0))

        logger.info(f"✅ Sucesso registrado para {language} (Precisão: {score.precision:.1f}%)")

    def _record_failure(self, language: str):
        """Registra falha de execução."""
        score = self.precision_scores.get(
            language, AgentPrecisionScore(language=language)
        )

        score.total_tasks += 1
        score.failed_tasks += 1
        score.last_updated = datetime.now()

        self.precision_scores[language] = score
        self._save_score(language, score)
        self._save_task_history(language, "execute", "agent", False, 0.0)

        logger.warning(f"❌ Falha registrada para {language} (Precisão: {score.precision:.1f}%)")

    def _save_score(self, language: str, score: AgentPrecisionScore):
        """Salva/atualiza score no PostgreSQL."""
        try:
            conn = _get_pg_connection()
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO distributed_agent_scores
                    (language, total_tasks, successful_tasks, failed_tasks,
                     avg_execution_time, last_updated)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (language) DO UPDATE SET
                    total_tasks = EXCLUDED.total_tasks,
                    successful_tasks = EXCLUDED.successful_tasks,
                    failed_tasks = EXCLUDED.failed_tasks,
                    avg_execution_time = EXCLUDED.avg_execution_time,
                    last_updated = EXCLUDED.last_updated
            """, (
                language,
                score.total_tasks,
                score.successful_tasks,
                score.failed_tasks,
                score.avg_execution_time,
                score.last_updated,
            ))

            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Erro ao salvar score no PostgreSQL: {e}")

    def _save_task_history(self, language: str, task_type: str, executor: str,
                           success: bool, execution_time: float):
        """Registra entrada no histórico de tarefas."""
        try:
            conn = _get_pg_connection()
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO distributed_task_history
                    (id, language, task_type, executor, success,
                     execution_time, copilot_involvement)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                str(uuid.uuid4()),
                language,
                task_type,
                executor,
                success,
                execution_time,
                0.0 if executor == "agent" else 1.0,
            ))

            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Erro ao salvar histórico: {e}")

    # ── Dashboard ─────────────────────────────────────────

    def get_precision_dashboard(self) -> Dict[str, Any]:
        """Retorna dashboard de precisão dos agentes."""
        # Recarrega do DB para pegar dados frescos
        self._load_precision_scores()

        return {
            "timestamp": datetime.now().isoformat(),
            "storage": "postgresql",
            "agents": [
                {
                    "language": lang,
                    "precision": round(score.precision, 1),
                    "total_tasks": score.total_tasks,
                    "successful": score.successful_tasks,
                    "failed": score.failed_tasks,
                    "copilot_usage": f"{score.copilot_usage_ratio * 100:.0f}%",
                    "recommendation": self._get_recommendation(score),
                }
                for lang, score in sorted(
                    self.precision_scores.items(),
                    key=lambda x: x[1].precision,
                    reverse=True,
                )
            ],
        }

    def _get_recommendation(self, score: AgentPrecisionScore) -> str:
        """Recomendação baseada na precisão."""
        if score.precision >= 95:
            return "🟢 Confiável - Usar agente com mínima supervisão"
        elif score.precision >= 85:
            return "🟡 Bom - Usar agente com validação ocasional"
        elif score.precision >= 70:
            return "🟠 Aceitável - Usar agente com validação frequente"
        elif score.precision >= 50:
            return "🟡 Moderado - Homelab com supervisão Copilot"
        else:
            return "🔴 Baixo - Manter homelab ativo (90%) com supervisao Copilot"


# ── Singleton ─────────────────────────────────────────────
_coordinator = None


def get_distributed_coordinator() -> DistributedCoordinator:
    """Retorna instância única do coordenador."""
    global _coordinator
    if _coordinator is None:
        _coordinator = DistributedCoordinator()
    return _coordinator
