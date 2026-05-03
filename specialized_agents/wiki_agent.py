#!/usr/bin/env python3
"""
Agente Wiki — publica e evolui documentação no Wiki.js usando Ollama local.

Recebe input mínimo do chamador (tópico + texto bruto) e usa Ollama (GPU0→GPU1)
para expandir, estruturar ou mesclar conteúdo em documentação markdown completa,
depois publica diretamente no Wiki.js via GraphQL.

Endpoints:
  POST /wiki/publish  — expande texto via Ollama e publica nova página
  POST /wiki/evolve   — busca página existente, mescla com novo conteúdo via Ollama
  POST /wiki/raw      — publica markdown sem passar por Ollama
  GET  /wiki/health
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

import aiohttp
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from specialized_agents.config import LLM_CONFIG, LLM_GPU1_CONFIG

logger = logging.getLogger(__name__)

WIKI_URL = os.getenv("WIKI_URL", "http://192.168.15.2:3009/graphql")
WIKI_TOKEN = os.getenv(
    "WIKI_TOKEN",
    # Token copilot-agent (id=3) — válido até 2027, revogável via Wiki.js admin
    "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcGkiOjMsImdycCI6MSwiaWF0IjoxNzczNTUzNDU0LCJleHAiOjE4MDUwODk0NTQsImF1ZCI6InVybjp3aWtpLmpzIiwiaXNzIjoidXJuOndpa2kuanMifQ.fLRuaCR_P5X8__vQpYtMW3ASGN0Bojjm8T9rQ0Sw8rISr_hP2MJUXV3Zb8kqnjjPrXFbk8kEYUqeMlvGlEDILbf-sqAs8QxqTlwpIKbBpEqo2Z3fpzupYhcc3C5YXbZ4YToX1yDBV_9-l3Om7M80WN8HqvhSfE-TKqvRn9fJgtxRuSKBEiPrpeTWqqI2I1YzBM5sYl9sDhBfEqyQql7uzFXecoSyOxd3aQLlw9AmHghHI-2Llst-dy2vCYRC6de-XTucwEG0WlbmnhlwbQenNnfS7L-SshD6srl6cE5sG0ltMgbQipiqJ-_UH6Q0iUTjZp85QnBvYp8VUCFGyU8sEA",
)
WIKI_LOCALE = os.getenv("WIKI_LOCALE", "en")

OLLAMA_GPU0: str = LLM_CONFIG.get("base_url", "http://192.168.15.2:11434")
OLLAMA_GPU1: str = LLM_GPU1_CONFIG.get("base_url", "http://192.168.15.2:11435")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "shared-coder")
OLLAMA_TIMEOUT = int(os.getenv("WIKI_OLLAMA_TIMEOUT", "120"))

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
    skip_ollama: bool = Field(
        default=False,
        description="Publicar raw_text diretamente sem expandir via Ollama",
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
    Agente que usa Ollama para gerar/evoluir documentação e publicar no Wiki.js.

    Fluxo publish:
        raw_text → Ollama expand → GraphQL create/update

    Fluxo evolve:
        wiki_path → GraphQL fetch → Ollama evolve(existing + new_info) → GraphQL update
    """

    def __init__(self) -> None:
        self._gpu0 = OLLAMA_GPU0
        self._gpu1 = OLLAMA_GPU1
        self._model = OLLAMA_MODEL
        self._wiki_url = WIKI_URL
        self._token = WIKI_TOKEN
        self._locale = WIKI_LOCALE

    # ── Ollama ────────────────────────────────────────────────────────────────

    async def _ollama_reachable(self, base_url: str) -> bool:
        """Verifica disponibilidade do endpoint Ollama."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=4),
                ) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def _pick_ollama(self) -> tuple[str, str]:
        """
        Retorna (base_url, gpu_label) do primeiro Ollama disponível.
        Ordem: GPU0 → GPU1.
        """
        if await self._ollama_reachable(self._gpu0):
            return self._gpu0, "GPU0"
        if await self._ollama_reachable(self._gpu1):
            return self._gpu1, "GPU1"
        raise HTTPException(
            status_code=503,
            detail="Nenhum Ollama disponível (GPU0 e GPU1 offline)",
        )

    async def _resolve_model(self, base_url: str) -> str:
        """
        Retorna o modelo a usar: preferência OLLAMA_MODEL,
        fallback para o primeiro disponível na instância.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=4),
                ) as resp:
                    if resp.status != 200:
                        return self._model
                    data = await resp.json()
            available = [m["name"] for m in data.get("models", [])]
            if not available:
                return self._model
            if self._model in available:
                return self._model
            for name in available:
                if "coder" in name or "qwen" in name or "llama" in name:
                    return name
            return available[0]
        except Exception:
            return self._model

    async def _ollama_generate(self, system: str, user: str) -> tuple[str, str, str]:
        """
        Chama Ollama com prompt system+user.

        Returns:
            (content, model_used, gpu_label)
        """
        base_url, gpu = await self._pick_ollama()
        model = await self._resolve_model(base_url)

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 8192},
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/api/chat",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=OLLAMA_TIMEOUT),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        raise HTTPException(
                            status_code=502,
                            detail=f"Ollama {gpu} retornou {resp.status}: {body[:200]}",
                        )
                    data = await resp.json()
        except HTTPException:
            raise
        except aiohttp.ClientError as exc:
            raise HTTPException(
                status_code=503, detail=f"Erro de conexão Ollama {gpu}: {exc}"
            ) from exc

        content: str = data.get("message", {}).get("content", "")
        if not content.strip():
            raise HTTPException(
                status_code=502,
                detail=f"Ollama {gpu} retornou resposta vazia",
            )
        logger.info("Ollama %s/%s gerou %d chars", gpu, model, len(content))
        return content, model, gpu

    # ── Wiki.js GraphQL ───────────────────────────────────────────────────────

    def _graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        """Executa query/mutation GraphQL no Wiki.js."""
        payload = json.dumps({"query": query, "variables": variables}).encode()
        req = urllib.request.Request(
            self._wiki_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._token}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            raise HTTPException(
                status_code=exc.code,
                detail=f"Wiki.js HTTP {exc.code}: {exc.read().decode()[:300]}",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Erro de conexão com Wiki.js: {exc}",
            ) from exc

    def _get_page(self, wiki_path: str) -> dict[str, Any] | None:
        """Busca página pelo path. Retorna dict ou None se não existir."""
        query = """
        query GetPage($path: String!, $locale: String!) {
          pages {
            singleByPath(path: $path, locale: $locale) {
              id path title content updatedAt
            }
          }
        }"""
        result = self._graphql(query, {"path": wiki_path, "locale": self._locale})
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
                "locale": self._locale,
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
                "locale": self._locale,
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
    ) -> tuple[dict[str, Any], str]:
        """
        Cria ou atualiza dependendo se página já existe.

        Returns:
            (page_dict, operation) onde operation é 'created' ou 'updated'
        """
        existing = self._get_page(wiki_path)
        if existing:
            page = self._update_page(
                existing["id"], wiki_path, title, content, tags
            )
            return page, "updated"
        page = self._create_page(wiki_path, title, content, tags)
        return page, "created"

    # ── Lógica principal ──────────────────────────────────────────────────────

    async def publish(self, req: WikiPublishRequest) -> WikiResponse:
        """
        Expande raw_text via Ollama e publica/atualiza página na wiki.
        Se skip_ollama=True publica raw_text diretamente.
        """
        model_used: str | None = None
        gpu_label: str | None = None

        if req.skip_ollama:
            final_content = req.raw_text
        else:
            user_prompt = f"Tópico: {req.topic}\n\nNotas brutas:\n{req.raw_text}"
            final_content, model_used, gpu_label = await self._ollama_generate(
                _SYSTEM_EXPAND, user_prompt
            )

        page, operation = self._upsert_page(
            wiki_path=req.wiki_path,
            title=req.topic,
            content=final_content,
            tags=req.tags,
        )

        logger.info("Wiki %s: %s (id=%s)", operation, req.wiki_path, page["id"])
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
        Busca página existente, mescla com new_info via Ollama e atualiza na wiki.
        """
        existing = self._get_page(req.wiki_path)
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

        evolved_content, model_used, gpu_label = await self._ollama_generate(
            _SYSTEM_EVOLVE, user_prompt
        )
        logger.info(
            "Página evoluída via Ollama %s/%s: %d → %d chars",
            gpu_label, model_used, len(current_content), len(evolved_content),
        )

        page = self._update_page(
            page_id=existing["id"],
            wiki_path=req.wiki_path,
            title=current_title,
            content=evolved_content,
            tags=req.tags or [],
        )

        return WikiResponse(
            ok=True,
            page_id=page["id"],
            wiki_path=page["path"],
            model_used=model_used,
            gpu=gpu_label,
            message="Página evoluída com sucesso",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Singleton e router FastAPI
# ─────────────────────────────────────────────────────────────────────────────

_agent: WikiAgent | None = None


def get_wiki_agent() -> WikiAgent:
    """Retorna instância singleton do WikiAgent."""
    global _agent
    if _agent is None:
        _agent = WikiAgent()
    return _agent


router = APIRouter()


@router.get("/health")
async def wiki_health() -> dict[str, Any]:
    """Health check do wiki agent com status das GPUs."""
    agent = get_wiki_agent()
    gpu0_ok = await agent._ollama_reachable(OLLAMA_GPU0)
    gpu1_ok = await agent._ollama_reachable(OLLAMA_GPU1)
    return {
        "status": "ok",
        "wiki_url": WIKI_URL,
        "ollama_gpu0": "up" if gpu0_ok else "down",
        "ollama_gpu1": "up" if gpu1_ok else "down",
        "default_model": OLLAMA_MODEL,
    }


@router.post("/publish", response_model=WikiResponse)
async def wiki_publish(req: WikiPublishRequest) -> WikiResponse:
    """
    Expande raw_text via Ollama e publica/atualiza página na wiki.

    Input mínimo do caller: topic + raw_text + wiki_path.
    O Ollama gera documentação estruturada com tabelas e diagramas mermaid.
    """
    return await get_wiki_agent().publish(req)


@router.post("/evolve", response_model=WikiResponse)
async def wiki_evolve(req: WikiEvolveRequest) -> WikiResponse:
    """
    Busca página existente na wiki, usa Ollama para mesclar new_info
    com o conteúdo atual e atualiza a página.

    Input mínimo do caller: wiki_path + new_info.
    """
    return await get_wiki_agent().evolve(req)


@router.post("/raw", response_model=WikiResponse)
async def wiki_raw(req: WikiPublishRequest) -> WikiResponse:
    """
    Publica markdown diretamente sem passar por Ollama.
    Útil quando o caller já tem o conteúdo final formatado.
    """
    req.skip_ollama = True
    return await get_wiki_agent().publish(req)
