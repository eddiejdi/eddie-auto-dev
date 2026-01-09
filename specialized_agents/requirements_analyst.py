"""
Agente Analista de Requisitos
Responsavel por levantar requisitos, gerar documentacao, casos de teste e aprovar entregas
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

from .base_agent import LLMClient, Task, TaskStatus
from .config import LLM_CONFIG, SYSTEM_PROMPTS


class RequirementStatus(Enum):
    DRAFT = "draft"
    ANALYZING = "analyzing"
    DOCUMENTED = "documented"
    TESTS_GENERATED = "tests_generated"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


class DeliveryStatus(Enum):
    PENDING = "pending"
    REVIEWING = "reviewing"
    NEEDS_CHANGES = "needs_changes"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class Requirement:
    id: str
    title: str
    description: str
    user_story: str = ""
    acceptance_criteria: List[str] = field(default_factory=list)
    priority: str = "medium"
    status: RequirementStatus = RequirementStatus.DRAFT
    documentation: str = ""
    test_cases: List[Dict] = field(default_factory=list)
    technical_specs: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "user_story": self.user_story,
            "acceptance_criteria": self.acceptance_criteria,
            "priority": self.priority,
            "status": self.status.value,
            "documentation": self.documentation,
            "test_cases": self.test_cases,
            "technical_specs": self.technical_specs,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class DeliveryReview:
    id: str
    task_id: str
    requirement_id: str
    agent_name: str
    code: str
    tests: str
    status: DeliveryStatus = DeliveryStatus.PENDING
    review_notes: str = ""
    issues_found: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    approved_at: Optional[datetime] = None
    reviewed_by: str = "RequirementsAnalyst"
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "requirement_id": self.requirement_id,
            "agent_name": self.agent_name,
            "status": self.status.value,
            "review_notes": self.review_notes,
            "issues_found": self.issues_found,
            "suggestions": self.suggestions,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "reviewed_by": self.reviewed_by,
            "created_at": self.created_at.isoformat()
        }


class RequirementsAnalystAgent:
    """
    Agente Analista de Requisitos
    Trabalha em conjunto com agentes programadores para:
    - Levantar e documentar requisitos
    - Gerar casos de teste
    - Aprovar entregas
    """

    def __init__(self):
        self.llm = LLMClient()
        self.requirements: Dict[str, Requirement] = {}
        self.reviews: Dict[str, DeliveryReview] = {}
        self._req_counter = 0
        self._review_counter = 0
        self.rag_manager = None

    @property
    def name(self) -> str:
        return "Requirements Analyst Agent"

    @property
    def capabilities(self) -> List[str]:
        return [
            "Analise e levantamento de requisitos",
            "Geracao de User Stories",
            "Definicao de criterios de aceitacao",
            "Documentacao tecnica e funcional",
            "Geracao de casos de teste",
            "Revisao de codigo e entregas",
            "Aprovacao de entregas de agentes",
            "Validacao de qualidade"
        ]

    def _get_system_prompt(self) -> str:
        return SYSTEM_PROMPTS.get("requirements_analyst", """
Voce e um Analista de Requisitos senior especializado em engenharia de software.
Suas responsabilidades incluem:
1. Entender e documentar requisitos de negocio e tecnicos
2. Criar user stories claras e objetivas
3. Definir criterios de aceitacao mensuraveis
4. Gerar casos de teste abrangentes
5. Revisar entregas de codigo contra requisitos
6. Aprovar ou rejeitar entregas com feedback construtivo

Seja preciso, detalhista e focado em qualidade.
""")

    # ==========================================
    # LEVANTAMENTO DE REQUISITOS
    # ==========================================

    async def analyze_requirements(self, project_description: str) -> Requirement:
        """Analisa uma descricao de projeto e extrai requisitos estruturados"""
        self._req_counter += 1
        req_id = f"REQ_{self._req_counter}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        prompt = f"""Analise a seguinte descricao de projeto e extraia requisitos estruturados:

DESCRICAO DO PROJETO:
{project_description}

Retorne APENAS um JSON valido com a estrutura:
{{
    "title": "titulo curto do requisito principal",
    "description": "descricao detalhada do que deve ser feito",
    "user_story": "Como [tipo de usuario], eu quero [acao], para [beneficio]",
    "acceptance_criteria": [
        "criterio 1 - mensuravel e testavel",
        "criterio 2 - mensuravel e testavel"
    ],
    "priority": "low|medium|high|critical",
    "technical_specs": {{
        "suggested_language": "linguagem sugerida",
        "architecture": "arquitetura sugerida",
        "dependencies": ["dep1", "dep2"],
        "estimated_complexity": "simple|moderate|complex",
        "estimated_hours": 0
    }},
    "sub_requirements": [
        {{"title": "sub-req 1", "description": "desc"}},
        {{"title": "sub-req 2", "description": "desc"}}
    ]
}}"""

        response = await self.llm.generate(prompt, self._get_system_prompt())
        req_data = self._extract_json(response)

        requirement = Requirement(
            id=req_id,
            title=req_data.get("title", "Requisito sem titulo"),
            description=req_data.get("description", project_description),
            user_story=req_data.get("user_story", ""),
            acceptance_criteria=req_data.get("acceptance_criteria", []),
            priority=req_data.get("priority", "medium"),
            technical_specs=req_data.get("technical_specs", {}),
            status=RequirementStatus.ANALYZING,
            metadata={"sub_requirements": req_data.get("sub_requirements", [])}
        )

        self.requirements[req_id] = requirement
        return requirement

    async def refine_requirement(self, req_id: str, additional_info: str) -> Requirement:
        """Refina um requisito existente com informacoes adicionais"""
        req = self.requirements.get(req_id)
        if not req:
            raise ValueError(f"Requisito {req_id} nao encontrado")

        prompt = f"""Refine o seguinte requisito com as informacoes adicionais:

REQUISITO ATUAL:
Titulo: {req.title}
Descricao: {req.description}
User Story: {req.user_story}
Criterios de Aceitacao: {json.dumps(req.acceptance_criteria, ensure_ascii=False)}

INFORMACOES ADICIONAIS:
{additional_info}

Retorne um JSON com os campos atualizados:
{{
    "title": "titulo atualizado",
    "description": "descricao atualizada",
    "user_story": "user story atualizada",
    "acceptance_criteria": ["criterios atualizados"],
    "priority": "prioridade atualizada"
}}"""

        response = await self.llm.generate(prompt, self._get_system_prompt())
        update_data = self._extract_json(response)

        if update_data.get("title"):
            req.title = update_data["title"]
        if update_data.get("description"):
            req.description = update_data["description"]
        if update_data.get("user_story"):
            req.user_story = update_data["user_story"]
        if update_data.get("acceptance_criteria"):
            req.acceptance_criteria = update_data["acceptance_criteria"]
        if update_data.get("priority"):
            req.priority = update_data["priority"]

        req.updated_at = datetime.now()
        return req

    # ==========================================
    # GERACAO DE DOCUMENTACAO
    # ==========================================

    async def generate_documentation(self, req_id: str, doc_type: str = "full") -> str:
        """Gera documentacao para um requisito"""
        req = self.requirements.get(req_id)
        if not req:
            raise ValueError(f"Requisito {req_id} nao encontrado")

        doc_prompts = {
            "full": "Gere documentacao completa incluindo visao geral, requisitos funcionais, nao-funcionais, arquitetura e guia de implementacao",
            "technical": "Gere documentacao tecnica detalhada incluindo arquitetura, APIs, estrutura de dados e fluxos",
            "user": "Gere documentacao de usuario com guia de uso, exemplos e FAQ",
            "api": "Gere documentacao de API no formato OpenAPI/Swagger com endpoints, parametros e exemplos"
        }

        criteria_text = "\n".join(f"- {c}" for c in req.acceptance_criteria)
        prompt = f"""{doc_prompts.get(doc_type, doc_prompts["full"])}

REQUISITO:
ID: {req.id}
Titulo: {req.title}
Descricao: {req.description}
User Story: {req.user_story}
Criterios de Aceitacao:
{criteria_text}

Especificacoes Tecnicas:
{json.dumps(req.technical_specs, indent=2, ensure_ascii=False)}

Gere a documentacao em Markdown bem estruturado."""

        documentation = await self.llm.generate(prompt, self._get_system_prompt())

        req.documentation = documentation
        req.status = RequirementStatus.DOCUMENTED
        req.updated_at = datetime.now()

        return documentation

    async def generate_readme(self, req_id: str, project_name: str) -> str:
        """Gera README.md para o projeto"""
        req = self.requirements.get(req_id)
        if not req:
            raise ValueError(f"Requisito {req_id} nao encontrado")

        prompt = f"""Gere um README.md profissional para o projeto:

PROJETO: {project_name}
DESCRICAO: {req.description}
USER STORY: {req.user_story}

Inclua:
1. Titulo e badges
2. Descricao
3. Features
4. Instalacao
5. Uso com exemplos
6. API (se aplicavel)
7. Testes
8. Contribuicao
9. Licenca

Formato: Markdown bem estruturado"""

        return await self.llm.generate(prompt, self._get_system_prompt())

    # ==========================================
    # GERACAO DE CASOS DE TESTE
    # ==========================================

    async def generate_test_cases(self, req_id: str, language: str = "python") -> List[Dict]:
        """Gera casos de teste baseados nos requisitos"""
        req = self.requirements.get(req_id)
        if not req:
            raise ValueError(f"Requisito {req_id} nao encontrado")

        criteria_text = "\n".join(f"- {c}" for c in req.acceptance_criteria)
        prompt = f"""Gere casos de teste detalhados para o seguinte requisito:

REQUISITO:
Titulo: {req.title}
Descricao: {req.description}
Criterios de Aceitacao:
{criteria_text}

Linguagem alvo: {language}

Retorne um JSON com array de casos de teste:
{{
    "test_cases": [
        {{
            "id": "TC001",
            "name": "nome_do_teste",
            "description": "descricao do que esta sendo testado",
            "type": "unit|integration|e2e",
            "preconditions": ["pre-condicao 1"],
            "steps": ["passo 1", "passo 2"],
            "expected_result": "resultado esperado",
            "test_data": {{}},
            "code_template": "codigo de teste em {language}"
        }}
    ]
}}"""

        response = await self.llm.generate(prompt, SYSTEM_PROMPTS.get("tester", self._get_system_prompt()))
        test_data = self._extract_json(response)

        test_cases = test_data.get("test_cases", [])
        req.test_cases = test_cases
        req.status = RequirementStatus.TESTS_GENERATED
        req.updated_at = datetime.now()

        return test_cases

    async def generate_test_code(self, req_id: str, language: str = "python") -> str:
        """Gera codigo de testes executavel"""
        req = self.requirements.get(req_id)
        if not req:
            raise ValueError(f"Requisito {req_id} nao encontrado")

        if not req.test_cases:
            await self.generate_test_cases(req_id, language)

        prompt = f"""Gere codigo de testes executavel em {language} baseado nos casos de teste:

CASOS DE TESTE:
{json.dumps(req.test_cases, indent=2, ensure_ascii=False)}

REQUISITOS DO CODIGO:
1. Use o framework de testes padrao da linguagem
2. Inclua setup e teardown adequados
3. Cubra todos os casos de teste listados
4. Adicione assertions claras
5. Documente cada teste

Retorne APENAS o codigo de teste, pronto para executar."""

        return await self.llm.generate(prompt, SYSTEM_PROMPTS.get(f"{language}_expert", self._get_system_prompt()))

    # ==========================================
    # REVISAO E APROVACAO DE ENTREGAS
    # ==========================================

    async def review_delivery(
        self,
        task_id: str,
        requirement_id: str,
        agent_name: str,
        code: str,
        tests: str = ""
    ) -> DeliveryReview:
        """Revisa uma entrega de codigo contra os requisitos"""
        req = self.requirements.get(requirement_id)
        if not req:
            raise ValueError(f"Requisito {requirement_id} nao encontrado")

        self._review_counter += 1
        review_id = f"REV_{self._review_counter}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        review = DeliveryReview(
            id=review_id,
            task_id=task_id,
            requirement_id=requirement_id,
            agent_name=agent_name,
            code=code,
            tests=tests,
            status=DeliveryStatus.REVIEWING
        )

        criteria_text = "\n".join(f"- {c}" for c in req.acceptance_criteria)
        prompt = f"""Revise a entrega de codigo contra os requisitos especificados:

REQUISITO:
ID: {req.id}
Titulo: {req.title}
Descricao: {req.description}
Criterios de Aceitacao:
{criteria_text}

CODIGO ENTREGUE:
```
{code[:5000]}
```

TESTES:
```
{tests[:2000] if tests else "Nenhum teste fornecido"}
```

Analise e retorne um JSON:
{{
    "meets_requirements": true,
    "criteria_evaluation": [
        {{"criterion": "criterio 1", "met": true, "notes": "observacao"}}
    ],
    "code_quality": {{
        "score": 85,
        "strengths": ["pontos fortes"],
        "weaknesses": ["pontos fracos"]
    }},
    "issues_found": ["issue 1", "issue 2"],
    "suggestions": ["sugestao 1", "sugestao 2"],
    "test_coverage_adequate": true,
    "recommendation": "approve|needs_changes|reject",
    "review_summary": "resumo da revisao"
}}"""

        response = await self.llm.generate(prompt, self._get_system_prompt())
        review_data = self._extract_json(response)

        review.review_notes = review_data.get("review_summary", "")
        review.issues_found = review_data.get("issues_found", [])
        review.suggestions = review_data.get("suggestions", [])

        recommendation = review_data.get("recommendation", "needs_changes")
        if recommendation == "approve":
            review.status = DeliveryStatus.APPROVED
            review.approved_at = datetime.now()
        elif recommendation == "reject":
            review.status = DeliveryStatus.REJECTED
        else:
            review.status = DeliveryStatus.NEEDS_CHANGES

        self.reviews[review_id] = review
        return review

    async def approve_delivery(self, review_id: str, notes: str = "") -> DeliveryReview:
        """Aprova manualmente uma entrega"""
        review = self.reviews.get(review_id)
        if not review:
            raise ValueError(f"Review {review_id} nao encontrada")

        review.status = DeliveryStatus.APPROVED
        review.approved_at = datetime.now()
        if notes:
            review.review_notes += f"\n\nNota de aprovacao: {notes}"

        return review

    async def reject_delivery(self, review_id: str, reason: str) -> DeliveryReview:
        """Rejeita uma entrega com motivo"""
        review = self.reviews.get(review_id)
        if not review:
            raise ValueError(f"Review {review_id} nao encontrada")

        review.status = DeliveryStatus.REJECTED
        review.review_notes += f"\n\nMotivo da rejeicao: {reason}"
        review.issues_found.append(reason)

        return review

    async def request_changes(self, review_id: str, changes_required: List[str]) -> DeliveryReview:
        """Solicita mudancas em uma entrega"""
        review = self.reviews.get(review_id)
        if not review:
            raise ValueError(f"Review {review_id} nao encontrada")

        review.status = DeliveryStatus.NEEDS_CHANGES
        review.suggestions.extend(changes_required)

        return review

    # ==========================================
    # COLABORACAO COM OUTROS AGENTES
    # ==========================================

    async def prepare_task_for_programmer(self, req_id: str, language: str) -> Dict[str, Any]:
        """Prepara um pacote completo para o agente programador"""
        req = self.requirements.get(req_id)
        if not req:
            raise ValueError(f"Requisito {req_id} nao encontrado")

        if not req.documentation:
            await self.generate_documentation(req_id, "technical")

        if not req.test_cases:
            await self.generate_test_cases(req_id, language)

        test_code = await self.generate_test_code(req_id, language)

        criteria_text = "\n".join(f"- {c}" for c in req.acceptance_criteria)
        return {
            "requirement_id": req.id,
            "task_description": f"""{req.title}

{req.description}

USER STORY: {req.user_story}

CRITERIOS DE ACEITACAO:
{criteria_text}

ESPECIFICACOES TECNICAS:
{json.dumps(req.technical_specs, indent=2, ensure_ascii=False)}
""",
            "documentation": req.documentation,
            "test_cases": req.test_cases,
            "test_code": test_code,
            "language": language,
            "priority": req.priority
        }

    async def validate_agent_output(
        self,
        req_id: str,
        task: "Task",
        agent: "SpecializedAgent"
    ) -> Dict[str, Any]:
        """Valida a saida de um agente programador"""
        review = await self.review_delivery(
            task_id=task.id,
            requirement_id=req_id,
            agent_name=agent.name,
            code=task.code,
            tests=task.tests
        )

        result = {
            "review": review.to_dict(),
            "approved": review.status == DeliveryStatus.APPROVED,
            "can_proceed": review.status in [DeliveryStatus.APPROVED, DeliveryStatus.NEEDS_CHANGES]
        }

        if review.status == DeliveryStatus.NEEDS_CHANGES:
            result["feedback_for_agent"] = {
                "issues": review.issues_found,
                "suggestions": review.suggestions,
                "action": "Por favor, corrija os problemas identificados e resubmeta."
            }

        return result

    # ==========================================
    # UTILITARIOS
    # ==========================================

    def _extract_json(self, text: str) -> Dict:
        """Extrai JSON de uma resposta de texto"""
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
        return {}

    def get_requirement(self, req_id: str) -> Optional[Requirement]:
        """Obtem um requisito por ID"""
        return self.requirements.get(req_id)

    def get_review(self, review_id: str) -> Optional[DeliveryReview]:
        """Obtem uma review por ID"""
        return self.reviews.get(review_id)

    def list_requirements(self, status: RequirementStatus = None) -> List[Dict]:
        """Lista todos os requisitos, opcionalmente filtrados por status"""
        reqs = list(self.requirements.values())
        if status:
            reqs = [r for r in reqs if r.status == status]
        return [r.to_dict() for r in reqs]

    def list_reviews(self, status: DeliveryStatus = None) -> List[Dict]:
        """Lista todas as reviews, opcionalmente filtradas por status"""
        reviews = list(self.reviews.values())
        if status:
            reviews = [r for r in reviews if r.status == status]
        return [r.to_dict() for r in reviews]

    def get_status(self) -> Dict[str, Any]:
        """Retorna status do agente"""
        return {
            "name": self.name,
            "capabilities": self.capabilities,
            "total_requirements": len(self.requirements),
            "requirements_by_status": {
                status.value: len([r for r in self.requirements.values() if r.status == status])
                for status in RequirementStatus
            },
            "total_reviews": len(self.reviews),
            "reviews_by_status": {
                status.value: len([r for r in self.reviews.values() if r.status == status])
                for status in DeliveryStatus
            },
            "approved_deliveries": len([r for r in self.reviews.values() if r.status == DeliveryStatus.APPROVED]),
            "rejected_deliveries": len([r for r in self.reviews.values() if r.status == DeliveryStatus.REJECTED])
        }


# Singleton
_analyst_instance: Optional[RequirementsAnalystAgent] = None


def get_requirements_analyst() -> RequirementsAnalystAgent:
    """Retorna instancia singleton do RequirementsAnalystAgent"""
    global _analyst_instance
    if _analyst_instance is None:
        _analyst_instance = RequirementsAnalystAgent()
    return _analyst_instance
