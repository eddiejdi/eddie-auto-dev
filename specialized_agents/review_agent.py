#!/usr/bin/env python3
"""
ReviewAgent — Agente especializado em Quality Gate + CI/CD Review

Responsabilidades:
1. Validar código (estilo, segurança, duplicação, complexidade)
2. Executar testes (unit, E2E com Selenium, integração com outros agents)
3. Gerar/validar documentação (Confluence, Jira, Draw.io)
4. Rejeitar commits ruins com feedback claro
5. Aprovar commits bons
6. Retrospectiva e aprendizado dos agentes
7. Recomendações de refatoração

Usa modelo LLM grande (33B+) para análise profunda.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum

from .base_agent import LLMClient
from .agent_communication_bus import (
    get_communication_bus, MessageType,
    log_task_start, log_task_end, log_error
)

logger = logging.getLogger(__name__)


class ReviewStatus(Enum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    REJECTED = "rejected"
    APPROVED = "approved"
    MERGED = "merged"


class ReviewDecision(Enum):
    """Resultado da análise"""
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"
    NEEDS_RETEST = "needs_retest"


class ReviewAgent:
    """
    Agente Review especializado.
    Modelo: Claude 3.5 Sonnet (via Ollama 70B+ ou API externa)
    """

    def __init__(self):
        self.name = "review_agent"
        self.llm = LLMClient(model="claude-sonnet")  # Modelo grande
        self.system_prompt = self._build_system_prompt()
        self.decisions_log: List[Dict[str, Any]] = []

    def _build_system_prompt(self) -> str:
        """Prompt especializado para review de alta qualidade"""
        return """Você é o ReviewAgent, especialista em Quality Gate e CI/CD da plataforma RPA4ALL.

RESPONSABILIDADES:
1. **Validação de Código**: arquitetura, padrões, segurança, performance
2. **Detecção de Duplicação**: encontrar commits iguais/similares
3. **Testes**: avaliar cobertura, requerer testes E2E quando necessário
4. **Documentação**: validar Confluence, Jira, Draw.io atualizado
5. **Aprendizado**: identificar padrões ruins dos agentes e treinar
6. **Retrospectiva**: comparar qualidade antes/depois do treinamento

REGRAS DE DECISÃO:
✅ APROVAR se:
- Código segue padrões do projeto
- Sem duplicação ou Copy-Paste
- Testes cobrem >80% ou justificado
- Documentação atualizada
- Não quebra pipelines existentes
- Commits bem estruturados (não triviais/duplicados)

❌ REJEITAR se:
- Código duplicado/similar a PR anterior
- Teste falha ou não existe para lógica crítica
- Segurança em risco (hardcoded secrets, SQL injection, etc)
- Performance degradada (>10% mais lento)
- Documentação desatualizada
- Commits triviais (import, formatting sem mudança funcional)

🔄 REQUERER MUDANÇAS se:
- Design pode melhorar (mas funciona)
- Recomendações de refatoração (não bloqueia)
- Testes podem ser mais robustos

⚠️ RETESTE se:
- Testes falhram (pode ser flaky)
- Integração com outros agents necessária
- Ambiente de CI inconsistente

SAÍDA OBRIGATÓRIA (JSON):
{
  "decision": "approve|reject|request_changes|needs_retest",
  "score": 0-100,
  "Summary": "resumo executivo (2-3 linhas)",
  "findings": ["achado 1", "achado 2", ...],
  "risks": ["risco 1 se houver"],
  "recommendations": ["recomendação 1", ...],
  "training_feedback": {
    "agent": "agent_name",
    "issue": "descrição do padrão ruim",
    "training": "recomendação de treinamento"
  },
  "tests_required": ["test_type_1", "test_type_2"],
  "retry_count": 0
}
"""

    async def review_commit(
        self,
        commit_id: str,
        branch: str,
        author_agent: str,
        diff: str,
        files_changed: List[str],
        test_results: Optional[Dict] = None,
        previous_reviews: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Revisa um commit/PR completo.

        Args:
            commit_id: hash do commit
            branch: nome da branch
            author_agent: agent que criou
            diff: diff do Git
            files_changed: arquivos modificados
            test_results: resultados de testes (se rodados)
            previous_reviews: reviews anteriores para context (cyclical learning)

        Returns:
            Decision completa com detalhes
        """
        logger.info("🔍 Iniciando review de %s por %s", commit_id[:7], author_agent)

        review = {
            "commit_id": commit_id,
            "branch": branch,
            "author_agent": author_agent,
            "reviewed_at": datetime.now().isoformat(),
            "status": ReviewStatus.IN_REVIEW.value,
        }

        try:
            # 1. Análise de duplicação
            dup_score = await self._check_duplication(
                diff, files_changed, previous_reviews or []
            )
            if dup_score > 0.8:
                review["decision"] = ReviewDecision.REJECT.value
                review["reason"] = "Código duplicado detectado"
                review["duplication_score"] = dup_score
                logger.warning("⚠️  Duplicação alto: %.1f%%", dup_score * 100)
                self.decisions_log.append(review)
                return review

            # 2. Análise de código (segurança, padrões, etc)
            code_analysis = await self._analyze_code(diff, files_changed)
            review["code_analysis"] = code_analysis

            # 3. Validação de testes
            test_validation = await self._validate_tests(
                files_changed, test_results, code_analysis
            )
            review["test_validation"] = test_validation

            # 4. Verificação de documentação
            docs_check = await self._check_documentation(files_changed, branch)
            review["docs_check"] = docs_check

            # 5. Decisão final
            llm_prompt = self._build_review_prompt(
                diff, code_analysis, test_validation, docs_check, author_agent
            )
            decision_json = await self.llm.generate(
                llm_prompt, system=self.system_prompt, temperature=0.3
            )

            try:
                decision = json.loads(decision_json)
            except json.JSONDecodeError:
                # Fallback parsing
                decision = self._parse_review_fallback(decision_json)

            review["decision"] = decision.get("decision", "request_changes")
            review["score"] = decision.get("score", 50)
            review["summary"] = decision.get("summary", "Revisão concluída")
            review["findings"] = decision.get("findings", [])
            review["risks"] = decision.get("risks", [])
            review["recommendations"] = decision.get("recommendations", [])

            # 6. Aprendizado: registrar padrão ruim para treinar agent
            if decision.get("training_feedback"):
                await self._record_training_feedback(
                    author_agent, decision["training_feedback"]
                )

            # 7. Determinar testes necessários
            review["required_tests"] = decision.get("tests_required", [])

            self.decisions_log.append(review)
            logger.info(
                "✅ Review concluído: %s (score=%d)",
                decision["decision"],
                review["score"],
            )

        except Exception as e:
            logger.error("💥 Erro na review: %s", e)
            review["decision"] = "error"
            review["error"] = str(e)
            self.decisions_log.append(review)

        return review

    async def _check_duplication(
        self, diff: str, files: List[str], previous_reviews: List[Dict]
    ) -> float:
        """Detectar se commit é duplicado vs anteriores (0.0-1.0)"""
        if not previous_reviews:
            return 0.0

        # Análise simples: hash do diff, compare com anteriores
        import hashlib

        current_hash = hashlib.sha256(diff[:500].encode()).hexdigest()
        dup_count = 0

        for prev in previous_reviews[-10:]:  # Últimas 10 reviews
            prev_hash = hashlib.sha256(prev.get("diff", "")[:500].encode()).hexdigest()
            if current_hash == prev_hash:
                dup_count += 1

        return min(dup_count / max(len(previous_reviews), 1), 1.0)

    async def _analyze_code(self, diff: str, files: List[str]) -> Dict[str, Any]:
        """Análise profunda de código"""
        prompt = f"""Analise este código (diff) para:
1. Segurança (secrets, injection, etc)
2. Performance (loops, queries, memory)
3. Padrões (arquitetura, design patterns)
4. Legibilidade e manutenibilidade

Diff:
{diff[:2000]}

Arquivos: {files}

Retorne JSON:
{{"security": ["achado1"], "performance": ["achado1"], "patterns": ["achado1"], "readability": ["achado1"]}}
"""
        response = await self.llm.generate(prompt, temperature=0.2)
        try:
            return json.loads(response)
        except:
            return {"raw": response}

    async def _validate_tests(
        self, files: List[str], test_results: Optional[Dict], code_analysis: Dict
    ) -> Dict[str, Any]:
        """Validar se testes cobrem mudanças"""
        if not test_results:
            return {"status": "no_tests", "required": True}

        critical_files = [f for f in files if "core" in f or "agent" in f]
        coverage = test_results.get("coverage", 0)

        return {
            "status": "validated",
            "coverage": coverage,
            "critical_files": critical_files,
            "ok": coverage > 0.75,
        }

    async def _check_documentation(self, files: List[str], branch: str) -> Dict:
        """Verificar se documentação foi atualizada"""
        doc_files = ["README.md", "docs/", ".md"]
        has_docs = any(
            doc in str(files).lower() for doc in doc_files
        ) or "docs" in branch.lower()

        return {"has_docs": has_docs, "required": not has_docs}

    def _build_review_prompt(
        self,
        diff: str,
        code_analysis: Dict,
        test_validation: Dict,
        docs_check: Dict,
        agent_name: str,
    ) -> str:
        """Construir prompt para LLM tomar decisão"""
        return f"""
COMMIT PARA REVIEW:
- Agent: {agent_name}
- Diff (primeiras 1000 chars): {diff[:1000]}
- Análise de código: {json.dumps(code_analysis, ensure_ascii=False)}
- Validação de testes: {json.dumps(test_validation, ensure_ascii=False)}
- Docs atualizado: {docs_check['has_docs']}

Baseado nisso, tome uma decisão e retorne JSON com:
- decision (approve/reject/request_changes/needs_retest)
- score (0-100)
- summary
- findings
- risks
- recommendations
- training_feedback (se houver padrão ruim)
- tests_required
"""

    def _parse_review_fallback(self, text: str) -> Dict[str, Any]:
        """Parser fallback se LLM não retornar JSON válido"""
        decision_map = {
            "approve": "approve",
            "reject": "reject",
            "request": "request_changes",
            "retest": "needs_retest",
        }

        for key, val in decision_map.items():
            if key.lower() in text.lower():
                return {"decision": val, "score": 50, "summary": text[:200]}

        return {"decision": "request_changes", "score": 50, "summary": text[:200]}

    async def _record_training_feedback(self, agent_name: str, feedback: Dict):
        """Registrar feedback para treinar agent (via bus)"""
        bus = get_communication_bus()
        try:
            bus.publish(
                MessageType.REQUEST,
                "review_agent",
                f"{agent_name}",
                json.dumps(
                    {
                        "type": "training_feedback",
                        "issue": feedback.get("issue"),
                        "training": feedback.get("training"),
                    }
                ),
                {"action": "train_from_review"},
            )
            logger.info("📚 Training feedback enviado para %s", agent_name)
        except Exception as e:
            logger.error("Erro enviando feedback: %s", e)

    async def retrospective(
        self, agent_name: str, period_days: int = 7
    ) -> Dict[str, Any]:
        """
        Fazer retrospectiva: como o agent evoluiu?
        Compara qualidade antes vs depois de treinamento.
        """
        # Filtrar decisions do agent nos últimos N dias
        cutoff = datetime.fromisoformat(
            (datetime.now().timestamp() - period_days * 86400).__str__()
        )

        agent_reviews = [
            r
            for r in self.decisions_log
            if r.get("author_agent") == agent_name
            and datetime.fromisoformat(r.get("reviewed_at", "")) > cutoff
        ]

        if not agent_reviews:
            return {"agent": agent_name, "status": "no_reviews_in_period"}

        # Calcular métricas
        avg_score = sum(r.get("score", 50) for r in agent_reviews) / len(agent_reviews)
        approved_pct = (
            sum(
                1
                for r in agent_reviews
                if r.get("decision") == ReviewDecision.APPROVE.value
            )
            / len(agent_reviews)
            * 100
        )
        dup_issues = sum(1 for r in agent_reviews if "duplication_score" in r)

        return {
            "agent": agent_name,
            "period_days": period_days,
            "reviews_count": len(agent_reviews),
            "avg_score": avg_score,
            "approved_pct": approved_pct,
            "duplication_issues": dup_issues,
            "trend": "improving" if len(agent_reviews) < 5 else "stable",
            "recommendations": [
                f"Agente melhorou em {approved_pct:.0f}% de aprovações"
                if approved_pct > 70
                else "Agente precisa melhorar em qualidade",
                "Reduzir commit duplicados" if dup_issues > 2 else "Bom controle de duplicação",
            ],
        }

    def get_status(self) -> Dict[str, Any]:
        """Status geral do ReviewAgent"""
        return {
            "name": self.name,
            "total_reviews": len(self.decisions_log),
            "approvals": sum(
                1 for r in self.decisions_log if r.get("decision") == "approve"
            ),
            "rejections": sum(
                1 for r in self.decisions_log if r.get("decision") == "reject"
            ),
            "avg_score": (
                sum(r.get("score", 50) for r in self.decisions_log)
                / max(len(self.decisions_log), 1)
            ),
        }
