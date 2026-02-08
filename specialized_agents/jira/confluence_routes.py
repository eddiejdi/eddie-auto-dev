"""
Rotas FastAPI para Confluence Cloud + draw.io integration.
Expõe a API do Confluence dentro do Eddie para agentes criarem/atualizarem documentação.
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .confluence_client import get_confluence_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jira/confluence", tags=["Confluence Cloud"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class CreatePageRequest(BaseModel):
    space_key: str = "EA"
    title: str
    body_html: str
    parent_id: Optional[str] = None


class UpdatePageRequest(BaseModel):
    title: str
    body_html: str


class SearchRequest(BaseModel):
    cql: str
    limit: int = 25


class AddLabelsRequest(BaseModel):
    labels: List[str]


class CommentRequest(BaseModel):
    body_html: str


class SyncDiagramRequest(BaseModel):
    space_key: str = "EA"
    page_title: str
    diagram_name: str
    diagram_xml: Optional[str] = None
    diagram_type: Optional[str] = None  # "architecture", "checkin_flow", "security"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _client():
    c = get_confluence_client()
    if not c.is_configured:
        raise HTTPException(503, "API_TOKEN não configurado — Confluence desabilitado")
    return c


# ═══════════════════════════ Health ═══════════════════════════════════════════

@router.get("/health")
async def confluence_health():
    """Verifica conexão com Confluence Cloud."""
    try:
        c = _client()
        spaces = await c.list_spaces(limit=5)
        return {
            "status": "connected",
            "url": c.base_url,
            "spaces": [{"key": s.get("key"), "name": s.get("name")} for s in spaces],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(503, f"Confluence inacessível: {e}")


# ═══════════════════════════ Spaces ══════════════════════════════════════════

@router.get("/spaces")
async def list_spaces():
    """Lista espaços Confluence."""
    return await _client().list_spaces()


@router.get("/spaces/{space_key}")
async def get_space(space_key: str):
    """Retorna detalhes de um espaço."""
    try:
        return await _client().get_space(space_key)
    except Exception as e:
        raise HTTPException(404, str(e))


# ═══════════════════════════ Pages ═══════════════════════════════════════════

@router.get("/pages/{page_id}")
async def get_page(page_id: str, expand: str = "body.storage,version"):
    """Retorna uma página por ID."""
    try:
        return await _client().get_page(page_id, expand=expand)
    except Exception as e:
        raise HTTPException(404, str(e))


@router.get("/spaces/{space_key}/pages")
async def get_space_pages(space_key: str, limit: int = 100):
    """Lista páginas de um espaço."""
    return await _client().get_space_pages(space_key, limit=limit)


@router.post("/pages")
async def create_page(req: CreatePageRequest):
    """Cria nova página no Confluence."""
    try:
        return await _client().create_page(
            space_key=req.space_key,
            title=req.title,
            body_html=req.body_html,
            parent_id=req.parent_id,
        )
    except Exception as e:
        raise HTTPException(400, str(e))


@router.put("/pages/{page_id}")
async def update_page(page_id: str, req: UpdatePageRequest):
    """Atualiza uma página existente."""
    try:
        return await _client().update_page(
            page_id=page_id,
            title=req.title,
            body_html=req.body_html,
        )
    except Exception as e:
        raise HTTPException(400, str(e))


@router.delete("/pages/{page_id}")
async def delete_page(page_id: str):
    """Deleta uma página."""
    try:
        return await _client().delete_page(page_id)
    except Exception as e:
        raise HTTPException(400, str(e))


@router.get("/pages/{page_id}/children")
async def get_child_pages(page_id: str):
    """Lista páginas filhas."""
    return await _client().get_child_pages(page_id)


# ═══════════════════════════ Search ══════════════════════════════════════════

@router.post("/search")
async def search_confluence(req: SearchRequest):
    """Busca no Confluence via CQL."""
    try:
        return await _client().search(req.cql, req.limit)
    except Exception as e:
        raise HTTPException(400, str(e))


# ═══════════════════════════ Labels ══════════════════════════════════════════

@router.get("/pages/{page_id}/labels")
async def get_labels(page_id: str):
    """Lista labels de uma página."""
    return await _client().get_labels(page_id)


@router.post("/pages/{page_id}/labels")
async def add_labels(page_id: str, req: AddLabelsRequest):
    """Adiciona labels a uma página."""
    return await _client().add_labels(page_id, req.labels)


# ═══════════════════════════ Comments ═════════════════════════════════════════

@router.get("/pages/{page_id}/comments")
async def get_comments(page_id: str):
    """Lista comentários de uma página."""
    return await _client().get_comments(page_id)


@router.post("/pages/{page_id}/comments")
async def add_comment(page_id: str, req: CommentRequest):
    """Adiciona comentário a uma página."""
    return await _client().add_comment(page_id, req.body_html)


# ═══════════════════════════ Attachments ══════════════════════════════════════

@router.get("/pages/{page_id}/attachments")
async def get_attachments(page_id: str):
    """Lista attachments de uma página."""
    return await _client().get_attachments(page_id)


# ═══════════════════════════ draw.io Diagrams ═════════════════════════════════

@router.post("/diagrams/sync")
async def sync_diagram(req: SyncDiagramRequest):
    """Sincroniza um diagrama draw.io com uma página Confluence.
    
    Se diagram_xml não for passado, usa templates pré-construídos.
    Tipos disponíveis: architecture, checkin_flow, security
    """
    from .drawio import (
        sync_drawio_to_confluence,
        architecture_diagram,
        checkin_flow_diagram,
        security_layers_diagram,
    )

    # Resolver XML do diagrama
    diagram_xml = req.diagram_xml
    if not diagram_xml and req.diagram_type:
        generators = {
            "architecture": architecture_diagram,
            "checkin_flow": checkin_flow_diagram,
            "security": security_layers_diagram,
        }
        gen = generators.get(req.diagram_type)
        if not gen:
            raise HTTPException(400, f"Tipo desconhecido: {req.diagram_type}. "
                                f"Disponíveis: {list(generators.keys())}")
        diagram_xml = gen()

    if not diagram_xml:
        raise HTTPException(400, "Forneça diagram_xml ou diagram_type")

    try:
        result = await sync_drawio_to_confluence(
            space_key=req.space_key,
            page_title=req.page_title,
            diagram_name=req.diagram_name,
            diagram_xml=diagram_xml,
        )
        return result
    except Exception as e:
        raise HTTPException(400, str(e))


@router.get("/diagrams/templates")
async def list_diagram_templates():
    """Lista templates de diagramas draw.io disponíveis."""
    return {
        "templates": [
            {
                "type": "architecture",
                "name": "Arquitetura do Sistema",
                "description": "Diagrama de componentes: App → API → Services → DB → Analytics",
            },
            {
                "type": "checkin_flow",
                "name": "Fluxo de Check-in",
                "description": "Fluxo completo: participante → validação → persistência → dashboard",
            },
            {
                "type": "security",
                "name": "Camadas de Segurança",
                "description": "7 camadas de validação: Auth → Device → Geo → QR → BLE → Risk → Rate",
            },
        ]
    }


@router.post("/diagrams/generate")
async def generate_diagram_xml(req: SyncDiagramRequest):
    """Gera o XML draw.io sem publicar no Confluence. Útil para preview."""
    from .drawio import (
        architecture_diagram,
        checkin_flow_diagram,
        security_layers_diagram,
        embed_drawio,
    )

    generators = {
        "architecture": architecture_diagram,
        "checkin_flow": checkin_flow_diagram,
        "security": security_layers_diagram,
    }

    if req.diagram_xml:
        xml = req.diagram_xml
    elif req.diagram_type and req.diagram_type in generators:
        xml = generators[req.diagram_type]()
    else:
        raise HTTPException(400, f"Forneça diagram_xml ou diagram_type válido: {list(generators.keys())}")

    return {
        "diagram_name": req.diagram_name,
        "diagram_type": req.diagram_type,
        "xml": xml,
        "confluence_macro": embed_drawio(req.diagram_name, xml),
    }


# ═══════════════════════════ Bulk Sync ════════════════════════════════════════

@router.post("/sync-all/{space_key}")
async def sync_all_docs(space_key: str = "EA"):
    """Sincroniza todos os diagramas draw.io pré-construídos para o espaço.
    
    Cria/atualiza 3 páginas com diagramas:
    - Arquitetura do Sistema (architecture)
    - Fluxo de Check-in (checkin_flow)
    - Camadas de Segurança (security)
    """
    from .drawio import (
        sync_drawio_to_confluence,
        architecture_diagram,
        checkin_flow_diagram,
        security_layers_diagram,
    )

    results = []
    diagrams = [
        ("Arquitetura do Sistema", "estou-aqui-architecture", architecture_diagram),
        ("Fluxo de Check-in", "estou-aqui-checkin-flow", checkin_flow_diagram),
        ("Segurança e Integridade", "estou-aqui-security", security_layers_diagram),
    ]

    for title, name, gen_func in diagrams:
        try:
            result = await sync_drawio_to_confluence(
                space_key=space_key,
                page_title=title,
                diagram_name=name,
                diagram_xml=gen_func(),
            )
            results.append(result)
        except Exception as e:
            results.append({"error": str(e), "title": title})

    return {
        "synced": len([r for r in results if "error" not in r]),
        "errors": len([r for r in results if "error" in r]),
        "results": results,
    }
