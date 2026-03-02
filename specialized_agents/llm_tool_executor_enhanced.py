"""
LLM Tool Executor Enhanced — Executor com integração AgentMemory + Bus.

Wraps o LLMToolExecutor base adicionando:
- Registro de decisões no PostgreSQL (AgentMemory)
- Publicação de eventos no AgentCommunicationBus
- Loop de reforço: sucesso → confidence ↑, falha → confidence ↓
- Aprendizado de padrões (learn_pattern) para futuras decisões

Uso:
    from specialized_agents.llm_tool_executor_enhanced import get_enhanced_executor
    executor = get_enhanced_executor()
    result = await executor.execute_with_learning("shell_exec", {"command": "docker ps"})
"""

import asyncio
import json
import time
import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger("llm_tool_executor_enhanced")

# ──────────────────────────────────────────────────────────────────
# Constantes de confiança (reinforcement)
# ──────────────────────────────────────────────────────────────────
CONFIDENCE_SUCCESS = 0.85
CONFIDENCE_FAILURE = 0.45
CONFIDENCE_EXCEPTION = 0.20
CONFIDENCE_MAX_CAP = 0.98
CONFIDENCE_MIN_FLOOR = 0.05


class LLMToolExecutorEnhanced:
    """
    Wrapper em torno do LLMToolExecutor base que adiciona:
    - AgentMemory (PostgreSQL) para registrar decisões e aprender
    - AgentCommunicationBus para publicar eventos inter-agente
    """

    def __init__(self):
        # Importar lazily para evitar circular imports
        from specialized_agents.llm_tool_executor import get_llm_tool_executor
        self.base_executor = get_llm_tool_executor()

        # Memory — graceful fallback se DATABASE_URL não configurado
        self.memory = None
        self._init_memory()

        # Bus — sempre disponível (singleton in-process)
        self.bus = None
        self._init_bus()

        # Cache de estatísticas para decisões informadas
        self._stats_cache: Dict[str, Any] = {}
        self._stats_cache_ttl = 300  # 5 minutos
        self._stats_cache_time = 0

    def _init_memory(self):
        """Inicializa AgentMemory se DATABASE_URL disponível."""
        try:
            db_url = os.environ.get("DATABASE_URL")
            if not db_url:
                logger.info("DATABASE_URL não definida — AgentMemory desabilitada (modo standalone)")
                return

            from specialized_agents.agent_memory import get_agent_memory
            self.memory = get_agent_memory("llm-tool-executor", db_url)
            logger.info("AgentMemory inicializada com sucesso para llm-tool-executor")
        except Exception as e:
            logger.warning(f"Falha ao inicializar AgentMemory: {e} — continuando sem persistência")
            self.memory = None

    def _init_bus(self):
        """Inicializa AgentCommunicationBus."""
        try:
            from specialized_agents.agent_communication_bus import get_communication_bus
            self.bus = get_communication_bus()
            logger.info("AgentCommunicationBus conectado")
        except Exception as e:
            logger.warning(f"Falha ao conectar ao Bus: {e}")
            self.bus = None

    # ──────────────────────────────────────────────────────────────
    # Métodos públicos
    # ──────────────────────────────────────────────────────────────

    async def execute_with_learning(
        self,
        tool_name: str,
        params: Dict[str, Any],
        user_query: str = "",
        conversation_id: str = "",
    ) -> Dict[str, Any]:
        """
        Executa ferramenta + registra decisão + reforça aprendizado.

        Args:
            tool_name: nome da ferramenta (shell_exec, read_file, list_directory, system_info)
            params: parâmetros da ferramenta
            user_query: query original do usuário (para contexto no memory)
            conversation_id: ID da conversa atual

        Returns:
            Dict com resultado + metadata de learning
        """
        start_time = time.time()
        decision_id = None
        command_str = params.get("command", params.get("filepath", params.get("dirpath", str(params))))

        # ──── 1. Consultar memória para decisões similares ────
        past_decisions = await self._recall_similar(tool_name, command_str)

        # ──── 2. Publicar no bus: TASK_START ────
        self._bus_publish("TASK_START", {
            "tool": tool_name,
            "params": params,
            "user_query": user_query,
            "conversation_id": conversation_id,
            "similar_past_decisions": len(past_decisions),
        })

        # ──── 3. Registrar decisão ANTES da execução ────
        initial_confidence = self._compute_initial_confidence(tool_name, command_str, past_decisions)
        decision_id = self._record_decision(
            tool_name=tool_name,
            command=command_str,
            user_query=user_query,
            confidence=initial_confidence,
            past_decisions=past_decisions,
        )

        # ──── 4. Executar ferramenta ────
        try:
            result = self.base_executor.execute_tool(tool_name, params)
            # execute_tool retorna coroutine — await se necessário
            if asyncio.iscoroutine(result):
                result = await result
            elapsed = time.time() - start_time
        except Exception as e:
            elapsed = time.time() - start_time
            result = {
                "success": False,
                "error": str(e),
                "exit_code": -1,
            }
            # Reforço negativo: exceção
            self._update_outcome(decision_id, "exception", {
                "error": str(e),
                "elapsed_seconds": elapsed,
            }, feedback_score=CONFIDENCE_EXCEPTION)

            self._learn_pattern("exception", {
                "tool": tool_name,
                "command": command_str,
                "error": str(e),
            }, success=False)

            self._bus_publish("ERROR", {
                "tool": tool_name,
                "error": str(e),
                "elapsed_seconds": elapsed,
            })

            # Adicionar metadata de learning ao resultado
            result["_learning"] = {
                "decision_id": decision_id,
                "confidence": CONFIDENCE_EXCEPTION,
                "outcome": "exception",
                "similar_past": len(past_decisions),
            }
            return result

        # ──── 5. Determinar outcome e reforçar ────
        success = result.get("success", False)
        exit_code = result.get("exit_code", -1)

        if success:
            outcome = "success"
            confidence = CONFIDENCE_SUCCESS
            # Boost adicional se houve decisões passadas bem-sucedidas similares
            past_success_count = sum(1 for d in past_decisions if d.get("outcome") == "success")
            if past_success_count > 0:
                confidence = min(CONFIDENCE_MAX_CAP, confidence + 0.02 * past_success_count)
        else:
            outcome = "failure"
            confidence = CONFIDENCE_FAILURE

        self._update_outcome(decision_id, outcome, {
            "exit_code": exit_code,
            "elapsed_seconds": elapsed,
            "stdout_len": len(result.get("stdout", "")),
            "stderr_len": len(result.get("stderr", "")),
        }, feedback_score=confidence)

        # ──── 6. Aprender padrão ────
        self._learn_pattern("command_execution", {
            "tool": tool_name,
            "command": command_str,
            "exit_code": exit_code,
            "elapsed": elapsed,
        }, success=success)

        # ──── 7. Publicar resultado no bus ────
        self._bus_publish("TASK_END", {
            "tool": tool_name,
            "success": success,
            "exit_code": exit_code,
            "elapsed_seconds": elapsed,
            "decision_id": decision_id,
            "confidence": confidence,
        })

        # ──── 8. Enriquecer resultado com metadata de learning ────
        result["_learning"] = {
            "decision_id": decision_id,
            "confidence": confidence,
            "outcome": outcome,
            "similar_past": len(past_decisions),
            "elapsed_seconds": round(elapsed, 3),
        }

        return result

    def get_available_tools(self) -> Dict[str, Any]:
        """Retorna ferramentas disponíveis do executor base."""
        return self.base_executor.get_available_tools()

    async def get_learning_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de aprendizado."""
        if not self.memory:
            return {"enabled": False, "reason": "DATABASE_URL não configurada"}

        now = time.time()
        if now - self._stats_cache_time < self._stats_cache_ttl and self._stats_cache:
            return self._stats_cache

        try:
            stats = self.memory.get_decision_statistics()
            patterns = self.memory.get_learned_patterns(limit=20)
            result = {
                "enabled": True,
                "total_decisions": stats.get("total_decisions", 0),
                "success_rate": stats.get("success_rate", 0),
                "avg_confidence": stats.get("avg_confidence", 0),
                "recent_patterns": len(patterns),
                "patterns_summary": [
                    {
                        "type": p.get("pattern_type"),
                        "success": p.get("success_count", 0),
                        "failure": p.get("failure_count", 0),
                    }
                    for p in patterns[:5]
                ],
            }
            self._stats_cache = result
            self._stats_cache_time = now
            return result
        except Exception as e:
            logger.warning(f"Erro ao obter estatísticas: {e}")
            return {"enabled": True, "error": str(e)}

    # ──────────────────────────────────────────────────────────────
    # Métodos privados — Memory
    # ──────────────────────────────────────────────────────────────

    async def _recall_similar(self, tool_name: str, command: str) -> list:
        """Busca decisões passadas similares no AgentMemory."""
        if not self.memory:
            return []
        try:
            decisions = self.memory.recall_similar_decisions(
                application="llm-tool-executor",
                component=tool_name,
                error_type="execution",
                error_message=command[:200],
                limit=5,
            )
            return decisions if decisions else []
        except Exception as e:
            logger.debug(f"recall_similar falhou: {e}")
            return []

    def _record_decision(
        self,
        tool_name: str,
        command: str,
        user_query: str,
        confidence: float,
        past_decisions: list,
    ) -> Optional[int]:
        """Registra decisão no AgentMemory."""
        if not self.memory:
            return None
        try:
            decision_id = self.memory.record_decision(
                application="llm-tool-executor",
                component=tool_name,
                error_type="execution",
                error_message=command[:200],
                decision_type="tool_call",
                decision=f"Execute {tool_name}: {command[:100]}",
                reasoning=f"User query: {user_query[:200]}" if user_query else "Direct tool call",
                confidence=confidence,
                context_data={
                    "command": command,
                    "user_query": user_query[:500] if user_query else "",
                    "past_success_count": sum(
                        1 for d in past_decisions if d.get("outcome") == "success"
                    ),
                },
                metadata={
                    "tool": tool_name,
                    "executor": "enhanced",
                },
            )
            return decision_id
        except Exception as e:
            logger.warning(f"record_decision falhou: {e}")
            return None

    def _update_outcome(
        self,
        decision_id: Optional[int],
        outcome: str,
        details: dict,
        feedback_score: float,
    ):
        """Atualiza outcome da decisão no AgentMemory (reforço)."""
        if not self.memory or decision_id is None:
            return
        try:
            self.memory.update_decision_outcome(
                decision_id=decision_id,
                outcome=outcome,
                outcome_details=details,
                feedback_score=feedback_score,
            )
        except Exception as e:
            logger.debug(f"update_decision_outcome falhou: {e}")

    def _learn_pattern(self, pattern_type: str, pattern_data: dict, success: bool):
        """Registra padrão aprendido no AgentMemory."""
        if not self.memory:
            return
        try:
            self.memory.learn_pattern(
                pattern_type=pattern_type,
                pattern_data=pattern_data,
                success=success,
            )
        except Exception as e:
            logger.debug(f"learn_pattern falhou: {e}")

    def _compute_initial_confidence(
        self,
        tool_name: str,
        command: str,
        past_decisions: list,
    ) -> float:
        """
        Calcula confiança inicial baseada no histórico.
        Se o mesmo comando teve sucesso antes, confiança sobe.
        """
        base = 0.5  # neutro

        if not past_decisions:
            return base

        successes = sum(1 for d in past_decisions if d.get("outcome") == "success")
        failures = sum(1 for d in past_decisions if d.get("outcome") in ("failure", "exception"))
        total = successes + failures

        if total == 0:
            return base

        # Score ponderado pelo histórico
        success_ratio = successes / total
        confidence = base + (success_ratio - 0.5) * 0.4  # range [0.3, 0.7]

        return max(CONFIDENCE_MIN_FLOOR, min(CONFIDENCE_MAX_CAP, confidence))

    # ──────────────────────────────────────────────────────────────
    # Métodos privados — Bus
    # ──────────────────────────────────────────────────────────────

    def _bus_publish(self, event_type: str, data: dict):
        """Publica evento no AgentCommunicationBus."""
        if not self.bus:
            return
        try:
            from specialized_agents.agent_communication_bus import MessageType

            # Mapear event_type para MessageType
            type_map = {
                "TASK_START": MessageType.TASK_START,
                "TASK_END": MessageType.TASK_END,
                "ERROR": MessageType.ERROR,
                "EXECUTION": MessageType.EXECUTION,
            }
            msg_type = type_map.get(event_type, MessageType.EXECUTION)

            # Bus.publish() espera content como str — converter dict
            self.bus.publish(
                message_type=msg_type,
                source="llm-tool-executor",
                target="all",
                content=json.dumps(data, default=str),
                metadata={"event": event_type},
            )
        except Exception as e:
            logger.debug(f"Bus publish falhou: {e}")


# ──────────────────────────────────────────────────────────────────
# Singleton factory
# ──────────────────────────────────────────────────────────────────
_enhanced_executor: Optional[LLMToolExecutorEnhanced] = None


def get_enhanced_executor() -> LLMToolExecutorEnhanced:
    """Retorna instância singleton do executor enhanced."""
    global _enhanced_executor
    if _enhanced_executor is None:
        _enhanced_executor = LLMToolExecutorEnhanced()
    return _enhanced_executor
