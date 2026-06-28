#!/usr/bin/env python3
"""
Agente Wiki — publica e evolui documentação no Wiki.js via Copilot Model Router.

Recebe input mínimo do chamador (tópico + texto bruto) e usa o CopilotModelRouter
(GPU0 → GPU1 → cloud) para expandir, estruturar ou mesclar conteúdo em documentação
markdown completa, depois publica diretamente no Wiki.js via GraphQL.

Endpoints:
  POST /wiki/publish  — expande texto via copilot e publica nova página
  POST /wiki/evolve   — busca página existente, mescla com novo conteúdo via copilot
  POST /wiki/raw      — publica markdown sem passar pelo copilot
  GET  /wiki/health
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from specialized_agents.copilot_model_router import (
    classify_request_complexity,
    get_active_model_info,
    get_copilot_router,
)
from specialized_agents.wiki_client import WikiJsClient
from specialized_agents.wiki_refactor import (
    WikiRefactorRequest,
    WikiRefactorResponse,
    WikiRefactorSkill,
)

logger = logging.getLogger(__name__)

WIKI_URL = os.getenv("WIKI_URL", "http://192.168.15.2:3009/graphql")
WIKI_TOKEN = os.getenv("WIKI_TOKEN", "")
WIKI_LOCALE = os.getenv("WIKI_LOCALE", "en")
COPILOT_TIMEOUT = int(os.getenv("WIKI_COPILOT_TIMEOUT", "120"))

# ─────────────────────────────────────────────────────────────────────────────
# Prompts do sistema
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_EXPAND = """Você é um especialista em documentação técnica de infraestrutura homelab.
Dado um tópico e notas brutas, escreva uma página wiki completa em Markdown:

- Título H1 no início
- Seções bem definidas com H2/H3
- Tabelas para comparações e configurações
- Blocos de código com linguagem (bash, yaml, python, etc.)
- Diagrama mermaid quando a arquitetura se beneficiar (use ```mermaid)
- Tom técnico, objetivo, PT-BR
- Seção "Histórico" ao final com a data de hoje
- Não invente dados técnicos — use apenas o que foi fornecido nas notas
- Retorne APENAS o markdown, sem explicações adicionais"""

_SYSTEM_EVOLVE = """Você é um especialista em documentação técnica de infraestrutura homelab.
Você receberá o conteúdo ATUAL de uma página wiki e NOVAS INFORMAÇÕES para integrar.
Evolua o documento:

- Mantenha o conteúdo existente correto e não o remova
- Integre as novas informações nas seções relevantes ou crie novas seções
- Atualize tabelas e listas com os novos dados
- Atualize ou adicione diagramas mermaid se a arquitetura mudou
- Adicione entrada na seção "Histórico" com a data de hoje
- Retorne APENAS o markdown completo evoluído, sem explicações adicionais"""


# ─────────────────────────────────────────────────────────────────────────────
# Modelos Pydantic
# ─────────────────────────────────────────────────────────────────────────────

class WikiPublishRequest(BaseModel):
    """Payload mínimo para publicar nova página via Ollama."""

    topic: str = Field(
        min_length=3,
        max_length=200,
        description="Título/tópico da página",
    )
    raw_text: str = Field(
        min_length=10,
        description="Notas brutas ou texto técnico a documentar",
    )
    wiki_path: str = Field(
        min_length=3,
        max_length=300,
        description="Caminho na wiki (ex: homelab/network/qos)",
    )
    tags: list[str] = Field(default_factory=list)
    locale: str | None = Field(
        default=None,
        description="Locale da página na wiki (ex: pt, en)",
    )
    skip_ollama: bool = Field(
        default=False,
        description="Publicar raw_text diretamente sem expandir via copilot",
    )


class WikiEvolveRequest(BaseModel):
    """Payload mínimo para evoluir página existente via Ollama."""

    wiki_path: str = Field(
        min_length=3,
        max_length=300,
        description="Caminho da página existente na wiki",
    )
    new_info: str = Field(
        min_length=10,
        description="Novas informações a integrar no documento existente",
    )
    tags: list[str] = Field(default_factory=list)
    locale: str | None = Field(
        default=None,
        description="Locale da página na wiki (ex: pt, en)",
    )


class WikiResponse(BaseModel):
    """Resposta padrão do agente wiki."""

    ok: bool
    page_id: int | None = None
    wiki_path: str | None = None
    model_used: str | None = None
    gpu: str | None = None
    message: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# WikiAgent
# ─────────────────────────────────────────────────────────────────────────────

class WikiAgent:
    """
    Agente que usa CopilotModelRouter para gerar/evoluir documentação e publicar no Wiki.js.

    Fluxo publish:
        raw_text → Copilot expand (GPU0→GPU1→cloud) → GraphQL create/update

    Fluxo evolve:
        wiki_path → GraphQL fetch → Copilot evolve(existing + new_info) → GraphQL update
    """

    def __init__(self) -> None:
        self._wiki_url = WIKI_URL
        self._token = WIKI_TOKEN
        self._locale = WIKI_LOCALE
        self._copilot = get_copilot_router()
        self._client = WikiJsClient(
            wiki_url=self._wiki_url,
            token=self._token,
            default_locale=self._locale,
        )
        self._refactor_skill = WikiRefactorSkill(self._client)
        self._skills = {
            "publish": self.publish,
            "evolve": self.evolve,
            "refactor_wiki": self.refactor_wiki,
        }

    def _effective_locale(self, locale: str | None = None) -> str:
        """Resolve o locale da operação com fallback para o padrão do agent."""
        return self._client.effective_locale(locale)

    # ── Copilot Model Router ──────────────────────────────────────────────────

    async def _copilot_generate(
        self, system: str, user: str, complexity: str = "MODERATE"
    ) -> tuple[str, str, str]:
        """
        Gera conteúdo via CopilotModelRouter (GPU0 → GPU1 → cloud).

        Returns:
            (content, model_used, gpu_label)
        """
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        try:
            data = await self._copilot.proxy_chat_completion(
                messages=messages,
                temperature=0.3,
                max_tokens=8192,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Copilot router indisponível: {exc}",
            ) from exc

        content: str = (
            data.get("choices", [{}])[0].get("message", {}).get("content", "")
        )
        if not content.strip():
            raise HTTPException(
                status_code=502,
                detail="Copilot router retornou resposta vazia",
            )

        model_used: str = data.get("model", "unknown")
        # CopilotModelRouter não retorna gpu no payload; inferir pelo provider
        provider = data.get("provider", data.get("object", ""))
        gpu_label = "CLOUD" if provider == "openai_compatible" else "GPU"
        logger.info("Copilot %s/%s gerou %d chars", gpu_label, model_used, len(content))
        return content, model_used, gpu_label

    # ── Wiki.js GraphQL ───────────────────────────────────────────────────────

    def _graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        """Executa query/mutation GraphQL no Wiki.js."""
        return self._client.graphql(query, variables)

    def _get_page(
        self,
        wiki_path: str,
        locale: str | None = None,
    ) -> dict[str, Any] | None:
        """Busca página pelo path. Retorna dict ou None se não existir."""
        query = """
        query GetPage($path: String!, $locale: String!) {
          pages {
            singleByPath(path: $path, locale: $locale) {
              id path title content updatedAt
            }
          }
        }"""
        result = self._graphql(
            query,
            {"path": wiki_path, "locale": self._effective_locale(locale)},
        )
        if result.get("errors"):
            logger.warning("Erro ao buscar página %s: %s", wiki_path, result["errors"])
            return None
        return result.get("data", {}).get("pages", {}).get("singleByPath")

    def _create_page(
        self,
        wiki_path: str,
        title: str,
        content: str,
        tags: list[str],
        locale: str | None = None,
    ) -> dict[str, Any]:
        """Cria nova página no Wiki.js."""
        mutation = """
        mutation CreatePage(
          $content: String!, $path: String!, $title: String!,
          $locale: String!, $tags: [String]!
        ) {
          pages {
            create(
              content: $content description: "" editor: "markdown"
              isPublished: true isPrivate: false
              locale: $locale path: $path tags: $tags title: $title
            ) {
              responseResult { succeeded errorCode message }
              page { id path }
            }
          }
        }"""
        result = self._graphql(
            mutation,
            {
                "content": content,
                "path": wiki_path,
                "title": title,
                "locale": self._effective_locale(locale),
                "tags": tags,
            },
        )
        if result.get("errors"):
            raise HTTPException(status_code=502, detail=str(result["errors"]))
        rr = result["data"]["pages"]["create"]["responseResult"]
        if not rr["succeeded"]:
            raise HTTPException(
                status_code=400,
                detail=f"Wiki create falhou ({rr['errorCode']}): {rr['message']}",
            )
        return result["data"]["pages"]["create"]["page"]

    def _update_page(
        self,
        page_id: int,
        wiki_path: str,
        title: str,
        content: str,
        tags: list[str],
        locale: str | None = None,
    ) -> dict[str, Any]:
        """Atualiza página existente no Wiki.js."""
        mutation = """
        mutation UpdatePage(
          $id: Int!, $content: String!, $path: String!, $title: String!,
          $locale: String!, $tags: [String]!
        ) {
          pages {
            update(
              id: $id content: $content description: "" editor: "markdown"
              isPublished: true isPrivate: false
              locale: $locale path: $path tags: $tags title: $title
            ) {
              responseResult { succeeded errorCode message }
              page { id path updatedAt }
            }
          }
        }"""
        result = self._graphql(
            mutation,
            {
                "id": page_id,
                "content": content,
                "path": wiki_path,
                "title": title,
                "locale": self._effective_locale(locale),
                "tags": tags,
            },
        )
        if result.get("errors"):
            raise HTTPException(status_code=502, detail=str(result["errors"]))
        rr = result["data"]["pages"]["update"]["responseResult"]
        if not rr["succeeded"]:
            raise HTTPException(
                status_code=400,
                detail=f"Wiki update falhou ({rr['errorCode']}): {rr['message']}",
            )
        return result["data"]["pages"]["update"]["page"]

    def _upsert_page(
        self,
        wiki_path: str,
        title: str,
        content: str,
        tags: list[str],
        locale: str | None = None,
    ) -> tuple[dict[str, Any], str]:
        """
        Cria ou atualiza dependendo se página já existe.

        Returns:
            (page_dict, operation) onde operation é 'created' ou 'updated'
        """
        existing = self._get_page(wiki_path, locale=locale)
        if existing:
            page = self._update_page(
                existing["id"], wiki_path, title, content, tags, locale
            )
            return page, "updated"
        page = self._create_page(wiki_path, title, content, tags, locale)
        return page, "created"

    def _rebuild_index(self) -> None:
        """Reconstrói o índice agrupando todas as páginas por prefixo de path.

        Chamado automaticamente após publish/evolve. Falha silenciosa para não
        interromper o fluxo principal caso o índice não seja crítico.
        """
        try:
            query = "{ pages { list(orderBy: TITLE) { id path title description } } }"
            result = self._graphql(query, {})
            pages = [
                p for p in result.get("data", {}).get("pages", {}).get("list", [])
                if p["path"] != "index"
            ]

            groups: dict = defaultdict(list)
            for p in pages:
                seg = p["path"].split("/")[0]
                groups[seg].append(p)

            lines = [
                "# Índice de Páginas",
                "",
                "_Atualizado automaticamente. Não editar manualmente._",
                "",
            ]
            for grp in sorted(groups.keys()):
                lines.append(f"## {grp}")
                for p in sorted(groups[grp], key=lambda x: x["title"]):
                    desc = f" — {p['description']}" if p.get("description") else ""
                    lines.append(f"- [{p['title']}](/{p['path']}){desc}")
                lines.append("")

            self._upsert_page(
                wiki_path="index",
                title="Índice de Páginas",
                content="\n".join(lines),
                tags=["index", "auto-generated"],
            )
            logger.info("Índice reconstruído: %d páginas", len(pages))
        except Exception as exc:
            logger.warning("Falha ao reconstruir índice: %s", exc)

    # ── Lógica principal ──────────────────────────────────────────────────────

    async def publish(self, req: WikiPublishRequest) -> WikiResponse:
        """
        Expande raw_text via CopilotModelRouter e publica/atualiza página na wiki.
        Se skip_ollama=True publica raw_text diretamente.
        """
        model_used: str | None = None
        gpu_label: str | None = None

        if req.skip_ollama:
            final_content = req.raw_text
        else:
            user_prompt = f"Tópico: {req.topic}\n\nNotas brutas:\n{req.raw_text}"
            complexity = classify_request_complexity([{"role": "user", "content": user_prompt}])
            final_content, model_used, gpu_label = await self._copilot_generate(
                _SYSTEM_EXPAND, user_prompt, complexity=complexity
            )

        page, operation = self._upsert_page(
            wiki_path=req.wiki_path,
            title=req.topic,
            content=final_content,
            tags=req.tags,
            locale=req.locale,
        )

        logger.info("Wiki %s: %s (id=%s)", operation, req.wiki_path, page["id"])
        if req.wiki_path != "index":
            self._rebuild_index()
        return WikiResponse(
            ok=True,
            page_id=page["id"],
            wiki_path=page["path"],
            model_used=model_used,
            gpu=gpu_label,
            message=f"Página {operation} com sucesso",
        )

    async def evolve(self, req: WikiEvolveRequest) -> WikiResponse:
        """
        Busca página existente, mescla com new_info via CopilotModelRouter e atualiza na wiki.
        """
        existing = self._get_page(req.wiki_path, locale=req.locale)
        if not existing:
            raise HTTPException(
                status_code=404,
                detail=f"Página não encontrada: {req.wiki_path}",
            )

        current_content = existing.get("content", "")
        current_title = existing.get("title", req.wiki_path.split("/")[-1])

        user_prompt = (
            f"=== CONTEÚDO ATUAL DA WIKI ===\n{current_content}\n\n"
            f"=== NOVAS INFORMAÇÕES PARA INTEGRAR ===\n{req.new_info}"
        )

        complexity = classify_request_complexity([{"role": "user", "content": user_prompt}])
        evolved_content, model_used, gpu_label = await self._copilot_generate(
            _SYSTEM_EVOLVE, user_prompt, complexity=complexity
        )
        logger.info(
            "Página evoluída via Copilot %s/%s: %d → %d chars",
            gpu_label, model_used, len(current_content), len(evolved_content),
        )

        page = self._update_page(
            page_id=existing["id"],
            wiki_path=req.wiki_path,
            title=current_title,
            content=evolved_content,
            tags=req.tags or [],
            locale=req.locale,
        )

        if req.wiki_path != "index":
            self._rebuild_index()
        return WikiResponse(
            ok=True,
            page_id=page["id"],
            wiki_path=page["path"],
            model_used=model_used,
            gpu=gpu_label,
            message="Página evoluída com sucesso",
        )

    async def refactor_wiki(self, req: WikiRefactorRequest) -> WikiRefactorResponse:
        """Executa a skill interna de refactor da wiki."""
        return await self._refactor_skill.run(req)

    async def execute_skill(self, skill_name: str, payload: Any) -> Any:
        skill = self._skills.get(skill_name)
        if skill is None:
            raise HTTPException(status_code=404, detail=f"Skill não encontrada: {skill_name}")
        return await skill(payload)


# ─────────────────────────────────────────────────────────────────────────────
# Singleton e router FastAPI
# ─────────────────────────────────────────────────────────────────────────────

_agent: WikiAgent | None = None


def get_wiki_agent():
    """Retorna instância singleton do WikiAgent (v1 ou v2 conforme WIKI_AGENT_VERSION)."""
    global _agent
    if os.getenv("WIKI_AGENT_VERSION", "v1") == "v2":
        from specialized_agents.wiki_agent_v2 import get_wiki_agent_v2
        return get_wiki_agent_v2()
    if _agent is None:
        _agent = WikiAgent()
    return _agent


router = APIRouter()


@router.get("/health")
async def wiki_health() -> dict[str, Any]:
    """Health check do wiki agent com status do copilot router."""
    model_info = await get_active_model_info()
    return {
        "status": "ok",
        "wiki_url": WIKI_URL,
        "copilot_router": model_info.get("status", "unknown"),
        "active_model": model_info.get("model"),
        "active_gpu": model_info.get("gpu"),
        "provider": model_info.get("provider"),
    }


@router.post("/publish", response_model=WikiResponse)
async def wiki_publish(req: WikiPublishRequest) -> WikiResponse:
    """
    Expande raw_text via CopilotModelRouter e publica/atualiza página na wiki.

    Input mínimo do caller: topic + raw_text + wiki_path.
    O copilot gera documentação estruturada com tabelas e diagramas mermaid.
    """
    return await get_wiki_agent().publish(req)


@router.post("/evolve", response_model=WikiResponse)
async def wiki_evolve(req: WikiEvolveRequest) -> WikiResponse:
    """
    Busca página existente na wiki, usa CopilotModelRouter para mesclar new_info
    com o conteúdo atual e atualiza a página.

    Input mínimo do caller: wiki_path + new_info.
    """
    return await get_wiki_agent().evolve(req)


@router.post("/raw", response_model=WikiResponse)
async def wiki_raw(req: WikiPublishRequest) -> WikiResponse:
    """
    Publica markdown diretamente sem passar pelo copilot.
    Útil quando o caller já tem o conteúdo final formatado.
    """
    req.skip_ollama = True
    return await get_wiki_agent().publish(req)


@router.post("/refactor", response_model=WikiRefactorResponse)
async def wiki_refactor(req: WikiRefactorRequest) -> WikiRefactorResponse:
    """Refatora a árvore da wiki a partir do inventário vivo e do repositório."""
    return await get_wiki_agent().execute_skill("refactor_wiki", req)
