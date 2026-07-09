"""Specialized Agents API - FastAPI entry point.

Centraliza todos os routers de agentes especializados:
- Conube (automação/banking)
- RAG (conhecimento)
- Agentes (status/health)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class NextcloudUserCreateRequest(BaseModel):
    """Payload para provisionamento de acesso ao Nextcloud via Authentik."""

    username: str = Field(min_length=3, max_length=64)
    email: str = Field(min_length=5, max_length=200)
    full_name: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=8, max_length=200)
    extra_groups: list[str] = Field(default_factory=list)
    manager_username: str | None = Field(default=None, max_length=200)
    storage_quota_mb: int = Field(default=100000, ge=1000, le=1000000)
    send_welcome_email: bool = True


class OrchestratorImageRequest(BaseModel):
    """Payload unificado para orquestração de geração de imagem."""

    prompt: str = Field(min_length=1, max_length=4000)
    model: str | None = Field(default=None, max_length=300)
    negative_prompt: str | None = Field(default=None, max_length=2000)
    width: int = Field(default=1024, ge=256, le=1536)
    height: int = Field(default=1024, ge=256, le=1536)
    steps: int = Field(default=30, ge=1, le=80)
    guidance_scale: float = Field(default=7.0, ge=1.0, le=20.0)
    save_to_disk: bool = Field(default=True)

# Criar app FastAPI
app = FastAPI(
    title="Specialized Agents API",
    version="2026.03.15",
    description="Multi-agent system orchestration"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# ROUTERS EXISTENTES (importar de módulos)
# ============================================================================

try:
    from .conube_agent import router as conube_router
    app.include_router(conube_router, prefix="/conube", tags=["conube"])
    logger.info("✅ Conube router carregado")
except ImportError as e:
    logger.warning(f"⚠️  Conube router não disponível: {e}")

try:
    import importlib
    m = importlib.import_module('.agent_communication_bus', package=__package__)
    comm_router = getattr(m, 'router', None)
    activate_agent = getattr(m, 'activate_agent', None)
    get_active_agents = getattr(m, 'get_active_agents', None)
    get_communication_bus = getattr(m, 'get_communication_bus', None)
    if comm_router:
        app.include_router(comm_router, prefix="/communication", tags=["communication"])
        logger.info("✅ Communication router carregado")
    else:
        raise ImportError('communication router not found')
except Exception as e:
    activate_agent = None
    get_active_agents = None
    get_communication_bus = None
    logger.warning(f"⚠️  Communication router não disponível: {e}")

try:
    from .copilot_routes import router as copilot_router
    app.include_router(copilot_router, tags=["copilot"])
    logger.info("✅ Copilot router carregado (modelo com fallback OpenAI-compatible)")
except ImportError as e:
    logger.warning(f"⚠️  Copilot router não disponível: {e}")

try:
    from .huggingface_inference_agent import router as huggingface_router
    app.include_router(huggingface_router, prefix="/huggingface", tags=["huggingface"])
    logger.info("✅ Hugging Face router carregado")
except ImportError as e:
    logger.warning(f"⚠️  Hugging Face router não disponível: {e}")

try:
    from .wiki_agent import router as wiki_router
    app.include_router(wiki_router, prefix="/wiki", tags=["wiki"])
    logger.info("✅ Wiki agent router carregado")
except ImportError as e:
    logger.warning(f"⚠️  Wiki agent router não disponível: {e}")

try:
    from .nextcloud_agent import router as nextcloud_agent_router
    app.include_router(nextcloud_agent_router, prefix="/nextcloud/agent", tags=["nextcloud-agent"])
    logger.info("✅ Nextcloud agent router carregado")
except ImportError as e:
    logger.warning(f"⚠️  Nextcloud agent router não disponível: {e}")

try:
    from .bn_acervo_agent import router as bn_acervo_router
    app.include_router(bn_acervo_router, prefix="/bn-acervo", tags=["bn-acervo"])
    logger.info("✅ BN Acervo agent router carregado")
except ImportError as e:
    logger.warning(f"⚠️  BN Acervo agent router não disponível: {e}")

# ============================================================================
# NOVOS ENDPOINTS: RAG, AGENTS, BANKING
# ============================================================================

# Health check geral
@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check da API."""
    return {
        "status": "ok",
        "service": "specialized-agents-api",
        "version": "2026.03.15"
    }


@app.head("/health")
async def health_check_head() -> dict[str, Any]:
    """Head health check da API."""
    return await health_check()


# ============================================================================
# ORCHESTRATOR (GPU0)
# ============================================================================

orchestrator_router = APIRouter()


def _publish_orchestrator_event(content: str, event: str) -> None:
    """Publica evento do orquestrador no communication bus quando disponível."""
    if get_communication_bus is None:
        return
    try:
        from .agent_communication_bus import MessageType

        bus = get_communication_bus()
        message_type = MessageType.TASK_START if event == "start" else MessageType.TASK_END
        bus.publish(
            message_type=message_type,
            source="orchestrator_gpu0",
            target="huggingface",
            content=content,
            metadata={"event": event, "route": "orchestrator/media"},
        )
    except Exception as exc:
        logger.debug("Falha ao publicar evento do orquestrador no bus: %s", exc)


@orchestrator_router.get("/media/resources")
async def orchestrator_media_resources() -> dict[str, Any]:
    """Retorna recursos de mídia disponíveis através do orquestrador da GPU0."""
    _publish_orchestrator_event("listar recursos de mídia", "start")
    try:
        from .huggingface_inference_agent import get_huggingface_client

        resources = await get_huggingface_client().list_available_resources()
        payload = {
            "orchestrator": "gpu0",
            "service": "diretor",
            "resource_type": "media",
            "provider": "huggingface-inference-api",
            "resources": resources,
        }
        _publish_orchestrator_event("recursos de mídia listados", "end")
        return payload
    except Exception as e:
        logger.error("Orchestrator media resources error: %s", e)
        _publish_orchestrator_event("falha ao listar recursos de mídia", "end")
        raise HTTPException(status_code=500, detail=str(e))


@orchestrator_router.post("/media/image/generate")
async def orchestrator_media_generate_image(payload: OrchestratorImageRequest) -> dict[str, Any]:
    """Gera imagem via orquestrador da GPU0 usando integração Hugging Face."""
    _publish_orchestrator_event(f"gerar imagem: {payload.prompt[:140]}", "start")
    try:
        from .huggingface_inference_agent import HFImageGenerateRequest, get_huggingface_client

        request = HFImageGenerateRequest(
            prompt=payload.prompt,
            model=payload.model,
            negative_prompt=payload.negative_prompt,
            width=payload.width,
            height=payload.height,
            steps=payload.steps,
            guidance_scale=payload.guidance_scale,
            save_to_disk=payload.save_to_disk,
        )
        result = await get_huggingface_client().generate_image(request)
        response = {
            "orchestrator": "gpu0",
            "service": "diretor",
            "provider": "huggingface-inference-api",
            "result": result,
        }
        _publish_orchestrator_event("imagem gerada com sucesso", "end")
        return response
    except Exception as e:
        logger.error("Orchestrator media generate error: %s", e)
        _publish_orchestrator_event("falha na geração de imagem", "end")
        raise HTTPException(status_code=500, detail=str(e))


class OrchestratorTradingConverseRequest(BaseModel):
    """Payload para conversa orquestrada com o Trading Analyst."""

    question: str = Field(min_length=1, max_length=4000)
    profile: str = Field(default="default", max_length=120)
    symbols: list[str] | None = Field(default=None)
    chat_id: str | None = Field(default=None, max_length=64)
    user: str | None = Field(default=None, max_length=200)


@orchestrator_router.post("/trading/converse")
async def orchestrator_trading_converse(
    payload: OrchestratorTradingConverseRequest,
) -> dict[str, Any]:
    """Responde uma pergunta de trading em linguagem natural via orquestrador.

    Delega para o cérebro do Trading Analyst (contexto ao vivo de ``btc.*`` +
    modelo ``trading-analyst``). É a integração usada pelo grupo "BTC Trade
    Agent" do Telegram — a conversa passa SEMPRE pelo orquestrador.
    """
    _publish_orchestrator_event(f"trading converse: {payload.question[:140]}", "start")
    try:
        import asyncio as _asyncio

        from btc_trading_agent.trading_conversation import answer_trading_question

        metadata = {
            "domain": "trading",
            "via": "orchestrator-api",
            "chat_id": payload.chat_id,
            "user": payload.user,
        }
        answer = await _asyncio.to_thread(
            answer_trading_question,
            payload.question,
            symbols=payload.symbols,
            profile=payload.profile,
            metadata=metadata,
        )
        _publish_orchestrator_event("trading converse concluído", "end")
        return {
            "orchestrator": "gpu0",
            "service": "diretor",
            "provider": "trading-analyst",
            "answer": answer,
        }
    except Exception as e:
        logger.error("Orchestrator trading converse error: %s", e)
        _publish_orchestrator_event("falha na conversa de trading", "end")
        raise HTTPException(status_code=500, detail=str(e))


app.include_router(orchestrator_router, prefix="/orchestrator", tags=["orchestrator"])


# ============================================================================
# NEXTCLOUD ACCESS PANEL
# ============================================================================

nextcloud_router = APIRouter()


def _nextcloud_panel_html() -> str:
    """HTML minimo para provisionamento administrativo de acesso ao Nextcloud."""
    return """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Painel Nextcloud RPA4All</title>
  <style>
    :root {
      --bg: #f4efe7;
      --panel: #fffdf9;
      --text: #14213d;
      --muted: #596273;
      --line: #d9d0c3;
      --accent: #0f766e;
      --accent-2: #d97706;
      --danger: #b91c1c;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(217, 119, 6, 0.12), transparent 28%),
        radial-gradient(circle at bottom right, rgba(15, 118, 110, 0.16), transparent 30%),
        var(--bg);
    }
    .wrap {
      max-width: 1040px;
      margin: 0 auto;
      padding: 40px 20px 64px;
    }
    .hero {
      margin-bottom: 24px;
      padding: 28px;
      border: 1px solid var(--line);
      border-radius: 24px;
      background: linear-gradient(135deg, rgba(255,255,255,0.95), rgba(249,244,236,0.95));
    }
    .hero h1 {
      margin: 0 0 10px;
      font-size: clamp(1.8rem, 5vw, 3rem);
      line-height: 1.05;
    }
    .hero p {
      margin: 0;
      max-width: 760px;
      color: var(--muted);
      font-size: 1rem;
    }
    .grid {
      display: grid;
      gap: 24px;
      grid-template-columns: 1.3fr 0.9fr;
    }
    .panel {
      border: 1px solid var(--line);
      border-radius: 24px;
      background: var(--panel);
      padding: 24px;
      box-shadow: 0 18px 48px rgba(20, 33, 61, 0.08);
    }
    .panel h2 {
      margin-top: 0;
      margin-bottom: 16px;
      font-size: 1.2rem;
    }
    label {
      display: block;
      font-size: 0.92rem;
      font-weight: 600;
      margin-bottom: 8px;
    }
    input, textarea {
      width: 100%;
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--text);
      font: inherit;
      margin-bottom: 16px;
    }
    .row {
      display: grid;
      gap: 16px;
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    button {
      width: 100%;
      border: 0;
      border-radius: 999px;
      padding: 14px 20px;
      font: inherit;
      font-weight: 700;
      background: linear-gradient(135deg, var(--accent), #155e75);
      color: #fff;
      cursor: pointer;
    }
    button:disabled {
      opacity: 0.65;
      cursor: wait;
    }
    .hint, .muted {
      color: var(--muted);
      font-size: 0.92rem;
    }
    .card-list {
      display: grid;
      gap: 12px;
    }
    .card {
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px 16px;
      background: #fff;
    }
    .status {
      margin-top: 16px;
      padding: 14px 16px;
      border-radius: 16px;
      display: none;
      white-space: pre-wrap;
    }
    .status.success { display: block; background: rgba(15,118,110,0.10); color: var(--accent); }
    .status.error { display: block; background: rgba(185,28,28,0.10); color: var(--danger); }
    .badge {
      display: inline-block;
      font-size: 0.78rem;
      font-weight: 700;
      letter-spacing: .03em;
      text-transform: uppercase;
      color: var(--accent-2);
      margin-bottom: 10px;
    }
    @media (max-width: 860px) {
      .grid, .row { grid-template-columns: 1fr; }
      .wrap { padding-top: 24px; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div class="badge">Authentik + Nextcloud</div>
      <h1>Painel de criação de acesso ao Nextcloud</h1>
      <p>Este fluxo cria o usuário no Authentik com os grupos certos para o Nextcloud. O provisionamento da conta no Nextcloud acontece automaticamente no primeiro login via OIDC.</p>
    </section>
    <div class="grid">
      <section class="panel">
        <h2>Novo acesso</h2>
        <form id="nextcloud-form">
          <div class="row">
            <div>
              <label for="username">Username</label>
              <input id="username" name="username" required pattern="[A-Za-z0-9._-]{3,64}" placeholder="ex: maria.silva ou maria_silva">
            </div>
            <div>
              <label for="full_name">Nome completo</label>
              <input id="full_name" name="full_name" required placeholder="Maria Silva">
            </div>
          </div>
          <div class="row">
            <div>
              <label for="email">Email</label>
              <input id="email" name="email" type="email" required placeholder="maria@rpa4all.com">
            </div>
            <div>
              <label for="password">Senha inicial</label>
              <input id="password" name="password" type="password" required minlength="8" placeholder="Senha temporária forte">
            </div>
          </div>
          <div class="row">
            <div>
              <label for="manager_username">Gestor responsável</label>
              <input id="manager_username" name="manager_username" placeholder="opcional; gera NC_TEAM_<gestor>">
            </div>
            <div>
              <label for="storage_quota_mb">Quota lógica (MB)</label>
              <input id="storage_quota_mb" name="storage_quota_mb" type="number" min="1000" max="1000000" value="100000">
            </div>
          </div>
          <label for="extra_groups">Grupos adicionais do Authentik</label>
          <input id="extra_groups" name="extra_groups" placeholder="Separar por vírgula. Ex: users,financeiro,NC_TEAM_diretoria">
          <p class="hint">O grupo base configurado para Nextcloud é aplicado automaticamente. Use grupos extras apenas quando precisar de acesso adicional.</p>
          <label style="display:flex;align-items:center;gap:10px;margin:10px 0 18px;">
            <input id="send_welcome_email" name="send_welcome_email" type="checkbox" checked style="width:auto;margin:0;">
            <span>Enviar email de onboarding com link Android e guia do app</span>
          </label>
          <button id="submit-btn" type="submit">Criar acesso ao Nextcloud</button>
          <div id="status" class="status"></div>
        </form>
      </section>
      <aside class="panel">
        <h2>O que este painel faz</h2>
        <div class="card-list">
          <div class="card">
            <strong>1. Cria a identidade</strong>
            <div class="muted">Usuário criado no Authentik com senha inicial e grupos do fluxo Nextcloud.</div>
          </div>
          <div class="card">
            <strong>2. Prepara o OIDC</strong>
            <div class="muted">O Nextcloud consome as claims do Authentik e auto-provisiona a conta no primeiro login.</div>
          </div>
          <div class="card">
            <strong>3. Mantém o acesso rastreável</strong>
            <div class="muted">O repositório já registra o pipeline localmente para auditoria operacional.</div>
          </div>
        </div>
        <p class="hint" style="margin-top:16px;">URL esperada do usuário final: <strong>https://nextcloud.rpa4all.com</strong></p>
      </aside>
    </div>
  </div>
  <script>
    const form = document.getElementById("nextcloud-form");
    const button = document.getElementById("submit-btn");
    const statusBox = document.getElementById("status");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      button.disabled = true;
      statusBox.className = "status";
      statusBox.textContent = "";
      const formData = new FormData(form);
      const payload = {
        username: String(formData.get("username") || "").trim(),
        email: String(formData.get("email") || "").trim(),
        full_name: String(formData.get("full_name") || "").trim(),
        password: String(formData.get("password") || ""),
        manager_username: String(formData.get("manager_username") || "").trim() || null,
        storage_quota_mb: Number(formData.get("storage_quota_mb") || 100000),
        send_welcome_email: Boolean(formData.get("send_welcome_email")),
        extra_groups: String(formData.get("extra_groups") || "")
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
      };
      try {
        const response = await fetch("/nextcloud-access/users", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || data.error || "Falha ao criar acesso");
        }
        statusBox.className = "status success";
        statusBox.textContent =
          "Acesso criado com sucesso.\\n\\n" +
          "Login: " + data.nextcloud.login_url + "\\n" +
          "Grupos: " + (data.nextcloud.groups || []).join(", ") + "\\n" +
          "Etapas: " + JSON.stringify(data.steps || {}, null, 2);
        form.reset();
      } catch (error) {
        statusBox.className = "status error";
        statusBox.textContent = error.message;
      } finally {
        button.disabled = false;
      }
    });
  </script>
</body>
</html>"""


@nextcloud_router.get("/", response_class=HTMLResponse)
@nextcloud_router.get("/panel", response_class=HTMLResponse)
async def nextcloud_access_panel() -> HTMLResponse:
    """Renderiza um painel simples para criar acesso ao Nextcloud."""
    return HTMLResponse(_nextcloud_panel_html())


@nextcloud_router.get("/health")
async def nextcloud_access_health() -> dict[str, Any]:
    """Health check do painel/logica de provisionamento do Nextcloud."""
    return {
        "status": "ok",
        "service": "nextcloud-access-panel",
    }


@nextcloud_router.post("/users")
async def nextcloud_access_create_user(payload: NextcloudUserCreateRequest) -> dict[str, Any]:
    """Cria um usuario no Authentik para auto-provisionamento no Nextcloud."""
    try:
        from .user_management import create_nextcloud_user

        return await create_nextcloud_user(
            username=payload.username,
            email=payload.email,
            full_name=payload.full_name,
            password=payload.password,
            extra_groups=payload.extra_groups,
            manager_username=payload.manager_username,
            storage_quota_mb=payload.storage_quota_mb,
            send_welcome_email=payload.send_welcome_email,
        )
    except Exception as e:
        logger.error("Nextcloud user creation error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


app.include_router(nextcloud_router, prefix="/nextcloud-access", tags=["nextcloud-access"])


# ============================================================================
# RAG (Retrieval-Augmented Generation)
# ============================================================================

rag_router = APIRouter()


@rag_router.get("/index")
async def rag_index() -> dict[str, Any]:
    """Obter índice de documentos RAG."""
    try:
        # TODO: Conectar com RAG backend real
        return {
            "status": "operational",
            "documents": {
                "total": 0,
                "indexed": 0,
                "categories": []
            },
            "last_update": None
        }
    except Exception as e:
        logger.error(f"RAG index error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@rag_router.post("/query")
async def rag_query(query: str, top_k: int = 5) -> dict[str, Any]:
    """Buscar documentos RAG."""
    try:
        # TODO: Implementar retrieval real
        return {
            "query": query,
            "results": [],
            "count": 0
        }
    except Exception as e:
        logger.error(f"RAG query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


app.include_router(rag_router, prefix="/rag", tags=["rag"])

# ============================================================================
# AGENTS (Status centralizador)
# ============================================================================

agents_router = APIRouter()


@agents_router.get("/status")
async def agents_status() -> dict[str, Any]:
    """Status de todos os agentes especializados."""
    try:
        return {
            "agents": {
                "trading": {
                    "status": "unknown",
                    "last_activity": None,
                    "trades_24h": None
                },
                "rag": {
                    "status": "unknown",
                    "documents_indexed": 0
                },
                "communication": {
                    "status": "unknown",
                    "messages_pending": None
                }
            },
            "timestamp": None
        }
    except Exception as e:
        logger.error(f"Agents status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@agents_router.post("/{agent_id}/activate")
async def agents_activate(agent_id: str) -> dict[str, Any]:
    """Ativa um agente em memória para fluxos de integração e smoke tests."""
    try:
        if activate_agent is None:
            raise RuntimeError("communication bus indisponivel")
        active_agents = activate_agent(agent_id)
        return {
            "success": True,
            "agent_id": agent_id,
            "status": "activated",
            "display_name": agent_id.replace("-", " ").replace("_", " ").title(),
            "active_agents": active_agents,
        }
    except Exception as e:
        logger.error(f"Agent activation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@agents_router.get("/{agent_id}/health")
async def agent_health(agent_id: str) -> dict[str, Any]:
    """Health check de um agente específico."""
    try:
        return {
            "agent_id": agent_id,
            "status": "unknown",
            "uptime_seconds": None
        }
    except Exception as e:
        logger.error(f"Agent health error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


app.include_router(agents_router, prefix="/agents", tags=["agents"])


@app.get("/debug/communication/subscribers")
async def debug_communication_subscribers() -> dict[str, Any]:
    """Expõe número de subscribers ativos no communication bus."""
    try:
        if get_communication_bus is None or get_active_agents is None:
            raise RuntimeError("communication bus indisponivel")
        bus = get_communication_bus()
        return {
            "count": len(bus.subscribers),
            "active_agents": get_active_agents(),
        }
    except Exception as e:
        logger.error(f"Communication debug error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# BANKING (Status bancário/financeiro)
# ============================================================================

banking_router = APIRouter()


@banking_router.get("/status")
async def banking_status() -> dict[str, Any]:
    """Status do sistema bancário/financeiro."""
    try:
        return {
            "balance": None,
            "accounts": [],
            "pending_transactions": 0
        }
    except Exception as e:
        logger.error(f"Banking status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


app.include_router(banking_router, prefix="/banking", tags=["banking"])

# ============================================================================
# Outros routers existentes (puxar de pastas)
# ============================================================================

try:
    from .home_automation import router as ha_router
    app.include_router(ha_router, prefix="/home-automation", tags=["home-automation"])
    logger.info("✅ Home Automation router carregado")
except (ImportError, AttributeError) as e:
    logger.debug(f"Home Automation router não disponível: {e}")

try:
    from .banking import router as banking_module_router
    app.include_router(banking_module_router, prefix="/banking-module", tags=["banking-module"])
    logger.info("✅ Banking module router carregado")
except (ImportError, AttributeError) as e:
    logger.debug(f"Banking module router não disponível: {e}")

logger.info("✅ Specialized Agents API initializado com sucesso")


# ============================================================================
# ALERTMANAGER WEBHOOK RECEIVER
# ============================================================================

@app.post("/alerts")
async def alertmanager_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    """Recebe webhooks do Alertmanager. Loga e encaminha ao communication bus."""
    alerts = payload.get("alerts", [])
    for alert in alerts:
        name = alert.get("labels", {}).get("alertname", "unknown")
        status = alert.get("status", "unknown")
        logger.warning("ALERT %s: %s — %s", status.upper(), name, alert.get("annotations", {}).get("summary", ""))
        if get_communication_bus is not None:
            try:
                from .agent_communication_bus import MessageType
                get_communication_bus().publish(
                    message_type=MessageType.ALERT if hasattr(MessageType, "ALERT") else MessageType.TASK_END,
                    source="alertmanager",
                    target="coordinator",
                    content=f"[{status.upper()}] {name}",
                    metadata=alert,
                )
            except Exception as exc:
                logger.debug("Falha ao publicar alerta no bus: %s", exc)
    return {"status": "ok", "received": len(alerts)}
# Temporary recording control endpoints (emergency use)
try:
    @app.post("/recording/pause")
    async def recording_pause():
        if get_communication_bus is None:
            raise HTTPException(status_code=500, detail="communication bus unavailable")
        get_communication_bus().pause_recording()
        return {"success": True, "recording": get_communication_bus().get_stats().get("recording", False)}

    @app.post("/recording/resume")
    async def recording_resume():
        if get_communication_bus is None:
            raise HTTPException(status_code=500, detail="communication bus unavailable")
        get_communication_bus().resume_recording()
        return {"success": True, "recording": get_communication_bus().get_stats().get("recording", False)}

    @app.post("/recording/clear")
    async def recording_clear():
        if get_communication_bus is None:
            raise HTTPException(status_code=500, detail="communication bus unavailable")
        get_communication_bus().clear()
        return {"success": True, "buffer_size": get_communication_bus().get_stats().get("buffer_size")}
except Exception as e:
    logger.warning(f"Recording control endpoints not available: {e}")
