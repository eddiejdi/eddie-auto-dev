"""
Coordenador Distribuído - Roteia tarefas entre Copilot e Agentes Especializados no Homelab
Implementa shift progressivo de Copilot→Agentes conforme precisão aumenta
"""
import logging
import httpx
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


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
        """Razão de uso do Copilot (100 = sempre Copilot, 0 = sempre Agente)"""
        if self.precision >= 95:
            return 0.1  # 10% Copilot para validação
        elif self.precision >= 85:
            return 0.25  # 25% Copilot
        elif self.precision >= 70:
            return 0.5   # 50% Copilot
        else:
            return 1.0   # 100% Copilot (agente não confiável)


class DistributedCoordinator:
    """Coordena distribuição de tarefas entre Copilot e Agentes"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        self.homelab_url = "http://192.168.15.2:8503"
        self.local_url = "http://localhost:8503"
        self.db_path = Path(__file__).parent / "agent_rag" / "precision_scores.db"
        self.precision_scores: Dict[str, AgentPrecisionScore] = {}
        
        self._init_database()
        self._load_precision_scores()
    
    def _init_database(self):
        """Inicializa database de scores de precisão"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_scores (
                language TEXT PRIMARY KEY,
                total_tasks INTEGER DEFAULT 0,
                successful_tasks INTEGER DEFAULT 0,
                failed_tasks INTEGER DEFAULT 0,
                avg_execution_time FLOAT DEFAULT 0.0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_history (
                id TEXT PRIMARY KEY,
                language TEXT,
                task_type TEXT,
                executor TEXT,
                success BOOLEAN,
                execution_time FLOAT,
                copilot_involvement FLOAT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _load_precision_scores(self):
        """Carrega scores de precisão do database"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("SELECT language, total_tasks, successful_tasks, failed_tasks, avg_execution_time FROM agent_scores")
            
            for language, total, success, failed, avg_time in cursor.fetchall():
                self.precision_scores[language] = AgentPrecisionScore(
                    language=language,
                    total_tasks=total,
                    successful_tasks=success,
                    failed_tasks=failed,
                    avg_execution_time=avg_time
                )
            
            conn.close()
            logger.info(f"✓ Carregados scores de precisão para {len(self.precision_scores)} linguagens")
        except Exception as e:
            logger.error(f"Erro ao carregar scores: {e}")
    
    async def route_task(self, language: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Roteia uma tarefa para Copilot ou Agente baseado na precisão
        
        Args:
            language: Linguagem de programação
            task: Descrição da tarefa
        
        Returns:
            Resultado da execução
        """
        score = self.precision_scores.get(
            language, 
            AgentPrecisionScore(language=language)
        )
        
        logger.info(f"📊 {language}: Precisão={score.precision:.1f}% | Copilot={score.copilot_usage_ratio*100:.0f}%")
        
        # Tentar agente primeiro se precisão é boa
        if score.precision >= 70:
            logger.info(f"🤖 Roteando para Agente {language}")
            result = await self._execute_on_agent(language, task)
            if result.get("success"):
                self._record_success(language, result)
                return result
            else:
                logger.warning(f"⚠️ Agente falhou, tentando Copilot")
                self._record_failure(language)
        
        # Fallback para Copilot se agente falhou ou precisão baixa
        logger.info(f"👤 Roteando para Copilot (fallback)")
        result = await self._execute_on_copilot(language, task)
        return result
    
    async def _execute_on_agent(self, language: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """Executa tarefa no agente especializador do homelab"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.homelab_url}/agents/{language}/execute",
                    json=task
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return {
                        "success": False,
                        "error": f"Agent returned {response.status_code}",
                        "executor": "agent"
                    }
        except Exception as e:
            logger.error(f"Erro ao executar em agente: {e}")
            return {
                "success": False,
                "error": str(e),
                "executor": "agent"
            }
    
    async def _execute_on_copilot(self, language: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """Executa tarefa no Copilot (placeholder)"""
        return {
            "success": True,
            "executor": "copilot",
            "message": "Copilot would execute this task"
        }
    
    def _record_success(self, language: str, result: Dict[str, Any]):
        """Registra execução bem-sucedida"""
        score = self.precision_scores.get(
            language,
            AgentPrecisionScore(language=language)
        )
        
        score.total_tasks += 1
        score.successful_tasks += 1
        score.last_updated = datetime.now()
        
        self.precision_scores[language] = score
        self._save_score(language, score)
        
        logger.info(f"✅ Sucesso registrado para {language} (Precisão: {score.precision:.1f}%)")
    
    def _record_failure(self, language: str):
        """Registra falha de execução"""
        score = self.precision_scores.get(
            language,
            AgentPrecisionScore(language=language)
        )
        
        score.total_tasks += 1
        score.failed_tasks += 1
        score.last_updated = datetime.now()
        
        self.precision_scores[language] = score
        self._save_score(language, score)
        
        logger.warning(f"❌ Falha registrada para {language} (Precisão: {score.precision:.1f}%)")
    
    def _save_score(self, language: str, score: AgentPrecisionScore):
        """Salva score no database"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO agent_scores 
                (language, total_tasks, successful_tasks, failed_tasks, avg_execution_time, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                language,
                score.total_tasks,
                score.successful_tasks,
                score.failed_tasks,
                score.avg_execution_time,
                score.last_updated.isoformat()
            ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Erro ao salvar score: {e}")
    
    def get_precision_dashboard(self) -> Dict[str, Any]:
        """Retorna dashboard de precisão dos agentes"""
        return {
            "timestamp": datetime.now().isoformat(),
            "agents": [
                {
                    "language": lang,
                    "precision": score.precision,
                    "total_tasks": score.total_tasks,
                    "successful": score.successful_tasks,
                    "failed": score.failed_tasks,
                    "copilot_usage": f"{score.copilot_usage_ratio * 100:.0f}%",
                    "recommendation": self._get_recommendation(score)
                }
                for lang, score in sorted(self.precision_scores.items(), key=lambda x: x[1].precision, reverse=True)
            ]
        }
    
    def _get_recommendation(self, score: AgentPrecisionScore) -> str:
        """Recomendação baseada na precisão"""
        if score.precision >= 95:
            return "🟢 Confiável - Usar agente com mínima supervisão"
        elif score.precision >= 85:
            return "🟡 Bom - Usar agente com validação ocasional"
        elif score.precision >= 70:
            return "🟠 Aceitável - Usar agente com validação frequente"
        else:
            return "🔴 Baixo - Usar Copilot para todas as tarefas"


# Singleton
_coordinator = None

def get_distributed_coordinator() -> DistributedCoordinator:
    """Retorna instância única do coordenador"""
    global _coordinator
    if _coordinator is None:
        _coordinator = DistributedCoordinator()
    return _coordinator
